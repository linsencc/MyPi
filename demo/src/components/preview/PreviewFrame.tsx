import { Calendar, CloudSun, Monitor } from "lucide-react"
import { memo, useState } from "react"

import { cn } from "@/lib/utils"

function unitAccent(typeKey: string) {
  switch (typeKey) {
    case "image-calendar":
      return { Icon: Calendar, iconClass: "text-violet-500/90" }
    case "output-screen":
      return { Icon: Monitor, iconClass: "text-slate-500/90" }
    default:
      return { Icon: CloudSun, iconClass: "text-sky-500/90" }
  }
}

export const PreviewFrame = memo(function PreviewFrame({
  src,
  alt,
  imageFilter,
  /**
   * 节点网格等多处缩略预览：跳过 CSS filter。多张大图同时 `filter: brightness() contrast()…`
   * 会显著增加合成与重绘成本，导致 hover/滚动不跟手。
   */
  lightweight = false,
}: {
  src: string
  alt: string
  imageFilter: string
  lightweight?: boolean
}) {
  const [broken, setBroken] = useState(false)
  if (broken) {
    const { Icon, iconClass } = unitAccent("image-weather")
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-200/90 text-center text-[13px] text-slate-500">
        <Icon className={cn("h-14 w-14 opacity-40", iconClass)} strokeWidth={1} />
        预览图加载失败，请检查图片地址
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      className={cn(
        "absolute inset-0 h-full w-full object-cover object-center select-none",
        "[-webkit-user-drag:none]"
      )}
      style={lightweight ? undefined : { filter: imageFilter }}
      loading={lightweight ? "lazy" : "eager"}
      decoding="async"
      onError={() => setBroken(true)}
    />
  )
})
