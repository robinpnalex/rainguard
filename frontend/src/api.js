// Every call to the RainGuard backend lives here.
//
// In development VITE_API_BASE is unset, so BASE is '/api' and the Vite dev
// proxy forwards to localhost:8000 (see vite.config.js). In production the
// dashboard and the API are on different hosts, so VITE_API_BASE holds the
// backend's full origin, e.g. https://rainguard-api.onrender.com
export const API_ORIGIN = import.meta.env.VITE_API_BASE ?? ''
const BASE = API_ORIGIN || '/api'

/**
 * Absolute URL for an image the API returned.
 *
 * The backend hands back site-relative paths like `/images/abc.jpg`, which
 * only resolve against the dashboard's own origin. Split across two hosts
 * they have to be prefixed with the API origin or every photo 404s.
 */
export function assetUrl(path) {
  return path ? API_ORIGIN + path : null
}

async function request(path, options = {}) {
  const response = await fetch(BASE + path, options)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return response.json()
}

export const api = {
  health: () => request('/health'),
  stats: () => request('/stats'),
  hazards: () => request('/hazards'),
  hazard: (id) => request(`/hazards/${id}`),

  markRepaired: (id) => request(`/hazards/${id}/repair`, { method: 'POST' }),
  reopen: (id) => request(`/hazards/${id}/reopen`, { method: 'POST' }),

  submitDetection: (formData) =>
    request('/detections', { method: 'POST', body: formData }),

  verifyRepair: (id, formData) =>
    request(`/hazards/${id}/verify`, { method: 'POST', body: formData }),

  routeStatus: () => request('/route/status'),
  route: (formData) => request('/route', { method: 'POST', body: formData }),

  seedDemo: () => request('/demo/seed', { method: 'POST' }),
  resetDemo: () => request('/demo/reset', { method: 'POST' }),
  runStory: (failFirst) =>
    request(`/demo/story?fail_first_repair=${failFirst ? 'true' : 'false'}`, {
      method: 'POST',
    }),
}
