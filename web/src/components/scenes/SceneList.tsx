import { Pencil, Power, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { Scene, TemplateMeta } from "@/types/api"
import { scheduleToFormState } from "@/lib/apply-scene-schedule"
import { describeRefreshPreview } from "@/lib/refresh-schedule"
import { cn } from "@/lib/utils"

function describeSchedule(scene: Scene) {
  const f = scheduleToFormState(scene.schedule)
  return describeRefreshPreview(f.refreshMode, f.intervalValue, f.intervalUnit, f.scheduledClock, f.weekdays)
}

/** 三枚操作按钮占位，与表头「操作」列对齐 */
const ACTIONS_COL_CLASS = "w-[6.75rem] shrink-0"

export function SceneList({
  scenes,
  templates,
  onToggle,
  onEdit,
  onDelete,
}: {
  scenes: Scene[]
  templates: TemplateMeta[]
  onToggle: (scene: Scene, enabled: boolean) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
}) {
  const tMap = Object.fromEntries(templates.map((t) => [t.templateId, t]))

  if (scenes.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-[length:var(--radius-surface)] border border-dashed border-slate-200 bg-slate-50/50">
        <p className="text-[13px] text-slate-500">暂无场景实例</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-200/60 bg-white shadow-sm">
      <div className="hidden border-b border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[12px] font-medium text-slate-500 sm:flex sm:items-center sm:gap-4">
        <div className="w-44 shrink-0">场景</div>
        <div className="min-w-0 flex-1">调度规则</div>
        <div className={`${ACTIONS_COL_CLASS} text-center`}>操作</div>
      </div>

      <ul className="divide-y divide-slate-100/80">
        {scenes.map((s) => {
          const t = tMap[s.templateId]
          const title = (s.name || s.templateId).trim()
          const templateLabel = (t?.displayName || s.templateId).trim()
          const showTemplateHint = templateLabel !== title

          return (
            <li key={s.id}>
              <div className="flex flex-col gap-3 px-4 py-3.5 transition-colors hover:bg-slate-50/40 sm:flex-row sm:items-center sm:gap-4 sm:py-3">
                <div className="min-w-0 sm:w-44 sm:shrink-0">
                  <div className="font-medium leading-snug text-slate-900">{title}</div>
                  {showTemplateHint ? (
                    <div className="mt-0.5 text-[11px] leading-snug text-slate-500">{templateLabel}</div>
                  ) : null}
                </div>

                <p className="text-[13px] leading-relaxed text-slate-600 sm:min-w-0 sm:flex-1">{describeSchedule(s)}</p>

                <div className={`flex ${ACTIONS_COL_CLASS} items-center justify-end gap-0.5 sm:justify-center`}>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "h-8 w-8 hover:text-slate-900",
                      s.enabled
                        ? "text-sky-600 hover:bg-sky-50 hover:text-sky-700"
                        : "text-slate-400 hover:bg-slate-100"
                    )}
                    aria-label={s.enabled ? `禁用「${title}」` : `启用「${title}」`}
                    aria-pressed={s.enabled}
                    onClick={() => onToggle(s, !s.enabled)}
                  >
                    <Power className="h-3.5 w-3.5" strokeWidth={1.75} />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-400 hover:text-slate-900"
                    onClick={() => onEdit(s.id)}
                    aria-label={`编辑「${title}」`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    onClick={() => {
                      if (window.confirm(`确定删除场景「${title}」？`)) {
                        onDelete(s.id)
                      }
                    }}
                    aria-label={`删除「${title}」`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
