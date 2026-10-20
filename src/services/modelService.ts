import { get, post } from './apiClient'
import { canonicalizePairId } from './compatibility'

export interface BackendCalibration {
  id: number
  pair_id: string
  algorithm_version: string
  feature_version: string
  train_start: string
  train_end: string
  cutoff_ts: string
  n: number
  median: number
  scale: number
  scale_method: 'mad' | 'iqr' | 'floor'
  threshold: number
  data_status_note: string | null
}

export interface BackendScoreDetail {
  pair_id: string
  observation_date: string
  data_status: string
  algorithm: string
  algorithm_version: string
  feature: string
  calibration: {
    id: number
    train_start: string
    train_end: string
    n: number
    median: number
    scale: number
    scale_method: string
    threshold: number
  }
  observed_value: number
  training_median: number | null
  scale_value: number | null
  scale_method: string | null
  robust_z: number
  anomaly_score: number
  is_anomaly: boolean
  severity: 'Normal' | 'Watch' | 'High'
  explanation: string
  warnings: string[]
  feature_values: Record<string, number | null>
  threshold: number
}

export async function fetchTrainingSummary(pairId: string): Promise<BackendCalibration> {
  return get(`/api/v1/model/pairs/${encodeURIComponent(canonicalizePairId(pairId))}/training-summary`)
}

export async function calibratePair(
  pairId: string,
  options?: { train_start?: string; train_end?: string; threshold?: number },
): Promise<BackendCalibration> {
  return post(
    `/api/v1/model/pairs/${encodeURIComponent(canonicalizePairId(pairId))}/calibrate`,
    options ?? {},
  )
}

export async function scoreObservation(
  pairId: string,
  observationDate: string,
  value?: number,
): Promise<BackendScoreDetail> {
  return post(
    `/api/v1/model/pairs/${encodeURIComponent(canonicalizePairId(pairId))}/score`,
    { observation_date: observationDate, ...(value !== undefined ? { value } : {}) },
  )
}
