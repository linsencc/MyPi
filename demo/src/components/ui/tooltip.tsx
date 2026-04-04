import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import * as React from "react"

import { cn } from "@/lib/utils"

const TooltipProvider = TooltipPrimitive.Provider

const Tooltip = TooltipPrimitive.Root

const TooltipTrigger = TooltipPrimitive.Trigger

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        /* 不用半透明+backdrop-blur：易触发合成层灰度抗锯齿，字会比正文「糊」 */
        "z-[240] max-w-[min(18rem,calc(100vw-1.5rem))] rounded-[length:var(--radius-md)] border border-slate-200 bg-white px-3 py-2 text-left text-[12px] leading-snug text-slate-700 shadow-[0_8px_28px_rgb(15_23_42/0.1),0_0_0_1px_rgb(15_23_42/0.04)] subpixel-antialiased",
        className
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }
