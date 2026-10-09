import { genSeries } from '../lib/demoUtil'
import { CONTRACTS } from './contracts'
import type { ContractId } from '../types'

// Deterministic price series per contract (60 points, ~Aug–Oct 2026 window for demo)
const START = '2026-08-01'
const LENGTH = 60

export interface ContractSeries {
  id: ContractId
  points: { date: string; value: number }[]
}

export const PRICE_SERIES: Record<ContractId, { date: string; value: number }[]> =
  Object.fromEntries(
    CONTRACTS.map((c, i) => [c.id, genSeries(START, LENGTH, c.demoPrice * 0.985, c.demoChangePct * 0.12, 45 + i * 6, 1000 + i * 71)]),
  ) as Record<ContractId, { date: string; value: number }[]>

// Normalized per fine gram: price / (quoteGrams * purity/1000)
export function normalizedPrice(
  raw: number,
  quoteGrams: number,
  purity: number,
): number {
  const fineGoldGrams = quoteGrams * (purity / 1000)
  return raw / fineGoldGrams
}

// Build multi-series normalized comparison data keyed by date
export function normalizedSeriesForContracts(
  ids: ContractId[],
): { date: string; [id: string]: number | string }[] {
  const maps = ids.map((id) => {
    const c = CONTRACTS.find((x) => x.id === id)!
    return PRICE_SERIES[id].map((p) => ({
      date: p.date,
      norm: normalizedPrice(p.value, c.quoteGrams, c.purity),
    }))
  })
  // align by date (all series share dates by construction)
  return maps[0].map((_, i) => {
    const row: { date: string; [k: string]: number | string } = { date: maps[0][i].date }
    ids.forEach((id, j) => {
      row[id] = Math.round(maps[j][i].norm * 100) / 100
    })
    return row
  })
}
