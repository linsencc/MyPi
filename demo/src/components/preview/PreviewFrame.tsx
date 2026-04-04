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
}: {
  src: string
  alt: string
  imageFilter: string
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
      className="absolute inset-0 h-full w-full object-cover object-center"
      style={{ filter: imageFilter }}
      loading="eager"
      onError={() => setBroken(true)}
    />
  )
})
