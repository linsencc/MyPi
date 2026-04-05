import { Plus, Play } from "lucide-react"
import { memo } from "react"

import { PreviewFrame } from "@/components/preview/PreviewFrame"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { TemplateMeta } from "@/types/api"
import { cn } from "@/lib/utils"

const TemplateCardThumbnail = memo(function TemplateCardThumbnail({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="relative w-full shrink-0 basis-[42%] overflow-hidden bg-slate-100">
      <PreviewFrame src={src} alt={alt} imageFilter="" lightweight />
    </div>
  )
})

export const TemplateCard = memo(function TemplateCard({
  template,
  previewUrl,
  renderBusy,
  onRenderNow,
  onCreateScene,
}: {
  template: TemplateMeta
  previewUrl: string
  renderBusy: boolean
  onRenderNow: (templateId: string) => void
  onCreateScene: (templateId: string) => void
}) {
  const title = template.displayName || template.templateId

  const handleRenderNow = () => {
    onRenderNow(template.templateId)
  }

  return (
    <li
      className={cn(
        "group flex aspect-square min-h-0 min-w-0 select-none flex-col overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)]"
      )}
    >
      <TemplateCardThumbnail src={previewUrl} alt={`${title} 缩略预览`} />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col justify-end gap-1.5 px-2.5 pb-2 pt-1 sm:gap-2 sm:px-3 sm:pb-2.5 sm:pt-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="min-w-0 cursor-default">
              <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[13px]">
                {title}
              </h3>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[15rem]">
            {title}
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
                aria-label={`立即渲染「${title}」`}
                aria-busy={renderBusy}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={handleRenderNow}
              >
                <Play className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">立即渲染 (基于模版)</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full border border-slate-200/80 bg-white/95 text-slate-400/80 shadow-[0_1px_2px_rgb(15_23_42/0.06)] transition-[color,background-color,box-shadow] hover:bg-white hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.08)]"
                aria-label={`创建场景「${title}」`}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={() => onCreateScene(template.templateId)}
              >
                <Plus className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">创建调度场景</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </li>
  )
})
