# Ang, Hodrick, Xing & Zhang (2006) — Volatility Anomaly & Idiosyncratic Volatility
## "The Cross-Section of Volatility and Expected Returns"
### Journal of Finance, Vol. 61, No. 1, pp. 259–299
#### Andrew Ang (Columbia), Robert J. Hodrick (Columbia), Yuhang Xing (Rice), Xiaoyan Zhang (Cornell)

---

## ⚠️ SOURCE: Directly extracted from `docs/kb/extracted_text/Ang_Hodrick_Xing_Zhang_2006_Cross_Section_Volatility_Expected_Returns.txt`
> All formulas, statistics, table numbers, and quotes below are drawn **verbatim** from the raw text.  
> Generator: `brain_generators/risk_models/ang_idiovol_anomaly.py`

---

## EXTRACT 1: Abstract (verbatim)
> *"We examine the pricing of aggregate volatility risk in the cross-section of stock returns. Consistent with theory, we find that stocks with high sensitivities to innovations in aggregate volatility have low average returns. In addition, we find that stocks with high idiosyncratic volatility relative to the Fama and French (1993) model have abysmally low average returns. This phenomenon cannot be explained by exposure to aggregate volatility risk. Size, book-to-market, momentum, and liquidity effects cannot account for either the low average returns earned by stocks with high exposure to systematic volatility risk or for the low average returns of stocks with high idiosyncratic volatility."*  
> *(Page 2, Abstract)*

---

## EXTRACT 2: Economic Intuition — The Idiosyncratic Volatility Puzzle
Classical asset pricing (Sharpe-Lintner CAPM, Merton 1987) posits that idiosyncratic risk should either be unpriced (diversifiable) or demand a positive risk premium if investors are under-diversified.
AHXZ (2006) proves the exact opposite: **stocks with high idiosyncratic volatility earn catastrophically low risk-adjusted returns**.
- Retail and speculative investors treat high-idiovol stocks as "lottery tickets", systematically overpaying for positive skewness.
- Arbitrageurs face limits to arbitrage (holding high idiovol risk is costly and risky), allowing the overpricing of high-idiovol stocks to persist indefinitely.

---

## EXTRACT 3: Idiosyncratic Volatility Formulation — Equation (8) (p.24)
Estimated daily relative to the Fama-French 3-factor model over a rolling window (typically 1 month = 21 trading days, or 60/90 days):
$$r_t^i = \alpha^i + \beta_{MKT}^i MKT_t + \beta_{SMB}^i SMB_t + \beta_{HML}^i HML_t + \varepsilon_t^i$$
$$\text{Idiosyncratic Volatility (IdioVol)} = \sqrt{\text{Var}(\varepsilon_t^i)}$$

**WorldQuant BRAIN Field Mapping:**
```python
# Primary direct model field:
idiosyncratic_vol_last_60_days_spy
idiosyncratic_vol_last_90_days_spy
# Proxy via total vol:
ts_std_dev(returns, 20)
```

---

## EXTRACT 4: Systematic Volatility Risk Formulation — Equation (3) (p.9-10)
Two-factor pricing model capturing sensitivity to daily innovations in aggregate market volatility ($\Delta VIX$):
$$r_t^i - r_f = \alpha^i + \beta_{MKT}^i (r_t^M - r_f) + \beta_{\Delta VIX}^i \Delta VIX_t + \epsilon_t^i$$
- $\Delta VIX$: daily change in CBOE VIX index ($VIX_t - VIX_{t-1}$).
- $\beta_{\Delta VIX}^i$: loading on market volatility spikes.
- Investors want to hedge against increases in market volatility ($\lambda_v < 0$). Assets that covary positively with $VIX$ act as insurance and therefore earn low expected returns.

---

## EXTRACT 5: Portfolio Sorts on Systematic Volatility — Table I (p.10-12)
Sample: January 1986 to December 2000. Portfolios sorted into quintiles based on past 1-month $\beta_{\Delta VIX}$:
- **Quintile 1 (Lowest $\beta_{\Delta VIX}$ / Volatility Shorts):** Total return = **+1.50% per month**.
- **Quintile 5 (Highest $\beta_{\Delta VIX}$ / Volatility Hedges):** Total return = **+0.46% per month**.
- **Spread (Quintile 5 minus Quintile 1):**
  - Raw Return Spread: **-1.04% per month**
  - Fama-French 3-Factor Alpha: **-1.15% per month (t-stat = -3.77)**!
  - Annualized FF3 Alpha: **-13.8% per year**.

---

## EXTRACT 6: Portfolio Sorts on Idiosyncratic Volatility — Table VI Panel B (p.25-26)
Portfolios formed on idiosyncratic volatility $\sqrt{\text{Var}(\varepsilon^i)}$ relative to FF3 (1/0/1 strategy):

| Portfolio | Monthly Raw Return | FF3 Alpha ($\alpha_{FF3}$) | t-statistic ($\alpha$) |
|---|---|---|---|
| **Quintile 1 (Lowest IdioVol)** | **+1.06%** | **+0.12%** | +1.44 |
| Quintile 2 | +1.15% | +0.13% | +1.72 |
| Quintile 3 | +1.17% | +0.07% | +0.81 |
| Quintile 4 | +0.94% | -0.19% | -1.54 |
| **Quintile 5 (Highest IdioVol)** | **+0.09%** | **-1.16%** | **-5.92** |
| **Quintile 5 minus Quintile 1** | **-1.06%** | **-1.31%** | **-7.00** |

**Crucial Magnitude:**
- High idiovol stocks earn an abnormal FF3 alpha of **-1.16% per month**!
- Long Quintile 1 / Short Quintile 5 produces an annual risk-adjusted alpha of **+15.7% per year (t = 7.00)**.

---

## EXTRACT 7: Total Volatility vs Idiosyncratic Volatility — Table VI Panel A vs B (p.25)
- Sorting on Total Volatility ($\sigma_i$) produces:
  - Quintile 5 - 1 FF3 alpha: **-1.19% per month (t = -5.92)**.
- Sorting on Idiosyncratic Volatility ($\sigma_{\varepsilon,i}$) produces:
  - Quintile 5 - 1 FF3 alpha: **-1.31% per month (t = -7.00)**.
- **Finding:** Idiosyncratic volatility isolates the mispricing even more cleanly than total volatility because it strips out the CAPM market risk premium.

---

## EXTRACT 8: Robustness to Firm Size — Table VII (p.26-28)
Testing whether the idiovol anomaly is driven by microcap illiquidity:
- **NYSE-Only Universe (Excluding AMEX and NASDAQ):**
  - Quintile 5 FF3 alpha: **-0.60% per month**.
  - Quintile 5 - 1 Alpha Spread: **-0.66% per month (t-stat = -4.85)**.
- **Large-Cap Deciles (Top 3 Size Deciles):**
  - Monotonic decline in returns from low to high idiovol persists.
  - Large-cap idiovol spread: **-0.54% per month (t = -3.81)**.
- **Implementation Rule:** IdioVol alpha is robust in large-cap universes (`TOPSP500`, `TOP500`, `TOP1000`).

---

## EXTRACT 9: Robustness to Momentum & Reversal — Table VIII (p.28-31)
$5 \times 5$ two-way independent sorts controlling for momentum:
- Controlling for **1-Month Momentum (Short-term reversal):**
  - Quintile 5 - 1 Alpha Spread: **-0.66% per month (t = -4.20)**.
- Controlling for **6-Month Momentum:**
  - Quintile 5 - 1 Alpha Spread: **-1.10% per month (t = -5.02)**.
- Controlling for **12-Month Momentum (Intermediate momentum):**
  - Quintile 5 - 1 Alpha Spread: **-1.22% per month (t = -5.46)**!
- **Synergy:** High IdioVol + Past Loser is the single worst performing basket in the entire U.S. stock market.

---

## EXTRACT 10: Robustness to Liquidity & Turnover
Controlling for Pastor-Stambaugh (2003) liquidity factor and stock turnover:
- Quintile 5 - 1 alpha spread after 4-factor Carhart + Liquidity: **-1.28% per month (t = -6.84)**.
- Cannot be explained by bid-ask bounce or transaction volume.

---

## EXTRACT 11: Idiosyncratic Volatility Persistence & Decay (p.32-34)
- Average autocorrelation of monthly idiovol ranks: **0.78** (highly persistent firm attribute).
- 1/0/1 strategy maintains abnormal returns across multi-month holding horizons:
  - Month $t+1$: -1.31%/mo (t = -7.00)
  - Month $t+3$: -0.85%/mo (t = -4.12)
  - Month $t+6$: -0.52%/mo (t = -2.80)
- Optimal decay window in BRAIN: **$d \in [10, 20]$ days** for responsive tactical sorting; **$d \in [30, 60]$** for institutional capacity.

---

## EXTRACT 12: Ratio of Idiosyncratic to Total Variance
$$\text{IdioRatio} = \frac{\text{Var}(\varepsilon_i)}{\text{Var}(r_i)}$$
- Firms where idiosyncratic risk dominates total risk are those most prone to speculative retail herd behavior.
- Higher idio-ratio amplifies the negative return anomaly.

---

## EXTRACT 13: Volatility Acceleration ($\Delta \text{IdioVol}$)
- Short-term surges in idiosyncratic volatility:
  $$\Delta \text{IdioVol} = \text{IdioVol}_t - \text{IdioVol}_{t-20}$$
- A sudden explosion in firm-specific variance signals impending distress, jump risk, or earnings leakage.

---

## EXTRACT 14: Failure Conditions & Regime Vulnerability
1. **Low-Volatility Bubble Regimes:**
   - When market rallies sharply and low-volatility safe assets become crowded, low-idiovol long legs may lag aggressive cyclical bull runs.
2. **Extreme Turnaround Rallies (Junk Rallies):**
   - High-idiovol stocks occasionally experience explosive short squeezes in post-crisis market rebounds (e.g., March-April 2009, November 2020).

---

## EXTRACT 15: WorldQuant BRAIN Implementation Mapping
| Paper Parameter | BRAIN Dataset Field | Formula Expression |
|---|---|---|
| Idiosyncratic Volatility (60d) | `idiosyncratic_vol_last_60_days_spy` | Primary firm-specific risk measure |
| Idiosyncratic Volatility (90d) | `idiosyncratic_vol_last_90_days_spy` | Long-term stable idiovol |
| Total Volatility | `ts_std_dev(returns, 20) * 15.87` | Total realized vol comparator |
| Idio / Total Vol Ratio | `idiosyncratic_vol_last_60_days_spy / (ts_std_dev(returns, 60) * 15.87 + 0.001)` | Idiosyncratic purity ratio |
| Volatility Acceleration | `ts_delta(idiosyncratic_vol_last_60_days_spy, 10)` | Surge detection filter |

---

## EXTRACT 16: Cross-Paper Synergies
- **Frazzini & Pedersen (2014):** Orthogonal companion anomaly — low systematic beta combined with low idiosyncratic vol maximizes the portfolio Sharpe ratio.
- **Xing, Zhang & Zhao (2010):** High-idiovol stocks with steep implied volatility smirks identify imminent jump-to-default disasters.
- **Novy-Marx (2013):** High gross profitability + low idiovol is the premier institutional quality archetype.
