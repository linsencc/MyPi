import { useEffect, useRef, useState } from "react"
import { Terminal, Trash2 } from "lucide-react"

import { getSystemLogs } from "@/api/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { dialogShell } from "@/lib/dialog-shell"
import type { SystemLog } from "@/types/api"

export function SystemLogsDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [logs, setLogs] = useState<SystemLog[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    getSystemLogs()
      .then(setLogs)
      .catch(console.error)

    const id = setInterval(() => {
      getSystemLogs()
        .then(setLogs)
        .catch(console.error)
    }, 5000)

    return () => clearInterval(id)
  }, [open])

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs, open])

  const getColor = (level: string) => {
    switch (level) {
      case "ERROR":
      case "CRITICAL":
        return "text-red-600"
      case "WARNING":
        return "text-amber-600"
      default:
        return "text-slate-700"
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={dialogShell("max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-3xl sm:max-w-3xl flex flex-col")}
      >
        <DialogHeader className="shrink-0 border-b border-slate-200/45 px-6 pb-3.5 pt-5 pr-14 text-left">
          <div className="flex items-center gap-2">
            <Terminal strokeWidth={1.5} size={18} className="text-slate-500" />
            <DialogTitle className="text-[17px] font-semibold tracking-tight text-slate-900">
              系统日志
            </DialogTitle>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto bg-slate-50/50 p-4 font-mono text-[13px] text-slate-700 [scrollbar-gutter:stable]">
          {logs.length === 0 ? (
            <div className="italic text-slate-400">暂无日志...</div>
          ) : (
            <div className="space-y-1">
              {logs.map((log, i) => (
                <div
                  key={i}
                  className="break-all rounded px-1.5 py-1 transition-colors hover:bg-slate-100/80"
                >
                  <span className="mr-2 shrink-0 text-slate-400">
                    [{log.timestamp}]
                  </span>
                  <span
                    className={`mr-2 shrink-0 font-semibold ${getColor(
                      log.level
                    )}`}
                  >
                    [{log.level}]
                  </span>
                  <span className="mr-2 shrink-0 text-slate-500">
                    {log.name}:
                  </span>
                  <span className="whitespace-pre-wrap">{log.message}</span>
                </div>
              ))}
              <div ref={bottomRef} className="h-2" />
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-slate-200/50 bg-slate-50/95 px-6 py-3.5">
          <Button
            type="button"
            variant="ghost"
            className="h-9 gap-1.5 rounded-lg px-3 text-[13px] font-medium text-slate-500 hover:bg-red-50 hover:text-red-600"
            onClick={() => setLogs([])}
          >
            <Trash2 size={15} strokeWidth={1.75} />
            清空日志
          </Button>
          <Button
            type="button"
            className="h-10 rounded-lg bg-[#0071e3] px-6 text-[13px] font-semibold text-white shadow-sm hover:bg-[#0068cf] focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
            onClick={() => onOpenChange(false)}
          >
            关闭
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
