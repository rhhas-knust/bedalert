import { useMemo, useState } from 'react'
import { qs, request } from '../shared/api.js'
import { usePoll } from '../shared/hooks.js'
import MapView from '../shared/MapView.jsx'
import StaffGate from '../shared/StaffGate.jsx'
import {
  AppShell, Badge, Button, Card, Choice, Countdown, Empty, Field, Freshness, inputCls, Notice, SectionTitle,
  SEVERITY_TONE, Spinner, STATUS_LABEL, STATUS_TONE, timeAgo, useNow, WARD_LABEL,
} from '../shared/ui.jsx'

const SEVERITIES = [
  { value: 'critical', label: 'Critical', activeCls: 'bg-coral text-white border-coral' },
  { value: 'severe', label: 'Severe', activeCls: 'bg-amber text-navy border-amber' },
  { value: 'moderate', label: 'Moderate', activeCls: 'bg-navy text-white border-navy' },
]
const DISPATCH_WARDS = ['ER', 'ICU', 'maternity', 'paediatric', 'general']

export default function DispatchApp() {
  return (
    <StaffGate app="Dispatch console" kind="dispatch">
      {(ctx) => <Console {...ctx} />}
    </StaffGate>
  )
}

function Console({ me, api, signOutButton }) {
  const right = (
    <>
      {me.agencies[0] && <span className="hidden lg:inline text-slate-300">{me.agencies[0].name}</span>}
      {signOutButton}
    </>
  )
  if (!me.agencies.length)
    return (
      <AppShell app="Dispatch console" right={right}>
        <Notice tone="warn">Your account is not linked to an ambulance agency yet. Ask the BedAlert team to add <b>{me.email}</b> as a dispatcher.</Notice>
      </AppShell>
    )
  return (
    <AppShell app="Dispatch console" right={right} wide>
      <Workspace api={api} />
    </AppShell>
  )
}

function Workspace({ api }) {
  const [incident, setIncident] = useState(null)
  const [severity, setSeverity] = useState('severe')
  const [ward, setWard] = useState('ER')
  const [category, setCategory] = useState('')
  const [note, setNote] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [options, setOptions] = useState(null)
  const [busy, setBusy] = useState(null)
  const [err, setErr] = useState(null)
  const [tracking, setTracking] = useState(null)
  const [fit, setFit] = useState(1)

  const effectiveWard = severity === 'critical' ? 'ER' : ward
  const meta = usePoll(() => request('/meta'), 0, [])
  const facilities = usePoll(() => request('/facilities' + qs({ ward: effectiveWard })), 30000, [effectiveWard])
  const board = usePoll(() => api('/dispatch/holds?status=all'), 6000, [])
  useNow(30000)

  const labels = useMemo(() => Object.fromEntries((meta.data?.condition_categories || []).map((c) => [c.id, c.label])), [meta.data])
  const cats = (meta.data?.condition_categories || []).filter((c) => c.id !== 'referral')

  // Follow a hold through any re-routes to where the ambulance should go now.
  const current = useMemo(() => {
    if (!tracking) return null
    const all = board.data || []
    let h = all.find((x) => x.id === tracking.id) || tracking
    for (let i = 0; i < 10; i++) {
      const next = all.find((x) => x.previous_hold_id === h.id)
      if (!next) break
      h = next
    }
    return h
  }, [tracking, board.data])

  const rank = Object.fromEntries((options || []).map((o, i) => [o.hospital_id, i + 1]))
  const markers = useMemo(
    () =>
      (facilities.data || []).map((f) => {
        const w = f.wards[0]
        const chosen = current && current.hospital_id === f.id
        const cls = chosen ? 'ba-pin-chosen' : !w.fresh ? 'ba-pin-stale' : w.available === 0 ? 'ba-pin-full' : w.available <= 2 ? 'ba-pin-low' : 'ba-pin-free'
        return {
          id: f.id,
          lat: f.lat,
          lng: f.lng,
          cls,
          html: rank[f.id] ? `#${rank[f.id]}` : String(w.available),
          title: `${f.name}: ${w.available} ${WARD_LABEL[effectiveWard]} free${w.fresh ? '' : ' (not confirmed recently)'}`,
        }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [facilities.data, options, current, effectiveWard],
  )
  // Zoom: everything → patient + best options → patient + chosen hospital.
  const [fitPoints, fitKey] = useMemo(() => {
    const inc = incident ? [[incident.lat, incident.lng]] : []
    if (incident && current && current.hospital_lat !== undefined)
      return [[...inc, [current.hospital_lat, current.hospital_lng]], `held-${current.id}`]
    if (incident && options && options.length)
      return [
        [...inc, ...options.filter((o, i) => i === 0 || o.distance_km <= Math.max(25, options[0].distance_km * 2)).slice(0, 3).map((o) => [o.lat, o.lng])],
        `options-${fit}`,
      ]
    if (incident) return [inc, `incident-${incident.lat}-${incident.lng}`]
    const all = (facilities.data || []).map((f) => [f.lat, f.lng])
    return [all, all.length ? `all-${effectiveWard}` : null]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incident, current?.id, current?.hospital_lat, options, fit, facilities.data, effectiveWard])
  const line = incident && current && current.hospital_lat !== undefined && (current.status === 'held' || current.status === 'accepted')
    ? [[incident.lat, incident.lng], [current.hospital_lat, current.hospital_lng]]
    : null

  const find = async () => {
    setBusy('find')
    setErr(null)
    try {
      setOptions(await api('/dispatch/options' + qs({ lat: incident.lat, lng: incident.lng, severity, ward })))
      setFit((x) => x + 1)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(null)
    }
  }

  const hold = async (hospitalId) => {
    setBusy(hospitalId || 'best')
    setErr(null)
    try {
      const h = await api('/dispatch/holds', {
        method: 'POST',
        body: {
          lat: incident.lat, lng: incident.lng, severity, ward, condition_category: category,
          condition_note: note.trim() || null, age_group: age || null, sex: sex || null, hospital_id: hospitalId || null,
        },
      })
      setTracking(h)
      setOptions(null)
      board.reload()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(null)
    }
  }

  const reset = () => {
    setIncident(null)
    setOptions(null)
    setTracking(null)
    setCategory('')
    setNote('')
    setAge('')
    setSex('')
  }

  const useMyLocation = () =>
    navigator.geolocation?.getCurrentPosition((p) => {
      setIncident({ lat: p.coords.latitude, lng: p.coords.longitude })
      setOptions(null)
    })

  return (
    <div className="grid gap-5 lg:grid-cols-[400px_1fr]">
      <div className="space-y-4">
        {!current ? (
          <Card className="p-4">
            <SectionTitle>New emergency</SectionTitle>
            <div className="space-y-4">
              <div>
                <span className="block text-sm font-semibold mb-1">1 · Patient location</span>
                {incident ? (
                  <div className="text-sm flex items-center justify-between bg-slate-bg rounded-xl px-3 py-2">
                    <span className="font-mono-data">{incident.lat.toFixed(4)}, {incident.lng.toFixed(4)}</span>
                    <button className="text-teal font-semibold" onClick={() => { setIncident(null); setOptions(null) }}>Change</button>
                  </div>
                ) : (
                  <div className="text-sm text-slate-muted">
                    Click the map where the patient is, or <button className="text-teal font-semibold underline" onClick={useMyLocation}>use this device’s location</button>.
                  </div>
                )}
              </div>
              <div>
                <span className="block text-sm font-semibold mb-1">2 · Severity</span>
                <Choice value={severity} onChange={(v) => { setSeverity(v); setOptions(null) }} options={SEVERITIES} />
              </div>
              <div>
                <span className="block text-sm font-semibold mb-1">3 · Ward needed</span>
                {severity === 'critical' ? (
                  <p className="text-sm text-slate-muted bg-slate-bg rounded-xl px-3 py-2">Critical patients always go to <b>Emergency</b>.</p>
                ) : (
                  <select className={inputCls} value={ward} onChange={(e) => { setWard(e.target.value); setOptions(null) }}>
                    {DISPATCH_WARDS.map((w) => <option key={w} value={w}>{WARD_LABEL[w]}</option>)}
                  </select>
                )}
              </div>
              <div>
                <span className="block text-sm font-semibold mb-1">4 · Main problem</span>
                <select className={inputCls} value={category} onChange={(e) => setCategory(e.target.value)}>
                  <option value="">Choose…</option>
                  {cats.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Field label="Age">
                  <select className={inputCls} value={age} onChange={(e) => setAge(e.target.value)}>
                    <option value="">Unknown</option>
                    {['0-17', '18-39', '40-64', '65+'].map((a) => <option key={a}>{a}</option>)}
                  </select>
                </Field>
                <Field label="Sex">
                  <select className={inputCls} value={sex} onChange={(e) => setSex(e.target.value)}>
                    <option value="">Unknown</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                  </select>
                </Field>
              </div>
              <Field label="Note for the hospital (optional)" hint="No names. e.g. conscious, heavy bleeding left leg">
                <textarea className={inputCls} rows={2} maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
              {err && <Notice tone="error">{err}</Notice>}
              <Button className="w-full" size="lg" busy={busy === 'find'} disabled={!incident || !category} onClick={find}>
                Find beds
              </Button>
            </div>
          </Card>
        ) : (
          <Tracking hold={current} labels={labels} api={api} onDone={reset} onChanged={board.reload} />
        )}

        {options && !current && (
          <Card className="p-4">
            <SectionTitle right={options.length > 0 && <Button variant="mint" size="sm" busy={busy === 'best'} onClick={() => hold(null)}>Hold best bed</Button>}>
              Best hospitals now
            </SectionTitle>
            {options.length === 0 && <Notice tone="error">No hospital has a free {WARD_LABEL[effectiveWard]} bed right now. Call the nearest hospitals directly.</Notice>}
            <ol className="space-y-2">
              {options.map((o, i) => (
                <li key={o.hospital_id} className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-start gap-3">
                    <span className="font-display font-bold text-lg text-teal w-7">#{i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-navy leading-snug">{o.hospital_name}</div>
                      <div className="text-xs text-slate-muted">{o.distance_km} km · ETA ~{o.eta_minutes} min · <b className="text-slate-text">{o.available} free</b></div>
                      <Freshness minutes={o.updated_minutes_ago} fresh={o.fresh} />
                    </div>
                    <Button size="sm" variant={i === 0 ? 'mint' : 'secondary'} busy={busy === o.hospital_id} onClick={() => hold(o.hospital_id)}>Hold</Button>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        )}
      </div>

      <div className="space-y-5 min-w-0">
        <MapView
          className="h-[460px] lg:h-[520px] z-0"
          center={[6.69, -1.62]}
          zoom={12}
          markers={markers}
          incident={incident}
          line={line}
          fitKey={fitKey}
          fitPoints={fitPoints}
          onMapClick={current ? null : (p) => { setIncident(p); setOptions(null) }}
        />
        <div className="flex flex-wrap gap-3 text-xs text-slate-muted">
          <span className="flex items-center gap-1"><i className="ba-dot bg-mint-dark" /> 3+ free</span>
          <span className="flex items-center gap-1"><i className="ba-dot bg-amber" /> 1–2 free</span>
          <span className="flex items-center gap-1"><i className="ba-dot bg-coral" /> Full</span>
          <span className="flex items-center gap-1"><i className="ba-dot bg-slate-400" /> Not confirmed recently</span>
        </div>
        <Board board={board} labels={labels} onTrack={(h) => setTracking(h)} />
      </div>
    </div>
  )
}

function Tracking({ hold, labels, api, onDone, onChanged }) {
  const [busy, setBusy] = useState(false)
  const active = hold.status === 'held' || hold.status === 'accepted'
  const cancel = async () => {
    if (!window.confirm('Cancel this bed hold?')) return
    setBusy(true)
    try {
      await api(`/dispatch/holds/${hold.id}/cancel`, { method: 'POST' })
      onChanged()
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card className={`p-5 border-2 ${hold.status === 'accepted' ? 'border-mint-dark' : hold.status === 'held' ? 'border-amber' : 'border-slate-200'}`}>
      <div className="flex items-center justify-between">
        <Badge tone={STATUS_TONE[hold.status]}>{hold.status === 'held' ? 'Waiting for hospital to accept' : STATUS_LABEL[hold.status]}</Badge>
        <span className="font-mono-data font-bold text-2xl text-navy">{hold.code}</span>
      </div>
      {hold.previous_hold_id && <Notice tone="warn" className="mt-3">↪ Re-routed: the first hospital declined, so BedAlert held this bed instead.</Notice>}
      <div className="mt-3 text-sm text-slate-muted">Send the ambulance to</div>
      <div className="font-display font-bold text-2xl text-navy leading-tight">{hold.hospital_name}</div>
      <div className="text-sm mt-1">{WARD_LABEL[hold.ward]} · {labels[hold.condition_category] || hold.condition_category} · ETA ~{hold.eta_minutes} min</div>
      {active && <div className="mt-2 text-sm">Bed held for <Countdown until={hold.expires_at} /></div>}
      {hold.hospital_phone && <a className="block mt-2 text-teal font-semibold text-sm" href={`tel:${hold.hospital_phone}`}>📞 {hold.hospital_phone}</a>}
      <div className="mt-4 flex gap-2">
        <Button variant="secondary" onClick={onDone}>New emergency</Button>
        {active && <Button variant="ghost" busy={busy} onClick={cancel}>Cancel hold</Button>}
      </div>
    </Card>
  )
}

function Board({ board, labels, onTrack }) {
  const rows = (board.data || []).slice(0, 12)
  return (
    <Card className="p-4">
      <SectionTitle right={<span className="text-xs text-slate-muted">Your agency · live</span>}>Ambulances in progress</SectionTitle>
      {!board.data ? <Spinner /> : rows.length === 0 ? <Empty>No holds yet today.</Empty> : (
        <ul className="divide-y divide-slate-100">
          {rows.map((h) => (
            <li key={h.id}>
              <button className="w-full text-left py-2.5 flex items-center gap-3 hover:bg-slate-bg rounded-lg px-2" onClick={() => onTrack(h)}>
                <span className="font-mono-data font-bold text-navy w-20">{h.code}</span>
                <span className="flex-1 min-w-0">
                  <span className="block font-semibold text-sm text-navy truncate">{h.previous_hold_id ? '↪ ' : ''}{h.hospital_name}</span>
                  <span className="block text-xs text-slate-muted">
                    <Badge tone={SEVERITY_TONE[h.severity]}>{h.severity}</Badge> {labels[h.condition_category] || h.condition_category} · {timeAgo(h.created_at)}
                    {h.decline_reason && <> · declined: {h.decline_reason}</>}
                  </span>
                </span>
                <Badge tone={STATUS_TONE[h.status]}>{STATUS_LABEL[h.status]}</Badge>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
