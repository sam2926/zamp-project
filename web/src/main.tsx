import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import App, { Contained } from './App'
import Dashboard from './screens/Dashboard'
import FutureOptimizations from './screens/FutureOptimizations'
import HeatMaps from './screens/HeatMaps'
import Home from './screens/Home'
import LiveProgress from './screens/LiveProgress'
import Process from './screens/Process'
import Queue from './screens/Queue'
import Result from './screens/Result'
import Upload from './screens/Upload'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Every route renders inside the app shell, so they share one dark plane. */}
        <Route element={<App />}>
          {/* The landing and the two workflow pages fill their own plane edge to edge. */}
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/live" element={<LiveProgress />} />
          <Route path="/process" element={<Process />} />

          {/* The rest take the standard page gutter. */}
          <Route element={<Contained />}>
            <Route path="/documents/:id" element={<Result />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/heatmaps" element={<HeatMaps />} />
            <Route path="/future" element={<FutureOptimizations />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
