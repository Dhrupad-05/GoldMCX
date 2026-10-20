import { apiBaseUrl } from './apiClient'
import type { Contract, ContractId } from '../types'

export interface BackendContractSpec {
  valid_from: string
  valid_to: string | null
  trading_unit_grams: number
  quote_grams: number
  purity_per_mille: number
  quote_rule: string
  verification_status: string
  source_document_id: string
  notes: string | null
}

export interface BackendContract {
  symbol: string
  display_name: string
  status: string
  specs: BackendContractSpec[]
  data_summary: {
    detail_days?: number
    first_date?: string
    last_date?: string
    value_per_lot_inr?: number
  }
  latest_quote_set?: { latest_date: string; lots: number; total_value_lakhs: number; note: string }
}

export interface ContractDetailsService {
  symbol: string
  displayName: string
  specs: BackendContractSpec[]
  status: string
  data: ContractDetailsServiceData | null
}

export interface ContractDetailsServiceData {
  detailDays: number
  firstDate: string | null
  lastDate: string | null
  valuePerLotInr: number | null
}

/** Map a backend contract payload into the existing frontend Contract shape. */
export function backendContractToFrontend(bc: BackendContract): Contract {
  const spec = bc.specs[0]
  return {
    id: bc.symbol as ContractId,
    symbol: bc.symbol as ContractId,
    displayName: bc.display_name,
    tradingUnitGrams: spec?.trading_unit_grams ?? 100,
    quoteGrams: spec?.quote_grams ?? 10,
    purity: spec?.purity_per_mille ?? 995,
    expiryLabel: '', //expiry identity is not derivable from this source corpus
    demoPrice: bc.data_summary?.value_per_lot_inr ?? 0,
    demoChangePct: 0,
    status: bc.status,
    description:
      (spec?.notes ?? '') +
      ` Source: ${spec?.source_document_id ?? 'n/a'} (${spec?.verification_status ?? 'unknown'}).`,
  }
}

export interface SeriesPoint {
  tradeDate: string
  value: number
  sourceStatus: string
}

export interface SeriesResult {
  symbol: string
  derivationMethod: string
  dataStatus: string
  points: SeriesPoint[]
}

interface RawSeriesResponse {
  symbol: string
  derivation_method: string
  data_status: string
  points: { trade_date: string; normalized_value: number; source_status: string }[]
}

export { apiBaseUrl }

// Implementation lives in dataSource.ts (mode selection); the mapper is exposed here.
export function mapSeries(res: RawSeriesResponse): SeriesResult {
  return {
    symbol: res.symbol,
    derivationMethod: res.derivation_method,
    dataStatus: res.data_status,
    points: res.points.map((p) => ({
      tradeDate: p.trade_date,
      value: p.normalized_value,
      sourceStatus: p.source_status,
    })),
  }
}
