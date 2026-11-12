# Deploying BedAlert

Two free services:

| Service | Hosts | Free-tier limit that matters |
|---|---|---|
| **Supabase** | Postgres database + staff login (Supabase Auth) | 2 active projects per account; pauses after 7 days of no activity |
| **Vercel** | Two projects from this one repo: the API (`backend/`) and the four web apps (`frontend/`) | Cron jobs run at most once a day on Hobby |

> Before real patients depend on BedAlert, move Supabase to a paid plan (it
> must never pause) and Vercel to Pro. A bed service that sleeps or pauses
> is not safe in an emergency.

(`render.yaml` is kept as an alternative API host, a long-running server
instead of Vercel Functions. You don't need it if you follow this guide.)

## 1. Supabase (database + staff login)

Free accounts can have 2 active projects. If both are in use, pause one
(Project → Settings → General → Pause project) or upgrade.

1. Create a project named `bedalert`. Pick the region closest to Ghana
   (e.g. `eu-west` / London).
2. Apply the schema, either:
   - `supabase link --project-ref <ref> && supabase db push` from the repo root, or
   - set `DATABASE_URL` to the project's connection string and run
     `python -m scripts.migrate` in `backend/`.
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

   Or, without Python, in Supabase → SQL Editor:

   ```sql
   insert into staff (user_id, email) values ('<uuid>', 'you@example.com')
     on conflict (user_id) do update set email = excluded.email;
   insert into memberships (user_id, role) values ('<uuid>', 'network_admin');
   ```

Every table has row level security switched on with no policies, so the
Supabase browser keys cannot read or write BedAlert data directly. Only the
API can.

## 2. Vercel: the API (`backend/`)

On Vercel the API runs as a function that is paused between requests, so:
every request sends the SMS it queued right after its transaction commits;
a daily cron job (`backend/vercel.json`) retries anything left; and the
database is reached through Supabase's **transaction pooler**.

1. Vercel → Add New → Project → import this repository. Name it
   `bedalert-api`. **Root Directory:** `backend`. Vercel detects FastAPI
   (`backend/pyproject.toml` points it at `main:app`).
2. **Environment variables** (Production):

   | Name | Value |
   |---|---|
   | `BEDALERT_ENV` | `production` |
   | `DATABASE_URL` | Supabase → Connect → **Transaction pooler** string (port 6543), with your DB password filled in |
   | `SUPABASE_JWKS_URL` | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
   | `CORS_ORIGINS` | the web apps' URL, e.g. `https://bedalert.vercel.app` (comma-separate several) |
   | `DB_POOL_MAX` | `3` |
   | `CITIZEN_TOKEN_SECRET` | random, 48+ characters (see below) |
   | `HASH_PEPPER` | random, 48+ characters. **Never change it later**: it would invalidate every hospital API key |
   | `USSD_CALLBACK_SECRET` | random, 48+ characters |
   | `CRON_SECRET` | random, 48+ characters (Vercel sends it to the cron job) |
   | `SMS_PROVIDER` | `africastalking` |
   | `AT_USERNAME` / `AT_API_KEY` | Africa's Talking (`sandbox` to start) |

   Make each random value on your own computer and paste it straight into
   Vercel, mark it **Sensitive**, and don't send it to anyone:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
3. Deploy, then open `https://<api>.vercel.app/v1/health`. It should say
   `{"status": "ok", "env": "production"}`.

The API refuses to start in production if a secret is missing or
`SMS_PROVIDER` is still `console`. Migrations are not run on deploy: apply
new files in `supabase/migrations/` to Supabase first (SQL editor,
`supabase db push`, or `python -m scripts.migrate` with `DATABASE_URL` set).

## 3. USSD + SMS (Africa's Talking)

1. Create an Africa's Talking account; start in the sandbox.
2. USSD → create a channel. Callback URL:
   `https://<api>.vercel.app/v1/ussd?key=<USSD_CALLBACK_SECRET>`
3. Test with the Africa's Talking simulator. A dedicated short code on
   MTN / Telecel / AT takes weeks to provision, so apply early.

## 4. Vercel: the four web apps (`frontend/`)

One Vercel project serves the family app (`/`), hospital portal
(`/hospital`), dispatch console (`/dispatch`) and admin page (`/admin`).

1. Vercel → Add New → Project → import this repository again, as a second
   project named `bedalert`.
2. **Root Directory:** `frontend`. Vercel detects Vite; `frontend/vercel.json`
   sets the build, the `/hospital` `/dispatch` `/admin` routes and security headers.
3. **Environment variables** (Settings → Environment Variables):
   - `VITE_API_URL` = the API project's URL, e.g. `https://bedalert-api.vercel.app` (no trailing slash)
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
