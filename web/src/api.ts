/** The only place that talks to the network.
 *
 *  Every path is relative: in production FastAPI serves this bundle from the same
 *  origin, and in development Vite proxies /api. Nothing here knows a hostname.
 */
import type {
  CorrectionResult,
  ExtractedDocument,
  Field,
  ProgressResponse,
  QueuePage,
  Stats,
  UploadAccepted,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI puts human-readable text in `detail`. Surface that rather than a code. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError(0, "Couldn't reach the server. Is the API running?")
  }

  if (!response.ok) {
    let message = `The server returned ${response.status}.`
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      /* not JSON — keep the generic message */
    }
    throw new ApiError(response.status, message)
  }

  return response.json() as Promise<T>
}

/** Header carrying the visitor's own LLM key. The server uses it for this one
 *  request and never stores it; a value never touches the URL or query string. */
export const LLM_KEY_HEADER = 'X-LLM-Key'

export function uploadDocument(
  file: File,
  apiKey?: string,
  signal?: AbortSignal,
): Promise<UploadAccepted> {
  const body = new FormData()
  body.append('file', file)
  const headers = apiKey ? { [LLM_KEY_HEADER]: apiKey } : undefined
  return request<UploadAccepted>('/api/documents', { method: 'POST', body, headers, signal })
}

/**
 * Upload with a real progress reading.
 *
 * `fetch` cannot report request-body progress, so this uses XHR. The percentage
 * shown to the user is therefore the actual number of bytes on the wire rather
 * than an animation pretending to be one — and it stops at 100% when the
 * transfer ends, which is where the server's own work begins.
 */
export function uploadDocumentWithProgress(
  file: File,
  onProgress: (fraction: number) => void,
  apiKey?: string,
): { promise: Promise<UploadAccepted>; abort: () => void } {
  const request = new XMLHttpRequest()
  const body = new FormData()
  body.append('file', file)

  const promise = new Promise<UploadAccepted>((resolve, reject) => {
    request.open('POST', '/api/documents')
    if (apiKey) request.setRequestHeader(LLM_KEY_HEADER, apiKey)

    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }

    request.onload = () => {
      let parsed: unknown = null
      try {
        parsed = JSON.parse(request.responseText)
      } catch {
        /* leave null — handled below */
      }

      if (request.status >= 200 && request.status < 300) {
        onProgress(1)
        resolve(parsed as UploadAccepted)
        return
      }

      const detail = (parsed as { detail?: string } | null)?.detail
      reject(new ApiError(request.status, detail ?? `The server returned ${request.status}.`))
    }

    request.onerror = () =>
      reject(new ApiError(0, "Couldn't reach the server. Is the API running?"))
    request.onabort = () => reject(new ApiError(0, 'Upload cancelled.'))

    request.send(body)
  })

  return { promise, abort: () => request.abort() }
}

export function getDocument(id: string, signal?: AbortSignal): Promise<ExtractedDocument> {
  return request<ExtractedDocument>(`/api/documents/${encodeURIComponent(id)}`, { signal })
}

export function listDocuments(
  params: {
    needs_review?: boolean
    limit?: number
    offset?: number
    sort?: 'uploaded' | 'confidence'
  } = {},
  signal?: AbortSignal,
): Promise<QueuePage> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  const suffix = query.toString() ? `?${query}` : ''
  return request<QueuePage>(`/api/documents${suffix}`, { signal })
}

export function correctField(
  documentId: string,
  fieldName: string,
  value: string,
  signal?: AbortSignal,
): Promise<Field> {
  return request<Field>(
    `/api/documents/${encodeURIComponent(documentId)}/fields/${encodeURIComponent(fieldName)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
      signal,
    },
  )
}

export function getStats(signal?: AbortSignal): Promise<Stats> {
  return request<Stats>('/api/stats', { signal })
}

/** A reviewer's corrected amount. The server records it, learns where the value sat, and
 *  resolves the document; the response says how the correction feeds region-learning. */
export function correctAmountDue(
  id: string,
  value: string,
  signal?: AbortSignal,
): Promise<CorrectionResult> {
  return request<CorrectionResult>(
    `/api/documents/${encodeURIComponent(id)}/fields/amount_due`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
      signal,
    },
  )
}

/** The live pipeline state — every tracked document and the stage it is at. */
export function getProgress(signal?: AbortSignal): Promise<ProgressResponse> {
  return request<ProgressResponse>('/api/progress', { signal })
}

/** Reset the session: clears the job list and the dedup cache so a new run reads its
 *  files fresh. Learned corrections are kept. */
export function clearSession(): Promise<{ ok: boolean; cleared: number }> {
  return request<{ ok: boolean; cleared: number }>('/api/documents/clear', { method: 'POST' })
}

/** The finished table, as a downloadable file. Relative so it works on any host. */
export const REPORT_CSV_URL = '/api/report.csv'
export const REPORT_JSON_URL = '/api/report.json'

/**
 * Upload many files at once, a few at a time.
 *
 * One POST per file — the server queues them and a single worker processes them in
 * order, so firing all hundred at once would only flood the network for no gain. The
 * cap keeps the browser's connection pool healthy; `onSettled` reports each result as
 * it lands so the caller can react without waiting for the whole batch.
 */
export async function uploadMany(
  files: File[],
  apiKey: string,
  concurrency = 4,
  onSettled?: (file: File, accepted: UploadAccepted | null, error: unknown) => void,
): Promise<void> {
  const queue = [...files]
  async function worker() {
    for (let file = queue.shift(); file; file = queue.shift()) {
      try {
        onSettled?.(file, await uploadDocument(file, apiKey), null)
      } catch (error) {
        onSettled?.(file, null, error)
      }
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, files.length) }, worker),
  )
}

/** URL for a rendered page image. Not yet implemented server-side (501) — the
 *  page view degrades to a placeholder on error rather than blocking on it. */
export function pageImageUrl(documentId: string, page: number, width = 1200): string {
  return `/api/documents/${encodeURIComponent(documentId)}/page/${page}?width=${width}`
}

const POLL_INTERVAL_MS = 700
const POLL_TIMEOUT_MS = 90_000

/**
 * Poll a document until it stops being `processing`.
 *
 * The mock currently returns `done` on the first read, so this resolves
 * immediately today. It is written against the contract rather than the mock:
 * when the real pipeline starts returning `processing`, upload keeps working
 * without a change here.
 */
export async function waitForDocument(
  id: string,
  options: { signal?: AbortSignal; onPoll?: (attempt: number) => void } = {},
): Promise<ExtractedDocument> {
  const startedAt = Date.now()
  for (let attempt = 0; ; attempt++) {
    if (options.signal?.aborted) throw new ApiError(0, 'Cancelled.')

    const doc = await getDocument(id, options.signal)
    if (doc.status !== 'processing') return doc

    if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
      throw new ApiError(
        504,
        'This document is taking longer than expected. It may still finish — check the queue.',
      )
    }

    options.onPoll?.(attempt)
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }
}
