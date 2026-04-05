import type { Scene, SceneRefreshMode } from "@/data/demo-data"
import { computeNextScheduledRefresh, formToIntervalSeconds, type IntervalTimeUnit } from "@/lib/refresh-schedule"
import { computeNextRefreshFromInterval } from "@/lib/demo-time"

export type SceneScheduleFormState = {
  refreshMode: SceneRefreshMode
  intervalValue: number
  intervalUnit: IntervalTimeUnit
  scheduledClock: string
  weekdays: number[]
}

/** 校验周期定时表单；失败时返回错误文案 */
export function validateScheduleForm(form: SceneScheduleFormState): string | null {
  if (form.refreshMode !== "scheduled") return null
  if (form.weekdays.length === 0) return "周期定时请至少选择一个星期"
  const probe = computeNextScheduledRefresh(form.scheduledClock.trim(), form.weekdays, new Date())
  if (probe === "—") return "请填写有效的触发时间（时:分）"
  return null
}

export function applyScheduleFormToScene(u: Scene, form: SceneScheduleFormState): Scene {
  if (form.refreshMode === "scheduled") {
    const scheduledClock = form.scheduledClock.trim()
    const scheduledWeekdays = [...form.weekdays]
    const nextRefresh = computeNextScheduledRefresh(scheduledClock, scheduledWeekdays, new Date())
    return {
      ...u,
      refreshMode: "scheduled",
      scheduledClock,
      scheduledWeekdays,
      nextRefresh,
    }
  }
  const intervalSeconds = formToIntervalSeconds(form.intervalValue, form.intervalUnit)
  return {
    ...u,
    refreshMode: "interval",
    intervalSeconds,
    nextRefresh: computeNextRefreshFromInterval(intervalSeconds),
  }
}
