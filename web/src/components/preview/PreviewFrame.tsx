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
  
  useEffect(() => {
    setBroken(false)
    
    if (src === displaySrc) return
    let isCancelled = false
    
    const img = new Image()
    img.src = src
    img.onload = () => {
      if (isCancelled) return
      
      // @ts-ignore View Transitions API might not be in all TS definitions
      if (!lightweight && document.startViewTransition) {
        // @ts-ignore
        document.startViewTransition(() => {
          setDisplaySrc(src)
        })
      } else {
        setDisplaySrc(src)
      }
    }
    img.onerror = () => {
      if (isCancelled) return
      setDisplaySrc(src)
    }
    
    return () => {
      isCancelled = true
    }
  }, [src, displaySrc, lightweight])
  
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
  return (
    <img
      src={displaySrc}
      alt={alt}
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      className={cn(
        "absolute inset-0 h-full w-full object-cover object-center select-none",
        "[-webkit-user-drag:none]"
      )}
      style={useCssFilter ? { filter: imageFilter } : undefined}
      loading={lightweight ? "lazy" : "eager"}
      decoding="async"
      onError={() => setBroken(true)}
    />
  )
})
