# BRAIN Alpha Pipeline: Complete Master Quality & Strategy Guide (`boost.md`)

This master reference outlines the exact quantitative engineering, calibrated screening math, cleaned template catalog, and supercharged LLM prompt architecture deployed to systematically discover and pass WorldQuant BRAIN alphas (`Sharpe ≥ 1.25`, `Fitness ≥ 1.0`, `Turnover 1%-70%`, `MaxCorr < 0.70`).

---

## 1. Root Cause Analysis: Why Previous Candidates Were Dropped

Out of the 1,549 all-time candidates tested prior to this upgrade, 100% failed at **Stage 0 (`rejected_stage0`)** due to three specific engineering bottlenecks:

| Bottleneck | Root Cause | Impact | Fix Applied |
| :--- | :--- | :--- | :--- |
| **1. Premature Stage 0 Gate** | Stage 0 screened candidates at `Sharpe ≥ 0.50` & `Fitness ≥ 0.30` on **fixed default settings** (`decay=8, neutralization=SUBINDUSTRY`). | Raw signals with Sharpe $0.35$ on default settings were dropped before **Stage 1 (30-combo neutralization $\times$ decay grid)** could optimize them to $1.35+$. | Calibrated Stage 0 floor to **`Sharpe ≥ 0.35`** and **`Fitness ≥ 0.20`**. |
| **2. Invalid Template Fields** | Seed templates contained invalid placeholders (`is_earnings_window`, `is_turn_of_month`, `day_of_week_flag`, `pe_ratio`, `ev_ebitda`). | BRAIN returned syntax errors or 0 scores on simulation. | Replaced 100% of seed templates with valid BRAIN data matrices and operators. |
| **3. Generic LLM Prompting** | LLM generator had no list of valid BRAIN operators, data fields, or multi-factor alpha patterns. | LLM generated simplistic single-factor price reversals that decayed years ago. | Supercharged prompt with valid field dictionaries, operator palettes, and multi-factor archetypes. |

---

## 2. The 5-Stage Screening Funnel & Calibration

```
[Candidate Alpha Expression]
             │
             ▼
┌──────────────────────────────────────────────┐
│  STAGE 0: Fast Screen (1 Simulation)         │  Settings: Universe=TOP3000, Decay=8, Neut=SUBINDUSTRY
│  Criteria: Sharpe ≥ 0.35, Fitness ≥ 0.20     │  Purpose: Weed out unviable noise quickly
└──────────────────────┬───────────────────────┘
                       │ (PASS)
                       ▼
┌──────────────────────────────────────────────┐
│  STAGE 1: Neutralization × Decay Grid (30 Sims) │  Sweeps: 6 Neutralizations (NONE, MARKET, SECTOR,
│  Criteria: Pick highest Fitness combo        │          INDUSTRY, SUBINDUSTRY, COUNTRY) × 5 Decays (0, 4, 8, 15, 20)
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  STAGE 2: Truncation Refinement (4 Sims)     │  Sweeps: Truncations [0.01, 0.03, 0.05, 0.08, 0.10]
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  STAGE 3: Sensitivity (6 Sims)               │  Sweeps: Delays (0, 1), Pasteurization, NaN Handling
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  LOCAL FILTER & CORRELATION GATES            │  Criteria: Sharpe ≥ 1.25, Fitness ≥ 1.00,
│  Final Acceptance Bar                        │            Turnover 1% - 70%, Max Pool Correlation < 0.70
└──────────────────────┬───────────────────────┘
                       │ (PASS)
                       ▼
⭐ [PASSED ALPHA: Written to review_store & Alerted on Telegram]
```

---

## 3. Valid WorldQuant BRAIN Fast Expression Syntax

### A. Valid Data Fields (USA Equities)
* `open`, `high`, `low`, `close`, `volume`, `vwap`, `returns`, `cap`, `adv20`, `sharesout`

### B. Valid Time-Series Operators (lookback window $d$)
* `ts_rank(x, d)`: Time-series percentile rank over $d$ days.
* `ts_zscore(x, d)`: Standardized score $(x - \mu_d) / \sigma_d$.
* `ts_decay_linear(x, d)`: Linear moving average with weights $[1, 2, \dots, d]$.
* `ts_delta(x, d)`: Difference $x_t - x_{t-d}$.
* `ts_delay(x, d)`: Lagged value $x_{t-d}$.
* `ts_std_dev(x, d)`: Moving standard deviation.
* `ts_mean(x, d)`: Moving arithmetic mean.
* `ts_corr(x, y, d)`: Rolling Pearson correlation between $x$ and $y$.
* `ts_max(x, d)` / `ts_min(x, d)`: Rolling extreme values.

### C. Valid Cross-Sectional Operators
* `rank(x)`: Percentile rank across the whole universe $[0.0, 1.0]$.
* `group_neutralize(x, group)`: Demeans $x$ within its `sector`, `industry`, or `subindustry`.
* `group_rank(x, group)`: Percentile rank of $x$ strictly within its group.
* `group_zscore(x, group)`: Group-relative standardized score.
* `group_mean(x, weight, group)`: Weighted group mean.

### D. Mathematical Operators
* `signed_power(x, p)`: $\text{sign}(x) \cdot |x|^p$ (non-linear shape accentuation).
* `min(x, y)` / `max(x, y)`: Element-wise min / max bounds.
* `abs(x)`: Absolute value.

---

## 4. Complete Cleaned Seed Template Catalog (40 Mathematical Templates)

The built-in template generator (`pipeline/generator/template_generator.py`) generates high-conviction variants across 6 quantitative styles:

### A. Reversal & Mean Reversion
1. **Classic n-Day Reversal**: `group_neutralize(rank(-ts_delta(close, {w})), sector)` with $w \in \{2, 3, 5, 10\}$
2. **Z-Score Mean Reversion**: `group_neutralize(rank(-ts_zscore(close, {w})), subindustry)` with $w \in \{5, 10, 20\}$
3. **Overnight Gap Fade**: `rank(-(open - ts_delay(close, 1)) / (ts_delay(close, 1) + 0.001))`
4. **Volume-Weighted Reversal**: `rank(-ts_delta(close, 1) * min(volume / (ts_mean(volume, {w}) + 0.001), 4))` with $w \in \{10, 20\}$
5. **Intraday-Range Reversal**: `rank(rank(-ts_delta(close, 1)) * rank((high - low) / (ts_mean(high - low, {w}) + 0.001)))` with $w \in \{10, 20\}$
6. **Sector-Relative Reversal**: `rank(-(ts_delta(close, 1) - group_mean(ts_delta(close, 1), 1, sector)))`
7. **Volume Anomaly Reversal**: `group_neutralize(rank(-ts_rank(returns, {w}) * rank(volume / (adv20 + 0.001))), subindustry)` with $w \in \{3, 5, 10\}$

### B. Momentum & Trend Following
8. **Decay-Smoothed Skip-Month Momentum**: `rank(ts_decay_linear(ts_delta(ts_delay(close, 21), {w}), 20))` with $w \in \{63, 126\}$
9. **Risk-Adjusted Momentum**: `group_neutralize(rank(ts_decay_linear(returns, {w}) / (ts_std_dev(returns, {w}) + 0.0001)), sector)` with $w \in \{20, 60\}$
10. **Momentum Acceleration**: `rank(ts_delta(rank(ts_delta(close, {w1})), {w2}))` with $(w_1, w_2) \in \{(63, 21), (20, 5)\}$
11. **Momentum Size Interaction**: `rank(rank(ts_delta(close, {w})) * rank(-cap))` with $w \in \{63, 126\}$
12. **Volatility-Conditioned Momentum**: `rank(ts_delta(close, {w})) * (1 / (1 + ts_std_dev(returns, 20)))` with $w \in \{63, 126\}$
13. **52-Week High Proximity**: `rank(close / (ts_max(high, {w}) + 0.001))` with $w \in \{126, 252\}$
14. **Momentum Rank Stability**: `ts_decay_linear(rank(ts_delta(close, {w})), 10)` with $w \in \{20, 60\}$

### C. Volume & Liquidity Microstructure
15. **Volume-Anomaly Price Signal**: `rank(ts_delta(close, 1) * min(volume / (adv20 + 0.001), 4))`
16. **Amihud Illiquidity Proxy**: `rank(abs(returns) / (volume * close + 1000))`
17. **Turnover-Decline Signal**: `rank(-ts_delta(ts_mean(volume, {w1}), {w2}))` with $(w_1, w_2) = (5, 20)$
18. **Volume-Price Divergence**: `rank(rank(ts_delta(close, {w})) * rank(-ts_delta(volume, {w})))` with $w \in \{5, 10\}$
19. **Price-Volume Correlation Anomaly**: `rank(-ts_corr(close, volume, {w}))` with $w \in \{10, 20\}$
20. **Intraday Range Compression**: `group_neutralize(rank(-((high - low) / close) / (ts_mean((high - low) / close, {w}) + 0.001)), sector)` with $w \in \{10, 20\}$
21. **VWAP Price Displacement**: `rank(ts_decay_linear((vwap - close) / close, {w}))` with $w \in \{5, 10\}$
22. **Intraday Pressure Surge**: `rank((close - open) / (high - low + 0.0001)) * rank(volume / adv20)`

### D. Multi-Factor Interactions
23. **Non-Linear Reversal Power**: `signed_power(group_neutralize(rank(-ts_delta(close, {w})), subindustry), 2)` with $w \in \{2, 5\}$
24. **Volume Rank $\times$ VWAP Deviation**: `rank(ts_rank(volume, {w}) * (close - vwap) / close)` with $w \in \{10, 20\}$
25. **Small-Cap Momentum Tilt**: `rank(ts_delta(close, {w}) / (ts_delay(close, {w}) + 0.001)) * rank(-cap)` with $w \in \{20, 60\}$
26. **Price Z-Score Minus Volume Z-Score**: `group_neutralize(rank(ts_zscore(close, 20)) - rank(ts_zscore(volume, 20)), industry)`
27. **Decay Momentum with Volume Confirmation**: `rank(ts_decay_linear(returns, {w})) * rank(ts_decay_linear(volume / adv20, {w}))` with $w \in \{5, 10\}$

### E. Volatility & Risk Regimes
28. **Low-Volatility Anomaly**: `group_neutralize(rank(-ts_std_dev(returns, {w})), sector)` with $w \in \{20, 60\}$
29. **Volatility Term Structure Ratio**: `rank(-(ts_std_dev(returns, {w1}) / (ts_std_dev(returns, {w2}) + 0.0001)))` with $(w_1, w_2) = (5, 60)$
30. **VWAP Displacement with Low-Vol Filter**: `rank(close - ts_decay_linear(vwap, {w})) * rank(-ts_std_dev(returns, {w}))` with $w \in \{10, 20\}$
31. **Returns-Volume Correlation Signal**: `group_neutralize(rank(ts_corr(returns, volume, {w})), subindustry)` with $w \in \{10, 20\}$
32. **Range Rank with Price Trend**: `rank(-ts_rank(high - low, {w})) * rank(ts_delta(close, 5))` with $w \in \{20, 60\}$

### F. Cross-Sectional & Group-Neutral
33. **Sector Mean Momentum Rotation**: `group_rank(ts_delta(group_mean(close, 1, sector), {w}), sector)` with $w \in \{5, 20\}$
34. **Industry-Neutral Time-Series Rank**: `group_neutralize(rank(ts_rank(close, {w})), industry)` with $w \in \{10, 20, 60\}$
35. **Subindustry-Neutral VWAP Reversal**: `group_neutralize(rank(-ts_delta(vwap, {w})), subindustry)` with $w \in \{3, 5, 10\}$
36. **Sector-Relative Return with Size Interaction**: `rank(returns - group_mean(returns, 1, sector)) * rank(-cap)`
37. **Subindustry Group Z-Score Decay**: `group_zscore(ts_decay_linear(returns, {w}), subindustry)` with $w \in \{5, 20\}$
38. **Dual-Horizon Momentum Spread**: `group_neutralize(rank(ts_delta(close, 5) - ts_delta(close, 20)), sector)`
39. **Large-Cap Short-Term Mean Reversion**: `rank(-ts_delta(close, 1)) * rank(cap)`
40. **Intraday Trend Decay**: `rank(ts_decay_linear(close - open, {w}))` with $w \in \{5, 10\}$

---

## 5. Supercharging the Multi-Key LLM Engine

### The 4-Key Groq + 4-Key OpenRouter Architecture
* **Groq Tier (4 accounts)**: Primary reasoning & mechanical generator. When an account hits a rate limit, the adapter automatically rotates to the next active key.
* **OpenRouter Tier (4 accounts)**: Fallback generator. If all Groq keys are exhausted, OpenRouter immediately takes over.
* **Deduplication Gate**: Every newly proposed formula is checked against the database `candidates` table. Exact matches are discarded before simulation.
* **Failure Memory**: Recent rejected formulas and their reasons (`rejected_stage0`, `rejected_filter`, `rejected_correlation`) are dynamically injected into the LLM prompt to steer the AI toward unexplored market dynamics.

### Supercharged Reasoning Prompt
```text
You are an elite quantitative researcher designing WorldQuant BRAIN alpha expressions (Fast Expression syntax, USA Equities).

### VALID WORLDQUANT BRAIN DATA FIELDS:
- Price / Volume: `open`, `high`, `low`, `close`, `volume`, `vwap`, `returns`, `cap`, `adv20`, `sharesout`
- DO NOT invent variables like pe_ratio, market_cap, earnings_window, or custom flags.

### VALID OPERATORS:
- Cross-Sectional: `rank(x)`, `group_rank(x, group)`, `group_neutralize(x, group)`, `group_zscore(x, group)` (groups: `sector`, `industry`, `subindustry`)
- Time-Series: `ts_rank(x, d)`, `ts_zscore(x, d)`, `ts_decay_linear(x, d)`, `ts_delta(x, d)`, `ts_delay(x, d)`, `ts_mean(x, d)`, `ts_std_dev(x, d)`, `ts_max(x, d)`, `ts_min(x, d)`, `ts_corr(x, y, d)`
- Math: `signed_power(x, p)`, `abs(x)`, `min(x, y)`, `max(x, y)`, `log(x)`

### HIGH-ALPHA MULTI-FACTOR PATTERNS:
1. Volume Shock x Reversal: `group_neutralize(rank(-ts_zscore(close, 5)) * rank(volume / (adv20 + 0.001)), subindustry)`
2. Risk-Adjusted Momentum: `group_neutralize(rank(ts_decay_linear(returns, 20) / (ts_std_dev(returns, 20) + 0.0001)), sector)`
3. Intraday Pressure x Trend: `rank((close - open) / (high - low + 0.0001)) * rank(ts_delta(close, 5))`
4. VWAP Deviation with Volatility Filter: `rank(ts_decay_linear((vwap - close) / close, 10)) * rank(-ts_std_dev(returns, 60))`
5. Volume-Price Divergence: `group_neutralize(rank(ts_delta(close, 10)) * rank(-ts_delta(volume, 10)), industry)`

### CONSTRAINTS:
- Outer expression MUST be cross-sectionally normalized with `rank(...)` or `group_neutralize(rank(...), ...)`.
- Windows `d` must be realistic trading horizons: 2, 3, 5, 10, 20, 60, 126, or 252.
- Avoid repeating recently proposed expressions.
```

---

## 6. How to Run, Track, and Verify Results

### 1. Automated Execution
GitHub Actions runs the pipeline on a scheduled cron cadence. You can also trigger an immediate run via:
```bash
gh workflow run run.yml
```

### 2. High-Signal Telegram Status Reports
Every run posts a clean, live update to Telegram showing:
* Systems connectivity (BRAIN API & DB).
* Live status across all 4 Groq and 4 OpenRouter keys.
* This run's processed and passed alphas.
* Today's and all-time cumulative analytics.

### 3. Real-Time Passed Alpha Alerts
As soon as any alpha clears all 5 stages, the bot instantly fires a dedicated **⭐ New Alpha Passed** alert containing the full winning mathematical formula, Sharpe, Fitness, Turnover, and optimal settings ready for direct submission.
