import { useState } from 'react'
import { History, TrendingUp } from 'lucide-react'
import { Panel } from '../components/Panel'
import { Modal } from '../components/Modal'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { HISTORICAL_EVENTS } from '../data/historicalEvents'
import { BACKTEST_SCENARIOS } from '../data/backtestScenarios'
import { pairLabel } from '../lib/filters'
import type { HistoricalEvent } from '../types'

export function EventsBacktestPage() {
  const [tab, setTab] = useState<'events' | 'backtest'>('events')
  const [scenarioId, setScenarioId] = useState(BACKTEST_SCENARIOS[0].id)
  const [detail, setDetail] = useState<HistoricalEvent | null>(null)
  const [severityFilter, setSeverityFilter] = useState('All')

  const sevFiltered = severityFilter === 'All' ? HISTORICAL_EVENTS : HISTORICAL_EVENTS.filter((e) => e.severity === severityFilter)
  const bt = BACKTEST_SCENARIOS.find((s) => s.id === scenarioId)!

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
          title="Historical events / similar observations"
          subtitle="Illustrative records — outcomes are scenario narratives, not verified MCX history"
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
          <div className="overflow-x-auto thin-scroll">
            <table className="w-full text-left">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3">Pair</th>
                  <th className="py-2 pr-3">Category</th>
                  <th className="py-2 pr-3">Severity</th>
                  <th className="py-2 pr-3 hidden md:table-cell">Spread deviation</th>
                  <th className="py-2 pr-3 hidden lg:table-cell">Expiry context</th>
                  <th className="py-2">Outcome (illustrative)</th>
                </tr>
              </thead>
              <tbody>
                {sevFiltered.map((e) => (
                  <tr key={e.id} onClick={() => setDetail(e)} className="border-b border-border/40 hover:bg-appBg cursor-pointer transition-colors">
                    <td className="py-2.5 pr-3 text-[11.5px] text-muted whitespace-nowrap">{e.date}</td>
                    <td className="py-2.5 pr-3 text-[12px] font-semibold text-text">{pairLabel(e.pairId)}</td>
                    <td className="py-2.5 pr-3 text-[11.5px] text-muted">{e.category}</td>
                    <td className="py-2.5 pr-3"><StatusBadge tone={e.severity === 'High' ? 'red' : e.severity === 'Moderate' ? 'amber' : 'neutral'} dot>{e.severity}</StatusBadge></td>
                    <td className="py-2.5 pr-3 text-[11.5px] text-text hidden md:table-cell">{e.spreadDeviationPct.toFixed(2)}%</td>
                    <td className="py-2.5 pr-3 text-[11px] text-muted hidden lg:table-cell">{e.expiryContext}</td>
                    <td className="py-2.5 text-[11.5px] text-muted max-w-xs truncate">{e.outcome}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sevFiltered.length === 0 && (
              <p className="py-10 text-center text-[12px] text-muted">No events with this severity — try another filter.</p>
            )}
          </div>
        </Panel>
      )}

      {tab === 'backtest' && (
        <div className="space-y-4">
          {/* Scenario selector */}
          <Panel title="Backtest & Evaluation" subtitle="Illustrative scenario — not a validated backtest" icon={<TrendingUp size={15} />}>
            <div className="flex flex-wrap gap-2">
              {BACKTEST_SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setScenarioId(s.id)}
                  className={`px-3 py-2 rounded-lg text-[11.5px] font-semibold border transition-colors ${
                    s.id === scenarioId ? 'bg-maroon text-warmwhite border-maroon' : 'bg-card text-muted border-border hover:text-text'
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </Panel>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              ['Gross result', `${bt.grossPct > 0 ? '+' : ''}${bt.grossPct.toFixed(1)}%`, 'before costs'],
              ['Est. transaction costs', `−${bt.txnCostPct.toFixed(1)}%`, 'demo cost assumptions'],
              ['Net result', `${bt.netPct > 0 ? '+' : ''}${bt.netPct.toFixed(1)}%`, 'after demo costs'],
              ['Buy & hold baseline', `${bt.baselinePct > 0 ? '+' : ''}${bt.baselinePct.toFixed(1)}%`, 'same window'],
            ].map(([k, v, sub]) => (
              <div key={k} className="bg-card border border-border rounded-xl p-3.5 shadow-panel">
                <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{k}</p>
                <p className={`text-[18px] font-extrabold mt-1 ${v.startsWith('−') || k === 'Est. transaction costs' ? 'text-[#B33838]' : v.startsWith('+') ? 'text-[#2E6447]' : 'text-text'}`}>{v}</p>
                <p className="text-[10px] text-muted mt-0.5">{sub}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              ['Signals traded', String(bt.trades)],
              ['Win rate', `${bt.winRatePct}%`],
              ['Max drawdown', `${bt.maxDrawdownPct.toFixed(1)}%`],
              ['Avg convergence', `${bt.avgConvergenceDays.toFixed(1)} d`],
              ['Evaluation period', bt.period],
            ].map(([k, v]) => (
              <div key={k} className="bg-card border border-border rounded-xl p-3.5">
                <p className="text-[9.5px] font-semibold uppercase tracking-wide text-muted">{k}</p>
                <p className="text-[14px] font-extrabold text-text mt-1">{v}</p>
              </div>
            ))}
          </div>

          <div className="bg-[#B87928]/10 border border-[#B87928]/30 rounded-xl px-4 py-3 text-[11.5px] text-[#8F5D1D] leading-relaxed">
            <strong>Illustrative scenario — not a validated backtest.</strong> All figures are internally consistent demo numbers derived from the frozen scenario dataset. They are not evidence of profitability, accuracy or real MCX performance. Gross vs net is shown to highlight how transaction costs consume thin spread edges.
          </div>
        </div>
      )}

      {/* Event detail modal */}
      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail ? pairLabel(detail.pairId) : ''} subtitle={detail ? `${detail.date} · ${detail.category} · Illustrative record` : ''}>
        {detail && (
          <div className="space-y-3.5">
            <div className="grid grid-cols-3 gap-2.5">
              {[
                ['Severity', detail.severity],
                ['Spread deviation', `${detail.spreadDeviationPct.toFixed(2)}%`],
                ['Expiry context', detail.expiryContext],
              ].map(([k, v]) => (
                <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                  <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                  <p className="text-[12px] font-bold text-text mt-0.5">{v}</p>
                </div>
              ))}
            </div>
            <div>
              <p className="text-[12px] font-bold text-text mb-1">Subsequent outcome (illustrative)</p>
              <p className="text-[12.5px] text-text leading-relaxed">{detail.outcome}</p>
            </div>
            <div className="bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
              This record is part of the frozen demo dataset. Outcomes are narrative illustrations, not verified market history, and imply no reusable edge.
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
