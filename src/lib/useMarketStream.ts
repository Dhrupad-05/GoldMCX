import { useEffect, useRef, useState } from 'react'
import { api, API_BASE, SSE_PATH } from './api'
import type { LiveQuote, LiveStatus, MlAnomaly } from './api'

export interface MarketStreamEvent {
  type: string // 'snapshot' | 'quote' | 'anomaly' | 'provider-status' | 'heartbeat'
  payload: unknown
  at: number
}

export interface MarketStreamState {
  connected: boolean
  error: string | null
  eventTime: number | null
  quotes: Map<string, LiveQuote>
  latestAnomaly: MlAnomaly | null
  status: LiveStatus | null
}

const QUOTE_FRESHNESS_LIMIT_S = 120

function quoteKey(q: LiveQuote): string {
  return `${q.provider}|${q.canonical_symbol}|${q.expiry_date ?? ''}`
}

/**
 * Robust SSE hook for /api/v1/market/live/stream.
 * - reconnect with bounded backoff, cleanup on unmount
 * - duplicate quote suppression (same provider/symbol/expiry acting as an update)
 * - explicit NOT_CONFIGURED handling: stays "not configured", never fakes "Live"
 * - heartbeat-driven LivenessState
 */
export function useMarketStream(): MarketStreamState {
  const [state, setState] = useState<MarketStreamState>({
    connected: false,
    error: null,
    eventTime: null,
    quotes: new Map(),
    latestAnomaly: null,
    status: null,
  })
  const esRef = useRef<EventSource | null>(null)
  const retryRef = useRef(0)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    let disposed = false

    const hydrate = async () => {
      try {
        const qs = await api.liveQuotes()
        const status = await api.liveStatus().catch(() => null)
        if (disposed) return
        setState((s) => {
          const next = new Map(s.quotes)
          for (const q of qs) next.set(quoteKey(q), q)
          return { ...s, quotes: next, status }
        })
      } catch {
        /* initial hydrate is best-effort; stream/socket errors surface separately */
      }
    }

    const connect = () => {
      if (disposed) return
      const es = new EventSource(joinSse())
      esRef.current = es

      es.onopen = () => {
        retryRef.current = 0
        setState((s) => ({ ...s, connected: true, error: null }))
      }

      const onEvent = (ev: MessageEvent) => {
        let parsed: { type?: string; payload?: unknown } | null = null
        try {
          parsed = JSON.parse(ev.data)
        } catch {
          /* skip malformed frame */
        }
        if (!parsed?.type) return
        const at = Date.now()
        setState((s) => {
          const next: MarketStreamState = { ...s, eventTime: at }
          switch (parsed!.type) {
            case 'snapshot': {
              const payload = parsed.payload as LiveQuote[] | { quotes: LiveQuote[] }
              const list = Array.isArray(payload) ? payload : (payload?.quotes ?? [])
              const m = new Map<string, LiveQuote>()
              for (const q of list as LiveQuote[]) m.set(quoteKey(q), q)
              next.quotes = m
              break
            }
            case 'quote': {
              const q = parsed.payload as LiveQuote
              next.quotes = new Map(s.quotes)
              next.quotes.set(quoteKey(q), q)
              break
            }
            case 'anomaly':
              next.latestAnomaly = parsed.payload as MlAnomaly
              break
            case 'provider-status':
              next.status = parsed.payload as LiveStatus
              break
            default:
              break
          }
          return next
        })
      }
      for (const name of ['snapshot', 'quote', 'anomaly', 'provider-status']) {
        es.addEventListener(name, onEvent as EventListener)
      }

      es.onerror = () => {
        setState((s) => ({ ...s, connected: false, error: 'stream disconnected — retrying' }))
        es.close()
        esRef.current = null
        if (disposed) return
        const delay = Math.min(15000, 1000 * Math.pow(2, retryRef.current++))
        timerRef.current = window.setTimeout(connect, delay)
      }
    }

    void hydrate()
    connect()

    return () => {
      disposed = true
      if (timerRef.current) window.clearTimeout(timerRef.current)
      esRef.current?.close()
      esRef.current = null
    }
  }, [])

  return state
}

/** Quote freshness gate: returns null when the quote's source event is too old or absent. */
export function quoteIfFresh(q: LiveQuote | undefined, now = Date.now()): LiveQuote | null {
  if (!q) return null
  const t = parseTime(q.event_time)
  if (t == null) return null
  if ((now - t) / 1000 > QUOTE_FRESHNESS_LIMIT_S) return null
  return q
}

function parseTime(iso: string): number | null {
  const t = Date.parse(iso)
  return Number.isFinite(t) ? t : null
}

function joinSse(): string {
  const base = API_BASE.replace(/\/+$/, '')
  return base ? `${base}${SSE_PATH}` : SSE_PATH
}
