import { Outlet } from 'react-router-dom'

/**
 * Shell for every page except the landing.
 *
 * Deliberately bare: there is no chrome bar. Each page renders its own
 * <PageTabs /> inside its own plane, so the tabs read as part of the page.
 */
export default function App() {
  return (
    <div className="shell">
      <Outlet />
    </div>
  )
}

/** Routes whose content wants the standard page gutter. Upload and Process are
 *  deliberately outside this — they fill their own plane edge to edge. */
export function Contained() {
  return (
    <main className="main">
      <Outlet />
    </main>
  )
}
