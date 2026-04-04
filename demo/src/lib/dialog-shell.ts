import { cn } from "@/lib/utils"

/** 大弹窗外壳：内部分段（标题 / 可滚内容 / 底栏）自行加 padding */
export function dialogShell(className?: string) {
  return cn(
    "gap-0 overflow-hidden rounded-[length:var(--radius-surface)] border border-white/50 bg-white/85 p-0 shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_24px_64px_-24px_rgb(15_23_42/0.18)] backdrop-blur-xl",
    className
  )
}

/** 小型确认类弹窗：内容区自带内边距 */
export function dialogShellCompact(className?: string) {
  return cn(
    "rounded-[length:var(--radius-surface)] border border-white/50 bg-white/85 p-6 shadow-lg backdrop-blur-xl",
    className
  )
}
