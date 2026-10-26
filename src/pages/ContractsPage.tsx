import { useState } from 'react'
import { Panel } from '../components/Panel'
import { StatusBadge } from '../components/StatusBadge'
import { PriceComparisonChart } from '../components/PriceComparisonChart'
import { SpreadChart } from '../components/SpreadChart'
import { RangeTabs } from '../components/RangeTabs'
import { api } from '../lib/api'
import type { ContractInventoryItem, ContractSymbol, SeriesResponse } from '../lib/api'
import { useApi } from '../lib/useApi'
import { pairLabel } from '../lib/api'
import type { TimeRange } from '../lib/filters'
import { fmtINR } from '../lib/demoUtil'
import { ChartSkeleton, ChartUnavailable } from '../components/PriceComparisonChart'

const TABS = ['Overview', 'Price Chart', 'Term Structure', 'Historical Data', 'Specifications'] as const
type Tab = (typeof TABS)[number]

const SYMBOLS: ContractSymbol[] = ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']
const NAMES: Record<ContractSymbol, string> = {
  GOLDM: 'Gold',
  GOLDTEN: 'Gold Mini',
  GOLDGUINEA: 'Gold Guinea',
  GOLDPETAL: 'Gold Petal',
}

const ALL_PAIRS: string[] = [
  'GOLDM-GOLDTEN',
  'GOLDM-GOLDGUINEA',
  'GOLDM-GOLDPETAL',
  'GOLDTEN-GOLDGUINEA',
  'GOLDTEN-GOLDPETAL',
  'GOLDGUINEA-GOLDPETAL',
]

export function ContractsPage({
  selected,
  onSelect,
}: {
  selected: ContractSymbol
  onSelect: (id: ContractSymbol) => void
}) {
  const [tab, setTab] = useState<Tab>('Overview')
  const [range, setRange] = useState<TimeRange>('3M')
  const inventory = useApi(() => api.contracts(), [])
  const series = useApi(() => api.contractSeries(selected), [selected])
  const pairsFor = ALL_PAIRS.filter((p) => p.startsWith(`${selected}-`) || p.endsWith(`-${selected}`))

  const items = inventory.data?.contracts ?? []
  const item = items.find((c) => c.symbol === selected)
  const spec = item?.specs[item.specs.length - 1]
  const allPoints = series.data?.points
  const lastPoint = allPoints && allPoints.length > 0 ? allPoints[allPoints.length - 1] : null

  return (
    <div className="space-y-4">
      {/* Contract selector */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {SYMBOLS.map((k) => {
          const it = items.find((c) => c.symbol === k)
          const lastVal = it?.latest_quote_set?.total_value_lakhs
          return (
            <button
              key={k}
              onClick={() => onSelect(k)}
              className={`rounded-xl border p-3.5 text-left transition-all ${
                k === selected
                  ? 'bg-maroon text-warmwhite border-maroon shadow-panel'
                  : 'bg-card border-border hover:shadow-soft'
              }`}
            >
              <p className="text-[13px] font-extrabold">{k}</p>
              <p className={`text-[10.5px] mt-0.5 ${k === selected ? 'text-warmwhite/70' : 'text-muted'}`}>
                {NAMES[k]} · {it?.data_summary.last_date ?? 'no data'}
              </p>
              <p className={`text-[14px] font-bold mt-1.5 ${k === selected ? 'text-gold' : 'text-text'}`}>
                {lastVal != null ? `${fmtINR(lastVal)} act/lot` : '—'}
              </p>
              <StatusBadge tone={k === selected ? 'gold' : it?.status === 'NO_DATA' ? 'neutral' : 'amber'}>
                {it?.status ?? 'NO_DATA'}
              </StatusBadge>
            </button>
          )
        })}
      </div>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-[18px] font-extrabold text-text" style={{ fontFamily: 'Georgia, serif' }}>
          {selected} — {NAMES[selected]}
        </h2>
        <StatusBadge tone={item && item.status !== 'NO_DATA' ? 'amber' : 'neutral'} dot>
          {item?.status ?? 'NO_DATA'}
        </StatusBadge>
        <span className="text-[11.5px] text-muted ml-auto">
          Official MCX observations · {item?.data_summary.last_date ?? 'awaiting EOD sync'}
        </span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border px-1 overflow-x-auto thin-scroll">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3.5 py-2 text-[12px] font-semibold border-b-2 -mb-px transition-colors whitespace-nowrap ${
              tab === t ? 'border-maroon text-maroon' : 'border-transparent text-muted hover:text-text'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <Panel>
        {tab === 'Overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
            <div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['Normalized last', lastPoint ? `₹${lastPoint.normalized_value.toFixed(0)} / fine g` : '—'],
                  ['Data status', item?.status ?? 'NO_DATA'],
                  ['Days covered', String(item?.data_summary.detail_days ?? 0)],
                  ['Last observation', item?.data_summary.last_date ?? '—'],
                ].map(([k, v]) => (
                  <div key={k} className="bg-appBg border border-border rounded-lg px-3 py-2">
                    <p className="text-[9.5px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                    <p className="text-[13px] font-bold text-text mt-0.5">{v}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 rounded-lg bg-[#B87928]/10 border border-[#B87928]/25 p-3 text-[11.5px] text-[#8F5D1D] leading-relaxed">
                {item?.coverage_note ??
                  'Contract inventory loads from the backend. Activity-report values are provisional aggregates, not settlement prices.'}
              </div>
            </div>
            <div>
              <p className="text-[11px] font-bold text-text mb-2">Pairs involving {selected}</p>
              <div className="space-y-2">
                {pairsFor.map((p) => (
                  <div key={p} className="flex items-center justify-between bg-appBg border border-border rounded-lg px-3 py-2">
                    <span className="text-[12px] font-semibold text-text">{pairLabel(p)}</span>
                    <span className="text-[10.5px] text-muted">6 canonical pairs</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'Price Chart' && (
          <div className="pt-2">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[12.5px] font-bold text-text">Normalized price (₹ per fine gram) — {selected}</p>
              <RangeTabs value={range} onChange={setRange} compact />
            </div>
            <PriceComparisonChart ids={[selected]} range={range} height={280} />
            <p className="text-[10px] text-muted mt-1">Normalized via verified contract specifications.</p>
          </div>
        )}

        {tab === 'Term Structure' && (
          <div className="space-y-4 pt-2">
            {pairsFor.map((p) => (
              <div key={p}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-[12px] font-bold text-text">{pairLabel(p)}</p>
                  <span className="text-[10px] text-muted">normalized spread % · real observations</span>
                </div>
                <SpreadChart pairId={p} range={range} showBand={false} height={120} />
              </div>
            ))}
          </div>
        )}

        {tab === 'Historical Data' && (
          <div className="pt-2">
            {series.loading ? (
              <ChartSkeleton height={280} />
            ) : series.error ? (
              <ChartUnavailable height={200} message={`Backend unavailable: ${series.error}`} />
            ) : series.data && series.data.points.length > 0 ? (
              <div className="overflow-x-auto thin-scroll">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-muted border-b border-border">
                      <th className="py-2 pr-3">Trade date</th>
                      <th className="py-2 pr-3">Normalized ₹/fine g</th>
                      <th className="py-2 pr-3">Source status</th>
                      <th className="py-2">Derivation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {series.data.points.slice(-30).reverse().map((p, i) => (
                      <tr key={i} className="border-b border-border/40">
                        <td className="py-2 pr-3 text-[11.5px] text-muted">{p.trade_date}</td>
                        <td className="py-2 pr-3 text-[12px] font-semibold text-text">{p.normalized_value.toFixed(2)}</td>
                        <td className="py-2 pr-3 text-[11.5px] text-text">{p.source_status}</td>
                        <td className="py-2 text-[11px] text-muted">{p.derivation_method}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <ChartUnavailable
                height={200}
                message="No normalized history for this contract yet — the daily EOD job has not ingested verified bars."
              />
            )}
            <p className="text-[10px] text-muted mt-2">
              {series.data
                ? `Showing last ${Math.min(30, series.data.points.length)} of ${series.data.points.length} stored observations.`
                : ''}
            </p>
          </div>
        )}

        {tab === 'Specifications' && (
          <div className="pt-2 max-w-xl">
            {spec ? (
              <>
                <table className="w-full text-left">
                  <tbody>
                    {[
                      ['Symbol', selected],
                      ['Trading unit', `${spec.trading_unit_grams} g`],
                      ['Quoted basis', `per ${spec.quote_grams} g`],
                      ['Purity', `${spec.purity_per_mille} / 1000 fine`],
                      ['Fine content quoted', `${(spec.quote_grams * spec.purity_per_mille) / 1000} g`],
                      ['Spec valid from', spec.valid_from],
                      ['Spec valid to', spec.valid_to ?? 'current'],
                      ['Verification', spec.verification_status],
                      ['Source document', spec.source_document_id],
                      ['Notes', spec.notes ?? '—'],
                    ].map(([k, v]) => (
                      <tr key={k} className="border-b border-border/40">
                        <td className="py-2.5 pr-3 text-[12px] text-muted font-medium">{k}</td>
                        <td className="py-2.5 text-[12.5px] font-semibold text-text">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-3 bg-appBg border border-border rounded-lg p-3 text-[11px] text-muted leading-relaxed">
                  Specifications come from the backend's verified contract-spec table with effective-dated validity. Changes are operator-approved; nothing here is assumed valid for all history.
                </div>
              </>
            ) : (
              <ChartUnavailable height={140} message="No verified specification loaded yet for this contract." />
            )}
          </div>
        )}
      </Panel>
    </div>
  )
}
