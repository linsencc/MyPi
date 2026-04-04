import { AnimatePresence, motion } from "motion/react"

export function AppToast({ message }: { message: string | null }) {
  return (
    <AnimatePresence mode="wait">
      {message ? (
        <motion.div
          key={message}
          role="status"
          aria-live="polite"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ type: "spring", stiffness: 520, damping: 38, mass: 0.85 }}
          className="pointer-events-none fixed inset-x-0 bottom-8 z-[100] flex justify-center px-4"
        >
          <div className="max-w-[min(22rem,calc(100vw-2rem))] rounded-[length:var(--radius-lg)] border border-white/12 bg-[#1c1c1e] px-5 py-3 text-center text-[13px] font-medium leading-snug tracking-tight text-white subpixel-antialiased shadow-[0_12px_48px_rgb(0_0_0/0.28),0_0_0_1px_rgb(255_255_255/0.06)_inset]">
            {message}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
