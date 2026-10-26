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
import { Panel } from '../components/Panel'
import { ContractCard } from '../components/ContractCard'
import { StatusBadge } from '../components/StatusBadge'
import { RangeTabs } from '../components/RangeTabs'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { Sparkline } from '../components/Sparkline'
import { DataState } from '../components/DataState'
import { KeySignalsMini } from '../components/KeySignalsMini'
import { api, pairLabel } from '../lib/api'
import type { DashboardSummary, ContractSymbol, MlAnomaly, SeriesResponse } from '../lib/api'
import { useApi } from '../lib/useApi'
import { quoteIfFresh } from '../lib/useMarketStream'
import type { MarketStreamState } from '../lib/useMarketStream'
import { fmtDateTime } from '../lib/demoUtil'
import type { TimeRange } from '../lib/filters'
import type { ViewId } from '../types'

const STEPS = [
  { n: '01', icon: Database, title: 'Collect', desc: 'Official MCX Bhavcopy + authorized providers' },
  { n: '02', icon: RefreshCw, title: 'Normalize', desc: 'Adjust for unit size, purity, expiry' },
  { n: '03', icon: ScanSearch, title: 'Detect', desc: 'Statistical novelty on real pair features' },
  { n: '04', icon: BadgeCheck, title: 'Validate', desc: 'Liquidity, cost and expiry checks' },
  { n: '05', icon: MessagesSquare, title: 'Insights', desc: 'Signals with reason codes and lineage' },
]

export function DashboardPage({
  stream,
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
  stream: MarketStreamState
  onNavigate: (v: ViewId) => void
  onOpenSignal: (a: MlAnomaly) => void
  onSelectContract: (id: string) => void
  comparisonRange: TimeRange
  setComparisonRange: (r: TimeRange) => void
  detailRange: TimeRange
  setDetailRange: (r: TimeRange) => void
  compareLeft: string
  setCompareLeft: (c: string) => void
}) {
  const allFour: ContractSymbol[] = ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']
  const summary = useApi(() => api.dashboardSummary(), [])
  const compareSeries = useApi<SeriesResponse[]>(
    () => Promise.all([api.contractSeries(compareLeft), api.contractSeries('GOLDTEN')]),
    [compareLeft],
  )
  const anomalies = useApi(() => api.latestAnomalies(undefined, 6), [])

  const data = summary.data
  const contracts = data?.contracts ?? []

  const lPts = compareSeries.data?.[0]?.points
  const rPts = compareSeries.data?.[1]?.points
  const lastLeft = lPts && lPts.length > 0 ? lPts[lPts.length - 1].normalized_value : null
  const lastRight = rPts && rPts.length > 0 ? rPts[rPts.length - 1].normalized_value : null

  return (
    <div className="space-y-4">
      {/* Grid row 1: hero + contract cards */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(340px,7fr)_minmax(0,12fr)] gap-4">
        {/* Hero */}
        <section className="hero-texture rounded-2xl p-6 text-warmwhite relative overflow-hidden">
          <div className="absolute inset-0 pointer-events-none opacity-40" aria-hidden>
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
              Statistical novelty on normalized cross-contract relationships, trained on official MCX history. Quiet until the data justifies a signal.
            </p>
            <div className="flex items-center gap-2.5 mt-5">
              <button
                onClick={() => document.getElementById('dashboard-signals')?.scrollIntoView({ behavior: 'smooth' })}
                className="flex items-center gap-1.5 bg-warmwhite text-deeper font-bold text-[12px] px-4 py-2.5 rounded-lg hover:bg-gold/20 transition-colors"
              >
                Explore Signals <ChevronRight size={13} />
              </button>
              <button
                onClick={() => onNavigate('learn')}
                className="flex items-center gap-1.5 border border-warmwhite/30 text-warmwhite font-semibold text-[12px] px-4 py-2.5 rounded-lg hover:bg-warmwhite/10 transition-colors"
              >
                How It Works <ChevronRight size={13} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-6 max-w-[340px]">
              {[
                { icon: Database, label: 'Real MCX Data', sub: 'Official Bhavcopy + providers' },
                { icon: ShieldCheck, label: 'Contract Aware', sub: 'Units, purity, expiry' },
                { icon: Sparkles, label: 'AI-Driven Signals', sub: 'Trained model + SSE updates' },
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
            {allFour.map((sym) => (
              <ContractCard
                key={sym}
                symbol={sym}
                quote={quoteIfFresh([...stream.quotes.values()].find((q) => q.canonical_symbol === sym))}
                onOpen={() => onSelectContract(sym)}
              />
            ))}
          </div>
          <Panel
            title="Normalized Price Trend"
            subtitle="₹ per fine gram · official verified observations"
            right={<RangeTabs value={comparisonRange} onChange={setComparisonRange} compact />}
            icon={<BarChart3 size={15} />}
          >
            <PriceComparisonChart ids={allFour} range={comparisonRange} height={196} />
            <p className="text-[10px] text-muted mt-1.5">
              Real trade dates from the backend. Gaps appear where a leg has no verified observation — none are filled.
            </p>
          </Panel>
        </div>
      </div>

      {/* Grid row 2: latest signals + contract detail + compare widget */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,9fr)_minmax(0,10fr)_minmax(0,9fr)] gap-4">
        {/* Latest signals */}
        <Panel
          title="Latest Signals"
          subtitle="Model-scored anomalies and dispositions"
          className="min-w-0"
          icon={<Bolt size={15} />}
          right={
            <button onClick={() => onNavigate('signals')} className="text-[11px] font-semibold text-maroon hover:underline">
              View All
            </button>
          }
        >
          <div className="space-y-2" id="dashboard-signals">
            {summary.loading &&
              [0, 1, 2, 3, 4].map((i) => <div key={i} className="h-10 rounded-lg bg-appBg animate-pulse" />)}
            {summary.error && (
              <p className="text-[11.5px] text-[#8C2B2B] bg-[#B33838]/10 border border-[#B33838]/25 rounded-lg p-3">
                Backend unavailable: {summary.error}
              </p>
            )}
            {data?.top_signals.map((s) => (
              <button
                key={s.score_id}
                onClick={() => onOpenSignal(scoreToAnomalyStub(s))}
                className="w-full flex items-center gap-2.5 p-2.5 rounded-lg hover:bg-appBg transition-colors text-left"
              >
                <StatusBadge tone={statusToneOf(s)} dot>{s.severity}</StatusBadge>
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold text-text truncate">{pairLabel(s.pair_id)}</p>
                  <p className="text-[10.5px] text-muted truncate">{s.disposition} · {s.liquidity_status}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[11px] font-bold text-maroon">z {s.robust_z.toFixed(1)}</p>
                  <p className="text-[9.5px] text-muted">{s.observation_date}</p>
                </div>
              </button>
            ))}
            {!summary.loading && !summary.error && data && data.top_signals.length === 0 && (
              <p className="text-[11.5px] text-muted rounded-lg bg-appBg border border-border p-3">
                No scored observations yet. The daily job scores real pair observations after official EOD data lands.
              </p>
            )}
          </div>
        </Panel>

        {/* Contract details */}
        <Panel
          title="Contract Details"
          icon={<Layers size={15} />}
          right={
            <select
              value={compareLeft}
              onChange={(e) => setCompareLeft(e.target.value)}
              className="text-[11.5px] font-semibold bg-appBg border border-border rounded-md px-2 py-1 outline-none"
            >
              {allFour.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          }
        >
          {(() => {
            const inv = contracts.find((c) => c.symbol === compareLeft)
            const spec = inv?.specs[inv.specs.length - 1]
            return (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-extrabold text-text">{compareLeft}</span>
                    <StatusBadge tone={inv?.status === 'NO_DATA' ? 'neutral' : 'amber'} dot>
                      {inv?.status ?? 'NO_DATA'}
                    </StatusBadge>
                  </div>
                  <button onClick={() => onSelectContract(compareLeft)} className="text-[11px] font-semibold text-maroon hover:underline flex items-center gap-0.5">
                    Full profile <ArrowRight size={10} />
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    ['Normalized last', lastLeft != null ? `₹${lastLeft.toFixed(0)}` : '—'],
                    ['Days covered', inv ? String(inv.data_summary.detail_days) : '—'],
                    ['Expiry', inv?.expiry_label ?? '—'],
                    ['Quote basis', spec ? `per ${spec.quote_grams} g` : '—'],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-appBg border border-border rounded-lg px-2 py-1.5 text-center">
                      <p className="text-[9px] text-muted font-semibold uppercase tracking-wide">{k}</p>
                      <p className="text-[12px] font-bold text-text mt-0.5 truncate">{v}</p>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-[10.5px] font-bold text-text mb-1">Price (₹/fine g)</p>
                    <PriceComparisonChart ids={[compareLeft as ContractSymbol]} range={detailRange} height={130} />
                  </div>
                  <div className="text-[11px] space-y-1.5">
                    <p className="text-[10.5px] font-bold text-text mb-1">Contract Information</p>
                    {[
                      ['First date', inv?.data_summary.first_date ?? '—'],
                      ['Last date', inv?.data_summary.last_date ?? '—'],
                      ['Trading unit', spec ? `${spec.trading_unit_grams} g / lot` : '—'],
                      ['Purity', spec ? `${spec.purity_per_mille} / 1000` : '—'],
                      ['Spec status', spec?.verification_status ?? '—'],
                      ['Normalized', lastLeft != null ? `₹${lastLeft.toFixed(0)}/fine g` : '—'],
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
          subtitle="Normalized per fine gram, real observations"
          icon={<GitCompareArrows size={15} />}
          right={
            <button onClick={() => onNavigate('comparison')} className="text-[11px] font-semibold text-maroon hover:underline">
              Full view
            </button>
          }
        >
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-1 rounded-md bg-maroon text-warmwhite text-[10.5px] font-bold">{compareLeft}</span>
              <span className="text-muted text-[11px]">vs</span>
              <span className="px-2.5 py-1 rounded-md bg-appBg border border-border text-[10.5px] font-bold text-text">GOLDTEN</span>
              <span className="ml-auto text-[10px] text-muted">normalized</span>
            </div>
            <PriceComparisonChart ids={[compareLeft as ContractSymbol, 'GOLDTEN']} range={comparisonRange} height={150} />
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="rounded-lg bg-appBg border border-border p-2">
                <p className="text-[9.5px] font-semibold text-muted uppercase">Normalized left</p>
                <p className="text-[12.5px] font-bold text-text mt-0.5">{lastLeft != null ? `₹${lastLeft.toFixed(0)}/g` : 'pending data'}</p>
              </div>
              <div className="rounded-lg bg-appBg border border-border p-2">
                <p className="text-[9.5px] font-semibold text-muted uppercase">Normalized right</p>
                <p className="text-[12.5px] font-bold text-text mt-0.5">{lastRight != null ? `₹${lastRight.toFixed(0)}/g` : 'pending data'}</p>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      {/* Grid row 3: live/newness + insights strip */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,8fr)_minmax(0,10fr)] gap-4">
        <div className="space-y-4">
          <Panel title="Data Freshness" subtitle="From the backend, not the page clock" icon={<RefreshCw size={15} />}>
            <div className="grid grid-cols-2 gap-2 text-[11.5px]">
              <FreshRow label="Pipeline status" value={data?.data_status ?? '—'} />
              <FreshRow label="Latest EOD date" value={data?.data_freshness.latest_activity_trade_date ?? 'None'} />
              <FreshRow label="Last source seen" value={fmtDateTime(data?.data_freshness.last_source_seen ?? null)} />
              <FreshRow label="Market feed" value={stream.connected ? 'streaming' : 'disconnected'} />
            </div>
            <p className="text-[10px] text-muted mt-2">{data?.data_freshness.note ?? 'Loading backend freshness…'}</p>
          </Panel>

          <Panel title="How It Works" subtitle="From official data to validated signals" icon={<ScanSearch size={15} />}>
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
              See how the normality model learns →
            </button>
          </Panel>
        </div>

        <KeySignalsMini
          anomalies={(anomalies.data?.anomalies ?? []).filter((a) => a.is_anomaly)}
          loading={anomalies.loading}
          onOpenSignal={onOpenSignal}
        />
      </div>
    </div>
  )
}

// Dashboard top-signals come as ApiSignal rows; the detail modal needs the anomaly VM shape.
function scoreToAnomalyStub(s: {
  score_id: number
  pair_id: string
  observation_date: string
  status: string
  disposition: string
  severity: string
  robust_z: number
  score: number
  data_status: string
  reason_codes: string[]
}): MlAnomaly {
  return {
    score_id: s.score_id,
    pair_id: s.pair_id,
    observation_date: s.observation_date,
    feature: '',
    observed_value: 0,
    robust_z: s.robust_z,
    score: s.score,
    is_anomaly: s.status !== 'NORMAL',
    severity: s.severity,
    explanation: '',
    warnings: [],
    feature_values: {},
    data_status: s.data_status,
    model_version: null,
    disposition: {
      status: s.status,
      disposition: s.disposition,
      liquidity_status: '',
      expiry_status: '',
      cost_status: '',
      reason_codes: s.reason_codes,
      checks: [],
    },
  }
}

function FreshRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-appBg border border-border px-3 py-2">
      <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{label}</p>
      <p className="text-[12px] font-bold text-text mt-0.5 truncate">{value}</p>
    </div>
  )
}

function statusToneOf(s: {
  status: string
  severity: string
  disposition: string
}): string {
  if (s.disposition === 'ACTIONABLE') return 'green'
  switch (s.severity) {
    case 'High':
      return 'red'
    case 'Watch':
      return 'amber'
    default:
      return 'neutral'
  }
}
