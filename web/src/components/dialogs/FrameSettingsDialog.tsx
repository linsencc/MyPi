import { type CSSProperties, useEffect, useState } from "react"
import { ArrowRight } from "lucide-react"

import { editDialogFieldClass, editDialogLabelClass } from "@/app/edit-dialog-styles"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  INKYPI_IMAGE_DEFAULTS,
  INKYPI_SLIDER_SPECS,
  type FrameDisplayConfig,
  type InkypiImageSettings,
} from "@/data/frame-config"
import { dialogShell } from "@/lib/dialog-shell"
import { cn } from "@/lib/utils"
import { ScheduleTimePicker } from "@/components/ScheduleTimePicker"
import { Switch } from "@/components/ui/switch"
import type { QuietHours } from "@/types/api"

/** 与 INKYPI_SLIDER_SPECS 顺序一致，供说明与滑块对照 */
const INK_RECOMMENDED_NUMBERS_LINE = INKYPI_SLIDER_SPECS.map((s) =>
  s.defaultValue.toFixed(2),
).join(" / ")

const DEFAULT_QUIET: QuietHours = {
  enabled: false,
  startLocal: "22:00",
  endLocal: "07:00",
}

function clockHead(s: string): string {
  return (s ?? "").trim().slice(0, 5)
}

export function FrameSettingsDialog({
  open,
  onOpenChange,
  committedConfig,
  committedQuietHours,
  onCommit,
  onNotify,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  committedConfig: FrameDisplayConfig
  committedQuietHours: QuietHours
  onCommit: (next: FrameDisplayConfig, quietHours: QuietHours) => void
  onNotify?: (message: string) => void
}) {
  const qh = committedQuietHours ?? DEFAULT_QUIET
  const [draft, setDraft] = useState<FrameDisplayConfig>(() => ({
    orientation: committedConfig.orientation,
    imageSettings: { ...committedConfig.imageSettings },
  }))
  const [quietDraft, setQuietDraft] = useState<QuietHours>(() => ({ ...qh }))

  useEffect(() => {
    if (!open) return
    setDraft({
      orientation: committedConfig.orientation,
      imageSettings: { ...committedConfig.imageSettings },
    })
    setQuietDraft({ ...(committedQuietHours ?? DEFAULT_QUIET) })
  }, [open, committedConfig, committedQuietHours])

  const resetSlider = (key: keyof InkypiImageSettings) => {
    const spec = INKYPI_SLIDER_SPECS.find((s) => s.key === key)
    if (!spec) return
    setDraft((d) => ({
      ...d,
      imageSettings: { ...d.imageSettings, [key]: spec.defaultValue },
    }))
  }

  const resetAllSliders = () => {
    setDraft((d) => ({
      ...d,
      imageSettings: { ...INKYPI_IMAGE_DEFAULTS },
    }))
  }

  const handleSave = () => {
    if (quietDraft.enabled && clockHead(quietDraft.startLocal) === clockHead(quietDraft.endLocal)) {
      onNotify?.("勿扰开始与结束时间不能相同")
      return
    }
    onCommit(
      {
        orientation: draft.orientation,
        imageSettings: { ...draft.imageSettings },
        timelineMaxEvents: committedConfig.timelineMaxEvents ?? 30,
      },
      quietDraft
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={dialogShell("max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-2xl sm:max-w-2xl")}
      >
        <DialogHeader className="border-b border-slate-200/45 px-6 pb-3.5 pt-5 pr-14 text-left">
          <DialogTitle className="text-[17px] font-semibold tracking-tight text-slate-900">画框设置</DialogTitle>
        </DialogHeader>

        <div className="max-h-[min(66dvh,560px)] overflow-y-auto overscroll-y-contain px-6 py-4 [scrollbar-gutter:stable]">
          <div className="space-y-5">
            <section className="space-y-2">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">画框方向</h3>
              <div
                className="grid grid-cols-2 gap-1 rounded-full bg-slate-100/90 p-1"
                role="group"
                aria-label="画框横竖屏"
              >
                <button
                  type="button"
                  aria-pressed={draft.orientation === "landscape"}
                  onClick={() => setDraft((d) => ({ ...d, orientation: "landscape" }))}
                  className={cn(
                    "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                    draft.orientation === "landscape"
                      ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  横屏
                </button>
                <button
                  type="button"
                  aria-pressed={draft.orientation === "portrait"}
                  onClick={() => setDraft((d) => ({ ...d, orientation: "portrait" }))}
                  className={cn(
                    "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                    draft.orientation === "portrait"
                      ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  竖屏
                </button>
              </div>
            </section>

            <section className="space-y-3 border-t border-slate-100 pt-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                  夜间勿扰
                </h3>
                <Switch
                  checked={quietDraft.enabled}
                  onCheckedChange={(v) => {
                    setQuietDraft((q) => ({ ...q, enabled: v }))
                    if (v) {
                      requestAnimationFrame(() => document.getElementById("quiet-start")?.focus())
                    }
                  }}
                  aria-label="启用夜间勿扰"
                />
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <Label htmlFor="quiet-start" className={editDialogLabelClass}>
                    开始（含）
                  </Label>
                  <ScheduleTimePicker
                    id="quiet-start"
                    value={quietDraft.startLocal}
                    onChange={(next) => setQuietDraft((q) => ({ ...q, startLocal: next }))}
                    disabled={!quietDraft.enabled}
                    wrapperClassName="w-full min-w-0"
                    className={cn(editDialogFieldClass, "min-w-0 w-full max-w-none")}
                  />
                </div>
                <div
                  className="hidden shrink-0 pb-2.5 text-slate-300 sm:flex sm:items-center sm:justify-center sm:self-end"
                  aria-hidden
                >
                  <ArrowRight className="h-4 w-4" strokeWidth={2} />
                </div>
                <div className="min-w-0 flex-1 space-y-1.5">
                  <Label htmlFor="quiet-end" className={editDialogLabelClass}>
                    结束（不含）
                  </Label>
                  <ScheduleTimePicker
                    id="quiet-end"
                    value={quietDraft.endLocal}
                    onChange={(next) => setQuietDraft((q) => ({ ...q, endLocal: next }))}
                    disabled={!quietDraft.enabled}
                    wrapperClassName="w-full min-w-0"
                    className={cn(editDialogFieldClass, "min-w-0 w-full max-w-none")}
                  />
                </div>
              </div>
            </section>

            <section className="space-y-3 border-t border-slate-100 pt-4">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                水墨屏色彩校对
              </h3>
              <p className="text-[12px] leading-relaxed text-slate-500">
                <span className="font-medium text-slate-600">建议设置值</span>
                ：
                <span className="font-mono tabular-nums text-slate-700"> {INK_RECOMMENDED_NUMBERS_LINE} </span>
                （饱和→对比→锐度→亮度→驱动）。保存后与树莓派同步，用于落盘、上屏与主预览。
              </p>
              <ul className="space-y-5">
                {INKYPI_SLIDER_SPECS.map((spec) => {
                  const v = draft.imageSettings[spec.key]
                  const isDefault = Math.abs(v - spec.defaultValue) < 1e-6
                  return (
                    <li key={spec.key} className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`ink-slider-${spec.key}`} className="text-[13px] font-semibold text-slate-800">
                          {spec.label}
                        </Label>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          id={`ink-slider-${spec.key}`}
                          type="range"
                          min={spec.min}
                          max={spec.max}
                          step={spec.step}
                          value={v}
                          aria-valuetext={`${spec.label} ${v.toFixed(2)}`}
                          onChange={(e) => {
                            const n = Number(e.target.value)
                            setDraft((d) => ({
                              ...d,
                              imageSettings: { ...d.imageSettings, [spec.key]: n },
                            }))
                          }}
                          className="ink-range-slider min-w-0 flex-1"
                          style={
                            {
                              "--ink-pct": `${spec.max === spec.min ? 0 : ((v - spec.min) / (spec.max - spec.min)) * 100}%`,
                            } as CSSProperties
                          }
                        />
                        <div className="flex min-w-[2.75rem] shrink-0 items-center justify-end tabular-nums">
                          {isDefault ? (
                            <span className="w-full text-right font-mono text-[12px] text-slate-500">
                              {v.toFixed(2)}
                            </span>
                          ) : (
                            <button
                              type="button"
                              aria-label={`${spec.label} 恢复为默认 ${spec.defaultValue.toFixed(2)}`}
                              className="w-full rounded-md px-1 py-0.5 text-right font-mono text-[12px] text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                              onClick={() => resetSlider(spec.key)}
                            >
                              {v.toFixed(2)}
                            </button>
                          )}
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/50 bg-slate-50/95 px-6 py-3.5">
          <Button
            type="button"
            variant="ghost"
            className="h-9 rounded-lg px-2 text-[12px] font-medium text-slate-500 hover:bg-slate-200/40 hover:text-slate-800"
            onClick={resetAllSliders}
          >
            全部恢复默认
          </Button>
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
      </DialogContent>
    </Dialog>
  )
}
