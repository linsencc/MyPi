import type { TemplateParamField } from "@/types/api"

/** Keep in sync with server ``renderers.templates.ui_params._coerce_bool_value``. */
function boolFromUnknown(v: unknown, fallback: boolean): boolean {
  if (typeof v === "boolean") return v
  if (typeof v === "number" && (v === 0 || v === 1)) return Boolean(v)
  if (typeof v === "string") {
    const x = v.trim().toLowerCase()
    if (x === "true" || x === "1" || x === "yes" || x === "on") return true
    if (x === "false" || x === "0" || x === "no" || x === "off" || x === "") return false
  }
  return fallback
}

function stringDefault(f: TemplateParamField): string {
  return typeof f.default === "string" ? f.default : ""
}

function boolDefault(f: TemplateParamField): boolean {
  return typeof f.default === "boolean" ? f.default : false
}

/** Validate form state against schema; returns first error message or null. */
export function validateTemplateParamForm(
  schema: TemplateParamField[] | undefined,
  params: Record<string, unknown>
): string | null {
  for (const f of schema ?? []) {
    if (!f.required) continue
    if (f.type === "boolean") continue
    const s = typeof params[f.key] === "string" ? (params[f.key] as string).trim() : ""
    if (!s) return `请填写参数：${(f.name && f.name.trim()) || f.key}`
  }
  return null
}

/** Build POST body for template show-now (all schema keys so booleans are not dropped). */
export function showNowRequestBodyFromForm(
  schema: TemplateParamField[] | undefined,
  params: Record<string, unknown>
): { templateParams: Record<string, unknown> } | undefined {
  if (!schema?.length) return undefined
  const merged: Record<string, unknown> = {}
  for (const f of schema) {
    if (f.type === "boolean") {
      merged[f.key] = boolFromUnknown(params[f.key], boolDefault(f))
    } else {
      merged[f.key] =
        typeof params[f.key] === "string" ? params[f.key] as string : String(params[f.key] ?? "")
    }
  }
  return { templateParams: merged }
}

/** Persisted scene: overlay schema fields onto base. */
export function sceneTemplateParamsFromForm(
  schema: TemplateParamField[] | undefined,
  base: Record<string, unknown>,
  form: Record<string, unknown>
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...base }
  if (!schema?.length) return next
  for (const f of schema) {
    if (f.type === "boolean") {
      next[f.key] = boolFromUnknown(form[f.key], boolDefault(f))
      continue
    }
    const raw = form[f.key]
    const s = typeof raw === "string" ? raw.trim() : String(raw ?? "").trim()
    if (s) next[f.key] = s
    else if (f.required) next[f.key] = ""
    else delete next[f.key]
  }
  return next
}

export function initialTemplateParamForm(
  schema: TemplateParamField[] | undefined,
  base: Record<string, unknown> | undefined
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of schema ?? []) {
    const v = base?.[f.key]
    if (f.type === "boolean") {
      if (typeof v === "boolean") out[f.key] = v
      else if (v != null) out[f.key] = boolFromUnknown(v, boolDefault(f))
      else out[f.key] = boolDefault(f)
      continue
    }
    if (typeof v === "string") out[f.key] = v
    else if (v != null) out[f.key] = String(v)
    else out[f.key] = stringDefault(f)
  }
  return out
}
