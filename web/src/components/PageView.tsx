import { useEffect, useState } from 'react'
import { pageImageUrl } from '../api'
import type { Box } from '../types'

/** A value with a place on the page.
 *
 *  `key` exists because `name` is not unique: every line item has its own
 *  `description`, `quantity` and so on. Selection and overlay identity both hang
 *  off the key; the name is only ever displayed. */
export interface Located {
  key: string
  name: string
  page: number
  box: Box | null
}

/**
 * The page, with every located value boxed on it. Clicking a field highlights
 * its region here — the moment that makes the extraction checkable.
 *
 * Page rendering is not implemented server-side yet (it returns 501), so this
 * degrades to a page-shaped placeholder instead of blocking. Box geometry is
 * fractional and anchored to the sheet, not to the image, so the overlay is
 * already correct — when the endpoint lands the placeholder is simply replaced.
 */
export function PageView({
  documentId,
  page,
  fields,
  selectedKey,
}: {
  documentId: string
  page: number
  fields: Located[]
  selectedKey: string | null
}) {
  const [imageState, setImageState] = useState<'loading' | 'ready' | 'unavailable'>('loading')

  useEffect(() => {
    setImageState('loading')
  }, [documentId, page])

  const boxed = fields.filter((f) => f.box && f.page === page)
  const hasSelection = boxed.some((f) => f.key === selectedKey)

  return (
    <div className="pageview">
      <div className="sheet">
        <img
          src={pageImageUrl(documentId, page)}
          alt={`Page ${page + 1}`}
          onLoad={() => setImageState('ready')}
          onError={() => setImageState('unavailable')}
          style={{ display: imageState === 'ready' ? 'block' : 'none' }}
        />

        {imageState !== 'ready' && <PagePlaceholder />}

        {boxed.map((field) => {
          const [left, top, right, bottom] = field.box!
          const isSelected = field.key === selectedKey
          return (
            <div
              key={field.key}
              className="box"
              data-dim={hasSelection && !isSelected}
              style={{
                left: `${left * 100}%`,
                top: `${top * 100}%`,
                width: `${(right - left) * 100}%`,
                height: `${(bottom - top) * 100}%`,
                borderColor: isSelected ? 'var(--series-1)' : 'var(--axis)',
                background: isSelected ? 'rgba(42, 120, 214, 0.14)' : 'transparent',
              }}
            >
              {isSelected && (
                /* Anchor the tag to whichever edge keeps it on the sheet. */
                <span className="box-tag" style={left > 0.55 ? { left: 'auto', right: -1 } : undefined}>
                  {field.name}
                </span>
              )}
            </div>
          )
        })}

        {imageState === 'unavailable' && (
          <p className="sheet-note">
            Page rendering isn’t available yet — this is a placeholder. The regions below are
            the real coordinates returned for this document.
          </p>
        )}
      </div>
    </div>
  )
}

/** A page-shaped skeleton. Deliberately abstract: it stands in for a document
 *  without pretending to be one. */
function PagePlaceholder() {
  const bars: Array<[number, number, number, number]> = [
    [8, 8, 34, 3],
    [8, 15, 30, 1.6],
    [8, 18.5, 26, 1.6],
    [8, 22, 22, 1.6],
    [72, 8, 20, 2.2],
    [72, 13, 18, 1.6],
    [8, 27, 32, 2],
    [8, 44, 84, 1],
    [8, 48, 84, 1],
    [8, 51.5, 84, 1],
    [8, 55, 84, 1],
    [8, 58.5, 84, 1],
    [62, 66, 30, 1.4],
    [62, 70, 30, 1.4],
    [62, 74, 30, 1.8],
  ]
  return (
    <svg
      viewBox="0 0 100 141.4"
      preserveAspectRatio="none"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      aria-hidden="true"
    >
      <rect x="0" y="0" width="100" height="141.4" fill="#ffffff" />
      {bars.map(([x, y, w, h], i) => (
        <rect
          key={i}
          x={x}
          y={y * 1.414}
          width={w}
          height={h * 1.414}
          rx="0.6"
          fill="#eceae4"
        />
      ))}
      <line x1="8" y1="59" x2="92" y2="59" stroke="#e1e0d9" strokeWidth="0.4" />
      <line x1="8" y1="90" x2="92" y2="90" stroke="#e1e0d9" strokeWidth="0.4" />
    </svg>
  )
}
