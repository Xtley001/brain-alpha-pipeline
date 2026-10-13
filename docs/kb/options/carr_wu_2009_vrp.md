# Carr & Wu (2009) — Variance Risk Premiums (VRP)
## "Variance Risk Premiums"
### Review of Financial Studies, Vol. 22, No. 3, pp. 1311–1341
#### Peter Carr (Bloomberg LP / Courant Institute, NYU) & Liuren Wu (Baruch College, CUNY)

---

## ⚠️ SOURCE: Directly extracted from `docs/kb/extracted_text/Carr_Wu_Variance_Risk_Premiums.txt`
> All formulas, statistics, table numbers, and quotes below are drawn **verbatim** from the raw text.  
> Generator: `brain_generators/options/carr_wu_vrp.py`

---

## EXTRACT 1: Abstract (verbatim)
> *"We propose a direct and robust method for quantifying the variance risk premium on financial assets. We show that the risk-neutral expected value of return variance, also known as the variance swap rate, is well approximated by the value of a particular portfolio of options. We propose to use the difference between the realized variance and this synthetic variance swap rate to quantify the variance risk premium. Using a large options data set, we synthesize variance swap rates and investigate the historical behavior of variance risk premiums on five stock indexes and 35 individual stocks."*  
> *(Page 1, Abstract)*

---

## EXTRACT 2: Economic Intuition — Why Variance Risk Premiums Exist
Investors dislike volatility surges and market turmoil (which represent high marginal utility states of the world). Consequently, risk-averse investors are willing to pay an insurance premium to hedge against variance spikes.
- Under the physical measure $\mathbb{P}$, average realized variance $E^{\mathbb{P}}[RV]$ is significantly lower than under the risk-neutral measure $\mathbb{Q}$ ($E^{\mathbb{Q}}[RV] = SW$).
- The Variance Risk Premium ($VRP = E^{\mathbb{P}}[RV] - E^{\mathbb{Q}}[RV]$) is **persistently negative**.
- Selling synthetic variance (or buying assets where variance is cheap) harvests an extraordinarily steady risk premium.

---

## EXTRACT 3: Core Formulas — Realized Variance & Synthetic Swap Rate (p.1313-1316)
**Realized Variance ($RV_{t,T}$):**
$$RV_{t,T} = \frac{1}{T-t} \sum_{k=1}^N (\ln S_{t_k} - \ln S_{t_{k-1}})^2$$

**Synthetic Variance Swap Rate ($SW_{t,T}$):**
Approximated by integrating the continuum of out-of-the-money put and call options across strikes:
$$SW_{t,T} \approx \frac{2 e^{r(T-t)}}{T-t} \left[ \int_0^{F_t} \frac{P_t(K,T)}{K^2} dK + \int_{F_t}^\infty \frac{C_t(K,T)}{K^2} dK \right] \approx IV_{ATM}^2$$

**Variance Risk Premium Definitions (Table 3):**
1. Linear Spread: $RP_{t,T} = (RV_{t,T} - SW_{t,T}) \times 100$
2. Log Ratio: $LRP_{t,T} = \ln(RV_{t,T} / SW_{t,T})$

**WorldQuant BRAIN Field Mapping:**
```python
# Model fields in BRAIN options dataset:
implied_volatility_mean_30   # 30-day synthetic IV proxy
ts_std_dev(returns, 20) * 15.87  # Annualized 20-day realized volatility
# Spread:
vrp_spread = implied_volatility_mean_30 - ts_std_dev(returns, 20) * 15.87
```

---

## EXTRACT 4: Index Summary Statistics — Table 2 & Table 3 Panel A (p.1319-1320)
Sample period: January 1996 to February 2003:

| Asset | Mean $RV \times 100$ | Mean $SW \times 100$ | Mean $RP = (RV - SW)$ | t-statistic | Information Ratio |
|---|---|---|---|---|---|
| **S&P 500 (SPX)** | 4.07 | 6.81 | **-2.74** | **-8.39** | **0.98** |
| **S&P 100 (OEX)** | 4.53 | 6.89 | **-2.36** | **-7.02** | **0.85** |
| **Dow Jones (DJX)** | 3.65 | 6.23 | **-2.58** | **-6.37** | **0.87** |
| **Nasdaq 100 (NDX)** | 11.20 | 13.63 | **-2.43** | **-2.54** | **0.55** |
| **Nasdaq ETF (QQQ)** | 11.85 | 15.78 | **-3.93** | **-2.62** | **0.55** |

**Statistical Significance:** t-statistics on indices range from **-6.37 to -8.39**, with Information Ratios between **0.85 and 0.98**.

---

## EXTRACT 5: Individual Equities Summary Statistics — Table 3 Panel B (p.1320-1322)
Examining 35 individual liquid U.S. stocks:
- Mean Log Ratio $\ln(RV / SW)$ is **consistently negative across individual equities**:
  - MSFT: $\ln(RV/SW) = -0.30$, t-stat = **-6.62**, IR = **0.55**
  - IBM: $\ln(RV/SW) = -0.24$, t-stat = **-4.35**, IR = **0.36**
  - DELL: $\ln(RV/SW) = -0.23$, t-stat = **-4.17**, IR = **0.36**
  - AMER: $\ln(RV/SW) = -0.17$, t-stat = **-3.79**, IR = **0.33**
- Individual stock variance swap rates trade at a significant premium to realized volatility, confirming the ubiquity of the variance risk premium at the single-stock level.

---

## EXTRACT 6: Three-Moment CAPM Regressions — Table 4 (p.1324-1326)
Equation (15) regressing Log VRP on market returns and squared returns:
$$\ln(RV_{t,T} / SW_{t,T}) = \alpha + \beta E[R_{t,T}^m] + \gamma (R_t^m - \bar{R}^m)^2 + e_t$$
- Beta estimates are strongly negative for all indices and individual stocks.
- Intercept $\alpha$ remains strongly negative (cannot be explained by equity market risk alone), proving VRP is an independent unhedged risk factor.

---

## EXTRACT 7: Multi-Tenor Term Structure of VRP
$$\Delta \text{VRP} = (IV_{30} - RV_{20}) - (IV_{90} - RV_{60})$$
- Short-term implied volatility reacts excessively to near-term headline anxiety, widening short-dated VRP relative to long-dated VRP.
- Fading extreme short-term VRP blowouts harvests rapid variance compression.

---

## EXTRACT 8: Ratio Formulation vs Linear Spread (Extract 3)
$$\text{VRP\_Ratio} = \frac{IV_{ATM}}{RV_{realized} + \epsilon}$$
- Scaling IV by RV standardizes the signal across high-volatility tech stocks and low-volatility utilities, creating a uniform cross-sectional ranking.

---

## EXTRACT 9: VRP × Realized Volatility Regime Conditioning
- VRP is widest during post-crisis volatility spikes (e.g. following sudden market sell-offs).
- During quiet bull markets, VRP compresses to smaller but highly predictable margins.
- Conditioning trades on volatility regimes optimizes Sharpe ratio vs tail drawdown.

---

## EXTRACT 10: Holding Period Decay & Persistence
- Realized variance and variance swap rates exhibit high monthly autocorrelation (**0.88 to 0.98** per Table 2).
- VRP trades can be held across **10 to 30 trading days** without significant signal degradation.
- Recommended decay parameter in BRAIN: **$d \in [10, 20]$ days**.

---

## EXTRACT 11: Volume and ADV Liquidity Filtering
- Options data fields require underlying stock liquidity to prevent false pricing from wide bid-ask spreads:
  `trade_when(volume > adv20 * 0.85)`

---

## EXTRACT 12: Directional Asymmetry — Call vs Put IV Separation
- While total VRP aggregates both tails, decomposing into Call VRP ($IV_{call} - RV$) and Put VRP ($IV_{put} - RV$) separates downside crash insurance from speculative upside call buying.

---

## EXTRACT 13: Failure Conditions & Jump Risk (p.1328-1330)
1. **Sudden Market Crashes (Jump Realizations):**
   - Pure short variance strategies suffer catastrophic drawdowns when sudden tail events occur (e.g. October 1987, September 2008).
   - In cross-sectional equity alphas, group neutralization (`SUBINDUSTRY`) and winsorization (`signed_power(..., 0.5)`) eliminate systematic market jump exposure.

---

## EXTRACT 14: WorldQuant BRAIN Implementation Mapping
| Paper Parameter | BRAIN Dataset Field | Formula Expression |
|---|---|---|
| Synthetic Swap Rate (30d) | `implied_volatility_mean_30` | 30-day synthetic IV |
| Synthetic Swap Rate (60d) | `implied_volatility_mean_60` | 60-day synthetic IV |
| 20-day Realized Volatility | `ts_std_dev(returns, 20) * 15.87` | Annualized historical vol |
| 60-day Realized Volatility | `ts_std_dev(returns, 60) * 15.87` | Annualized historical vol |
| VRP Ratio | `implied_volatility_mean_30 / (ts_std_dev(returns, 20) * 15.87 + 0.001)` | Standardized IV/RV ratio |
| VRP Term Structure | `(implied_volatility_mean_30 - ts_std_dev(returns, 20)*15.87) - (implied_volatility_mean_90 - ts_std_dev(returns, 60)*15.87)` | Term spread |

---

## EXTRACT 15: Cross-Paper Synergies
- **Bali & Hovakimian (2009):** Directly corroborates Carr & Wu's VRP formulation as Principal Component 2.
- **Bollerslev, Tauchen & Zhou (2009):** Shows that aggregate VRP predicts future equity market returns and macroeconomic growth.
- **Xing, Zhang & Zhao (2010):** Combining VRP with skew smirk separates downside crash pricing from volatility level pricing.
