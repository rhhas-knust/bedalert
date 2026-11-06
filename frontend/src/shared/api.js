// One small client for the BedAlert API, shared by every app.
// In development it talks to a local API; on Vercel set VITE_API_URL to the
// deployed API (no trailing slash).
const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '') + '/v1'

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function detailMessage(data) {
  if (!data) return null
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg?.replace(/^Value error, /, '')).join('; ')
  return null
}

export async function request(path, { method = 'GET', body, token, signal } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError(0, 'Cannot reach BedAlert right now. Check your connection and try again.')
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailMessage(data) || `Something went wrong (${res.status}).`)
  return data
}

export const qs = (params) => {
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return p.length ? '?' + new URLSearchParams(p).toString() : ''
}
