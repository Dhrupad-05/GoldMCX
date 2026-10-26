// Demo date anchor (consistent across the app)
export const DEMO_DATE = '2026-10-09'
export const DEMO_DATE_LABEL = '9 Oct 2026, 09:45 IST'

// Deterministic pseudo-random generator (mulberry32)
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0
  return function () {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Zig-zag with occasional reversal; smooth-ish deterministic series
export function genSeries(
  startDate: string,
  length: number,
  startValue: number,
  drift: number,
  vol: number,
  seed: number,
): { date: string; value: number }[] {
  const rand = seededRandom(seed)
  const out: { date: string; value: number }[] = []
  const d = new Date(startDate + 'T00:00:00Z')
  let v = startValue
  for (let i = 0; i < length; i++) {
    out.push({ date: d.toISOString().slice(0, 10), value: Math.round(v * 10) / 10 })
    const zig = rand() < 0.5 ? -1 : 1
    const jump = (rand() - 0.5) * 2 * vol
    v = v + drift + zig * Math.abs(jump)
    // occasional pull back toward start for stationarity
    if (i % 12 === 11) v = v - (v - startValue) * 0.25
    d.setUTCDate(d.getUTCDate() + 1)
  }
  return out
}

export const fmtINR = (v: number) => '₹' + v.toLocaleString('en-IN', { maximumFractionDigits: 0 })
export const fmtPct = (v: number, digits = 1) => `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`
export const fmtZ = (v: number) => (Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2))
export const fmtDateTime = (iso: string | null | undefined): string => {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}
