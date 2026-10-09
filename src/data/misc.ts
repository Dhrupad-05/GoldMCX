import type { Notification } from '../types'

export const NOTIFICATIONS: Notification[] = [
  { id: 'NT-01', title: 'High signal: GOLDM ↔ GOLDTEN spread widening', time: '2h ago', kind: 'signal', targetId: 'SIG-01' },
  { id: 'NT-02', title: 'Anomaly scenario recorded on GOLDTEN ↔ GOLDPETAL', time: '5h ago', kind: 'signal', targetId: 'SIG-10' },
  { id: 'NT-03', title: 'GUINEA expiry window begins in 2 days', time: '8h ago', kind: 'system' },
  { id: 'NT-04', title: 'New insight card: why median beats mean', time: 'Yesterday', kind: 'info', targetId: 'INS-05' },
  { id: 'NT-05', title: 'Calibration refreshed on GOLDM ↔ GOLDTEN', time: 'Yesterday', kind: 'system' },
  { id: 'NT-06', title: 'Liquidity guard filtered a petal signal', time: '2d ago', kind: 'system', targetId: 'SIG-09' },
  { id: 'NT-07', title: 'Watch signal: GOLDPETAL OI build-up', time: '2d ago', kind: 'signal', targetId: 'SIG-06' },
  { id: 'NT-08', title: 'Demo dataset frozen for recording', time: '3d ago', kind: 'system' },
]

export interface SearchItem {
  id: string
  label: string
  kind: 'Contract' | 'Pair' | 'Signal' | 'Insight' | 'Section'
  targetId: string
  keywords: string
}

export const SEARCH_INDEX: SearchItem[] = [
  { id: 'S-01', label: 'GOLDM — Gold Mini (100 g, 995)', kind: 'Contract', targetId: 'GOLDM', keywords: 'goldm mini 100g 995 contract' },
  { id: 'S-02', label: 'GOLDTEN — Gold Ten (10 g, 999)', kind: 'Contract', targetId: 'GOLDTEN', keywords: 'goldten ten 10g 999 contract' },
  { id: 'S-03', label: 'GOLDGUINEA — Gold Guinea (8 g, 999)', kind: 'Contract', targetId: 'GOLDGUINEA', keywords: 'guinea 8g coin contract' },
  { id: 'S-04', label: 'GOLDPETAL — Gold Petal (1 g, 999)', kind: 'Contract', targetId: 'GOLDPETAL', keywords: 'petal 1g small contract' },
  { id: 'S-05', label: 'GOLDM ↔ GOLDTEN spread widening', kind: 'Signal', targetId: 'SIG-01', keywords: 'high spread widening signal gold' },
  { id: 'S-06', label: 'GOLDPETAL spread event', kind: 'Signal', targetId: 'SIG-10', keywords: 'anomaly petal spread event' },
  { id: 'S-07', label: 'Novelty detection: normality-learning idea', kind: 'Insight', targetId: 'INS-04', keywords: 'novelty anomaly machine learning hands-on' },
  { id: 'S-08', label: 'Why raw gold prices cannot be compared', kind: 'Insight', targetId: 'INS-01', keywords: 'normalize quotation purity comparison' },
  { id: 'S-09', label: 'Comparison workspace', kind: 'Section', targetId: 'comparison', keywords: 'compare pair spread relative value' },
  { id: 'S-10', label: 'Novelty detection (model demo)', kind: 'Section', targetId: 'model', keywords: 'model anomaly novelty training robust' },
  { id: 'S-11', label: 'Backtest & evaluation', kind: 'Section', targetId: 'backtest', keywords: 'backtest costs net gross drawdown' },
  { id: 'S-12', label: 'Historical events', kind: 'Section', targetId: 'events', keywords: 'history events outcomes' },
]

export interface LearnItem {
  id: string
  q: string
  a: string
  category: string
}

export const LEARN_ITEMS: LearnItem[] = [
  {
    id: 'LR-01',
    q: 'What is MCX in this project?',
    a: 'Multi Commodity Exchange of India — the exchange where the four gold futures contracts used in this demo are listed. This prototype uses illustrative local data, not a live MCX feed.',
    category: 'Basics',
  },
  {
    id: 'LR-02',
    q: 'What do the four gold contracts represent?',
    a: 'GOLDM (100 g lot, quoted per 10 g, 995), GOLDTEN (10 g, 999), GOLDGUINEA (8 g coin-linked, 999) and GOLDPETAL (1 g, 999) — the same metal with different lot sizes, quote bases and purity.',
    category: 'Basics',
  },
  {
    id: 'LR-03',
    q: 'Why can raw prices not be compared directly?',
    a: 'A ₹72,480 price on GOLDM (per 10 g, 995) and a ₹7,120 price on GOLDPETAL (per 1 g, 999) are in different units and fineness. Only after dividing by the fine-gram basis do they become comparable.',
    category: 'Normalization',
  },
  {
    id: 'LR-04',
    q: 'What does normalization mean here?',
    a: 'pricePerFineGram = closePrice / (quoteGrams × purity/1000). It converts each quote into rupees per fine gram so the four contracts share one unit.',
    category: 'Normalization',
  },
  {
    id: 'LR-05',
    q: 'What is a relative spread?',
    a: 'For a pair (A, B): spread = (A − B) / ((A + B)/2), computed on normalized prices. It is a dimensionless percentage describing how far apart the two contracts are.',
    category: 'Relative value',
  },
  {
    id: 'LR-06',
    q: 'What is novelty detection?',
    a: 'A class of methods that learn what normal data looks like from mostly-normal observations, then decide whether a new observation resembles that normal region. Inspired by the Hands-On Machine Learning chapter on training with outliers ≤ 1%.',
    category: 'Model',
  },
  {
    id: 'LR-07',
    q: 'How does training on mostly-normal observations work?',
    a: 'Here, ~34 mostly-normal spread observations per pair form the training sample. The robust statistics (median, MAD) describe the learned normal region of the spread feature.',
    category: 'Model',
  },
  {
    id: 'LR-08',
    q: 'How is a new observation scored?',
    a: 'Modified z-score M = 0.6745 × (x − median) / MAD. |M| ≥ 3.5 flags a candidate anomaly; the demo severity score is min(|M|/6, 1), a heuristic — not a probability.',
    category: 'Model',
  },
  {
    id: 'LR-09',
    q: 'Why is an anomaly not automatically profitable?',
    a: 'Unusual ≠ mispriced, and mispriced ≠ tradable. Liquidity, expiry mechanics and round-trip costs can each remove the edge. Validation screens in the app separate these questions.',
    category: 'Caveats',
  },
  {
    id: 'LR-10',
    q: 'Why do time-based validation and costs matter?',
    a: 'Scoring an observation with statistics that include it is look-ahead bias. And an edge that survives must still clear double-sided transaction costs — both are included as demo guards.',
    category: 'Caveats',
  },
]
