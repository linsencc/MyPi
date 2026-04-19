import { getWallState } from "@/api/client"
import type { WallState } from "@/types/api"

export type WaitWallTarget =
  | { type: "scene"; sceneId: string }
  | { type: "template"; templateId: string }

const OUTPUT_PREVIEW_RE = /^\/api\/v1\/output\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/.+/i

function previewLooksReady(url: string | null | undefined): boolean {
  const u = url?.trim() ?? ""
  return OUTPUT_PREVIEW_RE.test(u)
}

function wallStateMatchesTarget(ws: WallState, target: WaitWallTarget): boolean {
  if (target.type === "scene") {
    return ws.currentSceneId === target.sceneId
  }
  return ws.currentTemplateId === target.templateId
}

/** Pi 渲染段持有 displayActiveSceneId；完成后与 currentPreviewUrl 一并更新。 */
export function isWallStateRenderComplete(
  ws: WallState,
  target: WaitWallTarget
): boolean {
  if (ws.displayActiveSceneId) return false
  if (!wallStateMatchesTarget(ws, target)) return false
  return previewLooksReady(ws.currentPreviewUrl)
}

export async function waitForWallPreview(
  target: WaitWallTarget,
  options?: {
    timeoutMs?: number
    intervalMs?: number
    onTick?: (ws: WallState) => void
  }
): Promise<WallState> {
  const timeoutMs = options?.timeoutMs ?? 120_000
  const intervalMs = options?.intervalMs ?? 550
  const onTick = options?.onTick
  const t0 = Date.now()
  let last: WallState | null = null

  while (Date.now() - t0 < timeoutMs) {
    last = await getWallState()
    onTick?.(last)
    if (isWallStateRenderComplete(last, target)) return last
    await new Promise((r) => setTimeout(r, intervalMs))
  }

  throw new Error("上屏超时，请稍后刷新页面或查看树莓派日志")
}
