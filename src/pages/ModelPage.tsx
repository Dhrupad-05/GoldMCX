import { useMemo, useState } from 'react'
import {
  BrainCircuit,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ShieldCheck,
  History as HistoryIcon,
  Scale,
  RefreshCw,
} from 'lucide-react'
import { Panel } from '../components/Panel'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { DataState } from '../components/DataState'
import { api, pairLabel } from '../lib/api'
import type { MlAnomaly } from '../lib/api'
import { useApi } from '../lib/useApi'
import { fmtZ } from '../lib/demoUtil'

const CANONICAL_PAIRS = [
  'GOLDM-GOLDTEN',
  'GOLDM-GOLDGUINEA',
  'GOLDM-GOLDPETAL',
  'GOLDTEN-GOLDGUINEA',
  'GOLDTEN-GOLDPETAL',
  'GOLDGUINEA-GOLDPETAL',
]

export function ModelPage() {
  const [pairId, setPairId] = useState('GOLDM-GOLDTEN')
  const status = useApi(() => api.mlStatus('daily'), [])
  const runs = useApi(() => api.mlJobRuns(), [])
  const anomalies = useApi(() => api.latestAnomalies(pairId, 40), [pairId])
  const [adminMsg, setAdminMsg] = useState<string | null>(null)

  const anomaliesForPair = useMemo(
    () => (anomalies.data?.anomalies ?? []),
    [anomalies.data],
  )

  const queueRetrain = async () => {
    const token = window.prompt('Administrator token (x-admin-token) — required to queue a server-side retrain job:')
    if (!token) return
    try {
      await api.triggerDailyJob(token)
      setAdminMsg('Retrain/daily job queued server-side. Check the jobs table below for status.')
      void runs.refresh()
    } catch (e) {
      setAdminMsg(`Job could not be queued: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const s = status.data

  return (
    <div className="space-y-4">
      {/* Header strip */}
      <div className="bg-card border border-border rounded-xl p-4 flex flex-wrap items-center gap-3 shadow-panel">
        <span className="w-9 h-9 rounded-lg bg-maroon text-warmwhite flex items-center justify-center"><BrainCircuit size={17} /></span>
        <div className="min-w-0">
          <h2 className="text-[15px] font-extrabold text-text" style={{ fontFamily: 'Georgia, serif' }}>Model Registry</h2>
          <p className="text-[11.5px] text-muted">Active artifact, readiness and scored observations — served by FastAPI, never trained in the browser.</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={pairId}
            onChange={(e) => setPairId(e.target.value)}
            className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
          >
            {CANONICAL_PAIRS.map((p) => (
              <option key={p} value={p}>{pairLabel(p)}</option>
            ))}
          </select>
          <button
            onClick={() => void queueRetrain()}
            className="flex items-center gap-1.5 bg-maroon hover:bg-deep text-warmwhite font-bold text-[11.5px] px-3 py-2 rounded-lg"
          >
            <RefreshCw size={12} /> Queue retrain (admin)
          </button>
        </div>
      </div>
      {adminMsg && (
        <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-xl px-4 py-2.5 text-[12px] text-[#8F5D1D]">
          {adminMsg}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* 1. Model status */}
        <Panel title="Active daily model" subtitle="Registered via the backend model registry" icon={<ShieldCheck size={15} />}>
          <DataState loading={status.loading} error={status.error} retry={status.refresh} />
          {s && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                {[
                  ['Status', s.status],
                  ['Model version', s.model_version ?? 'none'],
                  ['Mode', s.mode],
                ].map(([k, v]) => (
                  <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                    <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                    <p className="text-[12.5px] font-extrabold text-text mt-0.5 truncate">{v}</p>
                  </div>
                ))}
              </div>
              {s.status !== 'READY' && (
                <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-lg p-3 text-[11.5px] text-[#8F5D1D] leading-relaxed">
                  <p className="flex items-start gap-1.5 font-bold"><Info size={13} className="mt-0.5 shrink-0" /> ML_MODEL_NOT_READY</p>
                  <p className="mt-1">{s.notes}</p>
                  <p className="mt-1">Run <code className="text-[10.5px] bg-white/60 px-1 rounded">python -m ml.train_model --sync-history --mode all</code> from the backend environment once verified history is stored.</p>
                </div>
              )}
              {s.status === 'READY' && (
                <div className="bg-appBg border border-border rounded-lg p-3 text-[11.5px] leading-relaxed">
                  <p><strong>Algorithm:</strong> {s.algorithm}</p>
                  <p className="mt-1 text-muted">
                    <strong>Features ({s.feature_names?.length ?? 0}):</strong>{' '}
                    {s.feature_names?.slice(0, 8).join(', ')}
                    {(s.feature_names?.length ?? 0) > 8 ? ', …' : ''}
                  </p>
                  {s.artifact_sha256 && (
                    <p className="mt-1 text-muted break-all">SHA-256: {s.artifact_sha256.slice(0, 24)}…</p>
                  )}
                </div>
              )}
            </div>
          )}
        </Panel>

        {/* 2. Registry history */}
        <Panel title="Registry history" subtitle="candidate → active → retired lifecycle" icon={<HistoryIcon size={15} />}>
          <DataState loading={status.loading} error={status.error} retry={status.refresh} />
          {s && (s.registry?.length > 0 ? (
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-left mt-1">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                    <th className="py-2 pr-3">Version</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2 pr-3 hidden sm:table-cell">Algorithm</th>
                    <th className="py-2">Activated</th>
                  </tr>
                </thead>
                <tbody>
                  {s.registry.map((r) => (
                    <tr key={r.model_version} className="border-b border-border/40">
                      <td className="py-2 pr-3 text-[12px] font-semibold text-text">{r.model_version}</td>
                      <td className="py-2 pr-3"><StatusBadge tone={r.status === 'active' ? 'green' : r.status === 'failed' ? 'red' : 'neutral'} dot>{r.status}</StatusBadge></td>
                      <td className="py-2 pr-3 text-[11.5px] text-muted hidden sm:table-cell">{r.algorithm}</td>
                      <td className="py-2 text-[11.5px] text-muted">{r.activated_at ? r.activated_at.slice(0, 10) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[12px] text-muted py-6 text-center">
              No artifacts registered yet. The registry fills after the first successful training run.
            </p>
          ))}
        </Panel>
      </div>

      {/* 3. Scored observations */}
      <Panel
        title={`Scored observations — ${pairLabel(pairId)}`}
        subtitle="Real feature scores persisted by the daily job"
        icon={<Scale size={15} />}
      >
        <DataState loading={anomalies.loading} error={anomalies.error} retry={anomalies.refresh} />
        {!anomalies.loading && !anomalies.error && (anomaliesForPair.length === 0 ? (
          <div className="py-10 text-center">
            <BrainCircuit size={30} className="mx-auto text-muted/40" />
            <p className="text-[13px] font-bold text-text mt-3">No scored observations for this pair yet</p>
            <p className="text-[11.5px] text-muted mt-1 max-w-md mx-auto leading-relaxed">
              The daily job scores real pair observations after official EOD data is ingested. The browser never fabricates training or scoring.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)] gap-5">
            <ScoreSpace
              scores={anomaliesForPair.map((a) => a.robust_z)}
              thresholds={{ normal: 2.5, anomaly: 3.5 }}
              latest={anomaliesForPair[0]}
            />
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-left">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">z</th>
                    <th className="py-2 pr-3">Severity</th>
                    <th className="py-2">Disposition</th>
                  </tr>
                </thead>
                <tbody>
                  {anomaliesForPair.slice(0, 12).map((a) => (
                    <tr key={a.score_id} className="border-b border-border/40">
                      <td className="py-2 pr-3 text-[11.5px] text-muted">{a.observation_date}</td>
                      <td className="py-2 pr-3 text-[12px] font-bold text-maroon">{fmtZ(a.robust_z)}</td>
                      <td className="py-2 pr-3"><StatusBadge tone={a.is_anomaly ? statusTone(a.severity) : 'green'} dot>{a.is_anomaly ? a.severity : 'Normal'}</StatusBadge></td>
                      <td className="py-2 text-[11.5px] text-muted">{a.disposition?.disposition ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </Panel>

      {/* 4. Job runs */}
      <Panel title="Job runs (sync → features → scoring)" subtitle="Durable run records from the scheduled daily workflow" icon={<HistoryIcon size={15} />}>
        <DataState loading={runs.loading} error={runs.error} retry={runs.refresh} />
        {!runs.loading && !runs.error && ((runs.data?.runs?.length ?? 0) > 0 ? (
          <div className="overflow-x-auto thin-scroll">
            <table className="w-full text-left mt-1">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                  <th className="py-2 pr-3">Run</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Started</th>
                  <th className="py-2 hidden sm:table-cell">Summary</th>
                </tr>
              </thead>
              <tbody>
                {runs.data!.runs.slice(0, 10).map((r) => (
                  <tr key={r.run_id} className="border-b border-border/40">
                    <td className="py-2 pr-3 text-[11px] font-mono text-muted">{r.run_id.slice(0, 8)}</td>
                    <td className="py-2 pr-3"><StatusBadge tone={r.status === 'succeeded' ? 'green' : r.status === 'running' ? 'amber' : 'red'} dot>{r.status}</StatusBadge></td>
                    <td className="py-2 pr-3 text-[11.5px] text-muted">{r.started_at.slice(0, 16).replace('T', ' ')}</td>
                    <td className="py-2 text-[10.5px] text-muted truncate max-w-[280px]">
                      {r.errors.length > 0 ? r.errors[0] : JSON.stringify(r.summary).slice(0, 90)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[12px] text-muted py-6 text-center">No job runs recorded yet. The first EOD sync will register one.</p>
        ))}
      </Panel>

      <div className="bg-[#B87928]/8 border border-[#B87928]/25 rounded-xl p-3.5 text-[11.5px] text-[#8F5D1D] leading-relaxed">
        <p className="flex items-start gap-1.5 font-bold"><AlertTriangle size={13} className="mt-0.5 shrink-0" /> What a score does and does not mean</p>
        <p className="mt-1.5">
          Anomaly scores measure deviation from the learned normal region for contract-aware relative-value features. They are not probability of profit and not a trading recommendation. Dispositions apply liquidity, expiry and cost checks before anything is presented as actionable.
        </p>
      </div>
    </div>
  )
}

/** Feature-space visual driven by real persisted scores for the pair. */
function ScoreSpace({
  scores,
  thresholds,
  latest,
}: {
  scores: number[]
  thresholds: { normal: number; anomaly: number }
  latest: MlAnomaly | null
}) {
  const checkOk = latest ? Math.abs(latest.robust_z) < thresholds.anomaly : true
  return (
    <div className="bg-warmwhite border border-border rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        {checkOk ? <CheckCircle2 size={15} className="text-[#2E6447]" /> : <XCircle size={15} className="text-[#B33838]" />}
        <p className="text-[12.5px] font-bold text-text">
          {latest ? `Latest: z ${fmtZ(latest.robust_z)} on ${latest.observation_date}` : 'No observations'}
        </p>
        <StatusBadge tone={latest?.is_anomaly ? statusTone(latest.severity) : 'green'} dot>
          {latest?.is_anomaly ? latest.severity : 'Normal'}
        </StatusBadge>
      </div>
      <div className="space-y-1 h-32 overflow-y-auto thin-scroll pr-1">
        {scores.map((z, i) => {
          const anom = Math.abs(z) >= thresholds.anomaly
          const watch = !anom && Math.abs(z) >= thresholds.normal
          return (
            <div key={i} className="flex items-center gap-2">
              <div className="h-2 rounded-full flex-1 bg-appBg border border-border/50 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(100, (Math.abs(z) / 6) * 100)}%`,
                    background: anom ? '#B33838' : watch ? '#B87928' : '#3F8061',
                  }}
                />
              </div>
              <span className="text-[9.5px] text-muted w-10 text-right font-mono">{z.toFixed(2)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
