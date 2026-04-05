import { CircleHelp } from "lucide-react"
import { type CSSProperties, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  INKYPI_IMAGE_DEFAULTS,
  INKYPI_SLIDER_SPECS,
  type FrameDisplayConfig,
  type InkypiImageSettings,
} from "@/data/frame-config"
import { dialogShell } from "@/lib/dialog-shell"
import { cn } from "@/lib/utils"

export function FrameSettingsDialog({
  open,
  onOpenChange,
  committedConfig,
  onCommit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  committedConfig: FrameDisplayConfig
  onCommit: (next: FrameDisplayConfig) => void
}) {
  const [draft, setDraft] = useState<FrameDisplayConfig>(() => ({
    orientation: committedConfig.orientation,
    imageSettings: { ...committedConfig.imageSettings },
    timelineMaxEvents: committedConfig.timelineMaxEvents ?? 30,
  }))

  useEffect(() => {
    if (!open) return
    setDraft({
      orientation: committedConfig.orientation,
      imageSettings: { ...committedConfig.imageSettings },
      timelineMaxEvents: committedConfig.timelineMaxEvents ?? 30,
    })
  }, [open, committedConfig])

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
    onCommit({
      orientation: draft.orientation,
      imageSettings: { ...draft.imageSettings },
      timelineMaxEvents: draft.timelineMaxEvents,
    })
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
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                水墨屏色彩校对
              </h3>
              <ul className="space-y-5">
                {INKYPI_SLIDER_SPECS.map((spec) => {
                  const v = draft.imageSettings[spec.key]
                  const isDefault = Math.abs(v - spec.defaultValue) < 1e-6
                  const techTip = `${spec.hint} · 默认 ${spec.defaultValue.toFixed(2)}`
                  return (
                    <li key={spec.key} className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`ink-slider-${spec.key}`} className="text-[13px] font-semibold text-slate-800">
                          {spec.label}
                        </Label>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              type="button"
                              className="inline-flex shrink-0 rounded-md text-slate-300 transition-colors hover:bg-slate-100/80 hover:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/30"
                              aria-label={`${spec.label}：技术说明与默认值`}
                            >
                              <CircleHelp className="h-3 w-3" strokeWidth={1.75} aria-hidden />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[16rem]">
                            {techTip}
                          </TooltipContent>
                        </Tooltip>
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
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  aria-label={`${spec.label} 恢复为默认 ${spec.defaultValue.toFixed(2)}`}
                                  className="w-full rounded-md px-1 py-0.5 text-right font-mono text-[12px] text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                                  onClick={() => resetSlider(spec.key)}
                                >
                                  {v.toFixed(2)}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="left">
                                点击恢复默认 {spec.defaultValue.toFixed(2)}
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>

            <section className="space-y-3 border-t border-slate-100 pt-4">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                时间轴设置
              </h3>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label htmlFor="timeline-max-events" className="text-[13px] font-semibold text-slate-800">
                    最大展示条数
                  </Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex shrink-0 rounded-md text-slate-300 transition-colors hover:bg-slate-100/80 hover:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/30"
                        aria-label="时间轴最大展示条数：默认 30"
                      >
                        <CircleHelp className="h-3 w-3" strokeWidth={1.75} aria-hidden />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-[16rem]">
                      限制时间轴最多展示的记录条数，避免记录过多导致加载慢或滚动困难 · 默认 30
                    </TooltipContent>
                  </Tooltip>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    id="timeline-max-events"
                    type="range"
                    min={10}
                    max={100}
                    step={10}
                    value={draft.timelineMaxEvents ?? 30}
                    aria-valuetext={`最大展示 ${draft.timelineMaxEvents ?? 30} 条`}
                    onChange={(e) => {
                      const n = Number(e.target.value)
                      setDraft((d) => ({
                        ...d,
                        timelineMaxEvents: n,
                      }))
                    }}
                    className="ink-range-slider min-w-0 flex-1"
                    style={
                      {
                        "--ink-pct": `${(((draft.timelineMaxEvents ?? 30) - 10) / 90) * 100}%`,
                      } as CSSProperties
                    }
                  />
                  <div className="flex min-w-[2.75rem] shrink-0 items-center justify-end tabular-nums">
                    {(draft.timelineMaxEvents ?? 30) === 30 ? (
                      <span className="w-full text-right font-mono text-[12px] text-slate-500">
                        30
                      </span>
                    ) : (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            aria-label={`恢复为默认 30`}
                            className="w-full rounded-md px-1 py-0.5 text-right font-mono text-[12px] text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                            onClick={() => setDraft(d => ({ ...d, timelineMaxEvents: 30 }))}
                          >
                            {draft.timelineMaxEvents ?? 30}
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="left">
                          点击恢复默认 30
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                </div>
              </div>
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
