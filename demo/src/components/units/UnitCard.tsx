import { Pencil, Play } from "lucide-react"
import { memo } from "react"

import { PreviewFrame } from "@/components/preview/PreviewFrame"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Unit } from "@/data/demo-data"
import type { PreviewSrcRole } from "@/hooks/useInkypiSession"
import { cn } from "@/lib/utils"

/** 与 `unit` 引用解耦：仅 src/alt 变才重绘预览层，减轻连点「立即渲染」时的整区闪动 */
const UnitCardThumbnail = memo(function UnitCardThumbnail({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="relative w-full shrink-0 basis-[42%] overflow-hidden bg-slate-100">
      <PreviewFrame src={src} alt={alt} imageFilter="" lightweight />
    </div>
  )
})

export const UnitCard = memo(function UnitCard({
  unit,
  disabled,
  renderBusy,
  previewSrc,
  onRenderNow,
  onEdit,
}: {
  unit: Unit
  disabled: boolean
  /** 仅「立即渲染」冷却中；勿用于「编辑定时」，避免两枚按钮一起变灰、闪动 */
  renderBusy: boolean
  previewSrc: (u: Unit, role?: PreviewSrcRole) => string
  onRenderNow: (u: Unit) => void
  onEdit: (id: string) => void
}) {
  return (
    <li
      className={cn(
        "group flex aspect-square min-h-0 min-w-0 select-none flex-col overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)]",
        disabled && "opacity-[0.72]"
      )}
    >
      <UnitCardThumbnail src={previewSrc(unit, "thumb")} alt={`${unit.name} 缩略预览`} />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col justify-end gap-1.5 px-2.5 pb-2 pt-1 sm:gap-2 sm:px-3 sm:pb-2.5 sm:pt-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="min-w-0 cursor-default">
              <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[13px]">
                {unit.name}
              </h3>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[15rem] whitespace-pre-line">
            {unit.description ? `${unit.name}\n${unit.description}` : unit.name}
          </TooltipContent>
        </Tooltip>

        <div className="flex shrink-0 touch-manipulation items-center justify-end gap-3 pt-0.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full border border-slate-200/80 bg-white/95 text-slate-400/80 shadow-[0_1px_2px_rgb(15_23_42/0.06)] transition-[color,background-color,box-shadow] hover:bg-white hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.08)] disabled:opacity-50"
                disabled={renderBusy}
                aria-label={`立即渲染并优先上墙「${unit.name}」`}
                aria-busy={renderBusy}
                onMouseDown={(e) => {
                  /* 连点/双击时抑制默认选词，避免选中卡片外标题等正文 */
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={() => onRenderNow(unit)}
              >
                <Play className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">立即渲染</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full border border-slate-200/80 bg-white/95 text-slate-400/80 shadow-[0_1px_2px_rgb(15_23_42/0.06)] transition-[color,background-color,box-shadow] hover:bg-white hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.08)]"
                aria-label={`编辑间隔或定时刷新「${unit.name}」`}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={() => onEdit(unit.id)}
              >
                <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">编辑定时</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </li>
  )
})
