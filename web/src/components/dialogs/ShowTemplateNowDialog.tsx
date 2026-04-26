import { useCallback, useEffect, useMemo, useState } from "react"

import { TemplateParamsFields } from "@/components/templates/TemplateParamsFields"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { TemplateMeta } from "@/types/api"
import { dialogShell } from "@/lib/dialog-shell"
import { initialTemplateParamForm, validateTemplateParamForm } from "@/lib/template-params-form"

export function ShowTemplateNowDialog({
  open,
  template,
  busy,
  onOpenChange,
  onSubmit,
  onNotify,
}: {
  open: boolean
  template: TemplateMeta | null
  busy: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (templateId: string, templateParams: Record<string, unknown>) => void | Promise<void>
  onNotify?: (msg: string) => void
}) {
  const schema = template?.paramSchema ?? []
  const [params, setParams] = useState<Record<string, unknown>>({})

  useEffect(() => {
    if (!open || !template) return
    setParams(initialTemplateParamForm(template.paramSchema, undefined))
  }, [open, template])

  const title = useMemo(() => {
    if (!template) return "立即上屏"
    return `立即上屏 — ${template.displayName || template.templateId}`
  }, [template])

  const handleSubmit = useCallback(() => {
    if (!template || busy) return
    const err = validateTemplateParamForm(template.paramSchema, params)
    if (err) {
      onNotify?.(err)
      return
    }
    const id = template.templateId
    const payload = { ...params }
    void Promise.resolve(onSubmit(id, payload)).catch(() => {
      /* errors surfaced via runShowNowTemplate / showToast */
    })
    onOpenChange(false)
  }, [template, busy, onSubmit, onOpenChange, onNotify, params])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={dialogShell("max-h-[min(88dvh,640px)] w-[calc(100vw-1.5rem)] max-w-lg sm:max-w-lg")}
      >
        <DialogHeader className="border-b border-slate-200/45 px-6 pb-3 pt-4 pr-14 text-left">
          <DialogTitle className="text-left text-[17px] font-semibold tracking-tight text-slate-900">
            {title}
          </DialogTitle>
        </DialogHeader>

        <div className="max-h-[min(52dvh,480px)] overflow-y-auto px-6 py-3">
          {template && schema.length > 0 ? (
            <TemplateParamsFields
              fields={schema}
              value={params}
              onChange={setParams}
              idsPrefix="show-now"
            />
          ) : (
            <p className="text-[14px] text-slate-600">该模板无可调参数。</p>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200/50 bg-slate-50/95 px-6 py-2.5">
          <Button
            type="button"
            variant="ghost"
            className="h-8 min-h-8 rounded-md px-3 text-[13px] font-medium text-slate-600 hover:bg-slate-200/45 hover:text-slate-900"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            取消
          </Button>
          <Button
            type="button"
            disabled={busy || !template}
            className="h-8 min-h-8 rounded-md bg-[#0071e3] px-4 text-[13px] font-medium text-white shadow-sm hover:bg-[#0068cf] focus-visible:ring-2 focus-visible:ring-[#0071e3]/30 disabled:opacity-60"
            onClick={handleSubmit}
          >
            {busy ? "上屏中…" : "上屏"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
