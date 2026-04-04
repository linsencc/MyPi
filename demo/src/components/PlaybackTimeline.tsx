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
  /* ring 与页面浅灰底衔接 */
  const ringPage = "ring-2 ring-slate-100"
  if (kind === "playing") {
    return cn(
      "h-3 w-3 rounded-full bg-[var(--color-primary)]",
      /* 内圈强调 + 极弱外发光（呼吸感） */
      "shadow-[0_0_0_3px_rgb(0_113_227/0.14),0_0_18px_5px_rgb(0_113_227/0.1),0_0_32px_8px_rgb(0_113_227/0.05),0_0_44px_14px_rgb(0_113_227/0.035)]",
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
  // past：空心 + 淡灰，弱化历史节点
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

const MAX_EVENTS = 6

/** 对称时间轴：左时间 + 中轴（圆点）+ 右内容 */
const TIMELINE_GRID_COLS = "8rem 1.25rem minmax(0, 1fr)" as const
/** 与网格中缝对齐，用于视口底部轴线淡出层 */
const TIMELINE_AXIS_CENTER_LEFT = "calc(1rem + 8rem + 0.625rem)" as const

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

  const playingRowIndex = useMemo(() => {
    if (!playingAnchor) return -1
    return rows.findIndex((r) => r.key === playingAnchor.key)
  }, [rows, playingAnchor])

  /** 单条全局中轴：浅灰 + 锚点以上微蓝；首尾渐隐，避免截断感 */
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
          播放时间轴
        </h2>
        <p className="py-6 text-center text-[13px] leading-relaxed text-slate-500">
          暂无记录。启用节点并渲染后会显示在这里。
        </p>
      </section>
    )
  }

  return (
    <section className="space-y-3" aria-labelledby="playback-timeline-heading">
      <h2 id="playback-timeline-heading" className="text-lg font-semibold tracking-tight text-slate-900">
        播放时间轴
      </h2>

      <div className="relative">
        {showEmptyHistory ? (
          <p className="py-4 text-center text-[12px] text-slate-400">暂无历史记录</p>
        ) : (
          <div className="relative max-h-[min(280px,45vh)] overflow-y-auto overscroll-y-contain pl-4 pr-3 [scrollbar-gutter:stable]">
            {/* 贯穿列表的单条竖线：最底层，圆点叠在上方 */}
            <div
              aria-hidden
              className="pointer-events-none absolute bottom-0 top-0 z-0 w-px -translate-x-1/2"
              style={{
                left: TIMELINE_AXIS_CENTER_LEFT,
                background: axisLineBackground,
              }}
            />
            <ol className="relative z-[1] m-0 list-none pb-1">
              {rows.map((row, index) => {
                const iso = new Date(row.endMs).toISOString()
                const datePart = formatDatePart(row.endMs, nowMs)
                const relHint = formatRelativeHint(row.endMs, nowMs)
                const clock = formatClock(row.endMs)
                const kind = dotKindForRow(row)
                const isPast = kind === "past"
                return (
                  <li
                    key={row.key}
                    className={cn(
                      "grid items-center gap-0 py-1.5",
                      "transition-[background-color,opacity] duration-150 hover:bg-slate-200/[0.09]",
                      isPast && "opacity-[0.93]",
                      index !== rows.length - 1 && "border-b border-slate-200/[0.14]"
                    )}
                    style={{ gridTemplateColumns: TIMELINE_GRID_COLS }}
                    title={`${datePart} ${relHint} ${clock} · ${row.unitName}`}
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
                      <span
                        className={cn("relative z-[1]", dotClass(kind, row.ok))}
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
                      {row.unitName}
                    </span>
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
