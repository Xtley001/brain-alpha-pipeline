# Multi-Category Alpha Knowledge Base

Extracted signal cards for analyst estimates, short lending, supply chain, and hybrid strategies. Sourced from 15 foundational academic papers and institutional quantitative textbooks in `docs/research/`.

## Literature Base

- **Givoly & Lakonishok (1979)** — *The Information Content of Financial Analysts' Forecasts of Earnings* (Journal of Accounting and Economics)
- **Diether, Malloy & Scherbina (2002)** — *Differences of Opinion and the Cross-Section of Stock Returns* (Journal of Finance)
- **Bernard & Thomas (1989, 1990)** — *Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?* (Journal of Accounting Research)
- **Martineau (2021)** — *Rest in Peace Post-Earnings Announcement Drift* (Modern Information Diffusion & Event Windows)
- **Fabozzi, Focardi & Kolm (2010)** — *Quantitative Equity Investing: Techniques and Strategies* (Wiley Finance)
- **Cohen, Diether & Malloy (2007)** — *Supply and Demand Shifts in the Shorting Market* (Journal of Finance)
- **Engelberg, Reed & Ringgenberg (2012)** — *How are Shorts Informed?* (Journal of Finance)
- **Asquith, Pathak & Ritter (2005)** — *Short Interest, Institutional Ownership, and Stock Returns* (Journal of Financial Economics)
- **Rapach, Ringgenberg & Zhou (2016)** — *Short Interest and Aggregate Stock Returns* (Journal of Financial Economics)
- **Staley (1997)** — *The Art of Short Selling* (Wiley)
- **Barrot & Sauvagnat (2016)** — *Input Specificity and Shock Propagation in Production Networks* (Quarterly Journal of Economics)
- **Cohen & Frazzini (2008)** — *Economic Links and Predictable Returns* (Journal of Finance)
- **Lead-Lag Detection and Network Clustering (2022)** — Multivariate Time Series with Application to US Equities
- **Option Volume Imbalance as a Predictor (2022)** — Information Asymmetry in Derivative Flow
- **Dynamic Relation Between Short Sellers, Option Traders and Stock Returns (2012)** — Cross-Market Information Transmission

---

## Analyst Estimates & Earnings Revisions

### A. Analyst Revision Clustering & Sluggish Assimilation (Givoly & Lakonishok 1979)
- **Idea:** Sell-side financial analysts are slow to update projections and update forecasts in progressive autocorrelation clusters over 15–60 days due to career risk and cognitive anchoring.
- **Heuristic:** A positive revision ratio (more upward revisions than downward revisions over a 30-day window) signals positive drift for 30–90 days forward.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(ts_decay_linear((est_eps - ts_delay(est_eps, 30)) / (abs(ts_delay(est_eps, 30)) + 0.01), 10)), subindustry)
  group_neutralize(rank(ts_decay_linear((est_sales - ts_delay(est_sales, 30)) / (abs(ts_delay(est_sales, 30)) + 0.01), 10)), subindustry)
  ```
- **Pitfall:** Beware of currency mismatches or one-off non-GAAP adjustments; normalize by historical standard deviations.
- **Source:** Givoly & Lakonishok (1979), Ch. 3; Fabozzi (2010), Ch. 7.

### B. The Analyst Dispersion & Disagreement Law (Diether, Malloy, & Scherbina 2002)
- **Idea:** Stocks with high analyst disagreement (standard deviation of EPS forecasts divided by absolute mean forecast) substantially underperform stocks with low dispersion. Under short-sale constraints, market price reflects only the views of the most optimistic analysts; when reality catches up, prices drop.
- **Heuristic:** Short stocks in the highest quintile of forecast dispersion and long stocks in the lowest quintile (consensus harmony).
- **Expression Sketch:**
  ```python
  group_neutralize(rank(-ts_decay_linear(std_dev_eps_est / (abs(est_eps) + 0.01), 10)), subindustry)
  group_neutralize(rank(-ts_zscore(std_dev_eps_est / (abs(est_eps) + 0.01), 60)), sector)
  ```
- **Pitfall:** Names with fewer than 3 covering analysts have noisy sample standard deviations; gate on `num_analysts >= 3`.
- **Source:** Diether, Malloy, & Scherbina (2002), Table II & IV.

### C. Price Target Implied Upside vs. Realized Momentum (Fabozzi et al. 2010)
- **Idea:** The gap between consensus target price and current spot price reflects institutional upside expectation, but is most predictive when confirmed by recent price velocity.
- **Heuristic:** Rank the ratio of `(target_price - close) / close` and condition on non-negative price drift over the trailing 10 days to avoid catching falling knives.
- **Expression Sketch:**
  ```python
  trade_when(ts_delta(close, 10) > 0, group_neutralize(rank(ts_decay_linear((target_price - close) / close, 10)), subindustry), -1)
  ```
- **Pitfall:** Outdated target prices from unresponsive analysts create stale false positives; decay target prices over 15-day lookbacks.
- **Source:** Fabozzi, Focardi, & Kolm (2010), Ch. 8.

---

## 2. SHORT INTEREST & SECURITIES LENDING FLOW

### A. Short Demand Shift vs. Supply Shift Decomposition (Cohen, Diether, & Malloy 2007)
- **Idea:** Increases in short borrowing costs can stem from rising borrowing demand (informed bearish bets) or contracting lending supply (passive institutional recall). An outward shift in demand (fee increases + short interest increases) is followed by violent negative abnormal returns of over -15% annualized.
- **Heuristic:** Multiply normalized borrow fee by short interest acceleration over 10–20 days to isolate informed short demand.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(-ts_decay_linear(borrow_fee * (short_interest / (float_shares + 0.001)), 10)), subindustry)
  group_neutralize(rank(-ts_delta(borrow_fee, 5) * ts_delta(short_interest / (float_shares + 0.001), 10)), subindustry)
  ```
- **Pitfall:** Raw borrow fees can be volatile in micro-cap stocks; always neutralize by subindustry and filter for `volume > adv20`.
- **Source:** Cohen, Diether, & Malloy (2007), Section 3.

### B. De-Trended Short Interest Z-Score (Rapach, Ringgenberg, & Zhou 2016)
- **Idea:** Raw short interest contains non-stationary cross-sectional drift. Standardizing short interest against its trailing 12-month (252-day) historical mean and standard deviation isolates abnormal institutional short positioning.
- **Heuristic:** Standardize short interest ratio over 252 days and fade stocks where the short interest Z-score exceeds +1.50.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(-ts_zscore(short_interest / (float_shares + 0.001), 252)), subindustry)
  group_neutralize(rank(-ts_decay_linear(ts_zscore(short_interest_ratio, 126), 10)), sector)
  ```
- **Pitfall:** Short interest is reported bi-weekly with a reporting lag; apply `ts_delay` or multi-day linear smoothing (`ts_decay_linear`) to prevent look-ahead bias.
- **Source:** Rapach, Ringgenberg, & Zhou (2016), Journal of Financial Economics.

### C. Days-to-Cover Short Squeeze Breakout (Asquith, Pathak, & Ritter 2005 / Staley 1997)
- **Idea:** When a stock has extreme days-to-cover (short interest / ADV > 8 days) and loan utilization exceeds 85%, short sellers are trapped. Any unexpected upward price momentum triggers forced margin buy-ins, driving reflexive exponential price appreciation.
- **Heuristic:** Enter long when days-to-cover is in the top decile and trailing 5-day return crosses a positive momentum threshold.
- **Expression Sketch:**
  ```python
  trade_when((close > ts_mean(close, 20)) & (days_to_cover > 6.0), group_neutralize(rank(days_to_cover * ts_delta(close, 5)), subindustry), -1)
  ```
- **Pitfall:** A high short interest stock with deteriorating price is a bankruptcy candidate, not a squeeze candidate; only trigger on positive price breakouts!
- **Source:** Asquith et al. (2005); Staley (1997), Ch. 12.

---

## 3. SUPPLY CHAIN & NETWORK LEAD-LAG SPILLOVER

### A. Customer-to-Supplier Information Diffusion (Cohen & Frazzini 2008 / Barrot & Sauvagnat 2016)
- **Idea:** Investors suffer from limited attention across complex economic networks. When a major customer experiences positive return momentum or an earnings shock, supplier firms with significant revenue dependence lag by 10 to 30 days before adjusting.
- **Heuristic:** Build a customer return momentum proxy and trade suppliers in the direction of customer returns minus supplier returns.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(ts_decay_linear(customer_returns_15 - returns, 5)), subindustry)
  group_neutralize(rank(ts_delta(customer_revenue_exposure * customer_returns_20, 5)), subindustry)
  ```
- **Pitfall:** Suppliers with diverse, fragmented customer bases do not exhibit lead-lag predictable returns; condition on high revenue concentration.
- **Source:** Cohen & Frazzini (2008), Table IV; Barrot & Sauvagnat (2016).

---

## 4. CROSS-ASSET HYBRID CONFLUENCE (OPTIONS + SHORTS + REVISIONS)

### A. The Volatility Smirk vs. Borrow Fee Confluence Law (MPRA 42566 / Xing-Zhang-Zhao 2010)
- **Idea:** The options market and the securities lending market house the two most informed groups of market participants. When steep downside OTM put skew coincides with rising institutional borrow fees, both derivatives and cash equity borrow markets confirm an impending collapse.
- **Heuristic:** Multiply downside normalized skew by normalized borrow fee. When both are elevated, downside prediction reaches maximum statistical significance.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(-ts_decay_linear((implied_volatility_mean_skew_30 * sqrt(30/252.0)) * (borrow_fee + 1.0), 5)), subindustry)
  group_neutralize(rank(-ts_decay_linear((pcr_vol_10 / (pcr_oi_10 + 0.001)) * (borrow_fee + 1.0), 5)), sector)
  ```
- **Pitfall:** Hard-to-borrow stocks can skew volatility smile fitting; ensure liquidity gating with `volume > adv20`.
- **Source:** MPRA Paper 42566; Xing, Zhang, & Zhao (2010).

### B. Analyst Revisions vs. Volatility Skew Divergence Law
- **Idea:** When equity analysts are progressively raising consensus earnings estimates while the options market is pricing an abnormal surge in downside put skew, the cash and derivative markets are in sharp disagreement. The options market empirically leads the cash/analyst consensus by 10–20 trading days.
- **Heuristic:** Go long stocks where analyst upgrades are accompanied by flattening put skew (reversal of bearish hedging), and short stocks where upgrades are met with expanding tail risk.
- **Expression Sketch:**
  ```python
  group_neutralize(rank(ts_decay_linear((est_eps - ts_delay(est_eps, 30)) / (abs(ts_delay(est_eps, 30)) + 0.01) - (implied_volatility_mean_skew_30 * sqrt(30/252.0)), 10)), subindustry)
  ```
- **Source:** Option Volume Imbalance (2022); Livnat & Mendenhall (2006).
