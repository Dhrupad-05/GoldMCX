import { get, ApiRequestError } from './apiClient'
import type { BackendSignal, BackendScoreDetail } from './compatibility'

export async function fetchSignals(limit = 50): Promise<BackendSignal[]> {
  return get(`/api/v1/signals?limit=${limit}`)
}

export async function fetchSignalDetail(id: number): Promise<BackendScoreDetail> {
  return get(`/api/v1/signals/${id}`)
}

export { ApiRequestError }
