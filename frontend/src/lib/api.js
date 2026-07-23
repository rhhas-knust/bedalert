// In development this defaults to your local FastAPI server.
// In production (Vercel etc.), set VITE_API_URL to your deployed backend URL.
const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  getHospitals: () => request('/hospitals'),
  getHospital: (id) => request(`/hospitals/${id}`),
  registerHospital: (payload) =>
    request('/hospitals', { method: 'POST', body: JSON.stringify(payload) }),
  updateBeds: (id, payload) =>
    request(`/hospitals/${id}/beds`, { method: 'POST', body: JSON.stringify(payload) }),
  getAlerts: () => request('/alerts'),
  getEmergencyLog: () => request('/emergency-log'),
  createBooking: (payload) =>
    request('/bookings', { method: 'POST', body: JSON.stringify(payload) }),
  getHospitalBookings: (id) => request(`/hospitals/${id}/bookings`),
  dispatchEmergency: (payload) =>
    request('/dispatch/emergency', { method: 'POST', body: JSON.stringify(payload) }),
  sendSms: (payload) => request('/sms', { method: 'POST', body: JSON.stringify(payload) }),
}
