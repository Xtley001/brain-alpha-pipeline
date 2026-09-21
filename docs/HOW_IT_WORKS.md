# How It Works

A plain-language and technical walkthrough of the entire pipeline: architecture, alpha lifecycle, reinforcement learning, database design, and submission automation.

## Table of Contents

- [Overview](#overview)
- [Unified Pipeline Architecture](#unified-pipeline-architecture)
- [Alpha Lifecycle](#alpha-lifecycle)
- [Reinforcement Learning](#reinforcement-learning)
- [Database Schema](#database-schema)
- [Notification Schedule](#notification-schedule)
- [Plain-Language Summary](#plain-language-summary)

---

## Overview

This is an institutional-grade, fully automated quantitative alpha research and submission pipeline for **WorldQuant BRAIN**. It generates, tests, optimizes, verifies, and submits options-based and equity mathematical trading signals without human intervention, running 24/7.

The system runs **100% serverless on GitHub Actions**, backed by a serverless **Neon PostgreSQL** database as the single shared source of truth. There are no Docker containers, Render services, or Hugging Face Spaces.

---

## Unified Pipeline Architecture

All workload runs from a single repository — `Xtley001/brain-alpha-pipeline` — to maximize throughput while maintaining zero simulation collisions on the WorldQuant BRAIN account.

```
┌─────────────────────────────────────────────────┐
│            Xtley001/brain-alpha-pipeline         │
│                                                  │
│  Discovery (run.yml)  → 48 batches/day           │
│  Drip (drip.yml)      → 3 submissions/day        │
│  Health (health.yml)  → hourly Telegram ping     │
│  Digest (daily_digest.yml) → midnight recap      │
│                                                  │
│  Shared: Neon PostgreSQL · Telegram Bot          │
└─────────────────────────────────────────────────┘
           │
           ▼
   15 Modular Strategy Packages
   (brain_options/strategies/)
   ┌──────────────┬─────────────┬─────────────┐
   │ Pure Options │  Eq Lending │  Fundamental│
   │ term_structure│ short_int  │ analyst_rev │
   │ skew          │ inf_short  │ accruals    │
   │ pcr_flow      └─────────────┤ supply_chain│
   │ breakeven    ┌─────────────┤ network_mom │
   │ forward_basis│   Hybrid    │ formulaic   │
   │ extreme_tail │ confluence  │             │
   │ iv_lead_lag  └─────────────┴─────────────┘
   └──────────────
```

### Roles

- **Discovery (`run.yml`)**: Scheduled every 30 minutes (48 runs/day), rotating across all 15 modular strategy packages and 6 liquid asset universes (`TOP3000`, `TOP2000`, `TOP1000`, `TOP500`, `TOP200`, `TOPSP500`).
- **Drip Submitter (`drip.yml`)**: Submits verified orthogonal alphas paced to WorldQuant submission guidelines.
- **Hourly Health (`health.yml`)**: Pings Telegram at `:00` past every hour with live funnel counters.
- **Daily Digest (`daily_digest.yml`)**: End-of-day full recap at midnight WAT.

### Concurrency & Serialized Execution

To prevent overlapping simulation batches, the system enforces a strict process-level lock:

- Table: `cluster_run_lock`
- Function: `db.acquire_cluster_lock(worker_id, org_name)`
- A 15-minute heartbeat auto-cleans stale locks if a runner crashes unexpectedly.

---

## Alpha Lifecycle

Every alpha passes a rigorous 6-phase pipeline from initial idea to active submission.

```
┌─────────────────┐
│ 1. Generation   │ ◄── MAB + LLMs + Formula Templates
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Stage 0      │ ◄── Fast 2-year screen (Sharpe ≥ 0.35, Fitness ≥ 0.20)
└────────┬────────┘
         │ passes
         ▼
┌─────────────────┐
│ 3. Optimization │ ◄── 6-round diagnostic optimizer → target Sharpe ≥ 1.25
└────────┬────────┘
         │ passes
         ▼
┌─────────────────┐
│ 4. Gates        │ ◄── Platform checklist + self-correlation < 0.70
└────────┬────────┘
         │ passes
         ▼
┌─────────────────┐
│ 5. Reserve Pool │ ◄── Saved to options_alphas as QUALIFIED + Telegram alert
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. Submission   │ ◄── Immediate if quota open (max 3/day), else drip catch-up
└─────────────────┘
```

### Step 1: Generation

Candidates are synthesized before touching the BRAIN simulator:

- **Multi-Armed Bandit (MAB)**: Tracks which operator combinations and archetypes have yielded high Sharpe ratios. High-reward archetypes get higher selection weights; low-reward archetypes are deprioritized.
- **LLM Synthesis**: A rotating pool of LLMs (Groq → Cerebras → OpenRouter → Gemini) guided by institutional financial templates. Falls back to algorithmic mutation on rate limits or API unavailability.
- **AST Deduplication**: Every candidate is parsed into an Abstract Syntax Tree. Commutative operations produce identical hashes. Duplicates are discarded before any BRAIN API call.
- **Anti-Saturation Filtering**: If an archetype has already had an alpha submitted today, its generation probability drops to 0.02.

### Step 2: Stage 0 Simulation

A fast 2-year simulation on `USA TOP3000` with standard settings (`delay=1`, `neutralization=SUBINDUSTRY`).

| Gate | Threshold |
|---|---|
| Sharpe | ≥ 0.35 |
| Fitness | ≥ 0.20 |

On failure: logged to `options_evaluations`, RL memory penalized, runner moves to next candidate.
On pass: candidate is promoted to closed-loop diagnostic optimization.

### Step 3: Closed-Loop Diagnostic Optimization

The optimizer inspects BRAIN's diagnostic metrics and applies targeted mutations:

| Diagnostic | Mutation Applied |
|---|---|
| Turnover > 70% | Add smoothing: `ts_decay_linear`, `ts_mean`, longer lookback |
| Turnover < 1% | Shorten lookbacks or sharper delta operators |
| Low fitness | Test alternative neutralizations (`MARKET`, `SECTOR`, `INDUSTRY`, `SUBINDUSTRY`) |
| Skewed returns | Apply `rank`, `scale`, `winsorize`, `quantile` |

Up to 6 mutation rounds. The optimizer always returns the peak `best_seen` state — regressions are discarded.

**Qualification thresholds:**

| Metric | Threshold |
|---|---|
| Sharpe | ≥ 1.25 |
| Fitness | ≥ 1.00 |
| Turnover | 1% – 70% |
| Returns | > 0 |

### Step 4: Platform Checklist & Self-Correlation Gates

**Platform checklist** — queries BRAIN's `/alphas/{id}` endpoint:

| Gate | Required |
|---|---|
| `LOW_SHARPE` | PASS |
| `LOW_FITNESS` | PASS |
| `LOW_TURNOVER` | PASS |
| `HIGH_TURNOVER` | PASS |
| `CONCENTRATED_WEIGHT` | PASS |
| `LOW_SUB_UNIVERSE_SHARPE` | PASS |

**Self-correlation gate** — queries `/correlations/self`, cross-checks historical PnL against all accepted alphas in Neon DB. Max correlation must be strictly < 0.70. Failures archive to `options_correlated_alphas`.

### Step 5: Qualified Reserve Pool

When an alpha clears all gates:

- Saved to `options_alphas` with status `QUALIFIED`
- Daily PnL series stored for future correlation checks
- Instant Telegram alert dispatched with Sharpe, Fitness, Turnover, and Margin

### Step 6: Submission & Drip Engine

**Immediate submission**: If today's quota is not yet filled (`today_subs < 3`), the system triggers immediate submission. Updates BRAIN metadata, calls `POST /alphas/{id}/submit`, verifies Stage `OS` and status `ACTIVE`, marks `SUBMITTED` in Neon DB, and alerts Telegram.

**Catch-up mode**: If earlier windows were missed, the drip engine bypasses the spacing constraint and submits immediately to hit the daily quota.

---

## Reinforcement Learning

The pipeline learns continuously across all runs via a Multi-Armed Bandit (MAB) system:

- **Table**: `options_learning_memory` + `options_strategy_rl_state`
- **Rewards**: Qualifying and submitting an alpha adds +15.0 to +30.0 to the expression and its structural sub-trees.
- **Penalties**: Checklist failure or high-correlation rejection applies –10.0 to –15.0.
- **Result**: Over time, the generator naturally converges toward high-Sharpe, uncorrelated mathematical operator families and away from those that consistently fail platform gates.

---

## Database Schema

| Table | Purpose |
|---|---|
| `options_alphas` | Active pool — all `QUALIFIED` (reserve) and `SUBMITTED` alphas |
| `options_evaluations` | Immutable audit log of every candidate simulated |
| `options_strategy_rl_state` | Strategy-scoped RL weights (partitioned by `strategy_name`) |
| `options_learning_memory` | Global RL rewards, penalties, and weights per expression |
| `options_rejected_alphas` | Archive of checklist-failed alphas with failure reasons |
| `options_correlated_alphas` | Archive of self-correlation-rejected alphas (≥ 0.70) |
| `cluster_session_cache` | Shared BRAIN auth token (prevents re-login storms) |
| `cluster_run_lock` | Global mutex preventing overlapping simulation batches |
| `org_runs` | Real-time audit log — runs, candidate counts, passes per batch |

---

## Notification Schedule

All times in WAT (UTC+1):

| Time (WAT) | Event | Channel | Description |
|---|---|---|---|
| Every 30 min | Discovery Run | Background / Telegram | Strategy batch; alert fires on qualified alpha |
| Hourly at `:00` | Health Check | Telegram | Live counters: sims, qualified, submitted, strategy |
| Midnight WAT | Daily Digest | Telegram | Full end-of-day simulation and submission summary |
| Real-time | Submission Alert | Telegram | Fires the moment an alpha is verified and submitted |

---

## Plain-Language Summary

> *This pipeline is a 24/7 serverless quantitative research engine running on a single GitHub repository. It continuously invents options and equity trading signals using financial theory and reinforcement learning, tests them in a 2-stage simulation loop against WorldQuant BRAIN, and automatically optimizes them for high Sharpe, low turnover, and zero portfolio correlation. Once verified, qualified alphas are automatically submitted to the platform with catch-up pacing to consistently meet daily submission targets.*
