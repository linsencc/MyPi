import { memo } from "react"

import { PreviewFrame } from "@/components/preview/PreviewFrame"
import type { FrameDisplayConfig } from "@/data/frame-config"
import type { Unit } from "@/data/demo-data"
import type { PreviewSrcRole } from "@/hooks/useInkypiSession"
import { cn } from "@/lib/utils"

export const WallPreviewSection = memo(function WallPreviewSection({
  nowOnWall,
  frameConfig,
  previewSrc,
  previewFilter,
}: {
  nowOnWall: Unit | null
  frameConfig: FrameDisplayConfig
  previewSrc: (u: Unit, role?: PreviewSrcRole) => string
  previewFilter: string
}) {
  return (
    <section aria-labelledby="now-playing-heading" className="space-y-4">
      <h2 id="now-playing-heading" className="sr-only">
        画框上正在展示
      </h2>
      {nowOnWall ? (
        <>
          <div className="relative overflow-hidden rounded-[length:var(--radius-surface)]">
            <div
              aria-hidden
              className={cn(
                "pointer-events-none absolute inset-0",
                frameConfig.orientation === "portrait"
                  ? "bg-[radial-gradient(ellipse_95%_72%_at_14%_0%,rgb(148_163_184/0.22),transparent_55%),radial-gradient(ellipse_65%_50%_at_88%_12%,rgb(100_116_139/0.12),transparent_48%),radial-gradient(ellipse_50%_42%_at_48%_96%,rgb(71_85_105/0.08),transparent_52%),linear-gradient(to_bottom,rgb(203_213_225/0.38),rgb(148_163_184/0.09),transparent)]"
                  : "bg-[radial-gradient(ellipse_100%_78%_at_18%_0%,rgb(148_163_184/0.16),transparent_52%),radial-gradient(ellipse_72%_58%_at_90%_20%,rgb(148_163_184/0.1),transparent_46%),radial-gradient(ellipse_52%_44%_at_42%_98%,rgb(100_116_139/0.07),transparent_50%),linear-gradient(to_bottom,rgb(226_232_240/0.42),rgb(241_245_249/0.2),transparent)]"
              )}
            />
            <div aria-hidden className="paper-grain-hero z-[1]" />
            <div className="relative z-10 flex justify-center px-2 py-3 sm:px-3 sm:py-4">
              <div className="flex w-full max-w-[min(100%,980px)] justify-center">
                {frameConfig.orientation === "landscape" ? (
                    <div
                      className={cn(
                        "relative isolate aspect-[4/3] h-[min(34vh,288px)] w-auto max-w-full overflow-hidden rounded-[length:var(--radius-surface)] bg-slate-800/45 [contain:paint]",
                        "shadow-[0_0_0_1px_rgb(255_255_255/0.14),0_2px_6px_rgb(0_0_0/0.16),0_18px_48px_-22px_rgb(0_0_0/0.34),0_44px_112px_-50px_rgb(0_0_0/0.52),inset_0_1px_1px_rgb(255_255_255/0.12),inset_0_12px_40px_rgb(0_0_0/0.18)]"
                      )}
                    >
                    <PreviewFrame
                      src={previewSrc(nowOnWall, "hero")}
                      alt={`${nowOnWall.name} 当前画面预览`}
                      imageFilter={previewFilter}
                    />
                  </div>
                ) : (
                    <div
                      className={cn(
                        "relative isolate aspect-[3/4] h-[min(46vh,380px)] w-auto max-w-full overflow-hidden rounded-[length:var(--radius-surface)] bg-slate-800/45 [contain:paint] sm:h-[min(44vh,360px)]",
                        "shadow-[0_0_0_1px_rgb(255_255_255/0.14),0_2px_6px_rgb(0_0_0/0.16),0_18px_48px_-22px_rgb(0_0_0/0.34),0_44px_112px_-50px_rgb(0_0_0/0.52),inset_0_1px_1px_rgb(255_255_255/0.12),inset_0_12px_40px_rgb(0_0_0/0.18)]"
                      )}
                    >
                    <PreviewFrame
                      src={previewSrc(nowOnWall, "hero")}
                      alt={`${nowOnWall.name} 当前画面预览`}
                      imageFilter={previewFilter}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-[length:var(--radius-surface)] border border-dashed border-slate-200/90 bg-slate-50/60 px-6 py-14 text-center">
          <p className="text-[15px] font-semibold text-slate-800">暂无画框展示内容</p>
          <p className="mx-auto mt-1.5 max-w-sm text-[12px] leading-relaxed text-slate-500">
            启用至少一个绘画节点后，将在此显示预览。
          </p>
        </div>
      )}
    </section>
  )
})
