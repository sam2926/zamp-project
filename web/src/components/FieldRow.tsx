import { useEffect, useRef, useState } from 'react'
import type { Field } from '../types'
import { Confidence, StatusChip } from './status'

/**
 * One extracted value.
 *
 * Three rules from the contract are enforced here rather than left to each
 * screen: the confidence is always rendered beside the value, the reason is
 * always rendered when the status is not `ok`, and correction is per field.
 */
export function FieldRow({
  field,
  selected,
  onSelect,
  onCorrect,
  busy,
}: {
  field: Field
  selected: boolean
  onSelect: () => void
  onCorrect?: (value: string) => Promise<void> | void
  busy?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(field.value ?? '')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  const startEditing = () => {
    setDraft(field.value ?? '')
    setEditing(true)
  }

  const save = async () => {
    if (!onCorrect) return
    await onCorrect(draft)
    setEditing(false)
  }

  const isMissing = field.status === 'missing' || field.value === null

  return (
    <div className="field" aria-selected={selected}>
      <button
        type="button"
        className="field-select"
        onClick={onSelect}
        aria-label={`Show ${field.name} on the page`}
      >
        <span className="field-name">{field.name}</span>
        {editing ? null : (
          <span className={`field-value${isMissing ? ' is-missing' : ''}`}>
            {isMissing ? 'not found' : field.value}
          </span>
        )}
      </button>

      <div className="field-meta">
        <StatusChip status={field.status} />
        <Confidence value={field.confidence} status={field.status} />
        {onCorrect && !editing && (
          <button type="button" className="btn btn-sm" onClick={startEditing}>
            {isMissing ? 'Add' : 'Correct'}
          </button>
        )}
      </div>

      {editing && (
        <div className="field-edit">
          <input
            ref={inputRef}
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save()
              if (e.key === 'Escape') setEditing(false)
            }}
            aria-label={`Corrected value for ${field.name}`}
          />
          <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={busy}>
            Save
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setEditing(false)}
            disabled={busy}
          >
            Cancel
          </button>
        </div>
      )}

      {field.reason && (
        <p className="field-reason">
          <span>
            {field.reason}
            {field.original && (
              <>
                {' · was '}
                <span className="field-original">{field.original}</span>
              </>
            )}
          </span>
        </p>
      )}

      {!field.box && !isMissing && (
        <p className="field-reason">
          <span className="muted">No page region recorded for this value.</span>
        </p>
      )}
    </div>
  )
}
