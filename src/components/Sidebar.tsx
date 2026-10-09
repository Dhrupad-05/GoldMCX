import {
  LayoutDashboard,
  Activity,
  Briefcase,
  GitCompareArrows,
  BrainCircuit,
  Newspaper,
  GraduationCap,
  Database,
  FlaskConical,
  History,
} from 'lucide-react'
import type { ViewId } from '../types'

const NAV: { id: ViewId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'signals', label: 'Signals', icon: Activity },
  { id: 'contracts', label: 'Contracts', icon: Briefcase },
  { id: 'comparison', label: 'Comparison', icon: GitCompareArrows },
  { id: 'model', label: 'Model Demo', icon: BrainCircuit },
  { id: 'insights', label: 'Market Insights', icon: Newspaper },
  { id: 'learn', label: 'Learn', icon: GraduationCap },
]

export function Sidebar({
  activeView,
  onNavigate,
  researchMode,
  onToggleResearchMode,
}: {
  activeView: ViewId
  onNavigate: (v: ViewId) => void
  researchMode: boolean
  onToggleResearchMode: () => void
}) {
  return (
    <aside className="sidebar-texture w-60 shrink-0 flex flex-col text-warmwhite">
      {/* Brand */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-gold to-[#8F6A2E] flex items-center justify-center shadow-soft">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3B1117" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 17l6-6 4 4 8-8" />
              <path d="M14 7h7v7" />
            </svg>
          </div>
          <div>
            <h1 className="text-[15px] font-extrabold tracking-wide">GOLD INSIGHT</h1>
            <p className="text-[9.5px] tracking-[0.18em] text-warmwhite/60 font-semibold">MCX GOLD RELATIVE VALUE</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto thin-scroll">
        {NAV.map((item) => {
          const active = activeView === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-semibold transition-all ${
                active
                  ? 'bg-maroon/80 text-warmwhite shadow-soft ring-1 ring-gold/25'
                  : 'text-warmwhite/65 hover:text-warmwhite hover:bg-warmwhite/5'
              }`}
            >
              <item.icon size={16} strokeWidth={2.1} />
              {item.label}
            </button>
          )
        })}
        <button
          onClick={() => onNavigate('backtest')}
          className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-[13px] font-semibold transition-all ${
            activeView === 'backtest'
              ? 'bg-maroon/80 text-warmwhite shadow-soft ring-1 ring-gold/25'
              : 'text-warmwhite/65 hover:text-warmwhite hover:bg-warmwhite/5'
          }`}
        >
          <History size={16} strokeWidth={2.1} />
          Backtest &amp; Events
        </button>
      </nav>

      {/* Data source card */}
      <div className="px-4 pb-3">
        <div className="rounded-xl bg-deeper/60 border border-warmwhite/10 p-3.5">
          <div className="flex items-center gap-2">
            <Database size={14} className="text-gold" />
            <p className="text-[11.5px] font-bold">Real MCX Data</p>
          </div>
          <p className="text-[10.5px] text-warmwhite/55 leading-relaxed mt-1">
            <span className="text-gold font-semibold">Demo instance:</span> historical + illustrative local data only
          </p>
        </div>
      </div>

      {/* Research mode */}
      <div className="px-4 pb-6">
        <button
          onClick={onToggleResearchMode}
          className={`w-full rounded-xl border p-3.5 text-left transition-all ${
            researchMode
              ? 'bg-gold/15 border-gold/40'
              : 'bg-warmwhite/5 border-warmwhite/10 hover:bg-warmwhite/10'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FlaskConical size={14} className={researchMode ? 'text-gold' : 'text-warmwhite/60'} />
              <p className={`text-[11.5px] font-bold ${researchMode ? 'text-gold' : ''}`}>Research Mode</p>
            </div>
            <div className={`w-8 h-4.5 rounded-full relative transition-colors ${researchMode ? 'bg-gold' : 'bg-warmwhite/20'}`} style={{ height: 18, width: 32 }}>
              <div
                className="absolute top-0.5 w-3.5 h-3.5 rounded-full bg-warmwhite transition-all"
                style={{ left: researchMode ? 15 : 3 }}
              />
            </div>
          </div>
          <p className="text-[10px] text-warmwhite/50 mt-1.5 leading-relaxed">
            {researchMode
              ? 'Educational explanations visible across views.'
              : 'Toggle for methodology hints on every view.'}
          </p>
        </button>
      </div>
    </aside>
  )
}
