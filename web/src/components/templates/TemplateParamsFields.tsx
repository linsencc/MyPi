import { memo } from "react"

import { editDialogLabelClass } from "@/app/edit-dialog-styles"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { TemplateParamField } from "@/types/api"
import { cn } from "@/lib/utils"

const STRING_INPUT_MAX_LEN = 2000

const fieldLabelDisplayClass =
  "text-[15px] font-normal leading-5 text-slate-600"

const labelTriggerWithTooltipClass = cn(
  "inline-block min-w-0 max-w-full cursor-default truncate border-b border-dotted border-slate-300/70 pb-px",
  fieldLabelDisplayClass
)

function fieldValueString(v: unknown): string {
  if (v == null) return ""
  if (typeof v === "string") return v
  return String(v)
}

function fieldValueBool(v: unknown, fallback: boolean): boolean {
  if (typeof v === "boolean") return v
  if (typeof v === "number" && (v === 0 || v === 1)) return Boolean(v)
  if (typeof v === "string") {
    const x = v.trim().toLowerCase()
    if (x === "true" || x === "1" || x === "yes" || x === "on") return true
    if (x === "false" || x === "0" || x === "no" || x === "off" || x === "") return false
  }
  return fallback
}

function RequiredOptionalChip({ required }: { required: boolean }) {
  if (required) {
    return (
      <span
        className="shrink-0 rounded-sm bg-amber-50/90 px-1 py-0 text-[11px] font-medium leading-5 text-amber-800 ring-1 ring-amber-200/50"
        title="必填"
      >
        必填
      </span>
    )
  }
  return (
    <span
      className="shrink-0 text-[11px] font-normal leading-5 text-slate-400"
      title="选填"
    >
      可选
    </span>
  )
}

function fieldLabelText(f: TemplateParamField): string {
  const n = f.name?.trim()
  return n || f.key
}

/** 悬停展示说明。字符串行可带「必填/可选」；布尔行不显示徽标（Switch 本就有确定状态）。 */
function ParamKeyLabel({
  display,
  description,
  showRequirementChip,
  requiredChip,
}: {
  display: string
  description: string | undefined
  showRequirementChip: boolean
  /** When ``showRequirementChip``: ``true`` → 必填, ``false`` → 选填. */
  requiredChip?: boolean
}) {
  const keyText = description ? (
    <Tooltip delayDuration={280}>
      <TooltipTrigger asChild>
        <span className={labelTriggerWithTooltipClass}>
          {display}
        </span>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        align="start"
        className="max-w-[min(20rem,calc(100vw-2rem))]"
      >
        {description}
      </TooltipContent>
    </Tooltip>
  ) : (
    <span className={cn("min-w-0 max-w-full truncate", fieldLabelDisplayClass)}>{display}</span>
  )

  return (
    <span className="inline-flex min-h-5 min-w-0 max-w-full flex-nowrap items-center gap-x-1.5">
      {keyText}
      {showRequirementChip ? <RequiredOptionalChip required={requiredChip === true} /> : null}
    </span>
  )
}

export const TemplateParamsFields = memo(function TemplateParamsFields({
  fields,
  value,
  onChange,
  idsPrefix,
}: {
  fields: TemplateParamField[]
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  idsPrefix: string
}) {
  if (!fields.length) return null

  const setKey = (key: string, raw: string | boolean) => {
    onChange({ ...value, [key]: raw })
  }

  return (
    <div>
      <p
        className={cn(
          "mb-1.5 text-[11px] font-medium uppercase tracking-wider text-slate-400",
          editDialogLabelClass
        )}
      >
        模板参数
      </p>
      <div className="space-y-3.5">
        {fields.map((f) => {
          const id = `${idsPrefix}-${f.key}`
          const strReq = f.type === "string" && f.required === true
          if (f.type === "boolean") {
            const fb = typeof f.default === "boolean" ? f.default : false
            const checked = fieldValueBool(value[f.key], fb)
            return (
              <div
                key={f.key}
                className="flex min-w-0 items-center justify-between gap-3"
              >
                <label
                  htmlFor={id}
                  className="flex min-w-0 items-center text-[15px] text-slate-600"
                >
                  <ParamKeyLabel
                    display={fieldLabelText(f)}
                    description={f.description}
                    showRequirementChip={false}
                  />
                </label>
                <Switch
                  id={id}
                  checked={checked}
                  onCheckedChange={(c) => setKey(f.key, c)}
                  className="shrink-0"
                />
              </div>
            )
          }
          const str = fieldValueString(value[f.key])
          return (
            <div
              key={f.key}
              className="flex min-w-0 items-center gap-3"
            >
              <label
                htmlFor={id}
                className="flex h-10 min-w-0 max-w-[38%] shrink-0 items-center sm:max-w-[11rem] md:max-w-[12rem]"
              >
                <ParamKeyLabel
                  display={fieldLabelText(f)}
                  description={f.description}
                  showRequirementChip
                  requiredChip={strReq}
                />
              </label>
              <div className="relative min-w-0 flex-1">
                <Input
                  id={id}
                  value={str}
                  maxLength={STRING_INPUT_MAX_LEN}
                  onChange={(e) => setKey(f.key, e.target.value)}
                  autoComplete="off"
                  className={cn(
                    "h-10 min-w-0 flex-1 border-0 border-b border-slate-200/90 bg-transparent px-0.5 pr-[4.25rem]",
                    "rounded-none text-[15px] font-normal leading-10 shadow-none",
                    "placeholder:text-slate-400/70",
                    "focus-visible:border-b-[#0071e3] focus-visible:bg-transparent",
                    "focus-visible:ring-0 focus-visible:ring-offset-0"
                  )}
                />
                <span
                  className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 select-none pl-1 text-[10px] tabular-nums text-slate-300"
                  aria-hidden
                >
                  {str.length} / {STRING_INPUT_MAX_LEN}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
})
