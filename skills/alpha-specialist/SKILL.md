---
name: alpha-specialist
description: Master quantitative options alpha research, mathematical surface formulations, and WorldQuant BRAIN operator synthesis derived from 16 institutional papers and books.
---

# Alpha Specialist — Institutional Quantitative Research & Synthesis

This skill encapsulates mathematical theorems, empirical heuristics, and risk controls extracted from the repository's 16 foundational books and papers (located in `docs/research/`), including:
- **Pan & Poteshman (2006)**: *The Information in Option Volume for Future Stock Prices*
- **Xing, Zhang, & Zhao (2010)**: *What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?*
- **Bali & Hovakimian (2009)**: *Volatility Spreads and Expected Stock Returns*
- **Carr & Wu (2009)**: *Variance Risk Premiums*
- **Bakshi, Kapadia, & Madan (2003)**: *Model-Free Skew and Kurtosis Laws*
- **Garleanu, Pedersen, & Poteshman (2009)**: *Demand-Based Option Pricing*
- **Zura Kakushadze (2016)**: *101 Formulaic Alphas*
- **Igor Tulchinsky et al. (2019)**: *Finding Alphas: A Quantitative Approach to Building Trading Strategies* (WorldQuant WebSim)
- **Euan Sinclair (2013, 2014)**: *Volatility Trading* & *Positional Option Trading*
- **Marcos López de Prado (2018)**: *Advances in Financial Machine Learning*
- **Richard Grinold & Ronald Kahn (2000)**: *Active Portfolio Management*

---

## 1. Mathematical Surface & Skew Formulations

### A. The Volatility Smirk (Xing, Zhang, & Zhao 2010)
- **Economic Principle:** Downside out-of-the-money (OTM) puts become expensive when informed market participants anticipate negative firm-specific earnings surprises or jump-to-default risks.
- **Metric Formulation:**
  $$\text{SKEW}_{i,t} = \text{VOL}_{i,t}^{\text{OTMP}} - \text{VOL}_{i,t}^{\text{ATMC}}$$
  where $\text{VOL}_{i,t}^{\text{OTMP}}$ is the implied volatility of OTM puts ($K/S \approx 0.95$) and $\text{VOL}_{i,t}^{\text{ATMC}}$ is ATM calls ($K/S \approx 1.00$).
- **Cross-Sectional Edge:** Stocks in the steepest skew quintile significantly underperform stocks in the lowest skew quintile.
- **WorldQuant BRAIN Expression:**
  ```python
  group_neutralize(rank(-ts_decay_linear(implied_volatility_mean_skew_{tenor} * sqrt({tenor} / 252.0), 5)), subindustry)
  group_neutralize(rank(-(implied_volatility_put_{tenor} - implied_volatility_call_{tenor}) / (implied_volatility_mean_{tenor} + 0.001)), subindustry)
  ```

### B. Principal Component Volatility Spreads (Bali & Hovakimian 2009)
- **Economic Principle:** Total risk decomposes into 3 principal components:
  1. PC1: Level of total volatility (uncorrelated with cross-sectional alpha).
  2. PC2: Realized vs. Implied Volatility Spread ($\text{RVol} - \text{IVol}$, proxy for volatility risk premium).
  3. PC3: Call IV minus Put IV Spread ($\text{IV}_{\text{call}} - \text{IV}_{\text{put}}$, proxy for expected directional price moves).
- **WorldQuant BRAIN Expression:**
  ```python
  # PC3: Call-Put Spread
  group_neutralize(rank(ts_decay_linear((implied_volatility_call_{tenor} - implied_volatility_put_{tenor}) / (implied_volatility_mean_{tenor} + 0.001), 5)), subindustry)
  # PC2: Realized minus Implied Spread (VRP)
  group_neutralize(rank(-(implied_volatility_mean_{tenor} - ts_std_dev(returns, {window}) * 15.87)), subindustry)
  ```

---

## 2. Order Flow & Put-Call Mechanics

### A. Informed Put-Call Volume Ratio (Pan & Poteshman 2006)
- **Economic Principle:** Open-buy option trades initiated by informed customers convey private information. A low put-to-call volume ratio signals aggressive institutional buying and leads equity prices by 40+ bps on the next trading day.
- **Metric Formulation:**
  $$\text{PCR}_{i,t} = \frac{\text{Put Open-Buy Volume}_{i,t}}{\text{Put Open-Buy Volume}_{i,t} + \text{Call Open-Buy Volume}_{i,t}}$$
- **WorldQuant BRAIN Expression:**
  ```python
  # Normalized PCR contrarian signal
  group_neutralize(rank(-ts_zscore(pcr_vol_{tenor}, 20)), subindustry)
  # Volume-to-Open-Interest surge
  trade_when(volume > adv20, group_neutralize(rank(-ts_decay_linear(pcr_vol_{tenor} / (pcr_oi_{tenor} + 0.001), 5)), subindustry), -1)
  ```

### B. Demand-Based Option Inventory Imbalances (Garleanu, Pedersen, Poteshman 2009)
- **Economic Principle:** End-user demand pressures market makers to warehouse unhedgeable jump/volatility risk. Option price deviations from Black-Scholes are proportional to dealer net inventory positions.
- **Heuristic:** Fading extreme surges in open interest against quiet underlying volume extracts the inventory liquidity concession.

---

## 3. WorldQuant WebSim Optimization & Robustness (Tulchinsky et al. 2019)

### A. The Triple-Axis Plan (Nitish Maini, Ch. 11)
To prevent overfitting and ensure structural robustness, alphas must be designed across three orthogonal axes:
1. **Dataset Axis:** Utilize diverse option-derived features (volatility surface, implied forward, open-interest, Parkinson realized vol).
2. **Universe Axis:** Confirm signal monotonicity across Top 3000, Top 1000, and Top 500 liquid universes.
3. **Horizon Axis:** Balance holding periods (10-day to 60-day) to prevent high-frequency turnover burn.

### B. Robustness via L-Estimators (Michael Kozlov, Ch. 12)
- Mean estimators in options data are fragile to single-day quote errors or illiquid strikes.
- Always apply robust operators:
  - Linear decay smoothing: `ts_decay_linear(x, d)`
  - Outlier truncation / winsorization: `quantile(x, ...)` or `signed_power(..., 0.5)`
  - Cross-sectional ranking: `rank(x)` prior to neutralization.

### C. WebSim Quality Objective Function (Composite Quality Score — CQS)
WorldQuant BRAIN penalizes alphas with high turnover ($> 30\%$) and rewards high margin and fitness:
$$\text{Fitness} = \text{Sharpe} \times \sqrt{\frac{\text{Annualized Return}}{\text{Turnover}}}$$
$$\text{CQS} = 1.0 \times \text{Sharpe} + 1.2 \times \text{Fitness} + 200 \times \text{Margin} - 0.5 \times \text{Turnover}$$

Alphas with $\text{CQS} \ge 3.0$ achieve the **1,800+ points-per-alpha** tier on the leaderboard.

---

## 4. Regime Conditioning & Turnover Reduction

### A. Sinclair 0.75 SD Mean-Reversion Filter (Sinclair 2013, 2014)
- **Principle:** For mean-reverting processes (like VRP and Term Structure), entering at $\approx 0.75 \sigma$ optimizes the trade-off between statistical edge and trading frequency.
- **Syntax:**
  ```python
  trade_when(abs(ts_zscore(spread, window)) > 0.75, signal, -1)
  ```

### B. Bivariate Liquidity Gate
- **Principle:** Derivatives-driven signals require liquid underlying shares to execute without adverse selection.
- **Syntax:**
  ```python
  trade_when(volume > adv20, signal, -1)
  ```
