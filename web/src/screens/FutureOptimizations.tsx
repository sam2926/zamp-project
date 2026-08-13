import { useEffect, useRef, useState } from 'react'
import { PageTabs } from '../components/PageTabs'

/** Where the system goes next — each one builds on the shipped pipeline rather
 *  than replacing any of it. `points` are the card's bullets; kept short so the
 *  card stays as crisp as the Process steps. */
const OPTIMIZATIONS = [
  {
    mark: '1',
    step: 'Optimization 01',
    title: 'Cut the fallback rate',
    points: [
      'A value and its caption — an amount and its “TOTAL DUE” — sit side by side on the page.',
      'Learning the region around both would let the crop carry the caption every time.',
      'More documents are answered from the small crop, fewer ever reach the full-page read.',
      'Free to build; one measured run to confirm the gain.',
    ],
  },
  {
    mark: '2',
    step: 'Optimization 02',
    title: 'Replace the invented confidence with a calibrated one',
    points: [
      'Every correction is a labelled outcome: what the score said, and whether it held.',
      'Feeding those back fits the confidence score to a real, measured cut-off.',
      'The reviewer then sees exactly the risky share of documents, and no more.',
      'The loop already collects the corrections; this puts them to a second use.',
    ],
  },
  {
    mark: '3',
    step: 'Optimization 03',
    title: 'Read each page with a second OCR engine',
    points: [
      'Different readers are strong on different parts of a page.',
      'A second engine lets agreement raise confidence and disagreement raise an early flag.',
      'Most valuable on the degraded scans, where a single reader can slip.',
    ],
  },
  {
    mark: '4',
    step: 'Optimization 04',
    title: 'Read the line items, and let the invoice check itself',
    points: [
      'Roughly 80% of invoices carry line items that must sum to the totals.',
      'Reading them unlocks an arithmetic cross-check the header fields cannot give alone.',
      'When the maths balances, confidence is structural — the document agrees with itself.',
      'A natural step from single fields to the invoice’s full structure.',
    ],
  },
]

/**
 * Future optimizations.
 *
 * The same scroll-linked pattern as Process (see Process.tsx): the explanation
 * card is a fixed rectangle, pinned and vertically centred on the left,
 * crossfading; the named optimizations scroll past on the right, the active one
 * landing at the same vertical centre as the card. One IntersectionObserver
 * flips `.is-active` — no scroll library. Classes are shared with Process so the
 * theme and spacing stay identical.
 */
export default function FutureOptimizations() {
  const [active, setActive] = useState(0)
  const sections = useRef<(HTMLElement | null)[]>([])

  useEffect(() => {
    // The active optimization is the row crossing the horizontal centre band of
    // the viewport. Rows are contiguous, so exactly one holds the centre; if two
    // straddle a boundary, pick the one whose centre is nearest the middle.
    const intersecting = new Map<number, boolean>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          intersecting.set(Number((e.target as HTMLElement).dataset.index), e.isIntersecting)
        }
        const mid = window.innerHeight / 2
        let best = -1
        let bestDist = Infinity
        sections.current.forEach((el, i) => {
          if (!el || !intersecting.get(i)) return
          const r = el.getBoundingClientRect()
          const dist = Math.abs(r.top + r.height / 2 - mid)
          if (dist < bestDist) {
            bestDist = dist
            best = i
          }
        })
        if (best !== -1) setActive(best)
      },
      { rootMargin: '-40% 0px -40% 0px', threshold: 0 },
    )
    for (const el of sections.current) if (el) io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div className="process-plane">
      <div className="process-inner">
        <PageTabs />

        <div className="proc-scroll">
          {/* Pinned left: a fixed rectangle, centred on the y-axis, showing how
              to build whichever optimization is in view. */}
          <div className="proc-media-col">
            <div className="proc-sticky">
              <div className="proc-frame">
                {OPTIMIZATIONS.map((o, i) => (
                  <article
                    key={o.step}
                    className={`timeline-card proc-card${i === active ? ' is-active' : ''}`}
                    aria-hidden={i === active ? undefined : true}
                  >
                    <span className="timeline-step">{o.step}</span>
                    <h3>{o.title}</h3>
                    <ul className="proc-bullets">
                      {o.points.map((p, j) => (
                        <li key={j}>{p}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </div>
          </div>

          {/* Scrolling right: the marker and the optimization's name. */}
          <ol className="proc-steps">
            {OPTIMIZATIONS.map((o, i) => (
              <li
                key={o.step}
                data-index={i}
                ref={(el) => { sections.current[i] = el }}
                className={`proc-step${i === active ? ' is-active' : ''}`}
              >
                <span className="timeline-marker" aria-hidden="true">
                  {o.mark}
                </span>
                <div className="proc-step-text">
                  <span className="proc-step-label">{o.step}</span>
                  <h4>{o.title}</h4>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}
