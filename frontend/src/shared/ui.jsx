import { useEffect, useState } from 'react'

// ---------------------------------------------------------------- layout

export function AppShell({ app, right, children, wide = false }) {
  return (
    <div className="min-h-screen bg-slate-bg">
      <header className="bg-navy text-white">
        <div className={`${wide ? 'max-w-7xl' : 'max-w-5xl'} mx-auto px-4 py-3 flex items-center justify-between gap-3`}>
          <a href="/" className="flex items-center gap-2 shrink-0">
            <span className="w-3 h-3 rounded-full bg-mint ring-4 ring-mint/20" />
            <span className="font-display font-bold text-lg tracking-tight">BedAlert</span>
            {app && <span className="text-slate-300 text-sm font-medium hidden sm:inline">· {app}</span>}
          </a>
          <div className="flex items-center gap-2 text-sm">{right}</div>
        </div>
      </header>
      <main className={`${wide ? 'max-w-7xl' : 'max-w-5xl'} mx-auto px-4 py-5`}>{children}</main>
    </div>
  )
}

export function Card({ className = '', children, ...rest }) {
  return (
    <div className={`bg-white rounded-2xl border border-slate-200 shadow-sm ${className}`} {...rest}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, right }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="font-display font-bold text-xl text-navy">{children}</h2>
      {right}
    </div>
  )
}

// ---------------------------------------------------------------- controls

const BTN = {
  primary: 'bg-navy text-white hover:bg-navy-light',
  mint: 'bg-mint text-navy hover:bg-mint-light',
  teal: 'bg-teal text-white hover:bg-teal-light',
  danger: 'bg-coral text-white hover:brightness-105',
  secondary: 'bg-white text-navy border border-slate-300 hover:bg-slate-50',
  ghost: 'text-navy hover:bg-slate-100',
}

export function Button({ variant = 'primary', size = 'md', className = '', busy = false, children, ...rest }) {
  const sz = size === 'lg' ? 'px-5 py-3.5 text-base' : size === 'sm' ? 'px-3 py-1.5 text-sm' : 'px-4 py-2.5 text-sm'
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed ${BTN[variant]} ${sz} ${className}`}
      disabled={busy || rest.disabled}
      {...rest}
    >
      {busy && <Spinner small />}
      {children}
    </button>
  )
}

export const inputCls =
  'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-text focus:outline-none focus:ring-2 focus:ring-teal focus:border-teal'

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="block text-sm font-semibold text-slate-text mb-1">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-muted mt-1">{hint}</span>}
    </label>
  )
}

export function Choice({ options, value, onChange, cols = 3 }) {
  return (
    <div className={`grid gap-2`} style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
      {options.map((o) => (
        <button
          type="button"
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${
            value === o.value ? o.activeCls || 'bg-navy text-white border-navy' : 'bg-white text-navy border-slate-300 hover:bg-slate-50'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- feedback

const TONES = {
  info: 'bg-sky-50 text-sky-900 border-sky-200',
  ok: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  warn: 'bg-amber-50 text-amber-900 border-amber-200',
  error: 'bg-red-50 text-red-900 border-red-200',
}

export function Notice({ tone = 'info', children, className = '' }) {
  return <div className={`rounded-xl border px-4 py-3 text-sm ${TONES[tone]} ${className}`}>{children}</div>
}

export function Badge({ tone = 'slate', children }) {
  const t = {
    slate: 'bg-slate-100 text-slate-700',
    mint: 'bg-mint/40 text-navy',
    amber: 'bg-amber/20 text-amber-900',
    coral: 'bg-coral/15 text-red-800',
    navy: 'bg-navy text-white',
  }[tone]
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ${t}`}>{children}</span>
}

export function Spinner({ small }) {
  return (
    <span
      className={`inline-block ${small ? 'w-4 h-4 border-2' : 'w-6 h-6 border-[3px]'} rounded-full border-current border-r-transparent animate-spin`}
      aria-label="Loading"
    />
  )
}

export function Empty({ children }) {
  return <div className="text-center text-slate-muted py-8 text-sm">{children}</div>
}

// ---------------------------------------------------------------- data display

export function CapacityBar({ available, total, segments = 12 }) {
  const fraction = total > 0 ? available / total : 0
  const filled = Math.round(fraction * segments)
  const color = fraction >= 0.4 ? 'bg-mint-dark' : fraction >= 0.15 ? 'bg-amber' : 'bg-coral'
  return (
    <div className="flex gap-[3px]" aria-label={`${available} of ${total} beds free`}>
      {Array.from({ length: segments }).map((_, i) => (
        <div key={i} className={`h-2 flex-1 rounded-sm ${i < filled ? color : 'bg-slate-200'}`} />
      ))}
    </div>
  )
}

export function Freshness({ minutes, fresh }) {
  if (!fresh) return <span className="text-xs font-semibold text-amber-700">⚠ Not confirmed for {fmtMinutes(minutes)}</span>
  return <span className="text-xs text-slate-muted">Updated {minutes < 1 ? 'just now' : `${fmtMinutes(minutes)} ago`}</span>
}

export function fmtMinutes(m) {
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  return h < 48 ? `${h} h` : `${Math.floor(h / 24)} days`
}

export function timeAgo(iso, now = Date.now()) {
  const m = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
  return m < 1 ? 'just now' : `${fmtMinutes(m)} ago`
}

export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

export function Countdown({ until }) {
  const now = useNow(1000)
  const s = Math.max(0, Math.round((new Date(until).getTime() - now) / 1000))
  if (s === 0) return <span className="font-mono-data text-coral font-bold">expired</span>
  const mm = Math.floor(s / 60)
  const ss = String(s % 60).padStart(2, '0')
  return <span className={`font-mono-data font-bold ${s < 300 ? 'text-coral' : 'text-navy'}`}>{mm}:{ss}</span>
}

export const WARD_LABEL = { ER: 'Emergency', ICU: 'ICU', general: 'General ward', maternity: 'Maternity', paediatric: 'Paediatric' }
export const SEVERITY_TONE = { critical: 'coral', severe: 'amber', moderate: 'slate', stable: 'slate' }
export const STATUS_LABEL = {
  held: 'Waiting for hospital',
  accepted: 'Accepted',
  arrived: 'Arrived',
  declined: 'Declined',
  expired: 'Expired',
  cancelled: 'Cancelled',
}
export const STATUS_TONE = { held: 'amber', accepted: 'mint', arrived: 'navy', declined: 'coral', expired: 'slate', cancelled: 'slate' }
export const SOURCE_LABEL = { dispatcher: '🚑 Ambulance', public: '📱 Family (app)', ussd: '☎️ Family (USSD)' }

export function directionsUrl(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
}
