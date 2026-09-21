# Architecture

## Deployment

This system runs entirely on GitHub Actions — no Docker, no Render, no Hugging Face Spaces. The single unified runner is `Xtley001/brain-alpha-pipeline`.

## Unified Pipeline

All discovery, optimization, and submission runs on `Xtley001/brain-alpha-pipeline` via GitHub Actions with a shared Neon PostgreSQL database.

| Runner | Role | Schedule | Strategies |
|---|---|---|---|
| `Xtley001` — Discovery | Alpha generation & optimization | Every 30 min (48×/day) | All 15 strategies, rotating |
| `Xtley001` — Drip | Paced submissions | 3×/day | Submits top orthogonal qualified alphas |
| `Xtley001` — Health/Digest | Telemetry & monitoring | Hourly / midnight UTC | Funnel metrics & Telegram alerts |

## Strategy Packages

15 modular sub-systems in `brain_options/strategies/`, each with its own fields, generator templates, and strategy-scoped RL weights:

| # | Package | Domain |
|---|---|---|
| 1 | `term_structure` | VRP, IV vs HV, 30d/90d term structure curvature |
| 2 | `skew` | 25-delta vs 50-delta smirk steepness |
| 3 | `pcr_flow` | Put-call volume & open interest flow surges |
| 4 | `breakeven` | Call breakeven hurdle repricing vs realized vol |
| 5 | `forward_basis` | Synthetic forward basis parity spreads |
| 6 | `extreme_tail_risk` | OTM put jump-diffusion disaster pricing |
| 7 | `iv_lead_lag` | IV innovations leading cash equity returns |
| 8 | `short_interest` | Borrow fee spikes, utilization, squeeze pressure |
| 9 | `informed_short_demand` | Demand shifts vs lender supply friction |
| 10 | `analyst_revisions` | Consensus EPS/revenue drift, forecast dispersion, PEAD |
| 11 | `accruals_cashflow` | Sloan accrual anomaly & operating cash flow divergence |
| 12 | `supply_chain` | Supplier shock propagation to downstream customers |
| 13 | `network_momentum` | Cluster centroid lead-lag & co-movement momentum |
| 14 | `formulaic_101` | Kakushadze canonical price-volume cross-sectional alphas |
| 15 | `hybrid_confluence` | Skew × borrow fee × analyst revision multi-factor |

## Pipeline Stages

Each GitHub Actions batch job runs the following stages in order:

1. `record_org_run()` — write heartbeat to `org_runs` table
2. `--retry-stage0` — re-optimize older Stage 0 passers
3. `--single-batch` — generate → Stage 0 screen → optimize → correlate → archive
   - `ASTDeduplicator` seeded from all archive tables on startup
   - Stage 0 fast screen (Sharpe ≥ 0.35, Fitness ≥ 0.20)
   - `DiagnosticAlphaOptimizer` — up to 6 rounds, returns best-seen metrics
   - Correlation gate (max_corr < 0.70 vs SUBMITTED + QUALIFIED portfolio)
   - Archive to `options_alphas` as `QUALIFIED`
4. `send_telegram_batch_summary()` — fires on any qualified result
5. Zero-qualified tripwire — warning log if `today_evaluated ≥ 30` and `today_qualified = 0`

## Workflows

| File | Trigger | Purpose |
|---|---|---|
| `run.yml` | Cron 48×/day + manual | Discovery & multi-strategy optimization |
| `drip.yml` | Cron 3×/day + manual | Submit qualified alphas to BRAIN |
| `health.yml` | Cron hourly at `:00` | Telegram health check |
| `daily_digest.yml` | Cron 23:30 UTC daily | End-of-day Telegram digest |
| `status.yml` | Manual dispatch | System status report |

## Database

9 tables on Neon PostgreSQL:

| Table | Purpose |
|---|---|
| `options_alphas` | Qualified alpha pool + submission status |
| `options_evaluations` | Full evaluation log (every Stage 0 simulation) |
| `options_strategy_rl_state` | Strategy-scoped RL operator weights |
| `options_learning_memory` | Global operator reward memory |
| `options_rejected_alphas` | Checklist-failed alphas (unique on alpha_id) |
| `options_correlated_alphas` | Correlation-rejected alphas (unique on alpha_id) |
| `cluster_session_cache` | Shared BRAIN session token (TTL-enforced) |
| `cluster_run_lock` | Mutex ensuring serialized simulations |
| `org_runs` | Runner heartbeat & telemetry log |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FILTER_MIN_SHARPE` | `1.25` | Qualification threshold |
| `FILTER_MIN_FITNESS` | `1.00` | Qualification threshold |
| `FILTER_MAX_TURNOVER` | `0.70` | Max turnover to qualify |
| `MAX_CANDIDATES_PER_RUN` | `20` | Batch size |
| `RUN_TIME_BUDGET_SECONDS` | `820` | Hard time limit per batch |
| `NOTIFY_EVERY_BATCH` | `true` | Always send Telegram after every batch |
| `ENABLE_AUTO_SUBMIT` | `false` | Auto-submit to BRAIN (drip handles submissions) |

## Module Layout

```
brain_options/
├── config.py                   # OptionsConfig — env vars to typed config
├── run.py                      # Entry point: --single-batch, --retry-stage0, --health, --status
├── core/
│   ├── client.py               # BrainClient — BRAIN API: login, simulate, submit
│   ├── filter.py               # evaluate_alpha_metrics() quality gate
│   ├── notifier.py             # Telegram notifications: batch, health, drip, digest, emergency
│   ├── optimizer.py            # DiagnosticAlphaOptimizer — RL multi-arm bandit
│   └── drip.py                 # DripSubmitter — paced submission of qualified alphas
├── specialist/
│   ├── generator.py            # OptionsGenerator — LLM + template + MAB
│   └── templates.py            # OptionCandidate dataclass + seed expressions
├── store/
│   ├── db.py                   # OptionsDatabase — all SQL: schema, migrations, queries
│   └── store.py                # OptionsStore — high-level wrapper around OptionsDatabase
└── strategies/
    └── <strategy_name>/        # 15 isolated strategy packages
        ├── __init__.py
        ├── fields.py
        ├── strategy.py
        └── README.md
scripts/
├── verify_brain_parsing.py     # Validates BRAIN API response parsing against live account
tests/
├── test_filter.py              # Unit tests for quality gate
├── test_optimizer.py           # Unit tests for optimizer transformation operators
├── test_notifier.py            # Unit tests for Telegram notifier resilience
└── test_strategies_modular.py  # Validates all 15 strategy modules
```
