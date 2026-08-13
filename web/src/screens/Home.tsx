import { Link } from 'react-router-dom'

import { PageTabs } from '@/components/PageTabs'

/**
 * The landing: one screen, no scroll, no animation.
 *
 * It renders inside the app shell, so it sits on the same dark plane and carries
 * the same PageTabs row as every other page. A split hero — the pitch and a
 * plain "what it does" card — with three small section cards spread beneath it,
 * each a shortcut to its tab.
 */
export default function Home() {
  return (
    <div className="home">
      <div className="home-gutter">
        <PageTabs />

        <div className="home-body">
          <section className="home-hero">
            <div className="home-lead">
              <span className="home-eyebrow">Invoice field extraction</span>
              <h1 className="home-title">
                Transform Your Business with <span className="home-nowrap">AI-Powered</span> Solutions
              </h1>
              <ul className="home-sub home-sub-list">
                <li>We read the fields that matter off a scanned invoice.</li>
                <li>We check every answer before we trust it — fewer tokens, more to trust.</li>
              </ul>
              <div className="home-cta">
                <Link to="/upload" className="home-btn is-primary">
                  Try it on an invoice
                </Link>
                <Link to="/dashboard" className="home-btn is-ghost">
                  CR results
                </Link>
              </div>
            </div>

            <aside className="home-card">
              <span className="home-card-eyebrow">What this platform does for you</span>
              <p className="home-card-lead">
                A simple way to turn scattered, unstructured invoices into clean, organized data.
              </p>
              <ol className="home-steps">
                <li className="home-step">
                  <span className="home-step-n">1</span>
                  <div className="home-step-body">
                    <strong>Upload your invoices</strong>
                    <p>Bring your files in whatever form they arrive.</p>
                  </div>
                </li>
                <li className="home-step">
                  <span className="home-step-n">2</span>
                  <div className="home-step-body">
                    <strong>We extract what you need</strong>
                    <p>Our platform reads each one and pulls out the fields that matter to you.</p>
                  </div>
                </li>
                <li className="home-step">
                  <span className="home-step-n">3</span>
                  <div className="home-step-body">
                    <strong>Get organized data back</strong>
                    <p>Receive structured, ready-to-use records.</p>
                  </div>
                </li>
              </ol>
            </aside>
          </section>

          <div className="home-mini-cards">
            <Link to="/process" className="home-mini">
              <span className="home-mini-title">Process</span>
              <span className="home-mini-desc">How a document is processed, step by step.</span>
            </Link>
            <Link to="/dashboard" className="home-mini">
              <span className="home-mini-title">Accuracy</span>
              <span className="home-mini-desc">How accurate the extraction is, measured.</span>
            </Link>
            <Link to="/heatmaps" className="home-mini">
              <span className="home-mini-title">Heat maps</span>
              <span className="home-mini-desc">Where each field tends to sit on the page.</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
