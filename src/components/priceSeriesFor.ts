import { PRICE_SERIES } from '../data/marketSeries'
import type { ContractId } from '../types'

export function priceSeriesFor(id: ContractId) {
  return PRICE_SERIES[id]
}
