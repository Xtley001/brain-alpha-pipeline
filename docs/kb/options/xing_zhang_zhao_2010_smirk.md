# Xing, Zhang & Zhao (2010) — Volatility Smirk
## "What Does Individual Option Volatility Smirk Tell Us About Future Equity Returns?"
### Journal of Financial and Quantitative Analysis, Vol. 45, No. 3, pp. 641–662

---

## ⚠️ SOURCE: Directly extracted from `docs/kb/extracted_text/Xing_Zhang_Zhao_Volatility_Smirk.txt`
> All formulas, statistics, and quotes below are drawn **verbatim** from the PDF extraction.
> Generator: `brain_generators/options/xing_zhang_zhao_smirk.py`

---

## EXTRACT 1: Abstract (verbatim)
> *"The shape of the volatility smirk has significant cross-sectional predictive power for future equity returns. Stocks exhibiting the steepest smirks in their traded options underperform stocks with the least pronounced volatility smirks in their options by around **10.9% per year** on a risk-adjusted basis. This predictability persists for **at least six months**, and firms with the steepest volatility smirks are those experiencing the **worst earnings shocks in the following quarter**."*
> *(Page 2, Abstract)*

---

## EXTRACT 2: Core Formula — Equation (1), the SKEW Measure (p.8)
> *"We calculate our implied volatility smirk measure for firm i at week t, SKEW_i,t, as the difference between the implied volatilities of OTM puts and ATM calls"*

```
SKEW_{i,t} = VOL^{OTM_PUT}_{i,t} − VOL^{ATM_CALL}_{i,t}

OTM Put definition:  strike/stock < 0.95 (but > 0.80)
ATM Call definition: 0.95 ≤ strike/stock ≤ 1.05
Tenor filter:        10 to 60 days to expiration
Selection:           choose ONE option closest to moneyness target
                     (ATM call: K/S closest to 1.0; OTM put: K/S closest to 0.95)
Time-averaging:      weekly SKEW = average of daily SKEW (Tue close to Tue close)
```

**BRAIN Field Translation:**
```
VOL^{OTM_PUT}  = implied_volatility_put_30   (30d tenor, closest to paper's 10-60d filter)
VOL^{ATM_CALL} = implied_volatility_call_30  (30d ATM call IV)
SKEW_BRAIN     = implied_volatility_put_30 - implied_volatility_call_30
```

---

## EXTRACT 3: FM Regression Equation (2) — Prediction Framework (p.11)
> *"The standard FM regression has two stages. In the first stage, we estimate the following regression in cross-section for each week t:*
> `RET_{i,t} = b_0t + b_1t × SKEW_{i,t-1} + b_2t × CONTROLS'_{i,t-1} + e_{it}`"

**Control variables used (Table 2 controls — must be aware of for clean isolation):**
1. `SIZE` — market cap (Banz 1981 size effect)
2. `BM` — book-to-market (Fama-French value)
3. `LRET` — past 6-month returns (Jegadeesh-Titman momentum)
4. `VOLSTOCK` — 1-month historical vol (AHXZ 2006)
5. `TURNOVER` — stock turnover (Lee-Swaminathan 2000)
6. `HSKEW` — 1-month historical skewness
7. `PCR` — put-call ratio (Pan-Poteshman 2006)
8. `PVOL` — ATM call IV minus historical vol (VRP)
9. Option volumes (all contracts)
10. Option open interests (all contracts)

**Key result:** After all 10 controls, SKEW coefficient = **−0.0089, t-stat = −3.86** *(Table 2, Panel A, p.13)*

**Inter-quartile magnitude:** (8.43% − 2.40%) × (−0.0089) = **−8.30 bps/week = −4.41%/year** *(p.13)*

---

## EXTRACT 4: Portfolio Sort Results — Table 3 (p.14-15)
> *"Each week, we sort all sample firms into quintile portfolios based on the previous week average skew (Tuesday close to Tuesday close). Portfolio 1 includes firms with the lowest skews, and portfolio 5 includes firms with the highest skews. We then skip one day and compute the value-weighted quintile portfolio returns for the next week (Wednesday close to Wednesday close)."*

**Long-short results (moneyness-based SKEW, Table 3 Panel A):**
| Portfolio | Weekly Excess Ret | Annualized | FF3 Alpha |
|---|---|---|---|
| Q1 (lowest SKEW) | +24 bps/week | +13.18%/yr | +10 bps/week |
| Q5 (highest SKEW) | +8 bps/week | +3.99%/yr | −11 bps/week |
| **Q1 − Q5 L/S** | **+16 bps/week** | **+9.19%/yr** | **+21 bps/week** |
| t-stat | −2.19 | — | **2.93** |
| **FF3 Alpha L/S annualized** | — | — | **+10.90%/yr** |

**Volume-weighted SKEW (Table 3 Panel B):**
- L/S FF3 alpha: **+10.06%/yr**, t-stat = 2.07
- 68 firms per quintile (vs 168 in moneyness-based)

---

## EXTRACT 5: Holding Period Persistence — Table 4 (p.17-19)
> *"For a holding period of one week, the alpha difference is 10.90%. The alpha difference drops to 6.52% when we extend the holding period to 4 weeks. For holding period returns from 8 to 28 weeks, the risk-adjusted returns for the long-short strategy stay between 6% and 7%. It declines further after week 28."*

**FM regression coefficient on SKEW at different horizons (Table 4 Panel A):**
| Horizon | SKEW Coefficient | Significance |
|---|---|---|
| Week t+1 | −0.0089 | *** |
| Week t+4 | significant | *** |
| Week t+8 | significant | *** |
| Week t+24 | −0.0038 | ** (weakens) |

**Decay of predictive power:**
- **1st-order autocorrelation of SKEW: 66%** → skew is persistent for ~3-4 weeks
- Skew spikes 2-3 weeks before peak → enters trades early
- After week 28: predictability fades

**Implementation rule:** Optimal holding period = **4–8 weeks**. Use decay window = 20–42 days in BRAIN.

---

## EXTRACT 6: Smirk vs Risk-Neutral Skewness — Table 6 (p.21-22)
> *"The cross-sectional correlation between volatility skew and risk neutral skewness is −29%."*
> *"Risk neutral skewness doesn't predict future returns."*
> *"Volatility skew and risk neutral skewness contain different information."*

**Critical distinction:**
- `SKEW (XZZ)` = simple OTM_PUT_IV − ATM_CALL_IV → **predicts returns (t = −3.86)**
- `RNSKEW (BKM)` = full model-free risk-neutral skewness → **does NOT predict returns**
- These are DIFFERENT signals — do NOT replace XZZ SKEW with BKM RNSKEW

---

## EXTRACT 7: When Informed Traders Choose Options (Section V.B, p.23-24)
> *"Informed traders would choose to trade in the options market if the options traded provide high leverage, and/or if there are many informed traders in the stock market, and/or the stock market for the particular firm is illiquid."*

**Equation (3) — Interaction specification:**
```
RET_{i,t} = b_0 + b_1 × SKEW + b_2 × SKEW × DELTA_OTM_PUT
           + b_3 × SKEW × PIN + b_4 × SKEW × TURNOVER + controls + e
```

**Signal amplifiers (SKEW is stronger when):**
1. **OTM put delta is more negative** (higher leverage → more informed traders choose puts)
2. **PIN (probability of informed trading) is HIGH** (more informed flow in stock → options used more)
3. **Stock turnover is LOW** (illiquid stock → informed prefer options)

**BRAIN Implementation — Amplified Smirk Signal:**
```python
# Amplified: smirk × low turnover (illiquid stocks → most informed flow in options)
skew_signal = implied_volatility_put_30 - implied_volatility_call_30
trade_when(rank(adv20 / market_cap) < 0.35,   # low turnover = informed choose options
    group_neutralize(rank(-ts_decay_linear(skew_signal, D)), subindustry), -1)
```

---

## EXTRACT 8: Smirk and Future Earnings (Section IV — Table 5, p.19-20)
> *"The earnings surprise variable, UE, is the difference between announced earnings and the latest consensus earnings forecast before the announcement."*
> *"For n = 12 weeks: the difference in UE between the lowest 20% and highest 20% of SKEW firms is **0.63 of a cent (p.752), t-stat = 3.04**."*
> *"Given the average size of UE to be 2 cents, the 0.63 cent difference is economically significant."*

**FM coefficients on SKEW predicting SUE (Table 5 Panel B):**
- Range: −0.033 to −0.045, significant for all horizons from week 4 to 24

**Combined signal: Steep smirk + upcoming earnings = double-confirmed short:**
```python
# Gate: earnings within 12 weeks + steep smirk
trade_when(rank(ts_decay_linear(implied_volatility_put_30 - implied_volatility_call_30, D)) > 0.75,
    group_neutralize(rank(-ts_decay_linear(earnings_surprise, D)), subindustry), -1)
```

---

## EXTRACT 9: Sample Statistics — Table 1 (p.9-10)
> Average SKEW: **mean = 6.40%, median = 4.76%**
> 25th percentile SKEW: **2.40%**
> 75th percentile SKEW: **8.43%**
> Average ATM call IV (VOLATMC): **47.95%**
> Average OTM put IV (VOLOTMP): **54.35%**
> Average firm size: **$10.22B** (large caps only!)
> Average monthly turnover: **24%**
> Average annualized vol: **47.14%**

**Universe implication:** Signal is for firms WITH traded options → naturally large-cap biased.
In BRAIN: use `TOPSP500` or `TOP500` universe primarily, not `TOP3000`.

---

## EXTRACT 10: Alternative SKEW Constructions (p.8, Footnotes 3 and 4)
> *"There are several alternative ways to measure moneyness: Bollen and Whaley (2004) use Black-Scholes delta to measure moneyness; Ni (2007) uses total volatility-adjusted strike-to-stock price ratio."*
> *"We find quantitatively similar results using these alternative moneyness measures."*
> *"We also consider volume-weighted, highest-volume, highest-OI, OI-weighted alternatives."*
> *"Our results are not sensitive to which SKEW measure we choose."*

**Alternative constructions (all tested robust in paper):**
| Construction | BRAIN Proxy |
|---|---|
| Moneyness-based (primary) | `implied_volatility_put_30 - implied_volatility_call_30` |
| Volume-weighted | Proxy: `pcr_vol_30` weighted smirk |
| 60d tenor | `implied_volatility_put_60 - implied_volatility_call_60` |
| 30d ATM call baseline | `implied_volatility_mean_30` |
| Delta-adjusted | Not available in BRAIN |

---

## EXTRACT 11: Double-Sort Confirmation (Footnote 8, p.15)
> *"We conduct double sort based on volume/open interest and volatility skew. Our goal is to see whether the long-short strategy works better for firms with more option trading (in terms of higher volume and larger open interest), and the results indicate that is the case."*

**Implementation:** Gate smirk signal on high option volume:
```python
trade_when(rank(pcr_oi_30 + pcr_vol_30) > 0.50,   # options actively traded
    group_neutralize(rank(-ts_decay_linear(
        implied_volatility_put_30 - implied_volatility_call_30, D)), subindustry), -1)
```

---

## EXTRACT 12: Moneyness Range Robustness (p.8, Footnote 3)
The exact moneyness ranges that define the signal:
- OTM put: `0.80 < K/S < 0.95` (centered at 0.95 = deepest tested put)
- ATM call: `0.95 ≤ K/S ≤ 1.05`

Any tenor between **10 and 60 days** to expiration is valid.

In BRAIN with `implied_volatility_put_{t}`, we have fixed tenor buckets (30d, 60d). The 30d bucket maps best to the paper's ~10-60d average.

---

## EXTRACT 13: Non-Synchronous Trading Fix (p.11)
> *"The options market closes at 4:02 p.m. for individual stock options, while the equity market closes at 4 p.m. Therefore, we skip one day between weekly returns and weekly volatility skews to avoid non-synchronous trading issues."*

**BRAIN implication:** The smirk signal should have a **1-day skip** built in. In BRAIN expressions, use `ts_delay(smirk, 1)` or rely on BRAIN's own data lag to ensure this. The current expressions use `ts_decay_linear(smirk, D)` which naturally weights recent data less.

---

## EXTRACT 14: SKEW vs PVOL Distinction (p.13)
> *"The coefficient on volatility premium, PVOL, is negative, which indicates firms with higher volatility premium have higher returns. However, the coefficient is insignificant."*
> *"PVOL = ATM_call_IV − historical_vol"*

- **SKEW (XZZ):** OTM_put_IV − ATM_call_IV → **significantly predicts returns**
- **PVOL (VRP):** ATM_call_IV − historical_vol → **NOT significant predictor**
- These are orthogonal: both can be in the same model (Table 2 includes PVOL as control and SKEW remains t = −3.86)

---

## EXTRACT 15: Negative SKEW Firms (Footnote 7, p.15)
> *"In our sample, 9.91% of observations have negative volatility skews. We also separate firms with positive skews and negative skews, and redo the portfolios sorting for firms with positive skews only. The return difference is very similar."*

**Implementation:** Filter `SKEW > 0` is not necessary — but gating on extreme SKEW (top quartile) gives cleaner results. Use `signed_power(rank(-SKEW), 0.5)` which handles negatives gracefully.

---

## CROSS-PAPER SYNERGIES
| Combine XZZ SKEW with | Why | Expected Enhancement |
|---|---|---|
| **Pan-Poteshman PCR** | Both capture options-informed flow; PP captures direction, XZZ captures fear | Double-confirmed informed negative |
| **Bernard-Thomas SUE** | XZZ predicts bad earnings (Table 5); combine with SUE for timing | Enter after surprise confirms what smirk predicted |
| **AHXZ Idiovol** | XZZ works independently of VOLSTOCK (Table 2 shows VOLSTOCK coefficient = n.s.) | No multicollinearity; combine freely |
| **BKM RNSKEW** | They contain DIFFERENT information (correlation = −29%); BOTH can be used | Orthogonal signals → additive alpha |
| **Lee-Swaminathan Turnover** | Smirk strongest in LOW turnover stocks (Section V.B) | Gate smirk on low-turnover universe |

---

## IMPLEMENTATION STATUS
- [x] `brain_generators/options/xing_zhang_zhao_smirk.py` — 5 base constructions, 228 archetypes
- [x] This KB covers 15 paper-exact extracts
- [ ] **Missing signals from paper:**
  - Interaction: SKEW × delta (Extract 7) — not yet in generator
  - Interaction: SKEW × PIN proxy (Extract 7) — not yet in generator  
  - Interaction: SKEW × low-turnover gate (Extract 7) — partially done
  - SKEW × pre-earnings gate (Extract 8) — not yet in generator
  - Volume-weighted SKEW variant (Extract 10) — using PCR proxy only
- [ ] Miner qualified alpha: 0 so far
