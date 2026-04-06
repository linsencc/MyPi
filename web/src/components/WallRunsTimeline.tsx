import {
  memo,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
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
}

type DotKind = "past" | "playing" | "upcoming"

function dotClass(kind: DotKind, ok: boolean): string {
  const ringPage = "ring-2 ring-slate-100"
  if (kind === "playing") {
    return cn(
      "h-3 w-3 rounded-full bg-[var(--color-primary)] animate-timeline-pulse",
      ringPage
    )
  }
  if (kind === "upcoming") {
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

const TIMELINE_ROW_MIN_H = "min-h-[2.625rem]"
const TIMELINE_SIX_ROWS_MIN_H = "min-h-[15.75rem]"
const TIMELINE_VIEWPORT_H = "h-[min(17.75rem,45vh)]"
const TIMELINE_GRID_COLS = "8rem 1.25rem minmax(0, 1fr)" as const
const TIMELINE_AXIS_CENTER_LEFT = "calc(8rem + 0.625rem)" as const

const TimelineRowItem = memo(function TimelineRowItem({
  row,
  index,
  totalRows,
  nowMs,
  kind,
}: {
  row: Row
  index: number
  totalRows: number
  nowMs: number
  kind: DotKind
}) {
  const iso = new Date(row.endMs).toISOString()
  const datePart = formatDatePart(row.endMs, nowMs)
  const relHint = formatRelativeHint(row.endMs, nowMs)
  const clock = formatClock(row.endMs)
  const isPast = kind === "past"

  return (
    <li
      data-playing={kind === "playing" ? "true" : undefined}
      className={cn(
        "grid items-center gap-0 py-1.5 transition-all duration-400 ease-out",
        TIMELINE_ROW_MIN_H,
        kind === "playing" ? "bg-blue-600/[0.035]" : "hover:bg-slate-200/[0.09]",
        isPast && "opacity-[0.93]",
        index !== totalRows - 1 && "border-b border-slate-200/[0.14]"
      )}
      style={{ gridTemplateColumns: TIMELINE_GRID_COLS }}
    >
      <time
        dateTime={iso}
        className={cn(
          "inline-flex flex-col items-end gap-px text-right tabular-nums sm:flex-row sm:items-baseline sm:gap-x-1 sm:whitespace-nowrap",
          "min-w-0 pr-2 text-[11px] leading-snug tracking-tight sm:text-xs",
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
        <span className={cn("relative z-[1]", dotClass(kind, row.ok))} aria-hidden />
      </div>
      <span
        className={cn(
          "min-w-0 truncate pl-2 text-[13px]",
          kind === "playing"
            ? "font-medium text-slate-900"
            : kind === "upcoming"
              ? "text-slate-600"
              : "text-slate-500/95"
        )}
      >
        {row.sceneName}
      </span>
    </li>
  )
})

export function WallRunsTimeline({
  runs,
  upcoming,
  sceneNames,
  currentOnWall,
  maxEvents = 30,
}: {
  runs: WallRun[]
  upcoming: UpcomingItem[]
  sceneNames: Record<string, string>
  currentOnWall: { id: string; name: string } | null
  maxEvents?: number
}) {
  const rows = useMemo(() => {
    const list: Row[] = []
    
    // Add upcoming items
    const limitedUpcoming = upcoming.slice(0, 10)
    for (const u of limitedUpcoming) {
      const endMs = Date.parse(u.at)
      if (Number.isNaN(endMs)) continue
      list.push({
        key: `upcoming-${u.sceneId}-${u.at}`,
        sceneId: u.sceneId,
        sceneName: u.name || sceneNames[u.sceneId] || u.sceneId,
        endMs,
        ok: true, // Upcoming is assumed ok
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

    list.sort((a, b) => b.endMs - a.endMs)
    return list.slice(0, maxEvents)
  }, [runs, upcoming, sceneNames, maxEvents])

  const nowMs = useMemo(() => Date.now(), [rows])

  const playingAnchor = useMemo(() => {
    if (!currentOnWall) return null as { endMs: number; key: string } | null
    // Need to find the latest historical run for the current scene, not upcoming items
    const historyRuns = rows.filter((r) => r.sceneId === currentOnWall.id && !r.key.startsWith('upcoming-'))
    if (historyRuns.length === 0) return null
    const hit = historyRuns.find((r) => r.ok) ?? historyRuns[0]
    return { endMs: hit.endMs, key: hit.key }
  }, [rows, currentOnWall])

  function dotKindForRow(row: Row): DotKind {
    if (row.key.startsWith('upcoming-')) return "upcoming"
    if (!playingAnchor) return "past"
    if (row.key === playingAnchor.key) return "playing"
    if (row.endMs > playingAnchor.endMs) return "upcoming"
    return "past"
  }

  const showEmptyHistory = rows.length === 0

  const scrollRef = useRef<HTMLDivElement>(null)
  const listContainerRef = useRef<HTMLDivElement>(null)
  const isFirstRender = useRef(true)
  const idleTimerRef = useRef<number | null>(null)
  const [overflowY, setOverflowY] = useState(false)

  const centerActiveNode = useCallback((behavior: ScrollBehavior) => {
    const container = scrollRef.current
    if (!container) return
    const activeEl = container.querySelector<HTMLElement>('[data-playing="true"]')
    if (!activeEl) return

    const containerRect = container.getBoundingClientRect()
    const elRect = activeEl.getBoundingClientRect()
    const relativeTop = elRect.top - containerRect.top + container.scrollTop
    const targetTop = relativeTop - container.clientHeight / 2 + elRect.height / 2
    
    container.scrollTo({ top: targetTop, behavior })
  }, [])

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current)
      idleTimerRef.current = null
    }
    if (!scrollRef.current) return
    
    idleTimerRef.current = window.setTimeout(() => {
      const container = scrollRef.current
      if (!container) return
      const activeEl = container.querySelector<HTMLElement>('[data-playing="true"]')
      if (!activeEl) return
      
      const containerRect = container.getBoundingClientRect()
      const elRect = activeEl.getBoundingClientRect()
      
      if (elRect.top < containerRect.top || elRect.bottom > containerRect.bottom) {
        centerActiveNode("smooth")
      }
    }, 3000)
  }, [centerActiveNode])

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current !== null) {
      window.clearTimeout(idleTimerRef.current)
      idleTimerRef.current = null
    }
  }, [])

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

  const dragRef = useRef<{
    pointerId: number | null
    startY: number
    startScroll: number
    dragging: boolean
  }>({ pointerId: null, startY: 0, startScroll: 0, dragging: false })

  useLayoutEffect(() => {
    if (playingAnchor) {
      const behavior = isFirstRender.current ? "auto" : "smooth"
      if (!dragRef.current.dragging) {
        centerActiveNode(behavior)
      }
    }
    isFirstRender.current = false
  }, [playingAnchor?.key, rows, centerActiveNode])

  const onPointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!overflowY || e.button !== 0) return
      if (e.pointerType === "touch") return
      const el = scrollRef.current
      const target = listContainerRef.current
      if (!el || !target) return
      clearIdleTimer()
      dragRef.current = {
        pointerId: e.pointerId,
        startY: e.clientY,
        startScroll: el.scrollTop,
        dragging: false,
      }
      try {
        target.setPointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }
    },
    [overflowY, clearIdleTimer]
  )

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current
    if (d.pointerId !== e.pointerId || !scrollRef.current) return
    const dy = e.clientY - d.startY
    if (!d.dragging && Math.abs(dy) > 6) d.dragging = true
    if (d.dragging) {
      e.preventDefault()
      scrollRef.current.scrollTop = d.startScroll - dy
    }
  }, [])

  const onPointerUp = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const d = dragRef.current
    if (d.pointerId !== e.pointerId) return
    try {
      listContainerRef.current?.releasePointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
    dragRef.current = { pointerId: null, startY: 0, startScroll: 0, dragging: false }
    resetIdleTimer()
  }, [resetIdleTimer])

  const playingRowIndex = useMemo(() => {
    if (!playingAnchor) return -1
    return rows.findIndex((r) => r.key === playingAnchor.key)
  }, [rows, playingAnchor])

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
          <p className="py-6 text-center text-[13px] leading-relaxed text-slate-500">
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
            <p className="text-center text-[12px] text-slate-400">暂无历史记录</p>
          </div>
        ) : (
          <div
            ref={scrollRef}
            onScroll={() => {
              clearIdleTimer()
              if (!dragRef.current.dragging) {
                resetIdleTimer()
              }
            }}
            className={cn(
              "timeline-scroll-hide timeline-viewport-mask relative touch-pan-y overflow-y-auto overscroll-y-contain pb-2 pl-4 pr-3 pt-5 [contain:layout_paint]",
              TIMELINE_VIEWPORT_H
            )}
          >
            <div
              className="relative pr-12 lg:pr-16"
              ref={listContainerRef}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
            >
              <div
                aria-hidden
                className="timeline-axis-line pointer-events-none absolute inset-y-0 z-0 w-px -translate-x-1/2"
                style={{
                  left: TIMELINE_AXIS_CENTER_LEFT,
                  background: axisLineBackground,
                }}
              />
              <ol className={cn("relative z-[1] m-0 list-none pb-1", TIMELINE_SIX_ROWS_MIN_H)}>
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
