import type { FieldAccuracy } from '../types'

/**
 * F1 per field, worst last.
 *
 * One series, one colour: the categories are nominal, so shading bars by their
 * own length would double-encode what the length already says. The value sits at
 * the bar end rather than inside it, where a short bar would clip it.
 */
export function FieldAccuracyChart({ fields }: { fields: FieldAccuracy[] }) {
  const ordered = [...fields].sort((a, b) => b.f1 - a.f1)

  return (
    <div>
      <div className="bars">
        {ordered.map((field) => (
          <div className="bar-row" key={field.field} title={`${field.n.toLocaleString()} values scored`}>
            <span className="bar-label mono">{field.field}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${field.f1 * 100}%` }} />
            </span>
            <span className="bar-value num">{field.f1.toFixed(2)}</span>
            <span className="bar-n num muted">{field.n.toLocaleString()}</span>
          </div>
        ))}
      </div>

      <details className="table-view">
        <summary>Table view</summary>
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th className="num">F1</th>
              <th className="num">Values scored</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((field) => (
              <tr key={field.field}>
                <td className="mono">{field.field}</td>
                <td className="num">{field.f1.toFixed(2)}</td>
                <td className="num">{field.n.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}
