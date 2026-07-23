# BedAlert Pilot Plan — Web App + SMS/USSD

**Scope:** Given time before final submission, we're piloting two of BedAlert's
three tiers: the web dashboard (public + dispatcher + admin) and the SMS/USSD
simulator. The hospital API tier is demonstrated but not separately piloted —
it's the shared data layer underneath both.

**Goal:** Show real users completing real tasks, and capture data GCL judges
can see as evidence of validation (not just a working prototype).

---

## 1. Recruit testers (aim for 6–10 people)

Mix of:
- 2–3 teammates (acting as "hospital admin" / "dispatcher")
- 3–5 people outside the team — classmates, family, GCL networking contacts —
  playing "member of the public"
- If possible, 1–2 people with low smartphone/data literacy, to specifically
  stress-test whether the USSD flow is usable without assumptions

## 2. Give each tester a task, not a tour

Don't demo it to them first — hand them a task and watch. This is what makes
it a pilot rather than a demo.

**Public web app tester tasks:**
- "Your relative has chest pain. Find a hospital with an ER bed near [city] and book it."
- "Find a stable-case bed for a routine referral and book one."

**Dispatcher console tester tasks:**
- "A critical patient just came in from [location]. Dispatch them to the
  nearest hospital with capacity."

**Hospital admin tester tasks:**
- "A bed just opened up in General. Update the count and check who's on call."
- "Register a new hospital joining the network."

**SMS/USSD tester tasks:**
- "Using only this phone screen — no explanation from us — report an
  emergency and get booked into a hospital." (This is the most important one:
  it tests the zero-literacy design goal directly.)

## 3. Capture data while they work

For each tester, log:

| Metric | How to capture |
|---|---|
| Task completion (yes/no) | Did they finish without your help? |
| Time to complete | Stopwatch from task start to confirmation screen |
| Number of wrong turns / confusion points | Note where they hesitated or asked "what do I do here?" |
| Would they trust this in a real emergency? (1–5) | Ask directly after |
| One thing that confused them | Open-ended, write verbatim if possible |

A simple shared spreadsheet (Google Sheets) with one row per tester works
fine — don't over-engineer this part.

## 4. Turn results into your defense evidence

For Demo Day / defense, you want 3 numbers and 1 quote, not a data dump:
- **X out of Y testers completed the emergency booking without help**
- **Average time to book: X minutes** (compare to "hours of phone calls" in
  your research report)
- **Average trust score: X/5**
- One direct quote from a tester, especially from the USSD test — this is
  your strongest SDG 10 (equity) evidence

## 5. Timeline (submission July 26, Demo Day July 30)

| When | What |
|---|---|
| Day 1 (today–tomorrow) | Deploy web app + backend live (see DEPLOYMENT.md), recruit testers |
| Day 2 | Run all pilot sessions, log data |
| Day 3 | Summarize results into 1 slide + 1 paragraph for submission |
| Before Demo Day | Rehearse a live 2-minute walkthrough using the deployed URL, not localhost |

---

## What "pilot" does NOT need to be

You do not need real hospitals, real patient data, or a live telco SMS
integration to call this a pilot. Judges are assessing whether you validated
the *user experience* and *core assumption* (that people, including
low-literacy/no-internet users, can get routed to an available bed faster
this way) — not whether you have production infrastructure yet.
