import { cn } from "@/lib/utils"

/** 大弹窗外壳：内部分段（标题 / 可滚内容 / 底栏）自行加 padding */
export function dialogShell(className?: string) {
  return cn(
    "gap-0 overflow-hidden rounded-[20px] border border-slate-200/90 bg-white p-0 shadow-lg",
    className
  )
}

/** 小型确认类弹窗：内容区自带内边距 */
export function dialogShellCompact(className?: string) {
  return cn("rounded-[20px] border border-slate-200/90 bg-white p-6 shadow-lg", className)
}
