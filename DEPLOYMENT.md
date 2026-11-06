# Deploying BedAlert

Three free services, each used once:

| Service | Hosts | Free-tier limit that matters |
|---|---|---|
| **Supabase** | Postgres database + staff login (Supabase Auth) | 2 active projects per account; pauses after 7 days of no activity |
| **Render** | The API (`backend/`) | Sleeps after inactivity, 30–60 s to wake |
| **Vercel** | The web apps (`frontend/`), all from **one** project | — |

The separate citizen / hospital / dispatch apps planned for Phase 2 will be
built from the same Vercel project (separate pages and bundles), so we never
need more than one project on each service.

> Before real patients depend on BedAlert, move Supabase and Render to paid
> plans. A bed service that sleeps or pauses is not safe in an emergency.

## 1. Supabase (database + staff login)

Free accounts can have 2 active projects. If both are in use, pause one
(Project → Settings → General → Pause project) or upgrade.

1. Create a project named `bedalert`. Pick the region closest to Ghana
   (e.g. `eu-west` / London).
2. Apply the schema, either:
   - `supabase link --project-ref <ref> && supabase db push` from the repo root, or
   - set `DATABASE_URL` to the project's connection string and run
     `python -m scripts.migrate` in `backend/` (Render does this on every start).
3. Authentication → Providers: enable **Email**. Turn off public sign-ups
   if you want to invite staff only.
4. Note the JWKS URL: `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`.
5. Create your own account (Authentication → Users → Add user), copy its
   user id, and make yourself the first network admin:

   ```bash
   cd backend
   DATABASE_URL=<supabase connection string> \
     python -m scripts.grant_role --user-id <uuid> --email you@example.com --role network_admin
   ```

Every table has row level security switched on with no policies, so the
Supabase browser keys cannot read or write BedAlert data directly. Only the
API can.

## 2. Render (API)

1. New → Blueprint → pick this repo. `render.yaml` sets everything up.
2. Fill the variables marked "sync: false":
   - `DATABASE_URL`: Supabase connection string (session pooler)
   - `CORS_ORIGINS`: your Vercel URL, e.g. `https://bedalert.vercel.app`
   - `SUPABASE_JWKS_URL`: from step 1.4
   - `AT_USERNAME` / `AT_API_KEY`: Africa's Talking (use `sandbox` to start)
3. Render generates `CITIZEN_TOKEN_SECRET`, `HASH_PEPPER` and
   `USSD_CALLBACK_SECRET`. **Never change `HASH_PEPPER` later**; it would
   invalidate every hospital API key.
4. Check `https://<your-api>.onrender.com/v1/health`.

The API refuses to start in production if a secret is missing or
`SMS_PROVIDER` is still `console`.

## 3. USSD + SMS (Africa's Talking)

1. Create an Africa's Talking account; start in the sandbox.
2. USSD → create a channel. Callback URL:
   `https://<your-api>.onrender.com/v1/ussd?key=<USSD_CALLBACK_SECRET>`
3. Test with the Africa's Talking simulator. A dedicated short code on
   MTN / Telecel / AT takes weeks to provision, so apply early.

## 4. Vercel (the four web apps)

One Vercel project serves the family app (`/`), hospital portal
(`/hospital`), dispatch console (`/dispatch`) and admin page (`/admin`).

1. Vercel → Add New → Project → import this repository.
2. **Root Directory:** `frontend`. Vercel detects Vite; `frontend/vercel.json`
   sets the build, the `/hospital` `/dispatch` `/admin` routes and security headers.
3. **Environment variables** (Settings → Environment Variables):
   - `VITE_API_URL` = your API's URL, no trailing slash
   - `VITE_SUPABASE_URL` = `https://<project-ref>.supabase.co`
   - `VITE_SUPABASE_ANON_KEY` = the project's publishable (anon) key. It is
     meant to be public; row level security keeps the data closed.
4. Deploy. Then add the Vercel URL (and any custom domain) to the API's
   `CORS_ORIGINS`, comma-separated, e.g. `https://bedalert.vercel.app`.
5. In Supabase → Authentication → URL Configuration, set the Site URL to the
   Vercel URL so email confirmation links come back to BedAlert.

Without the two Supabase variables the apps fall back to the development
sign-in, which only works against an API running with `BEDALERT_ENV=dev`.

**Onboarding the first users after deploy:**
1. Create your own account at `/hospital` (or `/admin`), then make yourself
   network admin with `scripts/grant_role` (step 1.5 above).
2. At `/admin`: add the ambulance agency, and grant dispatchers their role
   once they have created an account.
3. Hospitals register themselves at `/hospital`. Verify each at `/admin`
   after checking the HeFRA licence by phone.

## Local development

See the README. No Supabase needed: in `BEDALERT_ENV=dev` the API issues
its own demo staff tokens.
