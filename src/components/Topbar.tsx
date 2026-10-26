import { useState, useMemo, useRef, useEffect } from 'react'
import { Search, Bell, CircleUser, Command, X } from 'lucide-react'
import type { MarketStreamState } from '../lib/useMarketStream'
import type { ContractSymbol, ViewId } from '../lib/api'

interface TopItem {
  id: string
  label: string
  kind: 'Contract' | 'Section'
  target: string
}

const SECTIONS: TopItem[] = [
  { id: 'nav-signals', label: 'Signals', kind: 'Section', target: 'signals' },
  { id: 'nav-comparison', label: 'Comparison', kind: 'Section', target: 'comparison' },
  { id: 'nav-model', label: 'Model Registry', kind: 'Section', target: 'model' },
  { id: 'nav-backtest', label: 'Events & Backtest', kind: 'Section', target: 'backtest' },
  { id: 'nav-insights', label: 'Insights', kind: 'Section', target: 'insights' },
  { id: 'nav-learn', label: 'Learn', kind: 'Section', target: 'learn' },
]

const CONTRACT_NAMES: Record<ContractSymbol, string> = {
  GOLDM: 'Gold (1 kg)',
  GOLDTEN: 'Gold Mini (100 g)',
  GOLDGUINEA: 'Gold Guinea (8 g)',
  GOLDPETAL: 'Gold Petal (1 g)',
}

export function Topbar({
  query,
  onQueryChange,
  onNavigate,
  onSelectContract,
  stream,
}: {
  query: string
  onQueryChange: (q: string) => void
  onNavigate: (v: ViewId) => void
  onSelectContract: (id: string) => void
  stream: MarketStreamState
}) {
  const [showNotif, setShowNotif] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotif(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const results = useMemo<TopItem[]>(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    const contracts: TopItem[] = (Object.keys(CONTRACT_NAMES) as ContractSymbol[])
      .filter((c) => `${c} ${CONTRACT_NAMES[c]}`.toLowerCase().includes(q))
      .map((c) => ({ id: `sym-${c}`, label: `${c} — ${CONTRACT_NAMES[c]}`, kind: 'Contract' as const, target: c }))
    const sections = SECTIONS.filter((s) => s.label.toLowerCase().includes(q))
    return [...contracts, ...sections]
  }, [query])

  // Feed-state label: only ever "Live" with a fresh quote stream.
  const feedState = stream.status?.state ?? 'NOT_CONFIGURED'
  const freshQuotes = useMemo(() => {
    void stream.eventTime
    return [...stream.quotes.values()].filter((q) => {
      if (q.last_price == null) return false
      const t = Date.parse(q.event_time)
      return Number.isFinite(t) && Date.now() - t < 120_000
    }).length
  }, [stream])
  const isLive = stream.connected && freshQuotes > 0
  const statusLine = !stream.connected
    ? stream.error ?? 'Stream disconnected'
    : isLive
      ? `${feedState} · ${freshQuotes} fresh quote${freshQuotes === 1 ? '' : 's'}`
      : `SSE connected · no fresh quotes (${feedState})`

  return (
    <header className="relative z-20 flex items-center gap-4 px-6 py-3 border-b border-border bg-appBg/80 backdrop-blur">
      {/* Search */}
      <div className="relative flex-1 max-w-xl">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search contracts, sections..."
          className="w-full bg-card border border-border rounded-lg pl-9 pr-16 py-2 text-[12.5px] placeholder:text-muted/70 focus:ring-2 focus:ring-gold/40 outline-none"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-0.5 text-[10px] text-muted">
          <Command size={10} /> K
        </span>

        {/* Suggestions */}
        {query.trim() && (
          <div className="absolute left-0 right-0 top-full mt-2 bg-warmwhite rounded-xl border border-border shadow-panel overflow-hidden fade-up">
            {results.length === 0 ? (
              <div className="px-4 py-5 text-center">
                <p className="text-[12.5px] font-semibold text-text">No matches found</p>
                <p className="text-[11px] text-muted mt-0.5">Try &ldquo;GOLDM&rdquo; or &ldquo;signals&rdquo;</p>
                <button onClick={() => onQueryChange('')} className="mt-2 text-[11.5px] font-semibold text-maroon hover:underline">
                  Clear search
                </button>
              </div>
            ) : (
              <>
                <div className="px-4 pt-3 pb-1 flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted">{results.length} results</span>
                  <button onClick={() => onQueryChange('')} className="text-[10.5px] text-muted hover:text-text flex items-center gap-1">
                    <X size={10} /> Clear
                  </button>
                </div>
                <div className="max-h-72 overflow-y-auto thin-scroll pb-1.5">
                  {results.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => {
                        if (r.kind === 'Contract') onSelectContract(r.target)
                        else onNavigate(r.target as ViewId)
                        onQueryChange('')
                      }}
                      className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-appBg transition-colors text-left"
                    >
                      <span className="text-[12.5px] text-text font-medium">{r.label}</span>
                      <span className="text-[10px] text-muted font-semibold uppercase tracking-wide">{r.kind}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex-1" />

      {/* Real connection status */}
      <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full border">
        <span className={`w-1.5 h-1.5 rounded-full ${isLive ? 'bg-[#3F8061] animate-pulse' : 'bg-[#B87928]'}`} />
        <span className={`text-[10.5px] font-bold ${isLive ? 'text-[#2E6447]' : 'text-[#8F5D1D]'}`}>
          {isLive ? 'LIVE' : 'NO FRESH QUOTES'}
        </span>
        <span className="text-[9.5px] text-muted max-w-[190px] truncate">{statusLine}</span>
      </div>

      {/* Real-time clock of last event */}
      <div className="hidden xl:flex flex-col items-end px-3 py-1 rounded-lg bg-card border border-border">
        <span className="text-[10.5px] font-bold text-text">
          {stream.status?.latest_event_at ? 'last provider event' : 'awaiting provider events'}
        </span>
        <span className="text-[9.5px] text-muted">
          {stream.status?.latest_event_at ? String(stream.status.latest_event_at) : '—'}
        </span>
      </div>

      {/* Notifications: real platform status + final anomalies are system-level only */}
      <div className="relative" ref={notifRef}>
        <button
          onClick={() => setShowNotif((s) => !s)}
          className="relative p-2 rounded-lg bg-card border border-border hover:bg-warmwhite transition-colors"
          aria-label="Provider status"
        >
          <Bell size={15} className="text-text" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[#B87928] ring-2 ring-appBg" />
        </button>
        {showNotif && (
          <div className="absolute right-0 top-full mt-2 w-80 bg-warmwhite rounded-xl border border-border shadow-panel overflow-hidden fade-up">
            <div className="px-4 py-2.5 border-b border-border">
              <p className="text-[12px] font-bold text-text">Provider status</p>
            </div>
            <div className="px-4 py-3 text-[11.5px] text-muted leading-relaxed space-y-1.5">
              <p><strong className="text-text">State:</strong> {feedState}</p>
              <p><strong className="text-text">Provider:</strong> {stream.status?.provider ?? 'not configured'}</p>
              {stream.status?.detail && <p>{stream.status.detail}</p>}
              <p>No notification content is generated client-side.</p>
            </div>
          </div>
        )}
      </div>

      <button
        className="w-9 h-9 rounded-full bg-maroon text-warmwhite font-bold text-[13px] flex items-center justify-center ring-1 ring-gold/40"
        aria-label="Profile"
        title="Operator console"
      >
        <CircleUser size={15} />
      </button>
    </header>
  )
}
