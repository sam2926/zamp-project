import { PageTabs } from '../components/PageTabs'
import { EmptyState } from '../components/States'
import { InboxIcon } from '../components/icons'

/** Routed and reachable, but nothing is built behind it yet — a designed
 *  placeholder rather than a dead tab or a blank page. */
export default function FutureOptimizations() {
  return (
    <>
      <PageTabs />
      <div className="page-head">
        <h1>Future optimizations</h1>
        <p>What the system would do next, and what it would buy.</p>
      </div>

      <section className="card">
        <EmptyState
          icon={<InboxIcon size={18} />}
          title="Not built yet"
          body="This tab is wired up and routable, but there is nothing behind it so far. Tell me what it should show and I'll build it."
        />
      </section>
    </>
  )
}
