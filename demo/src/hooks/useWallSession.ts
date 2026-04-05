import { startTransition, useCallback, useEffect, useMemo, useState } from "react"

import {
  getPreviewImageFilter,
  loadFrameConfigFromStorage,
  saveFrameConfigToStorage,
  type FrameDisplayConfig,
} from "@/data/frame-config"
import {
  INITIAL_SCENES,
  RUN_LOGS,
  type RunLog,
  type Scene,
} from "@/data/demo-data"
import {
  applyScheduleFormToScene,
  validateScheduleForm,
  type SceneScheduleFormState,
} from "@/lib/apply-scene-schedule"
import { computeNextScheduledRefresh } from "@/lib/refresh-schedule"
import { computeNextRefreshFromInterval, formatInstant } from "@/lib/demo-time"
import { useRowCooldown } from "@/hooks/useRowCooldown"

const ROW_ACTION_COOLDOWN_MS = 650

/** hero：主画框可带 cache-bust；thumb：卡片缩略图固定 URL，避免点击立即渲染后整图重载闪一下 */
export type PreviewSrcRole = "hero" | "thumb"

/**
 * 演示页核心状态与动作。列表/时间轴等非紧急更新包在 `startTransition` 内，
 * 减轻点击、hover 与输入被长任务拖慢的感觉（见 React 文档 useTransition）。
 */
export function useWallSession() {
  const [scenes, setScenes] = useState<Scene[]>(() => [...INITIAL_SCENES])
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
    () => scenes.filter((u) => u.enabled && u.typeKey !== "output-screen"),
    [scenes]
  )

  const nowOnWall = switchableOnWall[0] ?? null

  const editingScene = useMemo(
    () => (editingId ? (scenes.find((u) => u.id === editingId) ?? null) : null),
    [scenes, editingId]
  )

  const previewSrc = useCallback(
    (u: Scene, role: PreviewSrcRole = "hero") => {
      const bust = role === "hero" ? previewBust[u.id] : undefined
      const bustSuffix =
        bust != null ? `${(u.previewImageUrl ?? "").includes("?") ? "&" : "?"}r=${bust}` : ""
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
    (u: Scene) => {
      withRowCooldown(u.id, () => {
        const ms = 620 + Math.floor(Math.random() * 980)
        const wall = switchableOnWall[0] ?? null
        const nextRefreshFor = (scene: Scene) => {
          if (scene.refreshMode === "scheduled") {
            const days =
              scene.scheduledWeekdays.length > 0 ? scene.scheduledWeekdays : [0, 1, 2, 3, 4, 5, 6]
            return computeNextScheduledRefresh(scene.scheduledClock || "09:00:00", days, new Date())
          }
          return computeNextRefreshFromInterval(scene.intervalSeconds)
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
          startTransition(() => {
            setLiveRunLogExtras((prev) => ({
              ...prev,
              [u.id]: [log, ...(prev[u.id] ?? [])],
            }))
            setScenes((prev) =>
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
          })
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

        startTransition(() => {
          setLiveRunLogExtras((prev) => ({
            ...prev,
            [u.id]: [log, ...(prev[u.id] ?? [])],
          }))
          setPreviewBust((b) => ({ ...b, [u.id]: Date.now() }))
          setScenes((prev) =>
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
        })
        showToast(`「${u.name}」已上墙并完成渲染（演示）`)
      })
    },
    [showToast, switchableOnWall, withRowCooldown]
  )

  const handleScheduleSave = useCallback(
    (sceneId: string, form: SceneScheduleFormState) => {
      const err = validateScheduleForm(form)
      if (err) {
        showToast(err)
        return
      }
      setEditDialogOpen(false)
      setEditingId(null)
      showToast("已保存")
      startTransition(() => {
        setScenes((prev) =>
          prev.map((u) => (u.id === sceneId ? applyScheduleFormToScene(u, form) : u))
        )
      })
    },
    [showToast]
  )

  const handleEditDialogOpenChange = useCallback((open: boolean) => {
    setEditDialogOpen(open)
    if (!open) setEditingId(null)
  }, [])

  return {
    scenes,
    editDialogOpen,
    frameDialogOpen,
    setFrameDialogOpen,
    editingScene,
    toast,
    rowBusyId,
    frameConfig,
    mergedRunLogs,
    nowOnWall,
    previewSrc,
    previewFilter,
    commitFrameDialog,
    openEdit,
    runRenderNow,
    handleScheduleSave,
    handleEditDialogOpenChange,
  }
}
