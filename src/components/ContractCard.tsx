import { TrendingDown, TrendingUp, ArrowUpRight } from 'lucide-react'
import { fmtINR } from '../lib/demoUtil'
import type { LiveQuote } from '../lib/api'

export function ContractCard({
  symbol,
  quote,
  onOpen,
}: {
  symbol: string
  quote: LiveQuote | null
  onOpen: () => void
}) {
  const price = quote?.last_price ?? null
  // Up/down only when bid/ask exist to compare against; otherwise no change shown
  const up =
    quote?.last_price != null && quote?.bid != null ? quote.last_price >= quote.bid : null

  return (
    <button
      onClick={onOpen}
      className="bg-card border border-border rounded-xl p-3.5 text-left shadow-panel hover:shadow-soft hover:-translate-y-px transition-all group w-full"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] font-extrabold text-text tracking-tight">
            {symbol}
            {quote?.expiry_date && (
              <span className="text-muted font-semibold text-[10px]">
                {` · ${quote.expiry_date}`}
              </span>
            )}
          </p>
          <p
            className={`text-[16px] font-bold mt-1 ${
              price == null ? 'text-muted' : up ? 'text-[#2E6447]' : 'text-[#B33838]'
            }`}
          >
            {price == null ? '—' : fmtINR(price)}
          </p>
          {quote == null ? (
            <p className="text-[10px] text-muted mt-0.5">No verified quote</p>
          ) : price == null ? (
            <p className="text-[10px] text-muted mt-0.5">
              feed stale · {quote.data_status}
            </p>
          ) : (
            up != null && (
              <p
                className={`flex items-center gap-0.5 text-[11px] font-semibold ${
                  up ? 'text-[#2E6447]' : 'text-[#B33838]'
                }`}
              >
                {up ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                {quote.bid != null && quote.ask != null
                  ? `${fmtNum(quote.bid)} / ${fmtNum(quote.ask)}`
                  : (quote.receive_time || '').slice(11, 19)}
              </p>
            )
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {quote?.volume != null && (
            <p className="text-[9.5px] text-muted">
              vol {Number(quote.volume).toLocaleString('en-IN')}
            </p>
          )}
          {quote?.open_interest != null && (
            <p className="text-[9.5px] text-muted">OI {Number(quote.open_interest).toLocaleString('en-IN')}</p>
          )}
          <ArrowUpRight size={12} className="text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </button>
  )
}

function fmtNum(v: number): string {
  return v.toLocaleString('en-IN', { maximumFractionDigits: 0 })
}
