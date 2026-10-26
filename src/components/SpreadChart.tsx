import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { useMemo } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { comparisonToChartRows, sliceSeries } from '../lib/chartData'
import type { TimeRange } from '../lib/filters'
import { ChartSkeleton, ChartUnavailable } from './PriceComparisonChart'

export function SpreadChart({
  pairId,
  range,
  showBand = true,
  height = 170,
}: {
  pairId: string
  range: TimeRange
  showBand?: boolean
  height?: number
}) {
  const rangeDays: Record<TimeRange, number> = { '1M': 30, '3M': 90, '6M': 182, '1Y': 365 }
  const series = useApi(
    () => api.comparison(pairId, rangeDays[range]),
    [pairId, range],
  )

  const data = useMemo(() => series.data ? comparisonToChartRows(series.data) : [], [series.data])
  const sliced = useMemo(() => sliceSeries(data, range), [data, range])

  const band = useMemo(() => {
    const vals = data.map((p) => p.spreadPct)
    return robustBand(vals)
  }, [data])

  if (series.loading) return <ChartSkeleton height={height} />
  if (series.error)
    return <ChartUnavailable height={height} message={`Backend unavailable: ${series.error}`} />
  if (sliced.length === 0)
    return (
      <ChartUnavailable
        height={height}
        message={`No overlapping verified observations for ${pairId.replace('-', ' ↔ ')} in this window. Missing-leg dates are skipped, never filled.`}
      />
    )

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={sliced} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="#DCCBBE" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9.5, fill: '#76645B' }}
            tickFormatter={(d: string) => d.slice(5).replace('-', '/')}
            minTickGap={40}
            axisLine={{ stroke: '#DCCBBE' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 9.5, fill: '#76645B' }}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            width={46}
            axisLine={false}
            tickLine={false}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{ background: '#FFF9F3', border: '1px solid #DCCBBE', borderRadius: 8, fontSize: 11.5 }}
            formatter={(v: number | string) => [`${Number(v).toFixed(2)}%`, 'Spread']}
          />
          {showBand && (
            <>
              <ReferenceLine y={band.med} stroke="#C99A53" strokeDasharray="4 4" label={{ value: 'normal centre', position: 'insideTopRight', fontSize: 9, fill: '#8F6A2E' }} />
              <ReferenceLine y={band.hi} stroke="#B33838" strokeDasharray="2 5" strokeOpacity={0.55} label={{ value: 'robust band', position: 'insideTopRight', fontSize: 9, fill: '#8C2B2B' }} />
              <ReferenceLine y={band.lo} stroke="#B33838" strokeDasharray="2 5" strokeOpacity={0.55} />
            </>
          )}
          <Line type="monotone" dataKey="spreadPct" stroke="#662023" strokeWidth={1.8} dot={false} name="Spread %" connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Same robust statistic family the backend uses (median / MAD band). */
function robustBand(vals: number[]): { med: number; lo: number; hi: number } {
  if (vals.length === 0) return { med: 0, lo: -1, hi: 1 }
  const sorted = [...vals].sort((a, b) => a - b)
  const med = median(sorted)
  const dev = sorted.map((v) => Math.abs(v - med))
  const mad = median([...dev].sort((a, b) => a - b)) * 2.5
  return { med, lo: med - mad, hi: med + mad }
}

function median(sorted: number[]): number {
  const n = sorted.length
  return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2
}
