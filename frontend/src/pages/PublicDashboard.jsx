import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import HospitalCard from '../components/HospitalCard.jsx'

const emptyForm = { age_group: '18-39', sex: 'female', condition_notes: '', booking_type: 'stable' }

export default function PublicDashboard() {
  const [hospitals, setHospitals] = useState([])
  const [query, setQuery] = useState('')
  const [booking, setBooking] = useState(null) // hospital being booked
  const [form, setForm] = useState(emptyForm)
  const [confirmation, setConfirmation] = useState(null)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')

  const load = () => api.getHospitals().then(setHospitals).catch((e) => setError(e.message))

  useEffect(() => { load() }, [])

  const filtered = hospitals.filter((h) =>
    `${h.name} ${h.city} ${h.country}`.toLowerCase().includes(query.toLowerCase())
  )

  function openBooking(hospital) {
    setForm(emptyForm)
    setFormError('')
    setBooking(hospital)
  }

  async function submitBooking(e) {
    e.preventDefault()
    if (!form.condition_notes.trim()) {
      setFormError('Please describe the problem — this field is required so the hospital knows what to expect.')
      return
    }
    try {
      const result = await api.createBooking({ hospital_id: booking.id, ...form })
      setConfirmation(result)
      setBooking(null)
      load()
    } catch (err) {
      setFormError(err.message)
    }
  }

  const availableForType = booking
    ? form.booking_type === 'emergency'
      ? booking.departments.ER.available
      : booking.departments.general.available
    : 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-navy">Find bed availability</h1>
        <p className="text-slate-muted text-sm mt-1">
          Book a stable-case bed, or report your own emergency if you can't call an ambulance.
        </p>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by hospital or city..."
        className="w-full max-w-md px-4 py-2 rounded-md border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-teal"
      />

      {error && <p className="text-coral text-sm">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((h) => (
          <HospitalCard key={h.id} hospital={h} onBook={openBooking} />
        ))}
      </div>

      {booking && (
        <div className="fixed inset-0 bg-navy/40 flex items-center justify-center p-4">
          <form
            onSubmit={submitBooking}
            className="bg-white rounded-xl p-6 w-full max-w-sm flex flex-col gap-4"
          >
            <h2 className="font-display font-semibold text-navy">Book at {booking.name}</h2>

            <div className="flex gap-2">
              {['stable', 'emergency'].map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setForm({ ...form, booking_type: type })}
                  className={`flex-1 py-2 rounded-md text-sm font-medium border ${
                    form.booking_type === type
                      ? type === 'emergency'
                        ? 'bg-coral text-white border-coral'
                        : 'bg-teal text-white border-teal'
                      : 'bg-white text-slate-muted border-slate-200'
                  }`}
                >
                  {type === 'stable' ? 'Stable case' : 'Emergency'}
                </button>
              ))}
            </div>
            {form.booking_type === 'emergency' && (
              <p className="text-xs text-coral bg-coral/10 border border-coral/30 rounded-md px-3 py-2">
                For life-threatening emergencies, call your local emergency number first. This books an
                Emergency dept. bed and notifies the hospital immediately.
              </p>
            )}
            <p className="text-xs text-slate-muted -mt-2">
              {availableForType} bed{availableForType === 1 ? '' : 's'} free in this department
            </p>

            <label className="text-sm text-slate-muted">
              Age group
              <select
                value={form.age_group}
                onChange={(e) => setForm({ ...form, age_group: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
              >
                <option>0-17</option>
                <option>18-39</option>
                <option>40-64</option>
                <option>65+</option>
              </select>
            </label>
            <label className="text-sm text-slate-muted">
              Sex
              <select
                value={form.sex}
                onChange={(e) => setForm({ ...form, sex: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
              >
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other_unspecified">Other / unspecified</option>
              </select>
            </label>
            <label className="text-sm text-slate-muted">
              What's the problem? <span className="text-coral">*required</span>
              <input
                value={form.condition_notes}
                onChange={(e) => setForm({ ...form, condition_notes: e.target.value })}
                placeholder="e.g. chest pain, broken arm, referral for surgery"
                required
                className="mt-1 w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
              />
            </label>

            {formError && <p className="text-coral text-xs">{formError}</p>}

            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setBooking(null)}
                className="px-4 py-2 text-sm text-slate-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`px-4 py-2 rounded-md text-white text-sm font-medium ${
                  form.booking_type === 'emergency' ? 'bg-coral' : 'bg-teal'
                }`}
              >
                Confirm {form.booking_type === 'emergency' ? 'emergency' : 'booking'}
              </button>
            </div>
          </form>
        </div>
      )}

      {confirmation && (
        <div className="fixed bottom-6 right-6 bg-white border border-mint-dark rounded-lg shadow-lg p-4 max-w-xs">
          <p className="text-sm font-medium text-navy">
            {confirmation.booking_type === 'emergency' ? 'Emergency booked' : 'Booking confirmed'}
          </p>
          <p className="text-xs text-slate-muted mt-1">
            {confirmation.hospital_name} · code {confirmation.code}
          </p>
          <button
            onClick={() => setConfirmation(null)}
            className="text-xs text-teal mt-2"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
