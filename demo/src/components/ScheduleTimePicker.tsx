import { Clock } from "lucide-react"
import { type RefObject, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { cn } from "@/lib/utils"

const HOURS = Array.from({ length: 24 }, (_, i) => i)
/** 与原生 step=60（按分钟）一致，列表保持可读 */
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5)

function parseHm(raw: string): { h: number; m: number } {
  const m = (raw ?? "").trim().match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return { h: 9, m: 0 }
  let h = Number(m[1])
  let min = Number(m[2])
  if (Number.isNaN(h) || h < 0 || h > 23) h = 9
  if (Number.isNaN(min) || min < 0 || min > 59) min = 0
  min = Math.round(min / 5) * 5
  if (min > 55) min = 55
  return { h, m: min }
}

function formatHm(h: number, m: number): string {
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`
}

export function ScheduleTimePicker({
  value,
  onChange,
  className,
  portalRef,
  scrollContainerRef,
  id,
}: {
  value: string
  onChange: (next: string) => void
  className?: string
  portalRef: RefObject<HTMLElement | null>
  scrollContainerRef?: RefObject<HTMLElement | null>
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const hourScrollRef = useRef<HTMLDivElement>(null)
  const minuteScrollRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0 })
  const panelId = useId()
  const { h: vh, m: vm } = parseHm(value)

  const reposition = useCallback(() => {
    const trigger = triggerRef.current
    const content = portalRef.current
    if (!trigger || !content) return
    const tr = trigger.getBoundingClientRect()
    const cr = content.getBoundingClientRect()
    const margin = 6
    const panelH = 280
    const roomBelowInDialog = cr.bottom - tr.bottom - margin - 10
    const roomAboveInDialog = tr.top - cr.top - margin - 10
    const placeBelow = panelH <= roomBelowInDialog || roomBelowInDialog >= roomAboveInDialog
    const top = placeBelow ? tr.bottom - cr.top + margin : tr.top - cr.top - panelH - margin
    const left = Math.max(8, tr.left - cr.left)
    const width = tr.width
    setCoords({ top, left, width })
  }, [portalRef])

  useLayoutEffect(() => {
    if (!open) return
    reposition()
    const idRaf = requestAnimationFrame(() => reposition())
    return () => cancelAnimationFrame(idRaf)
  }, [open, reposition])

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

  useLayoutEffect(() => {
    if (!open) return
    const hel = hourScrollRef.current?.querySelector<HTMLElement>("[data-time-item-selected='true']")
    const mel = minuteScrollRef.current?.querySelector<HTMLElement>("[data-time-item-selected='true']")
    hel?.scrollIntoView({ block: "center" })
    mel?.scrollIntoView({ block: "center" })
  }, [open, vh, vm])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node
      if (triggerRef.current?.contains(t)) return
      if (panelRef.current?.contains(t)) return
      setOpen(false)
    }
    document.addEventListener("pointerdown", onPointer, false)
    return () => document.removeEventListener("pointerdown", onPointer, false)
  }, [open])

  const pickHour = (h: number) => {
    onChange(formatHm(h, vm))
  }

  const pickMinute = (m: number) => {
    onChange(formatHm(vh, m))
  }

  const portalHost = portalRef.current
  const display = formatHm(vh, vm)

  const panel =
    open && portalHost ? (
      <div
        ref={panelRef}
        id={panelId}
        role="dialog"
        aria-label="选择触发时间"
        className="pointer-events-auto absolute z-[80] w-[min(17.5rem,calc(100vw-2rem))] overflow-hidden rounded-[length:var(--radius-md)] border border-slate-200/70 bg-white/98 p-2 shadow-[0_16px_48px_-12px_rgb(15_23_42/0.2),0_0_0_1px_rgb(15_23_42/0.04)] backdrop-blur-xl"
        style={{
          top: coords.top,
          left: coords.left,
          minWidth: Math.max(coords.width, 200),
        }}
      >
        <div className="flex gap-2">
          <div className="min-w-0 flex-1">
            <div className="pb-1 text-center text-[11px] font-medium tracking-[0.06em] text-[#666666]">时</div>
            <div
              ref={hourScrollRef}
              className="max-h-52 overflow-y-auto overscroll-y-contain rounded-[length:var(--radius-sm)] border border-slate-200/40 bg-slate-50/50 py-1 [scrollbar-color:rgb(148_163_184/0.5)_transparent] [scrollbar-width:thin]"
            >
              {HOURS.map((h) => {
                const sel = h === vh
                return (
                  <button
                    key={h}
                    type="button"
                    data-time-item-selected={sel ? "true" : undefined}
                    onClick={() => pickHour(h)}
                    className={cn(
                      "flex w-full items-center justify-center py-2 font-mono text-[13px] tabular-nums transition-colors",
                      sel
                        ? "bg-sky-500/[0.14] font-semibold text-[#0071e3]"
                        : "text-slate-600 hover:bg-white/90 hover:text-slate-900"
                    )}
                  >
                    {String(h).padStart(2, "0")}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="min-w-0 flex-1">
            <div className="pb-1 text-center text-[11px] font-medium tracking-[0.06em] text-[#666666]">分</div>
            <div
              ref={minuteScrollRef}
              className="max-h-52 overflow-y-auto overscroll-y-contain rounded-[length:var(--radius-sm)] border border-slate-200/40 bg-slate-50/50 py-1 [scrollbar-color:rgb(148_163_184/0.5)_transparent] [scrollbar-width:thin]"
            >
              {MINUTES.map((m) => {
                const sel = m === vm
                return (
                  <button
                    key={m}
                    type="button"
                    data-time-item-selected={sel ? "true" : undefined}
                    onClick={() => pickMinute(m)}
                    className={cn(
                      "flex w-full items-center justify-center py-2 font-mono text-[13px] tabular-nums transition-colors",
                      sel
                        ? "bg-sky-500/[0.14] font-semibold text-[#0071e3]"
                        : "text-slate-600 hover:bg-white/90 hover:text-slate-900"
                    )}
                  >
                    {String(m).padStart(2, "0")}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
        <p className="mt-2 border-t border-slate-200/50 pt-2 text-center text-[11px] text-slate-400">24 小时制 · 每 5 分钟一档</p>
      </div>
    ) : null

  return (
    <>
      <button
        type="button"
        id={id}
        ref={triggerRef}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setOpen((o) => {
            const next = !o
            if (next) queueMicrotask(reposition)
            return next
          })
        }}
        className={cn(
          "flex h-10 w-full items-center justify-between gap-2 border px-3 text-left font-mono text-[13px] tabular-nums text-slate-900 transition-[border-color,background-color,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/15 focus-visible:ring-offset-0",
          open && "border-[#0071e3]/45 bg-white",
          className
        )}
      >
        <span>{display}</span>
        <Clock className="h-4 w-4 shrink-0 text-slate-400" strokeWidth={1.75} aria-hidden />
      </button>
      {panel && portalHost ? createPortal(panel, portalHost) : null}
    </>
  )
}
