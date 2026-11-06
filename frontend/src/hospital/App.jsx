import { useEffect, useMemo, useRef, useState } from 'react'
import { request } from '../shared/api.js'
import { useLocalState, usePoll } from '../shared/hooks.js'
import StaffGate from '../shared/StaffGate.jsx'
import {
  AppShell, Badge, Button, CapacityBar, Card, Countdown, Empty, Field, Freshness, inputCls, Notice, SectionTitle,
  SEVERITY_TONE, SOURCE_LABEL, Spinner, STATUS_LABEL, STATUS_TONE, timeAgo, useNow, WARD_LABEL,
} from '../shared/ui.jsx'

export const GHANA_REGIONS = [
  'Ahafo', 'Ashanti', 'Bono', 'Bono East', 'Central', 'Eastern', 'Greater Accra', 'North East', 'Northern', 'Oti',
  'Savannah', 'Upper East', 'Upper West', 'Volta', 'Western', 'Western North',
]
const WARDS = ['ER', 'ICU', 'general', 'maternity', 'paediatric']

export default function HospitalApp() {
  return (
    <StaffGate app="Hospital portal" kind="hospital">
      {(ctx) => <Portal {...ctx} />}
    </StaffGate>
  )
}

function Portal({ me, api, reloadMe, signOutButton }) {
  const [picked, setPicked] = useLocalState('bedalert.hospital', null)
  const hospitals = me.hospitals
  const current = hospitals.find((h) => h.id === picked) || hospitals[0]

  const right = (
    <>
      {hospitals.length > 1 && (
        <select className="rounded-lg bg-navy-light text-white text-sm px-2 py-1.5 max-w-[14rem]" value={current?.id} onChange={(e) => setPicked(e.target.value)} aria-label="Hospital">
          {hospitals.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
      )}
      {signOutButton}
    </>
  )

  return (
    <AppShell app="Hospital portal" right={right} wide>
      {current ? <Dashboard key={current.id} hospitalId={current.id} api={api} /> : <Apply api={api} onDone={reloadMe} />}
    </AppShell>
  )
}

// ---------------------------------------------------------------- dashboard

function Dashboard({ hospitalId, api }) {
  const [tab, setTab] = useState('live')
  const info = usePoll(() => api(`/hospital/${hospitalId}`), 15000, [hospitalId])
  const meta = usePoll(() => request('/meta'), 0, [])
  const labels = useMemo(() => Object.fromEntries((meta.data?.condition_categories || []).map((c) => [c.id, c.label])), [meta.data])

  if (info.error && !info.data) return <Notice tone="error">{info.error.message}</Notice>
  if (!info.data) return <div className="flex justify-center py-20 text-teal"><Spinner /></div>
  const h = info.data
  const admin = h.your_role === 'hospital_admin' || h.your_role === 'network_admin'
  const tabs = [['live', 'Live'], ['history', 'History'], ...(admin ? [['oncall', 'On-call'], ['team', 'Team'], ['keys', 'API keys']] : [])]

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display font-bold text-2xl sm:text-3xl text-navy">{h.name}</h1>
          <div className="text-sm text-slate-muted">{h.city}, {h.region} · signed in as {admin ? 'hospital admin' : 'hospital staff'}</div>
        </div>
        <nav className="flex gap-1 bg-white rounded-xl border border-slate-200 p-1">
          {tabs.map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-sm font-semibold ${tab === k ? 'bg-navy text-white' : 'text-navy hover:bg-slate-100'}`}>
              {l}
            </button>
          ))}
        </nav>
      </div>
      {h.status === 'pending' && (
        <Notice tone="warn" className="mt-4">
          <b>Waiting for verification.</b> BedAlert is checking your HeFRA licence ({h.license_number}). Until then your hospital is hidden from the public and cannot receive patients. You can already set up your wards and team.
        </Notice>
      )}
      {h.status === 'suspended' && <Notice tone="error" className="mt-4">This hospital is suspended from the BedAlert network. Contact the BedAlert team.</Notice>}

      <div className="mt-5">
        {tab === 'live' && <Live hospital={h} api={api} labels={labels} reloadInfo={info.reload} admin={admin} />}
        {tab === 'history' && <History hospitalId={hospitalId} api={api} labels={labels} />}
        {tab === 'oncall' && <OnCall hospital={h} api={api} reload={info.reload} />}
        {tab === 'team' && <Team hospitalId={hospitalId} api={api} />}
        {tab === 'keys' && <ApiKeys hospital={h} api={api} />}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- live: incoming + wards

function Live({ hospital, api, labels, reloadInfo, admin }) {
  const holds = usePoll(() => api(`/hospital/${hospital.id}/holds?status=active`), 8000, [hospital.id])
  const seen = useRef(null)
  const [fresh, setFresh] = useState(new Set())

  useEffect(() => {
    if (!holds.data) return
    const ids = holds.data.map((x) => x.id)
    if (seen.current) {
      const newOnes = ids.filter((id) => !seen.current.has(id))
      if (newOnes.length) setFresh((s) => new Set([...s, ...newOnes]))
    }
    seen.current = new Set(ids)
    const waiting = holds.data.filter((x) => x.status === 'held').length
    document.title = waiting ? `(${waiting}) Incoming patient · BedAlert` : 'Hospital portal · BedAlert'
  }, [holds.data])

  const afterAction = () => {
    holds.reload()
    reloadInfo()
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
      <section>
        <SectionTitle right={<span className="text-xs text-slate-muted">Refreshes automatically</span>}>Incoming patients</SectionTitle>
        {holds.error && <Notice tone="error">{holds.error.message}</Notice>}
        {holds.data && holds.data.length === 0 && (
          <Card className="p-2"><Empty>No patients on the way right now.</Empty></Card>
        )}
        <div className="space-y-3">
          {(holds.data || []).map((x) => (
            <HoldCard key={x.id} hold={x} hospitalId={hospital.id} api={api} labels={labels} isNew={fresh.has(x.id)} onDone={afterAction} />
          ))}
        </div>
      </section>
      <section>
        <SectionTitle>Beds</SectionTitle>
        <div className="space-y-3">
          {hospital.wards.map((w) => (
            <WardCard key={w.kind} ward={w} hospitalId={hospital.id} api={api} admin={admin} onDone={reloadInfo} />
          ))}
          {admin && <AddWard hospital={hospital} api={api} onDone={reloadInfo} />}
        </div>
        <Card className="p-4 mt-5">
          <div className="font-semibold text-navy text-sm">On call today</div>
          {hospital.on_call.filter((c) => c.on_call).length === 0 ? (
            <p className="text-sm text-amber-700 mt-1">Nobody is set to receive patient alerts by SMS.{admin ? ' Add someone in the On-call tab.' : ''}</p>
          ) : (
            <ul className="mt-1 text-sm text-slate-text">
              {hospital.on_call.filter((c) => c.on_call).map((c) => <li key={c.id}>{c.name} · {c.role} · <span className="font-mono-data">{c.phone}</span></li>)}
            </ul>
          )}
        </Card>
      </section>
    </div>
  )
}

function HoldCard({ hold, hospitalId, api, labels, isNew, onDone }) {
  const [busy, setBusy] = useState(null)
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')
  const [err, setErr] = useState(null)

  const act = async (action, body) => {
    setBusy(action)
    setErr(null)
    try {
      await api(`/hospital/${hospitalId}/holds/${hold.id}/${action}`, { method: 'POST', body: body || {} })
      onDone()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className={`p-4 ${hold.status === 'held' ? 'border-coral/60' : 'border-mint-dark'} ${isNew && hold.status === 'held' ? 'ring-4 ring-coral/30 animate-[pulse_2s_ease-in-out_3]' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEVERITY_TONE[hold.severity]}>{hold.severity.toUpperCase()}</Badge>
        <Badge tone={STATUS_TONE[hold.status]}>{STATUS_LABEL[hold.status]}</Badge>
        <span className="text-sm text-slate-muted">{SOURCE_LABEL[hold.source]}</span>
        <span className="ml-auto font-mono-data font-bold text-navy">{hold.code}</span>
      </div>
      <div className="mt-2 font-display font-bold text-lg text-navy">
        {labels[hold.condition_category] || hold.condition_category} · {WARD_LABEL[hold.ward]}
      </div>
      <div className="text-sm text-slate-text mt-1 flex flex-wrap gap-x-4 gap-y-1">
        {hold.eta_minutes && <span>ETA ~{hold.eta_minutes} min</span>}
        {hold.age_group && <span>Age {hold.age_group}</span>}
        {hold.sex && hold.sex !== 'unspecified' && <span className="capitalize">{hold.sex}</span>}
        <span>Alerted {timeAgo(hold.created_at)}</span>
        <span>Bed held for <Countdown until={hold.expires_at} /></span>
      </div>
      {hold.condition_note && <p className="mt-2 text-sm bg-slate-bg rounded-lg px-3 py-2">“{hold.condition_note}”</p>}
      {hold.citizen_phone && <p className="mt-2 text-sm">Family contact: <a className="font-mono-data text-teal font-semibold" href={`tel:${hold.citizen_phone}`}>{hold.citizen_phone}</a></p>}
      {err && <Notice tone="error" className="mt-2">{err}</Notice>}
      {!declining ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {hold.status === 'held' && <Button variant="mint" busy={busy === 'accept'} onClick={() => act('accept')}>✓ Accept</Button>}
          <Button variant="teal" busy={busy === 'arrive'} onClick={() => act('arrive')}>Patient arrived</Button>
          <Button variant="secondary" onClick={() => setDeclining(true)}>Decline</Button>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <input className={inputCls} placeholder="Reason (e.g. no oxygen, surgeon unavailable)" value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} />
          <p className="text-xs text-slate-muted">{hold.source === 'dispatcher' ? 'BedAlert will immediately hold a bed at the next hospital for this ambulance.' : 'The family will be told by SMS to choose another hospital.'}</p>
          <div className="flex gap-2">
            <Button variant="danger" busy={busy === 'decline'} onClick={() => act('decline', { reason: reason.trim() || null })}>Confirm decline</Button>
            <Button variant="ghost" onClick={() => setDeclining(false)}>Back</Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function WardCard({ ward, hospitalId, api, admin, onDone }) {
  const [busy, setBusy] = useState(null)
  const [edit, setEdit] = useState(false)
  const physicallyFree = ward.total - ward.occupied
  const [free, setFree] = useState(physicallyFree)
  const [total, setTotal] = useState(ward.total)
  const [err, setErr] = useState(null)

  const send = async (key, body) => {
    setBusy(key)
    setErr(null)
    try {
      await api(`/hospital/${hospitalId}/wards/${ward.kind}`, { method: 'PUT', body })
      setEdit(false)
      onDone()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-display font-bold text-lg text-navy">{WARD_LABEL[ward.kind]}</div>
          <Freshness minutes={ward.updated_minutes_ago} fresh={ward.fresh} />
        </div>
        <div className="text-right">
          <div className={`font-mono-data font-bold text-3xl leading-none ${ward.available ? 'text-teal' : 'text-coral'}`}>{ward.available}</div>
          <div className="text-xs text-slate-muted">bookable</div>
        </div>
      </div>
      <div className="mt-3"><CapacityBar available={ward.available} total={ward.total} /></div>
      <div className="mt-2 text-xs text-slate-muted">
        {physicallyFree} empty of {ward.total} · {ward.held} kept for incoming patients
      </div>
      {err && <Notice tone="error" className="mt-2">{err}</Notice>}
      {!edit ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button variant="mint" busy={busy === '+'} onClick={() => send('+', { free_delta: 1 })} disabled={physicallyFree >= ward.total}>+1 bed freed</Button>
          <Button variant="secondary" busy={busy === '-'} onClick={() => send('-', { free_delta: -1 })} disabled={physicallyFree <= 0}>−1 bed taken</Button>
          <Button variant="ghost" size="sm" busy={busy === 'ok'} onClick={() => send('ok', { free: physicallyFree })}>✓ Numbers still correct</Button>
          <Button variant="ghost" size="sm" onClick={() => { setFree(physicallyFree); setTotal(ward.total); setEdit(true) }}>Edit…</Button>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <Field label="Empty beds now">
              <input className={inputCls} type="number" min={0} value={free} onChange={(e) => setFree(e.target.value)} />
            </Field>
            {admin && (
              <Field label="Total beds">
                <input className={inputCls} type="number" min={0} value={total} onChange={(e) => setTotal(e.target.value)} />
              </Field>
            )}
          </div>
          <div className="flex gap-2">
            <Button busy={busy === 'save'} onClick={() => send('save', { free: Number(free), ...(admin && Number(total) !== ward.total ? { total: Number(total) } : {}) })}>Save</Button>
            <Button variant="ghost" onClick={() => setEdit(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function AddWard({ hospital, api, onDone }) {
  const missing = WARDS.filter((k) => !hospital.wards.some((w) => w.kind === k))
  const [kind, setKind] = useState(missing[0])
  const [total, setTotal] = useState('')
  const [err, setErr] = useState(null)
  if (!missing.length) return null
  const add = async () => {
    setErr(null)
    try {
      await api(`/hospital/${hospital.id}/wards/${kind}`, { method: 'PUT', body: { total: Number(total) } })
      setTotal('')
      onDone()
    } catch (e) {
      setErr(e.message)
    }
  }
  return (
    <Card className="p-4">
      <div className="font-semibold text-navy text-sm">Add a ward</div>
      <div className="mt-2 flex gap-2">
        <select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value)}>
          {missing.map((k) => <option key={k} value={k}>{WARD_LABEL[k]}</option>)}
        </select>
        <input className={inputCls} type="number" min={1} placeholder="Beds" value={total} onChange={(e) => setTotal(e.target.value)} />
        <Button onClick={add} disabled={!total}>Add</Button>
      </div>
      {err && <Notice tone="error" className="mt-2">{err}</Notice>}
    </Card>
  )
}

// ---------------------------------------------------------------- history

function History({ hospitalId, api, labels }) {
  const holds = usePoll(() => api(`/hospital/${hospitalId}/holds?status=all`), 20000, [hospitalId])
  useNow(30000)
  if (!holds.data) return <div className="flex justify-center py-10 text-teal"><Spinner /></div>
  if (!holds.data.length) return <Empty>No patients yet.</Empty>
  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-slate-muted">
          <tr className="border-b border-slate-200">
            {['Code', 'When', 'From', 'Problem', 'Ward', 'Status', 'Note'].map((c) => <th key={c} className="px-4 py-2 font-semibold">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {holds.data.map((x) => (
            <tr key={x.id} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-2 font-mono-data font-bold">{x.code}</td>
              <td className="px-4 py-2 whitespace-nowrap">{timeAgo(x.created_at)}</td>
              <td className="px-4 py-2 whitespace-nowrap">{SOURCE_LABEL[x.source]}</td>
              <td className="px-4 py-2">{labels[x.condition_category] || x.condition_category}</td>
              <td className="px-4 py-2">{WARD_LABEL[x.ward]}</td>
              <td className="px-4 py-2"><Badge tone={STATUS_TONE[x.status]}>{STATUS_LABEL[x.status]}</Badge></td>
              <td className="px-4 py-2 text-slate-muted">{x.decline_reason || x.condition_note || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}

// ---------------------------------------------------------------- admin tabs

function OnCall({ hospital, api, reload }) {
  const [rows, setRows] = useState(hospital.on_call.map(({ name, role, phone, on_call }) => ({ name, role, phone, on_call })))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const upd = (i, k, v) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const save = async () => {
    setBusy(true)
    setMsg(null)
    try {
      await api(`/hospital/${hospital.id}/on-call`, { method: 'PUT', body: rows.filter((r) => r.name.trim() && r.phone.trim()) })
      setMsg({ tone: 'ok', text: 'Saved. These people get an SMS whenever a patient is on the way.' })
      reload()
    } catch (e) {
      setMsg({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card className="p-5 max-w-3xl">
      <SectionTitle>Who gets patient alerts by SMS</SectionTitle>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-[1.4fr_1fr_1.2fr_auto_auto] gap-2 items-center">
            <input className={inputCls} placeholder="Name" value={r.name} onChange={(e) => upd(i, 'name', e.target.value)} />
            <input className={inputCls} placeholder="Role" value={r.role} onChange={(e) => upd(i, 'role', e.target.value)} />
            <input className={inputCls} placeholder="Phone" value={r.phone} onChange={(e) => upd(i, 'phone', e.target.value)} />
            <label className="text-sm flex items-center gap-1"><input type="checkbox" checked={r.on_call} onChange={(e) => upd(i, 'on_call', e.target.checked)} /> On call</label>
            <Button variant="ghost" size="sm" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="Remove">✕</Button>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-3">
        <Button variant="secondary" onClick={() => setRows([...rows, { name: '', role: 'doctor', phone: '', on_call: true }])}>+ Add person</Button>
        <Button busy={busy} onClick={save}>Save</Button>
      </div>
      {msg && <Notice tone={msg.tone} className="mt-3">{msg.text}</Notice>}
    </Card>
  )
}

function Team({ hospitalId, api }) {
  const members = usePoll(() => api(`/hospital/${hospitalId}/members`), 0, [hospitalId])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('hospital_staff')
  const [msg, setMsg] = useState(null)
  const add = async (e) => {
    e.preventDefault()
    setMsg(null)
    try {
      await api(`/hospital/${hospitalId}/members`, { method: 'POST', body: { email: email.trim(), role } })
      setEmail('')
      setMsg({ tone: 'ok', text: 'Added.' })
      members.reload()
    } catch (x) {
      setMsg({ tone: 'error', text: x.message })
    }
  }
  return (
    <div className="grid gap-5 md:grid-cols-2 max-w-4xl">
      <Card className="p-5">
        <SectionTitle>Team</SectionTitle>
        {!members.data ? <Spinner /> : (
          <ul className="divide-y divide-slate-100">
            {members.data.map((m) => (
              <li key={m.user_id + m.role} className="py-2 flex justify-between text-sm">
                <span>{m.email}</span>
                <Badge tone={m.role === 'hospital_admin' ? 'navy' : 'slate'}>{m.role === 'hospital_admin' ? 'Admin' : 'Staff'}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card className="p-5">
        <SectionTitle>Add a colleague</SectionTitle>
        <form onSubmit={add} className="space-y-3">
          <Field label="Their work email" hint="They must create a BedAlert account and sign in once first.">
            <input className={inputCls} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Role">
            <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="hospital_staff">Staff: update beds, handle patients</option>
              <option value="hospital_admin">Admin: also team, on-call, API keys</option>
            </select>
          </Field>
          <Button type="submit">Add to team</Button>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </form>
      </Card>
    </div>
  )
}

function ApiKeys({ hospital, api }) {
  const keys = usePoll(() => api(`/hospital/${hospital.id}/api-keys`), 0, [hospital.id])
  const [label, setLabel] = useState('')
  const [created, setCreated] = useState(null)
  const [err, setErr] = useState(null)
  const create = async (e) => {
    e.preventDefault()
    setErr(null)
    try {
      setCreated(await api(`/hospital/${hospital.id}/api-keys`, { method: 'POST', body: { label: label.trim() } }))
      setLabel('')
      keys.reload()
    } catch (x) {
      setErr(x.message)
    }
  }
  const revoke = async (id) => {
    if (!window.confirm('Revoke this key? Systems using it stop working immediately.')) return
    await api(`/hospital/${hospital.id}/api-keys/${id}`, { method: 'DELETE' })
    keys.reload()
  }
  return (
    <div className="max-w-3xl space-y-5">
      <Card className="p-5">
        <SectionTitle>Connect your hospital system</SectionTitle>
        <p className="text-sm text-slate-muted">An API key lets your hospital information system send bed numbers and accept patients automatically. Give it to your IT team.</p>
        {hospital.status !== 'verified' ? (
          <Notice tone="warn" className="mt-3">API keys are available once BedAlert has verified your hospital.</Notice>
        ) : (
          <form onSubmit={create} className="mt-3 flex gap-2">
            <input className={inputCls} placeholder="Label, e.g. Lightwave HIS production" required value={label} onChange={(e) => setLabel(e.target.value)} />
            <Button type="submit">Create key</Button>
          </form>
        )}
        {err && <Notice tone="error" className="mt-3">{err}</Notice>}
        {created && (
          <Notice tone="ok" className="mt-3">
            <b>Copy this key now.</b> BedAlert does not store it and cannot show it again.
            <div className="mt-2 flex gap-2">
              <code className="flex-1 bg-white rounded-lg px-3 py-2 font-mono-data text-xs break-all border border-emerald-200">{created.key}</code>
              <Button size="sm" variant="secondary" onClick={() => navigator.clipboard?.writeText(created.key)}>Copy</Button>
            </div>
          </Notice>
        )}
      </Card>
      <Card className="p-5">
        <SectionTitle>Keys</SectionTitle>
        {!keys.data ? <Spinner /> : keys.data.length === 0 ? <Empty>No keys yet.</Empty> : (
          <ul className="divide-y divide-slate-100">
            {keys.data.map((k) => (
              <li key={k.id} className="py-2 flex items-center gap-3 text-sm">
                <div className="flex-1">
                  <div className="font-semibold">{k.label} <span className="font-mono-data text-slate-muted">ba_live_{k.prefix}_…</span></div>
                  <div className="text-xs text-slate-muted">{k.scopes.join(', ')} · {k.last_used_at ? `last used ${timeAgo(k.last_used_at)}` : 'never used'}</div>
                </div>
                {k.revoked_at ? <Badge>Revoked</Badge> : <Button size="sm" variant="secondary" onClick={() => revoke(k.id)}>Revoke</Button>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------- joining

function Apply({ api, onDone }) {
  const [f, setF] = useState({ name: '', region: 'Greater Accra', district: '', city: '', lat: '', lng: '', phone: '', license_number: '' })
  const [wards, setWards] = useState([{ kind: 'ER', total: '', occupied: '' }])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const locate = () =>
    navigator.geolocation?.getCurrentPosition((p) => setF((x) => ({ ...x, lat: p.coords.latitude.toFixed(5), lng: p.coords.longitude.toFixed(5) })))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api('/hospitals/apply', {
        method: 'POST',
        body: {
          ...f,
          lat: Number(f.lat),
          lng: Number(f.lng),
          phone: f.phone || null,
          wards: wards.filter((w) => w.total !== '').map((w) => ({ kind: w.kind, total: Number(w.total), occupied: Number(w.occupied || 0) })),
        },
      })
      await onDone()
    } catch (x) {
      setErr(x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-display font-bold text-2xl text-navy">Bring your hospital onto BedAlert</h1>
      <p className="text-sm text-slate-muted mt-1">
        If your hospital is already on BedAlert, ask its admin to add your email to the team instead. New hospitals are checked by the BedAlert team before they go live.
      </p>
      <Card className="p-5 mt-4">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Hospital name"><input className={inputCls} required value={f.name} onChange={set('name')} /></Field>
          <div className="grid sm:grid-cols-3 gap-3">
            <Field label="Region">
              <select className={inputCls} value={f.region} onChange={set('region')}>{GHANA_REGIONS.map((r) => <option key={r}>{r}</option>)}</select>
            </Field>
            <Field label="District"><input className={inputCls} required value={f.district} onChange={set('district')} /></Field>
            <Field label="Town / city"><input className={inputCls} required value={f.city} onChange={set('city')} /></Field>
          </div>
          <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
            <Field label="Latitude"><input className={inputCls} required inputMode="decimal" value={f.lat} onChange={set('lat')} /></Field>
            <Field label="Longitude"><input className={inputCls} required inputMode="decimal" value={f.lng} onChange={set('lng')} /></Field>
            <Button type="button" variant="secondary" onClick={locate}>📍 I’m at the hospital</Button>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Emergency phone line" hint="Shown to the public so they can call ahead."><input className={inputCls} type="tel" value={f.phone} onChange={set('phone')} /></Field>
            <Field label="HeFRA licence number"><input className={inputCls} required value={f.license_number} onChange={set('license_number')} /></Field>
          </div>
          <div>
            <span className="block text-sm font-semibold mb-1">Wards</span>
            {wards.map((w, i) => (
              <div key={i} className="grid grid-cols-[1.2fr_1fr_1fr_auto] gap-2 mb-2">
                <select className={inputCls} value={w.kind} onChange={(e) => setWards(wards.map((x, j) => (j === i ? { ...x, kind: e.target.value } : x)))}>
                  {WARDS.map((k) => <option key={k} value={k}>{WARD_LABEL[k]}</option>)}
                </select>
                <input className={inputCls} type="number" min={0} placeholder="Total beds" value={w.total} onChange={(e) => setWards(wards.map((x, j) => (j === i ? { ...x, total: e.target.value } : x)))} />
                <input className={inputCls} type="number" min={0} placeholder="In use now" value={w.occupied} onChange={(e) => setWards(wards.map((x, j) => (j === i ? { ...x, occupied: e.target.value } : x)))} />
                <Button type="button" variant="ghost" onClick={() => setWards(wards.filter((_, j) => j !== i))}>✕</Button>
              </div>
            ))}
            <Button type="button" variant="secondary" size="sm" onClick={() => setWards([...wards, { kind: 'general', total: '', occupied: '' }])}>+ Add ward</Button>
          </div>
          {err && <Notice tone="error">{err}</Notice>}
          <Button type="submit" busy={busy} size="lg">Submit for verification</Button>
        </form>
      </Card>
    </div>
  )
}
