/**
 * Chart primitives for the Accuracy dashboard.
 *
 * CSS-driven bars, not SVG: every panel here is a comparison of a few values, and
 * a div with a width reads the same as a rect while staying responsive and simple.
 * One convention throughout — the baseline series is a recessive grey, the pipeline
 * series is gold, so "we improved" is carried by colour as well as length.
 */
import type { ReactNode } from 'react'

import { pct, k } from '../data/accuracy'

/* ---------- stat card (top row) ---------- */

export function StatCard({
  label,
  value,
  delta,
  deltaTone = 'up',
  note,
  hero = false,
  icon,
}: {
  label: string
  value: string
  delta?: string
  deltaTone?: 'up' | 'down' | 'flat'
  note?: string
  hero?: boolean
  icon?: ReactNode
}) {
  return (
    <div className={`dash-stat${hero ? ' is-hero' : ''}`}>
      <div className="dash-stat-top">
        <span className="dash-stat-label">{label}</span>
        {icon && <span className="dash-stat-icon">{icon}</span>}
      </div>
      <div className="dash-stat-value">{value}</div>
      <div className="dash-stat-foot">
        {delta && <span className={`dash-stat-delta is-${deltaTone}`}>{delta}</span>}
        {note && <span className="dash-stat-note">{note}</span>}
      </div>
    </div>
  )
}

/* ---------- two-series accuracy comparison ---------- */

export function AccuracyCompare({ baseline, pipeline }: { baseline: number; pipeline: number }) {
  const rows = [
    { label: 'Whole-page baseline', value: baseline, series: 'base' as const },
    { label: 'Region-crop pipeline', value: pipeline, series: 'gold' as const },
  ]
  return (
    <div className="cmp">
      {rows.map((r) => (
        <div className="cmp-row" key={r.label}>
          <span className="cmp-label">{r.label}</span>
          <span className="cmp-track">
            <span className={`cmp-fill is-${r.series}`} style={{ width: `${r.value * 100}%` }} />
          </span>
          <span className="cmp-val">{pct(r.value)}</span>
        </div>
      ))}
    </div>
  )
}

/* ---------- token cost, stacked ---------- */

export function TokenStack({
  baseline,
  cropCalls,
  fallbackPages,
}: {
  baseline: number
  cropCalls: number
  fallbackPages: number
}) {
  const pipeline = cropCalls + fallbackPages
  const w = (v: number) => `${(v / baseline) * 100}%`
  return (
    <div className="tok">
      <div className="tok-row">
        <span className="tok-name">Baseline</span>
        <span className="tok-bar">
          <span className="tok-seg is-full" style={{ width: '100%' }} />
        </span>
        <span className="tok-total">{k(baseline)}</span>
      </div>
      <div className="tok-row">
        <span className="tok-name">Pipeline</span>
        <span className="tok-bar">
          <span className="tok-seg is-crop" style={{ width: w(cropCalls) }} title={`crop calls · ${k(cropCalls)}`} />
          <span
            className="tok-seg is-fallback"
            style={{ width: w(fallbackPages) }}
            title={`fallback pages · ${k(fallbackPages)}`}
          />
        </span>
        <span className="tok-total">{k(pipeline)}</span>
      </div>
      <div className="tok-legend">
        <span>
          <i className="dot is-crop" /> crop calls (every doc) — {k(cropCalls)}
        </span>
        <span>
          <i className="dot is-fallback" /> fallback pages (the misses) — {k(fallbackPages)}
        </span>
      </div>
    </div>
  )
}

/* ---------- crop-answered vs fell-back ---------- */

export function CropSplit({
  cropAnswered,
  fellBack,
  cropAcc,
  fallbackAcc,
  n,
}: {
  cropAnswered: number
  fellBack: number
  cropAcc: number
  fallbackAcc: number
  n: number
}) {
  const cropShare = (cropAnswered / n) * 100
  return (
    <div className="csplit">
      <div className="csplit-bar">
        <span className="csplit-seg is-crop" style={{ width: `${cropShare}%` }}>
          {Math.round(cropShare)}%
        </span>
        <span className="csplit-seg is-fallback" style={{ width: `${100 - cropShare}%` }}>
          {Math.round(100 - cropShare)}%
        </span>
      </div>
      <div className="csplit-cards">
        <div className="csplit-card is-crop">
          <div className="csplit-acc">{pct(cropAcc)}</div>
          <div className="csplit-cap">accurate when the crop answered</div>
          <div className="csplit-n">{cropAnswered} of {n} docs</div>
        </div>
        <div className="csplit-card is-fallback">
          <div className="csplit-acc">{pct(fallbackAcc)}</div>
          <div className="csplit-cap">accurate when it fell back to the page</div>
          <div className="csplit-n">{fellBack} of {n} docs</div>
        </div>
      </div>
    </div>
  )
}

/* ---------- region-size ablation ---------- */

export function RegionAblation({
  rows,
}: {
  rows: { name: string; acc: number; tokensPct: number; series: 'base' | 'mid' | 'gold'; best?: boolean }[]
}) {
  return (
    <div className="reg">
      {rows.map((r) => (
        <div className={`reg-row${r.best ? ' is-best' : ''}`} key={r.name}>
          <span className="reg-name">
            {r.name}
            {r.best && <span className="reg-badge">chosen</span>}
          </span>
          <span className="reg-track">
            <span className={`cmp-fill is-${r.series}`} style={{ width: `${r.acc * 100}%` }} />
          </span>
          <span className="reg-acc">{pct(r.acc)}</span>
          <span className="reg-tok">{Math.round(r.tokensPct * 100)}% tokens</span>
        </div>
      ))}
    </div>
  )
}
