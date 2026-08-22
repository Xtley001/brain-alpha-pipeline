# Update: moving the deploy target from Render to GitHub Actions

This lists everything that changed (or needs to change) to run this pipeline
on GitHub Actions instead of Render, entirely free, in a public repo. Read
`SETUP.md` alongside this for the day-to-day operating steps; this file is
just the "what changed and why" record.

## The good news first

`pipeline/run_worker.py` was already refactored into a **bounded batch job**
(`run_once()`: reclaim orphans -> top up queue once -> process a bounded
batch -> exit). That refactor was done for Render Cron Job's pricing, but it
happens to be exactly the shape GitHub Actions' `schedule:` trigger needs
too. **No changes to any file under `pipeline/` were required.** State
persistence works the same way it always did: everything durable lives in
Postgres (`DATABASE_URL`), not on the runner's disk, and the runner is
thrown away after every run either way (Render's ephemeral cron dyno vs.
GitHub's ephemeral Actions VM -- same constraint, already handled).

## What was actually added

1. **`.github/workflows/run.yml`** (new) -- the replacement for
   `render.yaml`. Triggers on `schedule: "*/10 * * * *"` (same cadence) plus
   `workflow_dispatch` for manual runs. Checks out the repo, installs
   `requirements.txt`, runs `python -m pipeline.run_worker` with every env
   var `render.yaml` used to set, sourced from GitHub Actions secrets.

2. **`.github/workflows/keepalive.yml`** (new) -- see "The 60-day
   auto-disable gotcha" below. Not optional if you want this to genuinely
   run forever unattended.

3. **`concurrency:` block in `run.yml`** -- not strictly required (see
   below) but added as a second line of defense.

## What you need to do (nothing here is automatic)

- [ ] Push this repo to GitHub as a **public** repo (private repos on free
      personal GitHub plans get a monthly Actions-minutes quota; public
      repos on GitHub-hosted runners are unmetered -- see "Actually free?"
      below).
- [ ] In **Settings -> Secrets and variables -> Actions -> New repository
      secret**, add every secret `run.yml` references: `DATABASE_URL`,
      `BRAIN_USERNAME`, `BRAIN_PASSWORD`, `GEMINI_API_KEY_1`,
      `GEMINI_API_KEY_2`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`,
      `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. (Full walkthrough in the
      standalone setup guide.)
- [ ] Confirm the Actions tab shows both `BRAIN Alpha Pipeline` and
      `Keepalive` as enabled workflows after your first push.
- [ ] Run `BRAIN Alpha Pipeline` once manually (`workflow_dispatch`,
      "Run workflow" button) before waiting on the schedule, so a config
      mistake surfaces as a fast, visible failed run instead of a silent gap.
- [ ] `render.yaml` is left in the repo untouched but is now unused --
      GitHub Actions doesn't read it. Delete it or keep it as a reference
      for reverting to Render later; either is fine.

## Things that are genuinely different, not just relocated

These are real behavior changes, not paperwork -- read them before you trust
this unattended.

### The 60-day auto-disable gotcha

GitHub automatically disables a public repo's *scheduled* workflows if the
repo sees no activity for 60 days. A repo that's just quietly running a cron
job and nothing else can trip this -- the pipeline would go silent with no
error, no Telegram alert, nothing, until you noticed candidates had stopped
arriving. `keepalive.yml` makes one trivial commit a month specifically to
prevent this. If you ever remove or disable `keepalive.yml`, you've
reintroduced this risk.

### Schedule is best-effort, not guaranteed

Render's cron and GitHub Actions' `schedule:` trigger are both best-effort,
but GitHub is more openly so: at peak load (e.g. right at the top of the
hour, when a large fraction of all scheduled workflows on GitHub fire at
once), a run can be delayed by several minutes or, rarely, dropped entirely.
`*/10 * * * *` gives you six scheduled attempts an hour, so an occasional
skipped tick just means candidates sit in the queue slightly longer -- it
doesn't lose anything (the orphan-reclaim logic + `FOR UPDATE SKIP LOCKED`
claiming already assumed ticks could be missed or overlap).

### Actually free? Read this before assuming "free" means "unlimited"

Public repos on GitHub-hosted runners: workflow minutes themselves are not
metered. Where cost can still appear:
- If you ever flip the repo to private, GitHub Actions minutes are billed
  against your account's monthly free-minutes quota once exceeded.
- The compute itself is free; nothing about `DATABASE_URL` (Neon),
  `GEMINI_API_KEY_*`, `GROQ_API_KEY_*`, or Telegram becomes free just because
  the *runner* is -- confirm each of those is still within its own provider's
  free tier at whatever call volume this pipeline generates at your queue
  depth and schedule.

### Public repo means public config, not public secrets

Values pulled from `secrets.*` in `run.yml` are never printed in logs and are
not visible to anyone browsing the repo. Everything else in `run.yml` --
`BRAIN_MAX_CONCURRENT_SIMS`, `QUEUE_TARGET_DEPTH`, all the threshold values
-- is plain YAML in a public file, visible to anyone. None of that is a
credential, so this matches the project's existing "no hardcoded
credentials, everything else can be plain config" rule. Double check before
adding any *new* env var to `run.yml` that it isn't secret before writing it
as a plain value instead of `secrets.*`.

### Fork behavior

If someone forks this public repo, GitHub disables the scheduled trigger on
the fork by default (their fork won't silently start running your pipeline
against your secrets -- and it couldn't anyway, since your repo secrets
don't propagate to forks). Nothing to do here, just worth knowing so a
fork's inactive Actions tab doesn't look like a bug.
