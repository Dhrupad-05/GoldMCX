import { TrendingDown, TrendingUp, ArrowUpRight } from 'lucide-react'
import { Sparkline } from './Sparkline'
import { priceSeriesFor } from './priceSeriesFor'
import { fmtINR, fmtPct } from '../lib/demoUtil'
import { CONTRACT_MAP } from '../data/contracts'
import type { ContractId } from '../types'

export function ContractCard({
  contractId,
  onClick,
}: {
  contractId: ContractId
  onClick: (id: ContractId) => void
}) {
  const c = CONTRACT_MAP[contractId]
  const pts = priceSeriesFor(contractId)
  const recent = pts.slice(-14).map((p) => p.value)
  const up = c.demoChangePct >= 0
  return (
    <button
      onClick={() => onClick(contractId)}
      className="bg-card border border-border rounded-xl p-3.5 text-left shadow-panel hover:shadow-soft hover:-translate-y-px transition-all group w-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] font-extrabold text-text tracking-tight">{c.symbol} <span className="text-muted font-semibold text-[10px]">{c.expiryLabel}</span></p>
          <p className={`text-[16px] font-bold mt-1 ${up ? 'text-[#2E6447]' : 'text-[#B33838]'}`}>{fmtINR(c.demoPrice)}</p>
          <p className={`flex items-center gap-0.5 text-[11px] font-semibold ${up ? 'text-[#2E6447]' : 'text-[#B33838]'}`}>
            {up ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {fmtPct(c.demoChangePct)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Sparkline points={recent} color={up ? '#3F8061' : '#B33838'} />
          <ArrowUpRight size={12} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </button>
  )
}
