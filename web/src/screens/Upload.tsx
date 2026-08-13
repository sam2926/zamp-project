import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { clearSession, uploadMany } from '../api'
import { PageTabs } from '../components/PageTabs'

const MAX_BYTES = 20 * 1024 * 1024

/** The visitor's own LLM key lives in sessionStorage: it survives navigation
 *  between screens but is gone when the tab closes, and it never reaches
 *  localStorage or any log. It is sent only on the upload requests that use it. */
const KEY_STORE = 'llm_api_key'
const readKey = () => {
  try {
    return sessionStorage.getItem(KEY_STORE) ?? ''
  } catch {
    return ''
  }
}
const writeKey = (value: string) => {
  try {
    if (value) sessionStorage.setItem(KEY_STORE, value)
    else sessionStorage.removeItem(KEY_STORE)
  } catch {
    /* private mode or storage disabled — the key simply lives in memory */
  }
}

/** The same limits the API enforces, checked before the upload leaves the
 *  browser. A 20MB file should not travel just to be rejected. */
function localComplaint(file: File): string | null {
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return `“${file.name}” isn’t a PDF. Upload PDF invoices.`
  if (file.size > MAX_BYTES) {
    return `“${file.name}” is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is 20MB.`
  }
  if (file.size === 0) return `“${file.name}” is empty.`
  return null
}

type Phase =
  | { kind: 'idle' }
  | { kind: 'sending'; total: number; done: number }
  | { kind: 'error'; message: string }

/**
 * Upload one invoice or a hundred. Files are validated in the browser, then each is
 * sent to the server, which queues them; the moment they are on their way we move to
 * Live progress, where the whole batch is watched through the pipeline.
 *
 * Processing costs a model call, so an upload needs the visitor's own key — the
 * "Choose files" control stays disabled until one is present.
 */
export default function Upload() {
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [dragging, setDragging] = useState(false)
  const [apiKey, setApiKey] = useState(readKey)
  const [revealKey, setRevealKey] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const hasKey = apiKey.length > 0

  const updateKey = (value: string) => {
    const trimmed = value.trim()
    setApiKey(trimmed)
    writeKey(trimmed)
  }

  const handleFiles = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList)
    if (!files.length) return

    if (!hasKey) {
      setPhase({ kind: 'error', message: 'Add your API key below, then choose your files.' })
      return
    }

    const valid: File[] = []
    const rejected: string[] = []
    for (const file of files) {
      const complaint = localComplaint(file)
      if (complaint) rejected.push(complaint)
      else valid.push(file)
    }

    if (!valid.length) {
      setPhase({ kind: 'error', message: rejected[0] ?? 'None of those were PDFs.' })
      return
    }

    setPhase({ kind: 'sending', total: valid.length, done: 0 })
    // Every send starts a clean run: clear the previous stack (and dedup cache) first, so
    // Live progress shows only this batch and each file is read fresh.
    try {
      await clearSession()
    } catch {
      /* best effort — a failed clear shouldn't block the upload */
    }
    await uploadMany(valid, apiKey, 4, () => {
      setPhase((cur) => (cur.kind === 'sending' ? { ...cur, done: cur.done + 1 } : cur))
    })
    navigate('/live')
  }

  const pickFiles = () => inputRef.current?.click()
  const reset = () => setPhase({ kind: 'idle' })

  const canDrop = phase.kind !== 'sending' && hasKey
  const state = phase.kind === 'sending' ? 'working' : phase.kind

  return (
    <div className="upload-plane">
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files?.length) void handleFiles(e.target.files)
          e.target.value = ''
        }}
      />

      <PageTabs />

      <div className="upload-stage">
      <div className="upload-column">
      <section
        className="upload-card"
        data-state={state}
        data-dragging={canDrop && dragging}
        onDragOver={
          canDrop
            ? (e) => {
                e.preventDefault()
                setDragging(true)
              }
            : undefined
        }
        onDragLeave={canDrop ? () => setDragging(false) : undefined}
        onDrop={
          canDrop
            ? (e) => {
                e.preventDefault()
                setDragging(false)
                if (e.dataTransfer.files?.length) void handleFiles(e.dataTransfer.files)
              }
            : undefined
        }
      >
        <div className="upload-header">
          {phase.kind === 'error' && (
            <button type="button" className="upload-close" onClick={reset} aria-label="Dismiss">
              <CloseIcon />
            </button>
          )}
        </div>

        <div className="upload-body">
          <span className="upload-icon">
            {phase.kind === 'error' ? <CircleAlert /> : <CircleDown />}
          </span>

          <div className="upload-content">
            {phase.kind === 'idle' && (
              <>
                <h2>{dragging && canDrop ? 'Drop them anywhere' : 'Upload your documents'}</h2>
                <p>
                  {dragging && canDrop
                    ? 'Let go and they start reading.'
                    : 'Drop PDFs anywhere on this card, or choose them. PDF only, up to 20MB each.'}
                </p>
                <div className="upload-actions">
                  <button
                    type="button"
                    className="upload-btn upload-btn-primary"
                    onClick={pickFiles}
                    disabled={!hasKey}
                  >
                    Choose files
                  </button>
                  <button type="button" className="upload-btn" onClick={() => navigate('/live')}>
                    Live progress
                  </button>
                </div>
                {!hasKey && (
                  <p className="upload-note">Add your API key below to upload.</p>
                )}
              </>
            )}

            {phase.kind === 'sending' && (
              <>
                <h2>Sending your files…</h2>
                <p>
                  {phase.done} of {phase.total} on their way. We’ll take you to Live progress to
                  watch them read.
                </p>
                <div className="upload-progress">
                  <div className="upload-progress-column">
                    <span className="upload-progress-label">
                      {Math.round((phase.done / phase.total) * 100)}%
                    </span>
                    <div
                      className="upload-track"
                      style={{ ['--progress-width' as string]: `${(phase.done / phase.total) * 100}%` }}
                    />
                  </div>
                </div>
              </>
            )}

            {phase.kind === 'error' && (
              <>
                <h2>That didn’t go through</h2>
                <p>{phase.message}</p>
                <div className="upload-actions">
                  <button
                    type="button"
                    className="upload-btn upload-btn-primary"
                    onClick={pickFiles}
                    disabled={!hasKey}
                  >
                    Choose files
                  </button>
                  <button type="button" className="upload-btn" onClick={reset}>
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </section>
      {phase.kind !== 'sending' && (
        <section className="key-card">
          <span className="key-card-icon">
            <KeyIcon />
          </span>
          <div className="key-card-content">
            <label className="key-card-label" htmlFor="llm-key">
              Your LLM API key
            </label>
            <div className="key-card-row">
              <input
                id="llm-key"
                className="key-card-input"
                type={revealKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => updateKey(e.target.value)}
                placeholder="sk-…"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
              />
              {hasKey && (
                <button
                  type="button"
                  className="key-card-toggle"
                  onClick={() => setRevealKey((r) => !r)}
                >
                  {revealKey ? 'Hide' : 'Show'}
                </button>
              )}
            </div>
            <p className="key-card-hint">Sent with your upload, never stored.</p>
          </div>
        </section>
      )}
      </div>
      </div>
    </div>
  )
}

/* 24px circled icons, matching the reference's icon treatment. */
const svgProps = {
  width: 24,
  height: 24,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
}

const CircleDown = () => (
  <svg {...svgProps}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v8" />
    <path d="M8.5 12.5L12 16l3.5-3.5" />
  </svg>
)

const KeyIcon = () => (
  <svg {...svgProps}>
    <circle cx="8" cy="15" r="4" />
    <path d="M10.85 12.15 19 4" />
    <path d="M17.5 5.5 19.5 7.5" />
    <path d="M15 7 17 9" />
  </svg>
)

const CircleAlert = () => (
  <svg {...svgProps}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 7.5v5" />
    <path d="M12 16.2h.01" />
  </svg>
)

const CloseIcon = () => (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    aria-hidden="true"
  >
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
)
