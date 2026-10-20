// Data-source mode selection: local | api | hybrid.
//
//  - local:   only the existing TypeScript demo datasets (current behaviour).
//  - api:     the backend is the source of truth; failures surface as errors.
//  - hybrid:  backend for market data/analytics when reachable, local demo
//             content otherwise, ALWAYS with an explicit data-source label.
//
// The backend being offline must never silently pass local data off as
// backend-verified market output.

export type DataMode = 'local' | 'api' | 'hybrid'

export function dataMode(): DataMode {
  const env = (import.meta as unknown as { env?: Record<string, string> }).env ?? {}
  const raw = (env.VITE_DATA_MODE ?? 'local').toLowerCase()
  return raw === 'api' || raw === 'hybrid' ? raw : 'local'
}

export function isBackendDriven(): boolean {
  return dataMode() !== 'local'
}

/** Outcome of a backend-backed fetch attempt in hybrid/api mode. */
export type BackendResult<T> =
  | { source: 'backend'; data: T; note: string }
  | { source: 'local-fallback'; data: null; note: string } // hybrid only
  | { source: 'error'; data: null; note: string; code?: string } // api mode

export interface FetchOptions {
  /** Human-readable description shown when data comes from the backend. */
  backendNote?: string
  fallbackNote?: string
}

export interface ModeOutcome<T> {
  data: T | null
  mode: 'backend' | 'local' | 'error'
  note: string
  code?: string
}

export async function withMode<T>(
  backendFetch: () => Promise<T>,
  opts: FetchOptions = {},
): Promise<ModeOutcome<T>> {
  const mode = dataMode()
  if (mode === 'local') {
    return { data: null, mode: 'local', note: '' }
  }
  try {
    const data = await backendFetch()
    return {
      data,
      mode: 'backend',
      note: opts.backendNote ?? 'Live backend data (provisional, activity-implied).',
    }
  } catch (e) {
    if (mode === 'hybrid') {
      return {
        data: null,
        mode: 'local',
        note:
          opts.fallbackNote ??
          'Backend unavailable — showing local illustrative data (not backend-verified).',
      }
    }
    // api mode: explicit error state, never a fake success.
    const code = e instanceof Error && 'code' in e ? String((e as { code: string }).code) : undefined
    return {
      data: null,
      mode: 'error',
      note: opts.fallbackNote ?? 'Backend unavailable. Retry later.',
      code,
    }
  }
}

/** Status labels the UI may surface (honest data-source wording). */
export const DATA_SOURCE_LABELS: Record<DataMode, string> = {
  local: 'Local demo mode — illustrative data, not a live MCX feed',
  api: 'Backend mode — analytics from the MCX Gold Intelligence API (provisional)',
  hybrid: 'Hybrid mode — backend market data when available; local demo otherwise',
}
