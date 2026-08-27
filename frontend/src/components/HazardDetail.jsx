import { useState } from 'react'
import { api, assetUrl } from '../api'
import { formatDate, hazardColour, HAZARD_LABELS, STATUS_LABELS } from '../constants'

export default function HazardDetail({ hazard, onChanged, onClose }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [file, setFile] = useState(null)

  if (!hazard) {
    return (
      <div className="panel detail empty">
        <h2>No hazard selected</h2>
        <p className="hint">
          Click a marker on the map, or a row in the table below, to inspect a hazard.
        </p>
      </div>
    )
  }

  async function run(action) {
    setBusy(true)
    setMessage(null)
    try {
      const result = await action()
      setMessage({ text: result.message ?? 'Updated.', ok: !result.still_detected })
      await onChanged()
    } catch (err) {
      setMessage({ text: err.message, ok: false })
    } finally {
      setBusy(false)
    }
  }

  const underRepair = hazard.status === 'REPAIR_PENDING' || hazard.status === 'REPAIRED'
  const verifyProgress = `${hazard.clean_observation_count}/${hazard.clean_observations_required}`

  function submitVerification(event) {
    event.preventDefault()
    const form = new FormData()
    if (file) form.append('image', file)
    else form.append('simulate', 'clean')
    run(() => api.verifyRepair(hazard.id, form)).then(() => setFile(null))
  }

  return (
    <div className="panel detail">
      <div className="detail-head">
        <h2>Hazard #{hazard.id}</h2>
        <button className="link" onClick={onClose}>close</button>
      </div>

      <span className="badge" style={{ background: hazardColour(hazard) }}>
        {STATUS_LABELS[hazard.status] ?? hazard.status}
      </span>
      {hazard.verification_failed && (
        <span className="badge danger">Last repair check failed</span>
      )}

      <dl className="facts">
        <div><dt>Type</dt><dd>{HAZARD_LABELS[hazard.type] ?? hazard.type}</dd></div>
        <div><dt>Severity</dt><dd><strong>{hazard.severity} / 10</strong> ({hazard.risk_band})</dd></div>
        <div><dt>Confidence</dt><dd>{Math.round(hazard.avg_confidence * 100)}%</dd></div>
        <div><dt>Observations</dt><dd>{hazard.observation_count}</dd></div>
        <div><dt>First seen</dt><dd>{formatDate(hazard.first_seen)}</dd></div>
        <div><dt>Last seen</dt><dd>{formatDate(hazard.last_seen)}</dd></div>
        <div><dt>Location</dt><dd><code>{hazard.latitude.toFixed(5)}, {hazard.longitude.toFixed(5)}</code></dd></div>
      </dl>

      {(hazard.before_image_url || hazard.after_image_url) && (
        <div className="before-after">
          <figure>
            <img src={assetUrl(hazard.before_image_url) ?? ''} alt="Hazard as detected" />
            <figcaption>Before &mdash; hazard detected</figcaption>
          </figure>
          <figure>
            {hazard.after_image_url ? (
              <img src={assetUrl(hazard.after_image_url)} alt="After repair" />
            ) : (
              <div className="thumb placeholder">No re-inspection yet</div>
            )}
            <figcaption>After &mdash; re-inspection</figcaption>
          </figure>
        </div>
      )}

      <div className="actions">
        {hazard.status === 'VERIFIED' ? (
          <p className="alert success">
            Repair verified by {hazard.clean_observation_count} independent clean
            re-inspections. This hazard is closed.
          </p>
        ) : underRepair ? (
          <>
            <p className="hint">
              Awaiting proof of repair &mdash; <strong>{verifyProgress}</strong> clean
              re-inspections recorded.
            </p>
            <form onSubmit={submitVerification} className="verify-form">
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <button type="submit" className="primary" disabled={busy}>
                {file ? 'Check this photo' : 'Record clean check (demo)'}
              </button>
            </form>
            <button
              className="ghost small"
              disabled={busy}
              onClick={() => run(() => api.reopen(hazard.id))}
            >
              Cancel repair claim
            </button>
          </>
        ) : (
          <button
            className="primary"
            disabled={busy}
            onClick={() => run(() => api.markRepaired(hazard.id))}
          >
            Mark as repaired
          </button>
        )}
      </div>

      {message && (
        <p className={`alert ${message.ok ? 'success' : 'error'}`}>{message.text}</p>
      )}

      <details className="log">
        <summary>Observation log ({hazard.observations?.length ?? 0})</summary>
        <ul>
          {(hazard.observations ?? []).map((obs) => (
            <li key={obs.id} className={obs.is_clean ? 'clean' : ''}>
              <span>{formatDate(obs.timestamp)}</span>
              <span>
                {obs.is_clean
                  ? 'clean re-inspection'
                  : `detected (${Math.round(obs.confidence * 100)}%)`}
              </span>
              <span className="badge subtle">{obs.location_source}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
