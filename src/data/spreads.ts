import { PRICE_SERIES, normalizedPrice } from './marketSeries'
import { CONTRACT_MAP, ALL_PAIRS } from './contracts'
import type { SpreadPoint } from '../types'

// Compute relative spread (%) between normalized per-gram prices for every pair
export const SPREAD_SERIES: Record<string, SpreadPoint[]> = Object.fromEntries(
  ALL_PAIRS.map((p) => {
    const cl = CONTRACT_MAP[p.left]
    const cr = CONTRACT_MAP[p.right]
    const a = PRICE_SERIES[p.left]
    const b = PRICE_SERIES[p.right]
    const pts: SpreadPoint[] = a.map((v, i) => {
      const na = normalizedPrice(v.value, cl.quoteGrams, cl.purity)
      const nb = normalizedPrice(b[i].value, cr.quoteGrams, cr.purity)
      return {
        date: v.date,
        spreadPct: Math.round(((na - nb) / ((na + nb) / 2)) * 10000) / 100,
      }
    })
    return [p.pairId, pts]
  }),
)
