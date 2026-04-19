import { Pencil, Play, Power, Trash2 } from "lucide-react"
import { useState } from "react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import type { Scene, TemplateMeta } from "@/types/api"
import { scheduleToFormState } from "@/lib/apply-scene-schedule"
import { describeRefreshPreview } from "@/lib/refresh-schedule"
import { cn } from "@/lib/utils"

function describeSchedule(scene: Scene) {
  const f = scheduleToFormState(scene.schedule)
  return describeRefreshPreview(f.refreshMode, f.intervalValue, f.intervalUnit, f.scheduledClock, f.weekdays)
}

/** 旧版模板展示名：与当前 displayName 指同一模板，避免「AI 每日寄语」+「每日寄语」双行 */
const LEGACY_TEMPLATE_LABELS: Partial<Record<string, string[]>> = {
  ai_motto: ["AI 每日寄语"],
}

function sceneListPrimaryAndHint(
  templateId: string,
  sceneName: string,
  templateLabel: string,
): { primary: string; showHint: boolean; hint: string } {
  const stored = (sceneName || templateId).trim()
  const label = templateLabel.trim()
  const legacy = LEGACY_TEMPLATE_LABELS[templateId] ?? []
  if (legacy.includes(stored)) {
    return { primary: label, showHint: false, hint: label }
  }
  if (label === stored) {
    return { primary: stored, showHint: false, hint: label }
  }
  return { primary: stored, showHint: true, hint: label }
}

/** 与时间轴行首列 10.75rem 对齐；中为调度说明；末为操作（含立即上屏） */
const GRID_COLS =
  "[grid-template-columns:10.75rem_minmax(0,1fr)_8.5rem]" as const

/** 与 WallRunsTimeline 行高一致 */
const SCENE_ROW_MIN_H = "min-h-[2.75rem]"

const ICON_STROKE = 1.5

export function SceneList({
  scenes,
  templates,
  onToggle,
  onEdit,
  onDelete,
  onShowNow,
  sceneBusySceneId,
}: {
  scenes: Scene[]
  templates: TemplateMeta[]
  onToggle: (scene: Scene, enabled: boolean) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onShowNow?: (scene: Scene) => void
  /** 与 useWallSession.rowBusyId 对齐：上屏进行中时禁用该场景按钮 */
  sceneBusySceneId?: string | null
}) {
  const tMap = Object.fromEntries(templates.map((t) => [t.templateId, t]))
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null)

  if (scenes.length === 0) {
    return (
      <div className="select-none py-6">
        <p className="text-center text-[14px] leading-relaxed text-slate-500">
          暂无场景实例。在「画框模板」中点「+」即可创建。
        </p>
      </div>
    )
  }

  return (
    <div className="select-none">
      <AlertDialog
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除场景？</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget
                ? `将永久删除「${deleteTarget.label}」及其调度配置，此操作无法撤销。`
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">取消</AlertDialogCancel>
            <AlertDialogAction
              type="button"
              onClick={() => {
                if (deleteTarget) onDelete(deleteTarget.id)
                setDeleteTarget(null)
              }}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ul className="m-0 list-none p-0">
        {scenes.map((s) => {
          const t = tMap[s.templateId]
          const templateLabel = (t?.displayName || s.templateId).trim()
          const { primary, showHint, hint } = sceneListPrimaryAndHint(
            s.templateId,
            s.name ?? "",
            templateLabel
          )

          return (
            <li
              key={s.id}
              className="border-b border-slate-200/[0.14] last:border-b-0"
            >
              <div
                className={cn(
                  "flex flex-col gap-1 py-1.5 transition-colors hover:bg-slate-200/[0.09]",
                  "sm:grid sm:items-center sm:gap-x-0 sm:gap-y-0",
                  SCENE_ROW_MIN_H,
                  GRID_COLS
                )}
              >
                <div className="min-w-0 pr-2">
                  <div className="truncate text-[14px] font-medium leading-snug text-slate-900 sm:text-[15px]">
                    {primary}
                  </div>
                  {showHint ? (
                    <div className="mt-px text-[12px] leading-snug tracking-tight text-slate-400/85 sm:text-[13px]">
                      {hint}
                    </div>
                  ) : null}
                </div>

                <p className="min-w-0 pl-2 text-[12px] leading-snug tracking-tight text-slate-500 sm:text-[13px]">
                  {describeSchedule(s)}
                </p>

                <div className="flex shrink-0 items-center justify-end gap-0.5 pl-2 sm:gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "h-7 w-7 hover:text-slate-900",
                      s.enabled
                        ? "text-sky-600 hover:bg-sky-50 hover:text-sky-700"
                        : "text-slate-400 hover:bg-slate-100"
                    )}
                    aria-label={s.enabled ? `禁用「${primary}」` : `启用「${primary}」`}
                    aria-pressed={s.enabled}
                    onClick={() => onToggle(s, !s.enabled)}
                  >
                    <Power className="h-3 w-3" strokeWidth={ICON_STROKE} />
                  </Button>
                  {onShowNow && s.enabled ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-slate-500 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-50"
                      disabled={sceneBusySceneId === s.id}
                      aria-label={`立即上屏「${primary}」`}
                      aria-busy={sceneBusySceneId === s.id}
                      onClick={() => onShowNow(s)}
                    >
                      <Play className="h-3 w-3" strokeWidth={ICON_STROKE} />
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-slate-500 hover:text-slate-900"
                    onClick={() => onEdit(s.id)}
                    aria-label={`编辑「${primary}」`}
                  >
                    <Pencil className="h-3 w-3" strokeWidth={ICON_STROKE} />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-slate-500 hover:bg-red-50 hover:text-red-600"
                    onClick={() => setDeleteTarget({ id: s.id, label: primary })}
                    aria-label={`删除「${primary}」`}
                  >
                    <Trash2 className="h-3 w-3" strokeWidth={ICON_STROKE} />
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
