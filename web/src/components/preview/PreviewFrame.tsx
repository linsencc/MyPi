import { ImageIcon } from "lucide-react"
import { memo, useEffect, useState } from "react"

import { isDataImagePlaceholder } from "@/lib/preview-placeholder"
import { cn } from "@/lib/utils"

export const PreviewFrame = memo(function PreviewFrame({
  src,
  alt,
  imageFilter,
  lightweight = false,
}: {
  src: string
  alt: string
  imageFilter: string
  lightweight?: boolean
}) {
  const [broken, setBroken] = useState(false)
  const [displaySrc, setDisplaySrc] = useState(src)
  const [previousSrc, setPreviousSrc] = useState<string | null>(null)
  
  useEffect(() => {
    setBroken(false)
    
    if (src === displaySrc) return
    let isCancelled = false
    
    const img = new Image()
    img.src = src
    img.onload = () => {
      if (isCancelled) return
      
      const update = () => {
        setPreviousSrc(displaySrc)
        setDisplaySrc(src)
      }
      
      // @ts-ignore View Transitions API might not be in all TS definitions
      if (document.startViewTransition) {
        // @ts-ignore
        document.startViewTransition(update)
      } else {
        update()
      }
    }
    img.onerror = () => {
      if (isCancelled) return
      setDisplaySrc(src)
    }
    
    return () => {
      isCancelled = true
    }
  }, [src, displaySrc])
  
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

  const containerStyle = previousSrc ? {
    backgroundImage: `url(${previousSrc})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
  } : undefined

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
          previousSrc && "animate-preview-fade-in"
        )}
        style={useCssFilter ? { filter: imageFilter } : undefined}
        loading={lightweight ? "lazy" : "eager"}
        decoding="async"
        onError={() => setBroken(true)}
      />
    </div>
  )
})
