import type { NoveltyObservation } from '../types'

export const THRESHOLD = 3.5

export interface TrainingStats {
  n: number
  median: number
  mad: number
  scaleUsed: 'mad' | 'iqr' | 'floor'
  fallNote: string
}

export interface ScoreResult {
  observation: NoveltyObservation
  stats: TrainingStats
  robustZ: number
  score: number // min(|z|/6, 1)
  isAnomaly: boolean
  severity: 'Normal' | 'Watch' | 'High'
  explanation: string
}

export function median(xs: number[]): number {
  if (xs.length === 0) return 0
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 === 1 ? s[m] : (s[m - 1] + s[m]) / 2
}

/** Estimate the training distribution of the spread feature robustly. */
export function computeTrainingStats(trainingSpreads: number[]): TrainingStats {
  const n = trainingSpreads.length
  const med = median(trainingSpreads)
  const absDeviations = trainingSpreads.map((x) => Math.abs(x - med))
  const mad = median(absDeviations)

  // MAD≈0 fallback: IQR/1.349, then a small documented floor
  if (mad > 1e-9) {
    return { n, median: med, mad, scaleUsed: 'mad', fallNote: 'Scale from MAD (robust).' }
  }
  const sorted = [...trainingSpreads].sort((a, b) => a - b)
  const q1 = median(sorted.slice(0, Math.floor(n / 2)))
  const q3 = median(sorted.slice(Math.ceil(n / 2)))
  const iqrScale = (q3 - q1) / 1.349
  if (iqrScale > 1e-9) {
    return { n, median: med, mad: iqrScale, scaleUsed: 'iqr', fallNote: 'MAD was 0 — IQR/1.349 fallback scale used.' }
  }
  const floor = Math.max(med * 0.01, 1e-4)
  return { n, median: med, mad: floor, scaleUsed: 'floor', fallNote: 'MAD and IQR both 0 — minimum scale floor applied.' }
}

export function robustZ(x: number, stats: TrainingStats): number {
  return (0.6745 * (x - stats.median)) / stats.mad
}

export function scoreObservation(
  obs: NoveltyObservation,
  trainingSpreads: number[],
): ScoreResult {
  const stats = computeTrainingStats(trainingSpreads)
  const z = robustZ(obs.spreadPct, stats)
  const az = Math.abs(z)
  const score = Math.min(az / 6, 1)
  const isAnomaly = az >= THRESHOLD
  const severity: ScoreResult['severity'] = az >= THRESHOLD ? (az >= 4.5 ? 'High' : 'Watch') : 'Normal'
  const features = describeFeatures(obs, stats, az)
  const explanation = isAnomaly
    ? `Unusual relative spread: the observation lies ${az.toFixed(1)} robust sigma outside the normal spread range learned from ${stats.n} mostly-normal training observations. ${features}`
    : `Within the normal region: the observation sits ${az.toFixed(1)} robust sigma from the training centre, inside the learned normal spread range (${stats.n} training observations). ${features}`
  return { observation: obs, stats, robustZ: z, score, isAnomaly, severity, explanation }
}

function describeFeatures(obs: NoveltyObservation, stats: TrainingStats, az: number): string {
  const parts: string[] = []
  if (az >= THRESHOLD) parts.push(`Triggered feature: relative spread at ${obs.spreadPct.toFixed(2)}% vs training median ${stats.median.toFixed(2)}%`)
  if (obs.volumeRatio > 1.5 || obs.volumeRatio < 0.6) parts.push(`volume ratio ${obs.volumeRatio.toFixed(2)} is unusual`)
  if (obs.daysToExpiry <= 10) parts.push(`expiry window context: ${obs.daysToExpiry} days to expiry`)
  return parts.join('; ')
}

export function classifyDisposition(
  isAnomaly: boolean,
  liquidityOk: boolean,
  expiryOk: boolean,
  costOk: boolean,
  convergenceOk: boolean,
): 'Actionable' | 'Watch' | 'Ignore' {
  if (!isAnomaly) return 'Ignore'
  if (!liquidityOk || !expiryOk) return 'Watch'
  if (costOk && convergenceOk) return 'Actionable'
  return 'Watch'
}
