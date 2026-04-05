import { useCallback, useRef, useState } from "react"

/** 防止同一节点在短时间内重复触发「立即渲染」等操作；其他节点仍可操作。 */
export function useRowCooldown(cooldownMs: number) {
  const busyRef = useRef<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const withCooldown = useCallback(
    (sceneId: string, action: () => void) => {
      if (busyRef.current === sceneId) return
      busyRef.current = sceneId
      setBusyId(sceneId)
      action()
      window.setTimeout(() => {
        if (busyRef.current === sceneId) {
          busyRef.current = null
          setBusyId(null)
        }
      }, cooldownMs)
    },
    [cooldownMs]
  )

  return { busyId, withCooldown }
}
