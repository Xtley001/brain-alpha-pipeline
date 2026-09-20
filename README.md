# BRAIN Options Alpha Pipeline

> Autonomous WorldQuant BRAIN options alpha discovery engine.
> 5-org distributed cluster · 48 discovery runs/day · 3 daily submissions · Neon PostgreSQL · Telegram alerts.

---

## Architecture — 5 Orgs, 2 Roles

```
┌─────────────────────────────────────────────────────────────────┐
│                   BRAIN ALPHA CLUSTER                           │
│                                                                 │
│  ┌──────────────────────────────────────────┐                  │
│  │         Xtley001/brain-alpha-pipeline    │  PRIMARY ORG     │
│  │  drip.yml       → 3 submissions/day      │  (this repo)     │
│  │  health.yml     → hourly Telegram ping   │                  │
│  │  daily_digest.yml → EOD Telegram report  │                  │
│  │  status.yml     → on-demand dispatch     │                  │
│  └──────────────────────────────────────────┘                  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  research-01  │  │  research-02  │  │  research-03  │        │
│  │ breakeven     │  │ analyst_rev   │  │ short_interest│        │
│  │ skew          │  │               │  │               │        │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  ┌──────────────────────────────────────────┐                  │
│  │             research-04                  │                  │
│  │  hybrid_confluence · term_structure      │                  │
│  │  pcr_flow                                │                  │
│  └──────────────────────────────────────────┘                  │
│                                                                 │
│  Shared: Neon PostgreSQL DB · Telegram Bot                      │
└─────────────────────────────────────────────────────────────────┘
```

### Org Roles

| Org | Role | Specialization | Schedule |
|---|---|---|---|
| `Xtley001` | **Primary** — drip, health, digest | submit + monitor | On-demand / cron |
| `xtley-alpha-research-01` | **Worker** | `breakeven`, `skew` | Every 2h even UTC |
| `xtley-alpha-research-02` | **Worker** | `analyst_revisions` | Every 2h even +30m |
| `xtley-alpha-research-03` | **Worker** | `short_interest` | Every 2h odd UTC |
| `xtley-alpha-research-04` | **Worker** | `hybrid_confluence`, `term_structure`, `pcr_flow` | Every 2h odd +30m |

**Zero slot collision:** Workers are staggered 30 minutes apart so only one org sims on BRAIN at a time (enforced also by `cluster_run_lock` in Neon).

---

## Workflows

### Primary Org (Xtley001)

| Workflow | Trigger | What It Does |
|---|---|---|
| [`drip.yml`](.github/workflows/drip.yml) | 3× daily (08:00, 14:00, 20:00 WAT) | Submits 1 qualified alpha from reserve to BRAIN, paced by 4h New York window |
| [`health.yml`](.github/workflows/health.yml) | Hourly at `:00` | Sends Telegram heartbeat with today's funnel stats |
| [`daily_digest.yml`](.github/workflows/daily_digest.yml) | Daily at 23:30 UTC | Sends full-day summary: simulated, qualified, submitted, reserve, correlated |
| [`status.yml`](.github/workflows/status.yml) | **Manual dispatch** | On-demand cluster status report + DB stats in Actions logs |

### Worker Orgs (research-01 to 04)

| Workflow | Trigger | What It Does |
|---|---|---|
| [`run.yml`](.github/workflows/run.yml) | Staggered cron (every 2h) | Discovers new alpha candidates for assigned archetype channels |

---

## Telegram Notifications

All notifications are minimalist, no links, no raw formulas, straight to the point.

### 🟢 Hourly Health (every hour at :00)
```
🟢 Hourly Health · 18:00 UTC+1

Simulated today: 142
Qualified: 3/5  ●●●○○
Submitted: 1/3  ●○○
Reserve (unsubmitted): 2
Corr-rejected today: 4

Orgs: 5/5 · 4 discovery + drip active
```

### ✅ Alpha Qualified (real-time, when a worker finds a pass)
```
✅ Alpha Qualified

xA3872wq

Sharpe 1.47 · Fitness 1.16 · TO 3.8%
Margin 38.2 bps · Corr 0.35 < 0.70 ✓
Universe TOP3000 · Delay 1 · Decay 14
```

### 🚀 Alpha Submitted (real-time drip confirmation)
```
🚀 Submitted [1/3]

Alpha gJbAP76e

Sharpe 1.79 · Fitness 1.46
Margin 40.6 bps · TO 4.1%
```

### 📊 Daily Digest (23:30 UTC every day)
```
📊 Daily Digest · Sat 20 Sept

Simulated    : 486
Stage0 pass  : 31
Qualified    : 5
Submitted    : 3
Corr-rejected: 12
Reserve      : 2

All-time pool: 47
All-time corr: 38
```

---

## Database — 7 Tables

| Table | Purpose |
|---|---|
| `options_alphas` | Live alpha pool — `QUALIFIED` (ready to submit) or `SUBMITTED` |
| `options_evaluations` | Immutable audit log of every simulation across all 5 orgs |
| `options_learning_memory` | MAB RL brain — reward scores per expression, drives archetype weighting |
| `options_rejected_alphas` | Alphas that failed BRAIN platform checklist gates (permanent ban) |
| `options_correlated_alphas` | Alphas that failed self-correlation < 0.70 gate |
| `cluster_session_cache` | Shared BRAIN session token (2h TTL) across all 5 orgs |
| `cluster_run_lock` | Cluster mutex — ensures only 1 org sims at a time on BRAIN |

---

## LLM Providers (Generation)

Alpha expression generation uses a 4-provider sequential fallback chain:

| Priority | Provider | Models | Notes |
|---|---|---|---|
| 1 | **Groq** | `llama-3.3-70b-versatile`, `deepseek-r1-distill-llama-70b`, `llama-3.1-8b-instant` | Primary — fastest inference |
| 2 | **Cerebras** | `llama-3.3-70b`, `llama3.1-70b`, `llama3.1-8b` | Secondary |
| 3 | **OpenRouter** | `meta-llama/llama-3.3-70b-instruct:free`, `mistralai/mistral-7b-instruct:free` | Tertiary — free tier |
| 4 | **Google Gemini** | `gemini-2.0-flash`, `gemini-1.5-flash`, `gemini-1.5-pro` | Final fallback |

> **Note:** Groq `compound-beta` (deprecated Sept 21 2026) is **not used** in this pipeline.

---

## Daily Alpha Target

**Goal: 5 non-correlated qualified alphas per day** (Sharpe ≥ 1.25, Fitness ≥ 1.00, Corr < 0.70)

Each of the 4 archetype channels is expected to contribute ≥ 1 qualified alpha per day:

| Channel | Target |
|---|---|
| Breakeven / Skew | 1–2 |
| Analyst Revisions | 1 |
| Short Interest | 1 |
| Hybrid / Term Structure / PCR | 1–2 |

---

## Secrets Required

```
DATABASE_URL          — Neon PostgreSQL connection string
TELEGRAM_BOT_TOKEN    — Telegram bot token
TELEGRAM_CHAT_ID      — Your Telegram chat/channel ID
GROQ_API_KEYS         — Comma-separated Groq API keys
CEREBRAS_API_KEYS     — Comma-separated Cerebras API keys
OPENROUTER_API_KEYS   — Comma-separated OpenRouter API keys
GEMINI_API_KEYS       — Comma-separated Gemini API keys
BRAIN_EMAIL           — WorldQuant BRAIN login email
BRAIN_PASSWORD        — WorldQuant BRAIN login password
ORG_SYNC_PAT          — GitHub PAT with repo scope (for cross-org pushes)
```

> All secrets must be set on **all 5 orgs**. Use `python scripts/org_manager.py --sync` to push code updates to all 4 worker orgs after any change to the primary.

---

## Operations

```bash
# Sync all 5 orgs to latest main
python scripts/org_manager.py --sync

# Check status of all 5 orgs
python scripts/org_manager.py --status

# Manually trigger a health ping to Telegram
python -m brain_options.run --health

# Manually trigger a daily digest to Telegram
python -m brain_options.run --daily-digest

# Run tests
python -m pytest tests/ -v
```
