import { useMemo, useState } from 'react'
import {
  BrainCircuit,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  ShieldCheck,
  IndianRupee,
  History as HistoryIcon,
  Scale,
} from 'lucide-react'
import { Panel } from '../components/Panel'
import { StatusBadge, statusTone } from '../components/StatusBadge'
import { trainingForPair } from '../data/noveltyTraining'
import { TEST_OBSERVATIONS } from '../data/testObservations'
import { ALL_PAIRS, CONTRACT_MAP } from '../data/contracts'
import { scoreObservation, classifyDisposition, type ScoreResult } from '../lib/anomalyScore'
import { pairLabel } from '../lib/filters'
import type { NoveltyObservation } from '../types'

export function ModelPage() {
  const [pairId, setPairId] = useState('GOLDM-GOLDTEN')
  const [obsId, setObsId] = useState('OBS-01')
  const [trainedPair, setTrainedPair] = useState<string | null>(null)
  const [trainedStats, setTrainedStats] = useState<{ n: number; median: number; mad: number; note: string } | null>(null)

  const pairObs = useMemo(() => TEST_OBSERVATIONS.filter((o) => o.pairId === pairId), [pairId])
  const selectedObs = pairObs.find((o) => o.id === obsId) ?? pairObs[0]
  const training = useMemo(() => trainingForPair(pairId), [pairId])

  const result: ScoreResult | null = useMemo(() => {
    if (!selectedObs || !trainedPair || trainedPair !== pairId) return null
    const spreads = training.filter((o) => o.id !== selectedObs.id).map((o) => o.spreadPct)
    return scoreObservation(selectedObs, spreads)
  }, [selectedObs, trainedPair, pairId, training])

  const calibrate = () => {
    const spreads = training.map((o) => o.spreadPct)
    const r = scoreObservation(training[0], spreads) // median/MAD computed on full training sample
    setTrainedPair(pairId)
    setTrainedStats({ n: r.stats.n, median: r.stats.median, mad: r.stats.mad, note: r.stats.fallNote })
  }

  const disposition = useMemo(() => {
    if (!result) return null
    const liquidityOk = selectedObs.volumeRatio > 0.6 && selectedObs.openInterestRatio > 0.6
    const expiryOk = selectedObs.daysToExpiry > 10
    const costOk = Math.abs(result.robustZ) < 5
    const convergenceOk = selectedObs.daysToExpiry > 12
    return classifyDisposition(result.isAnomaly, liquidityOk, expiryOk, costOk, convergenceOk)
  }, [result, selectedObs])

  const liquidityOk = selectedObs ? selectedObs.volumeRatio > 0.6 && selectedObs.openInterestRatio > 0.6 : false
  const expiryOk = selectedObs ? selectedObs.daysToExpiry > 10 : false
  const costOk = result ? Math.abs(result.robustZ) < 5 : false

  return (
    <div className="space-y-4">
      {/* Header strip */}
      <div className="bg-card border border-border rounded-xl p-4 flex flex-wrap items-center gap-3 shadow-panel">
        <span className="w-9 h-9 rounded-lg bg-maroon text-warmwhite flex items-center justify-center"><BrainCircuit size={17} /></span>
        <div>
          <h2 className="text-[15px] font-extrabold text-text" style={{ fontFamily: 'Georgia, serif' }}>Novelty Detection — Normality Learning</h2>
          <p className="text-[11.5px] text-muted">Train on mostly-normal observations → learn the normal region → score a new, unseen observation. Robust statistical baseline (median + MAD), not an Isolation Forest.</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={pairId}
            onChange={(e) => {
              setPairId(e.target.value)
              setObsId(TEST_OBSERVATIONS.find((o) => o.pairId === e.target.value)!.id)
            }}
            className="bg-card border border-border rounded-lg px-3 py-2 text-[12px] font-bold text-maroon outline-none"
          >
            {ALL_PAIRS.map((p) => (
              <option key={p.pairId} value={p.pairId}>{pairLabel(p.pairId)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* 1. Training panel */}
        <Panel
          title="1 · Normality-learning panel"
          subtitle="Calibration data: mostly-normal cross-contract behaviour"
          icon={<ShieldCheck size={15} />}
        >
          <div className="grid grid-cols-3 gap-2 mb-3">
            {[
              ['Training size', trainedStats ? `${trainedStats.n} obs` : '—'],
              ['Training period', 'Aug 4 – Oct 8, 2026'],
              ['Mostly-normal share', '~94% normal'],
            ].map(([k, v]) => (
              <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                <p className="text-[13px] font-extrabold text-text mt-0.5">{v}</p>
              </div>
            ))}
          </div>

          {/* Distribution visual */}
          <FeatureSpace
            training={training.map((o) => o.spreadPct)}
            newPoint={trainedPair === pairId && selectedObs ? selectedObs.spreadPct : null}
            isAnomaly={result?.isAnomaly ?? false}
            showNew={!!result}
          />

          <div className="flex items-center gap-3 mt-3">
            <button
              onClick={calibrate}
              className="flex items-center gap-2 bg-maroon hover:bg-deep text-warmwhite font-bold text-[12.5px] px-4 py-2.5 rounded-lg transition-colors"
            >
              <Play size={13} /> {trainedPair === pairId ? 'Re-learn normal behaviour' : 'Learn Normal Behaviour'}
            </button>
            {trainedStats && (
              <StatusBadge tone={trainedPair === pairId ? 'green' : 'amber'} dot>
                {trainedPair === pairId ? 'Calibrated for this pair' : 'Calibration stale — pair changed'}
              </StatusBadge>
            )}
          </div>

          {trainedStats && (
            <div className="mt-3 bg-appBg border border-border rounded-lg p-3 text-[11.5px] leading-relaxed">
              <p><strong>Learned statistics (computed locally, not stored):</strong></p>
              <p className="mt-1 text-muted">
                Training median <strong className="text-text">{trainedStats.median.toFixed(3)}%</strong> · robust scale (MAD) <strong className="text-text">{trainedStats.mad.toFixed(3)}</strong> · n = {trainedStats.n}. {trainedStats.note}
              </p>
            </div>
          )}
        </Panel>

        {/* 2. New observation panel */}
        <Panel
          title="2 · New-observation panel"
          subtitle="Held-out scenarios — excluded from training statistics before scoring"
          icon={<AlertTriangle size={15} />}
        >
          <div className="grid grid-cols-2 gap-2">
            {pairObs.map((o) => (
              <button
                key={o.id}
                onClick={() => setObsId(o.id)}
                className={`rounded-lg border p-2.5 text-left transition-all ${
                  selectedObs?.id === o.id
                    ? 'border-maroon bg-maroon/5 ring-1 ring-maroon/30'
                    : 'border-border bg-appBg hover:bg-warmwhite'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <p className="text-[11.5px] font-bold text-text leading-tight">{o.scenarioLabel}</p>
                  <StatusBadge tone={o.expectedHint === 'normal' ? 'green' : 'red'}>
                    {o.expectedHint === 'normal' ? 'normal' : 'unusual'}
                  </StatusBadge>
                </div>
                <p className="text-[10px] text-muted mt-1">spread {o.spreadPct.toFixed(2)}% · vol ×{o.volumeRatio.toFixed(2)}</p>
              </button>
            ))}
          </div>

          {selectedObs && (
            <div className="mt-3 bg-appBg border border-border rounded-lg p-3">
              <p className="text-[12px] font-bold text-text">{selectedObs.scenarioLabel}</p>
              <p className="text-[11.5px] text-muted mt-1 leading-relaxed">{selectedObs.narrative}</p>
              <div className="grid grid-cols-4 gap-2 mt-2.5">
                {[
                  ['Spread', `${selectedObs.spreadPct.toFixed(2)}%`],
                  ['Vol ratio', `×${selectedObs.volumeRatio.toFixed(2)}`],
                  ['OI ratio', `×${selectedObs.openInterestRatio.toFixed(2)}`],
                  ['Expiry', `${selectedObs.daysToExpiry} d`],
                ].map(([k, v]) => (
                  <div key={k} className="bg-card border border-border rounded-md px-2 py-1.5 text-center">
                    <p className="text-[8.5px] uppercase font-semibold text-muted">{k}</p>
                    <p className="text-[11.5px] font-bold text-text">{v}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* 3. Result panel */}
      <Panel
        title="3 · Statistical anomaly score"
        subtitle="Modified z-score: M = 0.6745 × (x − median) / MAD — screening threshold |M| ≥ 3.5"
        icon={<Scale size={15} />}
      >
        {!result ? (
          <div className="py-10 text-center">
            <BrainCircuit size={30} className="mx-auto text-muted/40" />
            <p className="text-[13px] font-bold text-text mt-3">Calibration required before scoring</p>
            <p className="text-[11.5px] text-muted mt-1 max-w-md mx-auto leading-relaxed">
              Click <strong>&ldquo;Learn Normal Behaviour&rdquo;</strong> to compute the training distribution first — the held-out observation is excluded from its own training statistics.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,4fr)] gap-5">
            <div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  ['New observation', `${selectedObs!.spreadPct.toFixed(2)}%`],
                  ['Training median', `${result.stats.median.toFixed(2)}%`],
                  ['MAD (scale)', result.stats.mad.toFixed(3)],
                  ['Modified z', result.robustZ.toFixed(2)],
                ].map(([k, v]) => (
                  <div key={k} className="bg-appBg border border-border rounded-lg p-2.5 text-center">
                    <p className="text-[9px] uppercase tracking-wide text-muted font-semibold">{k}</p>
                    <p className={`text-[14px] font-extrabold mt-0.5 ${k === 'Modified z' ? (result.isAnomaly ? 'text-[#B33838]' : 'text-[#2E6447]') : 'text-text'}`}>{v}</p>
                  </div>
                ))}
              </div>

              <div className={`mt-3 rounded-xl border p-4 ${
                result.isAnomaly ? 'bg-[#B33838]/8 border-[#B33838]/30' : 'bg-[#3F8061]/8 border-[#3F8061]/30'
              }`}>
                <div className="flex items-center gap-2">
                  {result.isAnomaly
                    ? <XCircle size={18} className="text-[#B33838]" />
                    : <CheckCircle2 size={18} className="text-[#2E6447]" />}
                  <p className={`text-[14px] font-extrabold ${result.isAnomaly ? 'text-[#8C2B2B]' : 'text-[#2E6447]'}`}>
                    {result.isAnomaly ? 'ANOMALOUS' : 'NORMAL'}
                  </p>
                  <StatusBadge tone={statusTone(result.severity)}>{result.severity}</StatusBadge>
                  <span className="ml-auto text-[11px] font-semibold text-muted">severity score {result.score.toFixed(2)} / 1.00</span>
                </div>
                <p className="text-[12px] text-text leading-relaxed mt-2">{result.explanation}</p>
              </div>

              {/* Severity meter */}
              <div className="mt-3">
                <div className="flex items-center justify-between text-[10px] text-muted mb-1">
                  <span>0 — normal</span>
                  <span>0.58 — threshold (|z| 3.5)</span>
                  <span>1.00 — max</span>
                </div>
                <div className="h-2.5 rounded-full bg-appBg border border-border overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${result.score * 100}%`, background: result.isAnomaly ? '#B33838' : '#3F8061' }}
                  />
                </div>
              </div>
            </div>

            {/* 4. Validation + explanation */}
            <div className="space-y-3">
              <div className="bg-appBg border border-border rounded-xl p-3.5">
                <p className="text-[12px] font-bold text-text mb-2">Post-detection validation</p>
                <div className="space-y-1.5">
                  <CheckRow ok={liquidityOk} label="Liquidity" detail={liquidityOk ? 'Flow ratios inside acceptable range' : 'Thin-book signature — volume/OI collapsed'} />
                  <CheckRow ok={expiryOk} label="Contract expiry" detail={expiryOk ? `${selectedObs!.daysToExpiry} days to expiry — outside distortion window` : `Only ${selectedObs!.daysToExpiry} days to expiry — settlement mechanics likely`} />
                  <CheckRow ok={costOk} label="Transaction-cost assumption" detail={costOk ? 'Illustrative cost model leaves residual edge in scenario' : 'Extreme excursion — costs likely dominate in scenario'} />
                  <CheckRow ok={liquidityOk} label="Slippage potential" detail={liquidityOk ? 'Moderate slippage assumed (demo)' : 'High slippage risk on thin leg'} />
                  <CheckRow ok={convergenceOk(selectedObs!)} label="Historical convergence" detail={convergenceOk(selectedObs!) ? 'Similar scenarios reverted within ~4 sessions (illustrative)' : 'Short window — convergence untestable in scenario'} />
                </div>
                {disposition && (
                  <div className={`mt-3 rounded-lg p-2.5 flex items-center gap-2 ${
                    disposition === 'Actionable' ? 'bg-[#3F8061]/12 text-[#2E6447]'
                    : disposition === 'Watch' ? 'bg-[#B87928]/12 text-[#8F5D1D]'
                    : 'bg-appBg text-muted'
                  }`}>
                    <ShieldCheck size={14} />
                    <p className="text-[12px] font-bold">Final classification: {disposition}</p>
                    <span className="ml-auto text-[9.5px] text-muted">scenario classification only</span>
                  </div>
                )}
              </div>

              <div className="bg-[#B87928]/8 border border-[#B87928]/25 rounded-xl p-3.5 text-[11.5px] text-[#8F5D1D] leading-relaxed">
                <p className="flex items-start gap-1.5 font-bold"><Info size={13} className="mt-0.5 shrink-0" /> What this result does and does not mean</p>
                <p className="mt-1.5">
                  A high score means the observation is <strong>unusual relative to the calibration sample</strong> under a robust screening rule. It does not prove economic mispricing, guarantee convergence, or imply a profitable trade. Tradability and backtest evidence are separate, unimplemented questions.
                </p>
              </div>
            </div>
          </div>
        )}
      </Panel>

      {/* Method footer */}
      <div className="bg-card border border-border rounded-xl p-4 shadow-panel text-[11.5px] text-muted leading-relaxed">
        <p><strong className="text-text">Method:</strong> robust statistical novelty baseline (median + MAD modified z-score) computed in-browser on {training.length} illustrative mostly-normal observations per pair. Threshold |M| ≥ 3.5 is a configurable screening heuristic. If MAD is near zero, an IQR-based fallback scale is used; a documented floor prevents division by zero. No Isolation Forest, production model, or live MCX data is involved.</p>
      </div>
    </div>
  )
}

function convergenceOk(o: NoveltyObservation): boolean {
  return o.daysToExpiry > 12
}

function CheckRow({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <div className="flex items-start gap-2">
      {ok ? <CheckCircle2 size={14} className="text-[#2E6447] mt-0.5 shrink-0" /> : <XCircle size={14} className="text-[#B33838] mt-0.5 shrink-0" />}
      <div className="min-w-0">
        <p className="text-[11.5px] font-bold text-text leading-tight">{label} <span className={`text-[9.5px] font-semibold ${ok ? 'text-[#2E6447]' : 'text-[#8C2B2B]'}`}>· {ok ? 'PASS' : 'FLAG'}</span></p>
        <p className="text-[10.5px] text-muted leading-snug">{detail}</p>
      </div>
    </div>
  )
}

/** Schematic feature-space: training histogram + held-out point marker. */
function FeatureSpace({
  training,
  newPoint,
  isAnomaly,
  showNew,
}: {
  training: number[]
  newPoint: number | null
  isAnomaly: boolean
  showNew: boolean
}) {
  const W = 460
  const H = 130
  const pad = 26
  const all = newPoint != null ? [...training, newPoint] : training
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const x = (v: number) => pad + ((v - min) / span) * (W - pad * 2)

  // bin the training points
  const bins = 22
  const counts = new Array(bins).fill(0)
  training.forEach((v) => {
    const b = Math.min(bins - 1, Math.floor(((v - min) / span) * bins))
    counts[b]++
  })
  const maxC = Math.max(...counts, 1)

  return (
    <div className="bg-warmwhite border border-border rounded-lg p-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Feature space: training distribution and new observation">
        {/* learned normal region */}
        <rect
          x={x(min + span * 0.18)}
          width={x(min + span * 0.82) - x(min + span * 0.18)}
          y={8}
          height={H - 30}
          fill="#3F8061"
          opacity={0.10}
        />
        <text x={x(min + span * 0.5)} y={H - 8} textAnchor="middle" fontSize={8.5} fill="#76645B">
          spread (%) — learned normal region shaded
        </text>
        {counts.map((cnt, i) => {
          const bw = (W - pad * 2) / bins
          const h = (cnt / maxC) * (H - 45)
          return (
            <rect
              key={i}
              x={pad + i * bw + 1}
              y={H - 22 - h}
              width={bw - 2}
              height={h}
              rx={1.5}
              fill="#662023"
              opacity={0.55}
            />
          )
        })}
        {showNew && newPoint != null && (
          <g>
            <line x1={x(newPoint)} y1={4} x2={x(newPoint)} y2={H - 22} stroke={isAnomaly ? '#B33838' : '#3F8061'} strokeWidth={1.5} strokeDasharray="3 3" />
            <circle cx={x(newPoint)} cy={12} r={5} fill={isAnomaly ? '#B33838' : '#3F8061'} stroke="#FFF9F3" strokeWidth={1.5} />
            <text x={Math.min(W - 60, Math.max(24, x(newPoint)))} y={10} textAnchor="middle" fontSize={8.5} fontWeight={700} fill={isAnomaly ? '#8C2B2B' : '#2E6447'}>
              NEW
            </text>
          </g>
        )}
      </svg>
    </div>
  )
}
