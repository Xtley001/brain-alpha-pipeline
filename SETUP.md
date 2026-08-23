# Setup

## 1. Prerequisites

- Python 3.11+
- A Postgres database (this project targets Neon)
- A WorldQuant BRAIN account
- API keys for Gemini and/or Groq (used by the LLM generator)
- A Telegram bot token + chat ID (used for candidate alerts and the heartbeat)

## 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with real values. It is gitignored and must never be committed —
in production (GitHub Actions), set these as repository secrets instead (see
`UPDATE.md` and step 6 below), never as plain values in a workflow file.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `BRAIN_USERNAME` / `BRAIN_PASSWORD` | WorldQuant BRAIN login |
| `BRAIN_MAX_CONCURRENT_SIMS` | Hard cap on simultaneous BRAIN simulations -- now a real, global ceiling shared across every in-flight candidate's sweep (see README's concurrency section), not a per-candidate bound |
| `GEMINI_API_KEY_1` / `GEMINI_API_KEY_2` | Gemini keys, rotated on rate limit |
| `GROQ_API_KEY_1` / `GROQ_API_KEY_2` | Groq keys, rotated on rate limit |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Where candidate-passed alerts, operational alerts, and the per-tick heartbeat are sent |
| `QUEUE_TARGET_DEPTH` | Candidates the generation step tries to keep queued |
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

This runs `pipeline/db/schema.sql` directly. Re-running it is safe — column
additions use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. This now also creates
`run_history` (the heartbeat's queryable trend table) and adds the
`attempts`/`last_error` columns to `candidates` and the `error_text` column to
`sweep_runs` used by the fault-isolated sweep.

## 5. Run the tests

```bash
PYTHONPATH=. pytest tests/ -v
```

All tests run against in-memory fakes — no live BRAIN, Postgres, Telegram, or
LLM credentials required or contacted.

## 6. Deploy

This pipeline runs on a scheduled GitHub Actions job (`.github/workflows/run.yml`),
not Render — see `UPDATE.md` for the full migration history. `render.yaml` is
left in the repo, unused, as a reference for reverting if needed.

1. Push this repo to GitHub as a **public** repo (see `UPDATE.md`'s "Actually
   free?" section for why).
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

## 7. Before going live

This pipeline never calls a BRAIN submit/create-alpha endpoint — it only
simulates and alerts. A human always reviews the Telegram alert and submits
manually in BRAIN's UI. Still, confirm the following against real, live
infrastructure before trusting it unattended:

1. **Verify BRAIN response parsing against your real account (do this first).**
   `pipeline/brain/client.py`'s `_parse_sim_response`/`_parse_pnl_response` use
   soft key-lookup fallbacks that do not raise on a schema mismatch -- a
   genuinely good candidate could silently score `sharpe=0.0` and get rejected
   if BRAIN's real response shape doesn't match what's assumed. This has not
   been verified against a live account in this codebase's history. Run:

   ```bash
   export BRAIN_USERNAME=... BRAIN_PASSWORD=...
   PYTHONPATH=. python scripts/verify_brain_parsing.py
   ```

   and compare the printed raw JSON against BRAIN's own dashboard for the same
   simulation, for at least 3 test expressions across a range of quality (one
   obviously bad, one mediocre, one you already know clears BRAIN's bar). See
   the script's own docstring for details, and the warning comment at the top
   of `pipeline/brain/client.py`.
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
