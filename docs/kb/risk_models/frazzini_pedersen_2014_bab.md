# Frazzini & Pedersen (2014) — Betting Against Beta

## Classification
- **Pillar:** Risk Models
- **Journal:** Journal of Finance (2014), NBER WP 16601
- **Datasets:** model51, model52 (BRAIN beta fields)
- **Alpha Yield Estimate:** 5 constructions × parameter grid = 144 archetypes
- **Novelty Score:** 9/10 — foundational low-vol anomaly with AQR-grade pedigree
- **Generator:** `brain_generators/risk_models/frazzini_pedersen_bab_exact.py`

## Core Thesis
Leverage-constrained investors (pension funds, mutual funds, regulated entities) cannot use leverage to amplify returns. Instead they **tilt toward high-beta assets** to get more return per dollar invested. This tilting bids up high-beta assets and depresses their risk-adjusted returns. Conversely, low-beta assets are under-demanded, underpriced, and earn **excess risk-adjusted returns** when held leveraged to beta=1.

**The BAB Factor:** Long low-beta (leveraged to β=1) + Short high-beta (de-leveraged to β=1) = zero-net-beta, positive-return portfolio.

**Magnitude:** U.S. BAB Sharpe = **0.75** from 1926–2009 (vs. HML = 0.43, momentum = 0.61). Significant in all 20 global equity markets tested.

## Exact Beta Construction (Paper Section II)

```
beta_raw = corr(r_i, r_m) × (σ_i / σ_m)

where:
  corr(r_i, r_m)  = rolling 1-year correlation of daily stock vs market returns
  σ_i             = rolling 1-year std dev of daily stock returns
  σ_m             = rolling 1-year std dev of daily market returns

Shrinkage toward cross-sectional mean (reduces estimation noise):
  beta_shrunk = 0.6 × beta_raw + 0.4 × 1.0

Cross-sectional z-score (paper uses this for portfolio weights):
  z_beta = (beta_shrunk - mean(beta)) / std(beta)
```

**BRAIN Field Mapping:**
| Paper Variable | BRAIN Field | Notes |
|---|---|---|
| `beta_raw` | `beta_last_60_days_spy` | 60d rolling vs SPY |
| `beta_raw` | `beta_last_90_days_spy` | 90d rolling (closer to paper's 252d) |
| `beta_raw` | `beta_last_252_days_spy` | 252d rolling (paper-exact) |
| `sigma_i` | `idiosyncratic_vol_last_60_days_spy` | proxy |

## Extracted Signal Cards

### Signal 1: Raw BAB Cross-Sectional Beta Rank (Paper Table 1 — Primary)
**Economic Logic:** Short high-beta (constrained investor overbid), long low-beta (underloved). Within subindustry to strip sector effects.

```python
group_neutralize(
    signed_power(rank(-ts_decay_linear(beta_last_90_days_spy, D)), 0.5),
    subindustry
)
```

### Signal 2: Beta × Reversal (Paper Table 2)
**Economic Logic:** BAB returns are stronger after high-beta stocks have recently underperformed — timing the constraint relaxation cycle.
```python
rank(-ts_decay_linear(beta_last_60_days_spy, D)) * rank(-ts_delta(close, 5))
```

### Signal 3: Shrunk Beta Z-Score (Paper Section II.B — Exact Construction)
**Economic Logic:** Shrinkage reduces beta estimation noise, giving a cleaner z-score ranking.
```
shrunk_beta = 0.6 × beta_last_90_days_spy + 0.4 × 1.0
signal = rank(-shrunk_beta)
```

### Signal 4: AHXZ Idiovol Companion (Paper Footnote 2)
**Economic Logic:** BAB holds controlling for idiovol. Standalone idiovol signal (AHXZ 2006): high idiovol → negative future returns. Orthogonal to BAB.

### Signal 5: Liquidity Regime Gate (Paper Section IV.B)
**Economic Logic:** BAB underperforms when funding constraints tighten (TED spread high). Only activate BAB when beta dispersion is wide (constraints loose).
```python
trade_when(ts_rank(ts_std_dev(beta, 60), 252) > 0.40, bab_signal, -1)
```

## Key Paper Tables to Replicate
- **Table 1:** Portfolio sorted by beta → monotonically declining alpha. Long-short = BAB factor.
- **Table 2:** BAB alpha controlling for Fama-French 5 factors — remains significant (t=7.4)
- **Table 3:** BAB across 20 global markets — persistent everywhere
- **Table 5:** BAB × TED spread regime — negative relationship confirmed

## Cross-Paper Synergies
- **Baker-Bradley-Wurgler (2011):** Explains WHY BAB works — benchmark-constrained managers avoid low-beta stocks
- **AHXZ (2006):** Companion anomaly — orthogonal but reinforcing (BAB × idiovol combo)
- **Merton (1974):** BAB conditional on distance-to-default gate — exclude near-distress stocks from low-beta long leg

## Implementation Status
- [x] Coded in `brain_generators/risk_models/frazzini_pedersen_bab_exact.py`
- [x] 144 archetypes generated (5 signal constructions × universe × neutralization × decay)
- [ ] Tested in miner
- [ ] Qualified alpha found
