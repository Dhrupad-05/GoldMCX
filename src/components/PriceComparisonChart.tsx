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
import { normalizedSeriesForContracts } from '../data/marketSeries'
import { sliceForRange, type TimeRange } from '../lib/filters'
import type { ContractId } from '../types'

export const SERIES_COLORS: Record<ContractId, string> = {
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
  ids: ContractId[]
  range: TimeRange
  onRangeChange?: (r: TimeRange) => void
  height?: number
  title?: string
}) {
  const [localRange, setLocalRange] = useState<TimeRange>('1M')
  const r = range ?? localRange
  const setR = onRangeChange ?? setLocalRange

  const data = useMemo(() => sliceForRange(normalizedSeriesForContracts(ids), r), [ids, r])

  return (
    <div>
      {title && (
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[12.5px] font-bold text-text">{title}</p>
          {setR && (
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
          )}
        </div>
      )}
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
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
