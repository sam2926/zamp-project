/**
 * The measured accuracy results, as one typed source of truth.
 *
 * Every number here was computed row-by-row from `data/runs/*.jsonl` — LIVE
 * `gpt-4o-mini`, `val` split, field `amount_due`. Not the offline stub, not
 * reconstructed. Re-derivable from the saved runs at any time; nothing here is
 * a model's self-report or a placeholder.
 *
 * Two scoring verdicts are carried so the whole page can sit on one consistently:
 *   - `exact`   — string match after normalising `$`/commas   (the strict pick)
 *   - `numeric` — numeric value equality                       (conservative floor)
 *
 * NOT included, because it is not measured yet (see note in Dashboard.tsx):
 *   - per-field accuracy beyond amount_due
 *   - seen-layout vs unseen-layout split
 *   - a calibration curve — the confidence weights are still hand-set, so plotting
 *     one would imply a calibration we have not earned.
 */

export type Verdict = 'exact' | 'numeric'

export const PROVENANCE = {
  field: 'amount_due',
  split: 'val',
  model: 'gpt-4o-mini',
  n: 291,
} as const

/** Full val (n=291): whole-page baseline vs the shipped pipeline (80% region). */
export const HEADLINE: Record<Verdict, { baseline: number; pipeline: number; baseHits: number; pipeHits: number }> = {
  exact: { baseline: 0.732, pipeline: 0.766, baseHits: 213, pipeHits: 223 },
  numeric: { baseline: 0.701, pipeline: 0.739, baseHits: 204, pipeHits: 215 },
}

/** Tokens sent, all 291 documents. Pipeline = crop (every doc) + fallback pages (the misses). */
export const TOKENS = {
  baseline: 74181,
  cropCalls: 17371,
  fallbackPages: 46547,
  pipeline: 63918, // = cropCalls + fallbackPages, 86.2% of baseline
}

/**
 * The decisive signal: did the value land inside its expected region?
 * Whether the crop answered separates ~98% accuracy from ~65% — free to compute.
 */
export const CROP_SPLIT: Record<Verdict, { cropHits: number; fallbackHits: number }> & {
  cropAnswered: number
  fellBack: number
  n: number
} = {
  cropAnswered: 103,
  fellBack: 188,
  n: 291,
  exact: { cropHits: 101, fallbackHits: 122 },
  numeric: { cropHits: 98, fallbackHits: 117 },
}

/** Region-size ablation, on the 85 documents common to all three runs. Tighter won. */
type RegionRow = { acc: number; hits: number; tokens: number; tokensPct: number; fellBack?: number; cropAcc?: number }
export const REGION_ABLATION: Record<Verdict, { baseline: RegionRow; r95: RegionRow; r80: RegionRow }> & { n: number } = {
  n: 85,
  exact: {
    baseline: { acc: 0.8, hits: 68, tokens: 20210, tokensPct: 1.0 },
    r95: { acc: 0.8, hits: 68, tokens: 19837, tokensPct: 0.98, fellBack: 41, cropAcc: 0.977 },
    r80: { acc: 0.835, hits: 71, tokens: 16594, tokensPct: 0.82, fellBack: 53, cropAcc: 1.0 },
  },
  numeric: {
    baseline: { acc: 0.788, hits: 67, tokens: 20210, tokensPct: 1.0 },
    r95: { acc: 0.788, hits: 67, tokens: 19837, tokensPct: 0.98, fellBack: 41, cropAcc: 0.955 },
    r80: { acc: 0.824, hits: 70, tokens: 16594, tokensPct: 0.82, fellBack: 53, cropAcc: 0.969 },
  },
}

export const pct = (v: number) => `${(v * 100).toFixed(1)}%`
export const pts = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(1)} pts`
export const k = (v: number) => `${(v / 1000).toFixed(1)}k`
