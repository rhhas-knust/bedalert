import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import AlertFeed from '../components/AlertFeed.jsx'

const CITY_PRESETS = [
  { label: 'London, UK', lat: 51.5074, lng: -0.1278 },
  { label: 'Manchester, UK', lat: 53.4808, lng: -2.2426 },
  { label: 'Nairobi, Kenya', lat: -1.2921, lng: 36.8219 },
  { label: 'Kisumu, Kenya', lat: -0.0917, lng: 34.7680 },
  { label: 'Accra, Ghana', lat: 5.5362, lng: -0.2266 },
  { label: 'Kumasi, Ghana', lat: 6.6885, lng: -1.6244 },
  { label: 'Tamale, Ghana', lat: 9.4008, lng: -0.8393 },
  { label: 'Austin, USA', lat: 30.2672, lng: -97.7431 },
]

export default function DispatcherConsole() {
  const [preset, setPreset] = useState(CITY_PRESETS[0])
  const [severity, setSeverity] = useState('severe')
  const [department, setDepartment] = useState('ER')
  const [notes, setNotes] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [alerts, setAlerts] = useState([])
  const [emergencyLog, setEmergencyLog] = useState([])

  const isCritical = severity === 'critical'
  const effectiveDept = isCritical ? 'ER' : department

  const refresh = () => {
    api.getAlerts().then(setAlerts).catch(() => {})
    api.getEmergencyLog().then(setEmergencyLog).catch(() => {})
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    try {
      const res = await api.dispatchEmergency({
        lat: preset.lat,
        lng: preset.lng,
        severity,
        department_needed: effectiveDept,
        condition_notes: notes,
      })
      setResult(res)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-2 flex flex-col gap-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-navy">Dispatcher console</h1>
          <p className="text-slate-muted text-sm mt-1">
            Reports the nearest hospital with capacity, reserves a bed, and alerts the on-call doctor.
          </p>
        </div>

        <form onSubmit={submit} className="bg-white rounded-xl border border-slate-200 p-6 flex flex-col gap-4 max-w-md">
          <label className="text-sm text-slate-muted">
            Incident location
            <select
              value={preset.label}
              onChange={(e) => setPreset(CITY_PRESETS.find((p) => p.label === e.target.value))}
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            >
              {CITY_PRESETS.map((p) => (
                <option key={p.label}>{p.label}</option>
              ))}
            </select>
          </label>
          <label className="text-sm text-slate-muted">
            Severity
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            >
              <option value="critical">Critical</option>
              <option value="severe">Severe</option>
              <option value="moderate">Moderate</option>
            </select>
          </label>
          <label className="text-sm text-slate-muted">
            Department needed
            <select
              value={effectiveDept}
              disabled={isCritical}
              onChange={(e) => setDepartment(e.target.value)}
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-muted"
            >
              <option value="ER">Emergency</option>
              <option value="ICU">ICU</option>
            </select>
            {isCritical && (
              <span className="text-xs text-coral">Critical cases always route to Emergency.</span>
            )}
          </label>
          <label className="text-sm text-slate-muted">
            Notes for the hospital
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. multi-vehicle collision, unconscious"
              className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            />
          </label>
          <button className="mt-2 px-4 py-2 rounded-md bg-coral text-white text-sm font-semibold hover:bg-coral/90">
            Find hospital &amp; dispatch
          </button>
        </form>

        {error && (
          <p className="text-coral text-sm bg-coral/10 border border-coral/30 rounded-md px-4 py-3 max-w-md">
            {error}
          </p>
        )}

        {result && (
          <div className="bg-mint/20 border border-mint-dark rounded-xl p-6 max-w-md flex flex-col gap-1">
            <p className="text-xs uppercase tracking-wide text-teal-dark font-medium">Dispatch confirmed</p>
            <p className="font-display text-lg font-semibold text-navy">{result.hospital_name}</p>
            <p className="text-sm text-slate-muted">
              {result.department} · {result.distance_km} km · ETA ~{result.eta_minutes_estimate} min
            </p>
            <p className="text-sm text-slate-muted">Notified: {result.notified_doctor}</p>
            <p className="font-mono-data text-xs text-slate-muted mt-1">
              Dispatch {result.dispatch_id} · code {result.emergency_code}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-8">
        <div>
          <h2 className="font-display font-semibold text-navy mb-3">Surge alerts</h2>
          <AlertFeed alerts={alerts} />
        </div>

        <div>
          <h2 className="font-display font-semibold text-navy mb-1">Live emergency feed</h2>
          <p className="text-xs text-slate-muted mb-3">
            Emergencies from the public app, SMS/USSD, and this console — all in one place.
          </p>
          {emergencyLog.length === 0 ? (
            <p className="text-sm text-slate-muted">No emergencies logged yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {emergencyLog.map((e) => (
                <li key={e.code} className="bg-white border border-slate-200 rounded-md px-3 py-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-navy">{e.hospital_name}</p>
                    <span className="text-[10px] uppercase tracking-wide bg-slate-bg px-2 py-0.5 rounded text-slate-muted">
                      {e.source}
                    </span>
                  </div>
                  <p className="text-xs text-slate-muted">{e.severity}{e.condition_notes ? ` — ${e.condition_notes}` : ''}</p>
                  <p className="font-mono-data text-[10px] text-slate-muted mt-1">{e.code}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
