import { useMemo, useState } from 'react'
import { Search, ArrowUpDown, Inbox } from 'lucide-react'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { Panel } from '../components/Panel'
import { SignalDetailModal } from '../components/SignalDetailModal'
import { DataState } from '../components/DataState'
import { api, pairLabel } from '../lib/api'
import type { ApiSignal, SignalDetail } from '../lib/api'
import { useApi } from '../lib/useApi'
import { vmFromAnomaly } from '../lib/signalVM'
import type { SignalVM } from '../lib/signalVM'
import { fmtZ } from '../lib/demoUtil'

const STATUSES = ['All', 'ANOMALOUS', 'NORMAL', 'UNSCORABLE'] as const
const DISPOSITIONS = ['All', 'ACTIONABLE', 'WATCH', 'IGNORE', 'UNSCORABLE'] as const
const PERIODS: Record<string, number | undefined> = { '7d': 7, '30d': 30, all: undefined }

export function SignalsPage({
  onNavigateComparison,
}: {
  onNavigateComparison?: (pairId: string) => void
}) {
  const [status, setStatus] = useState<(typeof STATUSES)[number]>('All')
  const [disposition, setDisposition] = useState<(typeof DISPOSITIONS)[number]>('All')
  const [period, setPeriod] = useState<'7d' | '30d' | 'all'>('all')
  const [query, setQuery] = useState('')
  const [sortAsc, setSortAsc] = useState(false)
  const [detail, setDetail] = useState<SignalVM | null>(null)

  const rows = useApi(
    () => {
      const days = PERIODS[period]
      const date_from =
        days != null
          ? new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)
          : undefined
      return api.signals({
        status: status === 'All' ? undefined : status,
        disposition: disposition === 'All' ? undefined : disposition,
        date_from,
        limit: 200,
      })
    },
    [status, disposition, period],
  )

  const filtered = useMemo(() => {
    const list = (rows.data ?? []).filter((s) =>
      `${s.pair_id} ${s.disposition} ${s.severity}`.toLowerCase().includes(query.toLowerCase()),
    )
    return list.sort((a, b) => (sortAsc ? a.robust_z - b.robust_z : b.robust_z - a.robust_z))
  }, [rows.data, query, sortAsc])

  const openDetail = async (s: ApiSignal) => {
    try {
      const d: SignalDetail = await api.signalDetail(s.id)
      setDetail(
        vmFromAnomaly({
          score_id: s.score_id,
          pair_id: s.pair_id,
          observation_date: s.observation_date,
          feature: '',
          observed_value: d.observed_value,
          robust_z: s.robust_z,
          score: s.score,
          is_anomaly: s.status !== 'NORMAL',
          severity: s.severity,
          explanation: d.explanation,
          warnings: d.warnings,
          feature_values: d.feature_values,
          data_status: s.data_status,
          model_version: null,
          disposition: {
            status: s.status,
            disposition: s.disposition,
            liquidity_status: s.liquidity_status,
            expiry_status: s.expiry_status,
            cost_status: s.cost_status,
            reason_codes: s.reason_codes,
            checks: d.checks,
          },
        }),
      )
    } catch {
      // detail fetch failure still opens the row-level information
      setDetail(vmFromAnomaly(rawAnomalyFallback(s)))
    }
  }

  return (
    <div className="space-y-4">
      <Panel
        title="Signals"
        subtitle="Dispositions of model-scored pair observations"
        right={<span className="text-[11px] text-muted">{filtered.length} of {rows.data?.length ?? 0} records</span>}
      >
        <DataState
          loading={rows.loading}
          error={rows.error}
          retry={rows.refresh}
          skeleton={
            <div className="space-y-2 py-2">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-8 rounded bg-appBg animate-pulse" />
              ))}
            </div>
          }
        />
        {!rows.loading && !rows.error && (
          <>
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
                value={disposition}
                onChange={(e) => setDisposition(e.target.value as (typeof DISPOSITIONS)[number])}
                className="text-[11px] font-semibold bg-card border border-border rounded-lg px-2 py-1.5 outline-none"
              >
                {DISPOSITIONS.map((t) => (
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
                  placeholder="Filter by pair..."
                  className="bg-card border border-border rounded-lg pl-8 pr-3 py-1.5 text-[11.5px] w-48 outline-none focus:ring-2 focus:ring-gold/40"
                />
              </div>
            </div>

            {/* Table */}
            {filtered.length === 0 ? (
              <div className="py-14 text-center">
                <Inbox size={28} className="mx-auto text-muted/50" />
                <p className="text-[13px] font-bold text-text mt-3">
                  {rows.data && rows.data.length > 0 ? 'No signals match these filters' : 'No scored signals in the database yet'}
                </p>
                <p className="text-[11.5px] text-muted mt-1 max-w-md mx-auto leading-relaxed">
                  {rows.data && rows.data.length > 0
                    ? 'Try widening the period or clearing filters.'
                    : 'The daily job scores real pair observations once official EOD history is available; until then this list is empty rather than fabricated.'}
                </p>
                {rows.data && rows.data.length > 0 && (
                  <button
                    onClick={() => {
                      setStatus('All')
                      setDisposition('All')
                      setPeriod('all')
                      setQuery('')
                    }}
                    className="mt-3 px-3.5 py-1.5 rounded-lg bg-maroon text-warmwhite text-[11.5px] font-semibold"
                  >
                    Clear all filters
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto thin-scroll">
                <table className="w-full text-left mt-1">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                      <th className="py-2 pr-3 font-semibold">Date</th>
                      <th className="py-2 pr-3 font-semibold hidden md:table-cell">Contract pair</th>
                      <th className="py-2 pr-3 font-semibold cursor-pointer select-none" onClick={() => setSortAsc((v) => !v)}>
                        <span className="inline-flex items-center gap-1">Robust z <ArrowUpDown size={10} /></span>
                      </th>
                      <th className="py-2 pr-3 font-semibold hidden sm:table-cell">Disposition</th>
                      <th className="py-2 pr-3 font-semibold">Severity</th>
                      <th className="py-2 font-semibold hidden lg:table-cell">Liquidity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((s) => (
                      <tr
                        key={s.id}
                        onClick={() => void openDetail(s)}
                        className="border-b border-border/40 hover:bg-appBg cursor-pointer transition-colors"
                      >
                        <td className="py-2.5 pr-3 text-[11.5px] text-muted whitespace-nowrap">{s.observation_date}</td>
                        <td className="py-2.5 pr-3 text-[12px] font-semibold text-text hidden md:table-cell">{pairLabel(s.pair_id)}</td>
                        <td className="py-2.5 pr-3 text-[12px] font-bold text-maroon">
                          {s.score.toFixed(2)} <span className="text-muted font-medium text-[10px]">/ z {fmtZ(s.robust_z)}</span>
                        </td>
                        <td className="py-2.5 pr-3 text-[11.5px] text-muted hidden sm:table-cell">{s.disposition}</td>
                        <td className="py-2.5 pr-3"><StatusBadge tone={statusTone(s.severity)} dot>{s.severity}</StatusBadge></td>
                        <td className="py-2.5 text-[11.5px] text-muted hidden lg:table-cell">{s.liquidity_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Panel>

      <p className="text-[11px] text-muted px-1">
        Signals are dispositions of real, model-scored observations from the backend. A high score means unusual relative to the learned normal region — it is not a trading recommendation.
      </p>

      <SignalDetailModal
        signal={detail}
        onClose={() => setDetail(null)}
        onNavigateComparison={onNavigateComparison ? (pid) => { setDetail(null); onNavigateComparison(pid) } : undefined}
      />
    </div>
  )
}

function rawAnomalyFallback(s: ApiSignal) {
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
    explanation: '(detail endpoint unavailable)',
    warnings: [],
    feature_values: {},
    data_status: s.data_status,
    model_version: null,
    disposition: {
      status: s.status,
      disposition: s.disposition,
      liquidity_status: s.liquidity_status,
      expiry_status: s.expiry_status,
      cost_status: s.cost_status,
      reason_codes: s.reason_codes,
      checks: [],
    },
  }
}
