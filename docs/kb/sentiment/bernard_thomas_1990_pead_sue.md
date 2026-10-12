# Bernard & Thomas (1990) + Chan, Jegadeesh & Lakonishok (1996) — SUE & PEAD

## Classification
- **Pillar:** Sentiment / Analyst
- **Journals:** JAE 1990 (Bernard-Thomas), JF 1996 (Chan-Jegadeesh-Lakonishok)
- **Datasets:** analyst (BRAIN analyst fields)
- **Alpha Yield Estimate:** 5 constructions × parameter grid = 94 archetypes
- **Novelty Score:** 8/10 — PEAD is one of the oldest/strongest anomalies in finance
- **Generator:** `brain_generators/sentiment/bernard_thomas_sue.py`

## Core Thesis — Bernard & Thomas (1990)
Stock prices **systematically under-react** to publicly announced earnings surprises. The drift continues for at least 6 months post-announcement. The sign and magnitude of the drift correlates with the autocorrelation structure of seasonal quarterly earnings — the market acts as if earnings follow a seasonal random walk when they demonstrably do not.

**Magnitude:** 18%/year annualized abnormal return (before transaction costs) in the first quarter post-announcement period.

**Critical Finding:** A disproportionate fraction of the drift is "delayed" until the **NEXT quarter's earnings announcement** — meaning the market fails to fully update Q+1 expectations when it receives Q's news.

## Core Thesis — Chan, Jegadeesh & Lakonishok (1996)
Both earnings momentum (SUE) and price momentum independently predict future returns. Their **combination** ("dual confirmation") is the strongest predictor — stocks with both positive earnings surprise AND positive price momentum have the highest subsequent returns.

Analyst estimate **revision momentum** (cumulative analyst upgrades over 6 months) is a third independent signal that combines additively with the other two.

## Exact Signal Formulas

### SUE Formula (Bernard & Thomas, Paper Equation, p. 308)
```
UE_{i,q}  = EPS_{i,q} - EPS_{i,q-4}              ← Year-over-year seasonal change
SUE_{i,q} = UE_{i,q} / σ(UE_{i,q}, last 8 qtrs)  ← Standardized by historical surprise std
```

**BRAIN Field Mapping:**
| Paper Variable | BRAIN Field | Notes |
|---|---|---|
| `UE_{i,q}` | `earnings_surprise` | Directly available |
| `σ(UE)` | (implied in earnings_surprise normalization) | Field is already standardized in most BRAIN configs |
| 6m price momentum | `ts_sum(returns, 126) - ts_sum(returns, 5)` | Skip 1-week reversal |
| Analyst revision | `analyst_rating_change` | Direction of revision |
| Revision momentum | `ts_sum(analyst_rating_change, 63)` | 3-month cumulative |

## Signal Cards

### Signal 1: Pure SUE (Paper Table 1 — Core PEAD)
```python
group_neutralize(
    signed_power(rank(ts_decay_linear(earnings_surprise, D)), 0.5),
    subindustry
)
```
**Notes:** Decay D = 10–30 days. Longer decay captures persistence up to 6m.

### Signal 2: SUE × Price Momentum — Dual Confirmation (CJL 1996 Sec. III)
```python
rank(ts_decay_linear(earnings_surprise, D)) *
rank(ts_sum(returns, 126) - ts_sum(returns, 5))
```
**Notes:** Both signals are independent predictors; multiplicative combination amplifies signal where both agree.

### Signal 3: Analyst Revision Momentum (CJL 1996 Sec. III.B — REV6)
```python
group_neutralize(
    signed_power(rank(ts_decay_linear(ts_sum(analyst_rating_change, 63), D)), 0.5),
    subindustry
)
```
**Notes:** 3-month cumulative revision. CJL find Sharpe ~1.4 standalone for this signal.

### Signal 4: PEAD Next-Quarter Delayed Drift (BT 1990 Key Finding)
**Economic Logic:** Market fails to update Q+1 estimates when it receives Q news. Use 63-day lagged earnings surprise as a proxy for loading up ahead of the next quarter.
```python
rank(ts_decay_linear(ts_delay(earnings_surprise, 63), D))
```

### Signal 5: SUE Gated on Low Analyst Dispersion (DMS 2002 Cross)
**Economic Logic:** In high-dispersion stocks, pessimists can't short → noise. PEAD signal is cleaner when analyst consensus is tight.
```python
trade_when(rank(analyst_estimate_dispersion) < 0.30,
    signed_power(rank(ts_decay_linear(earnings_surprise, D)), 0.5), -1)
```

## Key Empirical Results to Match
| Test | Benchmark |
|---|---|
| BT 1990: PEAD 1st quarter | +18%/yr abnormal return |
| BT 1990: PEAD persistence | 6+ months |
| CJL 1996: SUE standalone | +9.5%/yr |
| CJL 1996: Price momentum | +10.5%/yr |
| CJL 1996: Dual confirmation | +14.2%/yr |
| CJL 1996: REV6 analyst revision | Sharpe ~1.4 |

## Cross-Paper Synergies
- **Gleason & Lee (2002):** Revision speed complements PEAD — analyst revisions take time to propagate into price
- **DMS (2002):** Analyst dispersion gates PEAD — high-dispersion stocks have noisier SUE signal
- **Loh & Stulz (2018):** Regime conditioning — PEAD + analyst revision stronger in high-uncertainty periods
- **Barber & Odean (2008):** Attention stocks have attention-driven SUE reactions that overshoot — fade the attention overshoot

## Implementation Status
- [x] Coded in `brain_generators/sentiment/bernard_thomas_sue.py`
- [x] 94 archetypes across 5 signal constructions
- [ ] Tested in miner
- [ ] Qualified alpha found
