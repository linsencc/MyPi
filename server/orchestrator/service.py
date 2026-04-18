from __future__ import annotations

import os
import threading
import queue
import json
import logging
from pathlib import Path
from collections import deque
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from domain.models import AppConfig, Scene, UpcomingItem, WallState
from orchestrator.next_run import future_fire_times, global_min_next, next_fire_time
from pipeline.wall_show import WallPipeline
from renderers.registry import TemplateRegistry
from storage.stores import load_config, load_schedule_state
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Shanghai")


class WallOrchestrator:
    """Serializes queue mutations; drain runs on a worker so HTTP returns while show() blocks."""

    def __init__(self, pipeline: WallPipeline, registry: TemplateRegistry) -> None:
        self._pipeline = pipeline
        self._registry = registry
        tz_name = os.environ.get("MYPI_TZ", "Asia/Shanghai")
        self._tz = _resolve_tz(tz_name)
        self._immediate: deque[str] = deque()
        self._scheduled: deque[str] = deque()
        self._ephemeral_scenes: dict[str, Scene] = {}
        self._display_lock = threading.Lock()
        self._q_lock = threading.Lock()
        self._q_ready = threading.Condition(self._q_lock)
        self._active_lock = threading.Lock()
        self._display_active_scene_id: str | None = None
        self._scheduler: BackgroundScheduler | None = None
        self._wall_state = WallState()
        self._sse_clients: list[queue.Queue] = []
        self._sse_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None

    @property
    def wall_state(self) -> WallState:
        return self._wall_state

    def bind_scheduler(self, scheduler: BackgroundScheduler) -> None:
        self._scheduler = scheduler

    def add_sse_client(self) -> queue.Queue:
        q = queue.Queue(maxsize=10)
        with self._sse_lock:
            self._sse_clients.append(q)
        return q

    def remove_sse_client(self, q: queue.Queue) -> None:
        with self._sse_lock:
            if q in self._sse_clients:
                self._sse_clients.remove(q)

    def _broadcast_event(self, event_type: str, data: dict) -> None:
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        with self._sse_lock:
            dead = []
            for q in self._sse_clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._sse_clients.remove(q)

    def _ensure_drain_worker(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        def loop() -> None:
            self._drain_worker_loop()

        self._worker_thread = threading.Thread(
            target=loop, daemon=True, name="mypi-wall-drain"
        )
        self._worker_thread.start()

    def _sync_display_fields_and_broadcast(self) -> None:
        """Lock order: _active_lock, then _q_lock (same order everywhere)."""
        with self._active_lock:
            active = self._display_active_scene_id
        with self._q_lock:
            queued = list(self._immediate) + list(self._scheduled)
        ws = self._wall_state
        self._wall_state = WallState(
            current_scene_id=ws.current_scene_id,
            current_scene_name=ws.current_scene_name,
            current_template_id=ws.current_template_id,
            current_preview_url=ws.current_preview_url,
            upcoming=ws.upcoming,
            display_active_scene_id=active,
            queued_display_scene_ids=queued,
        )
        self._broadcast_event(
            "wall_update", self._wall_state.model_dump(mode="json", by_alias=True)
        )

    def enqueue_show_now(self, scene_id: str) -> None:
        with self._q_lock:
            log.info(f"Orchestrator: Enqueued show-now for scene_id={scene_id}")
            self._immediate.append(scene_id)
            self._ensure_drain_worker()
            self._q_ready.notify()
        self._sync_display_fields_and_broadcast()

    def enqueue_ephemeral_scene(self, scene: Scene) -> None:
        with self._q_lock:
            log.info(f"Orchestrator: Enqueued ephemeral show-now for scene_id={scene.id}")
            self._ephemeral_scenes[scene.id] = scene
            self._immediate.append(scene.id)
            self._ensure_drain_worker()
            self._q_ready.notify()
        self._sync_display_fields_and_broadcast()

    def wakeup(self) -> None:
        cfg = load_config()
        st = load_schedule_state()
        last_map = dict(st.get("lastShownAtBySceneId", {}))
        now = datetime.now(UTC)
        now_buffered = now + timedelta(seconds=1)
        due_scenes: list = []
        for sc in cfg.scenes:
            if not sc.enabled:
                continue
            raw = last_map.get(sc.id)
            last = _parse_iso(raw) if raw else None
            nxt = next_fire_time(sc, last, now, self._tz)
            if nxt is not None and nxt <= now_buffered:
                due_scenes.append(sc)
        due_scenes.sort(key=lambda s: (s.tie_break_priority, s.id))

        with self._q_lock:
            for sc in due_scenes:
                log.info(f"Orchestrator: Scheduled scene_id={sc.id} for execution")
                self._scheduled.append(sc.id)
            had_due = bool(due_scenes)
            self._ensure_drain_worker()
            if had_due:
                self._q_ready.notify()

        self._reschedule_alarm()

        st2 = load_schedule_state()
        last_map2 = st2.get("lastShownAtBySceneId", {})
        now_after = datetime.now(UTC)
        self._refresh_wall_state(cfg, last_map2, now_after)

        if had_due:
            self._broadcast_event(
                "wall_update", self._wall_state.model_dump(mode="json", by_alias=True)
            )

    def _drain_worker_loop(self) -> None:
        while True:
            with self._q_lock:
                while not self._immediate and not self._scheduled:
                    self._q_ready.wait()
                if self._immediate:
                    sid = self._immediate.popleft()
                    force = True
                else:
                    sid = self._scheduled.popleft()
                    force = False

            cfg = load_config()
            try:
                self._run_one_scene(sid, cfg, force)
            except Exception:
                log.exception("Orchestrator: drain worker failed for scene_id=%s", sid)

            st2 = load_schedule_state()
            last_map2 = st2.get("lastShownAtBySceneId", {})
            now_after = datetime.now(UTC)
            self._refresh_wall_state(cfg, last_map2, now_after)
            self._reschedule_alarm()
            self._broadcast_event(
                "wall_update", self._wall_state.model_dump(mode="json", by_alias=True)
            )

    def _run_one_scene(self, sid: str, cfg: AppConfig, force: bool) -> None:
        log.info(f"Orchestrator: Preparing to run scene_id={sid} (force={force})")
        with self._q_lock:
            sc = self._ephemeral_scenes.pop(sid, None)
        if sc is None:
            sc = next((x for x in cfg.scenes if x.id == sid), None)
        if sc is None:
            return
        if not sc.enabled and not force:
            return

        with self._active_lock:
            self._display_active_scene_id = sid
        self._sync_display_fields_and_broadcast()

        with self._display_lock:
            run = self._pipeline.run_scene(sc, cfg.frame_tuning, cfg.device_profile)

        with self._active_lock:
            self._display_active_scene_id = None

        if run.ok and run.output_path:
            bn = Path(run.output_path).name
            preview = f"/api/v1/output/{run.id}/{bn}"
            ws = self._wall_state
            self._wall_state = WallState(
                current_scene_id=sc.id,
                current_scene_name=sc.name or sc.template_id,
                current_template_id=sc.template_id,
                current_preview_url=preview,
                upcoming=ws.upcoming,
                display_active_scene_id=None,
                queued_display_scene_ids=ws.queued_display_scene_ids,
            )

    def _refresh_wall_state(self, cfg: AppConfig, last_map: dict, now: datetime) -> None:
        upcoming: list[UpcomingItem] = []
        for sc in cfg.scenes:
            if not sc.enabled:
                continue
            raw = last_map.get(sc.id)
            last = _parse_iso(raw) if raw else None
            nxts = future_fire_times(sc, last, now, self._tz, limit=10, max_hours=24)

            plug = self._registry.get(sc.template_id)
            label = (sc.name or "").strip() or (
                plug.display_name if plug else sc.template_id
            )
            for nxt in nxts:
                upcoming.append(
                    UpcomingItem(scene_id=sc.id, at=nxt.isoformat().replace("+00:00", "Z"), name=label)
                )

        upcoming.sort(key=lambda u: u.at)
        with self._active_lock:
            active = self._display_active_scene_id
        with self._q_lock:
            queued = list(self._immediate) + list(self._scheduled)
        self._wall_state = WallState(
            current_scene_id=self._wall_state.current_scene_id,
            current_scene_name=self._wall_state.current_scene_name,
            current_template_id=self._wall_state.current_template_id,
            current_preview_url=self._wall_state.current_preview_url,
            upcoming=upcoming[:50],
            display_active_scene_id=active,
            queued_display_scene_ids=queued,
        )

    def _reschedule_alarm(self) -> None:
        if self._scheduler is None:
            return
        cfg = load_config()
        st = load_schedule_state()
        last_map = st.get("lastShownAtBySceneId", {})
        now = datetime.now(UTC)
        tmin = global_min_next(cfg.scenes, last_map, now, self._tz)
        job_id = "wall_alarm"
        if tmin is not None:
            log.info(f"Orchestrator: Rescheduled next wakeup for {tmin.isoformat()}")
            trigger = DateTrigger(run_date=tmin)
        else:
            log.info("Orchestrator: Rescheduled next wakeup for +1 hour (no due scenes)")
            trigger = IntervalTrigger(hours=1)
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(job_id, trigger=trigger)
        else:
            self._scheduler.add_job(self.wakeup, trigger, id=job_id, replace_existing=True, misfire_grace_time=None)
