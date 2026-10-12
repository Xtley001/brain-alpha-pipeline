# Xing, Zhang & Zhao (2010) — Volatility Smirk

## Classification
- **Pillar:** Options
- **JFQA Full Title:** "What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?"
- **WorldQuant Datasets:** option8, option9
- **Alpha Yield Estimate:** 8 distinct signal constructions × parameter grid = 60+ archetypes
- **Novelty Score:** 9/10 — Core smirk paper, directly maps to BRAIN IV fields
- **Generator:** `brain_generators/options/xing_zhang_zhao_smirk.py`

## Core Thesis
Informed traders with negative private information prefer out-of-the-money (OTM) put options over direct short-selling because puts provide leverage and limit downside. This creates a persistent asymmetry in the implied volatility surface: OTM puts become expensive relative to ATM calls. The steepness of this slope (the "smirk") carries predictive information for future negative equity returns. The equity market is slow to incorporate this options-market signal.

**Magnitude (Table 3):** Top-quintile smirk stocks underperform bottom-quintile by **10.9% per year** on a risk-adjusted basis. Predictability persists for at least **6 months**.

## Key Variables / Data Fields (BRAIN Operator Mapping)

| Paper Variable | BRAIN Field | Notes |
|---|---|---|
| OTM Put IV (K/S ≈ 0.95) | `implied_volatility_put_{tenor}` | 30d, 60d, 90d, 180d tenors available |
| ATM Call IV (K/S ≈ 1.00) | `implied_volatility_call_{tenor}` | Matched tenor to put |
| Mean IV surface level | `implied_volatility_mean_{tenor}` | Used for normalization |
| SKEW_{i,t} | `implied_volatility_put_{t} - implied_volatility_call_{t}` | The primary signal |
| Normalized SKEW | `(put_iv - call_iv) / (mean_iv + epsilon)` | Eps = 0.001 to prevent div/0 |
| Time-scaled SKEW | `normalized_skew × sqrt(T/252)` | Annualizes the tenor component |

## Extracted Signal Cards

### Signal 1: Raw Smirk Slope (Paper's Primary Signal, Table 3)
**Economic Logic:** Higher IV on OTM puts vs ATM calls reveals informed put-buying pressure anticipating a negative price jump. Short stocks with the steepest smirk — they underperform by ~10.9%/yr.

**Construction:**
```
raw_smirk = implied_volatility_put_{T} - implied_volatility_call_{T}
signal    = rank(-ts_decay_linear(raw_smirk, D))
expression = group_neutralize(signed_power(signal, 0.5), subindustry)
```

**BRAIN Expression (with liquidity + tail gates):**
```python
trade_when(volume > adv20 * 0.90,
  trade_when(abs(rank(ts_decay_linear(
    (implied_volatility_put_{T} - implied_volatility_call_{T}), D
  )) - 0.5) > 0.25,
    group_neutralize(signed_power(rank(-ts_decay_linear(
      (implied_volatility_put_{T} - implied_volatility_call_{T}), D
    )), 0.5), subindustry),
  -1), -1)
```
- **Universe:** TOPSP500, TOP500, TOP1000
- **Decay:** 10–18 days
- **Expected Sharpe:** 1.2–1.8 (paper reports ~2.0 in portfolio sorts; BRAIN single-alpha lower)

### Signal 2: Normalized Smirk (Paper Eq. 2 Extension)
**Economic Logic:** Dividing by the ATM IV level strips out the overall volatility regime effect and isolates the pure shape/skew information content. More robust across high-vol and low-vol periods.

**Construction:**
```
normalized_smirk = (IV_put - IV_call) / (IV_mean + 0.001)
signal = rank(-ts_decay_linear(normalized_smirk, D))
```

**BRAIN Expression:**
```python
trade_when(volume > adv20 * 0.90,
  trade_when(abs(rank(ts_decay_linear(
    (implied_volatility_put_{T} - implied_volatility_call_{T}) / (implied_volatility_mean_{T} + 0.001), D
  )) - 0.5) > 0.25,
    group_neutralize(signed_power(rank(-ts_decay_linear(
      (implied_volatility_put_{T} - implied_volatility_call_{T}) / (implied_volatility_mean_{T} + 0.001), D
    )), 0.5), subindustry),
  -1), -1)
```

### Signal 3: Annualized (Time-Scaled) Smirk
**Economic Logic:** Multiplying by √(T/252) allows apples-to-apples comparison across 30d, 60d, 90d tenors — the time-normalization isolates the per-unit-time information content.

**Construction:**
```
annualized_smirk = normalized_smirk × sqrt(T/252)
```

### Signal 4: Smirk Change Momentum (Information Arrival Timing)
**Economic Logic:** The *rate of steepening* of the smirk captures the timing of when informed traders begin loading up on OTM puts — an earlier signal than the level itself.

**Construction:**
```
delta_smirk = ts_delta(normalized_smirk, lookback)
# Short stocks where smirk is rapidly steepening (delta_smirk > 0 → short)
signal = rank(-delta_smirk) conditioned on rank < 0.2 (only extremes)
```

### Signal 5: Term Structure of Smirk (30d - 90d Differential)
**Economic Logic:** When near-term smirk >> long-term smirk, informed traders anticipate an *imminent* catalyst (< 30 days), not long-term uncertainty. Higher precision, shorter holding period.

**Construction:**
```
ts_smirk_spread = norm_smirk(30d) - norm_smirk(90d)
signal = rank(-ts_decay_linear(ts_smirk_spread, D))
```

### Signal 6: Smirk × Earnings Proximity (Table 6 Extension)
**Economic Logic:** Paper finds smirk is most predictive ahead of earnings announcements (steepest smirks appear before worst earnings shocks). Gate the signal on proximity to earnings.

**Construction:**
```python
# Condition: within 20 days of expected earnings announcement
# Use ts_decay_linear to weight signals closer to earnings more heavily
trade_when(days_to_earnings < 20 AND days_to_earnings > 0,
  smirk_signal, -1)
```
*(Note: BRAIN may not have `days_to_earnings` directly — use `analyst_revision_date` proxy or unconditional)*

## Cross-Paper Synergies
- **Bali & Hovakimian (2009):** Combine smirk with VRP (realized - implied vol spread) for a two-dimensional options surface signal
- **Pan & Poteshman (2006):** Combine smirk with PCR (informed put-call volume) — both are options-market negative-flow signals, but orthogonal dimensions
- **Garleanu-Pedersen (2009):** When demand pressure is high for OTM puts (high delta-hedging cost), smirk signal is amplified
- **Bollerslev-Tauchen-Zhou (2009):** Variance risk premium is the aggregate version; smirk is the idiosyncratic version

## Implementation Status
- [x] Coded in `brain_generators/options/xing_zhang_zhao_smirk.py`
- [ ] Tested in miner
- [ ] Qualified alpha found
