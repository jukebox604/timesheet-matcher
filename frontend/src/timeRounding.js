/**
 * Round a positive duration to the nearest 15 minutes.
 * Exact halfway values round up; invalid, non-positive, and over-24-hour
 * values become zero.
 *
 * @param {number | string | null | undefined} minutes
 * @returns {number}
 */
export function roundToQuarterHour(minutes) {
  const duration = Number(minutes || 0)
  if (!Number.isFinite(duration) || duration <= 0 || duration > 24 * 60) return 0
  return Math.max(15, Math.floor((duration + 7.5) / 15) * 15)
}
