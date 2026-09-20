/**
 * ARPT backend API client.
 * All calls hit the FastAPI server (proxied via vite dev server at /api).
 */

const json = async (r) => {
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body?.detail) detail = body.detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return r.json()
}

export const getOverview = () => fetch('/api/overview').then(json)
export const getQueue = () => fetch('/api/queue').then(json)
export const getReports = () => fetch('/api/reports').then(json)
export const getReport = (id) => fetch(`/api/reports/${id}`).then(json)

export const submitReview = (id, body) =>
  fetch(`/api/reports/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json)

export const videoUrl = (id) => `/api/reports/${id}/video`
export const skelUrl = (id) => `/api/reports/${id}/skel`

/** Map an asymmetry percentage to a CoreUI color token. */
export const riskColor = (pct) => {
  if (pct == null) return 'secondary'
  if (pct >= 60) return 'danger'
  if (pct >= 35) return 'warning'
  if (pct >= 15) return 'info'
  return 'success'
}

/** Map an urgency string to a CoreUI color token. */
export const urgencyColor = (u) =>
  ({ urgent: 'danger', soon: 'warning', routine: 'success' })[u] || 'secondary'

/** Map a review status to a CoreUI color token. */
export const statusColor = (s) =>
  ({ pending: 'warning', confirmed: 'success', revised: 'danger' })[s] || 'secondary'
