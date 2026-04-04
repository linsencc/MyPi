export type UnitRefreshMode = "interval" | "scheduled"

export interface Unit {
  id: string
  name: string
  /** 卡片简述：用途 / 场景 / 数据来源，约 20–40 字 */
  description: string
  typeKey: string
  typeLabel: string
  enabled: boolean
  nextRefresh: string
  /** 演示：刷新策略（间隔 / 定时），在编辑节点弹窗中配置 */
  refreshMode: UnitRefreshMode
  /** 间隔更新时的周期（秒）；定时模式下可保留上次值供切换回间隔时使用 */
  intervalSeconds: number
  lastStatus: { ok: boolean; text: string }
  /** 当前画面预览图，可为实际输出缩略图地址；演示用占位 */
  previewImageUrl?: string
}

export type ParamDef =
  | {
      key: string
      label: string
      type: "number"
      required?: boolean
      default: number
      min?: number
      max?: number
      step?: number
      hint?: string
    }
  | {
      key: string
      label: string
      type: "string"
      required?: boolean
      default: string
      hint?: string
    }
  | {
      key: string
      label: string
      type: "boolean"
      required?: boolean
      default: boolean
      hint?: string
    }
  | {
      key: string
      label: string
      type: "enum"
      required?: boolean
      default: string
      options: string[]
      hint?: string
    }

export interface RunLog {
  start: string
  end: string
  ms: number
  ok: boolean
  err: string
  path: string
}

export const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "image-weather", label: "图片生成 · 天气卡片" },
  { value: "image-calendar", label: "图片生成 · 月历" },
  { value: "output-screen", label: "屏幕输出" },
]

export const INITIAL_UNITS: Unit[] = [
  {
    id: "u1",
    name: "早间天气卡片",
    description: "晨起场景展示今日天气与空气质量，数据来自本地天气接口。",
    typeKey: "image-weather",
    typeLabel: "图片生成 · 天气卡片",
    enabled: true,
    nextRefresh: "2026-03-29 08:05:00",
    refreshMode: "interval",
    intervalSeconds: 300,
    lastStatus: { ok: true, text: "成功 · 1.2s" },
    previewImageUrl: "/shunde-city-sounds.png",
  },
  {
    id: "u2",
    name: "客厅月历",
    description: "客厅常驻月历画面，按月轮播节日与日程摘要。",
    typeKey: "image-calendar",
    typeLabel: "图片生成 · 月历",
    enabled: true,
    nextRefresh: "2026-03-29 09:00:00",
    refreshMode: "scheduled",
    intervalSeconds: 3600,
    lastStatus: { ok: true, text: "成功 · 0.8s" },
    previewImageUrl: "https://picsum.photos/seed/mypi-frame-u2/1440/1080",
  },
  {
    id: "u3",
    name: "水墨屏主输出",
    description: "将合成画面推送至电子墨水屏设备，含尺寸与全刷策略。",
    typeKey: "output-screen",
    typeLabel: "屏幕输出",
    enabled: true,
    nextRefresh: "—",
    refreshMode: "interval",
    intervalSeconds: 120,
    lastStatus: { ok: false, text: "失败 · 尺寸校验" },
    previewImageUrl: "https://picsum.photos/seed/mypi-frame-u3/1440/1080",
  },
]

export const PARAM_SCHEMA: Record<string, ParamDef[]> = {
  "image-weather": [
    {
      key: "canvas_w",
      label: "画布宽度",
      type: "number",
      required: true,
      default: 800,
      min: 400,
      max: 1200,
      hint: "须匹配屏幕分辨率",
    },
    {
      key: "canvas_h",
      label: "画布高度",
      type: "number",
      required: true,
      default: 480,
      min: 300,
      max: 800,
    },
    {
      key: "theme",
      label: "主题",
      type: "enum",
      required: false,
      default: "light",
      options: ["light", "dark", "high-contrast"],
      hint: "枚举示例",
    },
    {
      key: "data_url",
      label: "数据来源地址",
      type: "string",
      required: true,
      default: "https://api.example/weather",
      hint: "字符串 · 必填",
    },
    { key: "dither", label: "启用抖动", type: "boolean", required: false, default: true },
  ],
  "image-calendar": [
    {
      key: "orientation",
      label: "方向",
      type: "enum",
      required: true,
      default: "landscape",
      options: ["landscape", "portrait"],
    },
    {
      key: "font_scale",
      label: "字体缩放",
      type: "number",
      required: false,
      default: 1,
      min: 0.8,
      max: 1.4,
      step: 0.1,
    },
    { key: "locale", label: "区域", type: "string", required: false, default: "zh-CN" },
  ],
  "output-screen": [
    { key: "device_path", label: "设备路径", type: "string", required: true, default: "/dev/epd0" },
    {
      key: "full_refresh_every",
      label: "每 N 次全刷",
      type: "number",
      required: true,
      default: 5,
      min: 1,
      max: 20,
      hint: "局刷/全刷策略",
    },
    { key: "dedupe", label: "相同内容去重", type: "boolean", required: false, default: true },
  ],
}

export const RUN_LOGS: Record<string, RunLog[]> = {
  u1: [
    {
      start: "2026-03-29 07:55:01",
      end: "2026-03-29 07:55:02",
      ms: 1200,
      ok: true,
      err: "",
      path: "/var/epd/out/weather_20260329_0755.png",
    },
    {
      start: "2026-03-29 07:25:00",
      end: "2026-03-29 07:25:01",
      ms: 980,
      ok: true,
      err: "",
      path: "/var/epd/out/weather_20260329_0725.png",
    },
  ],
  u2: [
    {
      start: "2026-03-29 07:00:00",
      end: "2026-03-29 07:00:01",
      ms: 810,
      ok: true,
      err: "",
      path: "/var/epd/out/cal_202603.png",
    },
  ],
  u3: [
    {
      start: "2026-03-29 06:58:12",
      end: "2026-03-29 06:58:12",
      ms: 320,
      ok: false,
      err: "校验失败：宽度 810 与设备 800 不一致",
      path: "—",
    },
  ],
}
