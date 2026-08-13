import { useEffect, useRef, useState } from 'react'
import { PageTabs } from '../components/PageTabs'

/**
 * Scroll-linked heat maps. The map is pinned on the left; the five field write-ups scroll
 * past on the right, and the pinned map crossfades to whichever section is in view.
 *
 * The swap is driven by an IntersectionObserver on the sections (no scroll library). The
 * maps themselves are `web/public/heatmaps/*.svg`, learned on the build split at 80%.
 */
interface Field {
  field: string
  title: string
  gloss: string
  /** % of the page the 80% region covers. */
  area: number
  /** grid cells the region spans, out of 2,500. */
  cells: number
  /** % of held-out (val) values whose whole box lands inside the region. */
  containment: number
  /** labelled invoices the region was learned from. */
  buildN: number
}

// Measured: the region is learned on `build`, containment scored on the held-out `val`
// split. Keep in step with scripts/gen_display.py and the SVGs it writes.
const FIELDS: Field[] = [
  { field: 'customer_billing_name', title: 'Customer billing name', gloss: 'who the invoice is billed to', area: 8.4, cells: 209, containment: 63.9, buildN: 3019 },
  { field: 'amount_due', title: 'Amount due', gloss: 'how much is owed', area: 25.8, cells: 645, containment: 67.7, buildN: 2645 },
  { field: 'date_issue', title: 'Date issued', gloss: 'when it was issued', area: 19.8, cells: 494, containment: 69.5, buildN: 2973 },
  { field: 'amount_total_gross', title: 'Total (gross)', gloss: 'the gross total', area: 20.9, cells: 522, containment: 67.2, buildN: 2588 },
  { field: 'vendor_address', title: 'Vendor address', gloss: 'where it came from', area: 25.2, cells: 630, containment: 76.7, buildN: 2620 },
]

export default function HeatMaps() {
  const [active, setActive] = useState(0)
  const sections = useRef<(HTMLElement | null)[]>([])

  useEffect(() => {
    // The active field is the write-up crossing the horizontal centre line of the viewport.
    // An IntersectionObserver with a zero-height root band at 50%/50% reacts to rendered
    // position directly (not to scroll events), so it is immune to programmatic scrolls and
    // momentum alike. Sections are contiguous, so exactly one holds the centre line; the
    // guard picks the lowest index if a boundary ever reports two at once.
    const intersecting = new Map<number, boolean>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          intersecting.set(Number((e.target as HTMLElement).dataset.index), e.isIntersecting)
        }
        // Among the sections currently in the band, choose the one whose centre is nearest
        // the viewport's centre — correct even when two straddle the band at a boundary.
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
    <>
      <PageTabs />

      <div className="hm-scroll">
        <div className="hm-media-col">
          <div className="hm-sticky">
            <div className="hm-frame">
              {FIELDS.map((f, i) => (
                <img
                  key={f.field}
                  src={`/heatmaps/${f.field}.svg`}
                  alt={`${f.title} heat map — the 80% region covers ${f.area}% of the page`}
                  className={`hm-map${i === active ? ' is-active' : ''}`}
                  loading={i === 0 ? 'eager' : 'lazy'}
                  aria-hidden={i === active ? undefined : true}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="hm-sections">
          {FIELDS.map((f, i) => (
            <section
              key={f.field}
              data-index={i}
              ref={(el) => { sections.current[i] = el }}
              className={`hm-section${i === active ? ' is-active' : ''}`}
            >
              <span className="hm-index">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="hm-title">{f.title}</h3>
              <p className="hm-gloss">{f.gloss}</p>
              <dl className="hm-stats">
                <div><dt>Region</dt><dd>{f.area}% of the page</dd></div>
                <div><dt>Grid</dt><dd>{f.cells} / 2,500 cells</dd></div>
                <div><dt>Held&#8209;out</dt><dd>{f.containment}% inside</dd></div>
              </dl>
              <p className="hm-foot">Learned from {f.buildN.toLocaleString()} labelled invoices</p>
            </section>
          ))}
        </div>
      </div>
    </>
  )
}
