import { get, post } from './apiClient'

export interface IngestionScanResult {
  run_id: string
  counts: Record<string, unknown>
  errors: string[]
}

export interface QualityReport {
  run_id: string | null
  overall_status: string
  counts: Record<string, unknown>
  by_class: Record<string, number>
  by_format: Record<string, number>
  source_status_totals: Record<string, number>
  rejection_reasons: Record<string, number>
}

export function scanSources(): Promise<IngestionScanResult> {
  return post('/api/v1/ingestion/scan')
}

export function importSources(): Promise<IngestionScanResult> {
  return post('/api/v1/ingestion/import')
}

export function qualityReport(): Promise<QualityReport> {
  return get('/api/v1/ingestion/quality-report')
}
