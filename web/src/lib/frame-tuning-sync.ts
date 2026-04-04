import type { FrameDisplayConfig, InkypiImageSettings } from "@/data/frame-config"
import {
  DEFAULT_FRAME_CONFIG,
  INKYPI_IMAGE_DEFAULTS,
  INKYPI_SLIDER_SPECS,
} from "@/data/frame-config"

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

/** 从 AppConfig.frameTuning 解析画框 UI 状态（与后端约定嵌套结构） */
export function parseFrameTuning(raw: Record<string, unknown> | undefined): FrameDisplayConfig {
  if (!raw || typeof raw !== "object") {
    return {
      orientation: DEFAULT_FRAME_CONFIG.orientation,
      imageSettings: { ...INKYPI_IMAGE_DEFAULTS },
    }
  }
  const orientation =
    raw.orientation === "portrait" || raw.orientation === "landscape"
      ? raw.orientation
      : DEFAULT_FRAME_CONFIG.orientation
  let imageSettings: InkypiImageSettings
  if (raw.imageSettings && typeof raw.imageSettings === "object") {
    imageSettings = clampSettings(raw.imageSettings as Partial<InkypiImageSettings>)
  } else {
    imageSettings = { ...INKYPI_IMAGE_DEFAULTS }
  }
  return { orientation, imageSettings }
}

export function frameConfigToTuning(cfg: FrameDisplayConfig): Record<string, unknown> {
  return {
    orientation: cfg.orientation,
    imageSettings: clampSettings(cfg.imageSettings),
  }
}
