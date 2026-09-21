# Installation & Setup

## Prerequisites

- Python 3.11+
- A Neon (or compatible) PostgreSQL database
- A WorldQuant BRAIN account
- A Groq API key (free tier, no card required) — primary LLM provider
- Optional: Cerebras and/or OpenRouter API keys for LLM fallback
- A Telegram bot token + chat ID for alerts and heartbeat

## Environment Variables

```bash
cp .env.example .env
```

Fill in `.env` with real values. It is gitignored and must never be committed — in production, set these as GitHub Actions repository secrets instead (see Deployment below).

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `BRAIN_USERNAME` / `BRAIN_PASSWORD` | WorldQuant BRAIN login |
| `BRAIN_MAX_CONCURRENT_SIMS` | Global cap on simultaneous BRAIN simulations |
| `GROQ_API_KEY_1` … `_4` | Up to 4 accounts, rotated on rate limit — primary LLM provider |
| `CEREBRAS_API_KEY_1` … `_4` | Optional. Second LLM provider in the fallback chain |
| `OPENROUTER_API_KEY_1` … `_4` | Optional. Third LLM provider in the fallback chain |
| `GEMINI_API_KEY_1` … `_4` | Optional. Final LLM fallback |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Alert destination |
| `QUEUE_TARGET_DEPTH` | Candidates the generator keeps queued |
| `TEMPLATE_TIER_MAX_SHARE` | Max fraction of queue gap the template tier may fill (default `0.5`) |
| `MAX_CANDIDATES_PER_RUN` / `RUN_TIME_BUDGET_SECONDS` | Bounded-batch tuning per tick |
| `STAGE0_MIN_FITNESS` / `STAGE0_MIN_SHARPE` | Fast-screen thresholds |
| `FILTER_MIN_SHARPE` / `FILTER_MIN_FITNESS` / `FILTER_MAX_TURNOVER` / `FILTER_MIN_TURNOVER` | Qualification thresholds |

See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) for what each stage does with these values.

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Migrate the Database

```bash
python -m brain_options.run --migrate
```

Runs schema migrations and is a no-op if already current.

## Run Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

## Deployment

This pipeline runs on scheduled GitHub Actions (`.github/workflows/run.yml`).

1. Push this repo to GitHub as a **public** repo (Actions minutes are free on public repos).
2. Add every secret `run.yml` references under **Settings → Secrets and variables → Actions**.
3. Confirm the Actions tab shows the discovery, health, drip, and digest workflows as enabled.
4. Run `BRAIN Alpha Pipeline` once manually (`workflow_dispatch`) before waiting on the schedule — surfaces config mistakes immediately.
5. Enable GitHub's native Actions-failure email notifications (**account Settings → Notifications → Actions**) as a backup channel independent of Telegram.

## Pre-Launch Checklist

1. **Verify BRAIN response parsing against your real account first.**

   ```bash
   export BRAIN_USERNAME=... BRAIN_PASSWORD=...
   PYTHONPATH=. python scripts/verify_brain_parsing.py
   ```

   Compare printed output against BRAIN's dashboard for the same simulation across a few test expressions of varying quality.

2. Confirm all tables and indexes exist after migration (`\dt`, `\di`, `\d+ <table>` in `psql`).
3. Deliberately break `BRAIN_PASSWORD` for one test run and confirm you receive a Telegram alert rather than a silent failed Actions run.
4. Let it run a few real ticks and check the heartbeat and `org_runs` table for queue depth and per-stage rejection breakdown.
5. Confirm `.env` was never committed in any earlier local commit (`git log --all --full-history -- .env`).
