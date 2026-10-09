import type { TimeRange } from '../lib/filters'

const RANGES: TimeRange[] = ['1M', '3M', '6M', '1Y']

export function RangeTabs({
  value,
  onChange,
  compact = false,
}: {
  value: TimeRange
  onChange: (r: TimeRange) => void
  compact?: boolean
}) {
  return (
    <div className="inline-flex items-center rounded-lg border border-border bg-warmwhite p-0.5">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-colors ${
            value === r
              ? compact
                ? 'bg-card text-text shadow-soft border border-border'
                : 'bg-maroon text-warmwhite'
              : 'text-muted hover:text-text'
          }`}
        >
          {r}
        </button>
      ))}
    </div>
  )
}
