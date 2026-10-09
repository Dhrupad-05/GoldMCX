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
import { SPREAD_SERIES } from '../data/spreads'
import { sliceForRange } from '../lib/filters'
import type { TimeRange } from '../lib/filters'
import { median } from '../lib/anomalyScore'

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
  const data = useMemo(() => sliceForRange(SPREAD_SERIES[pairId] ?? [], range), [pairId, range])
  const band = useMemo(() => {
    const vals = (SPREAD_SERIES[pairId] ?? []).map((p) => p.spreadPct)
    const med = median(vals)
    const dev = vals.map((v) => Math.abs(v - med))
    const mad = median(dev) * 2.5
    return { med, lo: med - mad, hi: med + mad }
  }, [pairId])

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -14 }}>
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
              <ReferenceLine y={band.hi} stroke="#B33838" strokeDasharray="2 5" strokeOpacity={0.55} label={{ value: 'band edge', position: 'insideTopRight', fontSize: 9, fill: '#8C2B2B' }} />
              <ReferenceLine y={band.lo} stroke="#B33838" strokeDasharray="2 5" strokeOpacity={0.55} />
            </>
          )}
          <Line type="monotone" dataKey="spreadPct" stroke="#662023" strokeWidth={1.8} dot={false} name="Spread %" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
