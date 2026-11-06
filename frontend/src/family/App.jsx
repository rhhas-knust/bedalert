import { useEffect, useMemo, useState } from 'react'
import { ApiError, qs, request } from '../shared/api.js'
import { useLocalState, usePoll } from '../shared/hooks.js'
import {
  AppShell, Badge, Button, CapacityBar, Card, Choice, Countdown, directionsUrl, Empty, Field, Freshness,
  inputCls, Notice, Spinner, STATUS_LABEL, STATUS_TONE, WARD_LABEL,
} from '../shared/ui.jsx'

const NEEDS = {
  emergency: { ward: 'ER', title: 'Emergency beds', icon: '🚨', label: 'Emergency', sub: 'Accident, chest pain, can’t breathe…' },
  maternity: { ward: 'maternity', title: 'Maternity beds', icon: '🤰', label: 'Labour / pregnancy', sub: 'Labour or pregnancy problems' },
  stable: { ward: 'general', title: 'Ward beds', icon: '🛏️', label: 'Not an emergency', sub: 'Referral, admission, check-up' },
}
const CATEGORIES = {
  emergency: ['chest_pain', 'road_accident', 'breathing_difficulty', 'stroke_signs', 'bleeding_injury', 'burns', 'poisoning', 'child_fever', 'other'],
  maternity: ['labour', 'bleeding_injury', 'other'],
  stable: ['referral', 'child_fever', 'other'],
}

export default function FamilyApp() {
  const [view, setView] = useState({ name: 'home' })
  const [citizen, setCitizen] = useLocalState('bedalert.citizen', null)
  const session = citizen && citizen.exp > Date.now() ? citizen : null
  const [meta, setMeta] = useState(null)

  useEffect(() => {
    request('/meta').then(setMeta).catch(() => {})
  }, [])

  const go = (name, extra = {}) => {
    setView({ name, ...extra })
    window.scrollTo(0, 0)
  }

  const right = session ? (
    <button className="text-mint font-semibold" onClick={() => go('mine')}>
      My bed holds
    </button>
  ) : null

  return (
    <AppShell app="Find a bed" right={right}>
      <a href="tel:112" className="block mb-4 rounded-2xl bg-coral text-white px-4 py-3 font-semibold text-center shadow-sm">
        Life-threatening emergency? <span className="underline">Call 112 now</span>
      </a>
      {view.name === 'home' && <Home onPick={(need) => go('list', { need })} />}
      {view.name === 'list' && <HospitalList need={view.need} onBack={() => go('home')} onHold={(f) => go('hold', { need: view.need, facility: f })} />}
      {view.name === 'hold' && (
        <HoldFlow
          need={view.need}
          facility={view.facility}
          meta={meta}
          session={session}
          setCitizen={setCitizen}
          onBack={() => go('list', { need: view.need })}
          onHeld={(hold) => go('held', { hold })}
          onMine={() => go('mine')}
        />
      )}
      {view.name === 'held' && (
        <Held hold={view.hold} session={session} setCitizen={setCitizen} meta={meta} onFindAnother={() => go('list', { need: 'emergency' })} />
      )}
      {view.name === 'mine' && <Mine session={session} setCitizen={setCitizen} meta={meta} onOpen={(hold) => go('held', { hold })} onHome={() => go('home')} />}
    </AppShell>
  )
}

// ---------------------------------------------------------------- home

function Home({ onPick }) {
  return (
    <div>
      <h1 className="font-display font-bold text-3xl sm:text-4xl text-navy leading-tight">Find a free hospital bed near you</h1>
      <p className="text-slate-muted mt-2">See which hospitals have space right now, and hold a bed before you set off.</p>
      <div className="grid gap-3 mt-5 sm:grid-cols-3">
        {Object.entries(NEEDS).map(([key, n]) => (
          <button
            key={key}
            onClick={() => onPick(key)}
            className={`text-left rounded-2xl p-5 border-2 transition shadow-sm ${
              key === 'emergency' ? 'bg-navy text-white border-navy hover:bg-navy-light' : 'bg-white border-slate-200 hover:border-teal'
            }`}
          >
            <div className="text-3xl">{n.icon}</div>
            <div className="font-display font-bold text-xl mt-2">{n.label}</div>
            <div className={`text-sm mt-1 ${key === 'emergency' ? 'text-slate-300' : 'text-slate-muted'}`}>{n.sub}</div>
          </button>
        ))}
      </div>
      <Card className="mt-6 p-5">
        <h2 className="font-display font-bold text-navy text-lg">How it works</h2>
        <ol className="mt-2 space-y-2 text-sm text-slate-text">
          <li><b>1.</b> Pick what you need and see hospitals with free beds, closest first.</li>
          <li><b>2.</b> Hold a bed with your phone number. You get a code by SMS.</li>
          <li><b>3.</b> Go straight there. The hospital is told you are coming.</li>
        </ol>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------- hospital list

function HospitalList({ need, onBack, onHold }) {
  const n = NEEDS[need]
  const [loc, setLoc] = useState(null)
  const [locState, setLocState] = useState('idle')
  const [region, setRegion] = useState('')
  const regions = usePoll(() => request('/regions'), 0, [])

  const locate = () => {
    if (!navigator.geolocation) return setLocState('unavailable')
    setLocState('asking')
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLoc({ lat: p.coords.latitude, lng: p.coords.longitude })
        setLocState('ok')
      },
      () => setLocState('denied'),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 120000 },
    )
  }
  useEffect(locate, [])

  const list = usePoll(
    () => request('/facilities' + qs({ ward: n.ward, lat: loc?.lat, lng: loc?.lng, region: loc ? undefined : region })),
    30000,
    [n.ward, loc?.lat, loc?.lng, region],
  )

  const sorted = useMemo(() => {
    const rows = (list.data || []).map((f) => ({ ...f, w: f.wards[0] }))
    return rows.sort(
      (a, b) =>
        (b.w.available > 0) - (a.w.available > 0) || b.w.fresh - a.w.fresh || (a.distance_km ?? 0) - (b.distance_km ?? 0) || b.w.available - a.w.available,
    )
  }, [list.data])

  return (
    <div>
      <button onClick={onBack} className="text-teal font-semibold text-sm">← Back</button>
      <h1 className="font-display font-bold text-2xl text-navy mt-1">{n.title} near you</h1>

      <Card className="p-3 mt-3 flex flex-wrap items-center gap-2">
        {locState === 'ok' ? (
          <span className="text-sm font-semibold text-teal">📍 Using your location</span>
        ) : (
          <>
            <Button variant="secondary" size="sm" onClick={locate} busy={locState === 'asking'}>
              📍 Use my location
            </Button>
            <span className="text-sm text-slate-muted">or</span>
            <select className={`${inputCls} !w-auto !py-1.5 text-sm`} value={region} onChange={(e) => setRegion(e.target.value)} aria-label="Region">
              <option value="">All regions</option>
              {(regions.data || []).map((r) => (
                <option key={r.region} value={r.region}>{r.region}</option>
              ))}
            </select>
            {locState === 'denied' && <span className="text-xs text-amber-700 w-full">Location is off. Pick your region instead.</span>}
          </>
        )}
      </Card>

      {list.error && <Notice tone="error" className="mt-3">{list.error.message}</Notice>}
      {list.loading && !list.data && (
        <div className="flex justify-center py-10 text-teal"><Spinner /></div>
      )}
      {list.data && sorted.length === 0 && <Empty>No hospitals on BedAlert here yet. Call 112 or your nearest hospital.</Empty>}

      <div className="mt-3 space-y-3">
        {sorted.map((f) => (
          <Card key={f.id} className={`p-4 ${f.w.available === 0 ? 'opacity-70' : ''}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-display font-bold text-lg text-navy leading-snug">{f.name}</div>
                <div className="text-sm text-slate-muted">
                  {f.city}, {f.region}
                  {f.distance_km !== undefined && <> · <b className="text-slate-text">{f.distance_km} km</b></>}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className={`font-mono-data font-bold text-3xl leading-none ${f.w.available ? 'text-teal' : 'text-coral'}`}>{f.w.available}</div>
                <div className="text-xs text-slate-muted">free</div>
              </div>
            </div>
            <div className="mt-3"><CapacityBar available={f.w.available} total={f.w.total} /></div>
            <div className="mt-1.5"><Freshness minutes={f.w.updated_minutes_ago} fresh={f.w.fresh} /></div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <Button variant="mint" size="sm" className="col-span-3 sm:col-span-1" disabled={!f.w.available} onClick={() => onHold(f)}>
                {f.w.available ? 'Hold a bed' : 'Full right now'}
              </Button>
              {f.phone && <a href={`tel:${f.phone}`} className="col-span-3 sm:col-span-1"><Button variant="secondary" size="sm" className="w-full">📞 Call</Button></a>}
              <a href={directionsUrl(f.lat, f.lng)} target="_blank" rel="noreferrer" className="col-span-3 sm:col-span-1">
                <Button variant="secondary" size="sm" className="w-full">🧭 Directions</Button>
              </a>
            </div>
          </Card>
        ))}
      </div>
      {sorted.length > 0 && (
        <p className="text-xs text-slate-muted mt-4">Bed numbers come from each hospital. If you can, call ahead while you travel.</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- holding a bed

function HoldFlow({ need, facility, meta, session, setCitizen, onBack, onHeld, onMine }) {
  const n = NEEDS[need]
  return (
    <div className="max-w-xl">
      <button onClick={onBack} className="text-teal font-semibold text-sm">← Back to hospitals</button>
      <h1 className="font-display font-bold text-2xl text-navy mt-1">Hold a bed at {facility.name}</h1>
      <p className="text-sm text-slate-muted">{WARD_LABEL[n.ward]} · {facility.wards[0].available} free</p>
      {!session ? (
        <PhoneVerify onVerified={setCitizen} />
      ) : (
        <HoldDetails need={need} facility={facility} meta={meta} session={session} setCitizen={setCitizen} onHeld={onHeld} onMine={onMine} />
      )}
    </div>
  )
}

function PhoneVerify({ onVerified }) {
  const [phone, setPhone] = useState('')
  const [sent, setSent] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const send = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      setSent(await request('/auth/otp/request', { method: 'POST', body: { phone } }))
    } catch (x) {
      setErr(x.message)
    } finally {
      setBusy(false)
    }
  }
  const verify = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const r = await request('/auth/otp/verify', { method: 'POST', body: { phone: sent.phone, code } })
      onVerified({ token: r.access_token, phone: r.phone, exp: Date.now() + (r.expires_in - 60) * 1000 })
    } catch (x) {
      setErr(x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5 mt-4">
      <h2 className="font-display font-bold text-lg text-navy">Step 1 · Your phone number</h2>
      <p className="text-sm text-slate-muted mt-1">We text you a code to check it’s you. Your bed code is sent to this number too.</p>
      {!sent ? (
        <form onSubmit={send} className="mt-4 space-y-3">
          <Field label="Phone number">
            <input className={inputCls} type="tel" inputMode="tel" required placeholder="024 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </Field>
          {err && <Notice tone="error">{err}</Notice>}
          <Button type="submit" busy={busy} size="lg" className="w-full">Send me a code</Button>
        </form>
      ) : (
        <form onSubmit={verify} className="mt-4 space-y-3">
          <Field label={`Code sent to ${sent.phone}`}>
            <input
              className={`${inputCls} font-mono-data text-2xl tracking-[0.4em] text-center`}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
          </Field>
          {sent.dev_code && <Notice tone="warn">Development mode: no SMS is sent. Your code is <b className="font-mono-data">{sent.dev_code}</b>.</Notice>}
          {err && <Notice tone="error">{err}</Notice>}
          <Button type="submit" busy={busy} size="lg" className="w-full" disabled={code.length !== 6}>Confirm</Button>
          <button type="button" className="text-sm text-teal font-semibold" onClick={() => { setSent(null); setCode('') }}>Use a different number</button>
        </form>
      )}
    </Card>
  )
}

function HoldDetails({ need, facility, meta, session, setCitizen, onHeld, onMine }) {
  const [category, setCategory] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const labels = Object.fromEntries((meta?.condition_categories || []).map((c) => [c.id, c.label]))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const hold = await request('/holds', {
        method: 'POST',
        token: session.token,
        body: {
          hospital_id: facility.id,
          type: need === 'stable' ? 'stable' : 'emergency',
          ward: NEEDS[need].ward,
          condition_category: category,
          condition_note: note.trim() || null,
          age_group: age || null,
          sex: sex || null,
        },
      })
      onHeld(hold)
    } catch (x) {
      if (x instanceof ApiError && x.status === 401) setCitizen(null)
      setErr(x)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5 mt-4">
      <h2 className="font-display font-bold text-lg text-navy">Step 2 · What’s happening?</h2>
      <p className="text-sm text-slate-muted mt-1">Only {facility.name} sees this, so they can get ready.</p>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <div>
          <span className="block text-sm font-semibold mb-1.5">Main problem</span>
          <Choice cols={2} value={category} onChange={setCategory} options={CATEGORIES[need].map((c) => ({ value: c, label: labels[c] || c }))} />
        </div>
        <div>
          <span className="block text-sm font-semibold mb-1.5">Patient’s age <span className="font-normal text-slate-muted">(optional)</span></span>
          <Choice cols={4} value={age} onChange={setAge} options={['0-17', '18-39', '40-64', '65+'].map((a) => ({ value: a, label: a }))} />
        </div>
        <div>
          <span className="block text-sm font-semibold mb-1.5">Sex <span className="font-normal text-slate-muted">(optional)</span></span>
          <Choice cols={3} value={sex} onChange={setSex} options={[{ value: 'female', label: 'Female' }, { value: 'male', label: 'Male' }, { value: 'unspecified', label: 'Prefer not' }]} />
        </div>
        <Field label="Anything else the hospital should know? (optional)" hint={`${note.length}/280 · Please don’t include names or ID numbers.`}>
          <textarea className={inputCls} rows={2} maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        {err && (
          <Notice tone="error">
            {err.message}
            {err.status === 409 && err.message.includes('already have') && (
              <button type="button" onClick={onMine} className="block mt-1 font-semibold underline">See my bed hold</button>
            )}
          </Notice>
        )}
        <Button type="submit" variant="mint" size="lg" busy={busy} className="w-full" disabled={!category}>
          Hold this bed
        </Button>
        <p className="text-xs text-slate-muted">Signed in as {session.phone}. One bed hold at a time per phone number.</p>
      </form>
    </Card>
  )
}

// ---------------------------------------------------------------- after holding

function Held({ hold: initial, session, setCitizen, meta, onFindAnother }) {
  const mine = usePoll(() => (session ? request('/holds/mine', { token: session.token }) : Promise.resolve([])), 10000, [session?.token])
  const hold = (mine.data || []).find((h) => h.id === initial.id) || initial
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const labels = Object.fromEntries((meta?.condition_categories || []).map((c) => [c.id, c.label]))
  const active = hold.status === 'held' || hold.status === 'accepted'

  useEffect(() => {
    if (mine.error instanceof ApiError && mine.error.status === 401) setCitizen(null)
  }, [mine.error, setCitizen])

  const cancel = async () => {
    if (!window.confirm('Cancel this bed hold? The bed goes back to others who need it.')) return
    setBusy(true)
    try {
      await request(`/holds/${hold.id}/cancel`, { method: 'POST', token: session.token })
      await mine.reload()
    } catch (x) {
      setErr(x.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-xl">
      <Card className="p-6 text-center">
        <Badge tone={STATUS_TONE[hold.status]}>{hold.status === 'accepted' ? '✓ Hospital confirmed' : STATUS_LABEL[hold.status]}</Badge>
        <div className="text-sm text-slate-muted mt-4">Your bed code</div>
        <div className="font-mono-data font-bold text-5xl tracking-[0.15em] text-navy mt-1">{hold.code}</div>
        <div className="text-sm text-slate-muted mt-2">Show this code when you arrive. It was also sent to you by SMS.</div>
        <div className="mt-5 font-display font-bold text-xl text-navy">{hold.hospital_name}</div>
        <div className="text-sm text-slate-muted">{WARD_LABEL[hold.ward]} · {labels[hold.condition_category] || hold.condition_category}</div>
        {active && (
          <div className="mt-4 rounded-xl bg-slate-bg py-3">
            <div className="text-xs text-slate-muted">Bed held for</div>
            <div className="text-2xl"><Countdown until={hold.expires_at} /></div>
          </div>
        )}
        {hold.status === 'held' && <p className="text-sm text-slate-muted mt-3">The hospital has been alerted. Start going now. You don’t need to wait for them to confirm.</p>}
        {hold.status === 'accepted' && <p className="text-sm text-teal font-semibold mt-3">They are expecting you. Go straight there.</p>}
        {hold.status === 'declined' && (
          <Notice tone="error" className="mt-4 text-left">
            {hold.hospital_name} can’t take this patient right now. Please choose another hospital.
            <Button variant="danger" size="sm" className="mt-2 w-full" onClick={onFindAnother}>Find another hospital</Button>
          </Notice>
        )}
        {hold.status === 'expired' && <Notice tone="warn" className="mt-4">This hold expired and the bed was released.</Notice>}
        {active && (
          <div className="grid grid-cols-2 gap-2 mt-5">
            {hold.hospital_lat !== undefined && (
              <a href={directionsUrl(hold.hospital_lat, hold.hospital_lng)} target="_blank" rel="noreferrer">
                <Button variant="mint" className="w-full">🧭 Directions</Button>
              </a>
            )}
            {hold.hospital_phone && (
              <a href={`tel:${hold.hospital_phone}`}>
                <Button variant="secondary" className="w-full">📞 Call hospital</Button>
              </a>
            )}
          </div>
        )}
        {err && <Notice tone="error" className="mt-3">{err}</Notice>}
        {active && (
          <Button variant="ghost" size="sm" className="mt-4" busy={busy} onClick={cancel}>
            Cancel this bed hold
          </Button>
        )}
      </Card>
      <p className="text-center text-sm text-slate-muted mt-3">Things getting worse? Call <a className="font-bold text-coral" href="tel:112">112</a>.</p>
    </div>
  )
}

function Mine({ session, setCitizen, meta, onOpen, onHome }) {
  const mine = usePoll(() => (session ? request('/holds/mine', { token: session.token }) : Promise.resolve([])), 15000, [session?.token])
  useEffect(() => {
    if (mine.error instanceof ApiError && mine.error.status === 401) setCitizen(null)
  }, [mine.error, setCitizen])
  if (!session) return <Notice>Please verify your phone number first by holding a bed.</Notice>
  return (
    <div className="max-w-xl">
      <h1 className="font-display font-bold text-2xl text-navy">My bed holds</h1>
      <p className="text-sm text-slate-muted">For {session.phone}</p>
      {mine.loading && !mine.data && <div className="flex justify-center py-10 text-teal"><Spinner /></div>}
      {mine.data && mine.data.length === 0 && <Empty>No bed holds yet.</Empty>}
      <div className="space-y-2 mt-3">
        {(mine.data || []).map((h) => (
          <button key={h.id} className="w-full text-left" onClick={() => onOpen(h)}>
            <Card className="p-4 flex items-center justify-between hover:border-teal">
              <div>
                <div className="font-semibold text-navy">{h.hospital_name}</div>
                <div className="text-xs text-slate-muted">{WARD_LABEL[h.ward]} · code <span className="font-mono-data">{h.code}</span></div>
              </div>
              <Badge tone={STATUS_TONE[h.status]}>{STATUS_LABEL[h.status]}</Badge>
            </Card>
          </button>
        ))}
      </div>
      <div className="flex gap-2 mt-4">
        <Button variant="secondary" onClick={onHome}>Find a bed</Button>
        <Button variant="ghost" onClick={() => setCitizen(null)}>Sign out</Button>
      </div>
    </div>
  )
}
