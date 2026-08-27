export const HAZARD_LABELS = {
  pothole: 'Pothole',
  manhole: 'Open / damaged manhole',
  waterlogging: 'Waterlogging',
}

export const HAZARD_GLYPHS = {
  pothole: '●',
  manhole: '◎',
  waterlogging: '≈',
}

export const STATUS_LABELS = {
  SUSPECTED: 'Suspected',
  CONFIRMED: 'Confirmed',
  REPAIR_PENDING: 'Repair pending',
  REPAIRED: 'Repaired (unverified)',
  VERIFIED: 'Verified fixed',
}

// Marker colour: repair status wins over risk band, because "is it fixed?"
// is the question a municipality actually looks at the map to answer.
const RISK_COLOURS = { low: '#60a5fa', medium: '#f59e0b', high: '#ef4444' }
const STATUS_COLOURS = {
  REPAIR_PENDING: '#a855f7',
  REPAIRED: '#2dd4bf',
  VERIFIED: '#22c55e',
}

export function hazardColour(hazard) {
  return STATUS_COLOURS[hazard.status] ?? RISK_COLOURS[hazard.risk_band] ?? '#94a3b8'
}

export function formatDate(value) {
  if (!value) return '--'
  const date = new Date(value.endsWith('Z') ? value : value + 'Z')
  return date.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}
