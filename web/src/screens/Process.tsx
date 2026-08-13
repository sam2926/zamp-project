import { useEffect, useRef, useState } from 'react'
import { PageTabs } from '../components/PageTabs'

/** The pipeline, in order — the region-crop approach we shipped, extracting
 *  customer_billing_name. Steps 0–1 are one-time setup from the customer's
 *  labelled documents; every step below runs per document. `points` are the
 *  card's bullets. */
const STEPS = [
  {
    mark: '0',
    step: 'Step 00',
    title: 'Get human-labelled data from the client',
    points: [
      'The client wants to automate a manual, unorganised process, their past invoices, already labelled by hand, are the only record of where each field sits.',
      'Everything downstream is learned from these labels: no labelled data, no region to crop to.',
      'The more examples, and the more varied the layouts, the tighter and more reliable the learned region, and the fewer documents fall to a human later.',
      'Nothing is fine-tuned; the labels are the one thing that teaches the system this client’s documents.',
    ],
  },
  {
    mark: '1',
    step: 'Step 01',
    title: 'Build the heat map',
    points: [
      'Runs once, from the labelled invoices collected above.',
      'Over a 50×50 grid, count every cell the field’s box touches, taking the billing name as our example, the whole box, not the centre.',
      'Take the smallest rectangle that still holds the majority of that mass, a trade-off between covering the value and keeping the region as small as possible.',
      'For our example, holding 95% of that mass takes just 21% of the page, the upper-left block.',
    ],
  },
  {
    mark: '2',
    step: 'Step 02',
    title: 'Seen this exact file before?',
    points: [
      'A SHA-256 of the file bytes is matched against everything processed before.',
      'A hit returns the stored answer at no cost.',
      'Only catches literal re-uploads, a fresh scan is different bytes and will not match.',
    ],
  },
  {
    mark: '3',
    step: 'Step 03',
    title: 'Read the page',
    points: [
      'docTR returns every word with its position and a per-word confidence.',
      'Local, no model call.',
      'The one step that always runs.',
    ],
  },
  {
    mark: '4',
    step: 'Step 04',
    title: 'Crop to the learned region',
    points: [
      'Keep only the words whose boxes fall entirely inside the learned rectangle.',
      'About 31% of the page’s text.',
      'Everything outside the region is dropped before the call.',
    ],
  },
  {
    mark: '5',
    step: 'Step 05',
    title: 'Ask the model for the billing name',
    points: [
      'One call, one field.',
      'Roughly a third of the tokens a whole-page read would cost.',
      'The name is inside the crop 92% of the time.',
    ],
  },
  {
    mark: '6',
    step: 'Step 06',
    title: 'Not found? Send the whole page',
    points: [
      'Covers the other 8%.',
      'A second call, on the full page.',
      'Never a truncated answer.',
    ],
  },
  {
    mark: '7',
    step: 'Step 07',
    title: 'Validate the value',
    points: [
      'Appears verbatim in the OCR text, catches invention outright.',
      '2–80 characters and contains letters; not pure digits or punctuation.',
      'Not a form label like “BILL TO” or “REMIT TO”.',
      'Not identical to the vendor name, the payer is not the sender.',
      'Word count plausible for an organisation (1–8).',
    ],
  },
  {
    mark: '8',
    step: 'Step 08',
    title: 'Score it',
    points: [
      'How sure docTR was about those words.',
      'How hot the cell the value landed in was.',
      '“Was it in the crop” is not a signal, a hit is in-region by definition.',
    ],
  },
  {
    mark: '9',
    step: 'Step 09',
    title: 'Route to a human if shaky',
    points: [
      'Confident extractions post straight through.',
      'Uncertain ones go to a person, flagged with the reason.',
    ],
  },
  {
    mark: '10',
    step: 'Step 10',
    title: 'Learn from corrections',
    points: [
      'Every human correction re-shapes the heat map.',
      'So the crop in step 4 tightens over time.',
    ],
  },
]

/**
 * Process.
 *
 * The same scroll-linked pattern as the heat maps (see HeatMaps.tsx): the step's
 * explanation card is a fixed rectangle, pinned and vertically centred on the
 * left, crossfading; the numbered step list scrolls past on the right, its
 * active heading landing at the same vertical centre as the card. One
 * IntersectionObserver flips `.is-active` — no scroll library.
 */
export default function Process() {
  const [active, setActive] = useState(0)
  const sections = useRef<(HTMLElement | null)[]>([])

  useEffect(() => {
    // The active step is the row crossing the horizontal centre band of the
    // viewport. Rows are contiguous, so exactly one holds the centre; if two
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
          {/* Pinned left: a fixed rectangle, centred on the y-axis, showing the
              explanation for whichever step is in view. */}
          <div className="proc-media-col">
            <div className="proc-sticky">
              <div className="proc-frame">
                {STEPS.map((s, i) => (
                  <article
                    key={s.step}
                    className={`timeline-card proc-card${i === active ? ' is-active' : ''}`}
                    aria-hidden={i === active ? undefined : true}
                  >
                    <span className="timeline-step">{s.step}</span>
                    <h3>{s.title}</h3>
                    <ul className="proc-bullets">
                      {s.points.map((p, j) => (
                        <li key={j}>{p}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </div>
          </div>

          {/* Scrolling right: the numbered marker and the step's name. */}
          <ol className="proc-steps">
            {STEPS.map((s, i) => (
              <li
                key={s.step}
                data-index={i}
                ref={(el) => { sections.current[i] = el }}
                className={`proc-step${i === active ? ' is-active' : ''}`}
              >
                <span className="timeline-marker" aria-hidden="true">
                  {s.mark}
                </span>
                <div className="proc-step-text">
                  <span className="proc-step-label">{s.step}</span>
                  <h4>{s.title}</h4>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}
