import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { clearSession, getProgress, REPORT_CSV_URL, REPORT_JSON_URL } from '../api'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { PageTabs } from '../components/PageTabs'
import { ReviewPanel } from '../components/ReviewPanel'
import type { Outcome, PipelineStage, ProgressJob, ProgressResponse } from '../types'

const STAGE_LABEL: Record<PipelineStage, string> = {
  queued: 'Queued',
  reading: 'Reading',
  matching: 'Matching layout',
  extracting: 'Extracting',
  checking: 'Checking',
  done: 'Done',
}

const STATUS_LABEL: Record<Outcome, string> = {
  ok: 'Extracted',
  review: 'Needs review',
  not_found: 'No amount found',
  unreadable: 'Unreadable',
}

/** Everything that isn't a clean, confident extraction wants a human. */
function needsReview(job: ProgressJob): boolean {
  return job.stage === 'done' && !job.corrected &&
    (job.status === 'review' || job.status === 'not_found' || job.status === 'unreadable')
}

export default function LiveProgress() {
  const [data, setData] = useState<ProgressResponse | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [active, setActive] = useState<ProgressJob | null>(null)
  const navigate = useNavigate()

  const refresh = async () => {
    try {
      const next = await getProgress()
      setData(next)
      setError(null)
    } catch (err) {
      setError(err)
    }
  }

  const clear = async () => {
    try {
      await clearSession()
      setActive(null)
      await refresh()
    } catch {
      /* the next poll will reflect reality either way */
    }
  }

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const next = await getProgress()
        if (alive) {
          setData(next)
          setError(null)
        }
      } catch (err) {
        if (alive) setError(err)
      }
    }
    void tick()
    const id = setInterval(tick, 1000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  if (!data && error) return <PlaneWrap><ErrorState error={error} /></PlaneWrap>
  if (!data) return <PlaneWrap><Loading label="Reading the pipeline…" /></PlaneWrap>

  const jobs = data.jobs
  if (jobs.length === 0) {
    return (
      <PlaneWrap>
        <EmptyState
          icon={<DocIcon />}
          title="No files uploaded yet"
          body="Upload invoices and this is where they’re processed. Anything we read confidently clears on its own — only the ones that need a human stay here for you."
          action={<button className="btn" onClick={() => navigate('/upload')}>Upload invoices</button>}
        />
      </PlaneWrap>
    )
  }

  const done = jobs.filter((j) => j.stage === 'done')
  const inFlight = jobs.length - done.length
  const review = jobs.filter(needsReview)
  const cleared = done.length - jobs.filter((j) => j.stage === 'done' && needsReview(j)).length
  const activeJob = jobs.find((j) => j.stage !== 'queued' && j.stage !== 'done')
  const queued = jobs.filter((j) => j.stage === 'queued').length
  const warming = !data.ocr_ready && jobs.some((j) => j.stage === 'reading')

  return (
    <PlaneWrap>
      <div className="live-wrap">
        <div className="live-head">
          <div>
            <h1 className="live-title">Live progress</h1>
            <p className="live-summary">
              {inFlight > 0
                ? `Processing ${done.length} of ${jobs.length} · ${cleared} cleared · ${review.length} to review`
                : `${jobs.length} processed · ${cleared} cleared automatically · ${review.length} need your review`}
            </p>
          </div>
          <div className="live-exports">
            {done.length > 0 && (
              <>
                <a className="btn" href={REPORT_CSV_URL} download>Export CSV</a>
                <a className="btn" href={REPORT_JSON_URL} download>Export JSON</a>
              </>
            )}
            <button className="btn" onClick={() => void clear()}>Clear</button>
          </div>
        </div>

        {inFlight > 0 && (
          <div className="live-progressbar" aria-hidden>
            <span style={{ width: `${(done.length / jobs.length) * 100}%` }} />
          </div>
        )}

        {activeJob && (
          <p className="live-now">
            <span className="live-dot" />
            Now: <strong>{activeJob.filename}</strong> · {STAGE_LABEL[activeJob.stage]}
            {queued > 0 && ` · ${queued} queued`}
          </p>
        )}

        {warming && (
          <p className="live-warming">
            Warming up the reader — the first document takes longer while the OCR model loads.
          </p>
        )}

        {review.length > 0 ? (
          <>
            <h2 className="live-section">Needs your review</h2>
            <div className="live-list">
              {review.map((job) => (
                <button key={job.id} className="review-row" data-status={job.status ?? ''} onClick={() => setActive(job)}>
                  <span className="review-row-left">
                    <span className="live-file" title={job.filename}>{job.filename}</span>
                    <span className="review-row-sub">
                      {job.status ? STATUS_LABEL[job.status] : 'Review'}
                      {job.reason ? ` · ${job.reason}` : ''}
                    </span>
                  </span>
                  <span className="review-row-right">
                    {job.layout.known && (
                      <span className="live-badge" data-tone="gold">
                        Known vendor{job.layout.seen_count ? ` · seen ${job.layout.seen_count}×` : ''}
                      </span>
                    )}
                    <span className="live-amount" data-empty={job.amount_due === null}>
                      {job.amount_due ?? 'NOT_FOUND'}
                    </span>
                    <span className="review-cta">Review →</span>
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : inFlight > 0 ? (
          <p className="live-watching">Watching — anything that needs you will appear here.</p>
        ) : (
          <EmptyState
            icon={<CheckIcon />}
            title="All clear"
            body={`Every invoice cleared on its own — nothing needs a human. The full table is in the export${cleared ? '' : ''}.`}
          />
        )}
      </div>

      {active && (
        <ReviewPanel
          job={active}
          onClose={() => setActive(null)}
          onResolved={() => void refresh()}
        />
      )}
    </PlaneWrap>
  )
}

function PlaneWrap({ children }: { children: React.ReactNode }) {
  return (
    <div className="upload-plane">
      <PageTabs />
      <div className="live-stage">{children}</div>
    </div>
  )
}

const DocIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M6 2.5h8L19 7v14.5H6z" />
    <path d="M13.5 2.5V7.5H19" />
    <line x1="9" y1="13" x2="15" y2="13" />
    <line x1="9" y1="16.5" x2="13" y2="16.5" />
  </svg>
)

const CheckIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <circle cx="12" cy="12" r="9.5" />
    <path d="M7.8 12.3l2.9 2.9L16.4 9.5" />
  </svg>
)
