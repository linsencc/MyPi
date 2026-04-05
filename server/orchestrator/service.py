from __future__ import annotations

import os
import threading
from pathlib import Path
from collections import deque
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from domain.models import AppConfig, UpcomingItem, WallState
from orchestrator.next_run import global_min_next, next_fire_time
from pipeline.wall_show import WallPipeline
from renderers.registry import TemplateRegistry
from storage.stores import load_config, load_schedule_state
from zoneinfo import ZoneInfo


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
    """Serializes wakeup / show-now so APScheduler and Flask never race on deques."""

    def __init__(self, pipeline: WallPipeline, registry: TemplateRegistry) -> None:
        self._pipeline = pipeline
        self._registry = registry
        tz_name = os.environ.get("MYPI_TZ", "Asia/Shanghai")
        self._tz = _resolve_tz(tz_name)
        self._immediate: deque[str] = deque()
        self._scheduled: deque[str] = deque()
        self._display_lock = threading.Lock()
        self._wakeup_lock = threading.Lock()
        self._scheduler: BackgroundScheduler | None = None
        self._wall_state = WallState()

    @property
    def wall_state(self) -> WallState:
        return self._wall_state

    def bind_scheduler(self, scheduler: BackgroundScheduler) -> None:
        self._scheduler = scheduler

    def enqueue_show_now(self, scene_id: str) -> None:
        with self._wakeup_lock:
            self._immediate.append(scene_id)
            self._run_wakeup_cycle()

    def wakeup(self) -> None:
        with self._wakeup_lock:
            self._run_wakeup_cycle()

    def _run_wakeup_cycle(self) -> None:
        cfg = load_config()
        st = load_schedule_state()
        last_map = dict(st.get("lastShownAtBySceneId", {}))
        now = datetime.now(UTC)
        due_scenes: list = []
        for sc in cfg.scenes:
            if not sc.enabled:
                continue
            raw = last_map.get(sc.id)
            last = _parse_iso(raw) if raw else None
            nxt = next_fire_time(sc, last, now, self._tz)
            if nxt is not None and nxt <= now:
                due_scenes.append(sc)
        due_scenes.sort(key=lambda s: (s.tie_break_priority, s.id))
        for sc in due_scenes:
            self._scheduled.append(sc.id)
        self._drain_queues(cfg)
        st2 = load_schedule_state()
        last_map2 = st2.get("lastShownAtBySceneId", {})
        now_after = datetime.now(UTC)
        self._refresh_wall_state(cfg, last_map2, now_after)
        self._reschedule_alarm()

    def _drain_queues(self, cfg: AppConfig) -> None:
        def one(sid: str) -> None:
            sc = next((x for x in cfg.scenes if x.id == sid), None)
            if sc is None or not sc.enabled:
                return
            with self._display_lock:
                run = self._pipeline.run_scene(sc, cfg.frame_tuning, cfg.device_profile)
            if run.ok and run.output_path:
                bn = Path(run.output_path).name
                preview = f"/api/v1/output/{run.id}/{bn}"
                self._wall_state = WallState(
                    current_scene_id=sc.id,
                    current_preview_url=preview,
                    upcoming=self._wall_state.upcoming,
                )

        while self._immediate:
            one(self._immediate.popleft())
        while self._scheduled:
            one(self._scheduled.popleft())

    def _refresh_wall_state(self, cfg: AppConfig, last_map: dict, now: datetime) -> None:
        upcoming: list[UpcomingItem] = []
        for sc in cfg.scenes:
            if not sc.enabled:
                continue
            raw = last_map.get(sc.id)
            last = _parse_iso(raw) if raw else None
            nxt = next_fire_time(sc, last, now, self._tz)
            if nxt is not None:
                plug = self._registry.get(sc.template_id)
                label = (sc.name or "").strip() or (
                    plug.display_name if plug else sc.template_id
                )
                upcoming.append(
                    UpcomingItem(scene_id=sc.id, at=nxt.isoformat().replace("+00:00", "Z"), name=label)
                )
        upcoming.sort(key=lambda u: u.at)
        self._wall_state = WallState(
            current_scene_id=self._wall_state.current_scene_id,
            current_preview_url=self._wall_state.current_preview_url,
            upcoming=upcoming[:24],
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
            trigger = DateTrigger(run_date=tmin)
        else:
            trigger = IntervalTrigger(hours=1)
        if self._scheduler.get_job(job_id):
            self._scheduler.reschedule_job(job_id, trigger=trigger)
        else:
            self._scheduler.add_job(self.wakeup, trigger, id=job_id, replace_existing=True)
