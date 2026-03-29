import {
  Activity,
  Calendar,
  CheckCircle2,
  CircleHelp,
  Clock,
  CloudSun,
  Monitor,
  Pause,
  Pencil,
  Play,
  Settings2,
  Trash2,
} from "lucide-react"
import { motion } from "motion/react"
import { type CSSProperties, useCallback, useDeferredValue, useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { dialogShell, dialogShellCompact } from "@/lib/dialog-shell"
import { cn } from "@/lib/utils"

type ListFilter = "active" | "paused" | "all"

/** 统一为 YYYY-MM-DD HH:mm:ss */
function formatStandardTime(raw: string): string {
  const s = (raw ?? "").trim()
  if (!s || s === "—") return "—"
  const normalized = s.replace("T", " ")
  const m = normalized.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2}):(\d{2})/)
  if (m) {
    const [, date, hh, mm, ss] = m
    return `${date} ${hh.padStart(2, "0")}:${mm}:${ss}`
  }
  return s
}

function formatScheduledNext(raw: string): string {
  const s = (raw ?? "").trim()
  if (!s || s === "—") return "—"
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) return formatStandardTime(s)
  return s
}

/** 列表区紧凑展示：YYYY-MM-DD HH:mm */
function formatTimestampShort(raw: string): string {
  const s = formatStandardTime(raw)
  if (s === "—") return "—"
  return s.replace(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}):\d{2}$/, "$1 $2")
}

/** 顶栏：无年份 MM-DD HH:mm */
function formatTimeNoYear(raw: string): string {
  const s = formatStandardTime(raw)
  if (s === "—") return "—"
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/)
  if (!m) return formatTimestampShort(raw).replace(/^\d{4}-/, "")
  return `${m[2]}-${m[3]} ${m[4]}:${m[5]}`
}

function nextRefreshToDatetimeLocal(raw: string): string {
  const s = formatStandardTime(raw)
  if (s === "—") return ""
  const m = s.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/)
  if (!m) return ""
  return `${m[1]}T${m[2]}:${m[3]}`
}

function datetimeLocalToNextRefresh(v: string): string {
  const t = (v ?? "").trim()
  if (!t) return "—"
  const m = t.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return "—"
  const ss = m[4] ?? "00"
  return `${m[1]} ${m[2]}:${m[3]}:${ss}`
}

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

function lastSuccessEndFormatted(unitId: string): string {
  const logs = RUN_LOGS[unitId] ?? []
  const hit = logs.find((l) => l.ok)
  return hit ? formatStandardTime(hit.end) : "—"
}

const ROW_ACTION_COOLDOWN_MS = 650

type MonitorRow = RunLog & { unitId: string; unitName: string }

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

function nodeStatusPresentation(u: Unit): {
  label: string
  dotClass: string
  dotGlow: string
  dotPulse: boolean
} {
  if (!u.enabled) {
    return {
      label: "停用中",
      dotClass: "bg-slate-400",
      dotGlow:
        // 2px 柔光圈 + 轻微外发光（低饱和）
        "shadow-[0_0_0_2px_rgb(148_163_184/0.18),0_0_0_1px_rgb(255_255_255/0.55),0_0_12px_3px_rgb(100_116_139/0.22)]",
      dotPulse: false,
    }
  }
  if (!u.lastStatus.ok) {
    return {
      label: "异常",
      // 柔玫瑰（比 Rose-500 更淡）
      dotClass: "bg-[#F9A8B3]",
      dotGlow:
        "shadow-[0_0_0_2px_rgb(249_168_179/0.11),0_0_0_1px_rgb(255_255_255/0.55),0_0_12px_4px_rgb(249_168_179/0.14)]",
      dotPulse: false,
    }
  }
  return {
    label: "运行中",
    // 柔翠绿（比 Emerald-500 更淡）
    dotClass: "bg-[#7DD3AE]",
    dotGlow:
      "shadow-[0_0_0_2px_rgb(125_211_174/0.1),0_0_0_1px_rgb(255_255_255/0.55),0_0_12px_4px_rgb(125_211_174/0.13)]",
    dotPulse: true,
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
  const [listFilter, setListFilter] = useState<ListFilter>("active")
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [frameDialogOpen, setFrameDialogOpen] = useState(false)
  const [monitorOpen, setMonitorOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Unit | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [rowBusyId, setRowBusyId] = useState<string | null>(null)

  const [formName, setFormName] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const [formRefreshMode, setFormRefreshMode] = useState<UnitRefreshMode>("interval")
  const [formInterval, setFormInterval] = useState(300)
  const [formScheduledAt, setFormScheduledAt] = useState("")
  const [frameConfig, setFrameConfig] = useState<FrameDisplayConfig>(() => loadFrameConfigFromStorage())
  const [frameDraft, setFrameDraft] = useState<FrameDisplayConfig>(() => ({ ...loadFrameConfigFromStorage() }))

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
  const deleteTargetIsOnDisplay = Boolean(
    deleteTarget && nowOnWall?.id === deleteTarget.id
  )

  const listFiltered = useMemo(() => {
    if (listFilter === "active") return units.filter((u) => u.enabled)
    if (listFilter === "paused") return units.filter((u) => !u.enabled)
    return [...units].sort((a, b) => {
      if (a.enabled !== b.enabled) return a.enabled ? -1 : 1
      return 0
    })
  }, [units, listFilter])

  /** 全部运行记录（监控用） */
  const allRunRows = useMemo(() => {
    const rows: MonitorRow[] = []
    units.forEach((u) => {
      ;(RUN_LOGS[u.id] ?? []).forEach((log) => {
        rows.push({ ...log, unitId: u.id, unitName: u.name })
      })
    })
    return rows.sort((a, b) => (a.start < b.start ? 1 : -1))
  }, [units])

  const pendingRows = useMemo(() => allRunRows.filter((r) => !r.ok), [allRunRows])

  const monitorMetrics = useMemo(() => {
    const last = allRunRows[0]
    const failCount = allRunRows.filter((r) => !r.ok).length
    const recentErrRow = allRunRows.find((r) => !r.ok)
    return {
      lastTaskLabel: last ? (last.ok ? "成功" : "失败") : "—",
      lastTaskTime: last ? formatStandardTime(last.end) : "—",
      failCount,
      recentError: recentErrRow?.err || "暂无",
      recentErrorAt: recentErrRow ? formatStandardTime(recentErrRow.start) : "—",
    }
  }, [allRunRows])

  const previewSrc = (u: Unit) => {
    if (u.previewImageUrl) return u.previewImageUrl
    const idNum = Number(u.id.replace(/\D/g, "")) || 0
    return `https://picsum.photos/id/${1000 + (idNum % 30)}/1440/1080`
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
    setFormName(u.name)
    setFormDescription(u.description)
    setFormRefreshMode(u.refreshMode)
    setFormInterval(u.intervalSeconds)
    setFormScheduledAt(nextRefreshToDatetimeLocal(u.nextRefresh))
    setEditDialogOpen(true)
  }

  const closeEditDialog = () => {
    setEditDialogOpen(false)
    setEditingId(null)
  }

  const handleSave = () => {
    if (!editingId) return
    const name = formName.trim() || "未命名画面"
    const description = formDescription.trim() || "未填写描述"
    const intervalSeconds = Math.max(30, Math.floor(Number(formInterval)) || 300)
    setUnits((prev) =>
      prev.map((u) => {
        if (u.id !== editingId) return u
        let nextRefresh = u.nextRefresh
        if (formRefreshMode === "scheduled") {
          nextRefresh = datetimeLocalToNextRefresh(formScheduledAt)
        } else {
          nextRefresh = computeNextRefreshFromInterval(intervalSeconds)
        }
        return {
          ...u,
          name,
          description,
          refreshMode: formRefreshMode,
          intervalSeconds,
          nextRefresh,
        }
      })
    )
    showToast("已保存")
    closeEditDialog()
  }

  const filterTabs: { key: ListFilter; label: string; count: number }[] = [
    { key: "active", label: "进行中", count: units.filter((u) => u.enabled).length },
    { key: "paused", label: "停用中", count: units.filter((u) => !u.enabled).length },
    { key: "all", label: "全部", count: units.length },
  ]

  return (
    <div className="min-h-screen px-4 pb-24 pt-8 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-4xl space-y-10">
        {/* 顶部：标题 + 画框配置 / 运行监控 */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h1 className="font-display text-[1.75rem] font-semibold leading-snug tracking-tight text-slate-900 sm:text-[2rem]">
            壁上此刻
          </h1>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-11 gap-2 rounded-full border-slate-200 bg-white px-5 shadow-sm"
              onClick={openFrameDialog}
            >
              <Settings2 className="h-4 w-4 text-slate-600" strokeWidth={1.75} />
              画框设置
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-11 gap-2 rounded-full border-slate-200 bg-white px-5 shadow-sm"
              onClick={() => setMonitorOpen(true)}
            >
              <Activity className="h-4 w-4 text-[#0071e3]" strokeWidth={1.75} />
              运行监控
            </Button>
          </div>
        </header>

        {/* 正在展示：顶栏仅保留当前节点与时间（无方向/区块标题）；下方仅预览 */}
        <section aria-labelledby="now-playing-heading" className="space-y-4">
          <h2 id="now-playing-heading" className="sr-only">
            画框上正在展示
          </h2>
          {nowOnWall ? (
            <div className="border-b border-slate-200/70 pb-3">
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[12px] leading-relaxed text-slate-600">
                <span className="shrink-0 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-400">
                  当前展示
                </span>
                <span className="min-w-0 font-semibold text-slate-900">{nowOnWall.name}</span>
                <span className="hidden h-3 w-px bg-slate-200 sm:block" aria-hidden />
                <span className="inline-flex items-center gap-1 whitespace-nowrap">
                  <span className="text-slate-500">上次成功</span>
                  <CheckCircle2
                    className="h-3.5 w-3.5 shrink-0 text-[#5EB89A]"
                    strokeWidth={1.75}
                    aria-hidden
                  />
                  <span className="font-mono text-[12px] tabular-nums text-slate-800">
                    {formatTimeNoYear(lastSuccessEndFormatted(nowOnWall.id))}
                  </span>
                </span>
                <span className="text-slate-200">·</span>
                <span className="inline-flex items-center gap-1 whitespace-nowrap">
                  <span className="text-slate-500">下次更新</span>
                  <Clock className="h-3.5 w-3.5 shrink-0 text-slate-400" strokeWidth={1.75} aria-hidden />
                  <span className="font-mono text-[12px] tabular-nums text-slate-800">
                    {formatTimeNoYear(formatScheduledNext(nowOnWall.nextRefresh))}
                  </span>
                </span>
              </p>
            </div>
          ) : null}

          {nowOnWall ? (
            <>
              <div
                className={cn(
                  "flex justify-center rounded-[1.8rem] px-4 py-5 sm:px-6 sm:py-7",
                  "bg-gradient-to-b from-slate-200/45 via-slate-100/25 to-transparent",
                  previewFrame.orientation === "portrait" &&
                    "from-slate-300/40 via-slate-800/[0.07] to-transparent"
                )}
              >
                <div className="flex w-full max-w-[min(100%,980px)] justify-center">
                  {previewFrame.orientation === "landscape" ? (
                    <div
                      className={cn(
                        "relative aspect-[4/3] h-[min(34vh,288px)] w-auto max-w-full overflow-hidden rounded-[1.35rem] bg-slate-900/[0.04]",
                        "shadow-[0_0_0_1px_rgb(15_23_42/0.05),0_26px_70px_-40px_rgb(15_23_42/0.16)] ring-1 ring-slate-900/[0.055]"
                      )}
                    >
                      {/* 物理画框：哑光金属外框 + 高光边 + 内阴影嵌入感 */}
                      <div className="absolute inset-0 p-1">
                        <div
                          className={cn(
                            "relative h-full w-full rounded-[12px] bg-[#1f232b]",
                            "shadow-[inset_0_1px_0_rgb(255_255_255/0.12),inset_0_0_0_1px_rgb(255_255_255/0.08)]"
                          )}
                        >
                          <div className="absolute inset-1 overflow-hidden rounded-[10px] bg-black shadow-[inset_0_0_0_1px_rgb(0_0_0/0.28),inset_0_8px_18px_rgb(0_0_0/0.2)]">
                            <PreviewFrame
                              src={previewSrc(nowOnWall)}
                              alt={`${nowOnWall.name} 当前画面预览`}
                              imageFilter={previewFilter}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div
                      className={cn(
                        "relative aspect-[3/4] h-[min(46vh,380px)] w-auto max-w-full overflow-hidden rounded-[1.35rem] bg-black sm:h-[min(44vh,360px)]",
                        "shadow-[0_0_0_1px_rgb(255_255_255/0.06),0_32px_80px_-36px_rgb(0_0_0/0.45)] ring-1 ring-white/12"
                      )}
                    >
                      {/* 物理画框：哑光金属外框 + 高光边 + 内阴影嵌入感 */}
                      <div className="absolute inset-0 p-1">
                        <div
                          className={cn(
                            "relative h-full w-full rounded-[12px] bg-[#1f232b]",
                            "shadow-[inset_0_1px_0_rgb(255_255_255/0.12),inset_0_0_0_1px_rgb(255_255_255/0.08)]"
                          )}
                        >
                          <div className="absolute inset-1 overflow-hidden rounded-[10px] bg-black shadow-[inset_0_0_0_1px_rgb(0_0_0/0.28),inset_0_8px_18px_rgb(0_0_0/0.2)]">
                            <PreviewFrame
                              src={previewSrc(nowOnWall)}
                              alt={`${nowOnWall.name} 当前画面预览`}
                              imageFilter={previewFilter}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200/90 bg-slate-50/60 px-6 py-14 text-center">
              <p className="text-[15px] font-semibold text-slate-800">暂无画框展示内容</p>
              <p className="mx-auto mt-1.5 max-w-sm text-[12px] leading-relaxed text-slate-500">
                启用至少一个绘画节点后，将在此显示预览与刷新时间。
              </p>
            </div>
          )}
        </section>

        {/* 绘画节点列表 */}
        <section className="space-y-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-slate-900">绘画节点</h2>
            <div
              className="relative flex flex-wrap gap-0 rounded-full bg-slate-200/55 p-1 ring-1 ring-slate-900/[0.05]"
              role="tablist"
              aria-label="筛选列表"
            >
              {filterTabs.map(({ key, label, count }) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={listFilter === key}
                  onClick={() => setListFilter(key)}
                  className={cn(
                    "relative z-10 rounded-full px-3.5 py-2.5 text-[13px] font-medium transition-colors duration-200",
                    listFilter === key
                      ? "text-slate-900"
                      : key === "all"
                        ? "text-slate-400 hover:text-slate-600"
                        : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  {listFilter === key ? (
                    <motion.span
                      layoutId="node-filter-pill"
                      className="absolute inset-0 -z-10 rounded-full bg-white shadow-[0_1px_2px_rgb(0_0_0/0.04),0_20px_48px_-28px_rgb(15_23_42/0.12)] ring-1 ring-slate-900/[0.06]"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  ) : null}
                  <span className="relative z-10">
                    {label}
                    <span
                      className={cn(
                        "ml-1 tabular-nums text-[12px]",
                        listFilter === key ? "text-slate-500" : "text-slate-400"
                      )}
                    >
                      {count}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <ul className="space-y-4">
            {listFiltered.map((u) => {
              const disabled = !u.enabled
              const rowLocked = rowBusyId === u.id
              const status = nodeStatusPresentation(u)
              return (
                <li
                  key={u.id}
                  className={cn(
                    "group rounded-[1.35rem] border border-slate-900/[0.055] bg-white/95 shadow-[0_0_0_1px_rgb(15_23_42/0.04),0_28px_72px_-36px_rgb(15_23_42/0.14),0_12px_28px_-18px_rgb(15_23_42/0.06)] backdrop-blur-[2px]",
                    disabled && listFilter === "all" && "opacity-[0.72]"
                  )}
                >
                  <div className="flex flex-col gap-4 px-6 py-6 sm:py-7">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span
                        className={cn(
                          "inline-block h-2 w-2 shrink-0 rounded-full",
                          status.dotClass,
                          status.dotGlow,
                          status.dotPulse && "animate-status-breathe"
                        )}
                        aria-hidden
                      />
                      <h3 className="min-w-0 text-[17px] font-semibold leading-[1.35] tracking-tight text-slate-900">
                        {u.name}
                        <span className="sr-only"> · {status.label}</span>
                      </h3>
                    </div>
                    <p
                      className="line-clamp-2 text-[13px] font-light leading-[1.85] text-slate-500"
                      title={u.description}
                    >
                      {u.description}
                    </p>
                    <div className="flex flex-col gap-4 border-t border-slate-100/90 pt-4 sm:flex-row sm:items-center sm:justify-between sm:gap-5">
                      <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5 text-[12px] leading-relaxed text-slate-600">
                        <span className="inline-flex items-center gap-1 whitespace-nowrap">
                          <span className="text-slate-500">上次成功</span>
                          <CheckCircle2
                            className="h-3.5 w-3.5 shrink-0 text-[#5EB89A]"
                            strokeWidth={1.75}
                            aria-hidden
                          />
                          <span className="font-mono tabular-nums text-slate-800">
                            {formatTimeNoYear(lastSuccessEndFormatted(u.id))}
                          </span>
                        </span>
                        <span className="text-slate-200">·</span>
                        <span className="inline-flex items-center gap-1 whitespace-nowrap">
                          <span className="text-slate-500">下次更新</span>
                          <Clock className="h-3.5 w-3.5 shrink-0 text-slate-400" strokeWidth={1.75} aria-hidden />
                          <span className="font-mono tabular-nums text-slate-800">
                            {formatTimeNoYear(formatScheduledNext(u.nextRefresh))}
                          </span>
                        </span>
                      </p>
                      <div className="flex shrink-0 flex-wrap items-center justify-end gap-0.5">
                        {!u.enabled ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-10 w-10 shrink-0 rounded-full text-slate-700 transition-[background-color,color,transform] duration-200 hover:bg-slate-900 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/30 active:scale-95"
                            disabled={rowLocked}
                            title="启用"
                            aria-label={`启用「${u.name}」`}
                            onClick={() =>
                              withRowCooldown(u.id, () => {
                                setUnits((prev) => prev.map((x) => (x.id === u.id ? { ...x, enabled: true } : x)))
                                showToast(`「${u.name}」已启用，列表已更新`)
                              })
                            }
                          >
                            <Play className="h-[17px] w-[17px]" strokeWidth={1.25} />
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-10 w-10 shrink-0 rounded-full text-slate-700 transition-[background-color,color,transform] duration-200 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20 active:scale-95"
                            disabled={rowLocked}
                            title="停用"
                            aria-label={`停用「${u.name}」`}
                            onClick={() =>
                              withRowCooldown(u.id, () => {
                                setUnits((prev) => prev.map((x) => (x.id === u.id ? { ...x, enabled: false } : x)))
                                showToast(`「${u.name}」已停用，列表已更新`)
                              })
                            }
                          >
                            <Pause className="h-[17px] w-[17px]" strokeWidth={1.25} />
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-10 w-10 shrink-0 rounded-full text-slate-700 transition-[background-color,color,transform] duration-200 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20 active:scale-95"
                          disabled={rowLocked}
                          title="编辑"
                          aria-label={`编辑「${u.name}」`}
                          onClick={() => openEdit(u.id)}
                        >
                          <Pencil className="h-[17px] w-[17px]" strokeWidth={1.25} />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-10 w-10 shrink-0 rounded-full text-slate-700 transition-[background-color,color,transform] duration-200 hover:bg-rose-50 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-200/80 active:scale-95"
                          disabled={rowLocked}
                          title="删除"
                          aria-label={`删除「${u.name}」`}
                          onClick={() => setDeleteTarget(u)}
                        >
                          <Trash2 className="h-[17px] w-[17px]" strokeWidth={1.25} />
                        </Button>
                      </div>
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
          <DialogHeader className="border-b border-slate-100 px-6 pb-3.5 pt-5 pr-14 text-left">
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
                          <button
                            type="button"
                            className="inline-flex shrink-0 rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/30"
                            title={techTip}
                            aria-label={`${spec.label}：技术说明与默认值`}
                          >
                            <CircleHelp className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
                          </button>
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
                              <button
                                type="button"
                                title={`点击恢复默认 ${spec.defaultValue.toFixed(2)}`}
                                aria-label={`${spec.label} 恢复为默认 ${spec.defaultValue.toFixed(2)}`}
                                className="w-full rounded-md px-1 py-0.5 text-right font-mono text-[13px] text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                                onClick={() => resetSlider(spec.key)}
                              >
                                {v.toFixed(2)}
                              </button>
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

          <div className="flex gap-2 border-t border-slate-200/80 bg-slate-50/90 px-6 py-3.5">
            <Button
              type="button"
              variant="outline"
              className="flex-1 rounded-xl border-slate-200 bg-white"
              onClick={() => setFrameDialogOpen(false)}
            >
              取消
            </Button>
            <Button
              type="button"
              className="flex-1 rounded-xl bg-slate-900 text-white hover:bg-slate-800"
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
          className={dialogShell("max-h-[min(92dvh,720px)] w-[calc(100vw-1.5rem)] max-w-xl sm:max-w-xl")}
        >
          <DialogHeader className="border-b border-slate-100 px-6 pb-3.5 pt-5 pr-14 text-left">
            <DialogTitle className="text-[17px] font-semibold tracking-tight text-slate-900">编辑节点</DialogTitle>
          </DialogHeader>

          <div className="max-h-[min(58dvh,520px)] overflow-y-auto px-6 py-4">
            <div className="space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="f-name" className="text-xs font-medium text-slate-500">
                  节点名称
                </Label>
                <Input
                  id="f-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="例如：早上天气"
                  className="h-10 rounded-xl text-[13px]"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="f-desc" className="text-xs font-medium text-slate-500">
                  简要描述
                </Label>
                <textarea
                  id="f-desc"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  rows={3}
                  maxLength={120}
                  placeholder="用途、场景或数据来源（建议 20–40 字）"
                  className="flex w-full resize-none rounded-xl border border-slate-200/90 bg-white px-3 py-2.5 text-[13px] text-slate-900 shadow-sm placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="f-refresh-mode" className="text-xs font-medium text-slate-500">
                  更新时间
                </Label>
                <select
                  id="f-refresh-mode"
                  value={formRefreshMode}
                  onChange={(e) => setFormRefreshMode(e.target.value as UnitRefreshMode)}
                  className="flex h-10 w-full rounded-xl border border-slate-200/90 bg-white px-3 text-[13px] shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]/35"
                >
                  <option value="interval">间隔更新</option>
                  <option value="scheduled">定时更新</option>
                </select>
                {formRefreshMode === "interval" ? (
                  <div className="space-y-1.5 pt-1">
                    <Label htmlFor="f-interval" className="text-xs text-slate-500">
                      间隔（秒）
                    </Label>
                    <Input
                      id="f-interval"
                      type="number"
                      min={30}
                      step={30}
                      value={formInterval}
                      onChange={(e) => setFormInterval(Number(e.target.value))}
                      className="h-10 rounded-xl font-mono text-[13px]"
                    />
                  </div>
                ) : (
                  <div className="space-y-1.5 pt-1">
                    <Label htmlFor="f-scheduled" className="text-xs text-slate-500">
                      下次刷新时间
                    </Label>
                    <Input
                      id="f-scheduled"
                      type="datetime-local"
                      value={formScheduledAt}
                      onChange={(e) => setFormScheduledAt(e.target.value)}
                      className="h-10 rounded-xl font-mono text-[13px]"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-2 border-t border-slate-200/80 bg-slate-50/90 px-6 py-3.5">
            <Button
              type="button"
              variant="outline"
              className="flex-1 rounded-xl border-slate-200 bg-white"
              onClick={closeEditDialog}
            >
              取消
            </Button>
            <Button
              type="button"
              className="flex-1 rounded-xl bg-slate-900 text-white hover:bg-slate-800"
              onClick={handleSave}
            >
              保存
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 运行监控 */}
      <Dialog open={monitorOpen} onOpenChange={setMonitorOpen}>
        <DialogContent
          className={dialogShell("max-h-[90vh] w-[calc(100vw-1.5rem)] max-w-3xl sm:max-w-3xl")}
        >
          <DialogHeader className="border-b border-slate-100 px-6 pb-4 pt-6 pr-14">
            <div className="flex items-start justify-between gap-3">
              <DialogTitle className="flex items-center gap-2 text-lg font-semibold text-slate-900">
                <Activity className="h-5 w-5 text-[#0071e3]" />
                运行监控
              </DialogTitle>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0 rounded-full"
                onClick={() => {
                  setMonitorOpen(false)
                  const first = units[0]
                  if (first) openEdit(first.id)
                }}
              >
                打开节点日志
              </Button>
            </div>
          </DialogHeader>

          <div className="max-h-[calc(90vh-6.5rem)] overflow-y-auto px-6 pb-6">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">最近任务</p>
                <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="text-[15px] font-semibold text-slate-900">{monitorMetrics.lastTaskLabel}</p>
                  <p
                    className={cn(
                      "text-[12px] font-semibold tabular-nums",
                      monitorMetrics.failCount > 0 ? "text-rose-700" : "text-slate-500"
                    )}
                  >
                    失败 {monitorMetrics.failCount}
                  </p>
                </div>
                <p className="mt-1 font-mono text-[12px] text-slate-600">{monitorMetrics.lastTaskTime}</p>
              </div>
              <div className="rounded-2xl border border-slate-100 bg-slate-50/80 px-4 py-3">
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">最近错误</p>
                <p className="mt-1 line-clamp-2 text-[13px] leading-snug text-slate-800" title={monitorMetrics.recentError}>
                  {monitorMetrics.recentError}
                </p>
                <p className="mt-1 font-mono text-[11px] text-slate-400">{monitorMetrics.recentErrorAt}</p>
              </div>
            </div>

            <div className="mt-8">
              <h3 className="text-[13px] font-semibold text-slate-900">异常队列</h3>
              {pendingRows.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-4 py-6 text-center text-[13px] text-slate-500">
                  暂无失败记录
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {pendingRows.map((row, i) => (
                    <li
                      key={`${row.unitId}-${row.start}-${i}`}
                      className="flex flex-col gap-2 rounded-2xl border border-rose-100 bg-rose-50/35 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-slate-900">{row.unitName}</p>
                        <p className="font-mono text-[12px] text-slate-500">
                          {formatStandardTime(row.start)} · 失败
                        </p>
                        {row.err ? <p className="mt-1 text-[12px] text-rose-700">{row.err}</p> : null}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="shrink-0 rounded-full border-slate-200 text-[12px]"
                        onClick={() => {
                          setMonitorOpen(false)
                          openEdit(row.unitId)
                        }}
                      >
                        查看节点
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-8">
              <h3 className="text-[13px] font-semibold text-slate-900">最近运行</h3>
              <ul className="mt-3 space-y-2">
                {allRunRows.slice(0, 10).map((row, i) => (
                  <li
                    key={`${row.unitId}-${row.start}-${i}`}
                    className={cn(
                      "grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-1 rounded-xl border px-3 py-2.5 text-[12px]",
                      row.ok ? "border-slate-100 bg-white" : "border-rose-100 bg-rose-50/30"
                    )}
                  >
                    <span className="min-w-0 truncate font-medium text-slate-800">{row.unitName}</span>
                    <span className="justify-self-end font-mono text-slate-500">{formatStandardTime(row.start)}</span>
                    <span
                      className={cn(
                        "rounded-md px-2 py-0.5 text-[11px] font-semibold",
                        row.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-100 text-rose-800"
                      )}
                    >
                      {row.ok ? "成功" : "失败"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <DialogContent className={dialogShellCompact("w-[calc(100vw-1.5rem)] max-w-md")}>
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold text-slate-900">确认删除节点？</DialogTitle>
            {deleteTarget ? (
              <div className="space-y-3 pt-2 text-left text-[13px] leading-relaxed text-slate-600">
                <p>
                  即将删除「<span className="font-medium text-slate-800">{deleteTarget.name}</span>
                  」。此操作仅移除配置与调度，<strong className="font-medium text-slate-800">不会删除</strong>
                  服务端已持久化的运行与输出历史（演示页中的运行记录为静态示例，亦不受此删除影响）。
                </p>
                <p>
                  {deleteTargetIsOnDisplay ? (
                    <>
                      该节点<strong className="font-medium text-slate-800">正在画框上展示</strong>
                      ，删除后画框将<strong className="font-medium text-slate-800">立即</strong>
                      切换为下一个已启用且可展示节点；若无可用节点，当前展示区域将变为无内容。
                    </>
                  ) : (
                    <>
                      该节点<strong className="font-medium text-slate-800">不是</strong>
                      当前展示节点，删除后<strong className="font-medium text-slate-800">不会</strong>
                      改变画框当前画面。
                    </>
                  )}
                </p>
              </div>
            ) : null}
          </DialogHeader>
          <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="rounded-full"
              onClick={() => setDeleteTarget(null)}
            >
              取消
            </Button>
            <Button
              type="button"
              className="rounded-full bg-rose-600 text-white hover:bg-rose-700"
              disabled={!deleteTarget || rowBusyId === deleteTarget?.id}
              onClick={() => {
                if (!deleteTarget || rowBusyId === deleteTarget.id) return
                const name = deleteTarget.name
                const id = deleteTarget.id
                setDeleteTarget(null)
                withRowCooldown(id, () => {
                  setUnits((prev) => prev.filter((x) => x.id !== id))
                  showToast(`「${name}」已删除，列表已更新`)
                })
              }}
            >
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {toast ? (
        <div
          className="fixed bottom-8 left-1/2 z-[100] max-w-sm -translate-x-1/2 rounded-full border border-white/12 bg-[#1d1d1f]/95 px-5 py-2.5 text-center text-[13px] font-medium text-white shadow-lg backdrop-blur-xl"
          role="status"
        >
          {toast}
        </div>
      ) : null}
    </div>
  )
}
