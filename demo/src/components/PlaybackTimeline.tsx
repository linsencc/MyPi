import { useMemo } from "react"

import { type RunLog, type Unit } from "@/data/demo-data"
import { cn } from "@/lib/utils"

function parseLogInstant(raw: string): number | null {
  const s = (raw ?? "").trim().replace("T", " ")
  const m = s.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})$/)
  if (!m) return null
  const t = Date.parse(`${m[1]}T${String(m[2]).padStart(2, "0")}:${m[3]}:${m[4]}`)
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
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
}

/** 当年为 M/D，跨年为 Y/M/D */
function formatDatePart(ms: number, nowMs: number): string {
  const d = new Date(ms)
  const mo = d.getMonth() + 1
  const day = d.getDate()
  const y = d.getFullYear()
  const nowY = new Date(nowMs).getFullYear()
  if (y === nowY) return `${mo}/${day}`
  return `${y}/${mo}/${day}`
}

/** 紧接在日期后的语境：今天、明天、周几等 */
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
  unitId: string
  unitName: string
  endMs: number
  ok: boolean
}

type DotKind = "past" | "playing" | "upcoming"

function dotClass(kind: DotKind, ok: boolean): string {
  if (kind === "playing") {
    return cn(
      "h-2.5 w-2.5 rounded-full bg-[var(--color-primary)] shadow-[0_0_0_3px_rgb(0_113_227/0.22)] ring-2 ring-white"
    )
  }
  if (kind === "upcoming") {
    return cn(
      "h-2 w-2 rounded-full border-[1.5px] border-sky-500 bg-sky-50 ring-2 ring-white",
      !ok && "border-amber-500/80 bg-amber-50/90"
    )
  }
  // past
  if (!ok) {
    return "h-2 w-2 rounded-full bg-slate-300 ring-2 ring-white opacity-90"
  }
  return "h-2 w-2 rounded-full bg-slate-300 ring-2 ring-white"
}

const MAX_EVENTS = 6

export function PlaybackTimeline({
  units,
  currentOnWall,
  runLogs,
}: {
  units: Unit[]
  currentOnWall: { id: string; name: string } | null
  runLogs: Record<string, RunLog[]>
}) {
  const nowMs = Date.now()

  const rows = useMemo(() => {
    const list: Row[] = []
    for (const u of units) {
      let i = 0
      for (const log of runLogs[u.id] ?? []) {
        const endMs = parseLogInstant(log.end) ?? parseLogInstant(log.start)
        if (endMs == null) continue
        list.push({
          key: `${u.id}-${log.start}-${log.end}-${i}`,
          unitId: u.id,
          unitName: u.name,
          endMs,
          ok: log.ok,
        })
        i += 1
      }
    }
    list.sort((a, b) => b.endMs - a.endMs)
    return list.slice(0, MAX_EVENTS)
  }, [units, runLogs])

  /** 当前上墙节点在列表中最近一条记录（优先成功）作为「正在展示」与时间锚点 */
  const playingAnchor = useMemo(() => {
    if (!currentOnWall) return null as { endMs: number; key: string } | null
    const forUnit = rows.filter((r) => r.unitId === currentOnWall.id)
    if (forUnit.length === 0) return null
    const hit = forUnit.find((r) => r.ok) ?? forUnit[0]
    return { endMs: hit.endMs, key: hit.key }
  }, [rows, currentOnWall])

  function dotKindForRow(row: Row): DotKind {
    if (!playingAnchor) return "past"
    if (row.key === playingAnchor.key) return "playing"
    if (row.endMs > playingAnchor.endMs) return "upcoming"
    return "past"
  }

  const showEmptyHistory = rows.length === 0

  if (showEmptyHistory && !currentOnWall) {
    return (
      <section className="space-y-5" aria-labelledby="playback-timeline-heading">
        <h2 id="playback-timeline-heading" className="text-lg font-semibold tracking-tight text-slate-900">
          播放时间轴
        </h2>
        <div className="rounded-xl border border-slate-200/90 bg-white px-4 py-8 text-center text-[13px] text-slate-500">
          暂无记录。启用节点并渲染后会显示在这里。
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-5" aria-labelledby="playback-timeline-heading">
      <h2 id="playback-timeline-heading" className="text-lg font-semibold tracking-tight text-slate-900">
        播放时间轴
      </h2>

      <div className="rounded-xl border border-slate-200/90 bg-white">
        {showEmptyHistory ? (
          <p className="px-4 py-6 text-center text-[12px] text-slate-400">暂无历史记录</p>
        ) : (
          <div className="relative max-h-[min(280px,45vh)] overflow-y-auto overscroll-y-contain [scrollbar-gutter:stable]">
            <div
              className="pointer-events-none absolute bottom-3 left-[26px] top-3 z-0 w-px -translate-x-1/2 bg-slate-200"
              aria-hidden
            />
            <ol className="relative z-[1] m-0 list-none">
              {rows.map((row, index) => {
                const iso = new Date(row.endMs).toISOString()
                const datePart = formatDatePart(row.endMs, nowMs)
                const relHint = formatRelativeHint(row.endMs, nowMs)
                const clock = formatClock(row.endMs)
                const kind = dotKindForRow(row)
                return (
                  <li
                    key={row.key}
                    className={cn(
                      "relative flex items-center gap-3 py-2.5 pl-4 pr-3 sm:pl-4",
                      index !== rows.length - 1 && "border-b border-slate-50"
                    )}
                    title={`${datePart} ${relHint} ${clock} · ${row.unitName}`}
                  >
                    <div className="relative z-[1] flex w-5 shrink-0 justify-center">
                      <span
                        className={dotClass(kind, row.ok)}
                        title={
                          kind === "playing"
                            ? "正在展示"
                            : kind === "upcoming"
                              ? "后续播放（时间上晚于当前上墙画面）"
                              : row.ok
                                ? "已播放"
                                : "已结束（失败）"
                        }
                        aria-hidden
                      />
                    </div>
                    <time
                      dateTime={iso}
                      className="inline-flex shrink-0 items-baseline gap-x-1 whitespace-nowrap text-[11px] leading-none tracking-tight text-slate-500 sm:text-xs"
                    >
                      <span>
                        {datePart}
                        <span className="text-slate-400"> {relHint}</span>
                      </span>
                      <span className="text-slate-300/90" aria-hidden>
                        ·
                      </span>
                      <span className="font-mono tabular-nums text-slate-600">{clock}</span>
                    </time>
                    <span className="min-w-0 flex-1 truncate pr-1 text-[13px] text-slate-800">{row.unitName}</span>
                  </li>
                )
              })}
            </ol>
          </div>
        )}
      </div>
    </section>
  )
}
