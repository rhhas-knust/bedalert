import CapacityBar from './CapacityBar.jsx'

export default function HospitalCard({ hospital, onBook }) {
  const { ER, ICU, general } = hospital.departments

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col gap-4">
      <div>
        <h3 className="font-display font-semibold text-navy text-base">{hospital.name}</h3>
        <p className="text-sm text-slate-muted">{hospital.city}, {hospital.country}</p>
      </div>
      <div className="flex flex-col gap-3">
        <CapacityBar label="Emergency" available={ER.available} total={ER.total} />
        <CapacityBar label="ICU" available={ICU.available} total={ICU.total} />
        <CapacityBar label="General" available={general.available} total={general.total} />
      </div>
      <button
        onClick={() => onBook(hospital)}
        disabled={general.available <= 0}
        className="mt-1 self-start px-4 py-2 rounded-md bg-teal text-white text-sm font-medium hover:bg-teal-dark disabled:bg-slate-200 disabled:text-slate-muted transition-colors"
      >
        {general.available > 0 ? 'Book a stable-case bed' : 'No beds available'}
      </button>
    </div>
  )
}
