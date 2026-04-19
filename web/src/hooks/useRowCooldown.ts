import { useCallback, useRef, useState } from "react"

export function useRowCooldown(cooldownMs: number) {
  const busyRef = useRef<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const withCooldown = useCallback(
    (id: string, action: () => void) => {
      if (busyRef.current != null) return
      busyRef.current = id
      setBusyId(id)
      action()
      window.setTimeout(() => {
        if (busyRef.current === id) {
          busyRef.current = null
          setBusyId(null)
        }
      }, cooldownMs)
    },
    [cooldownMs]
  )

  /** 上屏等长任务：在 Promise 结束前保持 busy，避免与 withCooldown 650ms 冲突。 */
  const withBusyAsync = useCallback(async (id: string, fn: () => Promise<void>) => {
    if (busyRef.current != null) return
    busyRef.current = id
    setBusyId(id)
    try {
      await fn()
    } finally {
      if (busyRef.current === id) {
        busyRef.current = null
        setBusyId(null)
      }
    }
  }, [])

  return { busyId, withCooldown, withBusyAsync }
}
