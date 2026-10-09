import type { DemoSignal, ResearchCard, HistoricalEvent, ContractId } from '../types'
import type { SearchItem } from '../data/misc'
import { SIGNALS } from '../data/signals'
import { RESEARCH_CARDS } from '../data/researchCards'
import { HISTORICAL_EVENTS } from '../data/historicalEvents'
import { SEARCH_INDEX } from '../data/misc'
import { ALL_PAIRS, CONTRACT_MAP } from '../data/contracts'

export type TimeRange = '1M' | '3M' | '6M' | '1Y'

export function sliceForRange<T extends { date: string }>(points: T[], range: TimeRange): T[] {
  const take: Record<TimeRange, number> = { '1M': 30, '3M': 45, '6M': 60, '1Y': 60 }
  return points.slice(-take[range])
}

export interface SignalFilters {
  status: 'All' | DemoSignal['status']
  type: 'All' | string
  period: '7d' | '30d' | 'all'
  query: string
}

export function filterSignals(signals: DemoSignal[], f: SignalFilters): DemoSignal[] {
  return signals.filter((s) => {
    if (f.status !== 'All' && s.status !== f.status) return false
    if (f.type !== 'All' && s.type !== f.type) return false
    if (f.period === '7d' && !withinDays(s.date, 7)) return false
    if (f.period === '30d' && !withinDays(s.date, 30)) return false
    if (f.query && !(`${s.title} ${s.type} ${s.pairId}`.toLowerCase().includes(f.query.toLowerCase()))) return false
    return true
  })
}

export function withinDays(date: string, days: number): boolean {
  const cutoff = new Date('2026-10-09')
  cutoff.setDate(cutoff.getDate() - days)
  return new Date(date) >= cutoff
}

export function pairLabel(pairId: string): string {
  const p = ALL_PAIRS.find((x) => x.pairId === pairId)
  return p ? `${CONTRACT_MAP[p.left].symbol} ↔ ${CONTRACT_MAP[p.right].symbol}` : pairId
}

export function searchAll(query: string): SearchItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return SEARCH_INDEX.filter(
    (item) => item.label.toLowerCase().includes(q) || item.keywords.includes(q),
  )
}

export const SIGNAL_TYPES = ['All', 'Spread', 'Volume', 'Open Interest', 'Term Structure', 'Expiry', 'Liquidity']

export function insightById(id: string): ResearchCard | undefined {
  return RESEARCH_CARDS.find((c) => c.id === id)
}

export function eventById(id: string): HistoricalEvent | undefined {
  return HISTORICAL_EVENTS.find((e) => e.id === id)
}
