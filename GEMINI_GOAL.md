# ============================================================
# GEMINI GOAL AGENT — MISSION BRIEFING v3.0
# 100 Pure-Sentiment Alphas | WorldQuant BRAIN
# Last Updated: 2026-10-03 05:28 WAT
# READ THIS FILE IN FULL BEFORE TOUCHING ANYTHING
# ============================================================

## 0. CRITICAL RULES — DO NOT SKIP

1. **NEVER SUBMIT ANY ALPHA.** The user submits manually. Your ONLY job is to accumulate QUALIFIED rows in the `options_alphas` table.
2. **Never simulate implied_volatility, iv_*, or options-surface fields.** Pure sentiment fields ONLY.
3. **Never wipe or truncate the database.** All history is precious.
4. **Never restart the miner unless it has hard-crashed** (exit code non-zero, no output for >10 minutes).
5. **Never add sleep/wait loops.** The miner runs continuously and non-stop.
6. **Report progress to the user in real time.** Parse the log, show the scoreboard, never go silent.

---

## 1. YOUR MISSION

**Accumulate 98 more QUALIFIED pure-sentiment alphas in the reserve database.**

| Metric | Value |
|:---|:---|
| Alphas already submitted by user | 2 (`O08exK8R`, `58gVPJln`) |
| QUALIFIED in reserve right now | 0 |
| Your target | **≥ 98 QUALIFIED rows in `options_alphas` where `status = 'QUALIFIED'`** |
| Global stop condition | `SELECT count(*) FROM options_alphas WHERE status IN ('QUALIFIED','SUBMITTED') >= 100` |

---

## 2. THE ONE COMMAND TO START

```powershell
cd c:\Users\pc\Desktop\brain-alpha-pipeline
python scripts/mine_qualify_sentiment_100.py
```

The script is fully autonomous. It mines, simulates, gates, correlates, and writes QUALIFIED rows.
Do NOT modify the script mid-run unless it crashes.

### Check if already running (do this first)
```powershell
Get-Process python | Where-Object { $_.CommandLine -like '*mine_qualify*' }
```
If already running, do NOT start a second instance. Just monitor the log.

---

## 3. THE UPGRADED MATRIX (v3.0 — Day 2 Changes)

### What Changed From Yesterday
The old matrix (P1–P10, TOP2000/TOP3000/TOP1000) was **exhausted** — producing Sharpe 0.01–0.56 on everything. The new matrix unlocks virgin territory:

| Change | Old (v2) | New (v3) |
|:---|:---|:---|
| `PROD_FIREWALL` | 0.55 (too strict) | **0.62** (aligned to BRAIN's 0.70 hard limit) |
| Universes | TOP2000, TOP3000, TOP1000 | **TOPSP500, TOP500, TOP200, TOP1000, TOP2000** |
| TOP3000 | Included | **REMOVED** — 2000–4400 alphas/field, saturated |
| Pillars | P1–P10 (10 pillars) | **P1–P16** (6 new pillars added) |
| Sentinel fields | 6 standard fields | **8 fields** + 2 virgin March 2026 fields |
| Candidates | ~438 | **1,214** |

### Universe Priority (LOW → HIGH competition)
```
TOPSP500 → TOP500 → TOP200 → TOP1000 → TOP2000
```
The miner works this list in order. **TOPSP500 has 11–132 platform alphas per field** (vs 2000–4400 for TOP3000). Fire the low-competition universes first to maximize qualification rate per simulation used.

---

## 4. ALL 16 PILLARS

### Original Pillars (P1–P10) — Expanded to All Universes

| Pillar | Signal | Sentiment Field |
|:---|:---|:---|
| **P1_SUE** | Earnings surprise × vol reversal | `snt1_d1_earningssurprise` |
| **P2_PEAD** | PEAD net revision × price reversal | `snt1_d1_netearningsrevision` |
| **P3_TARGET** | Target price revision × intraday spread | `snt1_d1_nettargetpercent` |
| **P4_RECOMMENDATION** | Net rec% × vol-normalized reversal | `snt1_d1_netrecpercent` |
| **P5_DISPERSION** | Forecast dispersion × net revision | `snt1_d1_dtstsespe` |
| **P6_FOCUS** | Dynamic institutional focus × price accel | `snt1_d1_dynamicfocusrank` |
| **P7_DUAL_CONFLUENCE** | Blended target price + recommendation | `nettargetpercent` + `netrecpercent` |
| **P8_REC_ACCELERATION** | Recommendation velocity delta × vol reversal | `snt1_d1_netrecpercent` |
| **P9_TRIPLE** | Triple confluence SUE × PEAD × Rec | three fields |
| **P10_BREADTH** | Volume breadth shock × SUE | `snt1_d1_earningssurprise` |

### NEW Virgin Pillars (P11–P16) — Day 2 Additions

| Pillar | Zone | Signal | Platform Alphas | Why |
|:---|:---|:---|:---:|:---|
| **P11_SENTLEVEL** | 🔥 D-1 | Daily composite sentiment (decay, vol, zscore) | **0–15** | Virgin 03/2026 field |
| **P12_MOODSCORE** | 🔥 D-2 | Weekly composite mood (decay, vol, reversal) | **0–14** | Virgin 03/2026 field |
| **P13_COMPOSITE_CROSS** | 🔥 D-3 | `sentlevel × moodscoreweekly` cross | **0** | Both fields virgin |
| **P14_DELAY0** | 🟣 F | Delay-0 (same-day) SUE + sentlevel + rec | low | Lower competition than delay 1 |
| **P15_SENTLEVEL_CROSS** | 🟡 B | `sentlevel × SUE`, `moodscoreweekly × rec` | low | Small-universe synergies |
| **P16_NEARMISS_TUNING** | 🔵 A | P9 family micro-tuned (vol threshold sweep) | — | Push near-misses over 1.25 |

### Virgin Field Details
```
snt1_d1_sentlevel       — Daily Composite Sentiment Level (Added 03/2026)
  TOPSP500: 0 platform alphas  ← FIRE HERE FIRST
  TOP500:   5 platform alphas
  TOP1000: 15 platform alphas
  TOP2000:  7 platform alphas

snt1_w1_moodscoreweekly — Weekly Composite Mood Score (Added 03/2026)
  TOPSP500: 0 platform alphas  ← FIRE HERE FIRST
  TOP500:   0 platform alphas
  TOP1000: 14 platform alphas
  TOP200:   2 platform alphas
  TOP2000:  7 platform alphas
```

---

## 5. ALPHA QUALIFICATION GATES

An alpha must pass ALL of these to be written as QUALIFIED:

| Gate | Threshold | Notes |
|:---|:---:|:---|
| Sharpe ratio | ≥ 1.25 | Primary gate |
| Fitness | ≥ 1.0 | Secondary gate |
| Margin | > 0 bps | Must be net positive |
| Turnover | ≤ 70% | Platform practical limit |
| Drawdown | ≤ 30% | Risk limit |
| Max correlation vs reserve | ≤ 0.62 (PROD_FIREWALL) | Orthogonality gate |
| BRAIN checklist | 100% PASS | Auto-checked after sim |

If a candidate scores Sharpe 1.15–1.24, the miner auto-spawns a **micro-sweep** (2 tuned variants) to attempt to push it over the 1.25 gate.

---

## 6. HOW TO CHECK PROGRESS (Run Anytime)

### Quick count
```powershell
cd c:\Users\pc\Desktop\brain-alpha-pipeline
python -c "
import sys; sys.path.insert(0, '.')
from brain_options.config import OptionsConfig
import psycopg
cfg = OptionsConfig.from_env()
conn = psycopg.connect(cfg.database_url)
cur = conn.cursor()
cur.execute('SELECT status, count(*) FROM options_alphas GROUP BY status ORDER BY count(*) DESC')
print('=== STATUS BREAKDOWN ===')
[print(f'  {r[0]}: {r[1]}') for r in cur.fetchall()]
cur.execute(\"SELECT count(*) FROM options_alphas WHERE status IN ('QUALIFIED','SUBMITTED')\")
total = cur.fetchone()[0]
print(f'  TOTAL (QUALIFIED+SUBMITTED): {total}/100')
print(f'  REMAINING: {max(0, 100 - total)}')
"
```

### Full reserve table (what's actually ready to submit)
```powershell
cd c:\Users\pc\Desktop\brain-alpha-pipeline
python -c "
import sys; sys.path.insert(0, '.')
from brain_options.config import OptionsConfig
import psycopg
cfg = OptionsConfig.from_env()
conn = psycopg.connect(cfg.database_url)
cur = conn.cursor()
cur.execute(\"SELECT alpha_id, archetype, universe, sharpe, fitness, margin, max_correlation, created_at FROM options_alphas WHERE status='QUALIFIED' ORDER BY sharpe DESC\")
rows = cur.fetchall()
print(f'QUALIFIED RESERVE: {len(rows)} alphas')
for r in rows:
    print(f'  {r[0]} | {r[2]:8s} | Sharpe={r[3]:.3f} | Fit={r[4]:.3f} | Margin={r[5]*10000:.1f}bps | rho={r[6]:.3f} | {r[1]}')
"
```

### Watch the live log
```powershell
Get-Content -Wait -Tail 30 'C:\Users\pc\.gemini\antigravity-ide\brain\2470f4e9-f54a-43c0-9684-766f09d82d3a\.system_generated\tasks\task-8230.log'
```
*(Replace `task-8230` with the current task ID if restarted)*

---

## 7. SATURATED PILLARS (Auto-Loaded From DB on Every Start)

These pillars are automatically skipped — no simulation quota wasted:
- `P1_SUE` — 6 collisions (saturated in TOP2000/TOP3000)
- `P10_OPTIONS_SKEW` — 4 collisions
- `HYBRID_OPTIONS_SUE` — 2 collisions

> NOTE: These are saturated in TOP2000/TOP3000 only. The same P1_SUE formula on TOPSP500 is NOT saturated. The miner correctly handles this via universe-aware saturation tracking.

---

## 8. QUOTA MANAGEMENT

| Resource | Limit | Strategy |
|:---|:---:|:---|
| BRAIN simulations/day | **1,802** | Reset at 05:00 WAT daily |
| Concurrent simulations | **4** (max safe) | Already configured |
| Sims needed for 98 alphas | ~400–600 est. | ~1 qualified per 5–8 sims |
| Daily quota vs need | 1,802 >> 600 | We have headroom |

**If you hit HTTP 429 (rate limit):**
```python
# In mine_qualify_sentiment_100.py, find run_sentiment_100_miner()
# Change max_concurrent_sims from 4 to 3
# Then restart
```

**If quota resets mid-task (05:00 WAT):**
- Do NOT restart the miner. It auto-retries failed sims.
- If you see `HTTP 201 Created` after 05:00, quota has refreshed.

---

## 9. TROUBLESHOOTING

| Symptom | Cause | Fix |
|:---|:---|:---|
| `HTTP 429` on every sim | Concurrent limit hit | Reduce workers to 3 in script |
| `NULL_METRICS` repeated | Network timeout | Let it run — auto-retries |
| `Expecting value: line 1 column 1` | BRAIN API returning empty | Normal during startup PnL fetch — ignore |
| Sharpe always < 0.5 | Wrong universe or saturated basin | Check if new P11–P16 pillar sims are queued |
| DB connection error | PostgreSQL container down | `docker-compose up -d db` in project root |
| Auth failure | Session expired | Miner auto-refreshes — if persistent, check `.env` |
| Script exits with code 0, `Qualified: 0` | All candidates exhausted | Need new pillar formulas — report to user |

---

## 10. ALPHA RESERVE TARGET ALLOCATION

| Zone | Source | Target Count |
|:---|:---|:---:|
| ✅ Already done | `O08exK8R`, `58gVPJln` (submitted by user) | 2 |
| 🔥 P11 Zone D-1 | `snt1_d1_sentlevel` × 5 universes × 3 variants | 23 |
| 🔥 P12 Zone D-2 | `snt1_w1_moodscoreweekly` × 5 universes × 3 variants | 22 |
| 🔥 P13 Zone D-3 | Cross: sentlevel × moodscoreweekly | 8 |
| 🟡 P2–P10 Zone B | TOP500 + TOPSP500 standard fields | 18 |
| 🟡 P15 Zone B+ | Small-universe sentiment crosses | 8 |
| 🔵 P16 Zone A | Near-miss P9 micro-tuning variants | 10 |
| 🟣 P14 Zone F | Delay-0 same-day sentiment | 9 |
| **TOTAL** | | **100** |

---

## 11. WHAT SUCCESS LOOKS LIKE

Each QUALIFIED alpha appears in the log as:
```
[+] Committed <alpha_id> to options_alphas as QUALIFIED (cluster=<cluster_id>).
```

And in the DB:
```sql
SELECT alpha_id, universe, sharpe, fitness FROM options_alphas
WHERE status = 'QUALIFIED'
ORDER BY sharpe DESC;
```

**When count(*) WHERE status IN ('QUALIFIED','SUBMITTED') >= 100:**
- Stop the miner
- Report final stats table to the user
- Do NOT submit anything — the user will review and submit manually

---

## 12. STOP CONDITION

```sql
SELECT count(*) FROM options_alphas WHERE status IN ('QUALIFIED','SUBMITTED');
```
**When this returns ≥ 100, mission complete.**

Final report format:
```
✅ MISSION COMPLETE — 100 Sentiment Alphas Accumulated
Total QUALIFIED in reserve: XX
Total SUBMITTED by user:     2
─────────────────────────────────
Top 5 by Sharpe:
  <alpha_id> | <universe> | Sharpe=X.XX | Fitness=X.XX | Margin=X.Xbps
  ...
Simulation budget used: ~XXX sims
Time elapsed: X hours X minutes
```

---

## 13. PROJECT STRUCTURE (For Reference)

```
brain-alpha-pipeline/
├── scripts/
│   └── mine_qualify_sentiment_100.py   ← THE MINER (do not touch mid-run)
├── brain_options/
│   ├── config.py                        ← OptionsConfig (reads .env)
│   ├── core/
│   │   ├── client.py                    ← BrainClient, SimMetrics, SimSettings
│   │   └── correlation.py              ← compute_correlation()
│   └── store/
│       └── store.py                     ← OptionsStore (DB reads)
├── .env                                 ← BRAIN_USERNAME, BRAIN_PASSWORD, DATABASE_URL
├── GEMINI_GOAL.md                       ← THIS FILE
└── docker-compose.yml                   ← PostgreSQL container
```

---

## 14. KEY CONSTANTS IN THE MINER

```python
PROD_FIREWALL = 0.62    # Max correlation vs reserve (BRAIN hard limit is 0.70)
HARD_LIMIT    = 0.70    # WorldQuant BRAIN platform ceiling
SHARPE_UPLIFT = 0.10    # Pareto uplift hurdle (10%)
TARGET        = 100     # Stop condition
CONCURRENCY   = 4       # Parallel simulation slots
```

**Do NOT change PROD_FIREWALL above 0.68** — that risks submitting alphas that will collide with other users' alphas on the platform.

---

*Mission started: 2026-10-03 05:22 WAT | Miner task: task-8230 | Matrix version: v3.0 (16 pillars, 1214 candidates)*
