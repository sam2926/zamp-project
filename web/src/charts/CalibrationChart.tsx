import { useState } from 'react'
import type { CalibrationBucket } from '../types'

/**
 * Predicted confidence against measured accuracy.
 *
 * One series, so no legend box — the title names it. The diagonal is chrome, not
 * a second series: it is where a perfectly calibrated system would sit, and the
 * distance from it is the entire point of the chart. Points below the line mean
 * the system is overconfident, which is the failure that matters.
 */
export function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
  const [hovered, setHovered] = useState<number | null>(null)

  const W = 340
  const H = 320
  const pad = { top: 12, right: 14, bottom: 34, left: 40 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom

  const x = (v: number) => pad.left + v * plotW
  const y = (v: number) => pad.top + (1 - v) * plotH

  const ordered = [...buckets].sort((a, b) => a.predicted - b.predicted)
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  const path = ordered.map((b, i) => `${i === 0 ? 'M' : 'L'}${x(b.predicted)},${y(b.actual)}`).join(' ')

  return (
    <div>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Calibration curve">
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={pad.left}
                x2={W - pad.right}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--grid)"
                strokeWidth="1"
              />
              <text x={pad.left - 8} y={y(t) + 3.5} textAnchor="end" className="axis-label">
                {Math.round(t * 100)}
              </text>
              <text x={x(t)} y={H - pad.bottom + 16} textAnchor="middle" className="axis-label">
                {Math.round(t * 100)}
              </text>
            </g>
          ))}

          <line
            x1={pad.left}
            x2={W - pad.right}
            y1={H - pad.bottom}
            y2={H - pad.bottom}
            stroke="var(--axis)"
            strokeWidth="1"
          />
          <line
            x1={pad.left}
            x2={pad.left}
            y1={pad.top}
            y2={H - pad.bottom}
            stroke="var(--axis)"
            strokeWidth="1"
          />

          {/* Perfect calibration. Chrome, deliberately recessive. */}
          <line
            x1={x(0)}
            y1={y(0)}
            x2={x(1)}
            y2={y(1)}
            stroke="var(--axis)"
            strokeWidth="1.5"
          />
          <text x={x(0.62)} y={y(0.68)} className="axis-label" transform={`rotate(-45 ${x(0.62)} ${y(0.68)})`}>
            perfectly calibrated
          </text>

          <path d={path} fill="none" stroke="var(--series-1)" strokeWidth="2" />

          {ordered.map((bucket, i) => (
            <g key={bucket.bucket}>
              <circle
                cx={x(bucket.predicted)}
                cy={y(bucket.actual)}
                r="5"
                fill="var(--series-1)"
                stroke="var(--surface)"
                strokeWidth="2"
              />
              <circle
                cx={x(bucket.predicted)}
                cy={y(bucket.actual)}
                r="14"
                fill="transparent"
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
              />
            </g>
          ))}

          <text
            x={pad.left + plotW / 2}
            y={H - 4}
            textAnchor="middle"
            className="axis-title"
          >
            predicted confidence (%)
          </text>
          <text
            x={-(pad.top + plotH / 2)}
            y={11}
            textAnchor="middle"
            transform="rotate(-90)"
            className="axis-title"
          >
            actually correct (%)
          </text>
        </svg>

        {hovered !== null && (
          <div
            className="tooltip"
            style={{
              left: `${(x(ordered[hovered].predicted) / W) * 100}%`,
              top: `${(y(ordered[hovered].actual) / H) * 100}%`,
            }}
          >
            <strong>{ordered[hovered].bucket}</strong>
            <div>
              predicted {Math.round(ordered[hovered].predicted * 100)}% · actual{' '}
              {Math.round(ordered[hovered].actual * 100)}%
            </div>
            <div className="muted">{ordered[hovered].n.toLocaleString()} values</div>
          </div>
        )}
      </div>

      <details className="table-view">
        <summary>Table view</summary>
        <table>
          <thead>
            <tr>
              <th>Bucket</th>
              <th className="num">Predicted</th>
              <th className="num">Actual</th>
              <th className="num">Values</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((b) => (
              <tr key={b.bucket}>
                <td>{b.bucket}</td>
                <td className="num">{Math.round(b.predicted * 100)}%</td>
                <td className="num">{Math.round(b.actual * 100)}%</td>
                <td className="num">{b.n.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
