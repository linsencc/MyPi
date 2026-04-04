import { ChevronDown } from "lucide-react"
import { type RefObject, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { type IntervalTimeUnit, unitLabelCn } from "@/lib/refresh-schedule"
import { cn } from "@/lib/utils"

const UNITS: IntervalTimeUnit[] = ["s", "m", "h"]

const ESTIMATED_MENU_H = 118

export function IntervalUnitSelect({
  value,
  onChange,
  className,
  /** 必须挂在 Radix Dialog Content 内，避免 body 上节点被 inert 导致无法点击 */
  portalRef,
  scrollContainerRef,
  "aria-label": ariaLabel = "间隔单位",
}: {
  value: IntervalTimeUnit
  onChange: (u: IntervalTimeUnit) => void
  className?: string
  portalRef: RefObject<HTMLElement | null>
  scrollContainerRef?: RefObject<HTMLElement | null>
  "aria-label"?: string
}) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0 })
  const listId = useId()

  const reposition = useCallback(() => {
    const trigger = triggerRef.current
    const content = portalRef.current
    if (!trigger || !content) return
    const tr = trigger.getBoundingClientRect()
    const cr = content.getBoundingClientRect()
    const margin = 6
    const h = menuRef.current?.offsetHeight ?? ESTIMATED_MENU_H
    /* 相对对话框可视底边翻转，避免父级 overflow-hidden 裁掉向下展开的面板 */
    const roomBelowInDialog = cr.bottom - tr.bottom - margin - 10
    const roomAboveInDialog = tr.top - cr.top - margin - 10
    const placeBelow = h <= roomBelowInDialog || roomBelowInDialog >= roomAboveInDialog
    const top = placeBelow ? tr.bottom - cr.top + margin : tr.top - cr.top - h - margin
    const left = tr.left - cr.left
    const width = tr.width
    setCoords({ top, left, width })
  }, [portalRef])

  useLayoutEffect(() => {
    if (!open) return
    reposition()
    const id = requestAnimationFrame(() => reposition())
    return () => cancelAnimationFrame(id)
  }, [open, value, reposition])

  useEffect(() => {
    if (!open) return
    const onReposition = () => reposition()
    window.addEventListener("resize", onReposition)
    window.addEventListener("scroll", onReposition, true)
    const sc = scrollContainerRef?.current
    sc?.addEventListener("scroll", onReposition, { passive: true })
    return () => {
      window.removeEventListener("resize", onReposition)
      window.removeEventListener("scroll", onReposition, true)
      sc?.removeEventListener("scroll", onReposition)
    }
  }, [open, reposition, scrollContainerRef])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open])

  /** 冒泡阶段：先让菜单内按钮收到事件，避免误关 / 与 capture 冲突 */
  useEffect(() => {
    if (!open) return
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node
      if (triggerRef.current?.contains(t)) return
      if (menuRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener("pointerdown", onPointer, false)
    return () => document.removeEventListener("pointerdown", onPointer, false)
  }, [open])

  const portalHost = portalRef.current
  const menu =
    open && portalHost ? (
      <div
        ref={menuRef}
        id={listId}
        role="listbox"
        className="pointer-events-auto absolute z-[80] overflow-hidden rounded-[length:var(--radius-md)] border border-slate-200/70 bg-white p-1 shadow-[0_16px_48px_-12px_rgb(15_23_42/0.2),0_0_0_1px_rgb(15_23_42/0.04)]"
        style={{
          top: coords.top,
          left: coords.left,
          minWidth: Math.max(coords.width, 5.75 * 16),
        }}
      >
        {UNITS.map((u) => (
          <button
            key={u}
            type="button"
            role="option"
            aria-selected={value === u}
            onClick={() => {
              onChange(u)
              setOpen(false)
            }}
            className={cn(
              "flex w-full items-center rounded-[length:var(--radius-sm)] px-2.5 py-2 text-left text-[13px] font-medium transition-colors",
              value === u
                ? "bg-sky-500/[0.12] text-[#0071e3]"
                : "text-slate-600 hover:bg-slate-100/90 hover:text-slate-900"
            )}
          >
            {unitLabelCn(u)}
          </button>
        ))}
      </div>
    ) : null

  return (
    <>
      <button
        type="button"
        ref={triggerRef}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          setOpen((o) => {
            const next = !o
            if (next) queueMicrotask(reposition)
            return next
          })
        }}
        className={cn(
          "inline-flex h-10 w-[5.75rem] shrink-0 items-center justify-between gap-1 border px-2.5 text-left text-[13px] font-medium text-slate-900 transition-[border-color,background-color,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/15 focus-visible:ring-offset-0",
          open && "border-[#0071e3]/45 bg-white",
          className
        )}
      >
        <span className="truncate">{unitLabelCn(value)}</span>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")}
          strokeWidth={2}
          aria-hidden
        />
      </button>
      {menu && portalHost ? createPortal(menu, portalHost) : null}
    </>
  )
}
