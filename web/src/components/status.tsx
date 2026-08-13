import type { ReactElement } from 'react'

import type { FieldStatus } from '../types'
import { AlertIcon, CheckIcon, MissingIcon, WrenchIcon } from './icons'

/** Single source of truth for how a field state is named, coloured and iconed.
 *  Every status ships an icon and a label, so colour is never the only channel. */
export const statusMeta: Record<
  FieldStatus,
  { label: string; token: string; Icon: (p: { size?: number }) => ReactElement }
> = {
  ok: { label: 'Accepted', token: 'good', Icon: CheckIcon },
  review: { label: 'Needs review', token: 'warning', Icon: AlertIcon },
  repaired: { label: 'Repaired', token: 'serious', Icon: WrenchIcon },
  missing: { label: 'Not found', token: 'critical', Icon: MissingIcon },
}

export function StatusChip({ status }: { status: FieldStatus }) {
  const { label, token, Icon } = statusMeta[status]
  return (
    <span className="chip" data-status={status}>
      <span className="chip-icon" style={{ color: `var(--${token})` }}>
        <Icon size={12} />
      </span>
      {label}
    </span>
  )
}

/**
 * A confidence reading. Calibrated, so the number means what it says: values at
 * 0.9 are right about 90% of the time. Shown as a figure *and* a meter — the
 * meter is the glance, the figure is the fact.
 *
 * `status` tints the meter to match the field's state, and is only passed where
 * a status label sits beside it. Without it the meter is the plain sequential
 * hue: a bare number is a magnitude, and dressing a magnitude in the status
 * palette makes colour claim something the data has not said.
 */
export function Confidence({ value, status }: { value: number; status?: FieldStatus }) {
  const percent = Math.round(value * 100)
  const token = status ? statusMeta[status].token : 'series-1'
  return (
    <span
      className="conf"
      title={`Confidence ${percent}%. Calibrated: values scored this high are correct about ${percent}% of the time.`}
    >
      <span className="conf-meter">
        <span
          className="conf-fill"
          style={{ width: `${percent}%`, background: `var(--${token})` }}
        />
      </span>
      <span className="conf-value">{percent}%</span>
    </span>
  )
}
