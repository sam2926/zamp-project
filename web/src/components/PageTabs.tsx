import { Link, NavLink } from 'react-router-dom'

import { TABS } from '../tabs'

/**
 * The product mark: a document with its learned region highlighted — the one idea
 * the whole app is about (we send the model a small region of the page, not all of it).
 * Gold picks up the plane's accent; the outline takes the pill's text colour.
 */
function LogoMark() {
  return (
    <svg className="page-logo" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="2.75" width="16" height="18.5" rx="3.2" stroke="currentColor" strokeWidth="1.6" />
      <rect x="7" y="6.2" width="8.4" height="4.6" rx="1.3" fill="#c9ba92" />
      <line x1="7.6" y1="14.4" x2="16.4" y2="14.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
      <line x1="7.6" y1="17.4" x2="12.8" y2="17.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
    </svg>
  )
}

/**
 * The tab pills, rendered as page content rather than as a chrome bar.
 *
 * A Home pill is pinned to the far left (it returns to the landing); the section
 * tabs sit on the right. There is no wrapper background, border or sticky behaviour —
 * the row sits on whatever plane the page provides and inherits its tone.
 */
export function PageTabs() {
  return (
    <div className="page-tabs">
      <Link to="/" className="page-home" aria-label="Home">
        <LogoMark />
        <span>Home</span>
      </Link>
      <nav className="page-tabs-row" aria-label="Sections">
        {TABS.map((tab) => (
          <NavLink key={tab.id} to={tab.path}>
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
