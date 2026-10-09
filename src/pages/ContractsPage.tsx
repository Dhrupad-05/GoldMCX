import { useState, useMemo } from 'react'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { SpreadChart } from '../components/SpreadChart'
import { RangeTabs } from '../components/RangeTabs'
import { CONTRACTS, CONTRACT_MAP, ALL_PAIRS } from '../data/contracts'
import { PRICE_SERIES, normalizedPrice } from '../data/marketSeries'
import { pairLabel, type TimeRange } from '../lib/filters'
import { fmtINR, fmtPct } from '../lib/demoUtil'
import type { ContractId } from '../types'

const TABS = ['Overview', 'Price Chart', 'Term Structure', 'Historical Data', 'Specifications'] as const
type Tab = (typeof TABS)[number]

export function ContractsPage({
  selected,
  onSelect,
}: {
  selected: ContractId
  onSelect: (id: ContractId) => void
}) {
  const [tab, setTab] = useState<Tab>('Overview')
  const [range, setRange] = useState<TimeRange>('3M')
  const c = CONTRACT_MAP[selected]
  const series = PRICE_SERIES[selected]
  const last = series[series.length - 1].value
  const norm = normalizedPrice(c.demoPrice, c.quoteGrams, c.purity)
  const pairsFor = ALL_PAIRS.filter((p) => p.left === selected || p.right === selected)

  return (
    <div className="space-y-4">
      {/* Contract selector */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {CONTRACTS.map((k) => (
          <button
            key={k.id}
            onClick={() => onSelect(k.id)}
            className={`rounded-xl border p-3.5 text-left transition-all ${
              k.id === selected
                ? 'bg-maroon text-warmwhite border-maroon shadow-panel'
                : 'bg-card border-border hover:shadow-soft'
            }`}
          >
            <p className="text-[13px] font-extrabold">{k.symbol}</p>
            <p className={`text-[10.5px] mt-0.5 ${k.id === selected ? 'text-warmwhite/70' : 'text-muted'}`}>{k.displayName} · {k.expiryLabel}</p>
            <p className={`text-[14px] font-bold mt-1.5 ${k.id === selected ? 'text-gold' : 'text-text'}`}>{fmtINR(k.demoPrice)}</p>
            <StatusBadge tone={k.id === selected ? 'gold' : 'neutral'}>{fmtPct(k.demoChangePct)}</StatusBadge>
          </button>
        ))}
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-[18px] font-extrabold text-text" style={{ fontFamily: 'Georgia, serif' }}>
          {c.symbol} — {c.displayName}
        </h2>
        <StatusBadge tone="green" dot>Active</StatusBadge>
        <span className="text-[11.5px] text-muted ml-auto">Illustrative prices · {c.expiryLabel} contract</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border px-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3.5 py-2 text-[12px] font-semibold border-b-2 -mb-px transition-colors ${
              tab === t ? 'border-maroon text-maroon' : 'border-transparent text-muted hover:text-text'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <Panel>
        {tab === 'Overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            <div>
              <p className="text-[12.5px] text-muted leading-relaxed">{c.description}</p>
              <div className="grid grid-cols-2 gap-2 mt-4">
                {[
                  ['Last price (demo)', fmtINR(c.demoPrice)],
                  ['Day change (demo)', fmtPct(c.demoChangePct)],
                  ['Normalized value', `₹${norm.toFixed(0)} / fine g`],
                  ['Status', c.status],
                ].map(([k, v]) => (
                  <div key={k} className="bg-appBg border border-border rounded-lg px-3 py-2">
                    <p className="text-[9.5px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                    <p className="text-[13px] font-bold text-text mt-0.5">{v}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-lg bg-[#B87928]/10 border border-[#B87928]/25 p-3 text-[11.5px] text-[#8F5D1D] leading-relaxed">
                Prices shown are hardcoded demo values, not a live MCX feed.
              </div>
            </div>
            <div>
              <p className="text-[11px] font-bold text-text mb-2">Pairs involving {c.symbol}</p>
              <div className="space-y-2">
                {pairsFor.map((p) => (
                  <div key={p.pairId} className="flex items-center justify-between bg-appBg border border-border rounded-lg px-3 py-2">
                    <span className="text-[12px] font-semibold text-text">{pairLabel(p.pairId)}</span>
                    <span className="text-[10.5px] text-muted">6 pairs available app-wide</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'Price Chart' && (
          <div className="pt-2">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[12.5px] font-bold text-text">Price (₹ per quote basis) — {c.symbol}</p>
              <RangeTabs value={range} onChange={setRange} compact />
            </div>
            <PriceComparisonChart ids={[c.id]} range={range} height={280} />
            <p className="text-[10px] text-muted mt-1">Single-series demo chart; raw quotes, not normalized.</p>
          </div>
        )}

        {tab === 'Term Structure' && (
          <div className="space-y-4 pt-2">
            <p className="text-[12.5px] text-muted">
              Relative spreads of {c.symbol} against the other three contracts. Structural levels differ by pair — small-lot pairs trade wider.
            </p>
            {pairsFor.map((p) => (
              <div key={p.pairId}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-bold text-text">{pairLabel(p.pairId)}</p>
                  <span className="text-[10px] text-muted">normalized spread % · demo series</span>
                </div>
                <SpreadChart pairId={p.pairId} range={range} showBand={false} height={120} />
              </div>
            ))}
          </div>
        )}

        {tab === 'Historical Data' && (
          <div className="pt-2">
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Close (demo)</th>
                    <th className="py-2 pr-3">Normalized ₹/fine g</th>
                  </tr>
                </thead>
                <tbody>
                  {slice(series, 10).map((p, i) => {
                    const n = normalizedPrice(p.value, c.quoteGrams, c.purity)
                    return (
                      <tr key={i} className="border-b border-border/40">
                        <td className="py-2 pr-3 text-[11.5px] text-muted">{p.date}</td>
                        <td className="py-2 pr-3 text-[12px] font-semibold text-text">{fmtINR(p.value)}</td>
                        <td className="py-2 pr-3 text-[12px] text-text">{n.toFixed(2)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-[10px] text-muted mt-2">Last 10 of 60 consecutive demo sessions.</p>
          </div>
        )}

        {tab === 'Specifications' && (
          <div className="pt-2 max-w-xl">
            <table className="w-full text-left">
              <tbody>
                {[
                  ['Symbol', `${c.symbol} (demo)`],
                  ['Trading unit', `${c.tradingUnitGrams} g`],
                  ['Quoted basis', `per ${c.quoteGrams} g`],
                  ['Purity', `${c.purity} / 1000 fine`],
                  ['Fine content quoted', `${(c.quoteGrams * c.purity) / 1000} g`],
                  ['Expiry label', c.expiryLabel],
                  ['Value (quoted)', fmtINR(c.demoPrice)],
                ].map(([k, v]) => (
                  <tr key={k} className="border-b border-border/40">
                    <td className="py-2.5 pr-3 text-[12px] text-muted font-medium">{k}</td>
                    <td className="py-2.5 text-[12.5px] font-semibold text-text">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
              Trading unit, quoted basis and purity are taken from the PS-03 problem statement. Expiry labels and other details are illustrative demo configuration — verify against official MCX specifications before any real use.
            </div>
          </div>
        )}
      </Panel>
    </div>
  )
}

function slice<T>(arr: T[], n: number): T[] {
  return arr.slice(-n)
}

export { useMemo }
