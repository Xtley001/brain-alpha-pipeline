# Cohen, Diether & Malloy (2007) + Engelberg, Reed & Ringgenberg (2012) + Rapach et al. (2016)

## Classification
- **Pillar:** Short Interest
- **Journals:** JF 2007 (CDM), JF 2012 (ERR), JFE 2016 (RRZ)
- **Datasets:** BRAIN short_interest fields (short_interest_ratio, etc.)
- **Alpha Yield Estimate:** 6 constructions × parameter grid = 180 archetypes
- **Novelty Score:** 8/10 — high-predictability signal, moderate dataset availability
- **Generator:** `brain_generators/short_interest/short_interest_p0_combined.py`

## Core Thesis — Cohen, Diether & Malloy (2007): Demand Shift
Standard empirical approaches confound **supply vs demand** for shorting. CDM separates them using proprietary data on loan fees (price) AND quantities (from a large institutional lender). Their identification strategy:
- `Fee ↑ + Quantity ↑` → DEMAND SHIFT OUTWARD (informed private shorting)
- `Fee ↑ + Quantity ↓` → SUPPLY SHIFT INWARD (lending constraint tightening)

**Key Result:** Shorting demand shifts predict **-2.98% abnormal return** the following month. Supply shifts have smaller, less reliable effects.

**Loan fee alone is NOT a sufficient statistic** — you need both price AND quantity to isolate demand from supply.

## Core Thesis — Engelberg, Reed & Ringgenberg (2012): Informed Shorts
Short sellers are specifically informed about **negative earnings surprises, analyst downgrades**, and other fundamental deterioration events. Their positions build 20+ days **before** the negative news hits. Short interest spikes are most informative when they occur **against the current analyst consensus** (i.e., short sellers disagree with the bullish crowd).

## Core Thesis — Rapach, Ringgenberg & Zhou (2016): Aggregate SI
Aggregate short interest negatively predicts **market-level** returns. At the stock level: high short interest ratio (shares shorted / shares outstanding) cross-sectionally predicts negative stock returns with t-stat > 4 across multiple decades.

## Core Thesis — Asquith, Pathak & Ritter (2005): Short Float + Inst. Ownership
The short-anomaly is **concentrated** in stocks where:
1. Short interest is HIGH (demand is present)
2. Institutional ownership is LOW (supply of lendable shares is constrained)

The combination creates maximum short-sale constraint → maximum pessimist exclusion → maximum overpricing.

## Signal Cards

### Signal 1: Short Interest Level (RRZ 2016 — Cross-Sectional)
**Formula:** `short_interest_ratio` (shares shorted / shares outstanding)
**Economic Logic:** High SIR reflects informed shorters' consensus negative view. Only trade the top 30% SIR stocks (lower tail has low signal/noise).
```python
trade_when(rank(short_interest_ratio) > 0.70,
    signed_power(rank(-ts_decay_linear(short_interest_ratio, D)), 0.5), -1)
```

### Signal 2: ΔShort Interest — Demand Shift (CDM 2007 Core Signal)
**Formula:** `ts_delta(short_interest_ratio, lookback)` for lookback = 10, 21, 42 days
**Economic Logic:** CHANGES in short interest are more informative than levels. Rising demand = informed shorts entering. Gate on top 35% of demand changes.
```python
trade_when(rank(ts_delta(short_interest_ratio, lookback)) > 0.65,
    rank(-ts_decay_linear(ts_delta(short_interest_ratio, lookback), D)))
```

### Signal 3: Informed Shorts × Earnings Surprise (ERR 2012 Mechanism)
**Formula:** `ΔShortInterest × negative(earnings_surprise)` — double-confirmation
**Economic Logic:** Short sellers are most informed when they're betting against positive analyst consensus. Combining rising SI with negative earnings surprise creates a dual-confirmed informed-flow signal.
```python
rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), D)) *
rank(-ts_decay_linear(earnings_surprise, D))
```

### Signal 4: Short Float × Low Institutional Ownership (APR 2005)
**Formula:** `short_interest_ratio × (1 - institutional_ownership_percentage)`
**Economic Logic:** Firms with high short interest AND low institutional ownership face maximum short-sale constraints — pessimists can't express negative views → maximum overpricing.
```python
trade_when(rank(short_interest_ratio) > 0.60,
    rank(-ts_decay_linear(short_interest_ratio, D)) *
    rank(-ts_decay_linear(institutional_ownership_percentage, D)))
```

### Signal 5: Days-to-Cover (Liquidity-Adjusted Constraint)
**Formula:** `short_interest_ratio / adv20` = how many days of average volume to cover all shorts
**Economic Logic:** High DTC = illiquid coverage → locked-in shorts → firm can't cover without market impact → amplified constraint → more overpriced.
```python
signed_power(rank(-ts_decay_linear(
    short_interest_ratio / (adv20 + 0.001), D)), 0.5)
```

## Key Empirical Benchmarks
| Signal | Expected Alpha |
|---|---|
| CDM 2007: ΔShortInterest (demand shift) | -2.98%/month |
| RRZ 2016: Short interest ratio | t-stat > 4 |
| ERR 2012: Informed shorts pre-earnings | Event window: -3% to -5% |
| APR 2005: High SI + low inst. ownership | -1.5%/month (concentrated in constrained stocks) |

## BRAIN Field Availability
| Field | Availability | Notes |
|---|---|---|
| `short_interest_ratio` | ✅ Available | Primary field |
| `institutional_ownership_percentage` | ✅ Available | For APR composite |
| `adv20` | ✅ Available | For DTC calculation |
| Direct loan fee | ❌ Not available | CDM's exact demand shift proxy not replicable |
| Direct quantity on loan | ❌ Not available | RRZ and CDM use proprietary data |

## Cross-Paper Synergies
- **Diether-Malloy-Scherbina (2002):** Analyst dispersion × short interest = amplified overpricing signal
- **Chen-Hong-Stein (2002):** Breadth of ownership (mutual fund holders) as complementary short-constraint proxy
- **Pan-Poteshman (2006):** Options PCR + rising short interest = cross-market informed-flow confirmation

## Implementation Status
- [x] Coded in `brain_generators/short_interest/short_interest_p0_combined.py`
- [x] 180 archetypes across 5 signal constructions
- [ ] Tested in miner
- [ ] Qualified alpha found
