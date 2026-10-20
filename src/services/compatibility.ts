// Legacy-identifier compatibility and DTO mapping.
// Backend canonical ids only ever exist in these mappers; the legacy
// `REST-GOLDPETAL` typo stays purely at the adapter boundary.

import type { SignalStatus, ValidationDisposition, DemoSignal, NoveltyObservation } from '../types'

/** Frontend legacy id -> canonical backend id. */
const LEGACY_PAIR_ALIASES: Record<string, string> = {
  'REST-GOLDPETAL': 'GOLDGUINEA-GOLDPETAL',
}

// Six canonical backend pair ids (alphabetical orientation).
export const CANONICAL_PAIR_IDS = [
  'GOLDM-GOLDTEN',
  'GOLDM-GOLDGUINEA',
  'GOLDM-GOLDPETAL',
  'GOLDTEN-GOLDGUINEA',
  'GOLDTEN-GOLDPETAL',
  'GOLDGUINEA-GOLDPETAL',
] as const

export function canonicalizePairId(id: string): string {
  if ((CANONICAL_PAIR_IDS as readonly string[]).includes(id)) return id
  if (LEGACY_PAIR_ALIASES[id]) return LEGACY_PAIR_ALIASES[id]
  // Accept reversed orientation for order-independent lookups.
  const parts = id.split('-')
  if (parts.length === 2) {
    const sorted = [...parts].sort().join('-')
    if ((CANONICAL_PAIR_IDS as readonly string[]).includes(sorted)) return sorted
  }
  // No silent fallback: the caller decides how to surface unknown ids.
  return id
}

/** Map backend validation disposition categories onto the frontend ones. */
export function mapValidationDisposition(
  disposition: string,
): ValidationDisposition {
  switch (disposition) {
    case 'ACTIONABLE':
      return 'Actionable'
    case 'WATCH':
      return 'Watch'
    default:
      return 'Ignore'
  }
}

/** Map backend severity onto the existing SignalStatus union. */
export function mapSignalSeverity(severity: string): SignalStatus {
  switch (severity) {
    case 'High':
      return 'High'
    case 'Watch':
      return 'Watch'
    default:
      return 'Normal'
  }
}

export interface BackendSignal {
  id: number
  score_id: number
  pair_id: string
  observation_date: string
  status: string
  disposition: string
  severity: string
  robust_z: number
  score: number
  liquidity_status: string
  expiry_status: string
  cost_status: string
  reason_codes: string[]
  data_status: string
}

export interface BackendScoreDetail extends BackendSignal {
  observed_value: number
  explanation: string
  warnings: string[]
  feature_values: Record<string, number | null>
  checks: { stage: string; result: string; detail: string }[]
  calibration: Record<string, unknown>
  threshold: number
  is_anomaly: boolean
}

/** Backend signal + score detail -> existing DemoSignal shape (visual parity). */
export function backendSignalToDemo(
  detail: BackendScoreDetail,
): DemoSignal & { _backend: true } {
  const canonical = canonicalizePairId(detail.pair_id)
  return {
    id: `API-${detail.id}`,
    date: detail.observation_date,
    pairId: canonical,
    title: `${canonical.replace(/-/g, ' \u2194 ')} spread screening`,
    type: 'Spread',
    status: mapSignalSeverity(detail.severity),
    robustZ: detail.robust_z,
    score: detail.score,
    daysToExpiry: 0,
    liquidity:
      detail.liquidity_status === 'OK'
        ? 'Healthy'
        : detail.liquidity_status === 'LOW'
          ? 'Low'
          : 'Adequate',
    summary: detail.explanation,
    reasons: detail.reason_codes ?? [],
    expiryNote:
      detail.expiry_status === 'UNSCORABLE'
        ? 'Expiry lifecycle unassessable: source corpus has no expiry dates.'
        : undefined,
    _backend: true,
  }
}

export interface BackendObservation {
  pair_id: string
  observation_date: string
  observed_value: number
  severity: string
  is_anomaly: boolean
}

export function backendScoreToObservation(
  detail: BackendScoreDetail,
): NoveltyObservation {
  return {
    id: `API-${detail.id}`,
    pairId: canonicalizePairId(detail.pair_id),
    scenarioLabel: `Scored ${detail.observation_date} (backend)`,
    spreadPct: detail.observed_value,
    volumeRatio: Number(detail.feature_values?.left_volume_lots ?? 0) || 1,
    openInterestRatio: 1,
    daysToExpiry: 0,
    expectedHint: detail.is_anomaly ? 'unusual' : 'normal',
    narrative: detail.explanation,
  }
}
