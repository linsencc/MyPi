import {
  memo,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  forwardRef,
} from "react"

import type { WallRun, UpcomingItem } from "@/types/api"
import { cn } from "@/lib/utils"

function runEndMs(run: WallRun): number | null {
  const raw = run.finishedAt ?? run.startedAt
  const t = Date.parse(raw)
  return Number.isNaN(t) ? null : t
}

const WEEKDAYS_CN = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"] as const

function startOfLocalDay(ms: number): number {
  const d = new Date(ms)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

function formatClock(ms: number): string {
  const d = new Date(ms)
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`
}

function formatDatePart(ms: number, nowMs: number): string {
  const d = new Date(ms)
  const mo = d.getMonth() + 1
  const day = d.getDate()
  const y = d.getFullYear()
  const nowY = new Date(nowMs).getFullYear()
  if (y === nowY) return `${mo}/${day}`
  return `${y}/${mo}/${day}`
}

function formatRelativeHint(ms: number, nowMs: number): string {
  const dayMs = 86400000
  const eventDay = startOfLocalDay(ms)
  const today = startOfLocalDay(nowMs)
  const diff = Math.round((eventDay - today) / dayMs)

  if (diff === 0) return "今天"
  if (diff === -1) return "昨天"
  if (diff === -2) return "前天"
  if (diff === 1) return "明天"
  if (diff === 2) return "后天"
  return WEEKDAYS_CN[new Date(ms).getDay()]
}

type Row = {
  key: string
  sceneId: string
  sceneName: string
  endMs: number
  ok: boolean
  /** Waiting behind a slow in-progress display refresh (e-ink queue). */
  queuedBehindDisplay?: boolean
}

type DotKind = "past" | "playing" | "upcoming"

const TIMELINE_DOT_RING_PAGE = "ring-2 ring-slate-100"

function dotClass(kind: DotKind, ok: boolean, queuedBehindDisplay: boolean): string {
  const ringPage = TIMELINE_DOT_RING_PAGE
  if (kind === "playing") {
    /* ring 在外层包裹上，避免与 animate-timeline-pulse 的 box-shadow 关键帧互斥 */
    return "block h-3 w-3 rounded-full bg-[var(--color-primary)] animate-timeline-pulse"
  }
  if (kind === "upcoming") {
    if (queuedBehindDisplay) {
      return cn(
        "h-2 w-2 rounded-full border-[1.5px] border-red-500 bg-red-50",
        ringPage
      )
    }
    return cn(
      "h-2 w-2 rounded-full border-[1.5px] border-sky-500 bg-sky-50",
      ringPage,
      !ok && "border-amber-500/80 bg-amber-50/90"
    )
  }
  if (!ok) {
    return cn(
      "h-2 w-2 rounded-full border border-amber-400/45 bg-white/40",
      "ring-1 ring-slate-200/80"
    )
  }
  return cn(
    "h-2 w-2 rounded-full border border-slate-300/55 bg-slate-50/80",
    "ring-1 ring-slate-200/70"
  )
}

const TIMELINE_ROW_MIN_H = "min-h-[2.75rem]"
const TIMELINE_SIX_ROWS_MIN_H = "min-h-[16.5rem]"
const TIMELINE_VIEWPORT_H = "h-[min(17.75rem,45vh)]"
/** 圆点列含 ring 需略宽；左右各 1fr 对称，节点水平居中 */
const TIMELINE_DOT_COL = "2rem" as const
const TIMELINE_GRID_COLS =
  `minmax(0, 1fr) ${TIMELINE_DOT_COL} minmax(0, 1fr)` as const
/** 与 list 同级的轴层：父级有 pr-* 时 50% 会相对整盒宽度，须减右内边距的一半才对齐 ol 内容区中心 */
const TIMELINE_AXIS_LEFT_CLASS =
  "left-[calc(50%-0.25rem)] sm:left-[calc(50%-0.375rem)] lg:left-[calc(50%-0.5rem)]"

/** 与 `.timeline-viewport-mask` 上下渐隐带大致对齐（约 0.85rem） */
const TIMELINE_VIEWPORT_MASK_INSET_PX = 14
/** 时间轴上无滚动手势/触摸等超过此时长后，才自动将激活行滚回中间 */
const TIMELINE_RECENTER_IDLE_MS = 3000

function scrollTimelinePlayingRowToCenter(container: HTMLDivElement): void {
  const activeEl = container.querySelector<HTMLElement>('[data-playing="true"]')
  if (!activeEl) return
  const containerRect = container.getBoundingClientRect()
  const elRect = activeEl.getBoundingClientRect()
  const relativeTop = elRect.top - containerRect.top + container.scrollTop
  const targetTop = relativeTop - container.clientHeight / 2 + elRect.height / 2
  container.scrollTop = targetTop
}

/** 激活行在渐隐/裁切区内，或纵向偏离视口中心超过比例时，需要重新居中 */
function timelinePlayingRowNeedsRecenter(container: HTMLDivElement): boolean {
  const activeEl = container.querySelector<HTMLElement>('[data-playing="true"]')
  if (!activeEl) return false
  const cr = container.getBoundingClientRect()
  const er = activeEl.getBoundingClientRect()
  const inset = TIMELINE_VIEWPORT_MASK_INSET_PX
  const inMaskOrClipped =
    er.top < cr.top + inset || er.bottom > cr.bottom - inset
  const viewMid = (cr.top + cr.bottom) / 2
  const rowMid = (er.top + er.bottom) / 2
  const offCenter =
    Math.abs(rowMid - viewMid) > container.clientHeight * 0.1
  return inMaskOrClipped || offCenter
}

const TimelineRowItem = memo(
  forwardRef<HTMLLIElement, {
    row: Row
    index: number
    totalRows: number
    nowMs: number
    kind: DotKind
  }>(function TimelineRowItem(
    { row, index, totalRows, nowMs, kind },
    ref,
  ) {
    const iso = new Date(row.endMs).toISOString()
    const datePart = formatDatePart(row.endMs, nowMs)
    const relHint = formatRelativeHint(row.endMs, nowMs)
    const clock = formatClock(row.endMs)

    return (
      <li
        ref={ref}
        data-playing={kind === "playing" ? "true" : undefined}
        className={cn("overflow-hidden", kind === "past" && "opacity-[0.93]")}
      >
      <div
        className={cn(
          "grid items-center gap-x-3 gap-y-0 py-1.5",
          TIMELINE_ROW_MIN_H,
          kind === "playing" ? "bg-blue-600/[0.035]" : "hover:bg-slate-200/[0.09]",
          index !== totalRows - 1 && "border-b border-slate-200/[0.14]"
        )}
        style={{ gridTemplateColumns: TIMELINE_GRID_COLS }}
      >
        <time
          dateTime={iso}
          className={cn(
            "inline-flex min-w-0 flex-col items-start gap-px text-left tabular-nums sm:flex-row sm:items-baseline sm:gap-x-1 sm:whitespace-nowrap",
            "shrink-0 justify-self-start text-[13px] leading-snug tracking-tight sm:text-[14px]",
            kind === "playing"
              ? "text-slate-600"
              : kind === "upcoming"
                ? "text-slate-400"
                : "text-slate-400/75"
          )}
        >
          <span className="leading-tight">
            {datePart}
            <span
              className={cn(
                kind === "playing"
                  ? "text-slate-500"
                  : kind === "upcoming"
                    ? "text-slate-400/85"
                    : "text-slate-400/65"
              )}
            >
              {" "}
              {relHint}
            </span>
          </span>
          <span className="inline-flex items-baseline gap-x-1 leading-none">
            <span
              className={cn(
                kind === "playing"
                  ? "text-slate-300"
                  : kind === "upcoming"
                    ? "text-slate-300/70"
                    : "text-slate-300/55"
              )}
              aria-hidden
            >
              ·
            </span>
            <span
              className={cn(
                "font-mono tabular-nums",
                kind === "playing"
                  ? "text-slate-800"
                  : kind === "upcoming"
                    ? "text-slate-500"
                    : "text-slate-500/75"
              )}
            >
              {clock}
            </span>
          </span>
        </time>
        <div className="relative z-[2] flex w-full items-center justify-center self-stretch bg-transparent">
          {kind === "playing" ? (
            <span
              className={cn(
                "relative z-[1] inline-flex shrink-0 rounded-full",
                TIMELINE_DOT_RING_PAGE
              )}
              aria-hidden
            >
              <span
                className={dotClass(kind, row.ok, row.queuedBehindDisplay ?? false)}
              />
            </span>
          ) : (
            <span
              className={cn(
                "relative z-[1]",
                dotClass(kind, row.ok, row.queuedBehindDisplay ?? false),
              )}
              aria-hidden
            />
          )}
        </div>
        <span
          className={cn(
            "min-w-0 pl-0 text-[14px] leading-snug sm:text-[15px]",
            "line-clamp-2 break-keep",
            kind === "playing"
              ? "font-medium text-slate-900"
              : kind === "upcoming"
                ? "text-slate-600"
                : "text-slate-500/95"
          )}
        >
          {row.sceneName}
        </span>
      </div>
    </li>
  )
}))

export function WallRunsTimeline({
  runs,
  upcoming,
  sceneNames,
  currentOnWall,
  queuedDisplaySceneIds = [],
  maxEvents = 30,
}: {
  runs: WallRun[]
  upcoming: UpcomingItem[]
  sceneNames: Record<string, string>
  currentOnWall: { id: string; name: string } | null
  /** Scene IDs waiting behind an in-progress wall refresh. */
  queuedDisplaySceneIds?: string[]
  maxEvents?: number
}) {
  const queueSet = useMemo(
    () => new Set(queuedDisplaySceneIds),
    [queuedDisplaySceneIds],
  )

  const rows = useMemo(() => {
    const list: Row[] = []
    const queueAnchorMs = Date.now()

    // Add upcoming items
    const limitedUpcoming = upcoming.slice(0, 10)
    const upcomingSceneIds = new Set<string>()
    for (const u of limitedUpcoming) {
      const endMs = Date.parse(u.at)
      if (Number.isNaN(endMs)) continue
      upcomingSceneIds.add(u.sceneId)
      list.push({
        key: `upcoming-${u.sceneId}-${u.at}`,
        sceneId: u.sceneId,
        sceneName: u.name || sceneNames[u.sceneId] || u.sceneId,
        endMs,
        ok: true, // Upcoming is assumed ok
        queuedBehindDisplay: queueSet.has(u.sceneId),
      })
    }

    // Add historical runs
    for (const run of runs) {
      const endMs = runEndMs(run)
      if (endMs == null) continue
      list.push({
        key: run.id,
        sceneId: run.sceneId,
        sceneName: run.sceneName || sceneNames[run.sceneId] || run.sceneId,
        endMs,
        ok: run.ok,
      })
    }

    // Show-now queue entries that are not in the upcoming slice
    const maxQueueExtras = 10
    let queueExtras = 0
    for (const qid of queuedDisplaySceneIds) {
      if (upcomingSceneIds.has(qid)) continue
      if (queueExtras >= maxQueueExtras) break
      list.push({
        key: `queue-${qid}`,
        sceneId: qid,
        sceneName: sceneNames[qid] ?? qid,
        endMs: queueAnchorMs,
        ok: true,
        queuedBehindDisplay: true,
      })
      queueExtras += 1
    }

    list.sort((a, b) => b.endMs - a.endMs)
    return list.slice(0, maxEvents)
  }, [runs, upcoming, sceneNames, maxEvents, queuedDisplaySceneIds, queueSet])

  const nowMs = useMemo(() => Date.now(), [rows])

  const playingAnchor = useMemo(() => {
    if (!currentOnWall) return null as { endMs: number; key: string } | null
    // Need to find the latest historical run for the current scene, not upcoming items
    const historyRuns = rows.filter(
      (r) =>
        r.sceneId === currentOnWall.id &&
        !r.key.startsWith("upcoming-") &&
        !r.key.startsWith("queue-"),
    )
    if (historyRuns.length === 0) return null
    const hit = historyRuns.find((r) => r.ok) ?? historyRuns[0]
    return { endMs: hit.endMs, key: hit.key }
  }, [rows, currentOnWall])

  function dotKindForRow(row: Row): DotKind {
    if (row.key.startsWith("upcoming-") || row.key.startsWith("queue-"))
      return "upcoming"
    if (!playingAnchor) return "past"
    if (row.key === playingAnchor.key) return "playing"
    if (row.endMs > playingAnchor.endMs) return "upcoming"
    return "past"
  }

  const showEmptyHistory = rows.length === 0

  const scrollRef = useRef<HTMLDivElement>(null)
  const listContainerRef = useRef<HTMLDivElement>(null)
  /** 为 true 时忽略 scroll，避免程序化 scrollTop 重置「空闲计时」 */
  const timelineProgrammaticScrollRef = useRef(false)
  const [, setOverflowY] = useState(false)

  function scrollTimelinePlayingRowAsSystem(container: HTMLDivElement) {
    timelineProgrammaticScrollRef.current = true
    scrollTimelinePlayingRowToCenter(container)
    requestAnimationFrame(() => {
      timelineProgrammaticScrollRef.current = false
    })
  }

  // Remove centerActiveNode entirely since it's causing scrolling jumpiness

  // Remove resetIdleTimer, clearIdleTimer, and related logic that forces scrolling
  
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el || showEmptyHistory) {
      setOverflowY(false)
      return
    }
    const measure = () => setOverflowY(el.scrollHeight > el.clientHeight + 1)
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [rows, showEmptyHistory])

  // Remove drag/pointer event handling logic since we are just using native scrolling now

  const playingRowIndex = useMemo(() => {
    if (!playingAnchor) return -1
    return rows.findIndex((r) => r.key === playingAnchor.key)
  }, [rows, playingAnchor])

  useLayoutEffect(() => {
    if (!playingAnchor) return
    const container = scrollRef.current
    if (!container) return

    const frame = requestAnimationFrame(() => {
      scrollTimelinePlayingRowAsSystem(container)
    })

    return () => cancelAnimationFrame(frame)
  }, [playingAnchor?.key])

  useEffect(() => {
    const container = scrollRef.current
    if (!container || showEmptyHistory || playingAnchor == null) return

    let idleTimer: ReturnType<typeof setTimeout> | null = null

    const clearIdleTimer = () => {
      if (idleTimer != null) {
        clearTimeout(idleTimer)
        idleTimer = null
      }
    }

    const runIdleRecenter = () => {
      const el = scrollRef.current
      if (!el) return
      if (!timelinePlayingRowNeedsRecenter(el)) return
      scrollTimelinePlayingRowAsSystem(el)
    }

    /** 每次用户手势都取消上一段空闲计时，从「此刻」重新计 3s */
    const rescheduleIdleRecenterFromUserGesture = () => {
      clearIdleTimer()
      idleTimer = setTimeout(() => {
        idleTimer = null
        runIdleRecenter()
      }, TIMELINE_RECENTER_IDLE_MS)
    }

    const onGesture = () => {
      if (timelineProgrammaticScrollRef.current) {
        /* 系统改 scrollTop 触发的 scroll：取消待执行的复位，避免与用户空闲计时打架 */
        clearIdleTimer()
        return
      }
      rescheduleIdleRecenterFromUserGesture()
    }

    const onPointerMove = (e: PointerEvent) => {
      if (e.pointerType === "mouse" && e.buttons === 0) return
      onGesture()
    }

    container.addEventListener("scroll", onGesture, { passive: true })
    container.addEventListener("touchstart", onGesture, { passive: true })
    container.addEventListener("touchmove", onGesture, { passive: true })
    container.addEventListener("pointerdown", onGesture, { passive: true })
    container.addEventListener("pointermove", onPointerMove, { passive: true })
    container.addEventListener("wheel", onGesture, { passive: true })

    return () => {
      clearIdleTimer()
      container.removeEventListener("scroll", onGesture)
      container.removeEventListener("touchstart", onGesture)
      container.removeEventListener("touchmove", onGesture)
      container.removeEventListener("pointerdown", onGesture)
      container.removeEventListener("pointermove", onPointerMove)
      container.removeEventListener("wheel", onGesture)
    }
  }, [playingAnchor?.key, showEmptyHistory])

  const axisLineBackground = useMemo(() => {
    const n = rows.length
    if (n === 0) return "transparent"
    const fadeIn = 5
    const fadeOut = 94
    if (playingRowIndex < 0 || !playingAnchor) {
      return `linear-gradient(180deg,
        transparent 0%,
        rgb(148 163 184 / 0.38) ${fadeIn}%,
        rgb(148 163 184 / 0.48) 50%,
        rgb(148 163 184 / 0.38) ${fadeOut}%,
        transparent 100%)`
    }
    const split = ((playingRowIndex + 0.5) / n) * 100
    const blend = 1.2
    return `linear-gradient(180deg,
      transparent 0%,
      rgb(0 113 227 / 0.22) ${fadeIn}%,
      rgb(0 113 227 / 0.18) ${Math.max(fadeIn + 2, split - blend)}%,
      rgb(0 113 227 / 0.13) ${split}%,
      rgb(148 163 184 / 0.42) ${split}%,
      rgb(148 163 184 / 0.36) ${Math.min(fadeOut - 2, split + blend * 3)}%,
      rgb(148 163 184 / 0.32) ${fadeOut}%,
      transparent 100%)`
  }, [rows.length, playingRowIndex, playingAnchor])

  if (showEmptyHistory && !currentOnWall) {
    return (
      <section className="space-y-3" aria-labelledby="playback-timeline-heading">
        <h2 id="playback-timeline-heading" className="text-lg font-semibold tracking-tight text-slate-900">
          时间轴
        </h2>
        <div className="select-none">
          <p className="py-6 text-center text-[14px] leading-relaxed text-slate-500">
            暂无记录。启用场景并执行「立即上墙」后会显示在这里。
          </p>
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-3" aria-labelledby="playback-timeline-heading">
      <h2 id="playback-timeline-heading" className="text-lg font-semibold tracking-tight text-slate-900">
        时间轴
      </h2>

      <div className="relative select-none">
        {showEmptyHistory ? (
          <div
            className={cn(
              "relative flex items-center justify-center overscroll-y-contain pb-2 pl-4 pr-3 pt-5",
              TIMELINE_VIEWPORT_H
            )}
          >
            <p className="text-center text-[13px] text-slate-400">暂无历史记录</p>
          </div>
        ) : (
          <div
            ref={scrollRef}
            className={cn(
              "timeline-scroll-hide timeline-viewport-mask relative w-full min-w-0 max-w-full touch-pan-y overflow-y-auto overscroll-y-contain pb-2 pl-4 pr-3 pt-5 [contain:layout_paint]",
              TIMELINE_VIEWPORT_H
            )}
          >
            <div
              className="relative w-full min-w-0 max-w-full pr-2 sm:pr-3 lg:pr-4"
              ref={listContainerRef}
            >
              <div
                aria-hidden
                className={cn(
                  "timeline-axis-line pointer-events-none absolute inset-y-0 z-0 w-px -translate-x-1/2",
                  TIMELINE_AXIS_LEFT_CLASS
                )}
                style={{
                  background: axisLineBackground,
                }}
              />
              <ol
                className={cn(
                  "relative z-[1] m-0 w-full min-w-0 max-w-full list-none pb-1",
                  TIMELINE_SIX_ROWS_MIN_H
                )}
              >
                {rows.map((row, index) => (
                  <TimelineRowItem
                    key={row.key}
                    row={row}
                    index={index}
                    totalRows={rows.length}
                    nowMs={nowMs}
                    kind={dotKindForRow(row)}
                  />
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
