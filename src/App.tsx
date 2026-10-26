import { useState, useCallback, useEffect, useMemo } from 'react'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { SignalDetailModal } from './components/SignalDetailModal'
import { Modal } from './components/Modal'
import { DashboardPage } from './pages/DashboardPage'
import { SignalsPage } from './pages/SignalsPage'
import { ContractsPage } from './pages/ContractsPage'
import { ComparisonPage } from './pages/ComparisonPage'
import { ModelPage } from './pages/ModelPage'
import { InsightsPage } from './pages/InsightsPage'
import { LearnPage } from './pages/LearnPage'
import { EventsBacktestPage } from './pages/EventsBacktestPage'
import { insightById } from './lib/filters'
import { useMarketStream } from './lib/useMarketStream'
import { vmFromAnomaly } from './lib/signalVM'
import type { SignalVM } from './lib/signalVM'
import type { MarketStreamState } from './lib/useMarketStream'
import type { ContractSymbol, MlAnomaly, ViewId } from './lib/api'
import { API_BASE } from './lib/api'

const INITIAL = {
  view: 'dashboard' as ViewId,
  contract: 'GOLDM' as ContractSymbol,
  left: 'GOLDM' as ContractSymbol,
  right: 'GOLDTEN' as ContractSymbol,
  query: '',
}

export default function App() {
  const [view, setView] = useState<ViewId>(INITIAL.view)
  const [query, setQuery] = useState(INITIAL.query)
  const [activeSignal, setActiveSignal] = useState<SignalVM | null>(null)
  const [activeInsightId, setActiveInsightId] = useState<string | null>(null)
  const [selectedContract, setSelectedContract] = useState<ContractSymbol>(INITIAL.contract)
  const [compareLeft, setCompareLeft] = useState<string>(INITIAL.left)
  const [compareRight, setCompareRight] = useState<string>(INITIAL.right)
  const [comparisonRange, setComparisonRange] = useState<'1M' | '3M' | '6M' | '1Y'>('3M')
  const [detailRange, setDetailRange] = useState<'1M' | '3M' | '6M' | '1Y'>('3M')

  const stream = useMarketStream()

  const navigate = useCallback((v: ViewId) => {
    setView(v)
    setActiveSignal(null)
  }, [])

  const openAnomaly = useCallback((a: MlAnomaly) => {
    setActiveSignal(vmFromAnomaly(a))
  }, [])

  // Insight modal via custom event (used by dashboard cards)
  useEffect(() => {
    const handler = (e: Event) => setActiveInsightId((e as CustomEvent<string>).detail)
    window.addEventListener('open-insight', handler)
    return () => window.removeEventListener('open-insight', handler)
  }, [])

  const activeInsight = activeInsightId ? insightById(activeInsightId) : null

  const viewMeta = useMemo(() => {
    return {
      title: view,
      sub: `API: ${API_BASE || 'same origin'} · data served by FastAPI`,
    }
  }, [view])

  return (
    <div className="flex h-full">
      <Sidebar activeView={view} onNavigate={navigate} researchMode onToggleResearchMode={() => {}} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          query={query}
          onQueryChange={setQuery}
          onNavigate={(target) => {
            const v = viewIdSafe(target)
            if (v) navigate(v)
          }}
          onSelectContract={(id) => {
            setSelectedContract(id as ContractSymbol)
            navigate('contracts')
          }}
          stream={stream}
        />
        {/* Inline sub-toolbar */}
        <div className="flex items-center justify-between px-6 py-2 border-b border-border/60 bg-appBg">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted font-bold">{viewMeta.title}</p>
            <p className="text-[10.5px] text-muted truncate">{viewMeta.sub}</p>
          </div>
        </div>

        <main className="flex-1 overflow-y-auto thin-scroll p-6">
          {view === 'dashboard' && (
            <DashboardPage
              stream={stream}
              onNavigate={navigate}
              onOpenSignal={openAnomaly}
              onSelectContract={(id) => {
                if (isSymbol(id)) setSelectedContract(id)
                setView('contracts')
              }}
              comparisonRange={comparisonRange}
              setComparisonRange={setComparisonRange}
              detailRange={detailRange}
              setDetailRange={setDetailRange}
              compareLeft={compareLeft}
              setCompareLeft={setCompareLeft}
            />
          )}
          {view === 'signals' && <SignalsPage onNavigateComparison={(pid) => { applyPair(pid); navigate('comparison') }} />}
          {view === 'contracts' && (
            <ContractsPage selected={selectedContract} onSelect={setSelectedContract} />
          )}
          {view === 'comparison' && (
            <ComparisonPage
              left={compareLeft}
              right={compareRight}
              setLeft={setCompareLeft}
              setRight={setCompareRight}
              onOpenSignal={(pid) => applyPair(pid)}
            />
          )}
          {view === 'model' && <ModelPage />}
          {view === 'insights' && <InsightsPage />}
          {view === 'learn' && <LearnPage onNavigate={navigate} />}
          {view === 'backtest' && <EventsBacktestPage />}
        </main>
      </div>

      <SignalDetailModal
        signal={activeSignal}
        onClose={() => setActiveSignal(null)}
        onNavigateComparison={(pid) => {
          applyPair(pid)
          navigate('comparison')
          setActiveSignal(null)
        }}
      />

      <Modal open={!!activeInsight} onClose={() => setActiveInsightId(null)} title={activeInsight?.title ?? ''} subtitle={activeInsight ? `${activeInsight.category} · ${activeInsight.date} · Educational content` : ''}>
        {activeInsight && (
          <div className="space-y-3">
            <p className="text-[13px] text-text leading-relaxed font-medium">{activeInsight.summary}</p>
            <ul className="space-y-2">
              {activeInsight.body.map((b, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] text-muted leading-relaxed">
                  <span className="w-1.5 h-1.5 rounded-full bg-gold mt-1.5 shrink-0" />
                  {b}
                </li>
              ))}
            </ul>
            <div className="bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
              Educational content. It is not current market data and not investment advice.
            </div>
          </div>
        )}
      </Modal>
    </div>
  )

  function applyPair(pid: string) {
    const [l, r] = pid.split('-')
    if (isSymbol(l)) setCompareLeft(l as ContractSymbol)
    if (isSymbol(r)) setCompareRight(r as ContractSymbol)
  }
}

function isSymbol(s: string): s is ContractSymbol {
  return ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL'].includes(s)
}

function viewIdSafe(v: string): ViewId | null {
  const allowed: ViewId[] = ['dashboard', 'signals', 'contracts', 'comparison', 'model', 'insights', 'learn', 'backtest', 'events']
  const map: Record<string, ViewId> = { backtest: 'backtest', events: 'backtest' }
  return allowed.includes(v as ViewId) ? (v as ViewId) : (map[v] ?? null)
}
