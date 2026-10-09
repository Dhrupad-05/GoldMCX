import { useState } from 'react'
import { ChevronDown, Database, RefreshCw, ScanSearch, BadgeCheck, MessagesSquare, BrainCircuit, ArrowRight } from 'lucide-react'
import { Panel } from '../components/Panel'
import { LEARN_ITEMS } from '../data/misc'
import type { ViewId } from '../types'

const STAGES = [
  { n: '01', icon: Database, title: 'Collect data', desc: 'Gather MCX quotes, volumes and open interest for the four gold contracts. In this demo: fixed local series.' },
  { n: '02', icon: RefreshCw, title: 'Normalize contracts', desc: 'Convert each quote to ₹ per fine gram — dividing by quote-gram basis and adjusting for purity (995 vs 999).' },
  { n: '03', icon: ScanSearch, title: 'Detect unusual spreads', desc: 'Learn the normal cross-contract spread region from mostly-normal observations, then screen new observations with a robust z-score.' },
  { n: '04', icon: BadgeCheck, title: 'Validate', desc: 'Apply liquidity, expiry and transaction-cost guards. An unusual spread is not automatically tradable.' },
  { n: '05', icon: MessagesSquare, title: 'Explain insights', desc: 'Reason codes, charts and plain-language explanations accompany every signal.' },
]

export function LearnPage({ onNavigate }: { onNavigate: (v: ViewId) => void }) {
  const [open, setOpen] = useState<string | null>('LR-06')

  return (
    <div className="space-y-4">
      <div className="bg-card border border-border rounded-xl p-5 shadow-panel">
        <h2 className="text-[19px] font-extrabold text-text" style={{ fontFamily: 'Georgia, serif' }}>Learn — Methodology in Plain Language</h2>
        <p className="text-[12.5px] text-muted mt-1.5 leading-relaxed max-w-3xl">
          Everything the dashboard does, explained step by step. Written so it can be narrated during a two-minute demo without a quant specialist in the room.
        </p>
      </div>

      {/* Pipeline */}
      <Panel title="The five-stage pipeline" icon={<ScanSearch size={15} />}>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {STAGES.map((s, i) => (
            <div key={s.n} className="relative bg-appBg border border-border rounded-xl p-3.5">
              <span className="w-8 h-8 rounded-lg bg-maroon text-warmwhite flex items-center justify-center">
                <s.icon size={14} />
              </span>
              <p className="text-[10px] font-bold text-gold mt-2.5">STEP {s.n}</p>
              <p className="text-[12.5px] font-extrabold text-text mt-0.5">{s.title}</p>
              <p className="text-[10.5px] text-muted leading-snug mt-1">{s.desc}</p>
              {i < 4 && <span className="hidden md:block absolute top-1/2 -right-2.5 text-muted">→</span>}
            </div>
          ))}
        </div>
        <button
          onClick={() => onNavigate('model')}
          className="mt-4 inline-flex items-center gap-1.5 text-[12px] font-bold text-maroon hover:underline"
        >
          Open the interactive normality-learning demo <ArrowRight size={12} />
        </button>
      </Panel>

      {/* Novelty explainer strip */}
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] gap-4">
        <div className="hero-texture rounded-2xl p-5 text-warmwhite">
          <div className="flex items-center gap-2">
            <BrainCircuit size={16} className="text-gold" />
            <p className="text-[13px] font-extrabold">Why &ldquo;normality learning&rdquo; works with few anomalies</p>
          </div>
          <p className="text-[12px] text-warmwhite/75 leading-relaxed mt-2.5">
            Labelled anomaly data is scarce. Instead of training a classifier on rare examples, novelty detection learns the <em>region of normal behaviour</em> from mostly-normal observations and asks, for each new point: does it look like the normal region, or does it fall outside?
          </p>
          <p className="text-[12px] text-warmwhite/75 leading-relaxed mt-2">
            This prototype implements the simplest faithful version of that idea: robust median/MAD statistics of the training spreads, scored via the modified z-score. Production systems could extend the same concept with richer features and Isolation Forests.
          </p>
          <button
            onClick={() => onNavigate('model')}
            className="mt-3.5 inline-flex items-center gap-1.5 bg-warmwhite text-deeper text-[12px] font-bold px-3.5 py-2 rounded-lg hover:bg-gold/20 transition-colors"
          >
            Try it on real (demo) observations <ArrowRight size={12} />
          </button>
        </div>

        <Panel title="Fast reference" subtitle="Formulas used in the demo">
          <div className="space-y-2.5 text-[12px] leading-relaxed">
            {[
              ['Normalized price', 'price / (quoteGrams × purity/1000) = ₹ per fine gram'],
              ['Relative spread', '(A − B) / ((A + B)/2), as %'],
              ['Robust centre', 'median of training spreads'],
              ['Robust scale', 'MAD = median(|xᵢ − median(x)|)'],
              ['Modified z-score', 'M = 0.6745 × (x − median) / MAD'],
              ['Screening rule', 'flag when |M| ≥ 3.5 (heuristic)'],
              ['Demo severity', 'min(|M| / 6, 1) — not a probability'],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-3 border-b border-border/50 pb-2 last:border-0">
                <span className="font-bold text-text shrink-0">{k}</span>
                <span className="text-muted text-right font-mono text-[11px]">{v}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* FAQ */}
      <Panel title="Common questions" subtitle="Expand any item">
        <div className="divide-y divide-border">
          {LEARN_ITEMS.map((item) => (
            <div key={item.id}>
              <button
                onClick={() => setOpen(open === item.id ? null : item.id)}
                className="w-full flex items-center gap-3 py-3 text-left"
              >
                <span className="text-[10px] font-bold uppercase tracking-wide text-gold shrink-0 w-20">{item.category}</span>
                <span className="text-[12.5px] font-semibold text-text flex-1">{item.q}</span>
                <ChevronDown size={14} className={`text-muted transition-transform ${open === item.id ? 'rotate-180' : ''}`} />
              </button>
              {open === item.id && (
                <p className="text-[12px] text-muted leading-relaxed pb-3.5 pl-[104px] pr-6">{item.a}</p>
              )}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
