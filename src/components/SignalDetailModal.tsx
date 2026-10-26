import { Modal } from './Modal'
import { StatusBadge, statusTone } from './StatusBadge'
import { pairLabel } from '../lib/api'
import { fmtZ } from '../lib/demoUtil'
import { vmTitle } from '../lib/signalVM'
import type { SignalVM } from '../lib/signalVM'

export function SignalDetailModal({
  signal,
  onClose,
  onNavigateComparison,
}: {
  signal: SignalVM | null
  onClose: () => void
  onNavigateComparison?: (pairId: string) => void
}) {
  if (!signal) return null
  const featureEntries = Object.entries(signal.featureValues)

  return (
    <Modal open={!!signal} onClose={onClose} title={vmTitle(signal)} subtitle={`score record #${signal.scoreId} · ${signal.dataStatus}`}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {signal.isAnomaly ? (
            <StatusBadge tone={statusTone(signal.severity)} dot>{signal.status}</StatusBadge>
          ) : (
            <StatusBadge tone="green" dot>Normal</StatusBadge>
          )}
          <StatusBadge tone="neutral">{signal.disposition}</StatusBadge>
          {signal.modelVersion && <StatusBadge tone="gold">{signal.modelVersion}</StatusBadge>}
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="bg-appBg rounded-lg border border-border p-3 text-center">
            <p className="text-[10px] uppercase tracking-wide text-muted font-semibold">Anomaly score</p>
            <p className="text-lg font-bold text-maroon mt-0.5">{signal.score.toFixed(2)}</p>
          </div>
          <div className="bg-appBg rounded-lg border border-border p-3 text-center">
            <p className="text-[10px] uppercase tracking-wide text-muted font-semibold">Robust z</p>
            <p className="text-lg font-bold text-text mt-0.5">{fmtZ(signal.robustZ)}</p>
          </div>
          <div className="bg-appBg rounded-lg border border-border p-3 text-center">
            <p className="text-[10px] uppercase tracking-wide text-muted font-semibold">Observation</p>
            <p className="text-lg font-bold text-text mt-0.5 truncate">{signal.observedValue}</p>
          </div>
        </div>

        {signal.explanation && (
          <p className="text-[13px] text-text leading-relaxed">{signal.explanation}</p>
        )}

        {featureEntries.length > 0 && (
          <div>
            <h4 className="text-[12px] font-bold text-text mb-1.5">Feature values (as scored)</h4>
            <div className="overflow-x-auto thin-scroll">
              <table className="w-full text-left">
                <tbody>
                  {featureEntries.map(([k, v]) => (
                    <tr key={k} className="border-b border-border/40">
                      <td className="py-1.5 pr-3 text-[11.5px] text-muted">{k}</td>
                      <td className="py-1.5 text-[12px] font-semibold text-text text-right">
                        {typeof v === 'number' ? v.toFixed(4) : String(v)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {signal.reasonCodes.length > 0 && (
          <div>
            <h4 className="text-[12px] font-bold text-text mb-1.5">Reason codes</h4>
            <div className="flex flex-wrap gap-1.5">
              {signal.reasonCodes.map((r) => (
                <span key={r} className="px-2 py-1 rounded-md bg-appBg border border-border text-[10.5px] font-semibold text-muted">{r}</span>
              ))}
            </div>
          </div>
        )}

        {signal.checks.length > 0 && (
          <div>
            <h4 className="text-[12px] font-bold text-text mb-1.5">Execution-quality checks</h4>
            <ul className="space-y-1.5">
              {signal.checks.map((c) => (
                <li key={c.name} className="flex gap-2 text-[12.5px] text-muted leading-relaxed">
                  <span className="w-1.5 h-1.5 rounded-full bg-gold mt-1.5 shrink-0" />
                  <span><strong className="text-text font-semibold">{c.name}</strong>: {c.status}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {signal.warnings.length > 0 && (
          <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-lg p-3 text-[12px] text-[#8F5D1D] leading-relaxed">
            <strong className="font-semibold">Data warnings:</strong> {signal.warnings.join('; ')}
          </div>
        )}

        <div className="bg-appBg rounded-lg border border-border p-3 text-[11px] text-muted leading-relaxed">
          <strong className="text-text">What this does not imply:</strong> an anomaly score measures deviation from the learned normal region only. It is a statistical novelty of the pair relationship, not evidence of mispricing, profitability, or a recommendation to trade.
        </div>

        {onNavigateComparison && (
          <button
            onClick={() => onNavigateComparison(signal.pairId)}
            className="w-full bg-maroon hover:bg-deep text-warmwhite text-[12.5px] font-semibold py-2.5 rounded-lg transition-colors"
          >
            Open this pair in Comparison
          </button>
        )}
      </div>
    </Modal>
  )
}
