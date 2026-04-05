import { Pencil, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import type { Scene, TemplateMeta } from "@/types/api"
import { scheduleToFormState } from "@/lib/apply-scene-schedule"
import { describeRefreshPreview } from "@/lib/refresh-schedule"

function describeSchedule(scene: Scene) {
  const f = scheduleToFormState(scene.schedule)
  return describeRefreshPreview(f.refreshMode, f.intervalValue, f.intervalUnit, f.scheduledClock, f.weekdays)
}

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
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/50 text-slate-500">
              <th className="w-16 px-4 py-3 text-center font-medium">启用</th>
              <th className="w-[30%] px-4 py-3 font-medium">场景名称</th>
              <th className="w-[45%] px-4 py-3 font-medium">调度规则</th>
              <th className="px-4 py-3 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100/80">
            {scenes.map((s) => {
              const t = tMap[s.templateId]
              const title = s.name || s.templateId
              return (
                <tr key={s.id} className="transition-colors hover:bg-slate-50/40">
                  <td className="px-4 py-3.5 text-center align-middle">
                    <Switch
                      checked={s.enabled}
                      onCheckedChange={(c) => onToggle(s, c)}
                      aria-label={`${title} 开关`}
                    />
                  </td>
                  <td className="px-4 py-3.5 align-middle">
                    <div className="font-medium text-slate-900">{title}</div>
                    <div className="mt-0.5 text-[11px] text-slate-500">
                      {t?.displayName || s.templateId}
                    </div>
                  </td>
                  <td className="px-4 py-3.5 align-middle text-slate-600">
                    {describeSchedule(s)}
                  </td>
                  <td className="px-4 py-3.5 text-right align-middle">
                    <div className="flex items-center justify-end gap-1">
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
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
