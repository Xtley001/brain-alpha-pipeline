# BRAIN Alpha Pipeline: Quality Boost & Calibration Guide (`boost.md`)

This document details the quantitative mechanics, operator grammar, Stage 0 calibration math, and prompt engineering strategies implemented to boost alpha generation quality and produce submittable WorldQuant BRAIN alphas (`Sharpe ≥ 1.25`, `Fitness ≥ 1.0`, `Turnover < 70%`, `MaxCorr < 0.70`).

---

## 1. The Calibration: Why Stage 0 Was Lowered

### The Multi-Stage Screening Funnel
The pipeline is designed as an inverted pyramid that balances simulation speed and parameter optimization:

$$\begin{matrix}
\textbf{Stage 0 (Quick Screen)} & \longrightarrow & 1\text{ Simulation (Fixed default settings: decay 8, subindustry)} \\
\textbf{Stage 1 (Grid Sweep)} & \longrightarrow & 30\text{ Simulations (6 Neutralizations } \times \text{ 5 Decays)} \\
\textbf{Stage 2 (Refinement)} & \longrightarrow & 4\text{ Simulations (Truncation } 0.01 \text{ to } 0.10) \\
\textbf{Stage 3 (Sensitivity)} & \longrightarrow & 6\text{ Simulations (Delay 0/1, Pasteurization, NaN)} \\
\textbf{Local Filter \& Corr} & \longrightarrow & \text{Final Gate: Sharpe } \ge 1.25, \text{ Fitness } \ge 1.0, \text{ Corr } < 0.70
\end{matrix}$$

### The Calibration Problem & Fix
* **The Problem**: Previously, Stage 0 required `Sharpe ≥ 0.50` and `Fitness ≥ 0.30` on **fixed default settings** (`decay=8, neutralization=SUBINDUSTRY`). However, an un-decayed or sector-neutral alpha often starts with raw Sharpe $0.35$ on default settings, but jumps to **$1.35 - 1.80$** once Stage 1 optimizes it across the 30-combo neutralization $\times$ decay grid.
* **The Calibrated Floor**:
  * **`STAGE0_MIN_SHARPE`**: **`0.35`** (was `0.50`)
  * **`STAGE0_MIN_FITNESS`**: **`0.20`** (was `0.30`)
* **The Result**: Viable raw economic signals pass Stage 0 into Stage 1, where the full 30-combination parameter grid finds their optimal decay and neutralization.

---

## 2. WorldQuant BRAIN Data Matrix & Operator Reference

Every generated formula must strictly use valid Fast Expression operators and standard USA Equities data fields.

### Valid Data Fields
| Data Field | Description | Type / Scale |
| :--- | :--- | :--- |
| `close` | Unadjusted closing price | Price (USD) |
| `open` | Unadjusted opening price | Price (USD) |
| `high` | Unadjusted session high | Price (USD) |
| `low` | Unadjusted session low | Price (USD) |
| `volume` | Daily share trading volume | Volume (Shares) |
| `vwap` | Volume-weighted average price | Price (USD) |
| `returns` | Daily 1-day percentage return | Return ratio |
| `cap` | Market capitalization | USD |
| `adv20` | 20-day average daily dollar volume | USD |
| `sharesout` | Shares outstanding | Count |

*(Note: Generic placeholders like `market_cap`, `pe_ratio`, `is_earnings_window`, or `is_turn_of_month` are invalid in Fast Expressions and have been completely replaced).*

---

### Valid Operators Palette

#### A. Cross-Sectional Operators
* `rank(x)`: Percentile rank across all stocks in universe $[0.0, 1.0]$.
* `group_neutralize(x, group)`: Demeans $x$ within its group (`sector`, `industry`, or `subindustry`).
* `group_rank(x, group)`: Percentile rank of $x$ strictly within its group.
* `group_zscore(x, group)`: Cross-sectional Z-score $(x - \mu_{\text{group}}) / \sigma_{\text{group}}$.
* `group_mean(x, weight, group)`: Weighted group average.

#### B. Time-Series Operators (lookback window $d$)
* `ts_rank(x, d)`: Time-series percentile rank over the last $d$ days.
* `ts_zscore(x, d)`: Time-series standardized score $(x - \text{mean}(x, d)) / \text{std}(x, d)$.
* `ts_decay_linear(x, d)`: Linearly weighted moving average with decay weights $[1, 2, \dots, d]$.
* `ts_delta(x, d)`: Difference $x_t - x_{t-d}$.
* `ts_delay(x, d)`: Historical lag $x_{t-d}$.
* `ts_std_dev(x, d)`: Moving standard deviation over $d$ days.
* `ts_mean(x, d)`: Moving arithmetic average over $d$ days.
* `ts_corr(x, y, d)`: Rolling Pearson correlation between $x$ and $y$.
* `ts_max(x, d)` / `ts_min(x, d)`: Rolling high / low over $d$ days.

#### C. Mathematical Transforms
* `signed_power(x, p)`: $\text{sign}(x) \cdot |x|^p$ (non-linear shape accentuation).
* `abs(x)`: Absolute value.
* `min(x, y)` / `max(x, y)`: Element-wise minimum / maximum.

---

## 3. High-Alpha Architectural Blueprints

Proven quantitative alpha expressions combine 2 or more complementary economic mechanisms:

### Blueprint 1: Volume Surge Mean-Reversion
* **Economic Thesis**: Short-term aggressive selling on abnormally heavy volume indicates liquidity exhaustion and overshooting, creating a sharp reversal opportunity.
* **Formula**:
  ```python
  group_neutralize(rank(-ts_zscore(close, 5)) * rank(volume / (adv20 + 0.001)), subindustry)
  ```

### Blueprint 2: Risk-Adjusted Momentum with Linear Decay
* **Economic Thesis**: Medium-term momentum is higher quality when normalized by idiosyncratic volatility, smoothed to eliminate high-frequency whipsaw noise.
* **Formula**:
  ```python
  group_neutralize(rank(ts_decay_linear(returns, 20) / (ts_std_dev(returns, 20) + 0.0001)), sector)
  ```

### Blueprint 3: Intraday Order-Flow Imbalance $\times$ Multi-Day Trend
* **Economic Thesis**: Strong buying pressure into the close ($(\text{close} - \text{open}) / (\text{high} - \text{low})$) combined with multi-day momentum signals institutional accumulation.
* **Formula**:
  ```python
  rank((close - open) / (high - low + 0.0001)) * rank(ts_delta(close, 5))
  ```

### Blueprint 4: VWAP Displacement with Volatility Filtering
* **Economic Thesis**: Large deviations from historical VWAP indicate price dislocations, with higher predictive Sharpe during calm/low-volatility regimes.
* **Formula**:
  ```python
  rank(ts_decay_linear((vwap - close) / close, 10)) * rank(-ts_std_dev(returns, 60))
  ```

### Blueprint 5: Volume-Price Divergence
* **Economic Thesis**: Rising prices accompanied by declining volume indicates momentum exhaustion and impending reversal.
* **Formula**:
  ```python
  group_neutralize(rank(ts_delta(close, 10)) * rank(-ts_delta(volume, 10)), industry)
  ```

---

## 4. Multi-Key AI Engine (Groq & OpenRouter)

The pipeline is powered by a 4-key Groq + 4-key OpenRouter rotation chain:

```
[Reasoning & Generation Request]
              │
              ▼
  ┌───────────────────────┐
  │      Groq Tier        │ (Keys 1-4: Fast mechanical & reasoning)
  │ (openai/gpt-oss-120b) │ 429 Rate-Limit -> Next key in rotation
  └───────────┬───────────┘
              │ (If all 4 Groq keys exhausted)
              ▼
  ┌───────────────────────┐
  │   OpenRouter Tier     │ (Keys 1-4: Fallback accounts)
  │ (llama-3.3-70b:free)  │ 429 Rate-Limit -> Next key in rotation
  └───────────────────────┘
```

* **Deduplication Engine**: Every newly generated candidate is checked against the database (`SELECT 1 FROM candidates WHERE expression = %s`) before insertion to prevent token waste.
* **Failure Memory**: The reasoning prompt receives a rolling log of recent failed expressions and specific failure reasons, instructing the model to explore distinct market mechanisms.

---

## 5. Summary of Final Acceptance Gates

An alpha is saved to `review_store` and alerted on Telegram only when it passes:
1. **Sharpe Ratio**: $\ge 1.25$
2. **Fitness**: $\ge 1.00$
3. **Turnover**: $1\% \le \text{Turnover} \le 70\%$
4. **Robustness**: Sweep variants also clearing the bar ($\ge 1$ robust variant)
5. **Correlation**: $\text{Max correlation} < 0.70$ vs existing accepted pool alphas.
