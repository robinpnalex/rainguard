// Every call to the RainGuard backend lives here.
const BASE = '/api'

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
