import type { AppConfig, Scene, TemplateMeta, WallRun, WallState } from "@/types/api"

const PREFIX = "/api/v1"

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: unknown = null
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function parseBody(r: Response): Promise<unknown> {
  const ct = r.headers.get("content-type") ?? ""
  if (!ct.includes("application/json")) return null
  try {
    return await r.json()
  } catch {
    return null
  }
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : `${PREFIX}${path}`
  const headers: HeadersInit = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string>),
  }
  if (init?.body != null && typeof init.body === "string" && !("Content-Type" in (headers as object))) {
    ;(headers as Record<string, string>)["Content-Type"] = "application/json"
  }
  const r = await fetch(url, { ...init, headers })
  if (r.status === 204) {
    return undefined as T
  }
  const data = await parseBody(r)
  if (!r.ok) {
    const msg =
      data && typeof data === "object" && "error" in data
        ? String((data as { error: unknown }).error)
        : r.statusText || `HTTP ${r.status}`
    throw new ApiError(msg, r.status, data)
  }
  return data as T
}

export function getConfig() {
  return fetchJson<AppConfig>("/config")
}

export function putConfig(cfg: AppConfig) {
  return fetchJson<AppConfig>("/config", {
    method: "PUT",
    body: JSON.stringify(cfg),
  })
}

export function getTemplates() {
  return fetchJson<TemplateMeta[]>("/templates")
}

export function getScene(id: string) {
  return fetchJson<Scene>(`/scenes/${encodeURIComponent(id)}`)
}

export function putScene(id: string, scene: Scene) {
  return fetchJson<Scene>(`/scenes/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(scene),
  })
}

export function showNow(sceneId: string) {
  return fetchJson<{ ok: boolean; wallState?: WallState }>(
    `/scenes/${encodeURIComponent(sceneId)}/show-now`,
    {
      method: "POST",
    }
  )
}

export function getWallState() {
  return fetchJson<WallState>("/wall/state")
}

export function getWallRuns() {
  return fetchJson<WallRun[]>("/wall/runs")
}
