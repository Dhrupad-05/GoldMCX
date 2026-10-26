import { useState } from 'react'
import { History, TrendingUp } from 'lucide-react'
import { Panel } from '../components/Panel'
import { Modal } from '../components/Modal'
import { StatusBadge } from '../components/StatusBadge'
import { DataState } from '../components/DataState'
import { api, pairLabel as canonicalLabel } from '../lib/api'
import type { ApiEvent, BacktestRunResponse } from '../lib/api'
import { useApi } from '../lib/useApi'

export function EventsBacktestPage() {
  const [tab, setTab] = useState<'events' | 'backtest'>('events')
  const [detail, setDetail] = useState<ApiEvent | null>(null)
  const [severityFilter, setSeverityFilter] = useState('All')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const events = useApi(() => api.events({}), [])
  const runs = useApi(() => api.backtestRuns(), [])

  const sevFiltered =
    severityFilter === 'All'
      ? events.data?.events ?? []
      : (events.data?.events ?? []).filter((e) => e.severity.toLowerCase().startsWith(severityFilter.toLowerCase()))

  const runId = selectedRunId ?? runs.data?.[0]?.id ?? null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 border-b border-border px-1">
        {([['events', 'Historical Events'], ['backtest', 'Backtest & Evaluation']] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2.5 text-[12.5px] font-semibold border-b-2 -mb-px transition-colors ${
              tab === id ? 'border-maroon text-maroon' : 'border-transparent text-muted hover:text-text'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'events' && (
        <Panel
          title="Historical events / verified recorded events"
          subtitle="Stored by the backend with source document lineage"
          icon={<History size={15} />}
          right={
            <div className="flex gap-1">
              {['All', 'High', 'Moderate', 'Low'].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${
                    severityFilter === s ? 'bg-maroon text-warmwhite border-maroon' : 'bg-card text-muted border-border'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          }
        >
          <DataState
            loading={events.loading}
            error={events.error}
            retry={events.refresh}
            empty={
              !events.loading && !events.error && sevFiltered.length === 0
                ? 'No verified event records are stored yet. Events appear once the event corpus is ingested through the backend.'
                : undefined
            }
          />
          {sevFiltered.length > 0 && (
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">Pair</th>
                    <th className="py-2 pr-3">Category</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2 pr-3 hidden md:table-cell">Source Doc</th>
                    <th className="py-2">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {sevFiltered.map((e) => (
                    <tr key={e.id} onClick={() => setDetail(e)} className="border-b border-border/40 hover:bg-appBg cursor-pointer transition-colors">
                      <td className="py-2.5 pr-3 text-[11.5px] text-muted whitespace-nowrap">{e.date}</td>
                      <td className="py-2.5 pr-3 text-[12px] font-semibold text-text">{e.pair_id ? canonicalLabel(e.pair_id) : 'corpus-wide'}</td>
                      <td className="py-2.5 pr-3 text-[11.5px] text-muted">{e.category}</td>
                      <td className="py-2.5 pr-3"><StatusBadge tone={e.severity === 'High' ? 'red' : e.severity === 'Moderate' ? 'amber' : 'neutral'} dot>{e.severity}</StatusBadge></td>
                      <td className="py-2.5 pr-3 text-[11px] text-muted hidden md:table-cell">{e.source_document}</td>
                      <td className="py-2.5 text-[11.5px] text-muted max-w-xs truncate">{e.title} — {e.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      {tab === 'backtest' && (
        <div className="space-y-4">
          <Panel title="Walk-forward backtest runs" subtitle="Executed by the backend on expiry-dated verified bars" icon={<TrendingUp size={15} />}>
            <DataState
              loading={runs.loading}
              error={runs.error}
              retry={runs.refresh}
              empty={
                !runs.loading && !runs.error && (runs.data?.length ?? 0) === 0
                  ? 'No backtest runs exist yet. A run is computed server-side only over expiry-dated, verified bars — nothing is simulated in the browser.'
                  : undefined
              }
            />
            {/* Run form */}
            <RunForm
              submitting={submitting}
              error={formError}
              onSubmit={async (pair_id, start, end) => {
                setSubmitting(true)
                setFormError(null)
                try {
                  const idem = crypto.randomUUID()
                  const res = await api.runBacktest({ pair_id, start, end }, idem)
                  setRunResult(res)
                  void runs.refresh()
                  setSelectedRunId(res.run.id)
                } catch (e) {
                  setFormError(e instanceof Error ? e.message : String(e))
                } finally {
                  setSubmitting(false)
                }
              }}
            />
            {(runs.data?.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-2">
                {runs.data!.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => setSelectedRunId(r.id)}
                    className={`px-3 py-2 rounded-lg text-[11.5px] font-semibold border transition-colors ${
                      r.id === runId ? 'bg-maroon text-warmwhite border-maroon' : 'bg-card text-muted border-border hover:text-text'
                    }`}
                  >
                    {canonicalLabel(r.pair_id)} · {r.start_date ?? '?'} → {r.end_date ?? '?'} · {r.status}
                  </button>
                ))}
              </div>
            )}
          </Panel>

          {runResult && (
            <BacktestResult res={runResult} />
          )}

          <div className="bg-[#B87928]/10 border border-[#B87928]/30 rounded-xl px-4 py-3 text-[11.5px] text-[#8F5D1D] leading-relaxed">
            <strong>Method:</strong> results come from backend-computed walk-forward runs on real, expiry-dated observations with configurable cost assumptions. Transient/provisional data is explicitly labelled. A single backtest is not proof of an edge — costs and slippage matter on thin spread structures.
          </div>
        </div>
      )}

      {/* Event detail modal */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail ? `${detail.date} · ${detail.category}` : ''} subtitle={detail ? `${detail.source_document} · ${detail.data_status}` : ''}>
        {detail && (
          <div className="space-y-3.5">
            <div className="grid grid-cols-3 gap-2.5">
              {[
                ['Severity', detail.severity],
                ['Verdict', detail.title],
                ['Record ID', detail.id],
              ].map(([k, v]) => (
                <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                  <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                  <p className="text-[12px] font-bold text-text mt-0.5">{v}</p>
                </div>
              ))}
            </div>
            <div>
              <p className="text-[12px] font-bold text-text mb-1">Description</p>
              <p className="text-[12.5px] text-text leading-relaxed">{detail.description}</p>
            </div>
            {detail.pair_id && (
              <p className="text-[11.5px] text-muted">Pair: {canonicalLabel(detail.pair_id)}</p>
            )}
            <div className="bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
              Stored record from the backend (`/api/v1/events`), with source-document lineage and data-status labelling.
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function RunForm({
  submitting,
  error,
  onSubmit,
}: {
  submitting: boolean
  error: string | null
  onSubmit: (pairId: string, start: string, end: string) => void
}) {
  const [pair, setPair] = useState('GOLDM-GOLDTEN')
  const today = new Date().toISOString().slice(0, 10)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState(today)
  return (
    <div className="bg-appBg border border-border rounded-xl p-3 mt-3">
      <p className="text-[12px] font-bold text-text mb-2">Request a server-side walk-forward run</p>
      <div className="flex flex-wrap items-center gap-2">
        <select value={pair} onChange={(e) => setPair(e.target.value)} className="bg-card border border-border rounded-lg px-2.5 py-1.5 text-[11.5px] font-semibold text-maroon outline-none">
          {['GOLDM-GOLDTEN', 'GOLDM-GOLDGUINEA', 'GOLDM-GOLDPETAL', 'GOLDTEN-GOLDGUINEA', 'GOLDTEN-GOLDPETAL', 'GOLDGUINEA-GOLDPETAL'].map((p) => (
            <option key={p} value={p}>{canonicalLabel(p)}</option>
          ))}
        </select>
        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="bg-card border border-border rounded-lg px-2 py-1.5 text-[11.5px] outline-none" placeholder="start (optional)" />
        <span className="text-[11px] text-muted">→</span>
        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="bg-card border border-border rounded-lg px-2 py-1.5 text-[11.5px] outline-none" />
        <button
          disabled={submitting || !start || !end}
          onClick={() => void onSubmit(pair, start, end)}
          className="px-3 py-1.5 rounded-lg bg-maroon text-warmwhite text-[11.5px] font-semibold disabled:opacity-50"
        >
          {submitting ? 'Running…' : 'Run on server'}
        </button>
      </div>
      {error && <p className="mt-2 text-[11.5px] text-[#8C2B2B]">Run failed: {error}</p>}
    </div>
  )
}

function BacktestResult({ res }: { res: BacktestRunResponse }) {
  const fmtCell = (name: string, v: number, units: string) => {
    const signed = v > 0 ? '+' : ''
    return name.includes('pct') || units === '%' ? `${signed}${v.toFixed(2)}%` : `${signed}${v.toFixed(2)}`;
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {res.metrics.slice(0, 4).map((m) => (
          <div key={m.metric_name} className="bg-card border border-border rounded-xl p-3.5 shadow-panel">
            <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{m.metric_name}</p>
            <p className="text-[18px] font-extrabold text-text mt-1">{fmtCell(m.metric_name, m.metric_value, m.units)}</p>
            <p className="text-[10px] text-muted mt-0.5">{m.units}</p>
          </div>
        ))}
      </div>
      {(res.metrics.length ?? 0) > 4 && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {res.metrics.slice(4, 9).map((m) => (
            <div key={m.metric_name} className="bg-card border border-border rounded-xl p-3.5">
              <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{m.metric_name}</p>
              <p className="text-[14px] font-extrabold text-text mt-1">{fmtCell(m.metric_name, m.metric_value, m.units)}</p>
            </div>
          ))}
        </div>
      )}
      <div className="bg-appBg border border-border rounded-xl p-3 text-[11px] text-muted leading-relaxed">
        <p><strong className="text-text">Run:</strong> {res.run.id}</p>
        <p className="mt-1"><strong className="text-text">Data window:</strong> {res.run.start_date ?? '—'} → {res.run.end_date ?? '—'} · status {res.run.data_status}</p>
        <p className="mt-1"><strong className="text-text">Costs:</strong> {JSON.stringify(res.run.costs ?? {})}</p>
        <p className="mt-1">{res.disclaimer}</p>
      </div>
      {res.run.data_status !== 'verified' && (
        <div className="bg-[#B87928]/10 border border-[#B87928]/30 rounded-xl px-4 py-3 text-[11.5px] text-[#8F5D1D]">
          This run scored provisional data ({res.run.data_status}); treat results as unscorable-only until verified bars cover the full window.
        </div>
      )}
    </div>
  )
}

