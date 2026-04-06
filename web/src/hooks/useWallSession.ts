import { useCallback, useEffect, useMemo, useState } from "react"

import {
  ApiError,
  getConfig,
  getTemplates,
  getWallRuns,
  getWallState,
  putConfig,
  putScene,
  createScene,
  deleteScene,
  showNow,
  showNowTemplate,
} from "@/api/client"
import { getPreviewImageFilter, type FrameDisplayConfig } from "@/data/frame-config"
import { frameConfigToTuning, parseFrameTuning } from "@/lib/frame-tuning-sync"
import { useRowCooldown } from "@/hooks/useRowCooldown"
import { 
  getFallbackPlaceholder, 
  isUsableImageRef, 
  pickLatestOutputUrlForScene, 
  pickLatestOutputUrlForTemplate 
} from "@/lib/preview-resolve"
import type { AppConfig, Scene, TemplateMeta, WallRun, WallState } from "@/types/api"

const ROW_COOLDOWN_MS = 650

export function useWallSession() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [templates, setTemplates] = useState<TemplateMeta[]>([])
  const [wallState, setWallState] = useState<WallState | null>(null)
  const [wallRuns, setWallRuns] = useState<WallRun[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [frameDialogOpen, setFrameDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [pendingTemplateId, setPendingTemplateId] = useState<string | null>(null)
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
      const msg = e instanceof ApiError ? e.message : "加载失败，请确认后端已启动（端口 5050）"
      setLoadError(msg)
      showToast(msg)
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
        const msg = e instanceof ApiError ? e.message : "加载失败，请确认后端已启动（端口 5050）"
        setLoadError(msg)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const sse = new EventSource('/api/v1/wall/events')
    
    sse.addEventListener('wall_update', (e) => {
      console.log('Received wall_update event', e.data)
      try {
        const nextState = JSON.parse(e.data) as WallState
        setWallState(nextState)
      } catch (err) {
        console.error('Failed to parse wall_update payload', err)
      }
      void refresh()
    })

    sse.onerror = (e) => {
      console.error('SSE Error', e)
    }

    return () => {
      sse.close()
    }
  }, [refresh])

  const scenes = config?.scenes ?? []

  const frameConfig = useMemo(
    () => parseFrameTuning(config?.frameTuning as Record<string, unknown> | undefined),
    [config?.frameTuning]
  )

  const nowOnWall = useMemo(() => {
    if (!wallState?.currentSceneId) return null
    const found = scenes.find((s) => s.id === wallState.currentSceneId)
    if (found) return found
    
    // Fallback for ephemeral/deleted scenes
    return {
      id: wallState.currentSceneId,
      name: wallState.currentSceneName ?? wallState.currentSceneId,
      description: "",
      enabled: true,
      templateId: wallState.currentTemplateId ?? "",
      templateParams: {},
      schedule: { type: "interval", intervalSeconds: 300 },
      previewImageUrl: wallState.currentPreviewUrl,
      tieBreakPriority: 9,
    } as Scene
  }, [scenes, wallState])

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
    (scene: Scene) => {
      // 1. Current on wall
      if (wallState?.currentSceneId === scene.id) {
        const u = wallState.currentPreviewUrl
        if (isUsableImageRef(u)) return u!.trim()
      }
      // 2. Persistent preview URL
      if (isUsableImageRef(scene.previewImageUrl)) return scene.previewImageUrl!.trim()
      // 3. Latest output run for this scene
      const latestRunOutput = pickLatestOutputUrlForScene(wallRuns, scene.id)
      if (latestRunOutput) return latestRunOutput
      // 4. Fallback placeholder
      return getFallbackPlaceholder(scene.name || scene.templateId)
    },
    [wallState, wallRuns]
  )

  const templatePreviewSrc = useCallback(
    (templateId: string, displayTitle: string) => {
      // 1. If this template is currently on the wall (e.g. via ephemeral run)
      if (wallState?.currentTemplateId === templateId) {
        const u = wallState.currentPreviewUrl
        if (isUsableImageRef(u)) return u!.trim()
      }
      
      // 2. Pick the first configured scene for this template and check its persistent preview
      const firstScene = scenes.find((s) => s.templateId === templateId)
      if (firstScene && isUsableImageRef(firstScene.previewImageUrl)) {
        return firstScene.previewImageUrl!.trim()
      }
      
      // 3. Latest output run for this template
      const latestRunOutput = pickLatestOutputUrlForTemplate(wallRuns, templateId)
      if (latestRunOutput) return latestRunOutput
      
      // 4. Fallback placeholder
      return getFallbackPlaceholder(displayTitle)
    },
    [wallState, scenes, wallRuns]
  )

  const editingScene = useMemo(() => {
    if (editingId) return scenes.find((s) => s.id === editingId) ?? null
    if (pendingTemplateId) {
      return {
        id: "", // No ID yet
        name: "",
        description: "",
        enabled: true,
        templateId: pendingTemplateId,
        templateParams: {},
        schedule: { type: "interval", intervalSeconds: 3600 },
        previewImageUrl: null,
        tieBreakPriority: 9,
      } as Scene
    }
    return null
  }, [editingId, pendingTemplateId, scenes])

  const openEdit = useCallback((id: string) => {
    setEditingId(id)
    setPendingTemplateId(null)
    setEditDialogOpen(true)
  }, [])

  const handleEditDialogOpenChange = useCallback((open: boolean) => {
    setEditDialogOpen(open)
    if (!open) {
      setEditingId(null)
      setPendingTemplateId(null)
    }
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

  const handleSceneCreate = useCallback(
    (templateId: string) => {
      setPendingTemplateId(templateId)
      setEditingId(null)
      setEditDialogOpen(true)
    },
    []
  )

  const handleSceneDelete = useCallback(
    async (id: string) => {
      if (!id) return // New scene
      try {
        await deleteScene(id)
        setConfig((c) =>
          c
            ? {
                ...c,
                scenes: c.scenes.filter((s) => s.id !== id),
              }
            : c
        )
        showToast("场景已删除")
        await refresh()
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "删除失败"
        showToast(msg)
      }
    },
    [refresh, showToast]
  )

  const handleSceneToggle = useCallback(
    async (scene: Scene, enabled: boolean) => {
      if (!scene.id) return // Should not happen for toggle
      const next = { ...scene, enabled }
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
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : "状态切换失败"
        showToast(msg)
      }
    },
    [showToast]
  )

  const handleSceneSave = useCallback(
    async (next: Scene) => {
      try {
        const isNew = !next.id
        const saved = isNew ? await createScene(next) : await putScene(next.id, next)
        setConfig((c) =>
          c
            ? {
                ...c,
                scenes: isNew ? [...c.scenes, saved] : c.scenes.map((s) => (s.id === saved.id ? saved : s)),
              }
            : c
        )
        showToast(isNew ? "场景已创建" : "场景已保存")
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

  const runShowNowTemplate = useCallback(
    (templateId: string) => {
      withCooldown(templateId, () => {
        void (async () => {
          try {
            const sn = await showNowTemplate(templateId)
            if (sn.wallState) setWallState(sn.wallState)
            showToast(`模板已上墙：${templateId}`)
            await refresh()
          } catch (e) {
            const msg = e instanceof ApiError ? e.message : "请求失败"
            showToast(msg)
          }
        })()
      })
    },
    [refresh, showToast, withCooldown]
  )

  return {
    loading,
    loadError,
    refresh,
    config,
    templates,
    scenes,
    wallState,
    wallRuns,
    frameConfig,
    nowOnWall,
    sceneNames,
    currentOnWallHeader,
    previewSrc,
    templatePreviewSrc,
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
    runShowNowTemplate,
    handleEditDialogOpenChange,
    commitFrameDialog,
    handleSceneSave,
    handleSceneDelete,
    handleSceneCreate,
    handleSceneToggle,
  }
}
