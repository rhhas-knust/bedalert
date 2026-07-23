# BedAlert — Demo Monorepo

A working demo of BedAlert's three-tier architecture, built for GCL 2026:

1. **Web dashboard** — public booking view, dispatcher console, hospital admin panel (all one React app, three routes)
2. **SMS/USSD layer** — simulated phone UI that talks to the same backend, standing in for the no-internet tier
3. **Hospital API** — FastAPI backend serving only anonymous bed counts + aggregate demographics (no patient records, by design)

All data is mocked and in-memory — resets when you restart the backend. This is intentionally fast to demo, not production-hardened.

## Structure

```
bedalert-app/
  backend/          FastAPI app + mock hospital data
  frontend/         React (Vite) app with 4 views
```

## Running it in VS Code

**1. Backend** (open a terminal in `backend/`):
```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API docs auto-generate at `http://localhost:8000/docs` — useful for testing endpoints directly.

**2. Frontend** (open a second terminal in `frontend/`):
```bash
npm install
npm run dev
```
Opens at `http://localhost:5173`.

Keep both terminals running side by side (VS Code's split terminal works well here).

## Where the three GCL tiers map to code

| Tier | Where |
|---|---|
| Public booking view | `frontend/src/pages/PublicDashboard.jsx` |
| Ambulance dispatcher | `frontend/src/pages/DispatcherConsole.jsx` |
| Hospital admin (tap button) | `frontend/src/pages/HospitalAdmin.jsx` |
| SMS/USSD tier | `frontend/src/pages/SmsSimulator.jsx` + `POST /api/sms` in `backend/main.py` |
| Shared hospital API | `backend/main.py`, data in `backend/mock_data.py` |

## Design tokens

- Navy `#0B2545`, Teal `#0F6E6E`, Mint `#8FE3C6`, Amber `#E8A33D` (surge), Coral `#E15554` (critical)
- Space Grotesk (headers) / Inter (body) / IBM Plex Mono (data — bed counts, IDs, timestamps)
- Signature component: the segmented **capacity bar** (`frontend/src/components/CapacityBar.jsx`) — same visual language across every view, so a dispatcher and a member of the public read hospital load the same way

## Next steps toward the full MVP

- Swap `mock_data.py` for a real database (Postgres) once a schema is agreed with your team
- Add auth so hospital admin is scoped to one hospital, not a dropdown
- Wire `POST /api/sms` to an actual SMS/USSD aggregator (e.g. Africa's Talking, Twilio) instead of the on-screen phone mockup
- Wire real SMS delivery for hospital notifications (currently logged in-app, not actually sent)

## Changelog — v0.2

- Added 3 Ghana hospitals (Accra, Kumasi, Tamale) to the mock network
- Booking reason (`condition_notes`) is now a required field everywhere, not optional
- Public dashboard supports both stable-case **and self-reported emergency** bookings, with a type toggle
- New shared **live emergency feed** (`GET /api/emergency-log`) — surfaces emergencies raised from the public app, SMS/USSD, and the dispatcher console in one place, visible on the Dispatcher Console
- Critical-severity dispatches now auto-lock to the Emergency department server-side and client-side
- Hospitals now track **doctors on site**, with on-call status; emergencies notify the on-call doctor and generate a code, visible on the Admin page
- Admin page now shows a **bookings table** per hospital and an **emergency notifications** panel
- New **hospital registration** form on the Admin page (`POST /api/hospitals`) so new hospitals can join the network
- SMS/USSD flow rebuilt: issue type (emergency/regular) → reason → locality/municipality → hospital list → auto-book + simulated SMS to the hospital
