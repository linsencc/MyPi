import {
  Calendar,
  CircleHelp,
  CloudSun,
  Monitor,
  Pencil,
  Play,
  Settings2,
} from "lucide-react"
import { type CSSProperties, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"

import { AppToast } from "@/components/AppToast"
import { IntervalUnitSelect } from "@/components/IntervalUnitSelect"
import { ScheduleTimePicker } from "@/components/ScheduleTimePicker"
import { PlaybackTimeline } from "@/components/PlaybackTimeline"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  INKYPI_IMAGE_DEFAULTS,
  INKYPI_SLIDER_SPECS,
  getPreviewImageFilter,
  loadFrameConfigFromStorage,
  saveFrameConfigToStorage,
  type FrameDisplayConfig,
  type InkypiImageSettings,
} from "@/data/frame-config"
import {
  INITIAL_UNITS,
  RUN_LOGS,
  type RunLog,
  type Unit,
  type UnitRefreshMode,
} from "@/data/demo-data"
import {
  computeNextScheduledRefresh,
  describeRefreshPreview,
  formToIntervalSeconds,
  intervalSecondsToForm,
  normalizeWeekdaysSelection,
  parseClockFromNextRefresh,
  weekdayShort,
  WEEKDAY_ORDER_UI,
  WEEKDAY_PRESETS,
  type IntervalTimeUnit,
} from "@/lib/refresh-schedule"

/** 演示：写入「立即渲染」产生的运行记录时间戳 */
function formatInstant(d: Date): string {
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, "0")
  const dy = String(d.getDate()).padStart(2, "0")
  const h = String(d.getHours()).padStart(2, "0")
  const mi = String(d.getMinutes()).padStart(2, "0")
  const s = String(d.getSeconds()).padStart(2, "0")
  return `${y}-${mo}-${dy} ${h}:${mi}:${s}`
}
import { dialogShell } from "@/lib/dialog-shell"
import { cn } from "@/lib/utils"

/** 编辑弹窗：标签降权（小字、灰、字间距） */
const editDialogLabelClass = "text-[12px] font-medium leading-none tracking-[0.04em] text-[#666666]"

/** 编辑弹窗：输入弱边框浅底，聚焦时提亮 */
const editDialogFieldClass =
  "rounded-[length:var(--radius-md)] border-slate-200/45 bg-slate-100/40 shadow-none transition-[border-color,background-color,box-shadow] placeholder:text-slate-400/90 focus-visible:border-[#0071e3]/45 focus-visible:bg-white focus-visible:ring-2 focus-visible:ring-[#0071e3]/15 focus-visible:ring-offset-0"

/** 统一为 YYYY-MM-DD HH:mm:ss */
function computeNextRefreshFromInterval(seconds: number): string {
  const sec = Math.max(30, Math.floor(Number(seconds)) || 300)
  const d = new Date()
  d.setSeconds(d.getSeconds() + sec)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, "0")
  const dy = String(d.getDate()).padStart(2, "0")
  const h = String(d.getHours()).padStart(2, "0")
  const mi = String(d.getMinutes()).padStart(2, "0")
  const s = String(d.getSeconds()).padStart(2, "0")
  return `${y}-${mo}-${dy} ${h}:${mi}:${s}`
}

const ROW_ACTION_COOLDOWN_MS = 650

function unitAccent(typeKey: string) {
  switch (typeKey) {
    case "image-calendar":
      return { Icon: Calendar, iconClass: "text-violet-500/90" }
    case "output-screen":
      return { Icon: Monitor, iconClass: "text-slate-500/90" }
    default:
      return { Icon: CloudSun, iconClass: "text-sky-500/90" }
  }
}

function PreviewFrame({
  src,
  alt,
  imageFilter,
}: {
  src: string
  alt: string
  imageFilter: string
}) {
  const [broken, setBroken] = useState(false)
  if (broken) {
    const { Icon, iconClass } = unitAccent("image-weather")
    return (
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-200/90 text-center text-[13px] text-slate-500">
        <Icon className={cn("h-14 w-14 opacity-40", iconClass)} strokeWidth={1} />
        预览图加载失败，请检查图片地址
      </div>
    )
  }
  return (
    <img
      src={src}
      alt={alt}
      className="absolute inset-0 h-full w-full object-cover object-center"
      style={{ filter: imageFilter }}
      loading="eager"
      onError={() => setBroken(true)}
    />
  )
}

export default function App() {
  const [units, setUnits] = useState<Unit[]>(() => [...INITIAL_UNITS])
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [frameDialogOpen, setFrameDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [rowBusyId, setRowBusyId] = useState<string | null>(null)
  const editDialogContentRef = useRef<HTMLDivElement>(null)
  const editDialogScrollRef = useRef<HTMLDivElement>(null)

  const [formRefreshMode, setFormRefreshMode] = useState<UnitRefreshMode>("interval")
  const [formIntervalValue, setFormIntervalValue] = useState(5)
  const [formIntervalUnit, setFormIntervalUnit] = useState<IntervalTimeUnit>("m")
  const [formScheduledClock, setFormScheduledClock] = useState("09:00")
  const [formWeekdays, setFormWeekdays] = useState<number[]>(() => [...WEEKDAY_PRESETS.daily])
  const [frameConfig, setFrameConfig] = useState<FrameDisplayConfig>(() => loadFrameConfigFromStorage())
  const [frameDraft, setFrameDraft] = useState<FrameDisplayConfig>(() => ({ ...loadFrameConfigFromStorage() }))
  /** 演示：用户点击「立即渲染」后追加到时间轴 / 监控的记录 */
  const [liveRunLogExtras, setLiveRunLogExtras] = useState<Record<string, RunLog[]>>({})
  /** 演示：打破预览缓存，使同一 URL 在渲染后立即重载缩略图 */
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

  const withRowCooldown = useCallback((unitId: string, action: () => void) => {
    if (rowBusyId === unitId) return
    setRowBusyId(unitId)
    action()
    window.setTimeout(() => {
      setRowBusyId((cur) => (cur === unitId ? null : cur))
    }, ROW_ACTION_COOLDOWN_MS)
  }, [rowBusyId])

  const switchableOnWall = useMemo(
    () => units.filter((u) => u.enabled && u.typeKey !== "output-screen"),
    [units]
  )

  const nowOnWall = switchableOnWall[0] ?? null

  const editingUnit = useMemo(
    () => (editingId ? (units.find((u) => u.id === editingId) ?? null) : null),
    [units, editingId]
  )

  const schedulePreviewText = useMemo(
    () =>
      describeRefreshPreview(
        formRefreshMode,
        formIntervalValue,
        formIntervalUnit,
        formScheduledClock,
        formWeekdays
      ),
    [formRefreshMode, formIntervalValue, formIntervalUnit, formScheduledClock, formWeekdays]
  )

  const toggleWeekday = useCallback((d: number) => {
    setFormWeekdays((prev) => {
      const next = new Set(prev)
      if (next.has(d)) next.delete(d)
      else next.add(d)
      return WEEKDAY_ORDER_UI.filter((x) => next.has(x))
    })
  }, [])

  const previewSrc = (u: Unit) => {
    const bust = previewBust[u.id]
    const bustSuffix = bust != null ? `${(u.previewImageUrl ?? "").includes("?") ? "&" : "?"}r=${bust}` : ""
    if (u.previewImageUrl) return `${u.previewImageUrl}${bustSuffix}`
    const idNum = Number(u.id.replace(/\D/g, "")) || 0
    const base = `https://picsum.photos/id/${1000 + (idNum % 30)}/1440/1080`
    return bust != null ? `${base}?r=${bust}` : base
  }

  const previewFrame = frameDialogOpen ? frameDraft : frameConfig
  /** 拖动滑块时延后更新首页预览滤镜，避免整页重绘与弹窗滚动条抖动 */
  const previewImageSettingsDeferred = useDeferredValue(previewFrame.imageSettings)
  const previewFilter = useMemo(
    () => getPreviewImageFilter(previewImageSettingsDeferred),
    [previewImageSettingsDeferred]
  )

  const openFrameDialog = useCallback(() => {
    setFrameDraft({
      orientation: frameConfig.orientation,
      imageSettings: { ...frameConfig.imageSettings },
    })
    setFrameDialogOpen(true)
  }, [frameConfig])

  const commitFrameDialog = useCallback(() => {
    const next = {
      orientation: frameDraft.orientation,
      imageSettings: { ...frameDraft.imageSettings },
    }
    setFrameConfig(next)
    saveFrameConfigToStorage(next)
    showToast("已保存")
    setFrameDialogOpen(false)
  }, [frameDraft, showToast])

  const resetSlider = useCallback((key: keyof InkypiImageSettings) => {
    const spec = INKYPI_SLIDER_SPECS.find((s) => s.key === key)
    if (!spec) return
    setFrameDraft((d) => ({
      ...d,
      imageSettings: { ...d.imageSettings, [key]: spec.defaultValue },
    }))
  }, [])

  const resetAllSliders = useCallback(() => {
    setFrameDraft((d) => ({
      ...d,
      imageSettings: { ...INKYPI_IMAGE_DEFAULTS },
    }))
  }, [])

  const openEdit = (id: string) => {
    const u = units.find((x) => x.id === id)
    if (!u) return
    setEditingId(id)
    setFormRefreshMode(u.refreshMode)
    const { value, unit } = intervalSecondsToForm(u.intervalSeconds)
    setFormIntervalValue(value)
    setFormIntervalUnit(unit)
    setFormScheduledClock((u.scheduledClock ?? "").trim() || parseClockFromNextRefresh(u.nextRefresh))
    setFormWeekdays(normalizeWeekdaysSelection(u.scheduledWeekdays))
    setEditDialogOpen(true)
  }

  const runRenderNow = useCallback(
    (u: Unit) => {
      withRowCooldown(u.id, () => {
        const ms = 620 + Math.floor(Math.random() * 980)
        const wall = nowOnWall
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
        setUnits((prev) => {
          const idx = prev.findIndex((x) => x.id === u.id)
          if (idx < 0) return prev
          const enabled = prev.map((x) =>
            x.id === u.id
              ? {
                  ...x,
                  enabled: true,
                  lastStatus: { ok: true, text: `成功 · ${(ms / 1000).toFixed(1)}s` },
                  nextRefresh: nextRefreshFor(x),
                }
              : x
          )
          const j = enabled.findIndex((x) => x.id === u.id)
          if (j < 0) return prev
          const next = [...enabled]
          const [item] = next.splice(j, 1)
          return [item, ...next]
        })
        showToast(`「${u.name}」已上墙并完成渲染（演示）`)
      })
    },
    [showToast, nowOnWall, withRowCooldown]
  )

  const closeEditDialog = () => {
    setEditDialogOpen(false)
    setEditingId(null)
  }

  const handleSave = () => {
    if (!editingId) return
    if (formRefreshMode === "scheduled") {
      if (formWeekdays.length === 0) {
        showToast("周期定时请至少选择一个星期")
        return
      }
      const probe = computeNextScheduledRefresh(formScheduledClock.trim(), formWeekdays, new Date())
      if (probe === "—") {
        showToast("请填写有效的触发时间（时:分）")
        return
      }
    }
    setUnits((prev) =>
      prev.map((u) => {
        if (u.id !== editingId) return u
        if (formRefreshMode === "scheduled") {
          const scheduledClock = formScheduledClock.trim()
          const scheduledWeekdays = [...formWeekdays]
          const nextRefresh = computeNextScheduledRefresh(scheduledClock, scheduledWeekdays, new Date())
          return {
            ...u,
            refreshMode: "scheduled",
            scheduledClock,
            scheduledWeekdays,
            nextRefresh,
          }
        }
        const intervalSeconds = formToIntervalSeconds(formIntervalValue, formIntervalUnit)
        return {
          ...u,
          refreshMode: "interval",
          intervalSeconds,
          nextRefresh: computeNextRefreshFromInterval(intervalSeconds),
        }
      })
    )
    showToast("已保存")
    closeEditDialog()
  }

  return (
    <TooltipProvider delayDuration={280} skipDelayDuration={200}>
    <div className="min-h-screen px-4 pb-24 pt-8 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-4xl space-y-10">
        {/* 顶部：标题 + 画框配置 */}
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
                  onClick={openFrameDialog}
                  aria-label="画框设置"
                >
                  <Settings2 strokeWidth={1.5} aria-hidden />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">画框设置</TooltipContent>
            </Tooltip>
          </div>
        </header>

        <section aria-labelledby="now-playing-heading" className="space-y-4">
          <h2 id="now-playing-heading" className="sr-only">
            画框上正在展示
          </h2>
          {nowOnWall ? (
            <>
              <div className="relative overflow-hidden rounded-[length:var(--radius-surface)]">
                {/* 网格渐变 + 基色，略增层次 */}
                <div
                  aria-hidden
                  className={cn(
                    "pointer-events-none absolute inset-0",
                    previewFrame.orientation === "portrait"
                      ? "bg-[radial-gradient(ellipse_95%_72%_at_14%_0%,rgb(148_163_184/0.22),transparent_55%),radial-gradient(ellipse_65%_50%_at_88%_12%,rgb(100_116_139/0.12),transparent_48%),radial-gradient(ellipse_50%_42%_at_48%_96%,rgb(71_85_105/0.08),transparent_52%),linear-gradient(to_bottom,rgb(203_213_225/0.38),rgb(148_163_184/0.09),transparent)]"
                      : "bg-[radial-gradient(ellipse_100%_78%_at_18%_0%,rgb(148_163_184/0.16),transparent_52%),radial-gradient(ellipse_72%_58%_at_90%_20%,rgb(148_163_184/0.1),transparent_46%),radial-gradient(ellipse_52%_44%_at_42%_98%,rgb(100_116_139/0.07),transparent_50%),linear-gradient(to_bottom,rgb(226_232_240/0.42),rgb(241_245_249/0.2),transparent)]"
                  )}
                />
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0 bg-hero-noise opacity-[0.035] mix-blend-multiply [background-size:256px_256px]"
                />
                <div className="relative z-10 flex justify-center px-4 py-5 sm:px-6 sm:py-7">
                <div className="flex w-full max-w-[min(100%,980px)] justify-center">
                  {previewFrame.orientation === "landscape" ? (
                    <div
                      className={cn(
                        "relative aspect-[4/3] h-[min(34vh,288px)] w-auto max-w-full overflow-hidden rounded-[length:var(--radius-surface)] bg-slate-800/45",
                        /* 单层圆角裁剪：避免 ring + 1px shadow + 子层 inset 在四角叠成双细线 */
                        "shadow-[0_0_0_1px_rgb(255_255_255/0.14),0_2px_6px_rgb(0_0_0/0.16),0_18px_48px_-22px_rgb(0_0_0/0.34),0_44px_112px_-50px_rgb(0_0_0/0.52),inset_0_1px_1px_rgb(255_255_255/0.12),inset_0_12px_40px_rgb(0_0_0/0.18)]"
                      )}
                    >
                      <PreviewFrame
                        src={previewSrc(nowOnWall)}
                        alt={`${nowOnWall.name} 当前画面预览`}
                        imageFilter={previewFilter}
                      />
                    </div>
                  ) : (
                    <div
                      className={cn(
                        "relative aspect-[3/4] h-[min(46vh,380px)] w-auto max-w-full overflow-hidden rounded-[length:var(--radius-surface)] bg-slate-800/45 sm:h-[min(44vh,360px)]",
                        "shadow-[0_0_0_1px_rgb(255_255_255/0.14),0_2px_6px_rgb(0_0_0/0.16),0_18px_48px_-22px_rgb(0_0_0/0.34),0_44px_112px_-50px_rgb(0_0_0/0.52),inset_0_1px_1px_rgb(255_255_255/0.12),inset_0_12px_40px_rgb(0_0_0/0.18)]"
                      )}
                    >
                      <PreviewFrame
                        src={previewSrc(nowOnWall)}
                        alt={`${nowOnWall.name} 当前画面预览`}
                        imageFilter={previewFilter}
                      />
                    </div>
                  )}
                </div>
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-[length:var(--radius-surface)] border border-dashed border-slate-200/90 bg-slate-50/60 px-6 py-14 text-center">
              <p className="text-[15px] font-semibold text-slate-800">暂无画框展示内容</p>
              <p className="mx-auto mt-1.5 max-w-sm text-[12px] leading-relaxed text-slate-500">
                启用至少一个绘画节点后，将在此显示预览。
              </p>
            </div>
          )}
        </section>

        <PlaybackTimeline
          units={units}
          currentOnWall={nowOnWall ? { id: nowOnWall.id, name: nowOnWall.name } : null}
          runLogs={mergedRunLogs}
        />

        <section className="space-y-5">
          <h2 className="text-lg font-semibold tracking-tight text-slate-900">绘画节点</h2>

          <ul className="grid grid-cols-2 gap-2.5 sm:grid-cols-[repeat(auto-fill,minmax(10.25rem,1fr))] sm:gap-3">
            {units.map((u) => {
              const disabled = !u.enabled
              const rowLocked = rowBusyId === u.id
              return (
                <li
                  key={u.id}
                  className={cn(
                    "group flex aspect-square min-h-0 min-w-0 flex-col overflow-hidden rounded-[length:var(--radius-surface)] border border-slate-900/[0.055] bg-white/95 shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_14px_36px_-22px_rgb(15_23_42/0.12),0_6px_14px_-10px_rgb(15_23_42/0.05)] backdrop-blur-[2px]",
                    disabled && "opacity-[0.72]"
                  )}
                >
                  <div className="relative w-full shrink-0 basis-[42%] overflow-hidden bg-slate-100">
                    <PreviewFrame
                      src={previewSrc(u)}
                      alt={`${u.name} 缩略预览`}
                      imageFilter={previewFilter}
                    />
                  </div>

                  <div className="flex min-h-0 min-w-0 flex-1 flex-col justify-end gap-1.5 px-2.5 pb-2 pt-1 sm:gap-2 sm:px-3 sm:pb-2.5 sm:pt-1.5">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="min-w-0 cursor-default">
                          <h3 className="line-clamp-2 text-[12px] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[13px]">
                            {u.name}
                          </h3>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-[15rem] whitespace-pre-line">
                        {u.description ? `${u.name}\n${u.description}` : u.name}
                      </TooltipContent>
                    </Tooltip>

                    <div className="flex shrink-0 items-center justify-end gap-3 pt-0.5">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 shrink-0 rounded-full border border-white/50 bg-white/45 text-slate-400/55 shadow-[0_1px_2px_rgb(15_23_42/0.05)] backdrop-blur-md transition-[color,background-color,box-shadow] hover:bg-white/70 hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.07)] disabled:opacity-50"
                            disabled={rowLocked}
                            aria-label={`立即渲染并优先上墙「${u.name}」`}
                            onClick={() => runRenderNow(u)}
                          >
                            <Play className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">立即渲染</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 shrink-0 rounded-full border border-white/50 bg-white/45 text-slate-400/55 shadow-[0_1px_2px_rgb(15_23_42/0.05)] backdrop-blur-md transition-[color,background-color,box-shadow] hover:bg-white/70 hover:text-slate-800 hover:shadow-[0_2px_6px_rgb(15_23_42/0.07)] disabled:opacity-50"
                            disabled={rowLocked}
                            aria-label={`编辑间隔或定时刷新「${u.name}」`}
                            onClick={() => openEdit(u.id)}
                          >
                            <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top">编辑定时</TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      </div>

      <Dialog open={frameDialogOpen} onOpenChange={setFrameDialogOpen}>
        <DialogContent
          className={dialogShell("max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-2xl sm:max-w-2xl")}
        >
          <DialogHeader className="border-b border-slate-200/45 px-6 pb-3.5 pt-5 pr-14 text-left">
            <DialogTitle className="text-[17px] font-semibold tracking-tight text-slate-900">画框设置</DialogTitle>
          </DialogHeader>

          <div className="max-h-[min(66dvh,560px)] overflow-y-auto overscroll-y-contain px-6 py-4 [scrollbar-gutter:stable]">
            <div className="space-y-5">
              <section className="space-y-2">
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">画框方向</h3>
                <div
                  className="grid grid-cols-2 gap-1 rounded-full bg-slate-100/90 p-1"
                  role="group"
                  aria-label="画框横竖屏"
                >
                  <button
                    type="button"
                    onClick={() => setFrameDraft((d) => ({ ...d, orientation: "landscape" }))}
                    className={cn(
                      "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                      frameDraft.orientation === "landscape"
                        ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    横屏
                  </button>
                  <button
                    type="button"
                    onClick={() => setFrameDraft((d) => ({ ...d, orientation: "portrait" }))}
                    className={cn(
                      "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                      frameDraft.orientation === "portrait"
                        ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    竖屏
                  </button>
                </div>
              </section>

              <section className="space-y-3 border-t border-slate-100 pt-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
                    水墨屏色彩校对
                  </h3>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 shrink-0 px-2 text-[12px] text-slate-600 hover:text-slate-900"
                    onClick={resetAllSliders}
                  >
                    全部恢复默认
                  </Button>
                </div>
                <ul className="space-y-5">
                  {INKYPI_SLIDER_SPECS.map((spec) => {
                    const v = frameDraft.imageSettings[spec.key]
                    const isDefault = Math.abs(v - spec.defaultValue) < 1e-6
                    const techTip = `${spec.hint} · 默认 ${spec.defaultValue.toFixed(2)}`
                    return (
                      <li key={spec.key} className="space-y-2">
                        <div className="flex items-center gap-1.5">
                          <Label htmlFor={`ink-slider-${spec.key}`} className="text-[13px] font-semibold text-slate-800">
                            {spec.label}
                          </Label>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                className="inline-flex shrink-0 rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/30"
                                aria-label={`${spec.label}：技术说明与默认值`}
                              >
                                <CircleHelp className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-[16rem]">
                              {techTip}
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <div className="flex items-center gap-3">
                          <input
                            id={`ink-slider-${spec.key}`}
                            type="range"
                            min={spec.min}
                            max={spec.max}
                            step={spec.step}
                            value={v}
                            aria-valuetext={`${spec.label} ${v.toFixed(2)}`}
                            onChange={(e) => {
                              const n = Number(e.target.value)
                              setFrameDraft((d) => ({
                                ...d,
                                imageSettings: { ...d.imageSettings, [spec.key]: n },
                              }))
                            }}
                            className="ink-range-slider min-w-0 flex-1"
                            style={
                              {
                                "--ink-pct": `${spec.max === spec.min ? 0 : ((v - spec.min) / (spec.max - spec.min)) * 100}%`,
                              } as CSSProperties
                            }
                          />
                          <div className="flex w-12 shrink-0 items-center justify-end tabular-nums">
                            {isDefault ? (
                              <span className="w-full text-right font-mono text-[13px] text-slate-900">
                                {v.toFixed(2)}
                              </span>
                            ) : (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    aria-label={`${spec.label} 恢复为默认 ${spec.defaultValue.toFixed(2)}`}
                                    className="w-full rounded-md px-1 py-0.5 text-right font-mono text-[13px] text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                                    onClick={() => resetSlider(spec.key)}
                                  >
                                    {v.toFixed(2)}
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="left">
                                  点击恢复默认 {spec.defaultValue.toFixed(2)}
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              </section>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-slate-200/50 bg-slate-100/25 px-6 py-3.5 backdrop-blur-sm">
            <Button
              type="button"
              variant="ghost"
              className="rounded-[length:var(--radius-md)] px-4 text-[13px] font-medium text-slate-600 hover:bg-slate-200/45 hover:text-slate-900"
              onClick={() => setFrameDialogOpen(false)}
            >
              取消
            </Button>
            <Button
              type="button"
              className="rounded-[length:var(--radius-md)] bg-[#0071e3] px-5 text-[13px] font-semibold text-white shadow-sm hover:bg-[#0068cf] focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
              onClick={commitFrameDialog}
            >
              保存
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={editDialogOpen}
        onOpenChange={(open) => {
          if (!open) closeEditDialog()
        }}
      >
        <DialogContent
          ref={editDialogContentRef}
          className={dialogShell(
            /* 勿加 relative：会覆盖 fixed；勿加 overflow-visible：底栏直角会露出圆角外（右下角发灰） */
            "max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-xl sm:max-w-xl"
          )}
        >
          <DialogHeader className="border-b border-slate-200/45 px-6 pb-3 pt-4 pr-14 text-left">
            <Tooltip>
              <TooltipTrigger asChild>
                <DialogTitle className="truncate text-left text-[17px] font-semibold tracking-tight text-slate-900">
                  {editingUnit?.name ?? "—"}
                </DialogTitle>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[min(20rem,calc(100vw-3rem))] break-words">
                {editingUnit?.name ?? "—"}
              </TooltipContent>
            </Tooltip>
          </DialogHeader>

          <div
            ref={editDialogScrollRef}
            className="max-h-[min(58dvh,560px)] overflow-y-auto px-6 py-3"
          >
            <div className="space-y-4">
              <div className="space-y-2">
                <span className={editDialogLabelClass}>更新方式</span>
                <div
                  className="grid grid-cols-2 gap-1 rounded-full bg-slate-100/90 p-1"
                  role="group"
                  aria-label="更新方式"
                >
                  <button
                    type="button"
                    aria-pressed={formRefreshMode === "interval"}
                    onClick={() => setFormRefreshMode("interval")}
                    className={cn(
                      "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                      formRefreshMode === "interval"
                        ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    频率循环
                  </button>
                  <button
                    type="button"
                    aria-pressed={formRefreshMode === "scheduled"}
                    onClick={() => setFormRefreshMode("scheduled")}
                    className={cn(
                      "rounded-full py-2.5 text-[13px] font-semibold transition-[color,background-color,box-shadow] duration-200",
                      formRefreshMode === "scheduled"
                        ? "bg-white text-slate-900 shadow-[0_1px_3px_rgb(0_0_0/0.06)]"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    周期定时
                  </button>
                </div>
              </div>

              {/* 同格叠放：隐藏层仍占位，高度取较高面板，切换不跳变 */}
              <div className="grid [&>*]:col-start-1 [&>*]:row-start-1 [&>*]:min-w-0">
                <div
                  className={cn(
                    formRefreshMode === "interval"
                      ? "relative z-10"
                      : "invisible pointer-events-none"
                  )}
                  aria-hidden={formRefreshMode !== "interval"}
                  inert={formRefreshMode !== "interval" || undefined}
                >
                  <div className="space-y-1.5">
                    <Label htmlFor="f-interval-value" className={editDialogLabelClass}>
                      循环间隔
                    </Label>
                    <div className="flex gap-2">
                      <Input
                        id="f-interval-value"
                        type="number"
                        min={formIntervalUnit === "s" ? 30 : 1}
                        step={1}
                        value={formIntervalValue}
                        onChange={(e) => setFormIntervalValue(Number(e.target.value))}
                        className={cn(
                          "h-10 min-w-0 flex-1 font-mono text-[13px] tabular-nums",
                          editDialogFieldClass
                        )}
                      />
                      <IntervalUnitSelect
                        value={formIntervalUnit}
                        onChange={setFormIntervalUnit}
                        portalRef={editDialogContentRef}
                        scrollContainerRef={editDialogScrollRef}
                        aria-label="间隔单位"
                        className={editDialogFieldClass}
                      />
                    </div>
                  </div>
                </div>
                <div
                  className={cn(
                    formRefreshMode === "scheduled"
                      ? "relative z-10"
                      : "invisible pointer-events-none"
                  )}
                  aria-hidden={formRefreshMode !== "scheduled"}
                  inert={formRefreshMode !== "scheduled" || undefined}
                >
                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="f-clock" className={editDialogLabelClass}>
                        触发时间
                      </Label>
                      <ScheduleTimePicker
                        id="f-clock"
                        value={formScheduledClock}
                        onChange={setFormScheduledClock}
                        className={editDialogFieldClass}
                      />
                    </div>
                    <div className="space-y-2">
                      <span className={editDialogLabelClass}>重复</span>
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          type="button"
                          className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                          onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.daily))}
                        >
                          每天
                        </button>
                        <button
                          type="button"
                          className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                          onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.workweek))}
                        >
                          工作日
                        </button>
                        <button
                          type="button"
                          className="rounded-full border border-slate-200/70 bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                          onClick={() => setFormWeekdays(normalizeWeekdaysSelection(WEEKDAY_PRESETS.weekend))}
                        >
                          周末
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5" role="group" aria-label="重复星期">
                        {WEEKDAY_ORDER_UI.map((d) => {
                          const on = formWeekdays.includes(d)
                          return (
                            <button
                              key={d}
                              type="button"
                              aria-label={`周${weekdayShort(d)}`}
                              aria-pressed={on}
                              onClick={() => toggleWeekday(d)}
                              className={cn(
                                "flex h-9 min-w-9 items-center justify-center rounded-full border text-[12px] font-semibold transition-[color,background-color,border-color]",
                                on
                                  ? "border-[#0071e3] bg-[#0071e3] text-white shadow-sm"
                                  : "border-slate-200/80 bg-white/90 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                              )}
                            >
                              {weekdayShort(d)}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-b-[length:var(--radius-surface)]">
            <div className="border-t border-slate-200/45 bg-slate-100/20 px-6 py-2.5">
              <p className="text-[12px] leading-relaxed text-slate-500">{schedulePreviewText}</p>
            </div>

            <div className="relative z-40 flex items-center justify-end gap-2 border-t border-slate-200/50 bg-slate-100/25 px-6 py-3.5 backdrop-blur-sm">
            <Button
              type="button"
              variant="ghost"
              className="rounded-[length:var(--radius-md)] px-4 text-[13px] font-medium text-slate-600 hover:bg-slate-200/45 hover:text-slate-900"
              onClick={closeEditDialog}
            >
              取消
            </Button>
            <Button
              type="button"
              className="rounded-[length:var(--radius-md)] bg-[#0071e3] px-5 text-[13px] font-semibold text-white shadow-sm hover:bg-[#0068cf] focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
              onClick={handleSave}
            >
              保存
            </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AppToast message={toast} />
    </div>
    </TooltipProvider>
  )
}
