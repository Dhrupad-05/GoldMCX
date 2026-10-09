import { seededRandom } from '../lib/demoUtil'
import { ALL_PAIRS } from './contracts'
import type { NoveltyObservation } from '../types'

// Curated, mostly-normal training observations per pair.
// Deterministic: generated once from a fixed seed, committed behaviour each load.
// Small structural differences per pair (small-lot pairs trade wider).
const PAIR_CENTER: Record<string, number> = {
  'GOLDM-GOLDTEN': 0.45,
  'GOLDM-GOLDGUINEA': 0.30,
  'GOLDM-GOLDPETAL': 1.05,
  'GOLDTEN-GOLDGUINEA': 0.40,
  'GOLDTEN-GOLDPETAL': 1.90,
  'GOLDGUINEA-GOLDPETAL': 1.75,
}

function buildPair(poolId: string, pairId: string, obsSeed: number): NoveltyObservation[] {
  const center = PAIR_CENTER[pairId] ?? 0.6
  const scale = center * 0.22
  const rand = seededRandom(obsSeed)
  const out: NoveltyObservation[] = []
  for (let i = 0; i < 34; i++) {
    // Mostly-normal: small band around center; a couple of mild points beyond it
    const shape = i % 17 === 16 ? 2.2 : i % 11 === 10 ? 1.6 : 1.0
    const spreadPct = Math.round((center + shape * scale * (rand() * 2 - 1)) * 100) / 100
    out.push({
      id: `${poolId}-${String(i + 1).padStart(2, '0')}`,
      pairId,
      scenarioLabel: `Training obs ${i + 1}`,
      spreadPct,
      volumeRatio: Math.round((1 + shape * 0.12 * (rand() * 2 - 1)) * 100) / 100,
      openInterestRatio: Math.round((1 + shape * 0.1 * (rand() * 2 - 1)) * 100) / 100,
      daysToExpiry: 15 + Math.round(rand() * 100),
      expectedHint: 'normal',
      narrative:
        shape > 1
          ? 'Mildly elevated but retained in the mostly-normal training sample (illustrative).'
          : 'Normal cross-contract behaviour retained in the training sample (illustrative).',
    })
  }
  return out
}

export const TRAINING_POOL: Record<string, NoveltyObservation[]> = Object.fromEntries(
  ALL_PAIRS.map((p, i) => [p.pairId, buildPair(p.pairId, p.pairId, 4200 + i * 137)]),
)

export function trainingForPair(pairId: string): NoveltyObservation[] {
  return TRAINING_POOL[pairId] ?? TRAINING_POOL['GOLDM-GOLDTEN']
}
