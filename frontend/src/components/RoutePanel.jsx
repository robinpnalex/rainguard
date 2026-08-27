import { useEffect, useState } from 'react'
import { api } from '../api'
import { LANDMARKS } from '../landmarks'

/**
 * Optional safe-routing demo.
 *
 *     safe_cost = road_length + (severity * 60 m) for each hazard on the road
 *
 * The panel hides itself if the backend reports routing is unavailable, so
 * the core hazard workflow never depends on osmnx being installed.
 */
export default function RoutePanel({ onRoute }) {
  const [status, setStatus] = useState(null)
  const [start, setStart] = useState(LANDMARKS[0].name)
  const [end, setEnd] = useState(LANDMARKS[1].name)
  const [minSeverity, setMinSeverity] = useState(5)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.routeStatus().then(setStatus).catch(() => setStatus({ available: false }))
  }, [])

  if (!status) return null
  if (!status.available || !status.graph_cached) {
    return (
      <div className="panel">
        <h2>Safe routing</h2>
        <p className="hint">
          Optional module, not enabled. {status.hint}
        </p>
      </div>
    )
  }

  async function findRoute(event) {
    event.preventDefault()
    setError(null)
    setBusy(true)
    const from = LANDMARKS.find((l) => l.name === start)
    const to = LANDMARKS.find((l) => l.name === end)
    const form = new FormData()
    form.append('start_latitude', from.latitude)
    form.append('start_longitude', from.longitude)
    form.append('end_latitude', to.latitude)
    form.append('end_longitude', to.longitude)
    form.append('min_severity', minSeverity)
    try {
      const response = await api.route(form)
      setResult(response)
      onRoute(response)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel" onSubmit={findRoute}>
      <h2>Safe routing</h2>

      <label className="field">
        <span>From</span>
        <select value={start} onChange={(e) => setStart(e.target.value)}>
          {LANDMARKS.map((l) => <option key={l.name}>{l.name}</option>)}
        </select>
      </label>

      <label className="field">
        <span>To</span>
        <select value={end} onChange={(e) => setEnd(e.target.value)}>
          {LANDMARKS.map((l) => <option key={l.name}>{l.name}</option>)}
        </select>
      </label>

      <label className="field">
        <span>Avoid hazards at or above severity {minSeverity}</span>
        <input
          type="range" min="1" max="10" step="0.5" value={minSeverity}
          onChange={(e) => setMinSeverity(Number(e.target.value))}
        />
      </label>

      <button type="submit" className="primary" disabled={busy || start === end}>
        {busy ? 'Routing...' : 'Compare routes'}
      </button>

      {error && <p className="alert error">{error}</p>}
      {result && (
        <div className="alert neutral route-summary">
          <div><i className="swatch shortest" /> Shortest: <strong>{(result.shortest.distance_metres / 1000).toFixed(2)} km</strong>, {result.shortest.hazard_count} hazard(s)</div>
          <div><i className="swatch safest" /> Safer: <strong>{(result.safest.distance_metres / 1000).toFixed(2)} km</strong>, {result.safest.hazard_count} hazard(s)</div>
          <p className="hint">
            {result.hazards_avoided > 0
              ? `${result.detour_metres} m longer, avoiding ${result.hazards_avoided} hazard(s).`
              : 'No safer alternative on this stretch -- the shortest route is already the best available.'}
          </p>
        </div>
      )}
    </form>
  )
}
