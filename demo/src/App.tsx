import { Settings2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { AppToast } from "@/components/AppToast"
import { EditUnitDialog } from "@/components/dialogs/EditUnitDialog"
import { FrameSettingsDialog } from "@/components/dialogs/FrameSettingsDialog"
import { PlaybackTimeline } from "@/components/PlaybackTimeline"
import { UnitCard } from "@/components/units/UnitCard"
import { WallPreviewSection } from "@/components/wall/WallPreviewSection"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  getPreviewImageFilter,
  loadFrameConfigFromStorage,
  saveFrameConfigToStorage,
  type FrameDisplayConfig,
} from "@/data/frame-config"
import {
  INITIAL_UNITS,
  RUN_LOGS,
  type RunLog,
  type Unit,
} from "@/data/demo-data"
import {
  applyScheduleFormToUnit,
  validateScheduleForm,
  type UnitScheduleFormState,
} from "@/lib/apply-unit-schedule"
import { computeNextScheduledRefresh } from "@/lib/refresh-schedule"
import { computeNextRefreshFromInterval, formatInstant } from "@/lib/demo-time"
import { useRowCooldown } from "@/hooks/useRowCooldown"

const ROW_ACTION_COOLDOWN_MS = 650

export default function App() {
  const [units, setUnits] = useState<Unit[]>(() => [...INITIAL_UNITS])
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [frameDialogOpen, setFrameDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const { busyId: rowBusyId, withCooldown: withRowCooldown } = useRowCooldown(ROW_ACTION_COOLDOWN_MS)
  const [frameConfig, setFrameConfig] = useState<FrameDisplayConfig>(() => loadFrameConfigFromStorage())
  const [liveRunLogExtras, setLiveRunLogExtras] = useState<Record<string, RunLog[]>>({})
  const [previewBust, setPreviewBust] = useState<Record<string, number>>({})

  const mergedRunLogs = useMemo(() => {
    const ids = new Set([...Object.keys(RUN_LOGS), ...Object.keys(liveRunLogExtras)])
    const out: Record<string, RunLog[]> = {}
    for (const id of ids) {
      const extra = liveRunLogExtras[id] ?? []
      const base = RUN_LOGS[id] ?? []
      out[id] = extra.length ? [...extra, ...base] : base
    }
    return out
  }, [liveRunLogExtras])

  const showToast = useCallback((msg: string) => {
    setToast(msg)
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2800)
    return () => window.clearTimeout(t)
  }, [toast])

  const switchableOnWall = useMemo(
    () => units.filter((u) => u.enabled && u.typeKey !== "output-screen"),
    [units]
  )

  const nowOnWall = switchableOnWall[0] ?? null

  const editingUnit = useMemo(
    () => (editingId ? (units.find((u) => u.id === editingId) ?? null) : null),
    [units, editingId]
  )

  const previewSrc = useCallback(
    (u: Unit) => {
      const bust = previewBust[u.id]
      const bustSuffix = bust != null ? `${(u.previewImageUrl ?? "").includes("?") ? "&" : "?"}r=${bust}` : ""
      if (u.previewImageUrl) return `${u.previewImageUrl}${bustSuffix}`
      const idNum = Number(u.id.replace(/\D/g, "")) || 0
      const base = `https://picsum.photos/id/${1000 + (idNum % 30)}/1440/1080`
      return bust != null ? `${base}?r=${bust}` : base
    },
    [previewBust]
  )

  const previewFilter = useMemo(
    () => getPreviewImageFilter(frameConfig.imageSettings),
    [frameConfig.imageSettings]
  )

  const commitFrameDialog = useCallback(
    (next: FrameDisplayConfig) => {
      setFrameConfig(next)
      saveFrameConfigToStorage(next)
      showToast("已保存")
      setFrameDialogOpen(false)
    },
    [showToast]
  )

  const openEdit = useCallback((id: string) => {
    setEditingId(id)
    setEditDialogOpen(true)
  }, [])

  const runRenderNow = useCallback(
    (u: Unit) => {
      withRowCooldown(u.id, () => {
        const ms = 620 + Math.floor(Math.random() * 980)
        const wall = switchableOnWall[0] ?? null
        const nextRefreshFor = (unit: Unit) => {
          if (unit.refreshMode === "scheduled") {
            const days =
              unit.scheduledWeekdays.length > 0 ? unit.scheduledWeekdays : [0, 1, 2, 3, 4, 5, 6]
            return computeNextScheduledRefresh(unit.scheduledClock || "09:00", days, new Date())
          }
          return computeNextRefreshFromInterval(unit.intervalSeconds)
        }

        if (u.typeKey === "output-screen") {
          const sourceName = wall?.name ?? "（无上墙画面）"
          const path =
            wall != null
              ? `/var/epd/out/push_${wall.id}_${Date.now()}.png`
              : "—"
          const log: RunLog = {
            start: formatInstant(new Date(Date.now() - ms)),
            end: formatInstant(new Date()),
            ms,
            ok: wall != null,
            err: wall != null ? "" : "无上墙画面可推送",
            path,
          }
          setLiveRunLogExtras((prev) => ({
            ...prev,
            [u.id]: [log, ...(prev[u.id] ?? [])],
          }))
          setUnits((prev) =>
            prev.map((x) =>
              x.id === u.id
                ? {
                    ...x,
                    enabled: true,
                    lastStatus: wall != null
                      ? { ok: true, text: `成功 · ${(ms / 1000).toFixed(1)}s` }
                      : { ok: false, text: "未推送 · 无上墙画面" },
                    nextRefresh: wall != null ? formatInstant(new Date()) : x.nextRefresh,
                  }
                : x
            )
          )
          setPreviewBust((b) => ({ ...b, [u.id]: Date.now() }))
          showToast(
            wall != null
              ? `已将「${sourceName}」推送至水墨屏（演示）`
              : `「${u.name}」已就绪；请先让画面上墙再推送（演示）`
          )
          return
        }

        const log: RunLog = {
          start: formatInstant(new Date(Date.now() - ms)),
          end: formatInstant(new Date()),
          ms,
          ok: true,
          err: "",
          path: `/var/epd/out/render_${u.id}_${Date.now()}.png`,
        }

        setLiveRunLogExtras((prev) => ({
          ...prev,
          [u.id]: [log, ...(prev[u.id] ?? [])],
        }))
        setPreviewBust((b) => ({ ...b, [u.id]: Date.now() }))
        setUnits((prev) =>
          prev.map((x) =>
            x.id === u.id
              ? {
                  ...x,
                  enabled: true,
                  lastStatus: { ok: true, text: `成功 · ${(ms / 1000).toFixed(1)}s` },
                  nextRefresh: nextRefreshFor(x),
                }
              : x
          )
        )
        showToast(`「${u.name}」已上墙并完成渲染（演示）`)
      })
    },
    [showToast, switchableOnWall, withRowCooldown]
  )

  const handleScheduleSave = useCallback(
    (unitId: string, form: UnitScheduleFormState) => {
      const err = validateScheduleForm(form)
      if (err) {
        showToast(err)
        return
      }
      setUnits((prev) =>
        prev.map((u) => (u.id === unitId ? applyScheduleFormToUnit(u, form) : u))
      )
      showToast("已保存")
      setEditDialogOpen(false)
      setEditingId(null)
    },
    [showToast]
  )

  const handleEditDialogOpenChange = useCallback((open: boolean) => {
    setEditDialogOpen(open)
    if (!open) setEditingId(null)
  }, [])

  return (
    <TooltipProvider delayDuration={280} skipDelayDuration={200}>
      <div className="min-h-screen px-4 pb-24 pt-8 sm:px-6 lg:px-10">
        <div className="mx-auto max-w-4xl space-y-10">
          <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="font-display text-[1.75rem] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[2rem]">
              壁上此刻
            </h1>
            <div className="flex flex-wrap gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-11 w-11 shrink-0 rounded-full text-slate-600 transition-[color,background-color,transform] hover:bg-slate-200/55 hover:text-slate-800 active:scale-[0.96] focus-visible:ring-slate-400/45 [&_svg]:!h-5 [&_svg]:!w-5"
                    onClick={() => setFrameDialogOpen(true)}
                    aria-label="画框设置"
                  >
                    <Settings2 strokeWidth={1.5} aria-hidden />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">画框设置</TooltipContent>
              </Tooltip>
            </div>
          </header>

          <WallPreviewSection
            nowOnWall={nowOnWall}
            frameConfig={frameConfig}
            previewSrc={previewSrc}
            previewFilter={previewFilter}
          />

          <PlaybackTimeline
            units={units}
            currentOnWall={nowOnWall ? { id: nowOnWall.id, name: nowOnWall.name } : null}
            runLogs={mergedRunLogs}
          />

          <section className="space-y-5">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">绘画节点</h2>

            <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-[repeat(auto-fill,minmax(10.25rem,1fr))] sm:gap-3">
              {units.map((u) => (
                <UnitCard
                  key={u.id}
                  unit={u}
                  disabled={!u.enabled}
                  rowLocked={rowBusyId === u.id}
                  previewSrc={previewSrc}
                  previewFilter={previewFilter}
                  onRenderNow={runRenderNow}
                  onEdit={openEdit}
                />
              ))}
            </ul>
          </section>
        </div>

        <FrameSettingsDialog
          open={frameDialogOpen}
          onOpenChange={setFrameDialogOpen}
          committedConfig={frameConfig}
          onCommit={commitFrameDialog}
        />

        <EditUnitDialog
          open={editDialogOpen}
          unit={editingUnit}
          onOpenChange={handleEditDialogOpenChange}
          onSave={handleScheduleSave}
        />

        <AppToast message={toast} />
      </div>
    </TooltipProvider>
  )
}
