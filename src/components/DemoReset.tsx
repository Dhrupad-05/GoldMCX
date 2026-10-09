import { RotateCcw } from 'lucide-react'

export function DemoReset({ onReset }: { onReset: () => void }) {
  return (
    <button
      onClick={onReset}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-card border border-border text-[11px] font-semibold text-muted hover:text-text hover:bg-warmwhite transition-colors"
      title="Reset demo to initial state"
    >
      <RotateCcw size={11} />
      Reset demo
    </button>
  )
}
