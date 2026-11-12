# BedAlert — From Demo to Real-World System

**Status:** Phase 1 built (see README); Phases 2–4 proposed. September 2026
**Problem:** "No bed syndrome." Patients in Ghana, often in emergencies, are
driven from hospital to hospital and turned away because there is no bed.
Some die on the way. Nobody (patient, relative, ambulance crew) knows where
a free bed is before they set off.

**What BedAlert must do in real life:** show *trustworthy, current* bed
availability and let a bed be *held* for a specific incoming patient, for
four groups of people:

| Actor | Who they are in Ghana | How they reach BedAlert |
|---|---|---|
| Hospital | Bed managers, ER nurses, hospital IT systems | Hospital portal (login) + **API keys** for their hospital system |
| Dispatcher | National Ambulance Service (NAS) control rooms, private ambulances | Dispatch console (login, role-based) |
| Citizen (smartphone) | Patients, relatives, taxi / trotro drivers bringing someone in | Citizen web app (phone-number OTP) |
| Citizen (no internet) | Feature-phone users, rural areas, no data | USSD short code + SMS |

---

## 1. What the v0.2 demo gets wrong for real use

These are not criticisms of the demo (it was built to present) but they
are blockers for real patients.

### 1.1 One app for everyone
`frontend/src/App.jsx` puts `/`, `/dispatch`, `/admin` and `/sms` in the
same app with no login. Anyone who opens `/admin` can change any hospital's
beds; anyone can open `/dispatch`. You are right that this has to be split.

### 1.2 No authentication or authorisation on the API
- `POST /api/hospitals/{id}/beds` (`backend/main.py:217`): anyone can set
  any hospital's bed count to 0 or to full.
- `POST /api/hospitals` (`backend/main.py:189`): anyone can register a fake
  hospital and it goes live immediately, and patients could be routed to it.
- `POST /api/dispatch/emergency` (`backend/main.py:309`): anyone can
  dispatch.

### 1.3 Privacy leaks (Ghana Data Protection Act, 2012 — Act 843)
- `GET /api/bookings` (`backend/main.py:295`) returns every booking in the
  country, including the free-text condition notes, to anyone.
- `GET /api/hospitals` returns each hospital's `notifications` list (with
  condition notes) and doctor names to the public.
- Condition notes are free text, so people *will* type names and phone
  numbers into them. Health data is sensitive data under Act 843; BedAlert
  will need to register with the Data Protection Commission.

### 1.4 Bookings permanently consume beds
A booking immediately does `available -= 1` and nothing ever gives the bed
back. In real life:
- people book and never arrive;
- a single script could "book" every ER bed in Accra in seconds, which
  would make the system *cause* no-bed turn-aways instead of preventing them.

### 1.5 Data can be stale and nobody would know
The whole system is only as good as the bed counts. If a nurse forgets to
tap the button for 6 hours, BedAlert sends patients to a hospital that is
actually full, which is exactly the failure we are trying to fix.

### 1.6 Nothing survives a restart
All state is in Python dictionaries. Render's free tier also sleeps after
inactivity and takes 30–60 seconds to wake. Neither is acceptable for an
emergency service.

---

## 2. Target architecture

Your instinct is right: **every actor gets its own app, but they all share
one core API and one database.** Beds must live in one ledger; if each group
had its own database, two groups could claim the same last bed.

```
 ┌────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────────┐ ┌──────────────┐
 │ Citizen    │ │ Dispatch    │ │ Hospital    │ │ Hospital HIS  │ │ USSD / SMS   │
 │ web app    │ │ console     │ │ portal      │ │ (their system)│ │ (telco via   │
 │ (PWA)      │ │ (NAS etc.)  │ │ (staff)     │ │               │ │ aggregator)  │
 └─────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬────────┘ └──────┬───────┘
  phone OTP     staff login +    staff login +     API key +          signed
  (JWT)         role: dispatcher role: hospital    HMAC signature     webhook
       │               │         scoped to 1 hosp.     │                  │
       └───────────────┴──────────────┬───────────────┴──────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │  BedAlert Core API        │  FastAPI (keep what we have)
                        │  - availability ledger    │
                        │  - holds / referrals      │
                        │  - routing                │
                        │  - notifications (SMS)    │
                        │  - audit log              │
                        └────────────┬──────────────┘
                                     ▼
                        Postgres (Supabase)  +  SMS provider
                                     ▲
                        ┌────────────┴──────────────┐
                        │  Network admin console     │  BedAlert ops team:
                        │  verify hospitals, issue   │  onboarding, API keys,
                        │  API keys, see analytics   │  data-quality monitoring
                        └────────────────────────────┘
```

### 2.1 The five surfaces

| App | Deploys as | Auth | Can do | Cannot do |
|---|---|---|---|---|
| **Citizen app** | Own Vercel project, installable PWA, low-data | None to *search*; phone OTP to *hold a bed* | See beds near me, hold one bed, get code + directions, cancel | See other people's bookings, see doctor names |
| **Dispatch console** | Own Vercel project, restricted domain | Staff account, `dispatcher` role, belongs to an agency | Find best hospital, place ER/ICU hold, see live incidents for their region, track ETA | Change bed counts |
| **Hospital portal** | Own Vercel project | Staff account, `hospital_staff` / `hospital_admin` role, **scoped to one hospital** | Update beds, accept/decline incoming patients, mark arrived, manage on-call staff, create/rotate API keys | See other hospitals' patients |
| **Hospital API (machine)** | Same core API, `/v1/integrations/*` | API key per hospital + request signing | Push bed counts from their system automatically, receive incoming-patient webhooks | Anything outside their own hospital |
| **USSD/SMS gateway** | Route in core API (`/v1/ussd`, `/v1/sms/inbound`) | Aggregator signature / IP allow-list | Same as citizen app, menu-driven | — |
| **Network admin** | Small internal app | BedAlert staff, 2FA | Verify new hospitals (license check with HeFRA), issue first API key, monitor stale data | — |

### 2.2 Replace "booking" with a **hold → accept → arrive** lifecycle

This is the most important change for real life.

```
 requested ──► held ──► accepted ──► arrived ──► (closed)
                 │          │
                 │          └──► declined ─► auto re-route to next hospital
                 └──► expired (no show within window) ─► bed released
```

- **Hold windows:** e.g. ER 30–45 min (or dispatcher's ETA + buffer),
  general ward 2 h. When a hold expires the bed goes back automatically.
- **Hospital must accept** emergency holds (one tap, or auto-accept if
  their API integration says so). If not accepted within ~3 min, BedAlert
  calls/SMSes the on-call contact, then re-routes.
- **Limits:** one active hold per phone number; rate limits per phone and
  per IP; dispatcher holds are unlimited but audited.
- Beds are counted as `total - occupied - held`, so a hold never makes the
  hospital's own count wrong.

### 2.3 Data freshness is a feature

- Every hospital shows **"updated X min ago"** everywhere, including in USSD
  replies.
- If a hospital hasn't updated in N minutes (e.g. 60), it is shown as
  **"unconfirmed"** and ranked below hospitals with fresh data, and the
  hospital gets an SMS reminder.
- Hospitals that connect their HIS through the API key are always fresh.
  That is the main reason the API-key integration matters.

### 2.4 Hospital API keys (what you described)

- A hospital admin creates keys in the portal. We store only a hash; the key
  is shown once. Format e.g. `ba_live_<prefix>_<secret>`.
- Keys are scoped (`beds:write`, `referrals:read`, `referrals:write`) and
  tied to exactly one hospital.
- Endpoints:
  - `PUT /v1/integrations/beds` (set current occupancy per ward)
  - `GET /v1/integrations/referrals?status=held` (incoming patients)
  - `POST /v1/integrations/referrals/{id}/accept|decline|arrived`
  - Outbound webhook to the hospital's URL when a patient is coming,
    signed with HMAC so they can verify it's from us.
- For hospitals with no IT system (the majority to start with): the portal's
  tap buttons plus an **SMS fallback** (e.g. nurse texts `ER 3` to update).

### 2.5 Privacy by design

- Public endpoints return **only**: hospital name, location, ward-level free
  counts, freshness. No doctor names, no notifications.
- Condition info is a **short picklist** (chest pain, road accident, labour,
  breathing difficulty, …) plus optional short text visible only to the
  receiving hospital and dispatcher.
- Phone numbers are stored only for active holds and follow-up SMS, then
  deleted or hashed after a retention period.
- Every write is written to an **audit log** (who, what, when).

### 2.6 Ghana-specific realities to design for

- **USSD sessions are short** (telcos cut them off after roughly 1–3 min) and
  menus must fit on a small screen. Keep to ≤ 4 steps; send the code by SMS
  afterwards so it survives the session ending.
- **Location:** support Ghana Post GPS digital addresses and a region →
  district picklist, not only GPS coordinates.
- **Short code:** a USSD short code is provisioned through an aggregator
  (e.g. Africa's Talking, Hubtel, Arkesel) across MTN / Telecel / AT. This
  takes weeks and costs money, so start early; use a shared/test code first.
- **National Ambulance Service** is the most important dispatcher partner.
  Design the dispatch console so it can sit next to what they already use.
- **Always show 112 / call-the-hospital fallbacks.** BedAlert must never be
  the only path in an emergency.

---

## 3. Proposed repository layout

```
bedalert/
  services/api/            FastAPI core (from backend/), Postgres, Alembic migrations
  apps/citizen/            React PWA — public search + hold
  apps/dispatch/           React — dispatcher console
  apps/hospital/           React — hospital portal + API-key management
  apps/admin/              React — network admin (later)
  packages/ui/             Shared components (CapacityBar, HospitalCard, tokens)
  docs/                    This file, API reference for hospitals, pilot plan
```

**Hosting within free-tier limits:** all web apps are built from ONE Vercel
project as separate pages with separate bundles (e.g. `/`, `/hospital`,
`/dispatch`), so the public never loads staff code. The API is a second
Vercel project (a Python function; SMS are sent by the request that queued
them, with a daily cron as a safety net). So we only ever need one Supabase
project and two Vercel projects. Security does
not depend on the split: every API route checks the caller's role.

---

## 4. Build plan (phased)

**Phase 1 — Real foundation ✅ done**
1. Postgres schema: `hospitals`, `wards`, `bed_snapshots`, `holds`,
   `users`, `memberships` (user ↔ hospital/agency + role), `api_keys`,
   `audit_log`.
2. Auth: staff email/password (or Supabase Auth) with roles; citizen phone
   OTP.
3. Lock down every endpoint by role; strip private fields from public
   responses.
4. Hold → accept → arrive lifecycle with expiry job.
5. Tests for the ledger (no double-booking the last bed, expiry releases beds).

**Phase 2 — Split the apps ✅ done** (family app, hospital portal, dispatch console, plus a small network-admin page)
6. Move to `apps/*` + `packages/ui`; one Vercel project per app.
7. Hospital portal: bed updates, incoming patients, accept/decline.
8. Dispatch console: region view, hold, ETA.
9. Citizen PWA: search, hold, SMS confirmation.

**Phase 3 — Real channels (≈2–4 weeks, partly waiting on telcos)**
10. Hospital API keys + webhooks + a short integration guide.
11. USSD + SMS through an aggregator (sandbox first, then short code).
12. Staleness reminders and SMS bed-update fallback for hospitals.

**Phase 4 — Pilot in one district**
13. 2–5 hospitals in one area (e.g. Kumasi Metro, near KNUST) + one
    ambulance station. Measure: minutes from call to bed confirmed,
    number of hospitals tried per patient, % of time data was fresh.

**Non-code work that decides whether this succeeds**
- A partner hospital champion and, ideally, a Regional Health Directorate
  or NAS contact.
- Data Protection Commission registration.
- Paid always-on hosting (not free tiers that sleep) before any real patient
  depends on it.

---

## 5. Decisions needed from the team

1. ~~Auth provider~~ Decided: Supabase Postgres + Supabase Auth for staff;
   citizen phone OTP is run by BedAlert itself so it can use a Ghanaian SMS
   provider (Africa's Talking).
2. **First pilot district** and which hospital to approach first.
3. **SMS/USSD aggregator** (Africa's Talking vs. Hubtel vs. Arkesel):
   compare pricing and short-code lead time.
4. ~~Which phase first~~ Phase 1 done. Next: Phase 2 (split the apps).
5. **A Supabase slot:** the free plan allows 2 active projects; BedAlert
   needs one of them (or Supabase Pro).
