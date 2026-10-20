// Thin HTTP client for the MCX Gold Intelligence backend.
// No analytics logic lives here: the backend is the source of truth in api/hybrid modes.

export interface ApiError {
  code: string
  message: string
}

export class ApiRequestError extends Error {
  code: string
  status: number

  constructor(err: ApiError, status: number) {
    super(err.message)
    this.name = 'ApiRequestError'
    this.code = err.code
    this.status = status
  }
}

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
const DEFAULT_TIMEOUT_MS = 10_000

export function apiBaseUrl(): string {
  const env = (import.meta as unknown as { env?: Record<string, string> }).env ?? {}
  const raw = (env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/$/, '')
  return raw
}

export function apiPrefix(): string {
  const env = (import.meta as unknown as { env?: Record<string, string> }).env ?? {}
  return (env.VITE_API_PREFIX ?? '/api/v1').replace(/\/$/, '')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { Accept: 'application/json', ...(init?.headers ?? {}) },
    })
  } catch (e) {
    clearTimeout(timer)
    throw new ApiRequestError(
      { code: 'backend_unavailable', message: 'Backend is unreachable.' },
      0,
    )
  }
  clearTimeout(timer)

  if (!res.ok) {
    let payload: { error?: ApiError } = {}
    try {
      payload = await res.json()
    } catch {
      // non-JSON error body
    }
    throw new ApiRequestError(
      payload.error ?? { code: 'unknown_error', message: `HTTP ${res.status}` },
      res.status,
    )
  }
  return (await res.json()) as T
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
