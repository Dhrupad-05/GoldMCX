import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { useMemo, useState } from 'react'
import { api, type ContractSymbol } from '../lib/api'
import { useApi } from '../lib/useApi'
import { seriesToChartRows, sliceSeries } from '../lib/chartData'
import type { TimeRange } from '../lib/filters'

export const SERIES_COLORS: Record<string, string> = {
  GOLDM: '#662023',
  GOLDTEN: '#B33838',
  GOLDGUINEA: '#C99A53',
  GOLDPETAL: '#3F8061',
}

export function PriceComparisonChart({
  ids,
  range,
  onRangeChange,
  height = 210,
  title,
}: {
  ids: ContractSymbol[]
  range?: TimeRange
  onRangeChange?: (r: TimeRange) => void
  height?: number
  title?: string
}) {
  const [localRange, setLocalRange] = useState<TimeRange>('3M')
  const r = range ?? localRange
  const setR = onRangeChange ?? setLocalRange

  const series = useApi(
    async () => {
      const rs = await Promise.all(ids.map((id) => api.contractSeries(id)))
      return seriesToChartRows(rs)
    },
    depsFor(ids),
  )

  const data = useMemo(() => sliceSeries(series.data ?? [], r), [series.data, r])

  return (
    <div>
      {title && (
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[12.5px] font-bold text-text">{title}</p>
          <div className="flex gap-1">
            {(['1M', '3M', '6M', '1Y'] as TimeRange[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setR(opt)}
                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                  r === opt ? 'bg-maroon text-warmwhite' : 'text-muted hover:text-text'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>
      )}
      {series.loading ? (
        <ChartSkeleton height={height} />
      ) : series.error ? (
        <ChartUnavailable
          height={height}
          message={`Backend unavailable: ${series.error}`}
        />
      ) : data.length === 0 ? (
        <ChartUnavailable
          height={height}
          message="No normalized price history available yet. Run the daily EOD sync — no chart is drawn without real, verified observations."
        />
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -12 }}>
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
                tickFormatter={(v: number) => v.toFixed(0)}
                width={48}
                axisLine={false}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip
                contentStyle={{
                  background: '#FFF9F3',
                  border: '1px solid #DCCBBE',
                  borderRadius: 8,
                  fontSize: 11.5,
                }}
                labelFormatter={(d) => `Date: ${d}`}
                formatter={(value: number | string, name: string) => [
                  typeof value === 'number' ? `₹${value.toFixed(2)}/g` : value,
                  name,
                ]}
              />
              <Legend
                wrapperStyle={{ fontSize: 10.5, paddingTop: 4 }}
                iconType="circle"
                iconSize={7}
              />
              {ids.map((id) => (
                <Line
                  key={id}
                  type="monotone"
                  dataKey={id}
                  stroke={SERIES_COLORS[id]}
                  strokeWidth={1.8}
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export function ChartUnavailable({ height, message }: { height: number; message: string }) {
  return (
    <div
      className="flex items-center justify-center rounded-lg border border-border bg-appBg p-4 text-center"
      style={{ minHeight: height }}
    >
      <p className="text-[11.5px] text-muted max-w-sm leading-relaxed">{message}</p>
    </div>
  )
}

export function ChartSkeleton({ height }: { height: number }) {
  return (
    <div
      className="animate-pulse rounded-lg border border-border bg-appBg"
      style={{ height }}
    />
  )
}

function depsFor(ids: ContractSymbol[]): unknown[] {
  return [ids.join(',')]
}
