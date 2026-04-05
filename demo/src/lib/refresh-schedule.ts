import type { SceneRefreshMode } from "@/data/demo-data"

/** 与 Date.getDay() 一致：0=周日 … 6=周六；界面顺序为 一二三四五六日 */
export type IntervalTimeUnit = "s" | "m" | "h"

export const WEEKDAY_ORDER_UI = [1, 2, 3, 4, 5, 6, 0] as const

const WD_SHORT: Record<number, string> = {
  0: "日",
  1: "一",
  2: "二",
  3: "三",
  4: "四",
  5: "五",
  6: "六",
}

export function weekdayShort(d: number): string {
  return WD_SHORT[d] ?? "?"
}

/** 从「YYYY-MM-DD HH:mm:ss」解析出 HH:mm:ss，失败则默认 09:00:00 */
export function parseClockFromNextRefresh(raw: string): string {
  const s = (raw ?? "").trim().replace("T", " ")
  if (s === "—" || !s) return "09:00:00"
  const m = s.match(/\d{4}-\d{2}-\d{2}\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return "09:00:00"
  return m[3] ? `${m[1].padStart(2, "0")}:${m[2]}:${m[3]}` : `${m[1].padStart(2, "0")}:${m[2]}:00`
}

export function intervalSecondsToForm(sec: number): { value: number; unit: IntervalTimeUnit } {
  const s = Math.max(3, Math.floor(Number(sec)) || 3)
  if (s >= 3600 && s % 3600 === 0) return { value: s / 3600, unit: "h" }
  if (s >= 60 && s % 60 === 0) return { value: s / 60, unit: "m" }
  return { value: s, unit: "s" }
}

export function formToIntervalSeconds(value: number, unit: IntervalTimeUnit): number {
  const v = Math.floor(Number(value)) || 1
  switch (unit) {
    case "h":
      return Math.max(3600, v * 3600)
    case "m":
      return Math.max(60, v * 60)
    default:
      return Math.max(3, v)
  }
}

export function unitLabelCn(unit: IntervalTimeUnit): string {
  switch (unit) {
    case "h":
      return "小时"
    case "m":
      return "分钟"
    default:
      return "秒"
  }
}

/** 下一触发时刻（严格大于 from） */
export function computeNextScheduledRefresh(
  clock: string,
  weekdays: number[],
  from: Date = new Date()
): string {
  const m = (clock ?? "").trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!m || weekdays.length === 0) return "—"
  const hh = Number(m[1])
  const mm = Number(m[2])
  const ss = m[3] ? Number(m[3]) : 0
  if (Number.isNaN(hh) || Number.isNaN(mm) || Number.isNaN(ss) || hh > 23 || mm > 59 || ss > 59) return "—"
  const set = new Set(weekdays)
  const fromMs = from.getTime()

  for (let add = 0; add < 400; add++) {
    const d = new Date(from)
    d.setDate(d.getDate() + add)
    if (!set.has(d.getDay())) continue
    d.setHours(hh, mm, ss, 0)
    if (d.getTime() > fromMs) {
      const y = d.getFullYear()
      const mo = String(d.getMonth() + 1).padStart(2, "0")
      const dy = String(d.getDate()).padStart(2, "0")
      const h = String(d.getHours()).padStart(2, "0")
      const mi = String(d.getMinutes()).padStart(2, "0")
      const s = String(d.getSeconds()).padStart(2, "0")
      return `${y}-${mo}-${dy} ${h}:${mi}:${s}`
    }
  }
  return "—"
}

function formatWeekdayList(days: number[]): string {
  const ordered = [...new Set(days)].sort((a, b) => {
    const ia = WEEKDAY_ORDER_UI.indexOf(a as (typeof WEEKDAY_ORDER_UI)[number])
    const ib = WEEKDAY_ORDER_UI.indexOf(b as (typeof WEEKDAY_ORDER_UI)[number])
    return ia - ib
  })
  return ordered.map((d) => `周${weekdayShort(d)}`).join("、")
}

export function describeRefreshPreview(
  mode: SceneRefreshMode,
  intervalValue: number,
  intervalUnit: IntervalTimeUnit,
  scheduledClock: string,
  scheduledWeekdays: number[]
): string {
  if (mode === "interval") {
    const u = unitLabelCn(intervalUnit)
    const v = Math.max(1, Math.floor(Number(intervalValue)) || 1)
    if (intervalUnit === "s") {
      return `将每隔 ${v} ${u} 自动刷新。`
    }
    return `将每 ${v} ${u} 自动刷新一次。`
  }
  const clock = (scheduledClock ?? "").trim() || "—"
  if (scheduledWeekdays.length === 0) {
    return `请选择至少一个星期；触发时间为 ${clock}。`
  }
  const wd = formatWeekdayList(scheduledWeekdays)
  const all = scheduledWeekdays.length === 7
  if (all) {
    return `将在每天的 ${clock} 自动更新。`
  }
  return `将在${wd}的 ${clock} 自动更新。`
}

export const WEEKDAY_PRESETS = {
  daily: [0, 1, 2, 3, 4, 5, 6] as number[],
  workweek: [1, 2, 3, 4, 5] as number[],
  weekend: [0, 6] as number[],
}

/** 载入表单：按界面顺序排序；空数组视为「每天」 */
export function normalizeWeekdaysSelection(days: number[] | undefined): number[] {
  const s = new Set(days && days.length > 0 ? days : [0, 1, 2, 3, 4, 5, 6])
  return WEEKDAY_ORDER_UI.filter((d) => s.has(d))
}
