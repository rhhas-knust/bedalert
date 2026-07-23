import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Public view', end: true },
  { to: '/dispatch', label: 'Dispatcher console' },
  { to: '/admin', label: 'Hospital admin' },
  { to: '/sms', label: 'SMS / USSD simulator' },
]

export default function Topbar() {
  return (
    <header className="bg-navy text-white">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-mint" />
          <span className="font-display font-semibold text-lg tracking-tight">BedAlert</span>
        </div>
        <nav className="flex gap-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive ? 'bg-teal text-white' : 'text-slate-200 hover:bg-navy-light'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
