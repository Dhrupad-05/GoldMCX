import type { ReactNode } from 'react'

const TONES: Record<string, { bg: string; text: string; ring: string }> = {
  green: { bg: 'bg-[#3F8061]/10', text: 'text-[#2E6447]', ring: 'ring-[#3F8061]/30' },
  amber: { bg: 'bg-[#B87928]/10', text: 'text-[#8F5D1D]', ring: 'ring-[#B87928]/30' },
  red: { bg: 'bg-[#B33838]/10', text: 'text-[#8C2B2B]', ring: 'ring-[#B33838]/30' },
  maroon: { bg: 'bg-[#662023]/10', text: 'text-[#662023]', ring: 'ring-[#662023]/25' },
  gold: { bg: 'bg-[#C99A53]/15', text: 'text-[#8F6A2E]', ring: 'ring-[#C99A53]/40' },
  neutral: { bg: 'bg-[#76645B]/10', text: 'text-muted', ring: 'ring-[#DCCBBE]' },
}

export function StatusBadge({
  tone,
  children,
  dot = false,
}: {
  tone: keyof typeof TONES | string
  children: ReactNode
  dot?: boolean
}) {
  const t = TONES[tone] ?? TONES.neutral
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ${t.bg} ${t.text} ${t.ring}`}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}

export function statusTone(status: string): string {
  switch (status) {
    case 'High':
    case 'Anomaly':
      return 'red'
    case 'Watch':
      return 'amber'
    case 'Opportunity':
      return 'green'
    case 'Normal':
      return 'green'
    case 'Actionable':
      return 'green'
    case 'Ignore':
      return 'neutral'
    case 'Healthy':
      return 'green'
    case 'Adequate':
      return 'amber'
    case 'Low':
      return 'red'
    default:
      return 'neutral'
  }
}
