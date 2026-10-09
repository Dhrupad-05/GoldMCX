import { useState, useMemo, useRef, useEffect } from 'react'
import { Search, Bell, CircleUser, Command, X } from 'lucide-react'
import { searchAll } from '../lib/filters'
import { NOTIFICATIONS } from '../data/misc'
import type { ViewId } from '../types'

export function Topbar({
  query,
  onQueryChange,
  onOpenResult,
  onOpenSignal,
  onNavigate,
  onSelectContract,
  activeSignalId,
}: {
  query: string
  onQueryChange: (q: string) => void
  onOpenResult: (targetId: string, kind: string) => void
  onOpenSignal: (signalId: string) => void
  onNavigate: (v: ViewId) => void
  onSelectContract: (id: string) => void
  activeSignalId?: string
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

  const results = useMemo(() => searchAll(query), [query])

  return (
    <header className="relative z-20 flex items-center gap-4 px-6 py-3 border-b border-border bg-appBg/80 backdrop-blur">
      {/* Search */}
      <div className="relative flex-1 max-w-xl">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Search contracts, signals, insights..."
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
                <p className="text-[11px] text-muted mt-0.5">Try &ldquo;GOLDM&rdquo;, &ldquo;spread&rdquo; or &ldquo;novelty&rdquo;</p>
                <button
                  onClick={() => onQueryChange('')}
                  className="mt-2 text-[11.5px] font-semibold text-maroon hover:underline"
                >
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
                        if (r.kind === 'Signal') onOpenSignal(r.targetId)
                        else if (r.kind === 'Contract') onSelectContract(r.targetId)
                        else if (r.kind === 'Section') onNavigate(r.targetId as ViewId)
                        else onOpenResult(r.targetId, r.kind)
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

      {/* Demo data badge */}
      <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#B87928]/12 border border-[#B87928]/30">
        <span className="w-1.5 h-1.5 rounded-full bg-[#B87928]" />
        <span className="text-[10.5px] font-bold text-[#8F5D1D]">DEMO MODE · Illustrative data</span>
      </div>

      {/* Update time */}
      <div className="hidden lg:flex flex-col items-end px-3 py-1 rounded-lg bg-card border border-border">
        <span className="flex items-center gap-1.5 text-[10.5px] font-bold text-[#2E6447]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3F8061] animate-pulse" />
          Simulated snapshot
        </span>
        <span className="text-[9.5px] text-muted">9 Oct 2026, 09:45 IST</span>
      </div>

      {/* Notifications */}
      <div className="relative" ref={notifRef}>
        <button
          onClick={() => setShowNotif((s) => !s)}
          className="relative p-2 rounded-lg bg-card border border-border hover:bg-warmwhite transition-colors"
          aria-label="Notifications"
        >
          <Bell size={15} className="text-text" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-danger ring-2 ring-appBg" />
        </button>
        {showNotif && (
          <div className="absolute right-0 top-full mt-2 w-80 bg-warmwhite rounded-xl border border-border shadow-panel overflow-hidden fade-up">
            <div className="px-4 py-2.5 border-b border-border">
              <p className="text-[12px] font-bold text-text">Activity (seeded demo)</p>
            </div>
            <div className="max-h-72 overflow-y-auto thin-scroll">
              {NOTIFICATIONS.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    if (n.kind === 'signal' && n.targetId) onOpenSignal(n.targetId)
                    else if (n.targetId?.startsWith('INS')) onOpenResult(n.targetId, 'Insight')
                    setShowNotif(false)
                  }}
                  className="w-full text-left px-4 py-2.5 hover:bg-appBg transition-colors border-b border-border/50 last:border-0"
                >
                  <p className="text-[12px] text-text leading-snug">{n.title}</p>
                  <p className="text-[10px] text-muted mt-0.5">{n.time}</p>
                </button>
              ))}
            </div>
            <div className="px-4 py-2 bg-appBg text-center">
              <span className="text-[10px] text-muted">No real notifications are sent</span>
            </div>
          </div>
        )}
      </div>

      {/* Avatar */}
      <button
        className="w-9 h-9 rounded-full bg-maroon text-warmwhite font-bold text-[13px] flex items-center justify-center ring-1 ring-gold/40"
        aria-label="Profile (demo)"
        title="Analyst profile — demo"
      >
        D
      </button>

      {activeSignalId && <span className="hidden">{activeSignalId}</span>}
    </header>
  )
}
