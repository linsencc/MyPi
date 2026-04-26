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
    <div className="relative h-full min-h-0 w-full overflow-hidden border-b border-slate-900/[0.06] bg-slate-100">
      <PreviewFrame src={src} alt={alt} imageFilter="" lightweight />
    </div>
  )
})

export const TemplateCard = memo(function TemplateCard({
  template,
  previewUrl,
  renderBusy,
  onPlayTemplate,
  onCreateScene,
}: {
  template: TemplateMeta
  previewUrl: string
  renderBusy: boolean
  onPlayTemplate: (template: TemplateMeta) => void
  onCreateScene: (templateId: string) => void
}) {
  const title = template.displayName || template.templateId

  const handlePlay = () => {
    onPlayTemplate(template)
  }

  return (
    <li
      className={cn(
        "group grid aspect-square min-h-0 min-w-0 grid-rows-2 select-none overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)]"
      )}
    >
      <TemplateCardThumbnail src={previewUrl} alt={`${title} 缩略预览`} />

      <div className="flex h-full min-h-0 min-w-0 flex-col justify-between gap-1.5 px-2.5 pb-2 pt-2 sm:gap-2 sm:px-3 sm:pb-2.5 sm:pt-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="min-h-0 min-w-0 cursor-default">
              <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[13px]">
                {title}
              </h3>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[15rem]">
            {title}
          </TooltipContent>
        </Tooltip>

        <div className="flex shrink-0 touch-manipulation items-center justify-end gap-1.5 sm:gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-md text-slate-500 transition-colors hover:bg-slate-100/85 hover:text-slate-900 disabled:opacity-50"
                disabled={renderBusy}
                aria-label={`立即渲染「${title}」`}
                aria-busy={renderBusy}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={handlePlay}
              >
                <Play className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">立即渲染（基于画框模板）</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-md text-slate-500 transition-colors hover:bg-slate-100/85 hover:text-slate-900"
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
