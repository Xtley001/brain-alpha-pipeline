# brain-alpha-pipeline

Autonomous WorldQuant BRAIN alpha discovery engine — 15 institutional strategies, 48 runs/day, 3 daily submissions.

[![CI](https://img.shields.io/github/actions/workflow/status/Xtley001/brain-alpha-pipeline/run.yml?label=discovery)](https://github.com/Xtley001/brain-alpha-pipeline/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Health](https://img.shields.io/github/actions/workflow/status/Xtley001/brain-alpha-pipeline/health.yml?label=health)](https://github.com/Xtley001/brain-alpha-pipeline/actions/workflows/health.yml)

A fully serverless quantitative alpha pipeline running on GitHub Actions, backed by Neon PostgreSQL. It generates, optimizes, and submits options and equity trading signals to WorldQuant BRAIN without human intervention, 24 hours a day. For full architecture and mechanism details, see [`docs/HOW_IT_WORKS.md`](./docs/HOW_IT_WORKS.md).

## Table of Contents

- [Quickstart](#quickstart)
- [Strategies](#strategies)
- [Workflows](#workflows)
- [Telegram Notifications](#telegram-notifications)
- [Database](#database)
- [LLM Providers](#llm-providers)
- [Daily Target](#daily-target)
- [Secrets](#secrets)
- [Operations](#operations)

## Quickstart

```bash
git clone https://github.com/Xtley001/brain-alpha-pipeline.git
cd brain-alpha-pipeline
pip install -r requirements.txt
cp .env.example .env   # fill in credentials
python -m pytest tests/ -v
python -m brain_options.run --single-batch --strategy skew
```

See [`SETUP.md`](./SETUP.md) for full environment configuration and deployment steps.

## Strategies

15 modular strategy packages in `brain_options/strategies/`, each isolated with its own fields, generator, and RL weights:

| Strategy | Domain | Primary Edge | Universes |
|---|---|---|---|
| `term_structure` | Options | Variance Risk Premium & IV term inversion | `TOP1000`, `TOP3000` |
| `skew` | Options | 25-delta vs 50-delta smirk asymmetry | `TOP1000`, `TOP3000` |
| `pcr_flow` | Options | Informed put-call order flow surges | `TOP2000`, `TOP3000` |
| `breakeven` | Options | Call breakeven hurdle repricing vs realized vol | `TOP500`, `TOP1000` |
| `forward_basis` | Options | Synthetic forward parity basis spreads | `TOP2000`, `TOP3000` |
| `extreme_tail_risk` | Options | OTM put smirk jump-diffusion pricing | `TOP1000`, `TOP3000` |
| `iv_lead_lag` | Options | IV innovations leading cash equity returns | `TOP1000`, `TOP2000` |
| `short_interest` | Equity Lending | Borrow fee spikes & utilization squeeze | `TOP500`, `TOPSP500` |
| `informed_short_demand` | Equity Lending | Demand shifts vs lender supply friction | `TOP500`, `TOP1000` |
| `analyst_revisions` | Fundamental | EPS/revenue consensus drift & PEAD | `TOPSP500`, `TOP500` |
| `accruals_cashflow` | Fundamental | Sloan accrual anomaly & OCF divergence | `TOPSP500`, `TOP1000` |
| `supply_chain` | Network | Supplier shock propagation to customers | `TOP2000`, `TOP3000` |
| `network_momentum` | Network | Cluster centroid lead-lag co-movement | `TOP1000`, `TOP2000` |
| `formulaic_101` | Price/Volume | Kakushadze canonical microstructure alphas | `TOP3000` |
| `hybrid_confluence` | Multi-Factor | Skew × borrow fee × analyst revision confluence | `TOPSP500`, `TOP1000` |

## Workflows

| Workflow | Trigger | Purpose |
|---|---|---|
| [`run.yml`](.github/workflows/run.yml) | 48× daily + manual | Discover & optimize alpha candidates across all 15 strategies |
| [`drip.yml`](.github/workflows/drip.yml) | 3× daily (08:00, 14:00, 20:00 WAT) | Submit 1 qualified orthogonal alpha from reserve to BRAIN |
| [`health.yml`](.github/workflows/health.yml) | Hourly at `:00` | Telegram heartbeat with today's discovery funnel stats |
| [`daily_digest.yml`](.github/workflows/daily_digest.yml) | Daily at 23:00 UTC | End-of-day summary: simulated, qualified, submitted, reserve |
| [`status.yml`](.github/workflows/status.yml) | Manual dispatch | On-demand status report & DB stats in Actions logs |

## Telegram Notifications

All alerts are minimalist — no links, no raw formulas.

### Hourly Health

```
🟢 Hourly Health · 18:00 UTC+1

Simulated today: 142
Qualified: 3/5 ●●●○○
Submitted: 1/3 ●○○
Reserve (unsubmitted): 2
Corr-rejected today: 4

Strategy: term_structure
```

### Alpha Qualified

```
🎯 Alpha qualified · 17:45 UTC+1

xA3872wq

Sharpe 1.47 · Fitness 1.16 · TO 3.8% · Margin 38.2 bps
Corr 0.35 < 0.70 ✓ · TOP3000 · Delay 1 · Decay 14
```

### Alpha Submitted

```
📬 Submitted · Slot 1/3 · 08:00 UTC+1

xA3872wq

Sharpe 1.47 · Fitness 1.16 · TO 3.8% · Margin 38.2 bps

Next slot opens at 12:00 UTC+1
```

### Daily Report

```
📊 Daily Report · Sat 20 Sept

Discovery
Simulated: 486 · Stage 0: 31 · Qualified: 5
Corr-rejected: 12

Submissions
Submitted: 3/3 ●●●
Ready (drip reserve): 2

Daily goal: 5 qualified · ✅ Target reached

All-time
Pool: 47 · Ready: 2 · Corr-archive: 38
```

## Database

9 tables on Neon PostgreSQL — single source of truth for the unified runner:

| Table | Purpose |
|---|---|
| `options_alphas` | Live alpha pool — `QUALIFIED` (ready) or `SUBMITTED` |
| `options_evaluations` | Immutable audit log of every simulation |
| `options_strategy_rl_state` | Strategy-scoped RL operator weights |
| `options_learning_memory` | Global MAB reward memory per expression |
| `options_rejected_alphas` | Checklist-failed alphas (permanent archive) |
| `options_correlated_alphas` | Correlation-rejected alphas (≥ 0.70) |
| `cluster_session_cache` | Shared BRAIN session token (2h TTL) |
| `cluster_run_lock` | Mutex — one simulation batch at a time |
| `org_runs` | Runner heartbeat & telemetry log |

## LLM Providers

Alpha expression generation uses a 4-provider sequential fallback chain:

| Priority | Provider | Notes |
|---|---|---|
| 1 | **Groq** | Primary — fastest inference |
| 2 | **Cerebras** | Secondary |
| 3 | **OpenRouter** | Tertiary — free tier |
| 4 | **Google Gemini** | Final fallback |

## Daily Target

**Goal: 5 non-correlated qualified alphas per day** (Sharpe ≥ 1.25, Fitness ≥ 1.00, Corr < 0.70)

| Strategy Group | Daily Target |
|---|---|
| Options surface (term_structure, skew, breakeven, pcr_flow) | 2–3 |
| Equity lending (short_interest, informed_short_demand) | 1 |
| Fundamental (analyst_revisions, accruals_cashflow) | 1 |
| Network & hybrid (supply_chain, network_momentum, hybrid_confluence) | 1 |

## Secrets

```bash
DATABASE_URL           # Neon PostgreSQL connection string
TELEGRAM_BOT_TOKEN     # Telegram bot token
TELEGRAM_CHAT_ID       # Telegram chat/channel ID
GROQ_API_KEYS          # Comma-separated Groq API keys
CEREBRAS_API_KEYS      # Comma-separated Cerebras API keys
OPENROUTER_API_KEYS    # Comma-separated OpenRouter API keys
GEMINI_API_KEYS        # Comma-separated Gemini API keys
BRAIN_EMAIL            # WorldQuant BRAIN login email
BRAIN_PASSWORD         # WorldQuant BRAIN login password
```

## Operations

```bash
# Run a single discovery batch locally
python -m brain_options.run --single-batch --strategy skew

# Send a health ping to Telegram
python -m brain_options.run --health

# Send a daily digest to Telegram
python -m brain_options.run --daily-digest

# Run the test suite
python -m pytest tests/ -v
```

## Security

Report vulnerabilities via GitHub private security advisory. This pipeline runs against a live WorldQuant BRAIN account — never commit `.env` or expose credentials in logs.

## Contributing

See [`SETUP.md`](./SETUP.md) for dev environment setup and local run instructions.

## License

Released under the [MIT License](./LICENSE).
