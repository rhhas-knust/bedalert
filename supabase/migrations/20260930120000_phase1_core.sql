-- BedAlert Phase 1 — core schema.
--
-- Portable Postgres (runs on a local Postgres 15+ and on Supabase). The API
-- talks to the database with a privileged server-side connection; every table
-- has row level security enabled with NO policies, so Supabase's public
-- PostgREST roles (anon / authenticated) can read and write nothing directly.
--
-- Bookable beds for a ward are:  total - occupied - (active holds)
-- where an active hold is one with status 'held' or 'accepted'.

-- ---------------------------------------------------------------- hospitals

create table hospitals (
    id              uuid primary key default gen_random_uuid(),
    name            text not null check (length(name) between 2 and 160),
    region          text not null,
    district        text not null,
    city            text not null,
    lat             double precision not null check (lat between -90 and 90),
    lng             double precision not null check (lng between -180 and 180),
    phone           text,                 -- public front-desk / emergency line
    license_number  text,                 -- HeFRA licence, checked on verification
    status          text not null default 'pending'
                    check (status in ('pending', 'verified', 'suspended')),
    created_at      timestamptz not null default now(),
    verified_at     timestamptz,
    verified_by     uuid
);

create index hospitals_status_region_idx on hospitals (status, region);

create table wards (
    id           uuid primary key default gen_random_uuid(),
    hospital_id  uuid not null references hospitals (id) on delete cascade,
    kind         text not null
                 check (kind in ('ER', 'ICU', 'general', 'maternity', 'paediatric')),
    total        integer not null check (total >= 0),
    occupied     integer not null default 0 check (occupied >= 0),
    updated_at   timestamptz not null default now(),
    updated_by   text,                    -- 'user:<uuid>' | 'api_key:<prefix>' | 'system'
    unique (hospital_id, kind),
    check (occupied <= total)
);

-- People who get an SMS when a patient is on the way.
create table on_call_contacts (
    id           uuid primary key default gen_random_uuid(),
    hospital_id  uuid not null references hospitals (id) on delete cascade,
    name         text not null,
    role         text not null default 'doctor',
    phone        text not null,
    on_call      boolean not null default true,
    created_at   timestamptz not null default now()
);

create index on_call_contacts_hospital_idx on on_call_contacts (hospital_id);

-- ---------------------------------------------------------------- dispatch agencies

create table agencies (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,             -- e.g. 'National Ambulance Service — Ashanti'
    region      text,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- staff + roles

-- user_id is the Supabase Auth user id (auth.users.id). No foreign key so the
-- schema also runs on plain Postgres for local development.
create table staff (
    user_id     uuid primary key,
    email       text not null,
    full_name   text,
    created_at  timestamptz not null default now()
);

create unique index staff_email_idx on staff (lower(email));

create table memberships (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid not null references staff (user_id) on delete cascade,
    role         text not null
                 check (role in ('network_admin', 'hospital_admin', 'hospital_staff', 'dispatcher')),
    hospital_id  uuid references hospitals (id) on delete cascade,
    agency_id    uuid references agencies (id) on delete cascade,
    created_at   timestamptz not null default now(),
    check (
        (role = 'network_admin'                         and hospital_id is null     and agency_id is null) or
        (role in ('hospital_admin', 'hospital_staff')   and hospital_id is not null and agency_id is null) or
        (role = 'dispatcher'                            and hospital_id is null     and agency_id is not null)
    ),
    unique nulls not distinct (user_id, role, hospital_id, agency_id)
);

create index memberships_user_idx on memberships (user_id);

-- ---------------------------------------------------------------- holds

create table holds (
    id                  uuid primary key default gen_random_uuid(),
    code                text not null unique,
    hospital_id         uuid not null references hospitals (id),
    ward_id             uuid not null references wards (id),
    source              text not null check (source in ('public', 'ussd', 'dispatcher')),
    status              text not null default 'held'
                        check (status in ('held', 'accepted', 'arrived', 'declined', 'expired', 'cancelled')),
    severity            text not null
                        check (severity in ('critical', 'severe', 'moderate', 'stable')),
    condition_category  text not null,
    condition_note      text check (length(condition_note) <= 280),
    age_group           text check (age_group in ('0-17', '18-39', '40-64', '65+')),
    sex                 text check (sex in ('female', 'male', 'unspecified')),
    citizen_phone       text,             -- E.164; only for public / ussd holds
    dispatcher_user_id  uuid,
    agency_id           uuid references agencies (id),
    origin_lat          double precision,
    origin_lng          double precision,
    eta_minutes         integer,
    route_chain_id      uuid,             -- first hold in a decline → re-route chain
    previous_hold_id    uuid references holds (id),
    decline_reason      text,
    expires_at          timestamptz not null,
    created_at          timestamptz not null default now(),
    accepted_at         timestamptz,
    arrived_at          timestamptz,
    closed_at           timestamptz
);

create index holds_active_ward_idx on holds (ward_id) where status in ('held', 'accepted');
create index holds_hospital_created_idx on holds (hospital_id, created_at desc);
create index holds_agency_created_idx on holds (agency_id, created_at desc);
create index holds_chain_idx on holds (route_chain_id);
-- One active hold per citizen phone number — stops one person (or a script)
-- from draining a hospital's beds.
create unique index holds_one_active_per_phone_idx
    on holds (citizen_phone)
    where status in ('held', 'accepted') and citizen_phone is not null;

-- ---------------------------------------------------------------- hospital API keys

create table api_keys (
    id            uuid primary key default gen_random_uuid(),
    hospital_id   uuid not null references hospitals (id) on delete cascade,
    label         text not null,
    prefix        text not null unique,   -- public part, shown in the portal
    key_hash      text not null,          -- HMAC-SHA256 of the full key; key itself is never stored
    scopes        text[] not null,
    created_by    uuid,
    created_at    timestamptz not null default now(),
    last_used_at  timestamptz,
    revoked_at    timestamptz
);

-- ---------------------------------------------------------------- citizen phone OTP

create table otp_codes (
    id           uuid primary key default gen_random_uuid(),
    phone        text not null,
    code_hash    text not null,
    attempts     integer not null default 0,
    expires_at   timestamptz not null,
    consumed_at  timestamptz,
    created_at   timestamptz not null default now()
);

create index otp_codes_phone_created_idx on otp_codes (phone, created_at desc);

-- ---------------------------------------------------------------- outbound SMS (transactional outbox)

create table sms_outbox (
    id            uuid primary key default gen_random_uuid(),
    to_phone      text not null,
    body          text not null,
    purpose       text not null,          -- 'otp' | 'hold_citizen' | 'hold_hospital' | ...
    status        text not null default 'queued' check (status in ('queued', 'sent', 'failed')),
    provider_ref  text,
    error         text,
    created_at    timestamptz not null default now(),
    sent_at       timestamptz
);

create index sms_outbox_queued_idx on sms_outbox (created_at) where status = 'queued';

-- ---------------------------------------------------------------- audit log

create table audit_log (
    id          bigint generated always as identity primary key,
    actor       text not null,            -- 'user:<uuid>' | 'citizen:<phone>' | 'api_key:<prefix>' | 'system'
    action      text not null,
    entity      text not null,
    entity_id   text,
    details     jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index audit_log_entity_idx on audit_log (entity, entity_id);

-- ---------------------------------------------------------------- lock down direct access

alter table hospitals         enable row level security;
alter table wards             enable row level security;
alter table on_call_contacts  enable row level security;
alter table agencies          enable row level security;
alter table staff             enable row level security;
alter table memberships       enable row level security;
alter table holds             enable row level security;
alter table api_keys          enable row level security;
alter table otp_codes         enable row level security;
alter table sms_outbox        enable row level security;
alter table audit_log         enable row level security;
