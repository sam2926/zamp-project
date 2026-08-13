import { PageTabs } from '../components/PageTabs'
import { CROP_SPLIT, HEADLINE, PROVENANCE, REGION_ABLATION, TOKENS, k, pct } from '../data/accuracy'

/**
 * The Accuracy tab — one full-viewport screen per idea, spacious and minimal.
 *
 *   1 · Token reduction   — we read only the region, not the page.
 *   2 · Accuracy          — and got MORE right, not less: the usual cost/accuracy
 *                           tradeoff, broken. Same model, same documents.
 *
 * One overall accuracy figure only (the `exact` verdict), never a verdict
 * breakdown. No money narrative — token dollars are negligible on gpt-4o-mini;
 * the story is efficiency + quality. Screen 3 (the confidence signal) is next.
 */

const H = HEADLINE.exact
const tokenPct = TOKENS.pipeline / TOKENS.baseline
const gainPts = (H.pipeline - H.baseline) * 100

/* ---------- screen 1 · token reduction ---------- */

const SET_85 = { n: 85, baseline: REGION_ABLATION.exact.baseline.tokens, pipeline: REGION_ABLATION.exact.r80.tokens }
const SET_291 = { n: 291, baseline: TOKENS.baseline, pipeline: TOKENS.pipeline }

function TokenBlock({ n, desc, baseline, pipeline }: { n: number; desc: string; baseline: number; pipeline: number }) {
  const cut = Math.round(((baseline - pipeline) / baseline) * 100)
  const pipeW = (pipeline / baseline) * 100
  return (
    <div className="tokopt-block">
      <div className="tokopt-head">
        <span className="tokopt-n">{n} documents</span>
        <span className="tokopt-desc">{desc}</span>
      </div>
      <div className="tokopt-bars">
        <div className="tokopt-bar">
          <span className="tokopt-lab">full page</span>
          <span className="tokopt-track">
            <span className="tokopt-fill is-base" style={{ width: '100%' }} />
          </span>
          <span className="tokopt-val">{k(baseline)}</span>
        </div>
        <div className="tokopt-bar">
          <span className="tokopt-lab">cropped</span>
          <span className="tokopt-track">
            <span className="tokopt-fill is-gold" style={{ width: `${pipeW}%` }} />
          </span>
          <span className="tokopt-val">{k(pipeline)}</span>
        </div>
      </div>
      <div className="tokopt-cut">
        <strong>−{cut}%</strong> fewer tokens
      </div>
    </div>
  )
}

function TokenScreen() {
  return (
    <section className="screen">
      <span className="screen-eyebrow">Token optimization</span>
      <h1 className="screen-title">Fewer tokens per invoice</h1>
      <p className="screen-sub">
        We crop each page to the region the amount usually sits in, and fall back to the whole page
        only when the crop comes back empty — so the model reads less.
      </p>
      <div className="tokopt">
        <TokenBlock n={SET_85.n} desc="controlled set" baseline={SET_85.baseline} pipeline={SET_85.pipeline} />
        <TokenBlock n={SET_291.n} desc="full held-out val" baseline={SET_291.baseline} pipeline={SET_291.pipeline} />
      </div>
      <p className="screen-prov">amount_due · val · gpt-4o-mini</p>
    </section>
  )
}

/* ---------- screen 2 · accuracy ---------- */

function DeltaRow({
  label,
  before,
  after,
  delta,
  dir,
}: {
  label: string
  before: string
  after: string
  delta: string
  dir: 'up' | 'down'
}) {
  return (
    <div className="acc-row">
      <span className="acc-metric">{label}</span>
      <span className="acc-before">{before}</span>
      <span className="acc-arrow">→</span>
      <span className="acc-after">{after}</span>
      <span className={`acc-delta is-${dir}`}>
        {dir === 'up' ? '▲' : '▼'} {delta}
      </span>
    </div>
  )
}

function Mini({ value, label }: { value: string; label: string }) {
  return (
    <div className="mini">
      <div className="mini-val">{value}</div>
      <div className="mini-lab">{label}</div>
    </div>
  )
}

function AccuracyScreen() {
  return (
    <section className="screen">
      <span className="screen-eyebrow">Accuracy</span>
      <h1 className="screen-title">Less to read. More to trust.</h1>
      <p className="screen-sub">
        Reading less of a page usually means getting more wrong. Here it got more right — the same
        model, on the same documents. Only the crop changed.
      </p>

      <div className="acc-hero">
        <DeltaRow label="Tokens sent" before="100%" after={`${Math.round(tokenPct * 100)}%`} delta={`${Math.round((1 - tokenPct) * 100)}% fewer`} dir="down" />
        <DeltaRow label="Accuracy" before={pct(H.baseline)} after={pct(H.pipeline)} delta={`${gainPts.toFixed(1)} pts`} dir="up" />
      </div>

      <div className="minis">
        <Mini value="gpt-4o-mini" label="same model, both runs" />
        <Mini value={PROVENANCE.n.toString()} label="held-out val documents" />
        <Mini value={`${H.pipeHits}/${PROVENANCE.n}`} label="correct, region crop" />
        <Mini value="one variable" label="only the crop differs" />
      </div>

      <p className="screen-prov">amount_due · val · gpt-4o-mini · exact match</p>
    </section>
  )
}

/* ---------- screen 3 · the confidence signal ---------- */

function ConfidenceScreen() {
  const cs = CROP_SPLIT.exact
  const cropAcc = cs.cropHits / CROP_SPLIT.cropAnswered
  const fbAcc = cs.fallbackHits / CROP_SPLIT.fellBack
  const cropShare = (CROP_SPLIT.cropAnswered / CROP_SPLIT.n) * 100
  const gap = (cropAcc - fbAcc) * 100

  return (
    <section className="screen">
      <span className="screen-eyebrow">Confidence signal</span>
      <h1 className="screen-title">It knows when it's unsure.</h1>
      <p className="screen-sub">
        One free check — did the value land where this field usually sits? — tells us whether to
        trust an answer before anyone reads it.
      </p>

      <div className="sig-bar">
        <span className="sig-seg is-crop" style={{ width: `${cropShare}%` }}>
          {Math.round(cropShare)}% in region
        </span>
        <span className="sig-seg is-fallback" style={{ width: `${100 - cropShare}%` }}>
          {Math.round(100 - cropShare)}% fell back
        </span>
      </div>

      <div className="sig-cards">
        <div className="sig-card is-crop">
          <div className="sig-pct">{pct(cropAcc)}</div>
          <div className="sig-cap">accurate when the value is in its region</div>
          <div className="sig-meter">
            <span className="sig-fill is-crop" style={{ width: `${cropAcc * 100}%` }} />
          </div>
          <div className="sig-n">{CROP_SPLIT.cropAnswered} of {CROP_SPLIT.n} documents</div>
        </div>
        <div className="sig-card is-fallback">
          <div className="sig-pct">{pct(fbAcc)}</div>
          <div className="sig-cap">accurate when it falls back to the whole page</div>
          <div className="sig-meter">
            <span className="sig-fill is-fallback" style={{ width: `${fbAcc * 100}%` }} />
          </div>
          <div className="sig-n">{CROP_SPLIT.fellBack} of {CROP_SPLIT.n} documents</div>
        </div>
      </div>

      <p className="sig-gap">
        A <strong>{gap.toFixed(0)}-point</strong> gap — from a check that costs nothing and isn't the
        model grading itself.
      </p>

      <p className="screen-prov">amount_due · val · gpt-4o-mini · exact match</p>
    </section>
  )
}

/* ---------- screen 4 · what the signal buys you (straight-through) ---------- */

function ReviewScreen() {
  const cs = CROP_SPLIT.exact
  const autoN = CROP_SPLIT.cropAnswered
  const reviewN = CROP_SPLIT.fellBack
  const n = CROP_SPLIT.n
  const autoAcc = cs.cropHits / autoN
  const autoErr = autoN - cs.cropHits
  const reviewErr = reviewN - cs.fallbackHits
  const totalErr = autoErr + reviewErr
  const errCaught = Math.round((reviewErr / totalErr) * 100)
  const slipPct = ((autoErr / n) * 100).toFixed(1)
  const cut = Math.round((autoN / n) * 100)

  return (
    <section className="screen">
      <span className="screen-eyebrow">Straight-through processing</span>
      <h1 className="screen-title">A person reviews only where it matters.</h1>
      <p className="screen-sub">
        Because the system flags its own uncertainty, the confident answers clear automatically and
        a human sees the rest — which is where almost every error actually is.
      </p>

      <div className="stp-piles">
        <div className="stp-pile is-auto">
          <div className="stp-role">Auto-accepted</div>
          <div className="stp-n">
            {autoN}
            <span>/{n}</span>
          </div>
          <div className="stp-share">{cut}% of the queue</div>
          <div className="stp-note">cleared at {pct(autoAcc)} — {autoErr} slip through</div>
        </div>
        <div className="stp-pile is-review">
          <div className="stp-role">Sent to review</div>
          <div className="stp-n">
            {reviewN}
            <span>/{n}</span>
          </div>
          <div className="stp-share">{100 - cut}% of the queue</div>
          <div className="stp-note">holds {reviewErr} of {totalErr} total errors</div>
        </div>
      </div>

      <div className="minis minis-3">
        <Mini value={`−${cut}%`} label="documents a human never touches" />
        <Mini value={`${errCaught}%`} label="of all errors land in the review pile" />
        <Mini value={`${slipPct}%`} label={`slip through auto-accept (${autoErr} of ${n})`} />
      </div>

      <p className="sig-gap">
        Auto-clearing a third of the queue lets through <strong>{autoErr} in {n}</strong>, while the
        human's pile still holds {errCaught}% of the mistakes.
      </p>

      <p className="screen-prov">amount_due · val · gpt-4o-mini · exact match</p>
    </section>
  )
}

export default function Dashboard() {
  return (
    <>
      <PageTabs />
      <TokenScreen />
      <AccuracyScreen />
      <ConfidenceScreen />
      <ReviewScreen />
    </>
  )
}
