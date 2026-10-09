import type { Contract, ContractPair, ContractId } from '../types'

export const CONTRACTS: Contract[] = [
  {
    id: 'GOLDM',
    symbol: 'GOLDM',
    displayName: 'Gold Mini',
    tradingUnitGrams: 100,
    quoteGrams: 10,
    purity: 995,
    expiryLabel: 'OCT 2025',
    demoPrice: 72480,
    demoChangePct: -0.8,
    status: 'Active',
    description:
      'Medium-sized gold futures contract. Quoted per 10 g, purity 995; one lot equals 100 g of underlying gold.',
  },
  {
    id: 'GOLDTEN',
    symbol: 'GOLDTEN',
    displayName: 'Gold Ten',
    tradingUnitGrams: 10,
    quoteGrams: 10,
    purity: 999,
    expiryLabel: 'NOV 2025',
    demoPrice: 72935,
    demoChangePct: +2.7,
    status: 'Active',
    description:
      'Standard 10 g gold futures contract. Quoted per 10 g, purity 999 — the benchmark small-lot gold future on MCX.',
  },
  {
    id: 'GOLDGUINEA',
    symbol: 'GOLDGUINEA',
    displayName: 'Gold Guinea',
    tradingUnitGrams: 8,
    quoteGrams: 8,
    purity: 999,
    expiryLabel: 'DEC 2025',
    demoPrice: 57410,
    demoChangePct: +0.5,
    status: 'Active',
    description:
      '8 g coin-linked futures contract, quoted per 7.7 g fine gold after the mandatory 4% coin premium adjustment.',
  },
  {
    id: 'GOLDPETAL',
    symbol: 'GOLDPETAL',
    displayName: 'Gold Petal',
    tradingUnitGrams: 1,
    quoteGrams: 1,
    purity: 999,
    expiryLabel: 'FEB 2026',
    demoPrice: 7120,
    demoChangePct: +3.9,
    status: 'Active',
    description:
      'Smallest gold futures contract (1 g). Prone to retail-driven flows and the widest relative spread behaviour.',
  },
]

export const CONTRACT_MAP: Record<ContractId, Contract> = Object.fromEntries(
  CONTRACTS.map((c) => [c.id, c]),
) as Record<ContractId, Contract>

export const ALL_PAIRS: ContractPair[] = [
  { pairId: 'GOLDM-GOLDTEN', left: 'GOLDM', right: 'GOLDTEN' },
  { pairId: 'GOLDM-GOLDGUINEA', left: 'GOLDM', right: 'GOLDGUINEA' },
  { pairId: 'GOLDM-GOLDPETAL', left: 'GOLDM', right: 'GOLDPETAL' },
  { pairId: 'GOLDTEN-GOLDGUINEA', left: 'GOLDTEN', right: 'GOLDGUINEA' },
  { pairId: 'GOLDTEN-GOLDPETAL', left: 'GOLDTEN', right: 'GOLDPETAL' },
  { pairId: 'REST-GOLDPETAL', left: 'GOLDGUINEA', right: 'GOLDPETAL' },
]

export function pairKey(a: ContractId, b: ContractId): string {
  return ALL_PAIRS.find(
    (p) => (p.left === a && p.right === b) || (p.left === b && p.right === a),
  )?.pairId ?? 'GOLDM-GOLDTEN'
}
