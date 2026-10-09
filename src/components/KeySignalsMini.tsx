import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { StatusBadge, statusTone } from './StatusBadge'
import { SIGNALS } from '../data/signals'
import type { DemoSignal } from '../types'

export function KeySignalsMini({ onOpenSignal }: { onOpenSignal: (s: DemoSignal) => void }) {
  const top = [...SIGNALS].sort((a, b) => b.score - a.score).slice(0, 3)
  return (
    <div className="bg-card rounded-xl border border-border shadow-panel p-3.5">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[13px] font-bold text-text">Key Signals</p>
        <span className="text-[11px] font-semibold text-maroon hover:underline">View All →</span>
      </div>
      <div className="space-y-2">
        {top.map((s) => (
          <button
            key={s.id}
            onClick={() => onOpenSignal(s)}
            className="w-full flex items-start gap-2.5 p-2 rounded-lg hover:bg-appBg transition-colors text-left"
          >
            <StatusBadge tone={statusTone(s.status)} dot>{s.status}</StatusBadge>
            <div className="min-w-0 flex-1">
              <p className="text-[11.5px] font-bold text-text leading-tight truncate">{pairTitle(s.pairId)}</p>
              <p className="text-[10px] text-muted leading-tight mt-0.5 line-clamp-1">{s.summary}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-[9.5px] text-muted">z-score</p>
              <p className="text-[12px] font-bold text-maroon">{s.robustZ.toFixed(1)}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function pairTitle(pairId: string) {
  return pairId.replace('-', ' ↔ ')
}
