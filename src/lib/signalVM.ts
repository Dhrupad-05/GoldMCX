import type { ApiSignal, ApiEvent, MlAnomaly, SignalDetail } from './api'
import { pairLabel } from './api'

export interface SignalVM {
  kind: 'anomaly'
  scoreId: number
  isAnomaly: boolean
  pairId: string
  date: string
  status: string
  disposition: string
  severity: string
  robustZ: number
  score: number
  observedValue: number
  explanation: string
  reasonCodes: string[]
  featureValues: Record<string, unknown>
  checks: Array<{ name: string; status: string; detail: unknown }>
  dataStatus: string
  modelVersion: string | null
  warnings: string[]
}

export function vmFromApiSignal(s: ApiSignal): SignalVM {
  return {
    kind: 'anomaly',
    scoreId: s.score_id,
    isAnomaly: s.status !== 'NORMAL',
    pairId: s.pair_id,
    date: s.observation_date,
    status: s.status,
    disposition: s.disposition,
    severity: s.severity,
    robustZ: s.robust_z,
    score: s.score,
    observedValue: 0, // detail endpoint fills this
    explanation: '',
    reasonCodes: s.reason_codes,
    featureValues: {},
    checks: [],
    dataStatus: s.data_status,
    modelVersion: null,
    warnings: [],
  }
}

export function vmFromAnomaly(a: MlAnomaly): SignalVM {
  return {
    kind: 'anomaly',
    scoreId: a.score_id,
    isAnomaly: a.is_anomaly,
    pairId: a.pair_id,
    date: a.observation_date,
    status: a.is_anomaly ? a.severity : 'Normal',
    disposition: a.disposition?.disposition ?? 'UNSCORABLE',
    severity: a.severity,
    robustZ: a.robust_z,
    score: a.score,
    observedValue: a.observed_value,
    explanation: a.explanation,
    reasonCodes: a.disposition?.reason_codes ?? [],
    featureValues: a.feature_values,
    checks: a.disposition?.checks ?? [],
    dataStatus: a.data_status,
    modelVersion: a.model_version,
    warnings: a.warnings,
  }
}

export function vmFromEventDetail(e: ApiEvent): SignalVM {
  return {
    kind: 'anomaly',
    scoreId: -1,
    isAnomaly: e.severity !== 'Normal',
    pairId: e.pair_id ?? '—',
    date: e.date,
    status: e.severity,
    disposition: e.category,
    severity: e.severity,
    robustZ: 0,
    score: 0,
    observedValue: 0,
    explanation: e.description,
    reasonCodes: [],
    featureValues: {},
    checks: [],
    dataStatus: e.data_status,
    modelVersion: null,
    warnings: [],
  }
}

export function vmTitle(vm: SignalVM): string {
  return `${pairLabel(vm.pairId)} · ${vm.date}`
}
