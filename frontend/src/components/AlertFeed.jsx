export default function AlertFeed({ alerts }) {
  if (!alerts.length) {
    return <p className="text-sm text-slate-muted">No surge alerts right now.</p>
  }
  return (
    <ul className="flex flex-col gap-2">
      {alerts.map((a) => (
        <li
          key={a.id}
          className="flex items-center justify-between bg-coral/10 border border-coral/30 rounded-md px-3 py-2"
        >
          <div>
            <p className="text-sm font-medium text-navy">{a.hospital_name}</p>
            <p className="text-xs text-slate-muted">
              {a.department} at {a.occupancy_pct}% occupancy
            </p>
          </div>
          <span className="font-mono-data text-xs text-coral">{a.id}</span>
        </li>
      ))}
    </ul>
  )
}
