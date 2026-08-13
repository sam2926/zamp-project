import type { ReactNode } from 'react'
import { AlertIcon, PlugIcon } from './icons'
import { ApiError } from '../api'

/** Empty, loading and error states are designed rather than left blank —
 *  they are most of what a reviewer actually sees on a quiet day. */

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: ReactNode
  title: string
  body: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="state">
      <span className="state-icon">{icon}</span>
      <h2>{title}</h2>
      <div className="state-body">{body}</div>
      {action && <div className="state-actions">{action}</div>}
    </div>
  )
}

/**
 * One error surface for the whole app. A dropped connection and a 500 are
 * different problems for the reader, so they get different words.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const offline = error instanceof ApiError && error.status === 0
  const message =
    error instanceof Error ? error.message : 'Something went wrong reading from the server.'

  return (
    <div className="state">
      <span className="state-icon" style={{ color: 'var(--critical)' }}>
        {offline ? <PlugIcon size={18} /> : <AlertIcon size={18} />}
      </span>
      <h2>{offline ? "Can't reach the API" : 'That request failed'}</h2>
      <p>{message}</p>
      {offline && (
        <p className="muted" style={{ fontSize: 12 }}>
          Start it with <code className="mono">uvicorn api.main:app --port 8000</code>
        </p>
      )}
      {onRetry && (
        <div className="state-actions">
          <button className="btn" onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
    </div>
  )
}

export function Banner({
  tone = 'neutral',
  icon,
  children,
}: {
  tone?: 'neutral' | 'warning' | 'critical'
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="banner" data-tone={tone}>
      {icon && <span style={{ flex: 'none', marginTop: 1 }}>{icon}</span>}
      <div>{children}</div>
    </div>
  )
}
