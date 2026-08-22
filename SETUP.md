# Setup

## 1. Prerequisites

- Python 3.11+
- A Postgres database (this project targets Neon)
- A WorldQuant BRAIN account
- API keys for Gemini and/or Groq (used by the LLM generator)
- A Telegram bot token + chat ID (used for candidate alerts)

## 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in `.env` with real values. It is gitignored and must never be committed —
on Render, set these in the dashboard's Environment tab instead of shipping
a `.env` file.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `BRAIN_USERNAME` / `BRAIN_PASSWORD` | WorldQuant BRAIN login |
| `BRAIN_MAX_CONCURRENT_SIMS` | Hard cap on simultaneous BRAIN simulations |
| `GEMINI_API_KEY_1` / `GEMINI_API_KEY_2` | Gemini keys, rotated on rate limit |
| `GROQ_API_KEY_1` / `GROQ_API_KEY_2` | Groq keys, rotated on rate limit |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Where candidate-passed alerts are sent |
| `QUEUE_TARGET_DEPTH` | Candidates the generation loop tries to keep queued |
| `STAGE0_MIN_FITNESS` / `STAGE0_MIN_SHARPE` | Quick-screen thresholds |
| `FILTER_MIN_SHARPE` / `FILTER_MIN_FITNESS` / `FILTER_MAX_TURNOVER` / `FILTER_MIN_TURNOVER` | Local filter thresholds after the sweep |

A missing required variable fails loudly at startup (`MissingConfigError`),
not partway through a run.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Migrate the database

```bash
python -c "from pipeline.db.repo import Repo; from pipeline.config import Config; Repo(Config.from_env().database_url).migrate()"
```

This runs `pipeline/db/schema.sql` directly. Re-running it is safe — column
additions use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

## 5. Run the tests

```bash
PYTHONPATH=. pytest tests/ -v
```

45 tests, all against in-memory fakes — no live BRAIN, Postgres, Telegram, or
LLM credentials required or contacted.

## 6. Deploy

Push to a git repo, then connect it in Render. `render.yaml` provisions a
**Background Worker** (not a Cron Job — this needs to run continuously).

In Render's dashboard, set every environment variable marked `sync: false`
in `render.yaml`. None of them are in the committed file.

## 7. Before going live

This pipeline never calls a BRAIN submit/create-alpha endpoint — it only
simulates and alerts. A human always reviews the Telegram alert and submits
manually in BRAIN's UI. Still, confirm the following against real, live
infrastructure before trusting it unattended:

1. Run one real candidate through `get_alpha_pnl()` and confirm the parsed
   `{date: daily_return}` series looks sane against BRAIN's actual PnL
   schema.
2. Confirm all tables, indexes, and foreign keys exist after migration
   (`\dt`, `\di`, `\d+ <table>` in `psql`).
3. Confirm the Render service shows as `type: worker` in the dashboard
   itself, not just in the committed YAML.
4. Let it run for a few real hours and check BRAIN slot utilization and
   queue depth over time.
5. Send one real Telegram message and confirm the settings block is
   genuinely paste-able into BRAIN's UI.
6. Before pushing to any remote, confirm `.env` was never staged in an
   earlier local commit.
