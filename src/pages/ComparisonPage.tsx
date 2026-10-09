import { useMemo, useState } from 'react'
import { Panel } from '../components/Panel'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { SpreadChart } from '../components/SpreadChart'
import { RangeTabs } from '../components/RangeTabs'
import { CONTRACTS, CONTRACT_MAP, ALL_PAIRS } from '../data/contracts'
import { PRICE_SERIES, normalizedPrice } from '../data/marketSeries'
import { SPREAD_SERIES } from '../data/spreads'
import { signalForPair } from '../data/signalForPair'
import { pairLabel, type TimeRange } from '../lib/filters'
import { fmtPct, fmtZ } from '../lib/demoUtil'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import type { ContractId, DemoSignal } from '../types'

const TABS = ['Price Comparison', 'Spreads', 'Relative Value', 'Historical Correlation'] as const

export function ComparisonPage({
  left,
  right,
  setLeft,
  setRight,
  onOpenSignal,
}: {
  left: ContractId
  right: ContractId
  setLeft: (c: ContractId) => void
  setRight: (c: ContractId) => void
  onOpenSignal: (s: DemoSignal) => void
}) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Price Comparison')
  const [range, setRange] = useState<TimeRange>('3M')
  const pairId = useMemo(
    () => ALL_PAIRS.find((p) => (p.left === left && p.right === right) || (p.left === right && p.right === left))?.pairId ?? 'GOLDM-GOLDTEN',
    [left, right],
  )
  const signal = signalForPair(pairId)
  const cl = CONTRACT_MAP[left]
  const cr = CONTRACT_MAP[right]
  const nLeft = normalizedPrice(cl.demoPrice, cl.quoteGrams, cl.purity)
  const nRight = normalizedPrice(cr.demoPrice, cr.quoteGrams, cr.purity)
  const spreadNow = ((nLeft - nRight) / ((nLeft + nRight) / 2)) * 100

  const corr = useMemo(() => {
    const a = PRICE_SERIES[left]
    const b = PRICE_SERIES[right]
    const n = Math.min(a.length, b.length)
    const ra = a.slice(-n).map((p) => p.value)
    const rb = b.slice(-n).map((p) => p.value)
    const ma = ra.reduce((s, v) => s + v, 0) / n
    const mb = rb.reduce((s, v) => s + v, 0) / n
    let num = 0
    let da = 0
    let db = 0
    for (let i = 0; i < n; i++) {
      num += (ra[i] - ma) * (rb[i] - mb)
      da += (ra[i] - ma) ** 2
      db += (rb[i] - mb) ** 2
    }
    return num / Math.sqrt(da * db)
  }, [left, right])

  const swapGuard = (side: 'L' | 'R', v: ContractId) => {
    if (side === 'L') setLeft(v === right ? left : v)
    else setRight(v === left ? right : v)
  }

  return (
    <div className="space-y-4">
      {/* Selectors */}
      <Panel>
        <div className="flex flex-wrap items-center gap-3 py-1">
          <div className="flex items-center gap-2">
            <span className="text-[10.5px] font-bold text-muted uppercase tracking-wide">Analyse</span>
            <select
              value={left}
              onChange={(e) => swapGuard('L', e.target.value as ContractId)}
              className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
            >
              {CONTRACTS.map((c) => (
                <option key={c.id} value={c.id}>{c.symbol}</option>
              ))}
            </select>
            <span className="text-muted text-[12px]">vs</span>
            <select
              value={right}
              onChange={(e) => swapGuard('R', e.target.value as ContractId)}
              className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
            >
              {CONTRACTS.map((c) => (
                <option key={c.id} value={c.id}>{c.symbol}</option>
              ))}
            </select>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] text-muted">6 unique pairs · currently {pairId}</span>
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
          ['Normalized left', `₹${nLeft.toFixed(0)} / fine g`, `per ${cl.quoteGrams} g · ${cl.purity} purity`],
          ['Normalized right', `₹${nRight.toFixed(0)} / fine g`, `per ${cr.quoteGrams} g · ${cr.purity} purity`],
          ['Current spread (demo)', fmtPct(spreadNow, 2), 'normalized relative spread'],
          ['Correlation (demo)', corr.toFixed(2), 'of raw demo price series'],
        ].map(([k, v, sub]) => (
          <div key={k} className="bg-card border border-border rounded-xl p-3.5 shadow-panel">
            <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{k}</p>
            <p className="text-[16px] font-extrabold text-text mt-1">{v}</p>
            <p className="text-[10px] text-muted mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

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
            <PriceComparisonChart ids={[left, right]} range={range} height={260} />
            <p className="text-[10px] text-muted mt-1.5">
              Both series re-based to ₹ per fine gram (quote basis × purity). Demo data.
            </p>
          </div>
        )}

        {tab === 'Spreads' && (
          <div className="pt-2">
            <SpreadChart pairId={pairId} range={range} showBand height={240} />
            <div className="grid grid-cols-3 gap-2 mt-3">
              {[
                ['Band centre', `${medianOf(pairId).toFixed(2)}%`],
                ['Latest spread', `${(SPREAD_SERIES[pairId][SPREAD_SERIES[pairId].length - 1]?.spreadPct ?? 0).toFixed(2)}%`],
                ['Range (90d)', `${(Math.min(...SPREAD_SERIES[pairId].map((p) => p.spreadPct))).toFixed(2)}% – ${(Math.max(...SPREAD_SERIES[pairId].map((p) => p.spreadPct))).toFixed(2)}%`],
              ].map(([k, v]) => (
                <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                  <p className="text-[9.5px] font-semibold text-muted uppercase">{k}</p>
                  <p className="text-[12.5px] font-bold text-text mt-0.5">{v}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'Relative Value' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            <div className="space-y-2 text-[12.5px] text-text leading-relaxed">
              <p><strong>{cl.symbol}</strong> is quoted per {cl.quoteGrams} g at {cl.purity} purity; <strong>{cr.symbol}</strong> is quoted per {cr.quoteGrams} g at {cr.purity} purity.</p>
              <p>After normalization both are expressed in ₹ per fine gram: ₹{nLeft.toFixed(0)} vs ₹{nRight.toFixed(0)}, a relative spread of <strong>{fmtPct(spreadNow, 2)}</strong> (demo values).</p>
              <p className="text-muted text-[11.5px]">A spread wider than the pair&rsquo;s usual carry + premium structure may indicate an unusual regime — but the anomaly screen, liquidity, expiry and cost guards decide whether to watch, act or ignore.</p>
            </div>
            <div className="bg-appBg border border-border rounded-xl p-4 space-y-2.5">
              {[
                ['Quote basis difference', cl.quoteGrams === cr.quoteGrams ? 'Same basis' : `${cl.quoteGrams} g vs ${cr.quoteGrams} g`],
                ['Purity gap', `${Math.abs(cl.purity - cr.purity)} (${cl.purity} vs ${cr.purity})`],
                ['Unit ratio', `${(cl.tradingUnitGrams / cr.tradingUnitGrams).toFixed(2)}× (lot exposure)`],
                ['Demo price ratio', `${(cl.demoPrice / cr.demoPrice).toFixed(2)}× (per quote)`],
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
                ['Correlation (demo)', corr.toFixed(3)],
                ['Corr. last 30 sessions', corr30(left, right).toFixed(3)],
                ['Shared gold beta', 'High'],
              ].map(([k, v]) => (
                <div key={k} className="bg-appBg border border-border rounded-lg p-3 text-center">
                  <p className="text-[9.5px] font-semibold text-muted uppercase">{k}</p>
                  <p className="text-[15px] font-extrabold text-text mt-1">{v}</p>
                </div>
              ))}
            </div>
            <p className="text-[12px] text-muted leading-relaxed">
              All four contracts share international gold beta, so raw-price correlation is high across every pair. Relative-value work subtracts this common movement; what remains is the contract-specific residual that the novelty detector evaluates.
            </p>
          </div>
        )}
      </Panel>

      {/* Latest anomaly classification */}
      {signal && (
        <Panel title="Latest anomaly classification for this pair" subtitle="From the shared signals dataset" icon={<span className="text-[13px]">⚡</span>}>
          <button
            onClick={() => onOpenSignal(signal)}
            className="w-full flex flex-wrap items-center gap-3 p-3 bg-appBg border border-border rounded-xl hover:bg-warmwhite transition-colors text-left"
          >
            <StatusBadge tone={statusTone(signal.status)} dot>{signal.status}</StatusBadge>
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-bold text-text">{signal.title}</p>
              <p className="text-[11px] text-muted">{signal.date} · {signal.type}</p>
            </div>
            <div className="text-right">
              <p className="text-[12px] font-bold text-maroon">score {signal.score.toFixed(2)} · z {fmtZ(signal.robustZ)}</p>
              <p className="text-[10px] text-muted">liquidity: {signal.liquidity} · expiry: {signal.daysToExpiry}d</p>
            </div>
          </button>
        </Panel>
      )}
    </div>
  )
}

function medianOf(pairId: string): number {
  const arr = SPREAD_SERIES[pairId].map((p) => p.spreadPct).sort((a, b) => a - b)
  return arr[Math.floor(arr.length / 2)]
}

function corr30(l: ContractId, r: ContractId): number {
  const a = PRICE_SERIES[l].slice(-30).map((p) => p.value)
  const b = PRICE_SERIES[r].slice(-30).map((p) => p.value)
  const n = a.length
  const ma = a.reduce((s, v) => s + v, 0) / n
  const mb = b.reduce((s, v) => s + v, 0) / n
  let num = 0, da = 0, db = 0
  for (let i = 0; i < n; i++) { num += (a[i] - ma) * (b[i] - mb); da += (a[i] - ma) ** 2; db += (b[i] - mb) ** 2 }
  return num / Math.sqrt(da * db)
}

export { pairLabel, CONTRACTS }
