// Typed API client for the FastAPI backend. The browser talks to FastAPI only —
// never to Supabase/vendor APIs — and no secret env vars are permitted in Vite
// (only the public VITE_API_BASE_URL base).

export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) || ''

function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, '')}${path}`
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init || {}
  const res = await fetch(joinUrl(API_BASE, path), {
    ...rest,
    headers: {
      ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(rest.headers || {}),
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  if (!res.ok) {
    let detail: unknown
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      detail = body
      const d = (body as { detail?: unknown }).detail
      if (typeof d === 'string') message = d
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ---------------------------------------------------------------------------
// Shared shapes (mirror backend /schemas/api.py and route returns)
// ---------------------------------------------------------------------------

export type ViewId =
  | 'dashboard'
  | 'signals'
  | 'contracts'
  | 'comparison'
  | 'model'
  | 'insights'
  | 'learn'
  | 'backtest'
  | 'events'

export type ContractSymbol = 'GOLDM' | 'GOLDTEN' | 'GOLDGUINEA' | 'GOLDPETAL'

export interface ApiSpec {
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

export interface ContractInventoryItem {
  symbol: string
  display_name: string
  status: string // NO_DATA | PROVISIONAL | ...
  specs: ApiSpec[]
  data_summary: {
    detail_days: number
    first_date?: string
    last_date?: string
    value_per_lot_inr?: number | null
  }
  latest_quote_set?: {
    latest_date: string
    lots: number | null
    total_value_lakhs: number
    note: string
  }
  coverage_note?: string
  expiry_label?: string | null
}

export interface DashboardDataFreshness {
  latest_activity_trade_date: string | null
  latest_options_trade_date: string | null
  latest_gold_context_trade_date: string | null
  last_source_seen: string | null
  note: string
}

export interface ApiSignal {
  id: number
  score_id: number
  pair_id: string
  observation_date: string
  status: string // ANOMALOUS | NORMAL | UNSCORABLE
  disposition: string // ACTIONABLE | WATCH | IGNORE | UNSCORABLE
  severity: string // Normal | Watch | High
  robust_z: number
  score: number
  liquidity_status: string
  expiry_status: string
  cost_status: string
  reason_codes: string[]
  data_status: string
}

export interface DashboardSummary {
  contracts: ContractInventoryItem[]
  data_status: string
  data_freshness: DashboardDataFreshness
  source_quality: Record<string, unknown> & { nivel?: string; note?: string }
  top_signals: ApiSignal[]
}

export interface NormalizedPoint {
  trade_date: string
  normalized_value: number
  source_status: string
  derivation_method: string
}

export interface SeriesResponse {
  symbol: string
  derivation_method: string
  data_status: string
  points: NormalizedPoint[]
  spec_versions_applied: string[]
}

export interface PairPoint {
  trade_date: string
  spread_pct: number
  spread_change_pct: number | null
  price_ratio: number | null
  left_value_lakhs: number | null
  right_value_lakhs: number | null
  source_status: string
}

export interface ComparisonResponse {
  pair_id: string
  left: string
  right: string
  range_start: string
  range_end: string
  derivation_method: string
  data_status: string
  point_count: number
  points: PairPoint[]
}

export interface SignalDetail extends ApiSignal {
  observed_value: number
  explanation: string
  warnings: string[]
  feature_values: Record<string, unknown>
  checks: Array<{ name: string; status: string; detail: unknown }>
  calibration: Record<string, unknown> | null
}

export interface ApiEvent {
  id: string
  date: string
  pair_id: string | null
  category: string
  severity: string
  title: string
  description: string
  source_document: string
  data_status: string
}

export interface BacktestRunOut {
  id: string
  pair_id: string
  strategy_version: string
  code_version: string
  data_status: string
  start_date?: string
  end_date?: string
  costs?: Record<string, unknown> | null
  config?: Record<string, unknown> | null
  status: string
  started_at?: string
  data_snapshot?: string | null
}

export interface BacktestRunResponse {
  run: BacktestRunOut
  metrics: Array<{ metric_name: string; metric_value: number; units: string; details: unknown }>
  trades: unknown[]
  disclaimer: string
}

export interface ModelStatusResponse {
  mode: string
  status: 'READY' | 'NOT_READY' | 'UNAVAILABLE'
  model_version: string | null
  algorithm: string | null
  feature_names: string[] | null
  artifact_path: string | null
  artifact_sha256: string | null
  evaluation: Record<string, unknown> | null
  notes: string | null
  registry: Array<{
    model_version: string
    status: string
    algorithm: string
    created_at: string | null
    activated_at: string | null
  }>
}

export interface MlAnomaly {
  score_id: number
  pair_id: string
  observation_date: string
  feature: string
  observed_value: number
  robust_z: number
  score: number
  is_anomaly: boolean
  severity: string
  explanation: string
  warnings: string[]
  feature_values: Record<string, unknown>
  data_status: string
  model_version: string | null
  disposition: {
    status: string
    disposition: string
    liquidity_status: string
    expiry_status: string
    cost_status: string
    reason_codes: string[]
    checks: Array<{ name: string; status: string; detail: unknown }>
  } | null
}

export interface MlAnomalyList {
  count: number
  status: string
  anomalies: MlAnomaly[]
}

export interface LiveQuote {
  id?: number
  provider: string
  canonical_symbol: string
  provider_symbol: string
  expiry_date: string | null
  event_time: string
  receive_time: string
  last_price: number | null
  bid: number | null
  ask: number | null
  volume: number | null
  open_interest: number | null
  data_status: string
  age_seconds?: number
}

export interface LiveStatus {
  provider: string | null
  state: string // NOT_CONFIGURED | ENTITLEMENT_REQUIRED | CONNECTING | CONNECTED_WITH_FRESH_DATA | STALE | RECONNECTING | DEGRADED | ERROR
  detail?: string
  worker_state?: string
  latest_event_at?: string | null
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  dashboardSummary: (limit = 8) =>
    request<DashboardSummary>(`/api/v1/dashboard/summary?limit=${limit}`),

  contracts: () => request<{ contracts: ContractInventoryItem[] }>('/api/v1/contracts'),

  contractSeries: async (symbol: string): Promise<SeriesResponse> => {
    try {
      return await request<SeriesResponse>(
        `/api/v1/contracts/${encodeURIComponent(symbol)}/series`,
      )
    } catch (e) {
      // A 404 "No derived price series" is an explicit EMPTY dataset, not a
      // backend failure: surface it as data_status NO_DATA so pages render the
      // honest no-data state instead of "backend unavailable".
      if (e instanceof ApiError && /No derived price series/i.test(e.message)) {
        return {
          symbol,
          derivation_method: 'none',
          data_status: 'NO_DATA',
          points: [],
          spec_versions_applied: [],
        }
      }
      throw e
    }
  },

  comparison: (pair: string, rangeDays?: number) => {
    const q = new URLSearchParams({ pair })
    if (rangeDays) q.set('range_days', String(rangeDays))
    return request<ComparisonResponse>(`/api/v1/comparisons?${q.toString()}`)
  },

  signals: (filters: {
    pair?: string
    status?: string
    disposition?: string
    date_from?: string
    date_to?: string
    limit?: number
    offset?: number
  } = {}) => {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) if (v != null && v !== '') q.set(k, String(v))
    return request<ApiSignal[]>(`/api/v1/signals?${q.toString()}`)
  },

  signalDetail: (signalId: number) =>
    request<SignalDetail>(`/api/v1/signals/${signalId}`),

  events: (filters: { category?: string; date_from?: string; date_to?: string } = {}) => {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) if (v) q.set(k, v)
    return request<{ events: ApiEvent[]; count: number }>(`/api/v1/events?${q.toString()}`)
  },

  backtestRuns: () => request<BacktestRunOut[]>('/api/v1/backtests'),

  runBacktest: (body: {
    pair_id: string
    start: string
    end: string
    threshold?: number
    cost_bps_per_leg?: number
    slippage_bps_per_leg?: number
    idempotency_key?: string
  }, idempotencyKey?: string) =>
    request<BacktestRunResponse>('/api/v1/backtests/run', {
      method: 'POST',
      json: { ...body, idempotency_key: undefined },
      headers: idempotencyKey || body.idempotency_key
        ? { 'Idempotency-Key': (idempotencyKey || body.idempotency_key)! }
        : undefined,
    }),

  mlStatus: (mode: 'daily' | 'intraday' = 'daily') =>
    request<ModelStatusResponse>(`/api/v1/ml/status?mode=${mode}`),

  latestAnomalies: (pairId?: string, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (pairId) q.set('pair_id', pairId)
    return request<MlAnomalyList>(`/api/v1/ml/latest-anomalies?${q.toString()}`)
  },

  mlJobRuns: () =>
    request<{ count: number; runs: Array<{ run_id: string; status: string; started_at: string; completed_at: string | null; summary: Record<string, unknown>; errors: string[] }> }>(`/api/v1/ml/jobs`),

  triggerDailyJob: (adminToken?: string) =>
    request<Record<string, unknown>>('/api/v1/ml/jobs/daily-run', {
      method: 'POST',
      headers: adminToken ? { 'x-admin-token': adminToken } : undefined,
    }),

  liveStatus: () => request<LiveStatus>('/api/v1/market/live/status'),

  liveQuotes: async (symbol?: string) => {
    type QuotesPayload = LiveQuote[] | { quotes: LiveQuote[] }
    const r = await request<QuotesPayload>(
      `/api/v1/market/live/quotes${symbol ? `?symbol=${symbol}` : ''}`,
    )
    return Array.isArray(r) ? r : (r?.quotes ?? [])
  },
}

export const SSE_PATH = '/api/v1/market/live/stream'

// Canonical pair id from two symbols (backend canonical orientation is authoritative).
export function pairIdOf(a: string, b: string): string {
  const order: ContractSymbol[] = ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']
  const ia = order.indexOf(a as ContractSymbol)
  const ib = order.indexOf(b as ContractSymbol)
  const [l, r] = ia <= ib ? [a, b] : [b, a]
  return `${l}-${r}`
}

export function pairLabel(pairId: string): string {
  return pairId.replace(/^(.+)-(.+)$/, '$1 ↔ $2')
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}
