export function Sparkline({
  points,
  color = '#B33838',
  width = 84,
  height = 30,
}: {
  points: number[]
  color?: string
  width?: number
  height?: number
}) {
  if (points.length < 2) return null
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const step = width / (points.length - 1)
  const coords = points.map((v, i) => {
    const x = i * step
    const y = height - 3 - ((v - min) / span) * (height - 6)
    return [x, y]
  })
  const d = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={coords[coords.length - 1][0]} cy={coords[coords.length - 1][1]} r={2.2} fill={color} />
    </svg>
  )
}
