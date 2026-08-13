import { useEffect, useState } from 'react'

import { ApiError, correctAmountDue, getDocument } from '../api'
import { PageView, type Located } from './PageView'
import type { CorrectionResult, ExtractedDocument, ProgressJob } from '../types'

/**
 * Review one flagged invoice.
 *
 * Shows the page with our guess boxed on it, says what we read and why it was flagged, and
 * asks for the right value. On save the correction is recorded, learned from, and the
 * document resolves — so the row leaves the queue. The panel closes itself once done.
 */
export function ReviewPanel({
  job,
  onClose,
  onResolved,
}: {
  job: ProgressJob
  onClose: () => void
  onResolved: () => void
}) {
  const [doc, setDoc] = useState<ExtractedDocument | null>(null)
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<CorrectionResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getDocument(job.id)
      .then((d) => {
        if (!alive) return
        setDoc(d)
        setValue(d.fields.find((f) => f.name === 'amount_due')?.value ?? '')
      })
      .catch(() => alive && setDoc(null))
    return () => {
      alive = false
    }
  }, [job.id])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const field = doc?.fields.find((f) => f.name === 'amount_due') ?? null
  const located: Located[] = field?.box
    ? [{ key: 'amount_due', name: 'Amount due', page: field.page, box: field.box }]
    : []

  const prompt =
    job.status === 'unreadable'
      ? 'This file couldn’t be read, so there was nothing to check. Enter the amount due if you can read it.'
      : job.status === 'not_found'
        ? 'We didn’t find an amount due on this page. If it’s there, enter it.'
        : `We read “${job.amount_due ?? '—'}” — ${job.reason ?? 'this needs a check'}.`

  const save = async () => {
    if (!value.trim()) {
      setError('Enter the correct amount.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await correctAmountDue(job.id, value.trim())
      setSaved(result)
      setTimeout(() => {
        onResolved()
        onClose()
      }, 1500)
    } catch (err) {
      setSaving(false)
      setError(err instanceof ApiError ? err.message : 'That correction did not save.')
    }
  }

  return (
    <div className="review-overlay" onMouseDown={onClose}>
      <div className="review-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="review-head">
          <span className="review-file" title={job.filename}>{job.filename}</span>
          <button className="review-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="review-body">
          <div className="review-page">
            <PageView documentId={job.id} page={0} fields={located} selectedKey="amount_due" />
          </div>

          <div className="review-side">
            {saved ? (
              <div className="review-done">
                <h3>Got it — I’ll remember this.</h3>
                {saved.located ? (
                  <p>
                    Saved, and I noted where the value sits.{' '}
                    <strong>{saved.corrections} of {saved.threshold}</strong> corrections toward
                    moving this field’s region.
                    {saved.region_moved && ' The region just updated.'}
                  </p>
                ) : (
                  <p>
                    Saved, and this file is fixed. I couldn’t pin the value on the page, so it
                    won’t move the region — but I won’t get this document wrong again.
                  </p>
                )}
              </div>
            ) : (
              <>
                <div className="review-what">
                  <span className="review-label">What we read</span>
                  <p className="review-guess">{prompt}</p>
                </div>

                <label className="review-input-label" htmlFor="amount-fix">
                  Correct amount due
                </label>
                <input
                  id="amount-fix"
                  className="review-input"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="e.g. 1,290.00"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && void save()}
                />
                {error && <p className="review-error">{error}</p>}

                <div className="review-actions">
                  <button className="btn btn-primary" onClick={() => void save()} disabled={saving}>
                    {saving ? 'Saving…' : 'Save & learn'}
                  </button>
                  <button className="btn" onClick={onClose} disabled={saving}>
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
