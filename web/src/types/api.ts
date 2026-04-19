export type SceneSchedule =
  | { type: "interval"; intervalSeconds: number }
  | { type: "cron_weekly"; time: string; weekdays: number[] }

/** 自动刷新勿扰时段（设备本地时间，与 MYPI_TZ 一致）；手动「立即上屏」不受限 */
export interface QuietHours {
  enabled: boolean
  startLocal: string
  endLocal: string
}

export interface Scene {
  id: string
  name: string
  description: string
  enabled: boolean
  templateId: string
  templateParams: Record<string, unknown>
  schedule: SceneSchedule
  previewImageUrl: string | null
  tieBreakPriority: number
}

export interface AppConfig {
  scenes: Scene[]
  frameTuning: Record<string, unknown>
  deviceProfile: Record<string, unknown>
  quietHours: QuietHours
}

export interface TemplateMeta {
  templateId: string
  displayName: string
}

export interface WallRun {
  id: string
  sceneId: string
  sceneName: string
  templateId: string
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  ok: boolean
  errorMessage: string | null
  outputPath: string | null
}

export interface UpcomingItem {
  sceneId: string
  at: string
  name: string
}

export interface WallState {
  currentSceneId: string | null
  currentSceneName: string | null
  currentTemplateId: string | null
  currentPreviewUrl: string | null
  upcoming: UpcomingItem[]
  displayActiveSceneId?: string | null
  queuedDisplaySceneIds?: string[]
}

export interface SystemLog {
  timestamp: string
  level: string
  name: string
  message: string
  formatted: string
}
