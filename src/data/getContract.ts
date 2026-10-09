import type { ViewId } from '../types'

export function viewIdFor(targetId: string): ViewId | null {
  if (['dashboard', 'signals', 'contracts', 'comparison', 'model', 'insights', 'learn', 'backtest', 'events'].includes(targetId)) {
    if (targetId === 'events') return 'backtest'
    return targetId as ViewId
  }
  return null
}
