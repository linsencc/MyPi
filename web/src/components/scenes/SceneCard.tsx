import { Pencil, Play } from "lucide-react"
import { memo } from "react"

import type { PreviewSrcRole } from "@/components/wall/WallPreviewSection"
import { PreviewFrame } from "@/components/preview/PreviewFrame"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { Scene } from "@/types/api"
import { cn } from "@/lib/utils"

const SceneCardThumbnail = memo(function SceneCardThumbnail({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="relative w-full shrink-0 basis-[42%] overflow-hidden bg-slate-100">
      <PreviewFrame src={src} alt={alt} imageFilter="" lightweight />
    </div>
  )
})

export const SceneCard = memo(function SceneCard({
  scene,
  displayName,
  disabled,
  renderBusy,
  previewSrc,
  onRenderNow,
  onEdit,
}: {
  scene: Scene
  /** 插件展示名（主标题） */
  displayName: string
  disabled: boolean
  renderBusy: boolean
  previewSrc: (s: Scene, role?: PreviewSrcRole) => string
  onRenderNow: (s: Scene) => void
  onEdit: (id: string) => void
}) {
  const trimmedName = (scene.name || "").trim()
  const title = trimmedName || displayName
  const showPluginSubtitle = trimmedName !== "" && trimmedName !== displayName
  const tooltipLines = [title, showPluginSubtitle ? displayName : null, scene.description]
    .filter(Boolean)
    .join("\n")
  const ariaScene = title

  return (
    <li
      className={cn(
        "group flex aspect-square min-h-0 min-w-0 select-none flex-col overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)]",
        disabled && "opacity-[0.72]"
      )}
    >
      <SceneCardThumbnail src={previewSrc(scene, "thumb")} alt={`${title} 缩略预览`} />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col justify-end gap-1.5 px-2.5 pb-2 pt-1 sm:gap-2 sm:px-3 sm:pb-2.5 sm:pt-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="min-w-0 cursor-default">
              <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[13px]">
                <span className="block">{title}</span>
                {showPluginSubtitle ? (
                  <span className="mt-0.5 block text-[11px] font-normal leading-snug text-slate-600">
                    {displayName}
                  </span>
                ) : null}
              </h3>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[15rem] whitespace-pre-line">
            {tooltipLines || title}
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
                aria-label={`立即渲染并优先上墙「${ariaScene}」`}
                aria-busy={renderBusy}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={() => onRenderNow(scene)}
              >
                <Play className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">立即上墙</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0 rounded-full border border-slate-200/80 bg-white/95 text-slate-400/80 shadow-[0_1px_2px_rgb(15_23_42/0.06)] transition-[color,background-color,box-shadow] hover:bg-white hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.08)]"
                aria-label={`编辑场景「${ariaScene}」`}
                onMouseDown={(e) => {
                  if (e.button === 0 && e.detail > 1) e.preventDefault()
                }}
                onClick={() => onEdit(scene.id)}
              >
                <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">编辑</TooltipContent>
          </Tooltip>
        </div>
      </div>
    </li>
  )
})
