import { ImageIcon } from "lucide-react"
import { memo, useEffect, useState } from "react"

import { isDataImagePlaceholder } from "@/lib/preview-placeholder"
import { cn } from "@/lib/utils"

export const PreviewFrame = memo(function PreviewFrame({
  src,
  alt,
  imageFilter,
  lightweight = false,
  useViewTransition = true,
  preloadRetry = false,
}: {
  src: string
  alt: string
  imageFilter: string
  lightweight?: boolean
  /** 主预览关闭 View Transition，避免偶发过渡空白帧 */
  useViewTransition?: boolean
  /** PNG 刚落盘时可能短暂 404，预加载失败则带参重试一次 */
  preloadRetry?: boolean
}) {
  const [broken, setBroken] = useState(false)
  const [displaySrc, setDisplaySrc] = useState(src)
  const [previousSrc, setPreviousSrc] = useState<string | null>(null)

  /** 仅随 src / 预加载选项变化；勿把 displaySrc 放入依赖，否则会二次跑 effect、反复 setBroken(false) 与提前 return 打架 */
  useEffect(() => {
    setBroken(false)
    let isCancelled = false
    let retried = false
    /** effect 创建时的上一帧画面，用于过渡底图 */
    const previousDisplay = displaySrc

    const tryLoad = (url: string) => {
      const img = new Image()
      img.src = url
      img.onload = () => {
        if (isCancelled) return

        const update = () => {
          setPreviousSrc(previousDisplay)
          setDisplaySrc(url)
        }

        if (useViewTransition && document.startViewTransition) {
          // @ts-ignore View Transitions API
          document.startViewTransition(update)
        } else {
          update()
        }
      }
      img.onerror = () => {
        if (isCancelled) return
        if (
          preloadRetry &&
          !retried &&
          !url.startsWith("data:") &&
          !url.includes("_preloadRetry=1")
        ) {
          retried = true
          const sep = url.includes("?") ? "&" : "?"
          tryLoad(`${url}${sep}_preloadRetry=1`)
          return
        }
        setDisplaySrc(url)
      }
    }

    tryLoad(src)

    return () => {
      isCancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 故意只在 src 变化时预加载；displaySrc 用闭包上一帧
  }, [src, preloadRetry, useViewTransition])

  const useCssFilter =
    !lightweight && Boolean(imageFilter) && !isDataImagePlaceholder(displaySrc)

  if (broken) {
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-200/90 text-center text-[13px] text-slate-500">
        <ImageIcon className="h-14 w-14 opacity-40 text-slate-400" strokeWidth={1} aria-hidden />
        预览图加载失败，请检查图片地址
      </div>
    )
  }

  const containerStyle = previousSrc
    ? {
        backgroundImage: `url(${previousSrc})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }
    : undefined

  return (
    <div className="absolute inset-0 h-full w-full overflow-hidden" style={containerStyle}>
      <img
        key={displaySrc}
        src={displaySrc}
        alt={alt}
        draggable={false}
        onDragStart={(e) => e.preventDefault()}
        className={cn(
          "absolute inset-0 h-full w-full object-cover object-center select-none",
          "[-webkit-user-drag:none]",
          previousSrc && useViewTransition && "animate-preview-fade-in"
        )}
        style={useCssFilter ? { filter: imageFilter } : undefined}
        loading={lightweight ? "lazy" : "eager"}
        decoding="async"
        onError={() => setBroken(true)}
      />
    </div>
  )
})
