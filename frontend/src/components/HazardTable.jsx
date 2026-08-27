import { formatDate, hazardColour, HAZARD_LABELS, STATUS_LABELS } from '../constants'

export default function HazardTable({ hazards, selectedId, onSelect }) {
  return (
    <div className="panel table-panel">
      <h2>All hazards ({hazards.length})</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Type</th><th>Severity</th><th>Conf.</th>
              <th>Obs.</th><th>Status</th><th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {hazards.map((hazard) => (
              <tr
                key={hazard.id}
                className={hazard.id === selectedId ? 'selected' : ''}
                onClick={() => onSelect(hazard.id)}
              >
                <td>{hazard.id}</td>
                <td>{HAZARD_LABELS[hazard.type] ?? hazard.type}</td>
                <td>
                  <span className="sev-dot" style={{ background: hazardColour(hazard) }} />
                  {hazard.severity}
                </td>
                <td>{Math.round(hazard.avg_confidence * 100)}%</td>
                <td>{hazard.observation_count}</td>
                <td><span className="status-cell">{STATUS_LABELS[hazard.status] ?? hazard.status}</span></td>
                <td>{formatDate(hazard.last_seen)}</td>
              </tr>
            ))}
            {hazards.length === 0 && (
              <tr><td colSpan={7} className="hint">No hazards yet. Seed the demo data or submit a detection.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
