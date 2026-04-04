import { useCallback, useEffect, useMemo, useState } from "react"

import type { PreviewSrcRole } from "@/components/wall/WallPreviewSection"
import {
  ApiError,
  getConfig,
  getTemplates,
  getWallRuns,
  getWallState,
  putConfig,
  putScene,
  showNow,
} from "@/api/client"
import { getPreviewImageFilter, type FrameDisplayConfig } from "@/data/frame-config"
import { frameConfigToTuning, parseFrameTuning } from "@/lib/frame-tuning-sync"
import { useRowCooldown } from "@/hooks/useRowCooldown"
import { PREVIEW_PLACEHOLDER_SRC } from "@/lib/preview-placeholder"
import type { AppConfig, Scene, TemplateMeta, WallRun, WallState } from "@/types/api"

type NodeCardRow = { template: TemplateMeta; scene: Scene }

/** 无可用 http(s) 预览 URL 时用内联占位图（见 web/README.md） */
const PLACEHOLDER = PREVIEW_PLACEHOLDER_SRC
const ROW_COOLDOWN_MS = 650

/** http(s) 或同源相对路径（经 Vite 代理到 pi-server 的 /api/...） */
function isUsableImageRef(s: string | null | undefined): boolean {
  if (!s?.trim()) return false
  const t = s.trim()
  if (t.startsWith("/")) return true
  return /^https?:\/\//i.test(t)
}

export function useWallSession() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [templates, setTemplates] = useState<TemplateMeta[]>([])
  const [wallState, setWallState] = useState<WallState | null>(null)
  const [wallRuns, setWallRuns] = useState<WallRun[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [frameDialogOpen, setFrameDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const { busyId: rowBusyId, withCooldown } = useRowCooldown(ROW_COOLDOWN_MS)

  const showToast = useCallback((msg: string) => {
    setToast(msg)
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2800)
    return () => window.clearTimeout(t)
  }, [toast])

  const refresh = useCallback(async () => {
    setLoadError(null)
    setRefreshing(true)
    try {
      const [cfg, tpl, ws, runs] = await Promise.all([
        getConfig(),
        getTemplates(),
        getWallState(),
        getWallRuns(),
      ])
      setConfig(cfg)
      setTemplates(tpl)
      setWallState(ws)
      setWallRuns(runs)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "加载失败，请确认 pi-server 已启动（端口 5050）"
      setLoadError(msg)
      showToast(msg)
    } finally {
      setRefreshing(false)
    }
  }, [showToast])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setLoadError(null)
      try {
        const [cfg, tpl, ws, runs] = await Promise.all([
          getConfig(),
          getTemplates(),
          getWallState(),
          getWallRuns(),
        ])
        if (cancelled) return
        setConfig(cfg)
        setTemplates(tpl)
        setWallState(ws)
        setWallRuns(runs)
      } catch (e) {
        if (cancelled) return
        const msg = e instanceof ApiError ? e.message : "加载失败，请确认 pi-server 已启动（端口 5050）"
        setLoadError(msg)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const scenes = config?.scenes ?? []

  const nodeCards = useMemo((): NodeCardRow[] => {
    const byTid = Object.fromEntries(scenes.map((s) => [s.templateId, s]))
    return templates
      .map((t) => {
        const scene = byTid[t.templateId]
        return scene ? { template: t, scene } : null
      })
      .filter((row): row is NodeCardRow => row !== null)
  }, [scenes, templates])

  const frameConfig = useMemo(
    () => parseFrameTuning(config?.frameTuning as Record<string, unknown> | undefined),
    [config?.frameTuning]
  )

  const nowOnWall = useMemo(() => {
    if (!wallState?.currentSceneId) return null
    return scenes.find((s) => s.id === wallState.currentSceneId) ?? null
  }, [scenes, wallState?.currentSceneId])

  const sceneNames = useMemo(() => {
    const tidToDisplay = Object.fromEntries(templates.map((t) => [t.templateId, t.displayName]))
    const m: Record<string, string> = {}
    for (const s of scenes) {
      const custom = (s.name || "").trim()
      m[s.id] = custom || tidToDisplay[s.templateId] || s.templateId
    }
    return m
  }, [scenes, templates])

  const currentOnWallHeader = useMemo(() => {
    if (!wallState?.currentSceneId) return null
    const name = sceneNames[wallState.currentSceneId] ?? wallState.currentSceneId
    return { id: wallState.currentSceneId, name }
  }, [wallState?.currentSceneId, sceneNames])

  const previewFilter = useMemo(() => getPreviewImageFilter(frameConfig.imageSettings), [frameConfig])

  const previewSrc = useCallback(
    (scene: Scene, _role: PreviewSrcRole = "hero") => {
      if (wallState?.currentSceneId === scene.id) {
        const u = wallState.currentPreviewUrl
        if (isUsableImageRef(u)) return u!.trim()
      }
      if (isUsableImageRef(scene.previewImageUrl)) return scene.previewImageUrl!.trim()
      return PLACEHOLDER
    },
    [wallState]
  )

  const editingScene = useMemo(
    () => (editingId ? (scenes.find((s) => s.id === editingId) ?? null) : null),
    [editingId, scenes]
  )

  const openEdit = useCallback((id: string) => {
    setEditingId(id)
    setEditDialogOpen(true)
  }, [])

  const handleEditDialogOpenChange = useCallback((open: boolean) => {
    setEditDialogOpen(open)
    if (!open) setEditingId(null)
  }, [])

  const commitFrameDialog = useCallback(
    async (nextFrame: FrameDisplayConfig) => {
      if (!config) return
      try {
        const nextTuning = frameConfigToTuning(nextFrame)
        const nextCfg: AppConfig = {
          ...config,
          frameTuning: nextTuning,
        }
        const saved = await putConfig(nextCfg)
        setConfig(saved)
        setFrameDialogOpen(false)
        showToast("画框设置已保存")
        await refresh()
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "保存失败"
        showToast(msg)
      }
    },
    [config, refresh, showToast]
  )

  const handleSceneSave = useCallback(
    async (next: Scene) => {
      try {
        const saved = await putScene(next.id, next)
        setConfig((c) =>
          c
            ? {
                ...c,
                scenes: c.scenes.map((s) => (s.id === saved.id ? saved : s)),
              }
            : c
        )
        showToast("场景已保存")
        await refresh()
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "保存失败"
        showToast(msg)
      }
    },
    [refresh, showToast]
  )

  const runShowNow = useCallback(
    (scene: Scene) => {
      withCooldown(scene.id, () => {
        void (async () => {
          try {
            const sn = await showNow(scene.id)
            if (sn.wallState) setWallState(sn.wallState)
            showToast(`已上墙：${sceneNames[scene.id] ?? scene.templateId}`)
            await refresh()
          } catch (e) {
            const msg =
              e instanceof ApiError
                ? e.status === 400
                  ? "场景已禁用或未找到"
                  : e.message
                : "请求失败"
            showToast(msg)
          }
        })()
      })
    },
    [refresh, sceneNames, showToast, withCooldown]
  )

  return {
    loading,
    refreshing,
    loadError,
    refresh,
    config,
    templates,
    scenes,
    nodeCards,
    wallState,
    wallRuns,
    frameConfig,
    nowOnWall,
    sceneNames,
    currentOnWallHeader,
    previewSrc,
    previewFilter,
    editDialogOpen,
    frameDialogOpen,
    setFrameDialogOpen,
    editingScene,
    toast,
    rowBusyId,
    showToast,
    openEdit,
    runShowNow,
    handleEditDialogOpenChange,
    commitFrameDialog,
    handleSceneSave,
  }
}
