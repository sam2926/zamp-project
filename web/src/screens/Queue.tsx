import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { listDocuments } from '../api'
import { PageTabs } from '../components/PageTabs'
import { EmptyState, ErrorState, Loading } from '../components/States'
import { CheckIcon, InboxIcon } from '../components/icons'
import { Confidence } from '../components/status'
import type { QueuePage } from '../types'

const PAGE_SIZE = 25

export default function Queue() {
  const [page, setPage] = useState<QueuePage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [needsReview, setNeedsReview] = useState(true)
  const [sort, setSort] = useState<'uploaded' | 'confidence'>('confidence')
  const [offset, setOffset] = useState(0)
  const navigate = useNavigate()

  const load = useCallback(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    listDocuments(
      { needs_review: needsReview || undefined, sort, limit: PAGE_SIZE, offset },
      controller.signal,
    )
      .then(setPage)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [needsReview, sort, offset])

  useEffect(load, [load])

  return (
    <>
      <PageTabs />
      <div className="page-head">
        <h1>Review queue</h1>
        <p>
          Sorted by the weakest field in each document, so the least trustworthy extraction is
          the first thing you see. Reviewing happens field by field, not document by document.
        </p>
      </div>

      <section className="card">
        <div className="card-head">
          <div className="row">
            <div className="seg">
              <button
                aria-pressed={needsReview}
                onClick={() => {
                  setNeedsReview(true)
                  setOffset(0)
                }}
              >
                Needs attention
              </button>
              <button
                aria-pressed={!needsReview}
                onClick={() => {
                  setNeedsReview(false)
                  setOffset(0)
                }}
              >
                All documents
              </button>
            </div>
          </div>
          <div className="row">
            <span className="hint">Sort</span>
            <div className="seg">
              <button
                aria-pressed={sort === 'confidence'}
                onClick={() => {
                  setSort('confidence')
                  setOffset(0)
                }}
              >
                Lowest confidence
              </button>
              <button
                aria-pressed={sort === 'uploaded'}
                onClick={() => {
                  setSort('uploaded')
                  setOffset(0)
                }}
              >
                Most recent
              </button>
            </div>
          </div>
        </div>

        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : loading && !page ? (
          <Loading label="Loading the queue…" />
        ) : !page || page.items.length === 0 ? (
          needsReview ? (
            <EmptyState
              icon={<CheckIcon size={18} />}
              title="Nothing needs attention"
              body="Every processed document cleared its checks with confidence to spare. New uploads that fall short will appear here."
              action={
                <button className="btn" onClick={() => setNeedsReview(false)}>
                  Show all documents
                </button>
              }
            />
          ) : (
            <EmptyState
              icon={<InboxIcon size={18} />}
              title="No documents yet"
              body="Upload an invoice and it will show up here once it has been read."
              action={
                <button className="btn btn-primary" onClick={() => navigate('/')}>
                  Upload an invoice
                </button>
              }
            />
          )
        ) : (
          <>
            <div style={{ overflowX: 'auto', opacity: loading ? 0.6 : 1 }}>
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Vendor</th>
                    <th className="num">Total</th>
                    <th className="num">Flagged</th>
                    <th>Weakest field</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((item) => (
                    <tr
                      key={item.id}
                      className="rowlink"
                      onClick={() => navigate(`/documents/${item.id}`)}
                    >
                      <td>
                        {/* The row is clickable for speed, but the link is what makes
                            the queue reachable by keyboard and screen reader. */}
                        <Link to={`/documents/${item.id}`} className="rowlink-target">
                          {item.filename}
                        </Link>
                        <div className="muted" style={{ fontSize: 12 }}>
                          {new Date(item.uploaded).toLocaleDateString(undefined, {
                            day: 'numeric',
                            month: 'short',
                          })}
                        </div>
                      </td>
                      <td>{item.vendor}</td>
                      <td className="num">{item.total}</td>
                      <td className="num">
                        {item.fields_review === 0 ? (
                          <span className="muted">none</span>
                        ) : (
                          `${item.fields_review} of ${item.fields_ok + item.fields_review}`
                        )}
                      </td>
                      <td>
                        <Confidence value={item.min_confidence} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card-head" style={{ borderTop: '1px solid var(--border)', borderBottom: 0 }}>
              <span className="hint">
                {offset + 1}–{offset + page.items.length} of {page.total}
              </span>
              <div className="row">
                <button
                  className="btn btn-sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </button>
                <button
                  className="btn btn-sm"
                  disabled={offset + PAGE_SIZE >= page.total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  )
}
