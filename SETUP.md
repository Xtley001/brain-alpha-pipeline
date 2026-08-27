# Setup

## 1. Prerequisites

- Python 3.11+
- A Postgres database (this project targets Neon)
- A WorldQuant BRAIN account
- A Groq API key (used by the LLM generator; free tier, no card required),
  and optionally an OpenRouter key for a free-tier fallback
- A Telegram bot token + chat ID (used for candidate alerts and the heartbeat)

## 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with real values. It is gitignored and must never be committed —
in production (GitHub Actions), set these as repository secrets instead (see
step 6 below), never as plain values in a workflow file.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `BRAIN_USERNAME` / `BRAIN_PASSWORD` | WorldQuant BRAIN login |
| `BRAIN_MAX_CONCURRENT_SIMS` | Hard cap on simultaneous BRAIN simulations -- now a real, global ceiling shared across every in-flight candidate's sweep (see README's concurrency section), not a per-candidate bound |
| `GROQ_API_KEY_1` … `_4` | Up to 4 separate accounts/emails. Groq keys, rotated on rate limit -- primary provider in the chain |
| `CEREBRAS_API_KEY_1` … `_4` | Optional, up to 4 accounts. Cerebras free tier (~1M tokens/day, no card, resets daily) -- second full provider in the chain, not a fallback. One key is normally plenty for this pipeline's call volume |
| `OPENROUTER_API_KEY_1` … `_4` | Optional, up to 4 separate accounts/emails. OpenRouter free `:free`-tier, third leg of the chain. Free tier is request-capped per account (20/min, 50/day), so each additional account adds ~50/day of headroom — the 20/min cap doesn't rise no matter how many accounts you add |
| `GEMINI_API_KEY_1` / `GEMINI_API_KEY_2` | Not currently read by `build_worker()` (GCP billing gates Gemini's quota to 0 the moment an invoice lapses). Leave unset; still wired in `pipeline/llm/adapter.py` if you want to re-enable it later |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Where candidate-passed alerts, operational alerts, and the per-tick heartbeat are sent |
| `QUEUE_TARGET_DEPTH` | Candidates the generation step tries to keep queued |
| `TEMPLATE_TIER_MAX_SHARE` | Max fraction (0-1, default `0.5`) of a tick's queue-top-up gap the template tier is allowed to fill on its own. Guarantees the LLM reasoning/mechanical tiers actually get called every tick that needs topping up, instead of the ~53-expression template pool silently covering the whole gap and starving them out |
| `MAX_CANDIDATES_PER_RUN` / `RUN_TIME_BUDGET_SECONDS` | Bounded-batch tuning for one `run_once()` invocation |
| `STAGE0_MIN_FITNESS` / `STAGE0_MIN_SHARPE` | Quick-screen thresholds |
| `FILTER_MIN_SHARPE` / `FILTER_MIN_FITNESS` / `FILTER_MAX_TURNOVER` / `FILTER_MIN_TURNOVER` | Local filter thresholds after the sweep |

A missing required variable fails loudly at startup (`MissingConfigError`),
not partway through a run. A BRAIN authentication failure at startup
(`BrainAuthError`) is handled separately -- see step 7 below.

There is no separate env var for the candidate-level retry cap
(`MAX_CANDIDATE_ATTEMPTS`, currently 3) -- it's a fixed constant in
`pipeline/run_worker.py` rather than a tunable knob, since it isn't the kind of
value that needs per-deployment adjustment.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Migrate the database

```bash
python -c "from pipeline.db.repo import Repo; from pipeline.config import Config; Repo(Config.from_env().database_url).migrate()"
```

Update 10 Item 6: this now runs `alembic upgrade head` (via Alembic's
Python API, invoked from inside `Repo.migrate()`) instead of re-executing
`pipeline/db/schema.sql` directly. Migrations live under
`pipeline/db/alembic/versions/`; the current single baseline migration
(`93b626538c0e_baseline_schema.py`) reproduces `schema.sql`'s exact end
state -- verified by diffing `pg_dump --schema-only` output between a DB
migrated via Alembic and a DB migrated via the old schema.sql execution
(see the Update 10 report). `schema.sql` itself is kept in the repo only
as a historical/legacy reference; nothing executes it anymore.

Automatic migration is deliberately kept in the hot path (this call
already runs at the top of every `build_worker()`, i.e. every scheduled
tick -- see `run_worker.py`), since under this scheduled-job deployment
model there is no separate "deploy step" distinct from "the next tick" to
hang a manual migration step off of. What changed is that this is now a
genuine no-op on a tick where the schema is already current (Alembic
checks one version row in `alembic_version`) instead of re-parsing and
re-executing the entire schema file every ~10 minutes forever.

To add a new migration: `alembic revision -m "description"` generates a
new file under `pipeline/db/alembic/versions/`; write the `upgrade()`/
`downgrade()` SQL by hand (this project doesn't use SQLAlchemy models, so
`--autogenerate` won't produce anything useful), then run
`alembic upgrade head` (with `DATABASE_URL` set, or edit `alembic.ini`)
to apply it locally before committing.

## 5. Run the tests

```bash
PYTHONPATH=. pytest tests/ -v
```

All tests run against in-memory fakes — no live BRAIN, Postgres, Telegram, or
LLM credentials required or contacted.

## 6. Deploy

This pipeline runs on a scheduled GitHub Actions job (`.github/workflows/run.yml`),
not Render. An earlier `render.yaml` was removed since it had gone stale
(missing `GROQ_API_KEY_3/4`, every `CEREBRAS_API_KEY_*`/`OPENROUTER_API_KEY_*`,
and `FILTER_MIN_TURNOVER`, all `Optional` in `Config` so deploying from it
would silently under-deploy the pipeline with no error) and `run.yml` is the
only supported deploy target now. If Render is needed again, reconstruct the
config from `run.yml`'s env var list rather than resurrecting the stale file
from history.

1. Push this repo to GitHub as a **public** repo (GitHub Actions minutes are
   free on public repos, unlike private ones).
2. In **Settings -> Secrets and variables -> Actions -> New repository secret**,
   add every secret `run.yml` references: `DATABASE_URL`, `BRAIN_USERNAME`,
   `BRAIN_PASSWORD`, `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GROQ_API_KEY_1`,
   `GROQ_API_KEY_2`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
3. Confirm the Actions tab shows both `BRAIN Alpha Pipeline` and `Keepalive` as
   enabled workflows after your first push.
4. Run `BRAIN Alpha Pipeline` once manually (`workflow_dispatch`) before
   waiting on the schedule, so a config mistake surfaces as a fast, visible
   failed run instead of a silent gap.
5. **Enable GitHub's native Actions-failure email notifications** (Settings ->
   Notifications -> Actions in your GitHub account settings). This costs
   nothing, needs no code change, and is the one channel that still reaches
   you if Telegram, the database, and BRAIN are all down at the same time --
   see step 7 below for why that scenario specifically needs a backup
   channel.
6. **Known limitation, read this: the keepalive workflow has no external
   watchdog of its own (Update 10 Item 9.3).** `keepalive.yml` exists so
   GitHub doesn't auto-disable `run.yml`'s schedule after 60 days of repo
   inactivity -- but `keepalive.yml` is itself a dead-man's-switch, and
   nothing watches *it*. If GitHub Actions' scheduler silently stops
   firing either workflow, or the repo gets disabled for some unrelated
   reason, nothing inside this repo can notice -- the thing that would
   notice is the thing that went dark. Step 5 above (email on failure)
   does not cover this either: it only fires when a workflow actually
   runs and fails, not when a workflow simply never gets triggered.

   The actual fix requires a watchdog that lives somewhere else entirely:
   a third-party heartbeat-monitoring service (e.g.
   [healthchecks.io](https://healthchecks.io) -- free tier is enough for
   one check on a 10-minute schedule) that alerts you when it does **not**
   receive an expected ping within a time window, rather than one you
   ping to ask "are you up". `run_worker.py`'s `RunReporter` already
   supports this (`send_healthcheck_ping()`, wired into `run_once()`'s
   last step) -- it's just optional and unset by default, since it needs
   an account this codebase can't create for you:

   1. Create a free check at your chosen service, with the expected
      period set a bit above your cron interval (e.g. 15 minutes for a
      10-minute schedule, to allow for a slow tick without false-alarming).
   2. Set the check's own alert channel (email, Telegram, whatever the
      service supports) -- this is the part that's genuinely independent
      of GitHub Actions' own availability.
   3. Add the check's ping URL as the `HEALTHCHECK_PING_URL` repository
      secret (see `.github/workflows/run.yml`'s env block).

   Until this is set up, treat the keepalive/schedule mechanism as exactly
   what it is: a dead-man's-switch with no one watching the watcher.

## 7. Before going live

This pipeline never calls a BRAIN submit/create-alpha endpoint — it only
simulates and alerts. A human always reviews the Telegram alert and submits
manually in BRAIN's UI. Still, confirm the following against real, live
infrastructure before trusting it unattended:

1. **MANDATORY, BLOCKING: verify BRAIN response parsing against your real
   account before trusting ANY pipeline output — do this first, not as an
   optional diagnostic.**
   `pipeline/brain/client.py`'s `_parse_sim_response`/`_parse_pnl_response` use
   soft key-lookup fallbacks that do not raise on a schema mismatch -- a
   genuinely good candidate could silently score `sharpe=0.0` and get rejected
   if BRAIN's real response shape doesn't match what's assumed. **This has
   still not been verified against a live account as of Update 10** -- Update
   10 Item 8 added loud (ERROR-level) log warnings the first time a missing
   key is observed at runtime (see `_warn_missing_key_once` in
   `pipeline/brain/client.py`), so a schema mismatch in production now leaves
   a visible trace instead of being silently indistinguishable from a real
   rejection -- but that is a safety net, not a substitute for actually
   running this check. Run:

   ```bash
   export BRAIN_USERNAME=... BRAIN_PASSWORD=...
   PYTHONPATH=. python scripts/verify_brain_parsing.py
   ```

   and compare the printed raw JSON against BRAIN's own dashboard for the same
   simulation, for at least 3 test expressions across a range of quality (one
   obviously bad, one mediocre, one you already know clears BRAIN's bar). See
   the script's own docstring for details, and the warning comment at the top
   of `pipeline/brain/client.py`. Treat every historical row in `sweep_runs`/
   `review_store` as unverified until this has been run once, by a human,
   against a real account.
2. Confirm all tables, indexes, and foreign keys exist after migration
   (`\dt`, `\di`, `\d+ <table>` in `psql`), including the newer
   `run_history` table and the `attempts`/`last_error`/`error_text` columns.
3. **BRAIN-auth-failure alerting.** Deliberately break `BRAIN_PASSWORD` for one
   test run and confirm you receive a Telegram alert (via the
   `_best_effort_startup_alert` path in `run_worker.py`) rather than just a
   failed Actions run with no message -- this used to be a silent gap.
4. Let it run for a few real ticks and check the heartbeat messages / the
   `run_history` table for BRAIN slot utilization, queue depth, and the
   per-stage rejection breakdown over time.
5. Send one real Telegram message and confirm the candidate-alert settings
   block is genuinely paste-able into BRAIN's UI, and that the heartbeat
   message is visually distinct from both the candidate alert and operational
   alerts.
6. Before pushing to any remote, confirm `.env` was never staged in an
   earlier local commit.
