import { useCallback, useEffect, useMemo, useState } from 'react'
import 'leaflet/dist/leaflet.css'
import './index.css'

import { api } from './api'
import { HAZARD_LABELS, STATUS_LABELS } from './constants'
import MapView from './components/MapView'
import HazardDetail from './components/HazardDetail'
import HazardTable from './components/HazardTable'
import ReportForm from './components/ReportForm'
import StoryPanel from './components/StoryPanel'
import RoutePanel from './components/RoutePanel'

const DEFAULT_CENTRE = { latitude: 13.3525, longitude: 74.7868 }

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'open', label: 'Open only' },
  { key: 'high', label: 'High risk' },
  { key: 'repair', label: 'Awaiting repair proof' },
]

export default function App() {
  const [health, setHealth] = useState(null)
  const [stats, setStats] = useState(null)
  const [hazards, setHazards] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [pendingLocation, setPendingLocation] = useState(null)
  const [filter, setFilter] = useState('all')
  const [story, setStory] = useState(null)
  const [banner, setBanner] = useState(null)
  const [offline, setOffline] = useState(false)
  const [routes, setRoutes] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [hazardList, statsData] = await Promise.all([api.hazards(), api.stats()])
      setHazards(hazardList)
      setStats(statsData)
      setOffline(false)
    } catch {
      setOffline(true)
    }
  }, [])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setOffline(true))
    refresh()
  }, [refresh])

  // Keep the detail panel in step with the selected marker.
  useEffect(() => {
    if (selectedId == null) {
      setSelected(null)
      return
    }
    api.hazard(selectedId).then(setSelected).catch(() => setSelected(null))
  }, [selectedId, hazards])

  const visible = useMemo(() => {
    switch (filter) {
      case 'open': return hazards.filter((h) => h.status !== 'VERIFIED')
      case 'high': return hazards.filter((h) => h.risk_band === 'high' && h.status !== 'VERIFIED')
      case 'repair': return hazards.filter((h) => h.status === 'REPAIR_PENDING' || h.status === 'REPAIRED')
      default: return hazards
    }
  }, [hazards, filter])

  async function runDemoAction(action, label) {
    setBanner({ text: `${label}...`, ok: true })
    try {
      const result = await action()
      setBanner({ text: result.message ?? `${label} complete.`, ok: true })
      await refresh()
      return result
    } catch (err) {
      setBanner({ text: err.message, ok: false })
      return null
    }
  }

  const centre = health?.map_centre ?? DEFAULT_CENTRE
  const flyTarget = selected ?? null

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">RG</span>
          <div>
            <h1>RainGuard</h1>
            <p>AI-assisted road hazard monitoring &mdash; Manipal</p>
          </div>
        </div>

        <div className="kpis">
          <Kpi label="Hazards" value={stats?.total_hazards ?? '--'} />
          <Kpi label="Open" value={stats?.open_hazards ?? '--'} />
          <Kpi label="High risk" value={stats?.high_risk_open ?? '--'} tone="danger" />
          <Kpi label="Observations" value={stats?.total_observations ?? '--'} />
          <Kpi label="Verified fixed" value={stats?.by_status?.VERIFIED ?? 0} tone="good" />
        </div>

        <div className="demo-controls">
          <button className="ghost small" onClick={() => runDemoAction(api.seedDemo, 'Seeding Manipal demo data')}>
            Seed demo data
          </button>
          <button
            className="primary small"
            onClick={async () => {
              const result = await runDemoAction(() => api.runStory(true), 'Running demo story')
              if (result) {
                setStory(result)
                setSelectedId(result.hazard_id)
              }
            }}
          >
            Run demo story
          </button>
          <button
            className="ghost small"
            onClick={() => {
              setSelectedId(null); setStory(null)
              runDemoAction(api.resetDemo, 'Clearing database')
            }}
          >
            Reset
          </button>
        </div>
      </header>

      {offline && (
        <p className="alert error banner">
          Cannot reach the backend. Start it with{' '}
          <code>uvicorn main:app --reload</code> in <code>backend/</code>.
        </p>
      )}
      {banner && (
        <p className={`alert ${banner.ok ? 'success' : 'error'} banner`}>{banner.text}</p>
      )}

      <main className="layout">
        <section className="map-column">
          <div className="map-toolbar">
            <div className="filters">
              {FILTERS.map((option) => (
                <button
                  key={option.key}
                  className={`chip ${filter === option.key ? 'active' : ''}`}
                  onClick={() => setFilter(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <Legend />
          </div>

          <MapView
            hazards={visible}
            centre={centre}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onMapClick={(lat, lng) =>
              setPendingLocation({ latitude: lat, longitude: lng, source: 'manual' })
            }
            pendingLocation={pendingLocation}
            flyTarget={flyTarget}
            routes={routes}
          />

          <HazardTable hazards={visible} selectedId={selectedId} onSelect={setSelectedId} />
        </section>

        <aside className="side-column">
          <HazardDetail
            hazard={selected}
            onChanged={refresh}
            onClose={() => setSelectedId(null)}
          />
          <ReportForm
            pendingLocation={pendingLocation}
            onClearLocation={() => setPendingLocation(null)}
            onSubmitted={{
              refresh: async (result) => {
                await refresh()
                const id = result.created_hazard_ids[0] ?? result.updated_hazard_ids[0]
                if (id) setSelectedId(id)
                setPendingLocation(null)
              },
              locationFromBrowser: (latitude, longitude) =>
                setPendingLocation({ latitude, longitude, source: 'browser' }),
            }}
          />
          <RoutePanel onRoute={setRoutes} />
          <StoryPanel
            story={story}
            onClose={() => setStory(null)}
            onSelectHazard={setSelectedId}
          />
          {health && (
            <div className="panel meta">
              <h2>Pipeline</h2>
              <dl className="facts">
                <div><dt>Detector</dt><dd>{health.detector}</dd></div>
                <div><dt>Dedup radius</dt><dd>{health.dedup_radius_metres} m</dd></div>
                <div><dt>Confirm at</dt><dd>{health.observations_for_confirmed} observations</dd></div>
                <div><dt>Verify at</dt><dd>{health.clean_observations_for_verified} clean checks</dd></div>
              </dl>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}

function Kpi({ label, value, tone }) {
  return (
    <div className={`kpi ${tone ?? ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function Legend() {
  const items = [
    ['#60a5fa', 'Low risk'],
    ['#f59e0b', 'Medium'],
    ['#ef4444', 'High risk'],
    ['#a855f7', 'Repair pending'],
    ['#22c55e', 'Verified fixed'],
  ]
  return (
    <div className="legend">
      {items.map(([colour, label]) => (
        <span key={label}>
          <i style={{ background: colour }} />
          {label}
        </span>
      ))}
    </div>
  )
}
