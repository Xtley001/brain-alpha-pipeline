# Pan & Poteshman (2006) — Informed Put-Call Ratio
# Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing
# Bali & Hovakimian (2009) — Volatility Spreads
# Bakshi, Kapadia & Madan (2003) — Risk-Neutral Skew Laws

## Classification
- **Pillar:** Options
- **Journals:** RFS 2006 (PP), RFS 2009 (GPP), Management Science 2009 (BH), RFS 2003 (BKM)
- **Datasets:** BRAIN `options` fields: `pcr_vol_{tenor}`, `pcr_oi_{tenor}`, `implied_volatility_{call/put/mean}_{tenor}`
- **Alpha Yield Estimate:** 3 constructions × parameter grid = 348 archetypes (PCR module)
- **Novelty Score:** 9/10 — options-informed flow is among the most predictive signals available
- **Generator:** `brain_generators/options/pan_poteshman_pcr_informed.py`

---

## Paper 1: Pan & Poteshman (2006) — The Information in Option Volume

### Core Thesis
The PCR computed from **open-buy orders** placed by **public customers** (not market makers or firm proprietary traders) predicts next-day stock returns.

**Key Insight:** Standard PCR aggregates all trades. PP decompose by:
- **Order type:** Open vs. Close (open-buy = initiating new position = directional bet)
- **Account type:** Public customer (informed) vs. Firm account (market making noise)

**Magnitude:** Bottom-quintile PCR stocks (most bullish flow) outperform top-quintile by **+40bps next trading day**.

### Exact Formula
```
PCR_informed = Put_Open_Buy_Vol / (Put_Open_Buy_Vol + Call_Open_Buy_Vol)

Low PCR → net call buyers (bullish informed) → positive next-day returns
High PCR → net put buyers (bearish informed) → negative next-day returns
```

### BRAIN Field Mapping
| Paper Field | BRAIN Field | Notes |
|---|---|---|
| `Put_Open_Buy_Vol` | (embedded in) `pcr_vol_{t}` | BRAIN PCR uses all customer volume |
| `Call_Open_Buy_Vol` | (embedded in) `pcr_vol_{t}` | Decomposition not available |
| `PCR_informed` | `pcr_vol_{t}` | Best available proxy |
| `PCR_OI` | `pcr_oi_{t}` | OI-based version (less noisy) |

### Signal Cards
```python
# Signal 1: Raw PCR Rank (Table 3, Column 1)
group_neutralize(signed_power(rank(-ts_decay_linear(pcr_vol_30, D)), 0.5), subindustry)

# Signal 2: PCR × Volume Urgency (PP Mechanism)
trade_when(rank(pcr_vol_30 / (pcr_oi_30 + 0.001)) < 0.25,
    group_neutralize(rank(-ts_decay_linear(pcr_vol_30, D)), subindustry), -1)
```

---

## Paper 2: Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing

### Core Thesis
End-user demand pressure forces market makers to warehouse un-hedgeable jump and volatility risk. Options are **overpriced when demand surges** relative to the underlying price movement, because market makers charge a premium to take on the unhedgeable risk.

**Prediction:** When OI builds WITHOUT underlying price movement → dealers are accumulating inventory → IV elevated above fair value → **mean-revert as inventory clears**.

### Signal Card
```python
# OI Inventory Pressure (GPP Equation 3 Mechanism)
ts_delta(pcr_oi_30, 5) / (ts_std_dev(returns, 20) + 0.001)
# → High delta_OI in quiet market = inventory building = IV premium → short IV
group_neutralize(signed_power(rank(-ts_decay_linear(..., D)), 0.5), sector)
```

---

## Paper 3: Bali & Hovakimian (2009) — Volatility Spreads

### Core Thesis
Three principal components of the volatility term structure have independent predictive power:
- **PC1 (level):** Uncorrelated with returns — pure vol level has no predictive power
- **PC2 (RV−IV spread = VRP):** **POSITIVE** predictor — high VRP = large insurance demand = positive risk premium earned by vol sellers
- **PC3 (Call IV − Put IV):** **POSITIVE** predictor — upward-sloping call-put spread = bullish expectation tilt

### Key Distinction from XZZ
- **XZZ Smirk (PUT IV − CALL IV):** NEGATIVE predictor (put premium = informed downside fear)
- **BH PC3 (CALL IV − PUT IV):** POSITIVE predictor (directional expectation, separate mechanism)
- These are DIFFERENT signals — XZZ isolates crash risk, BH PC3 isolates directional bias

---

## Paper 4: Bakshi, Kapadia & Madan (2003) — Skew Laws

### Core Thesis
Full model-free derivation of risk-neutral moments from the entire option chain:

```
W(τ) = ∫ [2(1-ln(K/F)) / K²] × C(τ,K) dK  ← second moment integrand
X(τ) = ∫ [6ln(K/F) - 3ln²(K/F)] / K² × C(τ,K) dK  ← third moment integrand

RNSK = [e^{rτ}X(τ) - 3μW(τ) + 2μ³] / [e^{rτ}W(τ) - μ²]^{3/2}
```

**Key empirical finding:** High RNSK (expensive OTM calls relative to puts) → **negative future returns**. This is the model-free justification for the smirk signal.

### BRAIN Approximation
```python
# BKM RNSK proxy: smirk × realized vol scaling
(put_iv - call_iv) / mean_iv * (1 + 2 * realized_vol_60d)
```

---

## Cross-Signal Synergies
| Paper 1 | Paper 2 | Combined Signal |
|---|---|---|
| PP: Low PCR (bullish) | GPP: High OI delta (urgency) | Informed bullish + building urgency |
| BH: Positive VRP | CW: Large VRP | Both confirm insurance premium harvest |
| BKM: High RNSK | XZZ: Steep smirk | Double-confirmed downside protection demand |

## Implementation Status
- [x] Coded in `brain_generators/options/pan_poteshman_pcr_informed.py`
- [x] 348 archetypes (4 constructions × universe × neutralization × tenor × decay)
- [ ] Simulating in miner
- [ ] Qualified alpha confirmed
