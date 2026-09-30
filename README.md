# BedAlert

Real-time hospital bed availability for Ghana, to end "no bed syndrome":
patients driven from hospital to hospital and turned away because nobody
knew where a free bed was.

One core API holds a single bed ledger. Each group of users gets its own
way in, with its own credential:

| Who | Way in | Credential |
|---|---|---|
| Anyone | `GET /v1/facilities` (free beds, how fresh the numbers are) | none |
| Citizen with a smartphone | Citizen app → `POST /v1/holds` | phone number + SMS code |
| Citizen with a feature phone | USSD short code → `POST /v1/ussd` | the phone itself |
| Hospital staff | Hospital portal → `/v1/hospital/{id}/…` | Supabase Auth login, limited to their hospital |
| Hospital IT system | `/v1/integrations/…` | hospital API key |
| Ambulance dispatcher | Dispatch console → `/v1/dispatch/…` | Supabase Auth login + dispatcher role |
| BedAlert team | `/v1/admin/…` | Supabase Auth login + network admin role |

See `docs/PRODUCTION_ARCHITECTURE.md` for the reasoning and the roadmap.

## Status

- **Phase 1 (done, this branch): real foundation.** Postgres schema,
  role-based access on every route, holds that expire instead of bookings
  that consume beds forever, automatic re-routing when a hospital declines
  an ambulance patient, hospital API keys, phone OTP, USSD in the
  Africa's Talking format, SMS outbox, audit log. 31 tests.
- **Phase 2 (next): split the apps.** The React app in `frontend/` is still
  the v0.2 demo and **does not talk to the new API yet**; it will be
  rebuilt as citizen / hospital / dispatch apps.

## How a bed hold works

```
held ──► accepted ──► arrived        (patient now occupies the bed)
  ├─────────┴──► declined            (ambulance holds re-route to the next hospital)
  ├─────────┴──► cancelled
  └─────────┴──► expired             (no show in time → bed released automatically)
```

Bookable beds = `total − occupied − active holds`. Hospitals whose numbers
are older than 60 minutes are marked "not confirmed" and ranked lower.
One active hold per phone number. The last bed cannot be given twice (the
ward row is locked while a hold is created; there is a test with 20
simultaneous requests).

## Run the API locally

Needs Python 3.11+ and Postgres 15+.

```bash
cd backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

createdb bedalert                                    # or use pgAdmin / psql
export BEDALERT_ENV=dev DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bedalert
python -m scripts.migrate                            # creates the tables
python -m scripts.seed_dev                           # demo hospitals + demo staff (dev only)
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` to try every endpoint.

In dev mode you can log in as a demo staff member without Supabase:
`POST /v1/dev/staff-token {"email": "dispatch.ashanti@bedalert.dev"}`,
then click **Authorize** in `/docs` and paste the token. Demo accounts:
`admin@bedalert.dev` (network admin), `dispatch.ashanti@bedalert.dev`
(dispatcher), `nurse.kath@bedalert.dev` / `admin.kath@bedalert.dev`
(Komfo Anokye staff / admin). OTP codes are returned in the response
(`dev_code`) and SMS are printed to the server log.

Try USSD from a terminal (each answer is appended with `*`):

```bash
curl -X POST "localhost:8000/v1/ussd?key=dev-ussd-secret" -d "phoneNumber=0241234567&text=1*1*1*1"
```

### Tests

```bash
createdb bedalert_test
pytest                       # uses DATABASE_URL=…/bedalert_test by default; wipes it each run
```

## Layout

```
supabase/migrations/     SQL schema (works on local Postgres and on Supabase)
backend/app/
  ledger.py              beds, holds, expiry, routing, re-routing — the core rules
  auth.py                staff (Supabase JWT), citizen (OTP token), hospital API keys
  sms.py                 SMS outbox + Africa's Talking sender
  routers/               one file per caller: public, citizen, ussd, hospital,
                         integrations, dispatch, admin (+ dev, local only)
backend/scripts/         migrate, seed_dev, grant_role
backend/tests/
frontend/                v0.2 demo UI (to be replaced in Phase 2)
```

## Deploying

See `DEPLOYMENT.md`. Hosting stays within free-tier limits: Supabase (database
+ staff login), Render (API) and Vercel (the web apps, all from one project).
