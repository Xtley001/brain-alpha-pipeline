# Architecture

## Deployment

This system runs **entirely on GitHub Actions** - there is no Render, HuggingFace Spaces,
or Docker deployment. The Dockerfile, render.yaml, and app.py previously in the repo
have been deleted as dead code.

## Org Structure

| Org | Role | Cron | Archetype |
|---|---|---|---|
| Xtley001 (primary) | Drip submitter, health check, status | Various | N/A - no discovery |
| xtley-alpha-research-01 | Worker | Every 2h at :07 | breakeven, skew |
| xtley-alpha-research-02 | Worker | Every 2h at :37 | analyst_revisions |
| xtley-alpha-research-03 | Worker | Odd hours at :07 | short_interest |
| xtley-alpha-research-04 | Worker | Odd hours at :37 | hybrid_confluence, term_structure, pcr_flow |

All 5 orgs share one Neon Postgres database and one BRAIN researcher account session,
cached in the cluster_session_cache table.

## Pipeline Stages

For each batch run (one GitHub Actions job):
  1. record_org_run() - write heartbeat to org_runs table
  2. --retry-stage0   - re-optimize older Stage 0 passers
  3. --single-batch   - generate, Stage 0 screen, optimize, correlate, archive
     - ASTDeduplicator (seeded from all 4 archive tables on startup)
     - Stage 0 fast screen (Sharpe >= 0.35, Fitness >= 0.20)
     - DiagnosticAlphaOptimizer (max 6 rounds, returns best-seen metrics)
     - Correlation gate (max_corr < 0.70 vs SUBMITTED+QUALIFIED portfolio)
     - archive to options_alphas (QUALIFIED)
  4. send_telegram_batch_summary() - always fires (grey circle for 0-pass, green check for qualifiers)
  5. Zero-qualified tripwire - red alert if today_evaluated >= 30 and today_qualified = 0

## Workflows

| File | Runs on | Trigger | Purpose |
|---|---|---|---|
| run.yml | Worker orgs only | Cron 48x/day + manual | Discovery pipeline |
| drip.yml | Xtley001 only | Cron 5x/day + manual | Submit qualified alphas to BRAIN |
| health.yml | Xtley001 only | Cron every hour at :04 | Hourly Telegram health check |
| status.yml | Xtley001 only | Cron 07:00 UTC daily + manual | Morning status report |
| daily_digest.yml | Xtley001 only | Cron 23:30 UTC daily | End-of-day Telegram digest |

## Database Tables (Neon Postgres)

| Table | Purpose |
|---|---|
| options_alphas | Qualified alpha pool + submission status |
| options_evaluations | Full evaluation log (every Stage 0 sim) |
| options_learning_memory | MAB reward memory for generation |
| options_rejected_alphas | Checklist-failed alphas (UNIQUE on alpha_id) |
| options_correlated_alphas | Correlation-rejected alphas (UNIQUE on alpha_id) |
| cluster_session_cache | Shared BRAIN session token (TTL-enforced, 10-min margin) |
| cluster_run_lock | Cluster-wide mutex (one org simulating at a time) |
| org_runs | Per-org run heartbeat for multi-org activity monitoring |

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
