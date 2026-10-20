import { get, post } from './apiClient'
import { canonicalizePairId } from './compatibility'
import type { BacktestScenario } from '../types'

export interface BackendBacktestMetric {
  metric_name: string
  metric_value: number
  units: string
  details: Record<string, string> | null
}

export interface BackendBacktestRun {
  run: {
    id: string
    pair_id: string
    strategy_version: string
    code_version: string
    data_status: string
    data_snapshot: string | null
    start_date: string
    end_date: string
    costs: Record<string, number | string> | null
    config: Record<string, unknown> | null
    status: string
  }
  metrics: BackendBacktestMetric[]
  trades: Record<string, number | string>[]
  disclaimer: string
}

export async function fetchBacktests(limit = 50): Promise<BackendBacktestRun[]> {
  return get(`/api/v1/backtests?limit=${limit}`)
}

export async function runBacktest(req: {
  pair_id: string
  start: string
  end: string
  threshold?: number
  cost_bps_per_leg?: number
  slippage_bps_per_leg?: number
}): Promise<BackendBacktestRun> {
  return post('/api/v1/backtests/run', {
    ...req,
    pair_id: canonicalizePairId(req.pair_id),
  })
}

/** Map a stored run + metrics into the existing BacktestScenario card shape. */
export function metricsToScenario(run: BackendBacktestRun, name?: string): BacktestScenario {
  const m = (k: string): number =>
    run.metrics.find((x) => x.metric_name === k)?.metric_value ?? 0
  return {
    id: run.run.id,
    name: name ?? `${run.run.pair_id} ${run.run.start_date}→${run.run.end_date}`,
    pairId: canonicalizePairId(run.run.pair_id),
    period: `${run.run.start_date} – ${run.run.end_date} (provisional)`,
    grossPct: m('gross_return_pct'),
    txnCostPct: m('cost_drag_pct'),
    netPct: m('net_return_pct'),
    trades: Math.round(m('trades')),
    winRatePct: m('hit_rate') * 100,
    maxDrawdownPct: 0, // drawdown requires per-trade equity, reported in run detail
    avgConvergenceDays: 0,
    baselinePct: m('benchmark_move_pct'),
  }
}
