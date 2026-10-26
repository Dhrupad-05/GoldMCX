import { useMemo, useState } from 'react'
import { Panel } from '../components/Panel'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { SpreadChart } from '../components/SpreadChart'
import { RangeTabs } from '../components/RangeTabs'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { api, pairIdOf, pairLabel } from '../lib/api'
import type { ContractSymbol } from '../lib/api'
import { useApi } from '../lib/useApi'
import { seriesToChartRows, sliceSeries } from '../lib/chartData'
import type { TimeRange } from '../lib/filters'
import { fmtPct, fmtZ } from '../lib/demoUtil'

const TABS = ['Price Comparison', 'Spreads', 'Relative Value', 'Historical Correlation'] as const

const SYMBOLS: ContractSymbol[] = ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']

export function ComparisonPage({
  left,
  right,
  setLeft,
  setRight,
  onOpenSignal,
}: {
  left: string
  right: string
  setLeft: (c: string) => void
  setRight: (c: string) => void
  onOpenSignal: (pairId: string) => void
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Price Comparison')
  const [range, setRange] = useState<TimeRange>('3M')
  const pairId = pairIdOf(left, right)
  const rangeDays: Record<TimeRange, number> = { '1M': 30, '3M': 90, '6M': 182, '1Y': 365 }

  const comparison = useApi(() => api.comparison(pairId, rangeDays[range]), [pairId, range])
  const anomaly = useApi(() => api.latestAnomalies(pairId, 1), [pairId])
  const seriesPair = useApi(
    () => Promise.all([api.contractSeries(left), api.contractSeries(right)]),
    [left, right],
  )

  const swapGuard = (side: 'L' | 'R', v: string) => {
    if (side === 'L') setLeft(v === right ? left : v)
    else setRight(v === left ? right : v)
  }

  const points = comparison.data?.points ?? []
  const latest = points[points.length - 1]
  const spreadValues = points
    .map((p) => p.spread_pct)
    .filter((v): v is number => v != null && Number.isFinite(v))
  const stats = useMemo(
    () => ({
      min: spreadValues.length ? Math.min(...spreadValues) : null,
      max: spreadValues.length ? Math.max(...spreadValues) : null,
      med: spreadValues.length ? medianOfArr(spreadValues) : null,
    }),
    [spreadValues.join(',')],
  )

  const corr = useMemo(() => {
    if (!seriesPair.data) return null
    const rows = seriesToChartRows(seriesPair.data) as { date: string; [k: string]: number | string }[]
    const sliced = sliceSeries(rows, range).filter((r) => typeof r[left] === 'number' && typeof r[right] === 'number')
    if (sliced.length < 3) return null
    const a = sliced.map((r) => Number(r[left]))
    const b = sliced.map((r) => Number(r[right]))
    return pearson(a, b)
  }, [seriesPair.data, range, left, right])

  return (
    <div className="space-y-4">
      {/* Selectors */}
      <Panel>
        <div className="flex flex-wrap items-center gap-3 py-1">
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold text-muted uppercase tracking-wide">Analyse</span>
            <select
              value={left}
              onChange={(e) => swapGuard('L', e.target.value)}
              className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
            >
              {SYMBOLS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <span className="text-muted text-[12px]">vs</span>
            <select
              value={right}
              onChange={(e) => swapGuard('R', e.target.value)}
              className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
            >
              {SYMBOLS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] text-muted">canonical pair: {pairId}</span>
            <RangeTabs value={range} onChange={setRange} compact />
          </div>
        </div>
      </Panel>

      {left === right && (
        <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-xl px-4 py-2.5 text-[12px] text-[#8F5D1D] font-medium">
          A pair needs two different contracts — the selectors blocked that. Pick a distinct second leg.
        </div>
      )}

      {/* Summary strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ['Observations', String(comparison.data?.point_count ?? 0), 'overlapping verified dates'],
          ['Latest spread', latest?.spread_pct != null ? fmtPct(latest.spread_pct, 2) : '—', latest?.trade_date ?? 'no data'],
          ['Spread median', stats.med != null ? `${stats.med.toFixed(2)}%` : '—', 'all loaded observations'],
          ['Window range', stats.min != null && stats.max != null ? `${stats.min.toFixed(2)}% – ${stats.max.toFixed(2)}%` : '—', 'min – max in range'],
        ].map(([k, v, sub]) => (
          <div key={k} className="bg-card border border-border rounded-xl p-3.5 shadow-panel">
            <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{k}</p>
            <p className="text-[16px] font-extrabold text-text mt-1">{v}</p>
            <p className="text-[10px] text-muted mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      {comparison.data && comparison.data.data_status !== 'OK' && (
        <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-xl px-4 py-2.5 text-[12px] text-[#8F5D1D] font-medium">
          Pair status: {comparison.data.data_status}. Dates where either leg lacks a verified observation are skipped, never forward-filled.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border px-1 overflow-x-auto thin-scroll">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3.5 py-2 text-[12px] font-semibold border-b-2 -mb-px whitespace-nowrap transition-colors ${
              tab === t ? 'border-maroon text-maroon' : 'border-transparent text-muted hover:text-text'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <Panel>
        {tab === 'Price Comparison' && (
          <div className="pt-2">
            <PriceComparisonChart ids={[left as ContractSymbol, right as ContractSymbol]} range={range} height={260} />
            <p className="text-[10px] text-muted mt-1.5">
              Both series normalized to ₹ per fine gram using verified contract specs (quote basis × purity).
            </p>
          </div>
        )}

        {tab === 'Spreads' && (
          <div className="pt-2">
            <SpreadChart pairId={pairId} range={range} showBand height={240} />
            <p className="text-[10px] text-muted mt-1.5">
              spread = (nL − nR) / ((nL + nR) / 2). Only real, verified, overlapping dates are charted.
            </p>
          </div>
        )}

        {tab === 'Relative Value' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            <div className="space-y-2 text-[12.5px] text-text leading-relaxed">
              <p>
                <strong>{left}</strong> and <strong>{right}</strong> are normalized to ₹ per fine gram from the backend's verified specifications.
              </p>
              <p>
                The relative spread between them on the latest overlapping date is{' '}
                <strong>{latest?.spread_pct != null ? fmtPct(latest.spread_pct, 2) : 'not yet available'}</strong>, computed from {comparison.data?.point_count ?? 0} real observations in this window.
              </p>
              <p className="text-muted text-[11.5px]">
                A spread wider than the pair&rsquo;s usual structure may indicate an unusual regime — but the anomaly screen, liquidity, expiry and cost guards decide whether to watch, act or ignore.
              </p>
            </div>
            <div className="bg-appBg border border-border rounded-xl p-4 space-y-2.5">
              {[
                ['Pair id', pairId],
                ['Range loaded', comparison.data ? `${comparison.data.range_start} → ${comparison.data.range_end}` : '—'],
                ['Overlapping dates', String(comparison.data?.point_count ?? 0)],
                ['Data status', comparison.data?.data_status ?? '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex items-center justify-between border-b border-border/50 pb-2 last:border-0">
                  <span className="text-[11.5px] text-muted">{k}</span>
                  <span className="text-[12px] font-semibold text-text">{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'Historical Correlation' && (
          <div className="pt-2 space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {[
                ['Correlation', corr == null ? '—' : corr.toFixed(3)],
                ['Days used', String(points.length)],
                ['Shared gold beta', 'High'],
              ].map(([k, v]) => (
                <div key={k} className="bg-appBg border border-border rounded-lg p-3 text-center">
                  <p className="text-[9.5px] font-semibold text-muted uppercase">{k}</p>
                  <p className="text-[15px] font-extrabold text-text mt-1">{v}</p>
                </div>
              ))}
            </div>
            <p className="text-[12px] text-muted leading-relaxed">
              All four contracts share international gold beta, so raw-price correlation is high across every pair. Relative-value work subtracts this common movement; what remains is the contract-specific residual the novelty detector evaluates.
            </p>
          </div>
        )}
      </Panel>

      {/* Latest anomaly classification */}
      {anomaly.data && anomaly.data.anomalies.length > 0 && (
        <Panel title="Latest scored observation for this pair" subtitle="From the model registry's latest anomalies" icon={<span className="text-[13px]">⚡</span>}>
          {anomaly.data.anomalies.map((a) => (
            <button
              key={a.score_id}
              onClick={() => onOpenSignal(a.pair_id)}
              className="w-full flex flex-wrap items-center gap-3 p-3 bg-appBg border border-border rounded-xl hover:bg-warmwhite transition-colors text-left"
            >
              <StatusBadge tone={a.is_anomaly ? statusTone(a.severity) : 'green'} dot>
                {a.is_anomaly ? a.severity : 'Normal'}
              </StatusBadge>
              <div className="min-w-0 flex-1">
                <p className="text-[12.5px] font-bold text-text">{pairLabel(a.pair_id)}</p>
                <p className="text-[11px] text-muted">{a.observation_date} · {a.disposition?.disposition ?? '—'}</p>
              </div>
              <div className="text-right">
                <p className="text-[12px] font-bold text-maroon">score {a.score.toFixed(2)} · z {fmtZ(a.robust_z)}</p>
                <p className="text-[10px] text-muted">{a.model_version ?? 'baseline scored'}</p>
              </div>
            </button>
          ))}
        </Panel>
      )}
      {anomaly.data && anomaly.data.anomalies.length === 0 && !anomaly.loading && (
        <Panel title="Latest scored observation for this pair" subtitle="No scored record yet">
          <p className="text-[11.5px] text-muted">
            This pair has no anomaly record in the database yet. It will be scored automatically once verified EOD history lands.
          </p>
        </Panel>
      )}
    </div>
  )
}

function medianOfArr(vals: number[]): number {
  const arr = [...vals].sort((a, b) => a - b)
  const n = arr.length
  return n % 2 ? arr[(n - 1) / 2] : (arr[n / 2 - 1] + arr[n / 2]) / 2
}

function pearson(a: number[], b: number[]): number {
  const n = a.length
  const ma = a.reduce((s, v) => s + v, 0) / n
  const mb = b.reduce((s, v) => s + v, 0) / n
  let num = 0
  let da = 0
  let db = 0
  for (let i = 0; i < n; i++) {
    num += (a[i] - ma) * (b[i] - mb)
    da += (a[i] - ma) ** 2
    db += (b[i] - mb) ** 2
  }
  return da === 0 || db === 0 ? 0 : num / Math.sqrt(da * db)
}
