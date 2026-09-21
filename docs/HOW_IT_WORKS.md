# WorldQuant BRAIN Options Alpha Pipeline — How It Works

This document provides a comprehensive, plain-language and technical explanation of the entire system: its architecture, multi-organization structure, alpha discovery lifecycle, reinforcement learning loop, database design, and submission automation.

---

## 1. Executive Overview

### What is this system?
This is an institutional-grade, fully automated quantitative alpha research and submission pipeline designed for **WorldQuant BRAIN**. It generates, tests, optimizes, verifies, and submits options-based mathematical trading signals ("alphas") without human intervention, running 24 hours a day, 7 days a week.

### Where does it run?
The system runs **100% serverless on GitHub Actions**, backed by a serverless **Neon PostgreSQL** database as the single shared source of truth. There are no Docker containers, Render services, or Hugging Face spaces.

---

## 2. The 5-Organization Distributed Architecture

WorldQuant BRAIN restricts simulations and submission pacing to prevent system overload. To maximize research throughput while keeping zero collisions on the single WorldQuant BRAIN account, the workload is partitioned across **5 GitHub repositories/organizations**:

```
                              ┌──────────────────────────────────┐
                              │     Xtley001 (PRIMARY CONTROLLER)│
                              │  - Drip Submitter (Max 3/day)    │
                              │  - Hourly Health Checks (:04)    │
                              │  - Morning Briefing (6:00 AM WAT)│
                              │  - End-of-Day Digest (11:50 PM)  │
                              └────────────────┬─────────────────┘
                                               │
                        Shared Database: Neon PostgreSQL
               ┌───────────────────────┼───────────────────────┐
               │                       │                       │
 ┌─────────────▼─────────┐ ┌───────────▼─────────┐ ┌───────────▼─────────┐ ┌───────────▼─────────┐
 │xtley-alpha-research-01│ │xtley-alpha-research-02│ │xtley-alpha-research-03│ │xtley-alpha-research-04│
 │  Breakeven & Skew     │ │  Analyst Revisions  │ │   Short Interest    │ │ Hybrid Confluence,    │
 │  Even Hours at :07    │ │  Even Hours at :37  │ │   Odd Hours at :07  │ │ Term Structure, PCR   │
 │  (12 runs/day)        │ │  (12 runs/day)      │ │   (12 runs/day)     │ │ Odd Hours at :37      │
 └───────────────────────┘ └─────────────────────┘ └─────────────────────┘ └───────────────────────┘
```

### Roles & Responsibilities

1. **`Xtley001` (Primary Controller)**:
   - Does **not** run raw discovery (it is excluded in `run.yml` to prevent runner congestion).
   - Responsible for **orchestration**:
     - **Drip Submitter (`drip.yml`)**: Checks every 4 hours (and catch-up mode) to submit verified alphas.
     - **Hourly Health Check (`health.yml`)**: Pings Telegram at `:04` past every hour with live cluster counters.
     - **Morning Status Briefing (`status.yml`)**: Sends the daily cluster status report at **6:00 AM WAT (05:00 UTC)**.
     - **Daily Digest (`daily_digest.yml`)**: Sends the end-of-day trading recap at **11:50 PM WAT (22:50 UTC)**.

2. **Satellite Research Organizations (`01`, `02`, `03`, `04`)**:
   - Pure mathematical mining engines.
   - Staggered so that **one worker runs every 30 minutes, 24/7 (48 runs/day)**:
     - **Org 1 (`xtley-alpha-research-01`)**: Specialized in **Breakeven & Volatility Skew** (implied vs. historical volatility spreads, put/call IV skew, smile steepness).
     - **Org 2 (`xtley-alpha-research-02`)**: Specialized in **Analyst Revisions & PEAD** (analyst forecast dispersion, EPS revisions, revenue estimate changes).
     - **Org 3 (`xtley-alpha-research-03`)**: Specialized in **Short Interest** (borrow fee spikes, short interest ratios, days-to-cover, loan utilization pressure).
     - **Org 4 (`xtley-alpha-research-04`)**: Specialized in **Hybrid Confluence & Term Structure** (put/call volume imbalances, term structure slope/curvature, cross-surface confirmation).

### Concurrency & The Mutex Lock
All 4 satellite organizations simulate against the same underlying WorldQuant BRAIN account credentials. To guarantee that two organizations never execute simulations concurrently (which causes BRAIN `429 Too Many Requests` or `Simulations in Progress Limit Exceeded`), the database enforces a cluster-wide lock:
- Table: `cluster_run_lock`
- Function: `db.acquire_cluster_lock(worker_id, org_name)`
- If Org 2 triggers while Org 1 is finishing a batch, Org 2 waits for the lock or gracefully exits. A 15-minute heartbeat auto-cleans stale locks if a runner ever crashes unexpectedly.

---

## 3. The Lifecycle of an Alpha: Step-by-Step

Every alpha goes through a rigorous 6-phase pipeline from initial idea to active submission.

```
┌─────────────────┐
│ 1. Generation   │ ◄── Multi-Armed Bandit (MAB) + LLMs + Formula Templates
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. Stage 0 Triage│ ◄── Fast 2-Year Screening (Sharpe ≥ 0.35, Fitness ≥ 0.20)
└────────┬────────┘
         │ Passes
         ▼
┌─────────────────┐
│ 3. Closed-Loop  │ ◄── 6-Round Diagnostic Optimizer (Mutations, Neutralizations,
│   Optimization  │     Lookbacks) ──► Target: Sharpe ≥ 1.25, Fitness ≥ 1.00
└────────┬────────┘
         │ Passes
         ▼
┌─────────────────┐
│ 4. Platform &   │ ◄── WorldQuant Checklist (No FAIL gates) +
│   Correlation   │     Live Self-Correlation Gate (< 0.70 vs Active Pool)
└────────┬────────┘
         │ Passes
         ▼
┌─────────────────┐
│ 5. Qualified    │ ◄── Saved to Neon DB options_alphas as 'QUALIFIED'
│    Reserve Pool │     Instant Telegram notification sent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. Immediate or │ ◄── Submits straight up if daily quota open (Max 3/day)
│    Drip Submit  │     Enriches metadata, verifies stage 'OS' & status 'ACTIVE'
└─────────────────┘
```

---

### Step 1: Ideation & Mathematical Generation
Before touching the BRAIN simulator, candidates are synthesized using a combination of quantitative theory and artificial intelligence:
1. **Multi-Armed Bandit (MAB) Reinforcement Learning**:
   - The system tracks which mathematical operator combinations, data fields, and archetypes have yielded high Sharpe ratios in the past (`options_learning_memory` table).
   - High-reward archetypes are given higher selection weights; low-reward archetypes are dynamically deprioritized.
2. **LLM Synthesis & Fallbacks**:
   - If enabled, candidate generation uses a rotating pool of LLMs (Groq, Cerebras, OpenRouter, Google Gemini) guided by detailed options financial templates.
   - If external APIs hit rate limits or are offline, the generator instantly falls back to algorithmic genetic mutation without failing.
3. **AST Deduplication**:
   - Every candidate is parsed into an Abstract Syntax Tree (AST). Commutative operations (e.g., `a + b` vs `b + a`) produce identical hashes. Duplicate formulas are discarded before ever calling BRAIN, saving valuable API quota.
4. **Anti-Saturation Filtering**:
   - If an archetype has already had an alpha submitted today, its generation probability drops to 0.02. This forces workers to explore uncrowded mathematical territory.

---

### Step 2: Stage 0 Simulation (The Fast Triage Gate)
WorldQuant BRAIN takes time to simulate alphas. Running full 5-year multi-setting sweeps on every raw idea would exhaust time budgets.
- **What is Stage 0?**
  A fast, lightweight 2-year simulation on the `USA TOP3000` universe with standard settings (`delay=1`, `neutralization=SUBINDUSTRY`).
- **Gate Thresholds**:
  - **Sharpe Ratio $\ge 0.35$**
  - **Fitness $\ge 0.20$**
- **What happens if it fails?**
  The expression is logged to `options_evaluations` with status `STAGE0_FAIL` or `EXHAUSTED`. The RL memory receives a penalty. The runner moves immediately to the next candidate.
- **What happens if it passes?**
  The candidate demonstrated an underlying statistical signal and is immediately promoted to **Closed-Loop Diagnostic Optimization**.

---

### Step 3: Closed-Loop Diagnostic Optimization
This is where raw ideas are tuned into institutional-grade alphas:
- The optimizer inspects the diagnostic metrics returned by BRAIN:
  - Is turnover too high ($> 70\%$)? Add smoothing (`ts_decay_linear`, `ts_mean`, longer lookback).
  - Is turnover too low ($< 1\%$)? Shorten lookbacks or use sharper delta operators.
  - Is fitness low? Test alternative neutralizations (`MARKET`, `SECTOR`, `INDUSTRY`, `SUBINDUSTRY`).
  - Are returns skewed? Apply non-linear transformations (`rank`, `scale`, `winsorize`, `quantile`).
- **Best-Seen State Preservation**:
  In each of up to 6 mutation rounds, the optimizer records the results. If a mutation degrades performance, the optimizer discards the regression and **always returns the peak `best_seen` state**.
- **Stage 1 Qualification Thresholds**:
  - **Sharpe Ratio $\ge 1.25$**
  - **Fitness $\ge 1.00$**
  - **Turnover: $0.01 \le \text{Turnover} \le 0.70$ (1% to 70%)**
  - **Returns $> 0$**

---

### Step 4: Platform Checklist & Self-Correlation Gates
Even an alpha with Sharpe 2.0 can be rejected by WorldQuant BRAIN if it violates portfolio rules. Before an alpha can be approved, it must pass two final checkpoints:
1. **Platform Checklist Verification**:
   The runner queries BRAIN's `/alphas/{id}` endpoint and inspects all checks:
   - `LOW_SHARPE`: Must be PASS.
   - `LOW_FITNESS`: Must be PASS.
   - `LOW_TURNOVER` & `HIGH_TURNOVER`: Must be PASS.
   - `CONCENTRATED_WEIGHT`: Must be PASS.
   - `LOW_SUB_UNIVERSE_SHARPE`: Must be PASS.
   If any gate shows `FAIL`, the alpha is archived to `options_rejected_alphas` and memory is penalized.
2. **Pre-Submission Self-Correlation Gate ($< 0.70$)**:
   - The runner queries WorldQuant BRAIN's `/correlations/self` endpoint and compares the candidate against the user's active portfolio.
   - It also cross-checks historical PnL series against all previously accepted alphas stored in Neon DB.
   - **Limit**: Max correlation must be **strictly less than 0.70**.
   - If correlation $\ge 0.70$, the candidate is archived to `options_correlated_alphas` so it never pollutes the pool.

---

### Step 5: The Qualified Reserve Pool
When an alpha clears all checklist items and has max correlation $< 0.70$:
- It is saved to the Neon PostgreSQL table `options_alphas` with status `QUALIFIED`.
- Its daily PnL series is stored for future correlation checks.
- An **instant Telegram notification** is dispatched with its Sharpe, Fitness, Turnover, and Margin.

---

### Step 6: Immediate Submission & Catch-Up Drip Engine
Submitting alphas to WorldQuant BRAIN is governed by two complementary mechanisms:

1. **Instant Submission on Qualification (Straight Up)**:
   - When any worker qualifies an alpha, if today's submission quota has not yet been filled (`today_subs < max_daily`, where `max_daily = 3`), the system triggers **immediate submission straight up**.
   - It updates metadata on BRAIN (Alpha Name, Description, Tags, Category).
   - It calls `POST /alphas/{id}/submit`.
   - It verifies that the alpha transitioned to Stage `OS` (Out-of-Sample) and status `ACTIVE`.
   - It marks the alpha as `SUBMITTED` in Neon DB and alerts Telegram.

2. **Automated Catch-Up Mode (Drip Submitter)**:
   - If earlier windows were missed because no alphas were ready at that time (e.g. at 06:15 WAT or 10:15 WAT), the system enters **Catch-Up Mode**.
   - When a qualified alpha is found or when `drip.yml` runs, it detects that cumulative submissions are behind schedule for the day and **bypasses the 4-hour spacing constraint**.
   - Alphas are submitted to hit the target daily quota without arbitrary delays.

---

## 4. Reinforcement Learning (MAB) Memory System

The pipeline learns continuously across all runs:
- **Table**: `options_learning_memory`
- **Mechanism**:
  - Whenever an alpha qualifies and submits: Reward $+15.0$ to $+30.0$ added to the expression and its structural sub-trees.
  - Whenever an alpha fails platform checklist gates or is rejected for high correlation: Penalty $-10.0$ to $-15.0$ applied.
  - Success rates and average Sharpe per archetype are tracked.
- **Result**:
  Over time, workers naturally stop generating formula structures that tend to fail checklist tests and spend more compute on high-Sharpe, uncorrelated mathematical families.

---

## 5. Database Schema (Neon PostgreSQL)

Neon Serverless PostgreSQL is the single source of truth across all 5 organizations:

| Table | Purpose |
| :--- | :--- |
| **`options_alphas`** | The active pool: all `QUALIFIED` (reserve) and `SUBMITTED` alphas. |
| **`options_evaluations`** | Immutable audit log of every candidate simulated across all orgs. |
| **`options_learning_memory`** | RL rewards, penalties, and performance weights per expression. |
| **`options_rejected_alphas`** | Archive of alphas that failed checklist tests (with failure reasons). |
| **`options_correlated_alphas`**| Archive of alphas rejected because self-correlation was $\ge 0.70$. |
| **`cluster_session_cache`** | Shared WorldQuant BRAIN authentication token (prevents re-login storms). |
| **`cluster_run_lock`** | Global mutex preventing multiple worker orgs from simulating at once. |
| **`org_runs`** | Real-time audit log tracking runs, candidate counts, and passes per org. |

---

## 6. Daily Notification & Briefing Schedule

All times are tuned to **WAT (West Africa Time, UTC+1)** and offset to avoid GitHub runner queues:

| Time (WAT) | Time (UTC) | Event | Channel | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Every 30 Mins** | `:07` & `:37` | **Discovery Run** | Background / Telegram | Worker orgs run discovery batches; alerts on qualified alpha. |
| **Hourly at `:04`** | Hourly at `:04` | **Health Check** | Telegram | Live counters: sims today, qualified, submitted, org heartbeats. |
| **06:00 AM** | 05:00 UTC | **Morning Status Briefing** | Telegram | Full overnight recap, live pool reserves, and per-org stats. |
| **11:50 PM** | 22:50 UTC | **End-of-Day Digest** | Telegram | Complete end-of-day summary of simulations and submissions. |
| **Instantaneous** | Real-time | **Submission Alert** | Telegram | Fired the second an alpha is verified and submitted to BRAIN. |

---

## 7. Plain-Language Summary for Quick Explanations

If you ever need to describe this system to colleagues or investors in 3 sentences:
> *"Our system is a 24/7 distributed quantitative research cluster split across 5 specialized GitHub worker organizations and backed by a shared PostgreSQL database. It continuously invents options trading alphas using financial theory and reinforcement learning, tests them in a 2-stage simulation loop against WorldQuant BRAIN, and automatically optimizes them for high Sharpe, low turnover, and zero portfolio correlation. Once verified, qualified alphas are automatically submitted straight to the platform with automated catch-up pacing to consistently meet our daily submission targets."*
