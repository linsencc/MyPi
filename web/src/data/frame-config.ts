/**
 * 画框配置：方向 + InkyPi（fatihak/InkyPi）image_settings。
 * @see https://github.com/fatihak/InkyPi/blob/main/src/blueprints/settings.py
 * @see https://github.com/fatihak/InkyPi/blob/main/src/utils/image_utils.py apply_image_enhancement
 */

export type FrameOrientation = "landscape" | "portrait"

/** 与 InkyPi device_config.image_settings 字段一致 */
export interface InkypiImageSettings {
  /** PIL ImageEnhance.Color，默认 1.0 */
  saturation: number
  /** PIL ImageEnhance.Contrast，默认 1.0 */
  contrast: number
  /** PIL ImageEnhance.Sharpness，默认 1.0 */
  sharpness: number
  /** PIL ImageEnhance.Brightness，默认 1.0 */
  brightness: number
  /** Inky 驱动 set_image 饱和度，默认 0.5（与 InkyPi 表单一致） */
  inky_saturation: number
}

export interface FrameDisplayConfig {
  orientation: FrameOrientation
  imageSettings: InkypiImageSettings
  timelineMaxEvents?: number
}

export const INKYPI_IMAGE_DEFAULTS: InkypiImageSettings = {
  saturation: 1.0,
  contrast: 1.0,
  sharpness: 1.0,
  brightness: 1.0,
  inky_saturation: 0.5,
}

export const DEFAULT_FRAME_CONFIG: FrameDisplayConfig = {
  orientation: "portrait",
  imageSettings: { ...INKYPI_IMAGE_DEFAULTS },
  timelineMaxEvents: 30,
}

/** 滑块定义：范围参照 InkyPi Web 可调与 PIL enhance 常用区间 */
export const INKYPI_SLIDER_SPECS: {
  key: keyof InkypiImageSettings
  label: string
  /** InkyPi / PIL 语境短说明 */
  hint: string
  min: number
  max: number
  step: number
  defaultValue: number
}[] = [
  {
    key: "saturation",
    label: "饱和度",
    hint: "对应 InkyPi「Saturation」· PIL Color",
    min: 0,
    max: 2,
    step: 0.05,
    defaultValue: 1.0,
  },
  {
    key: "contrast",
    label: "对比度",
    hint: "对应 InkyPi「Contrast」· PIL Contrast",
    min: 0.5,
    max: 2,
    step: 0.05,
    defaultValue: 1.0,
  },
  {
    key: "sharpness",
    label: "锐度",
    hint: "对应 InkyPi「Sharpness」· PIL Sharpness",
    min: 0,
    max: 2,
    step: 0.05,
    defaultValue: 1.0,
  },
  {
    key: "brightness",
    label: "亮度",
    hint: "对应 InkyPi「Brightness」· PIL Brightness",
    min: 0.5,
    max: 2,
    step: 0.05,
    defaultValue: 1.0,
  },
  {
    key: "inky_saturation",
    label: "Inky 驱动饱和",
    hint: "对应 InkyPi「Inky Driver Saturation」· 下发 set_image",
    min: 0,
    max: 1,
    step: 0.05,
    defaultValue: 0.5,
  },
]

const STORAGE_KEY = "mypi-inkypi-frame-config"

function clampSettings(s: Partial<InkypiImageSettings>): InkypiImageSettings {
  const d = { ...INKYPI_IMAGE_DEFAULTS }
  for (const spec of INKYPI_SLIDER_SPECS) {
    const v = s[spec.key]
    if (typeof v === "number" && !Number.isNaN(v)) {
      d[spec.key] = Math.min(spec.max, Math.max(spec.min, v))
    }
  }
  return d
}

export function loadFrameConfigFromStorage(): FrameDisplayConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_FRAME_CONFIG, imageSettings: { ...INKYPI_IMAGE_DEFAULTS } }
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const orientation =
      parsed.orientation === "portrait" || parsed.orientation === "landscape"
        ? parsed.orientation
        : DEFAULT_FRAME_CONFIG.orientation
    let imageSettings: InkypiImageSettings
    if (parsed.imageSettings && typeof parsed.imageSettings === "object") {
      imageSettings = clampSettings(parsed.imageSettings as Partial<InkypiImageSettings>)
    } else {
      imageSettings = { ...INKYPI_IMAGE_DEFAULTS }
    }
    return { orientation, imageSettings, timelineMaxEvents: parsed.timelineMaxEvents as number | undefined ?? 30 }
  } catch {
    return { ...DEFAULT_FRAME_CONFIG, imageSettings: { ...INKYPI_IMAGE_DEFAULTS } }
  }
}

export function saveFrameConfigToStorage(cfg: FrameDisplayConfig): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        orientation: cfg.orientation,
        imageSettings: clampSettings(cfg.imageSettings),
        timelineMaxEvents: cfg.timelineMaxEvents,
      })
    )
  } catch {
    /* ignore */
  }
}

/**
 * 预览用 CSS filter：顺序接近 apply_image_enhancement（亮度→对比→色饱和→锐化近似）。
 * 彩色墨水屏：不套 grayscale。饱和度滑到 0 时 CSS saturate(0) 会变成纯灰预览，
 * 与实机彩色不符，故对 saturate 设下限。
 */
export function getPreviewImageFilter(s: InkypiImageSettings): string {
  const b = Math.max(0.2, Math.min(2.5, s.brightness))
  const c = Math.max(0.2, Math.min(2.5, s.contrast))
  const col = Math.max(0, Math.min(3, s.saturation))
  const ink = Math.max(0, Math.min(1, s.inky_saturation))
  const sharp = Math.max(0, Math.min(2, s.sharpness))
  const contrastBoost = c * (1 + Math.max(0, sharp - 1) * 0.15) * (0.88 + ink * 0.28)
  const sat = Math.max(0.55, col * (0.75 + ink * 0.5))
  return `brightness(${b}) contrast(${contrastBoost}) saturate(${sat})`
}
