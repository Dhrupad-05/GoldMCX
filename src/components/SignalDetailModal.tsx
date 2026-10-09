import { Modal } from './Modal'
import { StatusBadge, statusTone } from './StatusBadge'
import { pairLabel } from '../lib/filters'
import { fmtZ } from '../lib/demoUtil'
import type { DemoSignal } from '../types'

export function SignalDetailModal({
  signal,
  onClose,
  onNavigateComparison,
}: {
  signal: DemoSignal | null
  onClose: () => void
  onNavigateComparison?: () => void
}) {
  if (!signal) return null
  return (
    <Modal open={!!signal} onClose={onClose} title={signal.title} subtitle={`${pairLabel(signal.pairId)} · ${signal.date} · ${signal.type} signal`}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={statusTone(signal.status)} dot>{signal.status}</StatusBadge>
          <span className="text-[11px] text-muted">Illustrative demo signal — not a live MCX finding</span>
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
            <p className="text-[10px] uppercase tracking-wide text-muted font-semibold">Days to expiry</p>
            <p className="text-lg font-bold text-text mt-0.5">{signal.daysToExpiry}</p>
          </div>
        </div>

        <p className="text-[13px] text-text leading-relaxed">{signal.summary}</p>

        <div>
          <h4 className="text-[12px] font-bold text-text mb-1.5">Why it was flagged</h4>
          <ul className="space-y-1.5">
            {signal.reasons.map((r, i) => (
              <li key={i} className="flex gap-2 text-[12.5px] text-muted leading-relaxed">
                <span className="w-1.5 h-1.5 rounded-full bg-gold mt-1.5 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </div>

        {signal.expiryNote && (
          <div className="bg-[#B87928]/10 border border-[#B87928]/25 rounded-lg p-3 text-[12px] text-[#8F5D1D] leading-relaxed">
            <strong className="font-semibold">Expiry context:</strong> {signal.expiryNote}
          </div>
        )}

        <div className={`border rounded-lg p-3 text-[12px] leading-relaxed ${
          signal.liquidity === 'Low' ? 'bg-[#B33838]/10 border-[#B33838]/25 text-[#8C2B2B]'
          : signal.liquidity === 'Adequate' ? 'bg-[#B87928]/10 border-[#B87928]/25 text-[#8F5D1D]'
          : 'bg-[#3F8061]/10 border-[#3F8061]/25 text-[#2E6447]'
        }`}>
          <strong className="font-semibold">Liquidity:</strong>{' '}
          {signal.liquidity === 'Low'
            ? 'Thin book on at least one leg — execution in a realistic scenario would face slippage.'
            : signal.liquidity === 'Adequate'
            ? 'Adequate depth — sizing in a real scenario would be limited.'
            : 'Healthy liquidity on both legs in this scenario.'}
        </div>

        <div className="bg-appBg rounded-lg border border-border p-3 text-[11px] text-muted leading-relaxed">
          <strong className="text-text">What this does not imply:</strong> an anomaly score measures deviation from the learned normal region only. It is not evidence of mispricing, profitability, or a recommendation to trade.
        </div>

        {onNavigateComparison && (
          <button
            onClick={onNavigateComparison}
            className="w-full bg-maroon hover:bg-deep text-warmwhite text-[12.5px] font-semibold py-2.5 rounded-lg transition-colors"
          >
            Open this pair in Comparison
          </button>
        )}
      </div>
    </Modal>
  )
}
