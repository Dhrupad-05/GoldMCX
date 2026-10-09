import { SIGNALS } from './signals'

export function signalForPair(pairId: string) {
  return SIGNALS.find((s) => s.pairId === pairId)
}
