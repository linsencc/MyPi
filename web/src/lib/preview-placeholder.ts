/**
 * 内联 data URI：不依赖 `/public` 与部署 base，避免占位图 404 导致整页「预览图加载失败」。
 */
export function getPreviewPlaceholderSrc(label: string = "No preview URL"): string {
  const escapedLabel = label.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  return (
    "data:image/svg+xml;charset=utf-8," +
    encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">` +
        `<rect width="100%" height="100%" fill="#e2e8f0"/>` +
        `<rect x="8" y="8" width="384" height="284" rx="8" fill="none" stroke="#94a3b8" stroke-width="2"/>` +
        `<text x="200" y="160" text-anchor="middle" fill="#64748b" font-family="system-ui,sans-serif" font-size="14">${escapedLabel}</text>` +
        `</svg>`
    )
  )
}

export const PREVIEW_PLACEHOLDER_SRC = getPreviewPlaceholderSrc()

export function isDataImagePlaceholder(src: string): boolean {
  return src.startsWith("data:image/svg+xml")
}
