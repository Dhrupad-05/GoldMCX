import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from './api'

export interface ApiResource<T> {
  data: T | null
  loading: boolean
  error: string | null
  status: 'loading' | 'ok' | 'error' | 'empty'
  refresh: () => void
}

/**
 * Fetch-hook with loading/error/empty states and manual refresh/retry.
 * Never falls back to local fixtures: API failure surfaces as an explicit
 * error/unavailable state for the page to render.
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): ApiResource<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)

  const run = useCallback(async () => {
    const my = ++seq.current
    setLoading(true)
    setError(null)
    try {
      const d = await fetcher()
      if (seq.current === my) {
        setData(d)
        setLoading(false)
      }
    } catch (e) {
      if (seq.current === my) {
        setData(null)
        setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e))
        setLoading(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    void run()
    return () => {
      seq.current += 1 // ignore stale responses after unmount/dep change
    }
  }, [run])

  return { data, error, loading, status: error ? 'error' : !data ? 'loading' : 'ok', refresh: run }
}
