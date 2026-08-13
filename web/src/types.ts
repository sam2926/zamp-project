/** Types mirroring API.md. The contract is stable; this file is the single place
 *  it is written down, so a change there is a compile error here. */

export type FieldStatus = 'ok' | 'review' | 'repaired' | 'missing'
export type DocumentStatus = 'processing' | 'done' | 'failed'

/** [left, top, right, bottom] as fractions of the page, 0–1. */
export type Box = [number, number, number, number]

export interface Field {
  name: string
  /** null when status is 'missing'. */
  value: string | null
  confidence: number
  status: FieldStatus
  page: number
  /** null when the value was never located on the page. */
  box: Box | null
  /** Present on anything not 'ok'. Always shown. */
  reason?: string
  /** Present only on 'repaired' — what the value was before. */
  original?: string
}

export interface LineItem {
  id: number
  fields: Field[]
}

export interface ValidationRule {
  rule: string
  passed: boolean
  detail?: string
  suspect_fields?: string[]
}

export interface ExtractedDocument {
  id: string
  filename: string
  status: DocumentStatus
  pages: number
  /** Present when status is 'failed'. */
  error?: string
  layout?: { known: boolean; seen_count: number; used_template: boolean }
  processing?: { ms: number; model_called: boolean }
  fields: Field[]
  line_items: LineItem[]
  validation: ValidationRule[]
}

export interface UploadAccepted {
  id: string
  filename: string
  status: DocumentStatus
  pages: number
}

export interface QueueItem {
  id: string
  filename: string
  uploaded: string
  vendor: string
  total: string
  fields_ok: number
  fields_review: number
  min_confidence: number
}

export interface QueuePage {
  total: number
  items: QueueItem[]
}

export interface CalibrationBucket {
  bucket: string
  predicted: number
  actual: number
  n: number
}

export interface FieldAccuracy {
  field: string
  n: number
  f1: number
}

export interface Stats {
  documents: number
  deterministic_coverage: number
  auto_accepted: number
  calibration: CalibrationBucket[]
  per_field: FieldAccuracy[]
  by_layout: {
    seen: { f1: number; n?: number }
    unseen: { f1: number; n?: number }
  }
}

/** Live progress. A document walks these stages; the terminal one is always 'done',
 *  and the outcome it carries is the `status` below — there is no 'failed' stage. */
export type PipelineStage =
  | 'queued'
  | 'reading'
  | 'matching'
  | 'extracting'
  | 'checking'
  | 'done'

export type Outcome = 'ok' | 'review' | 'not_found' | 'unreadable'

export interface ProgressJob {
  id: string
  filename: string
  pages: number | null
  stage: PipelineStage
  /** null until the document is done. */
  status: Outcome | null
  /** true once a human has supplied the value; such rows leave the review queue. */
  corrected: boolean
  amount_due: string | null
  confidence: number | null
  reason: string | null
  layout: { known: boolean | null; seen_count: number }
  model_called: boolean | null
  created_at: number
  started_at: number | null
  finished_at: number | null
  stage_ms: Partial<Record<PipelineStage, number>>
}

export interface ProgressResponse {
  jobs: ProgressJob[]
  ocr_ready: boolean
  index_ready: boolean
}

/** The result of a reviewer correcting a value: it is always resolved to 'ok', and the
 *  server reports how the correction feeds the region-learning (see relearn.py). */
export interface CorrectionResult {
  value: string
  status: 'ok'
  /** Whether the corrected value was found on the page (so its box can teach the region). */
  located: boolean
  corrections: number
  threshold: number
  region_moved: boolean
}
