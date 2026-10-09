import {
  ShieldCheck,
  Sparkles,
  Lightbulb,
  BarChart3,
  ArrowRight,
  Database,
  RefreshCw,
  ScanSearch,
  BadgeCheck,
  MessagesSquare,
  ChevronRight,
  ExternalLink,
  Layers,
  GitCompareArrows,
  Bolt,
} from 'lucide-react'
import { useState } from 'react'
import { Panel } from '../components/Panel'
import { ContractCard } from '../components/ContractCard'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { SignalDetailModal } from '../components/SignalDetailModal'
import { RangeTabs, } from '../components/RangeTabs'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { SpreadChart } from '../components/SpreadChart'
import { Sparkline } from '../components/Sparkline'
import { CONTRACTS, CONTRACT_MAP } from '../data/contracts'
import { SIGNALS } from '../data/signals'
import { RESEARCH_CARDS } from '../data/researchCards'
import { pairLabel, sliceForRange, type TimeRange } from '../lib/filters'
import { normalizedPrice } from '../data/marketSeries'
import { PRICE_SERIES } from '../data/marketSeries'
import { fmtINR } from '../lib/demoUtil'
import type { ContractId, DemoSignal, ViewId } from '../types'

const FEATURES = [
  { icon: Database, label: 'Contract Aware', sub: 'MCX contracts · lots + purity', demo: 'Illustrative · Live' },
  { icon: ShieldCheck, label: 'Contract Aware', sub: 'Units, purity, expiry', demo: '' },
  { icon: Sparkles, label: 'AI-Driven Signals', sub: 'Explainable anomaly alerts' },
  { icon: Lightbulb, label: 'Explainable Insights', sub: 'Reason codes + charts' },
]

const STEPS = [
  { n: '01', icon: Database, title: 'Collect', desc: 'Live & historical MCX data' },
  { n: '02', icon: RefreshCw, title: 'Normalize', desc: 'Adjust for unit size, purity, expiry' },
  { n: '03', icon: ScanSearch, title: 'Detect', desc: 'Find unusual spreads and price deviations' },
  { n: '04', icon: BadgeCheck, title: 'Validate', desc: 'Check for realistic costs and liquidity' },
  { n: '05', icon: MessagesSquare, title: 'Insights', desc: 'Deliver signals with reason codes and explanations' },
]

export function DashboardPage({
  onNavigate,
  onOpenSignal,
  onSelectContract,
  comparisonRange,
  setComparisonRange,
  detailRange,
  setDetailRange,
  compareLeft,
  setCompareLeft,
}: {
  onNavigate: (v: ViewId) => void
  onOpenSignal: (s: DemoSignal) => void
  onSelectContract: (id: ContractId) => void
  comparisonRange: TimeRange
  setComparisonRange: (r: TimeRange) => void
  detailRange: TimeRange
  setDetailRange: (r: TimeRange) => void
  compareLeft: ContractId
  setCompareLeft: (c: ContractId) => void
}) {
  const allFour = CONTRACTS.map((c) => c.id)
  const keySignals = [...SIGNALS].sort((a, b) => b.score - a.score).slice(0, 3)
  const latestSignals = SIGNALS.slice(0, 5)

  return (
    <div className="space-y-4">
      {/* Grid row 1: hero + contract cards */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(340px,7fr)_minmax(0,12fr)] gap-4">
        {/* Hero */}
        <section className="hero-texture rounded-2xl p-6 text-warmwhite relative overflow-hidden">
          <div className="absolute inset-0 pointer-events-none opacity-40" aria-hidden>
            {/* decorative gold bars */}
            <svg width="220" height="160" viewBox="0 0 220 160" className="absolute right-2 top-6 opacity-60">
              <g transform="rotate(-12 110 80)">
                <rect x="20" y="30" width="120" height="34" rx="5" fill="#C99A53" opacity="0.95" />
                <rect x="44" y="70" width="120" height="34" rx="5" fill="#B9844B" opacity="0.9" />
                <rect x="68" y="110" width="120" height="34" rx="5" fill="#C99A53" opacity="0.85" />
                <text x="58" y="50" fontSize="9" fill="#3B1117" fontWeight="700">999.9 GOLD</text>
                <text x="82" y="90" fontSize="9" fill="#3B1117" fontWeight="700">999.9 GOLD</text>
                <text x="106" y="130" fontSize="9" fill="#3B1117" fontWeight="700">999.9 GOLD</text>
              </g>
            </svg>
            <div className="absolute -left-8 -bottom-10 w-52 h-52 rounded-full bg-gold/10 blur-2xl" />
          </div>
          <div className="relative">
            <p className="text-[9.5px] tracking-[0.28em] font-bold text-gold/90 uppercase">MCX Gold Relative Value Intelligence</p>
            <h2 className="text-[30px] leading-[1.08] mt-2 font-bold" style={{ fontFamily: 'Georgia, serif' }}>
              Same Gold.
              <br />
              <span className="text-gold">Different Opportunities.</span>
            </h2>
            <p className="text-[12px] text-warmwhite/75 mt-3 leading-relaxed max-w-[300px]">
              Analyze spreads, detect anomalies and find relative-value opportunities across MCX gold contracts using normalized pricing and statistical analysis.
            </p>
            <div className="flex items-center gap-2.5 mt-5">
              <button
                onClick={() => document.getElementById('dashboard-signals')?.scrollIntoView({ behavior: 'smooth' })}
                className="flex items-center gap-1.5 bg-warmwhite text-deeper font-bold text-[12px] px-4 py-2.5 rounded-lg hover:bg-gold/20 transition-colors"
              >
                Explore Insights <ChevronRight size={13} />
              </button>
              <button
                onClick={() => onNavigate('learn')}
                className="flex items-center gap-1.5 border border-warmwhite/30 text-warmwhite font-semibold text-[12px] px-4 py-2.5 rounded-lg hover:bg-warmwhite/10 transition-colors"
              >
                How It Works <ChevronRight size={13} />
              </button>
            </div>
            {/* feature chips */}
            <div className="grid grid-cols-2 gap-2 mt-6 max-w-[340px]">
              {[
                { icon: Database, label: 'Real MCX Data', sub: 'Historical · Demo' },
                { icon: ShieldCheck, label: 'Contract Aware', sub: 'Units, purity, expiry' },
                { icon: Sparkles, label: 'AI-Driven Signals', sub: 'Explainable anomaly alerts' },
                { icon: Lightbulb, label: 'Explainable Insights', sub: 'Reason codes + charts' },
              ].map((f, i) => (
                <div key={i} className="flex items-center gap-2 rounded-lg bg-warmwhite/8 border border-warmwhite/10 px-2.5 py-2">
                  <f.icon size={13} className="text-gold shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10.5px] font-bold truncate">{f.label}</p>
                    <p className="text-[8.5px] text-warmwhite/55 truncate">{f.sub}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Right column: contract cards + trend chart */}
        <div className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {CONTRACTS.map((c) => (
              <ContractCard key={c.id} contractId={c.id} onClick={onSelectContract} />
            ))}
          </div>
          <Panel
            title="Price Trend Comparison"
            subtitle="Normalized per fine gram · illustrative local series"
            right={<RangeTabs value={comparisonRange} onChange={setComparisonRange} compact />}
            icon={<BarChart3 size={15} />}
          >
            <PriceComparisonChart ids={allFour} range={comparisonRange} height={196} />
            <p className="text-[10px] text-muted mt-1.5">Synthetic demo series — not observed MCX history.</p>
          </Panel>
        </div>
      </div>

      {/* Grid row 2: latest signals + contract detail + compare widget */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,9fr)_minmax(0,10fr)_minmax(0,9fr)] gap-4">
        {/* Latest signals */}
        <Panel
          title="Latest Signals"
          subtitle="Detected unusual spreads, volume and price movements"
          className="min-w-0"
          icon={<Bolt size={15} />}
          right={
            <button onClick={() => onNavigate('signals')} className="text-[11px] font-semibold text-maroon hover:underline">
              View All
            </button>
          }
        >
          <div className="space-y-2" id="dashboard-signals">
            {latestSignals.map((s) => (
              <button
                key={s.id}
                onClick={() => onOpenSignal(s)}
                className="w-full flex items-center gap-2.5 p-2.5 rounded-lg hover:bg-appBg transition-colors text-left"
              >
                <StatusBadge tone={statusTone(s.status)} dot>{s.status}</StatusBadge>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold text-text truncate">{s.title}</p>
                  <p className="text-[10.5px] text-muted truncate">{pairLabel(s.pairId)} · {s.type}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[11px] font-bold text-maroon">z {s.robustZ.toFixed(1)}</p>
                  <p className="text-[9.5px] text-muted">{s.date}</p>
                </div>
              </button>
            ))}
          </div>
        </Panel>

        {/* Contract details */}
        <Panel
          title="Contract Details"
          icon={<Layers size={15} />}
          right={
            <select
              value={compareLeft}
              onChange={(e) => setCompareLeft(e.target.value as ContractId)}
              className="text-[11.5px] font-semibold bg-appBg border border-border rounded-md px-2 py-1 outline-none"
            >
              {CONTRACTS.map((c) => (
                <option key={c.id} value={c.id}>{c.symbol} ({c.expiryLabel})</option>
              ))}
            </select>
          }
        >
          {(() => {
            const c = CONTRACT_MAP[compareLeft]
            const series = PRICE_SERIES[c.id]
            const last = series[series.length - 1].value
            const norm = normalizedPrice(last, c.quoteGrams, c.purity)
            return (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-extrabold text-text">{c.symbol} <span className="text-muted font-semibold text-[10px]">{c.expiryLabel}</span></span>
                    <StatusBadge tone="green" dot>Active</StatusBadge>
                  </div>
                  <button onClick={() => onSelectContract(c.id)} className="text-[11px] font-semibold text-maroon hover:underline flex items-center gap-0.5">
                    Full profile <ArrowRight size={10} />
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    ['Last price', fmtINR(c.demoPrice)],
                    ['Volume', '12,840 lots'],
                    ['Open interest', '26,419 lots'],
                    ['Expiry', c.expiryLabel],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-appBg border border-border rounded-lg px-2 py-1.5 text-center">
                      <p className="text-[9px] text-muted font-semibold uppercase tracking-wide">{k}</p>
                      <p className="text-[12px] font-bold text-text mt-0.5 truncate">{v}</p>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-[10.5px] font-bold text-text mb-1">Price (₹/gram)</p>
                    <PriceComparisonChart ids={[c.id]} range={detailRange} height={130} />
                  </div>
                  <div className="text-[11px] space-y-1.5">
                    <p className="text-[10.5px] font-bold text-text mb-1">Contract Information</p>
                    {[
                      ['Symbol', `${c.symbol} ${c.expiryLabel === 'OCT 2025' ? 'OCT' : ''}`],
                      ['Full name', c.displayName],
                      ['Quoted basis', `per ${c.quoteGrams} g`],
                      ['Trading unit', `${c.tradingUnitGrams} g / lot`],
                      ['Purity', `${c.purity} / 1000`],
                      ['Normalized', `₹${norm.toFixed(0)}/fine g`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between gap-2 border-b border-border/50 pb-1">
                        <span className="text-muted shrink-0">{k}</span>
                        <span className="font-semibold text-text text-right truncate">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })()}
        </Panel>

        {/* Compare contracts widget */}
        <Panel
          title="Compare Contracts"
          subtitle="Analyze spreads, price ratio and term structure"
          icon={<GitCompareArrows size={15} />}
          right={
            <button onClick={() => onNavigate('comparison')} className="text-[11px] font-semibold text-maroon hover:underline">
              Full view
            </button>
          }
        >
          {(() => {
            const left = CONTRACT_MAP[compareLeft]
            const right = CONTRACT_MAP['GOLDTEN']
            return (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-2.5 py-1 rounded-md bg-maroon text-warmwhite text-[10.5px] font-bold">{left.symbol}</span>
                  <span className="text-muted text-[11px]">vs</span>
                  <span className="px-2.5 py-1 rounded-md bg-appBg border border-border text-[10.5px] font-bold text-text">{right.symbol}</span>
                  <span className="ml-auto text-[10px] text-muted">per-gram comparison</span>
                </div>
                <PriceComparisonChart ids={[left.id, right.id]} range={comparisonRange} height={150} />
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="rounded-lg bg-appBg border border-border p-2">
                    <p className="text-[9.5px] font-semibold text-muted uppercase">Normalized left</p>
                    <p className="text-[12.5px] font-bold text-text mt-0.5">₹{normalizedPrice(left.demoPrice, left.quoteGrams, left.purity).toFixed(0)}/g</p>
                  </div>
                  <div className="rounded-lg bg-appBg border border-border p-2">
                    <p className="text-[9.5px] font-semibold text-muted uppercase">Normalized right</p>
                    <p className="text-[12.5px] font-bold text-text mt-0.5">₹{normalizedPrice(right.demoPrice, right.quoteGrams, right.purity).toFixed(0)}/g</p>
                  </div>
                </div>
              </div>
            )
          })()}
        </Panel>
      </div>

      {/* Grid row 3: How it works + insights strip */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,8fr)_minmax(0,10fr)] gap-4">
        <Panel title="How It Works" subtitle="From raw MCX data to actionable insights" icon={<ScanSearch size={15} />}>
          <div className="flex items-stretch gap-0">
            {STEPS.map((s, i) => (
              <div key={s.n} className="flex-1 flex items-center">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="w-6 h-6 rounded-md bg-maroon/10 text-maroon flex items-center justify-center">
                      <s.icon size={12} />
                    </span>
                    <span className="text-[11px] font-bold text-gold">{s.n}</span>
                  </div>
                  <p className="text-[11.5px] font-bold text-text mt-1">{s.title}</p>
                  <p className="text-[9.5px] text-muted leading-tight mt-0.5">{s.desc}</p>
                </div>
                {i < STEPS.length - 1 && <div className="w-4 text-border shrink-0">→</div>}
              </div>
            ))}
          </div>
          <button
            onClick={() => onNavigate('model')}
            className="mt-3 w-full text-center text-[11.5px] font-semibold text-maroon hover:underline"
          >
            See the normality-learning demo →
          </button>
        </Panel>

        <Panel
          title="Market Insights"
          subtitle="Stay informed on analytics, trends and educational content"
          icon={<NewspaperIcon />}
          right={
            <button onClick={() => onNavigate('insights')} className="text-[11px] font-semibold text-maroon hover:underline">
              View All
            </button>
          }
        >
          <div className="grid grid-cols-3 gap-3">
            {RESEARCH_CARDS.slice(0, 3).map((card) => (
              <button
                key={card.id}
                onClick={() => onOpenInsight(card.id)}
                className="text-left rounded-xl overflow-hidden border border-border bg-card hover:shadow-soft hover:-translate-y-px transition-all"
              >
                <div className="hero-texture h-16 relative flex items-end p-2">
                  <Sparkline points={[5, 9, 7, 12, 10, 15]} color="#C99A53" width={50} height={22} />
                  <span className="absolute top-1.5 right-1.5 text-[8px] font-bold text-warmwhite/80 bg-deeper/50 px-1.5 py-0.5 rounded">
                    {card.category}
                  </span>
                </div>
                <div className="p-2">
                  <p className="text-[11px] font-bold text-text leading-tight line-clamp-2">{card.title}</p>
                  <p className="text-[9px] text-muted mt-1">{card.date}</p>
                </div>
              </button>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function NewspaperIcon() {
  return <ExternalLink size={15} />
}

// helper to open insight modal handled at App level via onOpenResult
function onOpenInsight(id: string) {
  window.dispatchEvent(new CustomEvent('open-insight', { detail: id }))
}

export { KeySignalsMini } from '../components/KeySignalsMini'
