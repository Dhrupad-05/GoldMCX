// Static-content helpers only: time-range slicing, educational index lookups and
// insight/event registry access. Operational data never comes from here — pages
// load it from the FastAPI backend through src/lib/api.ts.
import type { ResearchCard, HistoricalEvent } from '../types'
import type { SearchItem } from '../data/misc'
import { RESEARCH_CARDS } from '../data/researchCards'
import { HISTORICAL_EVENTS } from '../data/historicalEvents'
import { SEARCH_INDEX } from '../data/misc'

export type TimeRange = '1M' | '3M' | '6M' | '1Y'

export function sliceForRange<T extends { date: string }>(points: T[], range: TimeRange): T[] {
  const take: Record<TimeRange, number> = { '1M': 30, '3M': 45, '6M': 60, '1Y': 90 }
  return points.slice(-take[range])
}

export function searchAll(query: string): SearchItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return SEARCH_INDEX.filter(
    (item) => item.label.toLowerCase().includes(q) || item.keywords.includes(q),
  )
}

export function insightById(id: string): ResearchCard | undefined {
  return RESEARCH_CARDS.find((c) => c.id === id)
}

export function eventById(id: string): HistoricalEvent | undefined {
  return HISTORICAL_EVENTS.find((e) => e.id === id)
}
