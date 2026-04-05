import { Clock } from "lucide-react"
import { useEffect, useState } from "react"

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

function parseHm(raw: string): { h: number; m: number; s: number } {
  const m = (raw ?? "").trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!m) return { h: 9, m: 0, s: 0 }
  let h = Number(m[1])
  let min = Number(m[2])
  let s = m[3] ? Number(m[3]) : 0
  if (Number.isNaN(h) || h < 0 || h > 23) h = 9
  if (Number.isNaN(min) || min < 0 || min > 59) min = 0
  if (Number.isNaN(s) || s < 0 || s > 59) s = 0
  return { h, m: min, s }
}

function formatHm(h: number, m: number, s: number): string {
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
}

function tryParseTyped(s: string): string | null {
  let t = s.trim().replace(/[^\d:]/g, "")
  if (!t) return null
  if (!t.includes(":")) {
    if (t.length === 5 || t.length === 6) {
      t = `${t.slice(0, -4)}:${t.slice(-4, -2)}:${t.slice(-2)}`
    } else if (t.length >= 3) {
      t = `${t.slice(0, -2)}:${t.slice(-2)}`
    }
  }
  const m = t.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!m) return null
  const h = Number(m[1])
  let min = Number(m[2])
  const sec = m[3] ? Number(m[3]) : 0
  if (Number.isNaN(h) || Number.isNaN(min) || h < 0 || h > 23 || min < 0 || min > 59) return null
  if (Number.isNaN(sec) || sec < 0 || sec > 59) return null
  return formatHm(h, min, sec)
}

/**
 * 触发时间：前缀时钟 + 单行 HH:mm:ss 文本输入（无下拉/浮层）。
 * 失焦或 Enter 时解析；非法则恢复为上次有效值。
 */
export function ScheduleTimePicker({
  value,
  onChange,
  className,
  id,
}: {
  value: string
  onChange: (next: string) => void
  className?: string
  id?: string
}) {
  const toDisplay = (v: string) => {
    const { h, m, s } = parseHm(v)
    return formatHm(h, m, s)
  }
  const [draft, setDraft] = useState(() => toDisplay(value))

  useEffect(() => {
    setDraft(toDisplay(value))
  }, [value])

  const commit = () => {
    const next = tryParseTyped(draft)
    if (next) {
      onChange(next)
      setDraft(next)
    } else {
      setDraft(toDisplay(value))
    }
  }

  const hintId = id ? `${id}-hint` : undefined

  const hintText = "24 小时制。可输入 06:30:00 或 063000，精确到秒。"

  return (
    <div className="w-fit max-w-full">
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex h-10 w-fit min-w-[7.5rem] max-w-[11rem] shrink-0 cursor-text items-center gap-2 rounded-[length:var(--radius-md)] border px-2.5 transition-[border-color,background-color,box-shadow] focus-within:border-[#0071e3]/45 focus-within:bg-white focus-within:ring-2 focus-within:ring-[#0071e3]/12",
              className
            )}
          >
            <Clock className="h-3.5 w-3.5 shrink-0 text-slate-400" strokeWidth={2} aria-hidden />
            <input
              id={id}
              type="text"
              inputMode="numeric"
              autoComplete="off"
              spellCheck={false}
              placeholder="09:00:00"
              aria-describedby={hintId}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault()
                  ;(e.target as HTMLInputElement).blur()
                }
              }}
              className="min-w-0 flex-1 border-0 bg-transparent py-0 font-mono text-[13px] tabular-nums text-slate-900 outline-none placeholder:text-slate-400"
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-[16rem]">
          {hintText}
        </TooltipContent>
      </Tooltip>
      <span id={hintId} className="sr-only">
        {hintText}
      </span>
    </div>
  )
}
