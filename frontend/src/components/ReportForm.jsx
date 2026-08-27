import { useState } from 'react'
import { api } from '../api'
import { HAZARD_LABELS } from '../constants'

/**
 * Submit a road image.
 *
 * Location comes from one of three sources, in this order:
 *
 *   1. a click on the map          -- the demo-safe default
 *   2. EXIF GPS inside the photo   -- the backend reads it if present
 *   3. the browser's geolocation   -- a bonus, and often unavailable
 *
 * Browser geolocation only works on https:// or localhost, so a phone
 * pointed at this dashboard over LAN will get nothing. That is exactly why
 * clicking the map is the primary path.
 */
export default function ReportForm({ pendingLocation, onClearLocation, onSubmitted }) {
  const [file, setFile] = useState(null)
  const [hazardType, setHazardType] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [geoNote, setGeoNote] = useState(null)

  function useBrowserLocation() {
    if (!('geolocation' in navigator)) {
      setGeoNote('This browser has no geolocation API.')
      return
    }
    if (!window.isSecureContext) {
      setGeoNote(
        'Blocked: geolocation needs https:// or localhost. Click the map instead.',
      )
      return
    }
    setGeoNote('Locating...')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGeoNote(`Fix accurate to about ${Math.round(position.coords.accuracy)} m.`)
        onSubmitted?.locationFromBrowser?.(
          position.coords.latitude, position.coords.longitude,
        )
      },
      (err) => setGeoNote(`Geolocation failed: ${err.message}. Click the map instead.`),
      { enableHighAccuracy: true, timeout: 8000 },
    )
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    setResult(null)

    if (!file && !hazardType) {
      setError('Choose a photo, or pick a hazard type to report without one.')
      return
    }

    const form = new FormData()
    if (file) form.append('image', file)
    if (hazardType) form.append('hazard_type', hazardType)
    if (pendingLocation) {
      form.append('latitude', pendingLocation.latitude)
      form.append('longitude', pendingLocation.longitude)
      form.append('location_source', pendingLocation.source ?? 'manual')
    }

    setBusy(true)
    try {
      const response = await api.submitDetection(form)
      setResult(response)
      setFile(null)
      event.target.reset()
      onSubmitted?.refresh?.(response)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel report-form" onSubmit={submit}>
      <h2>Report a hazard</h2>

      <label className="field">
        <span>Road photo</span>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </label>

      <label className="field">
        <span>Hazard type <em>(optional -- overrides the detector)</em></span>
        <select value={hazardType} onChange={(e) => setHazardType(e.target.value)}>
          <option value="">Let the detector decide</option>
          {Object.entries(HAZARD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </label>

      <div className="field">
        <span>Location</span>
        {pendingLocation ? (
          <div className="location-chip">
            <code>
              {pendingLocation.latitude.toFixed(5)}, {pendingLocation.longitude.toFixed(5)}
            </code>
            <span className="badge subtle">{pendingLocation.source}</span>
            <button type="button" className="link" onClick={onClearLocation}>clear</button>
          </div>
        ) : (
          <p className="hint">
            Click anywhere on the map to set it, or rely on the photo&rsquo;s EXIF GPS.
          </p>
        )}
        <button type="button" className="ghost small" onClick={useBrowserLocation}>
          Use my location
        </button>
        {geoNote && <p className="hint">{geoNote}</p>}
      </div>

      <button type="submit" className="primary" disabled={busy}>
        {busy ? 'Analysing...' : 'Submit detection'}
      </button>

      {error && <p className="alert error">{error}</p>}
      {result && (
        <div className={`alert ${result.detections_found ? 'success' : 'neutral'}`}>
          <strong>{result.message}</strong>
          <p className="hint">
            Detector: {result.detector} &middot; location from {result.location_source}
          </p>
          {result.image_url && (
            <img className="thumb" src={result.image_url} alt="Submitted road" />
          )}
        </div>
      )}
    </form>
  )
}
