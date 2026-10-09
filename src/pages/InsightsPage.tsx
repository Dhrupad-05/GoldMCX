import { useMemo, useState } from 'react'
import { Filter } from 'lucide-react'
import { Panel } from '../components/Panel'
import { Modal } from '../components/Modal'
import { RESEARCH_CARDS } from '../data/researchCards'
import type { ResearchCard } from '../types'

export function InsightsPage() {
  const [cat, setCat] = useState('All')
  const [detail, setDetail] = useState<ResearchCard | null>(null)
  const cats = useMemo(() => ['All', ...Array.from(new Set(RESEARCH_CARDS.map((c) => c.category)))], [])

  const filtered = useMemo(() => (cat === 'All' ? RESEARCH_CARDS : RESEARCH_CARDS.filter((c) => c.category === cat)), [cat])

  return (
    <div className="space-y-4">
      <Panel
        title="Market Insights"
        subtitle="Educational and methodological notes — all content illustrative"
        right={
          <div className="flex items-center gap-1.5">
            <Filter size={12} className="text-muted" />
            {cats.map((c) => (
              <button
                key={c}
                onClick={() => setCat(c)}
                className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors ${
                  cat === c ? 'bg-maroon text-warmwhite border-maroon' : 'bg-card text-muted border-border hover:text-text'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((card) => (
            <button
              key={card.id}
              onClick={() => setDetail(card)}
              className="text-left rounded-xl border border-border bg-warmwhite overflow-hidden hover:shadow-soft hover:-translate-y-px transition-all"
            >
              <div className="hero-texture h-20 p-2.5 flex items-end justify-between">
                <span className="text-[8.5px] font-bold text-warmwhite/85 bg-deeper/60 px-1.5 py-0.5 rounded">{card.category}</span>
              </div>
              <div className="p-3">
                <p className="text-[12px] font-bold text-text leading-tight">{card.title}</p>
                <p className="text-[10.5px] text-muted mt-1.5 leading-snug line-clamp-2">{card.summary}</p>
                <p className="text-[9.5px] text-muted mt-2">{card.date} · Illustrative</p>
              </div>
            </button>
          ))}
        </div>
      </Panel>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.title ?? ''} subtitle={detail ? `${detail.category} · ${detail.date} · Illustrative content` : ''}>
        {detail && (
          <div className="space-y-3">
            <p className="text-[13px] text-text leading-relaxed font-medium">{detail.summary}</p>
            <ul className="space-y-2">
              {detail.body.map((b, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] text-muted leading-relaxed">
                  <span className="w-1.5 h-1.5 rounded-full bg-gold mt-1.5 shrink-0" />
                  {b}
                </li>
              ))}
            </ul>
            <div className="bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
              Educational content for the Hack in Hills '26 demo. Not investment advice; no claims about real MCX conditions.
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
