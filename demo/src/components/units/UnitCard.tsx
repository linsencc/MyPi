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
import { cn } from "@/lib/utils"

export const UnitCard = memo(function UnitCard({
  unit,
  disabled,
  rowLocked,
  previewSrc,
  previewFilter,
  onRenderNow,
  onEdit,
}: {
  unit: Unit
  disabled: boolean
  rowLocked: boolean
  previewSrc: (u: Unit) => string
  previewFilter: string
  onRenderNow: (u: Unit) => void
  onEdit: (id: string) => void
}) {
  return (
    <li
      className={cn(
        "group flex aspect-square min-h-0 min-w-0 flex-col overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white/95 shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)] backdrop-blur-[2px]",
        disabled && "opacity-[0.72]"
      )}
    >
      <div className="relative w-full shrink-0 basis-[42%] overflow-hidden bg-slate-100">
        <PreviewFrame
          src={previewSrc(unit)}
          alt={`${unit.name} 缩略预览`}
          imageFilter={previewFilter}
        />
      </div>

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

        <div className="flex shrink-0 items-center justify-end gap-3 pt-0.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full border border-white/50 bg-white/45 text-slate-400/55 shadow-[0_1px_2px_rgb(15_23_42/0.05)] backdrop-blur-md transition-[color,background-color,box-shadow] hover:bg-white/70 hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.07)] disabled:opacity-50"
                disabled={rowLocked}
                aria-label={`立即渲染并优先上墙「${unit.name}」`}
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
                className="h-9 w-9 shrink-0 rounded-full border border-white/50 bg-white/45 text-slate-400/55 shadow-[0_1px_2px_rgb(15_23_42/0.05)] backdrop-blur-md transition-[color,background-color,box-shadow] hover:bg-white/70 hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.07)] disabled:opacity-50"
                disabled={rowLocked}
                aria-label={`编辑间隔或定时刷新「${unit.name}」`}
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
