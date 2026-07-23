import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import CapacityBar from '../components/CapacityBar.jsx'

const emptyReg = {
  name: '', city: '', country: '', lat: '', lng: '',
  er_total: 10, icu_total: 5, general_total: 20,
}

export default function HospitalAdmin() {
  const [hospitals, setHospitals] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [hospital, setHospital] = useState(null)
  const [bookings, setBookings] = useState([])
  const [error, setError] = useState('')
  const [showRegister, setShowRegister] = useState(false)
  const [regForm, setRegForm] = useState(emptyReg)
  const [regError, setRegError] = useState('')

  function loadHospitals() {
    return api.getHospitals().then((list) => {
      setHospitals(list)
      if (list.length && !selectedId) setSelectedId(list[0].id)
      return list
    })
  }

  useEffect(() => { loadHospitals() }, [])

  useEffect(() => {
    if (!selectedId) return
    api.getHospital(selectedId).then(setHospital).catch((e) => setError(e.message))
    api.getHospitalBookings(selectedId).then(setBookings).catch(() => {})
  }, [selectedId])

  async function tap(department, delta) {
    try {
      const updated = await api.updateBeds(selectedId, { department, delta })
      setHospital(updated)
    } catch (err) {
      setError(err.message)
    }
  }

  async function submitRegistration(e) {
    e.preventDefault()
    setRegError('')
    if (!regForm.name || !regForm.city || !regForm.country || regForm.lat === '' || regForm.lng === '') {
      setRegError('Please fill in name, city, country, and coordinates.')
      return
    }
    try {
      const created = await api.registerHospital({
        ...regForm,
        lat: parseFloat(regForm.lat),
        lng: parseFloat(regForm.lng),
        er_total: Number(regForm.er_total),
        icu_total: Number(regForm.icu_total),
        general_total: Number(regForm.general_total),
        doctors: [],
      })
      await loadHospitals()
      setSelectedId(created.id)
      setShowRegister(false)
      setRegForm(emptyReg)
    } catch (err) {
      setRegError(err.message)
    }
  }

  if (!hospital) return <p className="text-slate-muted text-sm">Loading...</p>

  const demo = hospital.demographics

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h1 className="font-display text-2xl font-semibold text-navy">Hospital admin</h1>
        <p className="text-slate-muted text-sm mt-1">
          Update bed availability with a tap. Only anonymous counts and aggregate demographics are shared — never patient records.
        </p>
      </div>

      <div className="flex gap-2 items-center">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="flex-1 max-w-sm border border-slate-200 rounded-md px-3 py-2 text-sm bg-white"
        >
          {hospitals.map((h) => (
            <option key={h.id} value={h.id}>{h.name} — {h.city}</option>
          ))}
        </select>
        <button
          onClick={() => setShowRegister((s) => !s)}
          className="px-3 py-2 rounded-md border border-teal text-teal text-sm font-medium"
        >
          {showRegister ? 'Cancel' : '+ Register new hospital'}
        </button>
      </div>

      {showRegister && (
        <form onSubmit={submitRegistration} className="bg-white rounded-xl border border-slate-200 p-6 flex flex-col gap-3">
          <h2 className="font-display font-semibold text-navy">Register a new hospital</h2>
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Hospital name" value={regForm.name}
              onChange={(e) => setRegForm({ ...regForm, name: e.target.value })}
              className="border border-slate-200 rounded-md px-3 py-2 text-sm col-span-2" />
            <input placeholder="City" value={regForm.city}
              onChange={(e) => setRegForm({ ...regForm, city: e.target.value })}
              className="border border-slate-200 rounded-md px-3 py-2 text-sm" />
            <input placeholder="Country" value={regForm.country}
              onChange={(e) => setRegForm({ ...regForm, country: e.target.value })}
              className="border border-slate-200 rounded-md px-3 py-2 text-sm" />
            <input placeholder="Latitude" value={regForm.lat} type="number" step="any"
              onChange={(e) => setRegForm({ ...regForm, lat: e.target.value })}
              className="border border-slate-200 rounded-md px-3 py-2 text-sm" />
            <input placeholder="Longitude" value={regForm.lng} type="number" step="any"
              onChange={(e) => setRegForm({ ...regForm, lng: e.target.value })}
              className="border border-slate-200 rounded-md px-3 py-2 text-sm" />
          </div>
          <p className="text-xs text-slate-muted mt-1">Starting bed capacity (all beds start available)</p>
          <div className="grid grid-cols-3 gap-3">
            <label className="text-xs text-slate-muted">Emergency
              <input type="number" min="0" value={regForm.er_total}
                onChange={(e) => setRegForm({ ...regForm, er_total: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-slate-muted">ICU
              <input type="number" min="0" value={regForm.icu_total}
                onChange={(e) => setRegForm({ ...regForm, icu_total: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm" />
            </label>
            <label className="text-xs text-slate-muted">General
              <input type="number" min="0" value={regForm.general_total}
                onChange={(e) => setRegForm({ ...regForm, general_total: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm" />
            </label>
          </div>
          {regError && <p className="text-coral text-xs">{regError}</p>}
          <button className="self-start px-4 py-2 rounded-md bg-teal text-white text-sm font-medium">
            Add hospital to network
          </button>
        </form>
      )}

      {error && <p className="text-coral text-sm">{error}</p>}

      <div className="bg-white rounded-xl border border-slate-200 p-6 flex flex-col gap-6">
        {Object.entries(hospital.departments).map(([dept, data]) => (
          <div key={dept} className="flex items-center gap-4">
            <div className="flex-1">
              <CapacityBar label={dept} available={data.available} total={data.total} />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => tap(dept, -1)}
                disabled={data.available <= 0}
                className="w-9 h-9 rounded-md bg-slate-bg border border-slate-200 text-navy font-semibold disabled:opacity-40"
              >
                −
              </button>
              <button
                onClick={() => tap(dept, 1)}
                disabled={data.available >= data.total}
                className="w-9 h-9 rounded-md bg-teal text-white font-semibold disabled:opacity-40"
              >
                +
              </button>
            </div>
          </div>
        ))}
        <p className="text-xs text-slate-muted font-mono-data">
          Last updated {new Date(hospital.last_updated).toLocaleString()}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-semibold text-navy mb-3">Doctors on site</h2>
        {(!hospital.doctors || hospital.doctors.length === 0) ? (
          <p className="text-sm text-slate-muted">No doctors registered yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {hospital.doctors.map((d, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-navy">{d.name} <span className="text-slate-muted">· {d.specialty}</span></span>
                {d.on_call && (
                  <span className="text-[10px] uppercase tracking-wide bg-mint/40 text-teal-dark px-2 py-0.5 rounded">
                    On call
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-semibold text-navy mb-1">Emergency notifications</h2>
        <p className="text-xs text-slate-muted mb-3">
          Codes shared with the on-call doctor so they know who to expect.
        </p>
        {(!hospital.notifications || hospital.notifications.length === 0) ? (
          <p className="text-sm text-slate-muted">No notifications yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {hospital.notifications.slice(0, 8).map((n) => (
              <li key={n.code} className="border border-slate-200 rounded-md px-3 py-2">
                <div className="flex justify-between items-center">
                  <span className="font-mono-data text-xs text-navy">{n.code}</span>
                  <span className="text-[10px] uppercase tracking-wide bg-slate-bg px-2 py-0.5 rounded text-slate-muted">
                    {n.source}
                  </span>
                </div>
                <p className="text-sm text-navy mt-1">{n.severity}{n.condition_notes ? ` — ${n.condition_notes}` : ''}</p>
                <p className="text-xs text-slate-muted">Notified: {n.notified_doctor}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-semibold text-navy mb-3">Booked beds</h2>
        {bookings.length === 0 ? (
          <p className="text-sm text-slate-muted">No bookings yet for this hospital.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-muted uppercase tracking-wide">
                <th className="pb-2">Code</th>
                <th className="pb-2">Type</th>
                <th className="pb-2">Reason</th>
                <th className="pb-2">Age / Sex</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.id} className="border-t border-slate-100">
                  <td className="py-2 font-mono-data text-xs">{b.code}</td>
                  <td className="py-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${b.booking_type === 'emergency' ? 'bg-coral/10 text-coral' : 'bg-mint/30 text-teal-dark'}`}>
                      {b.booking_type}
                    </span>
                  </td>
                  <td className="py-2 text-slate-muted">{b.condition_notes}</td>
                  <td className="py-2 text-slate-muted">{b.age_group} / {b.sex}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-display font-semibold text-navy mb-3">Aggregate demographics on file</h2>
        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <p className="text-slate-muted mb-1">By age group</p>
            {Object.entries(demo.age_groups).map(([k, v]) => (
              <div key={k} className="flex justify-between font-mono-data text-xs py-0.5">
                <span>{k}</span><span>{v}</span>
              </div>
            ))}
          </div>
          <div>
            <p className="text-slate-muted mb-1">By sex</p>
            {Object.entries(demo.sex).map(([k, v]) => (
              <div key={k} className="flex justify-between font-mono-data text-xs py-0.5">
                <span>{k}</span><span>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
