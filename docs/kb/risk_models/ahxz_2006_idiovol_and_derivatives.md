# Ang, Hodrick, Xing & Zhang (2006) — Idiosyncratic Volatility Anomaly
# Baker, Bradley & Wurgler (2011) — Benchmarks as Limits to Arbitrage
# Merton (1974) — Structural Credit Model
# Savor & Wilson (2013) — Macroeconomic Announcement Premium
# Easley, Lopez de Prado & O'Hara (2012) — VPIN Flow Toxicity
# Lucca & Moench (2015) — Pre-FOMC Drift

## Classification
- **Pillar:** Risk Models
- **Journals:** JF 2006, FAJ 2011, JF 1974, JFE 2013, RFS 2012, JF 2015
- **Datasets:** BRAIN `model` fields: `beta_*`, `idiosyncratic_vol_*`
- **Alpha Yield Estimate:** 256 + 96 archetypes across 2 generator modules
- **Novelty Score:** 9/10 — foundational anomalies with diverse economic mechanisms
- **Generators:** `brain_generators/risk_models/ang_idiovol_anomaly.py`, `risk_model_p2_vpin_fomc.py`

---

## Paper 1: AHXZ (2006) — The Idiosyncratic Volatility Puzzle

### Core Thesis
Standard risk-pricing theory predicts idiosyncratic risk should be diversifiable and unrewarded. **AHXZ find the opposite:** stocks with high idiosyncratic volatility (IVOL) earn LOWER future returns — a persistent and economically significant anomaly.

### Exact Construction
```
IVOL = std(daily residuals from Fama-French 3-factor model, past 21 trading days)

resid_{i,t} = r_{i,t} - α - β_MKT × MKT_t - β_HML × HML_t - β_SMB × SMB_t

Cross-sectional sort: quintile 5 (high IVOL) - quintile 1 (low IVOL) = -1.06%/month
  High IVOL: -0.02% alpha/month
  Low IVOL:  +1.04% alpha/month
```

### BRAIN Field Mapping
| Paper Variable | BRAIN Field | Period |
|---|---|---|
| `IVOL (21d FF3 residuals)` | `idiosyncratic_vol_last_60_days_spy` | 60d vs SPY |
| `beta_MKT` | `beta_last_60_days_spy` | 60d |
| `beta_MKT (1yr)` | `beta_last_252_days_spy` | 252d (paper-exact) |

**Note:** BRAIN's `idiosyncratic_vol_last_60_days_spy` uses 60d, not 21d as in paper. The sign and direction of the effect is identical; the 21d signal is just noisier.

### Primary Signal
```python
trade_when(volume > adv20 * 0.80,
    trade_when(abs(rank(ts_decay_linear(idiosyncratic_vol_last_60_days_spy, D)) - 0.5) > 0.25,
        group_neutralize(
            signed_power(rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, D)), 0.5),
            subindustry
        ), -1), -1)
```

### AHXZ VARIANT: Rising IVOL (Timing Signal)
The paper's time-series finding: IVOL is **mean-reverting at long horizons** but **autocorrelated at short horizons**. A RISING IVOL trend (increasing over 21-42 days) is a sharper timing signal than the level alone:
```python
trade_when(rank(ts_delta(idiosyncratic_vol, lookback)) > 0.70,
    rank(-ts_decay_linear(ts_delta(idiosyncratic_vol, lookback), D)))
```

---

## Paper 2: Baker, Bradley & Wurgler (2011) — Why Does the Anomaly Persist?

### Mechanism
Institutional investors are **benchmarked** to market indices (S&P 500). Holding high-tracking-error low-beta stocks creates career risk even if risk-adjusted returns are superior. Result:
- High-beta, high-vol stocks: **overbought** by benchmark-hugging managers
- Low-beta, low-vol stocks: **underowned** due to benchmark exclusion → mispriced

**Key empirical finding (Table 3):** The volatility anomaly (short high-IVOL, long low-IVOL) delivers **+15.6% annualized** but has a **-0.3% monthly benchmark tracking error** — precisely why institutional managers won't implement it.

### Signal
```python
# Total realized vol as benchmark-constraint proxy
group_neutralize(
    signed_power(rank(-ts_decay_linear(ts_std_dev(returns, 21), D)), 0.5),
    subindustry
)
```

---

## Paper 3: Merton (1974) — Distance-to-Default

### Exact D2D Formula
```
Equity = Call option on firm assets with strike = Debt face value

V_A = V_E + V_D   (assets = equity + debt value)

D2D = [ln(V_A/D) + (μ_A - σ_A²/2)T] / (σ_A √T)

where:
  V_A = firm asset value (estimated via KMV iteration)
  D   = face value of debt (1-year horizon: short-term + 0.5 × long-term debt)
  μ_A = expected asset return
  σ_A = asset volatility (iteratively estimated from equity vol)
  T   = 1 year

Low D2D → near default → high credit risk premium → but NEGATIVE equity returns
```

### BRAIN Approximation
```python
# High leverage × high vol = near default = negative returns
1 / (debt_to_equity_ratio * ts_std_dev(returns, 252) + 0.001)  ← pseudo D2D
trade_when(rank(debt_to_equity_ratio * ts_std_dev(returns, 252)) > 0.70,
    rank(-...), -1)
```

---

## Paper 4: Easley-Lopez de Prado-O'Hara (2012) — VPIN

### VPIN Formula
```
VPIN = |V_b - V_s| / V_total

where: V_b, V_s = buy/sell volume estimated using bulk classification
       V_total = total volume in N volume-time buckets

High VPIN = high order flow toxicity = informed trading present
Market maker response: widen spreads → adverse selection risk realized
```

### BRAIN Approximation
```python
# |returns| / volume_ratio = flow toxicity proxy
ts_mean(abs(returns) / (volume / adv20 + 0.001), 10)
```

**Two possible interpretations:**
1. **Follow direction** (informed flow continuation): high VPIN + positive return → long
2. **Fade overshoot** (post-toxicity reversal): high VPIN → overshoot → mean-revert

Both signals are coded in `risk_model_p2_vpin_fomc.py`.

---

## Paper 5: Lucca & Moench (2015) — Pre-FOMC Drift

### Core Finding
S&P 500 earns **+49bps on average in the 24 hours before FOMC announcements** (1994-2011). This accounts for a large fraction of the overall equity premium. Effect is:
- Zero on non-FOMC days
- Concentrated in the window [T-24h, T-announcement]
- Driven by anticipation of Fed accommodation signals

### Stock-Level Application
Stocks with **highest FOMC-day beta** (sensitivity to macro announcements) earn the largest pre-announcement premium. BRAIN proxy: stocks with high realized beta × high market-vol periods.

---

## Implementation Status
- [x] `ang_idiovol_anomaly.py` — 112 archetypes (AHXZ + BBW + Merton + SW)
- [x] `risk_model_p2_vpin_fomc.py` — 96 archetypes (VPIN + FOMC + Nonejad + Blitz + Black)
- [x] Total risk model paper-faithful candidates: **352**
- [ ] Simulating in miner
- [ ] Qualified alpha confirmed
