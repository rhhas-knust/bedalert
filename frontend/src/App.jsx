import { Routes, Route } from 'react-router-dom'
import Topbar from './components/Topbar.jsx'
import PublicDashboard from './pages/PublicDashboard.jsx'
import DispatcherConsole from './pages/DispatcherConsole.jsx'
import HospitalAdmin from './pages/HospitalAdmin.jsx'
import SmsSimulator from './pages/SmsSimulator.jsx'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-bg font-body">
      <Topbar />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<PublicDashboard />} />
          <Route path="/dispatch" element={<DispatcherConsole />} />
          <Route path="/admin" element={<HospitalAdmin />} />
          <Route path="/sms" element={<SmsSimulator />} />
        </Routes>
      </main>
    </div>
  )
}
