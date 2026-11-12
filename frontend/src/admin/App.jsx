import { useState } from 'react'
import { usePoll } from '../shared/hooks.js'
import StaffGate from '../shared/StaffGate.jsx'
import { AppShell, Badge, Button, Card, Empty, Field, fmtMinutes, inputCls, Notice, SectionTitle, Spinner, timeAgo } from '../shared/ui.jsx'

export default function AdminApp() {
  return (
    <StaffGate app="Network admin" kind="admin">
      {(ctx) => (
        <AppShell app="Network admin" right={ctx.signOutButton} wide>
          {ctx.me.network_admin ? <Admin api={ctx.api} /> : <Notice tone="warn">This page is for the BedAlert team only.</Notice>}
        </AppShell>
      )}
    </StaffGate>
  )
}

function Admin({ api }) {
  const [tab, setTab] = useState('hospitals')
  const tabs = [['hospitals', 'Hospitals'], ['agencies', 'Ambulance agencies'], ['roles', 'Grant a role'], ['quality', 'Data freshness']]
  return (
    <div>
      <nav className="flex flex-wrap gap-1 bg-white rounded-xl border border-slate-200 p-1 w-fit">
        {tabs.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-sm font-semibold ${tab === k ? 'bg-navy text-white' : 'text-navy hover:bg-slate-100'}`}>{l}</button>
        ))}
      </nav>
      <div className="mt-5">
        {tab === 'hospitals' && <Hospitals api={api} />}
        {tab === 'agencies' && <Agencies api={api} />}
        {tab === 'roles' && <Roles api={api} />}
        {tab === 'quality' && <Quality api={api} />}
      </div>
    </div>
  )
}

function Hospitals({ api }) {
  const [status, setStatus] = useState('pending')
  const list = usePoll(() => api(`/admin/hospitals${status ? `?status=${status}` : ''}`), 0, [status])
  const act = async (id, action) => {
    if (action === 'suspend' && !window.confirm('Suspend this hospital? It disappears from the public and stops receiving patients.')) return
    await api(`/admin/hospitals/${id}/${action}`, { method: 'POST' })
    list.reload()
  }
  return (
    <Card className="p-5">
      <SectionTitle right={
        <select className={`${inputCls} !w-auto !py-1.5 text-sm`} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="pending">Waiting for verification</option>
          <option value="verified">Verified</option>
          <option value="suspended">Suspended</option>
          <option value="">All</option>
        </select>
      }>Hospitals</SectionTitle>
      {status === 'pending' && <Notice className="mb-3">Before verifying: check the HeFRA licence number and call the hospital on a number you found yourself, not the one they entered.</Notice>}
      {!list.data ? <Spinner /> : list.data.length === 0 ? <Empty>Nothing here.</Empty> : (
        <ul className="divide-y divide-slate-100">
          {list.data.map((h) => (
            <li key={h.id} className="py-3 flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-[16rem]">
                <div className="font-semibold text-navy">{h.name} <Badge tone={h.status === 'verified' ? 'mint' : h.status === 'pending' ? 'amber' : 'coral'}>{h.status}</Badge></div>
                <div className="text-xs text-slate-muted">{h.city}, {h.district}, {h.region} · licence <span className="font-mono-data">{h.license_number}</span> · {h.phone || 'no phone'} · applied {timeAgo(h.created_at)}</div>
              </div>
              {h.status !== 'verified' && <Button size="sm" variant="mint" onClick={() => act(h.id, 'verify')}>Verify</Button>}
              {h.status !== 'suspended' && <Button size="sm" variant="secondary" onClick={() => act(h.id, 'suspend')}>Suspend</Button>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function Agencies({ api }) {
  const list = usePoll(() => api('/admin/agencies'), 0, [])
  const [name, setName] = useState('')
  const [region, setRegion] = useState('')
  const add = async (e) => {
    e.preventDefault()
    await api('/admin/agencies', { method: 'POST', body: { name: name.trim(), region: region.trim() || null } })
    setName('')
    setRegion('')
    list.reload()
  }
  return (
    <div className="grid gap-5 md:grid-cols-2 max-w-4xl">
      <Card className="p-5">
        <SectionTitle>Agencies</SectionTitle>
        {!list.data ? <Spinner /> : list.data.length === 0 ? <Empty>None yet.</Empty> : (
          <ul className="divide-y divide-slate-100 text-sm">
            {list.data.map((a) => <li key={a.id} className="py-2"><b>{a.name}</b> <span className="text-slate-muted">{a.region}</span></li>)}
          </ul>
        )}
      </Card>
      <Card className="p-5">
        <SectionTitle>Add an agency</SectionTitle>
        <form onSubmit={add} className="space-y-3">
          <Field label="Name"><input className={inputCls} required placeholder="National Ambulance Service · Ashanti" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Region"><input className={inputCls} value={region} onChange={(e) => setRegion(e.target.value)} /></Field>
          <Button type="submit">Add agency</Button>
        </form>
      </Card>
    </div>
  )
}

function Roles({ api }) {
  const hospitals = usePoll(() => api('/admin/hospitals'), 0, [])
  const agencies = usePoll(() => api('/admin/agencies'), 0, [])
  const [f, setF] = useState({ email: '', role: 'dispatcher', hospital_id: '', agency_id: '' })
  const [msg, setMsg] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const grant = async (e) => {
    e.preventDefault()
    setMsg(null)
    try {
      await api('/admin/memberships', { method: 'POST', body: { ...f, email: f.email.trim(), hospital_id: f.hospital_id || null, agency_id: f.agency_id || null } })
      setMsg({ tone: 'ok', text: `Done. ${f.email} can now sign in with this role.` })
    } catch (x) {
      setMsg({ tone: 'error', text: x.message })
    }
  }
  return (
    <Card className="p-5 max-w-xl">
      <SectionTitle>Grant a role</SectionTitle>
      <form onSubmit={grant} className="space-y-3">
        <Field label="Email" hint="They must have signed in once so their account exists."><input className={inputCls} type="email" required value={f.email} onChange={set('email')} /></Field>
        <Field label="Role">
          <select className={inputCls} value={f.role} onChange={set('role')}>
            <option value="dispatcher">Dispatcher</option>
            <option value="hospital_staff">Hospital staff</option>
            <option value="hospital_admin">Hospital admin</option>
            <option value="network_admin">BedAlert network admin</option>
          </select>
        </Field>
        {f.role === 'dispatcher' && (
          <Field label="Agency">
            <select className={inputCls} required value={f.agency_id} onChange={set('agency_id')}>
              <option value="">Choose…</option>
              {(agencies.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </Field>
        )}
        {f.role.startsWith('hospital') && (
          <Field label="Hospital">
            <select className={inputCls} required value={f.hospital_id} onChange={set('hospital_id')}>
              <option value="">Choose…</option>
              {(hospitals.data || []).map((h) => <option key={h.id} value={h.id}>{h.name} ({h.status})</option>)}
            </select>
          </Field>
        )}
        <Button type="submit">Grant role</Button>
        {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      </form>
    </Card>
  )
}

function Quality({ api }) {
  const list = usePoll(() => api('/admin/data-quality'), 60000, [])
  return (
    <Card className="p-5 max-w-3xl">
      <SectionTitle>How fresh are the bed numbers?</SectionTitle>
      <p className="text-sm text-slate-muted mb-3">Oldest first. Call hospitals whose numbers are going stale.</p>
      {!list.data ? <Spinner /> : (
        <ul className="divide-y divide-slate-100 text-sm">
          {list.data.map((h) => (
            <li key={h.id} className="py-2 flex items-center gap-3">
              <span className="flex-1 font-semibold text-navy">{h.name}</span>
              <span className="font-mono-data text-slate-muted">{h.phone}</span>
              <Badge tone={h.minutes_since_last_update > 60 ? 'coral' : 'mint'}>{fmtMinutes(h.minutes_since_last_update)} ago</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
