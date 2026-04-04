/** 使用纯 CSS 入场动画，避免 Motion 在 main thread 上与列表更新抢时间片 */
export function AppToast({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-8 z-[100] flex justify-center px-4">
      <div
        key={message}
        role="status"
        aria-live="polite"
        className="app-toast-enter max-w-[min(22rem,calc(100vw-2rem))] rounded-[length:var(--radius-lg)] border border-white/12 bg-[#1c1c1e] px-5 py-3 text-center text-[13px] font-medium leading-snug tracking-tight text-white subpixel-antialiased shadow-[0_12px_48px_rgb(0_0_0/0.28),0_0_0_1px_rgb(255_255_255/0.06)_inset]"
      >
        {message}
      </div>
    </div>
  )
}
