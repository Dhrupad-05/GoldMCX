export type ViewId =
  | 'dashboard'
  | 'signals'
  | 'contracts'
  | 'comparison'
  | 'model'
  | 'insights'
  | 'learn'
  | 'backtest'
  | 'events'

export type ContractId = 'GOLDM' | 'GOLDTEN' | 'GOLDGUINEA' | 'GOLDPETAL'

export type SignalStatus = 'High' | 'Watch' | 'Opportunity' | 'Anomaly' | 'Normal'

export type ValidationDisposition = 'Actionable' | 'Watch' | 'Ignore'

export interface Contract {
  id: ContractId
  symbol: ContractId
  displayName: string
  tradingUnitGrams: number
  quoteGrams: number
  purity: number // per thousand
  expiryLabel: string
  demoPrice: number // per quoteGram basis
  demoChangePct: number
  status: string
  description: string
}

export interface ContractPair {
  pairId: string
  left: ContractId
  right: ContractId
}

export interface SeriesPoint {
  date: string
  [contract: string]: string | number
}

export interface SpreadPoint {
  date: string
  spreadPct: number
}

export interface DemoSignal {
  id: string
  date: string
  pairId: string
  title: string
  type: string
  status: SignalStatus
  robustZ: number
  score: number
  daysToExpiry: number
  liquidity: 'Healthy' | 'Adequate' | 'Low'
  summary: string
  reasons: string[]
  expiryNote?: string
}

export interface HistoricalEvent {
  id: string
  date: string
  pairId: string
  category: string
  severity: 'High' | 'Moderate' | 'Low'
  spreadDeviationPct: number
  expiryContext: string
  outcome: string
  outcomeDirection: 'positive' | 'negative' | 'neutral'
}

export interface ResearchCard {
  id: string
  title: string
  category: string
  date: string
  summary: string
  body: string[]
  isIllustrative: true
}

export interface BacktestScenario {
  id: string
  name: string
  pairId: string
  period: string
  grossPct: number
  txnCostPct: number
  netPct: number
  trades: number
  winRatePct: number
  maxDrawdownPct: number
  avgConvergenceDays: number
  baselinePct: number
}

export interface NoveltyObservation {
  id: string
  pairId: string
  scenarioLabel: string
  spreadPct: number
  volumeRatio: number
  openInterestRatio: number
  daysToExpiry: number
  expectedHint: 'normal' | 'unusual'
  narrative: string
}

export interface Notification {
  id: string
  title: string
  time: string
  kind: 'signal' | 'info' | 'system'
  targetId?: string
}
