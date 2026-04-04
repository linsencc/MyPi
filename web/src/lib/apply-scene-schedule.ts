import type { Scene, SceneSchedule } from "@/types/api"
import { computeNextRefreshFromInterval } from "@/lib/demo-time"
import {
  computeNextScheduledRefresh,
  formToIntervalSeconds,
  intervalSecondsToForm,
  normalizeWeekdaysSelection,
  WEEKDAY_PRESETS,
  type IntervalTimeUnit,
  type RefreshMode,
} from "@/lib/refresh-schedule"

export type SceneScheduleFormState = {
  refreshMode: RefreshMode
  intervalValue: number
  intervalUnit: IntervalTimeUnit
  scheduledClock: string
  weekdays: number[]
}

export function validateScheduleForm(form: SceneScheduleFormState): string | null {
  if (form.refreshMode !== "scheduled") return null
  if (form.weekdays.length === 0) return "周期定时请至少选择一个星期"
  const probe = computeNextScheduledRefresh(form.scheduledClock.trim(), form.weekdays, new Date())
  if (probe === "—") return "请填写有效的触发时间（时:分）"
  return null
}

function formToSchedule(form: SceneScheduleFormState): SceneSchedule {
  if (form.refreshMode === "scheduled") {
    return {
      type: "cron_weekly",
      time: form.scheduledClock.trim(),
      weekdays: [...form.weekdays],
    }
  }
  return {
    type: "interval",
    intervalSeconds: formToIntervalSeconds(form.intervalValue, form.intervalUnit),
  }
}

export function applyScheduleFormToScene(scene: Scene, form: SceneScheduleFormState): Scene {
  return {
    ...scene,
    schedule: formToSchedule(form),
  }
}

export function scheduleToFormState(schedule: SceneSchedule): SceneScheduleFormState {
  if (schedule.type === "interval") {
    const { value, unit } = intervalSecondsToForm(schedule.intervalSeconds)
    return {
      refreshMode: "interval",
      intervalValue: value,
      intervalUnit: unit,
      scheduledClock: "09:00",
      weekdays: [...WEEKDAY_PRESETS.daily],
    }
  }
  return {
    refreshMode: "scheduled",
    intervalValue: 5,
    intervalUnit: "m",
    scheduledClock: (schedule.time ?? "").trim() || "09:00",
    weekdays: normalizeWeekdaysSelection(schedule.weekdays),
  }
}

export function sceneNextRefreshHint(scene: Scene): string {
  const sch = scene.schedule
  if (sch.type === "interval") {
    return computeNextRefreshFromInterval(sch.intervalSeconds)
  }
  return computeNextScheduledRefresh(sch.time, sch.weekdays, new Date())
}
