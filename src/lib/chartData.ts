// Chart data adapters: turn typed API responses into the flat rows the existing
// Recharts components expect, anchored on actual trade dates. No fabricated
// points: if a date has no observation for a leg, that leg simply has no value
// on that row (Recharts naturally gaps it).
import type { ComparisonResponse, SeriesResponse } from './api'
import type { TimeRange } from './filters'

export function seriesToChartRows(
  resps: SeriesResponse[],
): { date: string; [symbol: string]: number | string }[] {
  const byDate = new Map<string, { date: string; [symbol: string]: number | string }>()
  for (const r of resps) {
    for (const p of r.points) {
      let row = byDate.get(p.trade_date)
      if (!row) {
        row = { date: p.trade_date }
        byDate.set(p.trade_date, row)
      }
      row[r.symbol] = round2(p.normalized_value)
    }
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1))
}

export function sliceSeries<T extends { date: string }>(
  rows: T[],
  range: TimeRange,
): T[] {
  const take: Record<TimeRange, number> = { '1M': 30, '3M': 45, '6M': 60, '1Y': 90 }
  return rows.slice(-take[range])
}

export function comparisonToChartRows(res: ComparisonResponse): { date: string; spreadPct: number }[] {
  return res.points
    .filter((p) => p.spread_pct != null && Number.isFinite(p.spread_pct))
    .map((p) => ({ date: p.trade_date, spreadPct: round2(p.spread_pct) }))
}

function round2(v: number): number {
  return Math.round(v * 100) / 100
}
