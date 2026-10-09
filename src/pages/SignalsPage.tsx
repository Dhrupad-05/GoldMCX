import { useMemo, useState } from 'react'
import { Search, ArrowUpDown, Inbox } from 'lucide-react'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { Panel } from '../components/Panel'
import { SignalDetailModal } from '../components/SignalDetailModal'
import { SIGNALS } from '../data/signals'
import { pairLabel, filterSignals, withinDays, SIGNAL_TYPES, type SignalFilters as F } from '../lib/filters'
import { fmtZ } from '../lib/demoUtil'
import type { DemoSignal } from '../types'

const STATUSES = ['All', 'High', 'Anomaly', 'Watch', 'Opportunity', 'Normal'] as const

export function SignalsPage({ onOpenSignal }: { onOpenSignal: (s: DemoSignal) => void }) {
  const [status, setStatus] = useState<(typeof STATUSES)[number]>('All')
  const [type, setType] = useState('All')
  const [period, setPeriod] = useState<'7d' | '30d' | 'all'>('all')
  const [query, setQuery] = useState('')
  const [sortAsc, setSortAsc] = useState(false)
  const [detail, setDetail] = useState<DemoSignal | null>(null)

  const filtered = useMemo(() => {
    const f: F = { status, type, period, query }
    const out = filterSignals(SIGNALS, f)
    out.sort((a, b) => (sortAsc ? a.robustZ - b.robustZ : b.robustZ - a.robustZ))
    return out
  }, [status, type, period, query, sortAsc])

  return (
    <div className="space-y-4">
      <Panel
        title="Signals"
        subtitle="Detected unusual cross-contract behaviour — all records illustrative"
        right={<span className="text-[11px] text-muted">{filtered.length} of {SIGNALS.length} signals</span>}
      >
        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-2 pb-3 border-b border-border">
          <div className="flex flex-wrap gap-1">
            {STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${
                  status === s
                    ? 'bg-maroon text-warmwhite border-maroon'
                    : 'bg-card text-muted border-border hover:text-text'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="text-[11px] font-semibold bg-card border border-border rounded-lg px-2 py-1.5 outline-none"
          >
            {SIGNAL_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as '7d' | '30d' | 'all')}
            className="text-[11px] font-semibold bg-card border border-border rounded-lg px-2 py-1.5 outline-none"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All dates</option>
          </select>
          <div className="relative ml-auto">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter signals..."
              className="bg-card border border-border rounded-lg pl-8 pr-3 py-1.5 text-[11.5px] w-48 outline-none focus:ring-2 focus:ring-gold/40"
            />
          </div>
        </div>

        {/* Table */}
        {filtered.length === 0 ? (
          <div className="py-14 text-center">
            <Inbox size={28} className="mx-auto text-muted/50" />
            <p className="text-[13px] font-bold text-text mt-3">No signals match these filters</p>
            <p className="text-[11.5px] text-muted mt-1">Try widening the period or clearing filters.</p>
            <button
              onClick={() => {
                setStatus('All')
                setType('All')
                setPeriod('all')
                setQuery('')
              }}
              className="mt-3 px-3.5 py-1.5 rounded-lg bg-maroon text-warmwhite text-[11.5px] font-semibold"
            >
              Clear all filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto thin-scroll">
            <table className="w-full text-left mt-1">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                  <th className="py-2 pr-3 font-semibold">Date</th>
                  <th className="py-2 pr-3 font-semibold">Signal</th>
                  <th className="py-2 pr-3 font-semibold hidden md:table-cell">Contract pair</th>
                  <th className="py-2 pr-3 font-semibold cursor-pointer select-none" onClick={() => setSortAsc((v) => !v)}>
                    <span className="inline-flex items-center gap-1">Anomaly score <ArrowUpDown size={10} /></span>
                  </th>
                  <th className="py-2 pr-3 font-semibold hidden sm:table-cell">Category</th>
                  <th className="py-2 pr-3 font-semibold">Severity</th>
                  <th className="py-2 font-semibold hidden lg:table-cell">Liquidity</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => setDetail(s)}
                    className="border-b border-border/40 hover:bg-appBg cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 pr-3 text-[11.5px] text-muted whitespace-nowrap">{s.date}</td>
                    <td className="py-2.5 pr-3 text-[12px] font-semibold text-text">{s.title}</td>
                    <td className="py-2.5 pr-3 text-[11.5px] text-muted hidden md:table-cell">{pairLabel(s.pairId)}</td>
                    <td className="py-2.5 pr-3 text-[12px] font-bold text-maroon">{s.score.toFixed(2)} <span className="text-muted font-medium text-[10px]">/ z {fmtZ(s.robustZ)}</span></td>
                    <td className="py-2.5 pr-3 text-[11.5px] text-muted hidden sm:table-cell">{s.type}</td>
                    <td className="py-2.5 pr-3"><StatusBadge tone={statusTone(s.status)} dot>{s.status}</StatusBadge></td>
                    <td className="py-2.5 text-[11.5px] text-muted hidden lg:table-cell">{s.liquidity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Research hint */}
      <p className="text-[11px] text-muted px-1">
        Signals are demo scenarios computed from local data. A high score means unusual relative to the learned normal region — it does not imply a profitable trade.
      </p>

      <SignalDetailModal
        signal={detail}
        onClose={() => setDetail(null)}
      />
    </div>
  )
}

export { withinDays }
