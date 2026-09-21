# Architecture

## Deployment

This system runs **entirely on GitHub Actions** - there is no Render, HuggingFace Spaces,
or Docker deployment. The Dockerfile, render.yaml, and app.py previously in the repo
have been deleted as dead code.

## Single Unified Pipeline Architecture

The entire pipeline runs on **Xtley001/brain-alpha-pipeline** using GitHub Actions with a unified Neon PostgreSQL database. All previous secondary worker orgs have been decommissioned and consolidated.

### Unified Scheduling & Dispatch

| Runner | Role | Schedule | Strategies Handled |
|---|---|---|---|
| `Xtley001` (Unified) | Discovery & Optimization | Every 30 min (48x/day) | All 8 modular strategies (rotating) |
| `Xtley001` (Drip Submitter) | Paced Submissions | 3x/day | Submits top orthogonal qualified alphas |
| `Xtley001` (Health / Digest) | Telemetry & Monitoring | Hourly / Midnight UTC | Funnel metrics, reserve status & Telegram alerts |

### Modular Strategy Sub-Systems (`brain_options/strategies/`)

Each strategy family is isolated in its own sub-system package with dedicated fields, templates, generator logic, and strategy-scoped RL weights:
1. `term_structure` (VRP, IV vs HV, 30d/90d term structure curvature)
2. `skew` (25-delta vs 50-delta skew, Put-Call IV smirk steepness)
3. `pcr_flow` (Put-Call Volume & Open Interest flow surges)
4. `breakeven` (Call Breakeven Hurdle Repricing vs Realized Vol)
5. `forward_basis` (Synthetic Forward Basis Parity Spreads)
6. `short_interest` (Borrow Fee Spikes, Utilization, Squeeze Pressure)
7. `analyst_revisions` (Consensus EPS/Revenue Drift, Forecast Dispersion, PEAD)
8. `hybrid_confluence` (Cross-Asset Options Skew x Borrow Fee x Analyst Drift)

## Pipeline Stages

For each batch run (one GitHub Actions job):
  1. `record_org_run()` - write heartbeat to `org_runs` table
  2. `--retry-stage0`   - re-optimize older Stage 0 passers
  3. `--single-batch`   - generate, Stage 0 screen, optimize, correlate, archive
     - `ASTDeduplicator` (seeded from all archive tables on startup)
     - Stage 0 fast screen (Sharpe >= 0.35, Fitness >= 0.20)
     - `DiagnosticAlphaOptimizer` (max 6 rounds, returns best-seen metrics)
     - Correlation gate (max_corr < 0.70 vs SUBMITTED+QUALIFIED portfolio)
     - archive to `options_alphas` (QUALIFIED)
  4. `send_telegram_batch_summary()` - always fires (grey circle for 0-pass, green check for qualifiers)
  5. Zero-qualified tripwire - red alert if today_evaluated >= 30 and today_qualified = 0

## Workflows

| File | Runs on | Trigger | Purpose |
|---|---|---|---|
| `run.yml` | `Xtley001` | Cron 48x/day + manual dispatch | Discovery & multi-strategy optimization |
| `drip.yml` | `Xtley001` | Cron 3x/day + manual | Submit qualified alphas to BRAIN |
| `health.yml` | `Xtley001` | Cron every hour at :04 | Hourly Telegram health check |
| `status.yml` | `Xtley001` | On-demand / scheduled | System status report |
| `daily_digest.yml` | `Xtley001` | Cron 23:30 UTC daily | End-of-day Telegram digest |

## Database Tables (Neon Postgres)

| Table | Purpose |
|---|---|
| `options_alphas` | Qualified alpha pool + submission status |
| `options_evaluations` | Full evaluation log (every Stage 0 sim) |
| `options_strategy_rl_state` | Strategy-scoped reinforcement learning operator weights |
| `options_learning_memory` | Global operator reward memory |
| `options_rejected_alphas` | Checklist-failed alphas (UNIQUE on alpha_id) |
| `options_correlated_alphas` | Correlation-rejected alphas (UNIQUE on alpha_id) |
| `cluster_session_cache` | Shared BRAIN session token (TTL-enforced, 10-min margin) |
| `cluster_run_lock` | Mutex ensuring clean serialized simulations |
| `org_runs` | Heartbeat log for runner telemetry |

## Key Config Env Vars

| Variable | Default | Purpose |
|---|---|---|
| FILTER_MIN_SHARPE | 1.25 | Qualification threshold |
| FILTER_MIN_FITNESS | 1.00 | Qualification threshold |
| FILTER_MAX_TURNOVER | 0.70 | Max turnover to qualify |
| MAX_CANDIDATES_PER_RUN | 20 | Batch size |
| RUN_TIME_BUDGET_SECONDS | 820 | Hard time limit per batch |
| NOTIFY_EVERY_BATCH | true | Always send Telegram after every batch |
| ENABLE_AUTO_SUBMIT | false | Auto-submit to BRAIN (drip handles manually) |

## Module Layout

brain_options/
  config.py             - OptionsConfig (env vars to typed config)
  run.py                - Main entry point: --single-batch, --retry-stage0, --health, --status
  core/
    client.py           - BrainClient (BRAIN API: login, simulate, submit)
    filter.py           - evaluate_alpha_metrics() quality gate
    notifier.py         - Telegram notifications (batch, health, drip, digest, emergency)
    optimizer.py        - DiagnosticAlphaOptimizer (RL multi-arm bandit)
    drip.py             - DripSubmitter (paced submission of qualified alphas)
  specialist/
    generator.py        - OptionsGenerator (LLM + template + MAB)
    templates.py        - OptionCandidate dataclass + seed expressions
  store/
    db.py               - OptionsDatabase (all SQL: schema, migrations, queries)
    store.py            - OptionsStore (high-level wrapper around OptionsDatabase)
scripts/
  org_manager.py        - CLI tool for syncing secrets across worker orgs
  verify_brain_parsing.py - Validates BRAIN API response parsing against live account
tests/
  test_filter.py        - Unit tests for quality gate
  test_optimizer.py     - Unit tests for optimizer transformation operators
