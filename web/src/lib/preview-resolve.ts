import { getPreviewPlaceholderSrc } from "./preview-placeholder"
import type { WallRun } from "@/types/api"

/**
 * 提取服务端的 output_path 到前端可用的相对 URL (经 Vite 代理到后端的 /api/...)
 */
function toPreviewUrl(run: WallRun): string | null {
  if (!run.outputPath) return null
  const parts = run.outputPath.split(/[/\\]/)
  const filename = parts[parts.length - 1]
  if (!filename) return null
  return `/api/v1/output/${run.id}/${filename}`
}

export function pickLatestOutputUrlForScene(runs: WallRun[], sceneId: string): string | null {
  for (const r of runs) {
    if (r.sceneId === sceneId && r.ok && r.outputPath) {
      return toPreviewUrl(r)
    }
  }
  return null
}

export function pickLatestOutputUrlForTemplate(runs: WallRun[], templateId: string): string | null {
  for (const r of runs) {
    if (r.templateId === templateId && r.ok && r.outputPath) {
      return toPreviewUrl(r)
    }
  }
  return null
}

export function getFallbackPlaceholder(label?: string) {
  if (!label) return getPreviewPlaceholderSrc("暂无预览")
  return getPreviewPlaceholderSrc(label + " 暂无预览")
}

/** http(s) 或同源相对路径（经 Vite 代理到后端的 /api/...） */
export function isUsableImageRef(s: string | null | undefined): boolean {
  if (!s?.trim()) return false
  const t = s.trim()
  if (t.startsWith("/")) return true
  return /^https?:\/\//i.test(t)
}
