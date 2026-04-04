/** 演示：写入「立即渲染」产生的运行记录时间戳 */
export function formatInstant(d: Date): string {
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, "0")
  const dy = String(d.getDate()).padStart(2, "0")
  const h = String(d.getHours()).padStart(2, "0")
  const mi = String(d.getMinutes()).padStart(2, "0")
  const s = String(d.getSeconds()).padStart(2, "0")
  return `${y}-${mo}-${dy} ${h}:${mi}:${s}`
}

/** 统一为 YYYY-MM-DD HH:mm:ss */
export function computeNextRefreshFromInterval(seconds: number): string {
  const sec = Math.max(30, Math.floor(Number(seconds)) || 300)
  const d = new Date()
  d.setSeconds(d.getSeconds() + sec)
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, "0")
  const dy = String(d.getDate()).padStart(2, "0")
  const h = String(d.getHours()).padStart(2, "0")
  const mi = String(d.getMinutes()).padStart(2, "0")
  const s = String(d.getSeconds()).padStart(2, "0")
  return `${y}-${mo}-${dy} ${h}:${mi}:${s}`
}
