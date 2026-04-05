import { useEffect, useMemo, useRef, useState } from "react"

import { editDialogFieldClass, editDialogLabelClass } from "@/app/edit-dialog-styles"
import { IntervalUnitSelect } from "@/components/IntervalUnitSelect"
import { ScheduleTimePicker } from "@/components/ScheduleTimePicker"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Scene, TemplateMeta } from "@/types/api"
import {
  applyScheduleFormToScene,
  scheduleToFormState,
  validateScheduleForm,
  type SceneScheduleFormState,
} from "@/lib/apply-scene-schedule"
import { dialogShell } from "@/lib/dialog-shell"
import {
  describeRefreshPreview,
  normalizeWeekdaysSelection,
  weekdayShort,
  WEEKDAY_ORDER_UI,
  WEEKDAY_PRESETS,
  type IntervalTimeUnit,
  type RefreshMode,
} from "@/lib/refresh-schedule"
import { cn } from "@/lib/utils"

export function EditSceneDialog({
  open,
  scene,
  templates,
  onOpenChange,
  onSave,
  onDelete,
  onError,
}: {
  open: boolean
  scene: Scene | null
  templates: TemplateMeta[]
  onOpenChange: (open: boolean) => void
  onSave: (next: Scene) => void
  onDelete?: (id: string) => void
  onError: (msg: string) => void
}) {
  const editDialogContentRef = useRef<HTMLDivElement>(null)
  const editDialogScrollRef = useRef<HTMLDivElement>(null)

  const [name, setName] = useState("")

  const [formRefreshMode, setFormRefreshMode] = useState<RefreshMode>("interval")
  const [formIntervalValue, setFormIntervalValue] = useState(5)
  const [formIntervalUnit, setFormIntervalUnit] = useState<IntervalTimeUnit>("m")
  const [formScheduledClock, setFormScheduledClock] = useState("09:00:00")
  const [formWeekdays, setFormWeekdays] = useState<number[]>(() => [...WEEKDAY_PRESETS.daily])

  useEffect(() => {
    if (!open || !scene) return
    const plugLabel =
      templates.find((t) => t.templateId === scene.templateId)?.displayName ?? scene.templateId
    setName((scene.name || "").trim() || plugLabel)
    const sch = scheduleToFormState(scene.schedule)
    setFormRefreshMode(sch.refreshMode)
    setFormIntervalValue(sch.intervalValue)
    setFormIntervalUnit(sch.intervalUnit)
    setFormScheduledClock(sch.scheduledClock)
    setFormWeekdays(sch.weekdays)
  }, [open, scene, templates])

  const pluginDisplayName = useMemo(() => {
    if (!scene) return ""
    return templates.find((t) => t.templateId === scene.templateId)?.displayName ?? scene.templateId
  }, [scene, templates])

  const schedulePreviewText = useMemo(
    () =>
      describeRefreshPreview(
        formRefreshMode,
        formIntervalValue,
        formIntervalUnit,
        formScheduledClock,
        formWeekdays
      ),
    [formRefreshMode, formIntervalValue, formIntervalUnit, formScheduledClock, formWeekdays]
  )

  const toggleWeekday = (d: number) => {
    setFormWeekdays((prev) => {
      const next = new Set(prev)
      if (next.has(d)) next.delete(d)
      else next.add(d)
      return WEEKDAY_ORDER_UI.filter((x) => next.has(x))
    })
  }

  const buildSceneFromForm = (base: Scene): Scene | null => {
    const form: SceneScheduleFormState = {
      refreshMode: formRefreshMode,
      intervalValue: formIntervalValue,
      intervalUnit: formIntervalUnit,
      scheduledClock: formScheduledClock,
      weekdays: formWeekdays,
    }
    const err = validateScheduleForm(form)
    if (err) {
      onError(err)
      return null
    }
    const trimmedName = name.trim()
    if (!trimmedName) {
      onError("请填写场景名称")
      return null
    }
    let next: Scene = {
      ...base,
      name: trimmedName,
      description: base.description,
      enabled: base.enabled,
      templateId: base.templateId,
      templateParams: base.templateParams,
      previewImageUrl: base.previewImageUrl,
      tieBreakPriority: base.tieBreakPriority,
    }
    next = applyScheduleFormToScene(next, form)
    return next
  }

  const handleSave = () => {
    if (!scene) return
    const next = buildSceneFromForm(scene)
    if (!next) return
    onSave(next)
    onOpenChange(false)
  }

  const handleDelete = () => {
    if (!scene || !onDelete) return
    if (!window.confirm(`确定删除「${pluginDisplayName}」？`)) return
    onDelete(scene.id)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        ref={editDialogContentRef}
        className={dialogShell(
          "max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-xl sm:max-w-xl"
        )}
      >
        <DialogHeader className="border-b border-slate-200/45 px-6 pb-3 pt-4 pr-14 text-left">
          <Tooltip>
            <TooltipTrigger asChild>
              <DialogTitle className="truncate text-left text-[17px] font-semibold tracking-tight text-slate-900">
                {scene ? pluginDisplayName : "—"}
              </DialogTitle>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-[min(20rem,calc(100vw-3rem))] break-words">
              编辑绘画模版
            </TooltipContent>
          </Tooltip>
        </DialogHeader>

        <div
          ref={editDialogScrollRef}
          className="max-h-[min(58dvh,560px)] overflow-y-auto px-6 py-3"
        >
          <div className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="scene-name" className={editDialogLabelClass}>
                场景名称
              </Label>
              <Input
                id="scene-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                aria-required
                autoComplete="off"
                className={cn("h-10 font-medium", editDialogFieldClass)}
              />
            </div>

            <div className="border-t border-slate-100 pt-4">
              <span className={editDialogLabelClass}>更新方式</span>
              <div
                className="mt-2 grid grid-cols-2 gap-1 rounded-full bg-slate-100/90 p-1"
                role="group"
                aria-label="更新方式"
              >
                <button
                  type="button"
                  aria-pressed={formRefreshMode === "interval"}
                  onClick={() => setFormRefreshMode("interval")}
                  className={cn(
                    "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                    formRefreshMode === "interval"
                      ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  频率循环
                </button>
                <button
                  type="button"
                  aria-pressed={formRefreshMode === "scheduled"}
                  onClick={() => setFormRefreshMode("scheduled")}
                  className={cn(
                    "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                    formRefreshMode === "scheduled"
                      ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  周期定时
                </button>
              </div>
            </div>

            <div className="grid [&>*]:col-start-1 [&>*]:row-start-1 [&>*]:min-w-0">
              <div
                className={cn(
                  formRefreshMode === "interval" ? "relative z-10" : "invisible pointer-events-none"
                )}
                aria-hidden={formRefreshMode !== "interval"}
                inert={formRefreshMode !== "interval" || undefined}
              >
                <div className="space-y-1.5">
                  <Label htmlFor="f-interval-value" className={editDialogLabelClass}>
                    循环间隔
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      id="f-interval-value"
                      type="number"
                      min={formIntervalUnit === "s" ? 3 : 1}
                      step={1}
                      value={formIntervalValue}
                      onChange={(e) => setFormIntervalValue(Number(e.target.value))}
                      className={cn(
                        "h-10 min-w-0 flex-1 font-mono text-[13px] tabular-nums",
                        editDialogFieldClass
                      )}
                    />
                    <IntervalUnitSelect
                      value={formIntervalUnit}
                      onChange={setFormIntervalUnit}
                      portalRef={editDialogContentRef}
                      scrollContainerRef={editDialogScrollRef}
                      aria-label="间隔单位"
                      className={editDialogFieldClass}
                    />
                  </div>
                </div>
              </div>
              <div
                className={cn(
                  formRefreshMode === "scheduled" ? "relative z-10" : "invisible pointer-events-none"
                )}
                aria-hidden={formRefreshMode !== "scheduled"}
                inert={formRefreshMode !== "scheduled" || undefined}
              >
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="f-clock" className={editDialogLabelClass}>
                      触发时间
                    </Label>
                    <ScheduleTimePicker
                      id="f-clock"
                      value={formScheduledClock}
                      onChange={setFormScheduledClock}
                      className={editDialogFieldClass}
                    />
                  </div>
                  <div className="space-y-2">
                    <span className={editDialogLabelClass}>重复</span>
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.daily))}
                      >
                        每天
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.workweek))}
                      >
                        工作日
                      </button>
                      <button
                        type="button"
                        className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.weekend))}
                      >
                        周末
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-1.5" role="group" aria-label="重复星期">
                      {WEEKDAY_ORDER_UI.map((d) => {
                        const on = formWeekdays.includes(d)
                        return (
                          <button
                            key={d}
                            type="button"
                            aria-label={`周${weekdayShort(d)}`}
                            aria-pressed={on}
                            onClick={() => toggleWeekday(d)}
                            className={cn(
                              "flex h-9 min-w-9 items-center justify-center rounded-full border text-[12px] font-semibold transition-[color,background-color,border-color]",
                              on
                                ? "border-[#0071e3] bg-[#0071e3] text-white shadow-sm"
                                : "border-slate-200/80 bg-white/90 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                            )}
                          >
                            {weekdayShort(d)}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-b-[length:var(--radius-surface)]">
          <div className="border-t border-slate-200/45 bg-slate-100/20 px-6 py-2.5">
            <p className="text-[12px] leading-relaxed text-slate-500">{schedulePreviewText}</p>
          </div>

          <div className="relative z-40 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/50 bg-slate-50/95 px-6 py-3.5">
            {onDelete && scene ? (
              <Button
                type="button"
                variant="ghost"
                className="h-10 rounded-lg px-3 text-[13px] font-medium text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={handleDelete}
              >
                删除场景
              </Button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                className="h-10 rounded-lg px-4 text-[13px] font-medium text-slate-600 hover:bg-slate-200/45 hover:text-slate-900"
                onClick={() => onOpenChange(false)}
              >
                取消
              </Button>
              <Button
                type="button"
                className="h-10 rounded-lg bg-[#0071e3] px-6 text-[13px] font-semibold text-white shadow-sm hover:bg-[#0068cf] focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                onClick={handleSave}
              >
                保存
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
