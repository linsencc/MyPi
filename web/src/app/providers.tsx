import { type ReactNode } from "react"

import {
  TooltipProvider,
} from "@/components/ui/tooltip"

/** 根级交互提供者：与页面内容分离，便于按需调整 delay 等参数 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <TooltipProvider delayDuration={280} skipDelayDuration={200}>
      {children}
    </TooltipProvider>
  )
}
