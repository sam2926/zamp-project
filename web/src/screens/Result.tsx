import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { correctField, getDocument } from '../api'
import { FieldRow } from '../components/FieldRow'
import { PageTabs } from '../components/PageTabs'
import { PageView, type Located } from '../components/PageView'
import { Banner, ErrorState, Loading } from '../components/States'
import { AlertIcon, CheckIcon } from '../components/icons'
import { Confidence, StatusChip } from '../components/status'
import type { ExtractedDocument, Field } from '../types'

const lineItemKey = (itemId: number, fieldName: string) => `li:${itemId}:${fieldName}`

export default function Result() {
  const { id = '' } = useParams()
  const [doc, setDoc] = useState<ExtractedDocument | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [onlyFlagged, setOnlyFlagged] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setError(null)
    setDoc(null)
    getDocument(id).then(setDoc).catch(setError)
  }, [id])

  useEffect(load, [load])

  /** Line items repeat field names, so identity is a composite key, not the name. */
  const located = useMemo<Located[]>(() => {
    if (!doc) return []
    return [
      ...doc.fields.map((f) => ({ key: f.name, name: f.name, page: f.page, box: f.box })),
      ...doc.line_items.flatMap((item) =>
        item.fields.map((f) => ({
          key: lineItemKey(item.id, f.name),
          name: `${f.name} · row ${item.id}`,
          page: f.page,
          box: f.box,
        })),
      ),
    ]
  }, [doc])

  if (error) return <ErrorState error={error} onRetry={load} />
  if (!doc) return <Loading label="Loading document…" />

  if (doc.status === 'failed') {
    return (
      <ErrorState
        error={new Error(doc.error ?? 'This document could not be processed.')}
        onRetry={load}
      />
    )
  }

  const flagged = doc.fields.filter((f) => f.status !== 'ok')
  const shown = onlyFlagged ? flagged : doc.fields
  const failedRules = doc.validation.filter((r) => !r.passed)

  const applyCorrection = async (field: Field, value: string) => {
    setSaving(true)
    try {
      const updated = await correctField(doc.id, field.name, value)
      setDoc((current) =>
        current
          ? {
              ...current,
              fields: current.fields.map((f) => (f.name === updated.name ? updated : f)),
            }
          : current,
      )
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageTabs />
      <div className="page-head">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{doc.filename}</h1>
            <p className="muted mono" style={{ fontSize: 12 }}>
              {doc.id} · {doc.pages} page{doc.pages === 1 ? '' : 's'}
            </p>
          </div>
          <Link to="/queue" className="btn">
            Back to queue
          </Link>
        </div>
      </div>

      <div className="stack">
        <ProcessingSummary doc={doc} flaggedCount={flagged.length} />

        {failedRules.length > 0 && (
          <Banner tone="warning" icon={<AlertIcon size={14} />}>
            <strong>
              {failedRules.length} check{failedRules.length === 1 ? '' : 's'} failed.
            </strong>{' '}
            {failedRules.map((rule, i) => (
              <span key={rule.rule}>
                {i > 0 && ' '}
                {rule.detail ?? rule.rule}
                {rule.suspect_fields?.length ? (
                  <>
                    {' — likely '}
                    {rule.suspect_fields.map((name, j) => (
                      <span key={name}>
                        {j > 0 && ', '}
                        <button
                          type="button"
                          className="linkish mono"
                          onClick={() => setSelected(name)}
                        >
                          {name}
                        </button>
                      </span>
                    ))}
                  </>
                ) : null}
                .
              </span>
            ))}
          </Banner>
        )}

        <div className="split">
          <div className="stack">
            <section className="card">
              <div className="card-head">
                <h2>Fields</h2>
                <div className="seg">
                  <button aria-pressed={!onlyFlagged} onClick={() => setOnlyFlagged(false)}>
                    All {doc.fields.length}
                  </button>
                  <button aria-pressed={onlyFlagged} onClick={() => setOnlyFlagged(true)}>
                    Needs attention {flagged.length}
                  </button>
                </div>
              </div>

              {shown.length === 0 ? (
                <div className="state" style={{ padding: '32px 24px' }}>
                  <span className="state-icon" style={{ color: 'var(--good)' }}>
                    <CheckIcon size={18} />
                  </span>
                  <h2>Nothing flagged</h2>
                  <p>
                    Every field passed its checks with confidence to spare. Switch to “All” to
                    see them.
                  </p>
                </div>
              ) : (
                <div className="fields">
                  {shown.map((field) => (
                    <FieldRow
                      key={field.name}
                      field={field}
                      selected={selected === field.name}
                      onSelect={() => setSelected(field.name)}
                      onCorrect={(value) => applyCorrection(field, value)}
                      busy={saving}
                    />
                  ))}
                </div>
              )}
            </section>

            {doc.line_items.length > 0 && (
              <section className="card">
                <div className="card-head">
                  <h2>Line items</h2>
                  <span className="hint">{doc.line_items.length} rows</span>
                </div>
                <div className="card-body" style={{ padding: 0, overflowX: 'auto' }}>
                  <LineItemTable
                    doc={doc}
                    selected={selected}
                    onSelect={(name) => setSelected(name)}
                  />
                </div>
              </section>
            )}

            <section className="card">
              <div className="card-head">
                <h2>Checks</h2>
                <span className="hint">arithmetic and format rules</span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <table>
                  <tbody>
                    {doc.validation.map((rule) => (
                      <tr key={rule.rule}>
                        <td style={{ width: 26 }}>
                          <span style={{ color: rule.passed ? 'var(--good)' : 'var(--warning)' }}>
                            {rule.passed ? <CheckIcon size={14} /> : <AlertIcon size={14} />}
                          </span>
                        </td>
                        <td className="mono" style={{ fontSize: 12 }}>
                          {rule.rule}
                        </td>
                        <td className="muted" style={{ fontSize: 12 }}>
                          {rule.passed ? 'passed' : (rule.detail ?? 'failed')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <PageView documentId={doc.id} page={0} fields={located} selectedKey={selected} />
        </div>
      </div>
    </>
  )
}

/** The "what did this cost" strip. `model_called: false` is the claim the whole
 *  architecture rests on, so it is stated on every document rather than buried. */
function ProcessingSummary({
  doc,
  flaggedCount,
}: {
  doc: ExtractedDocument
  flaggedCount: number
}) {
  const layout = doc.layout
  const processing = doc.processing
  return (
    <div className="tiles">
      <div className="tile">
        <div className="tile-label">Fields extracted</div>
        <div className="tile-value">{doc.fields.length}</div>
        <div className="tile-note">
          {flaggedCount === 0 ? 'none flagged' : `${flaggedCount} need attention`}
        </div>
      </div>
      <div className="tile">
        <div className="tile-label">Layout</div>
        <div className="tile-value">{layout?.known ? 'Known' : 'New'}</div>
        <div className="tile-note">
          {layout?.known
            ? `seen ${layout.seen_count} times before`
            : 'first document in this format'}
        </div>
      </div>
      <div className="tile">
        <div className="tile-label">Model calls</div>
        <div className="tile-value">{processing?.model_called ? '1' : '0'}</div>
        <div className="tile-note">
          {processing?.model_called
            ? 'cold read — a template was learned'
            : 'served from a learned template'}
        </div>
      </div>
      <div className="tile">
        <div className="tile-label">Processing time</div>
        <div className="tile-value">{processing ? `${processing.ms}ms` : '—'}</div>
        <div className="tile-note">end to end</div>
      </div>
    </div>
  )
}

function LineItemTable({
  doc,
  selected,
  onSelect,
}: {
  doc: ExtractedDocument
  selected: string | null
  onSelect: (name: string) => void
}) {
  const columns = Array.from(
    new Set(doc.line_items.flatMap((li) => li.fields.map((f) => f.name))),
  )

  return (
    <table>
      <thead>
        <tr>
          <th style={{ width: 28 }}>#</th>
          {columns.map((column) => (
            <th key={column} className="mono">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {doc.line_items.map((item) => (
          <tr key={item.id}>
            <td className="muted num">{item.id}</td>
            {columns.map((column) => {
              const field = item.fields.find((f) => f.name === column)
              if (!field) return <td key={column} className="muted">—</td>
              const key = lineItemKey(item.id, field.name)
              return (
                <td key={column}>
                  <button
                    type="button"
                    className="cellbtn"
                    aria-selected={selected === key}
                    onClick={() => onSelect(key)}
                  >
                    <span>{field.value ?? 'not found'}</span>
                    <Confidence value={field.confidence} status={field.status} />
                  </button>
                  {field.status !== 'ok' && (
                    <div style={{ marginTop: 4 }}>
                      <StatusChip status={field.status} />
                      {field.reason && (
                        <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                          {field.reason}
                        </div>
                      )}
                    </div>
                  )}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
