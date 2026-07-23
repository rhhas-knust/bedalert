// The signature element: a segmented capacity gauge. Every BedAlert surface
// (public view, dispatcher console, hospital admin, and the text summaries
// sent over SMS) reads hospital load through this same shape, so capacity
// is legible at a glance regardless of which tier you're looking at.

function segmentColor(fraction) {
  if (fraction >= 0.4) return 'bg-mint-dark'
  if (fraction >= 0.15) return 'bg-amber'
  return 'bg-coral'
}

export default function CapacityBar({ label, available, total, segments = 10 }) {
  const fraction = total > 0 ? available / total : 0
  const filled = Math.round(fraction * segments)
  const color = segmentColor(fraction)

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-slate-muted uppercase tracking-wide">
          {label}
        </span>
        <span className="font-mono-data text-sm text-navy">
          {available}/{total}
        </span>
      </div>
      <div className="flex gap-[3px]">
        {Array.from({ length: segments }).map((_, i) => (
          <div
            key={i}
            className={`h-2.5 flex-1 rounded-sm ${i < filled ? color : 'bg-slate-200'}`}
          />
        ))}
      </div>
    </div>
  )
}
