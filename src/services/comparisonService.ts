import { get } from './apiClient'
import { canonicalizePairId } from './compatibility'

export interface BackendComparisonPoint {
  trade_date: string
  spread_pct: number
  spread_change_pct: number | null
  price_ratio: number | null
  left_value_lakhs: number | null
  right_value_lakhs: number | null
  source_status: string
}

export interface BackendComparison {
  pair_id: string
  left: string
  right: string
  range_start: string
  range_end: string
  derivation_method: string
  data_status: string
  point_count: number
  points: BackendComparisonPoint[]
}

export function fetchComparison(left: string, right: string): Promise<BackendComparison> {
  return get(`/api/v1/comparisons?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`)
}

export function fetchComparisonByPair(pairId: string): Promise<BackendComparison> {
  const canonical = canonicalizePairId(pairId)
  return get(`/api/v1/comparisons?pair=${encodeURIComponent(canonical)}`)
}
