import { useCallback, useRef, useState } from "react"

export function useRowCooldown(cooldownMs: number) {
  const busyRef = useRef<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const withCooldown = useCallback(
    (id: string, action: () => void) => {
      if (busyRef.current === id) return
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

  return { busyId, withCooldown }
}
