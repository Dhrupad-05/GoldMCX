import { useState, useCallback, useEffect, useMemo } from 'react'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { DemoReset } from './components/DemoReset'
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
import { SIGNALS } from './data/signals'
import { CONTRACTS } from './data/contracts'
import { viewIdFor } from './data/getContract'
import type { ContractId, DemoSignal, ViewId } from './types'

const INITIAL = {
  view: 'dashboard' as ViewId,
  contract: 'GOLDM' as ContractId,
  left: 'GOLDM' as ContractId,
  right: 'GOLDTEN' as ContractId,
  query: '',
  researchMode: true,
}

export default function App() {
  const [view, setView] = useState<ViewId>(INITIAL.view)
  const [query, setQuery] = useState(INITIAL.query)
  const [activeSignal, setActiveSignal] = useState<DemoSignal | null>(null)
  const [activeInsightId, setActiveInsightId] = useState<string | null>(null)
  const [selectedContract, setSelectedContract] = useState<ContractId>(INITIAL.contract)
  const [compareLeft, setCompareLeft] = useState<ContractId>(INITIAL.left)
  const [compareRight, setCompareRight] = useState<ContractId>(INITIAL.right)
  const [comparisonRange, setComparisonRange] = useState<'1M' | '3M' | '6M' | '1Y'>('3M')
  const [detailRange, setDetailRange] = useState<'1M' | '3M' | '6M' | '1Y'>('1M')
  const [researchMode, setResearchMode] = useState(INITIAL.researchMode)

  const navigate = useCallback((v: ViewId) => {
    setView(v)
    setActiveSignal(null)
  }, [])

  const openSignalById = useCallback((id: string) => {
    const s = SIGNALS.find((x) => x.id === id)
    if (s) setActiveSignal(s)
  }, [])

  // Insight modal via custom event (used by dashboard cards)
  useEffect(() => {
    const handler = (e: Event) => setActiveInsightId((e as CustomEvent<string>).detail)
    window.addEventListener('open-insight', handler)
    return () => window.removeEventListener('open-insight', handler)
  }, [])

  const reset = useCallback(() => {
    setView(INITIAL.view)
    setQuery(INITIAL.query)
    setActiveSignal(null)
    setActiveInsightId(null)
    setSelectedContract(INITIAL.contract)
    setCompareLeft(INITIAL.left)
    setCompareRight(INITIAL.right)
    setComparisonRange('3M')
    setDetailRange('1M')
    setResearchMode(INITIAL.researchMode)
  }, [])

  const activeInsight = activeInsightId ? insightById(activeInsightId) : null

  const viewMeta = useMemo(() => {
    const c = CONTRACTS.find((x) => x.id === selectedContract)!
    return { title: view, sub: `${c.symbol} selected · demo data` }
  }, [view, selectedContract])

  return (
    <div className="flex h-full">
      <Sidebar
        activeView={view}
        onNavigate={navigate}
        researchMode={researchMode}
        onToggleResearchMode={() => setResearchMode((r) => !r)}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          query={query}
          onQueryChange={setQuery}
          onOpenSignal={openSignalById}
          onNavigate={(target) => {
            const v = viewIdFor(target)
            if (v) navigate(v)
          }}
          onOpenResult={(id) => setActiveInsightId(id)}
          onSelectContract={(id) => {
            setSelectedContract(id as ContractId)
            navigate('contracts')
          }}
          activeSignalId={activeSignal?.id}
        />
        {/* Inline sub-toolbar */}
        <div className="flex items-center justify-between px-6 py-2 border-b border-border/60 bg-appBg">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted font-bold">{viewMeta.title}</p>
            <p className="text-[10.5px] text-muted truncate">Illustrative data — not a live MCX feed; scores are demo calculations</p>
          </div>
          <DemoReset onReset={reset} />
        </div>

        <main className="flex-1 overflow-y-auto thin-scroll p-6">
          {view === 'dashboard' && (
            <DashboardPage
              onNavigate={navigate}
              onOpenSignal={setActiveSignal}
              onSelectContract={(id) => {
                setSelectedContract(id)
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
          {view === 'signals' && <SignalsPage onOpenSignal={setActiveSignal} />}
          {view === 'contracts' && (
            <ContractsPage selected={selectedContract} onSelect={setSelectedContract} />
          )}
          {view === 'comparison' && (
            <ComparisonPage
              left={compareLeft}
              right={compareRight}
              setLeft={setCompareLeft}
              setRight={setCompareRight}
              onOpenSignal={setActiveSignal}
            />
          )}
          {view === 'model' && <ModelPage />}
          {view === 'insights' && <InsightsPage />}
          {view === 'learn' && <LearnPage onNavigate={navigate} />}
          {view === 'backtest' && <EventsBacktestPage />}
        </main>
      </div>

      <SignalDetailModal signal={activeSignal} onClose={() => setActiveSignal(null)} onNavigateComparison={() => {
        if (activeSignal) {
          const [l, r] = activeSignal.pairId.split('-')
          if (CONTRACTS.some((c) => c.id === l)) setCompareLeft(l as ContractId)
          if (CONTRACTS.some((c) => c.id === r)) setCompareRight(r as ContractId)
        }
        setView('comparison')
        setActiveSignal(null)
      }} />

      <Modal open={!!activeInsight} onClose={() => setActiveInsightId(null)} title={activeInsight?.title ?? ''} subtitle={activeInsight ? `${activeInsight.category} · ${activeInsight.date} · Illustrative content` : ''}>
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
              Educational content for the Hack in Hills '26 demo. Not investment advice.
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
