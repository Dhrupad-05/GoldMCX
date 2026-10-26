import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { StatusBadge, statusTone } from './StatusBadge'
import { pairLabel } from '../lib/api'
import type { MlAnomaly } from '../lib/api'

export function KeySignalsMini({
  anomalies,
  loading,
  onOpenSignal,
}: {
  anomalies: MlAnomaly[]
  loading?: boolean
  onOpenSignal: (a: MlAnomaly) => void
}) {
  const top = [...anomalies].sort((a, b) => b.robust_z - a.robust_z).slice(0, 3)

  return (
    <div className="bg-card rounded-xl border border-border shadow-panel p-3.5">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[13px] font-bold text-text">Key Signals</p>
        <span className="text-[11px] font-semibold text-maroon">Model-scored</span>
      </div>
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-10 rounded-lg bg-appBg animate-pulse" />
          ))}
        </div>
      ) : top.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg bg-appBg border border-border px-3 py-2.5">
          <AlertTriangle size={13} className="text-muted shrink-0" />
          <p className="text-[11px] text-muted leading-snug">
            Anomalies will appear here once the daily job has scored real pair observations. No
            real signal yet — nothing is fabricated.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {top.map((s) => (
            <button
              key={s.score_id}
              onClick={() => onOpenSignal(s)}
              className="w-full flex items-start gap-2.5 p-2 rounded-lg hover:bg-appBg transition-colors text-left"
            >
              <StatusBadge tone={s.is_anomaly ? statusTone(s.severity) : 'neutral'} dot>
                {s.is_anomaly ? s.severity : 'Normal'}
              </StatusBadge>
              <div className="min-w-0 flex-1">
                <p className="text-[11.5px] font-bold text-text leading-tight truncate">
                  {pairLabel(s.pair_id)}
                </p>
                <p className="text-[10px] text-muted leading-tight mt-0.5 line-clamp-1">
                  {s.explanation || s.observation_date}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-[9.5px] text-muted">z-score</p>
                <p className="text-[12px] font-bold text-maroon">{s.robust_z.toFixed(1)}</p>
              </div>
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/40">
        <span className="text-[9.5px] text-muted">Data from FastAPI · no demo fallback</span>
        <ArrowUpRight size={10} className="text-muted ml-auto" />
      </div>
    </div>
  )
}
