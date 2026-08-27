# Setup

## 1. Prerequisites

- Python 3.11+
- A Postgres database (this project targets Neon)
- A WorldQuant BRAIN account
- A Groq API key (free tier, no card required) — primary LLM provider
- Optional: Cerebras and/or OpenRouter API keys for additional LLM fallback
- A Telegram bot token + chat ID (for alerts and heartbeat)

## 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with real values. It is gitignored and must never be
committed — in production, set these as GitHub Actions repository secrets
instead (step 6).

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `BRAIN_USERNAME` / `BRAIN_PASSWORD` | WorldQuant BRAIN login |
| `BRAIN_MAX_CONCURRENT_SIMS` | Global cap on simultaneous BRAIN simulations |
| `GROQ_API_KEY_1` … `_4` | Up to 4 accounts, rotated on rate limit — primary LLM provider |
| `CEREBRAS_API_KEY_1` … `_4` | Optional. Second LLM provider in the fallback chain |
| `OPENROUTER_API_KEY_1` … `_4` | Optional. Third LLM provider in the fallback chain |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Where alerts and the heartbeat are sent |
| `QUEUE_TARGET_DEPTH` | Candidates the generator tries to keep queued |
| `TEMPLATE_TIER_MAX_SHARE` | Max fraction of a tick's queue gap the template tier may fill alone (default `0.5`) |
| `MAX_CANDIDATES_PER_RUN` / `RUN_TIME_BUDGET_SECONDS` | Bounded-batch tuning per tick |
| `STAGE0_MIN_FITNESS` / `STAGE0_MIN_SHARPE` | Quick-screen thresholds |
| `FILTER_MIN_SHARPE` / `FILTER_MIN_FITNESS` / `FILTER_MAX_TURNOVER` / `FILTER_MIN_TURNOVER` | Local filter thresholds after the sweep |

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for what each stage
does with these values.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Migrate the database

```bash
python -c "from pipeline.db.repo import Repo; from pipeline.config import Config; Repo(Config.from_env().database_url).migrate()"
```

Runs `alembic upgrade head` and is a no-op if the schema is already
current. To add a new migration:

```bash
alembic revision -m "description"
# hand-write upgrade()/downgrade() in the generated file, then:
alembic upgrade head
```

## 5. Run the tests

```bash
PYTHONPATH=. pytest tests/ -v
```

## 6. Deploy

This pipeline runs on a scheduled GitHub Actions job
(`.github/workflows/run.yml`).

1. Push this repo to GitHub as a **public** repo (Actions minutes are free
   on public repos).
2. Add every secret `run.yml` references under **Settings → Secrets and
   variables → Actions**.
3. Confirm the Actions tab shows `BRAIN Alpha Pipeline` and `Keepalive` as
   enabled workflows.
4. Run `BRAIN Alpha Pipeline` once manually (`workflow_dispatch`) before
   waiting on the schedule, so a config mistake surfaces immediately.
5. Enable GitHub's native Actions-failure email notifications
   (account **Settings → Notifications → Actions**) as a backup channel
   independent of Telegram/DB/BRAIN.
6. Optional but recommended: point `run_worker.py`'s built-in
   `send_healthcheck_ping()` at a free dead-man's-switch service (e.g.
   [healthchecks.io](https://healthchecks.io)) via the
   `HEALTHCHECK_PING_URL` secret, so you're alerted if the scheduler ever
   stops firing entirely — a failure email only fires on a run that
   actually happens and fails.

## 7. Before going live

1. **Verify BRAIN response parsing against your real account first.**
   `pipeline/brain/client.py`'s parsers use soft key-lookup fallbacks that
   don't raise on a schema mismatch — an untested account could silently
   score a good candidate as `sharpe=0.0`. Run:

   ```bash
   export BRAIN_USERNAME=... BRAIN_PASSWORD=...
   PYTHONPATH=. python scripts/verify_brain_parsing.py
   ```

   and compare the printed output against BRAIN's dashboard for the same
   simulation, across a few test expressions of varying quality.
2. Confirm all tables/indexes exist after migration (`\dt`, `\di`,
   `\d+ <table>` in `psql`).
3. Deliberately break `BRAIN_PASSWORD` for one test run and confirm you
   receive a Telegram alert rather than a silent failed Actions run.
4. Let it run a few real ticks and check the heartbeat / `run_history`
   table for queue depth and per-stage rejection breakdown.
5. Send one real Telegram alert and confirm the settings block is
   paste-able directly into BRAIN's UI.
6. Confirm `.env` was never committed in any earlier local commit.
