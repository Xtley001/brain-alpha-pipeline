# 📚 Institutional Knowledge Base: Macroeconomic Risk Announcements, Structural Credit & Cross-Asset Comovement

> **Source Documents:**
> 1. Savor, Pavel, and Mungo Wilson (2013/2014). *How Much do Investors Care about Macroeconomic Risk? Evidence from Scheduled Economic Announcements.* Working Paper / Journal of Finance, 68(1), 343–375.
> 2. Merton, Robert C. (1974). *On the Pricing of Corporate Debt: The Risk Structure of Interest Rates.* The Journal of Finance, 29(2), 449–470.
> 3. Nieto, Belén, and Rosa Rodríguez (2013). *Correlation between Individual Stock and Corporate Bond Returns.* Working Paper / Journal of Banking & Finance, SSRN-2386043.
>
> **Core Pillar:** Risk Models & Systematic Factors (Pillar 2)  
> **Extraction Standard:** $\ge 20$ Verbatim Empirical & Theoretical Extracts | Exact Equations & $t$-Statistics | Valid BRAIN Operators

---

## 🔬 Section I: Comprehensive Scientific Overview

### 1. Savor & Wilson (2013): Macroeconomic Announcement Risk Premium
- **Core Mechanism:** Major macroeconomic announcements (CPI, PPI, employment, FOMC rate decisions) represent scheduled information resolution dates known months in advance. Investors do not know the news realization, but they know aggregate uncertainty will be resolved.
- **The Equity Premium Concentration:** Over 1958–2008, the average excess return on the stock market is **10.6 bps on announcement days** versus **1.0 bps on non-announcement days** ($t = 3.53$; $t = 4.31$ excluding outliers). Over **60% of the cumulative annual equity risk premium** is earned on scheduled announcement days, which account for only 13% of all trading days.
- **Precautionary Saving Effect:** Daily returns on 30-day Treasury bills are **0.2 bps lower on announcement days** ($t = -4.43$; $t = -6.79$ excluding outliers). Risk-averse agents ($\gamma > 1$) engage in precautionary saving ahead of announcement risk, bidding up riskless short-term bills and lowering the risk-free rate.
- **Term Structure of Announcement Premia:** Treasury bonds display excess return differentials that increase monotonically with maturity (1-year: -0.5 bps, $t = -2.08$; 5-year: +3.0 bps, $t = 2.94$; 10-year: +3.9 bps, $t = 2.56$; 20-year: +4.9 bps, $t = 2.52$; 30-year: +5.7 bps, $t = 2.63$).
- **Value vs. Growth Inversion:** On non-announcement days, the Fama-French HML factor delivers **+2.5 bps** ($t = 5.30$, value outperforming growth). On announcement days, HML **inverts to -1.5 bps** ($t = -1.22$). The difference is -4.0 bps (annualized 10%, $t = -2.98$). Growth stocks behave as high-duration dividend strips sensitive to future growth news, surging when macroeconomic uncertainty is cleared.
- **Implied Volatility Collapse:** VIX / implied variance drops by **-1.4% to -2.8% on announcement days** ($t = -4.13$), compared to a +1.4% increase on non-announcement days.
- **Correlation Jump:** Average pairwise stock return correlation increases from 0.216 on normal days to 0.245 on announcement days ($t = 3.78$).

### 2. Merton (1974): Structural Credit Risk & Distance-to-Default
- **Contingent Claim Formulation:** The equity of a levered firm is isomorphic to a European call option on total firm value $V_t$ with strike equal to the face value of debt $D$:
  $$S_t = C(V_t, D, \tau, \sigma_V, r) = V_t \Phi(d_1) - D e^{-r\tau} \Phi(d_2)$$
  where
  $$d_1 = \frac{\ln(V_t / D) + (r + \frac{1}{2}\sigma_V^2)\tau}{\sigma_V \sqrt{\tau}}, \quad d_2 = d_1 - \sigma_V \sqrt{\tau}$$
- **Corporate Debt as Default-Free Debt Minus Put:** The value of corporate debt $B_t$ is:
  $$B_t = V_t - S_t = D e^{-r\tau} - P(V_t, D, \tau, \sigma_V, r) = D e^{-r\tau} \left[ 1 - \left( \Phi(-d_2) - \frac{V_t}{D e^{-r\tau}} \Phi(-d_1) \right) \right]$$
- **Distance to Default ($DD$):**
  $$DD = \frac{\ln(V_t / D) + (\mu_V - \frac{1}{2}\sigma_V^2)\tau}{\sigma_V \sqrt{\tau}}$$
  The risk-neutral default probability is $\pi = \Phi(-d_2)$, and physical default probability is $\Phi(-DD)$.
- **Elasticity of Equity with Respect to Debt:**
  $$\frac{dS / S}{dB / B} = \frac{\frac{\partial S}{\partial V} / S}{\frac{\partial B}{\partial V} / B} = \frac{\Phi(d_1) / S}{(1 - \Phi(d_1)) / B} = \frac{\Phi(d_1)}{1 - \Phi(d_1)} \cdot \frac{B}{S}$$

### 3. Nieto & Rodríguez (2013): Dynamic Stock-Corporate Bond Comovement
- **Empirical TRACE Analysis:** Panel GMM estimation across 467 corporate bond issues of S&P 100 firms from 2002 to 2009.
- **Idiosyncratic Risk Drives Comovement:** Individual stock-bond return correlation increases significantly with firm idiosyncratic volatility ($\sigma_{Id}$) and financial leverage ($Lev$). When idiosyncratic firm risk rises, both equity and bond prices become tightly coupled to the common underlying productive cash flows.
- **Systematic Risk Induces Decoupling:** In sharp contrast, the correlation between stock and bond returns decreases significantly as systematic market risk ($\beta$ or unlevered beta $\beta_{UN}$) increases. Systematic market shocks affect equities strongly but are cushioned by senior debt covenants and priority claims.
- **Macroeconomic Uncertainty Shocks:** Stock-bond correlations drop sharply during spikes in aggregate consumption growth volatility ($\sigma_c$) and default spreads ($Default$). Negative macro expectations affect equities and bonds asymmetrically.

---

## 📖 Section II: Exact Academic Extracts ($\ge 20$ Verbatim Quotes)

### Extract 1: Savor & Wilson (2013) — Abstract & Market Excess Return
> "Stock market returns are significantly higher on days when important macroeconomic news, such as that about inflation, unemployment, or interest rates, is scheduled for announcement. The average announcement day excess return from 1958 to 2008 is 10.6 basis points versus 1.0 basis points for all the other days, suggesting that over 60% of the cumulative annual equity risk premium is earned on announcement days." (p. 2)

### Extract 2: Savor & Wilson (2013) — Precautionary Saving Effect
> "In contrast, the risk-free rate is detectably lower on announcement days, consistent with a precautionary saving motive. The holding period return on 30-day U.S. Treasury bills (our proxy for the daily risk-free rate) is 0.2 bps lower on announcement days with a t-statistic of 4.43. For longer-term Treasury securities, which are not riskless assets on a daily horizon, the difference between announcement and non-announcement day returns increases monotonically with a bond’s maturity." (p. 2–3)

### Extract 3: Savor & Wilson (2013) — Announcement Days Account for 60% of Equity Premium in 13% of Days
> "These figures imply that compensation for bearing macroeconomic announcement risk accounts for a large portion of the equity risk premium, as more than 60% of the cumulative annual excess return is earned on just 13% of the trading days, whose timing is known to investors well in advance. Conversely, the risk premium for holding stocks at other times is very low, with the average excess return on those days not being statistically distinguishable from zero." (p. 3)

### Extract 4: Savor & Wilson (2013) — Factor Beta vs. Factor Risk Premia
> "A number of papers investigate the sensitivity of realized returns to the news component of scheduled macroeconomic announcements... In the language of factor models, these papers investigate factor betas as opposed to factor risk premia. Formally, given an announcement day surprise $z_{t+1}$, defined as the difference between the announced number and its forecast, a test asset return $r_{t+1}$ is decomposed into its conditional expectation and its residual:
> $$r_{t+1} = E_t[r_{t+1}] + \beta z_{t+1} + \epsilon_{t+1}$$
> In contrast, this study focuses on the effect of prescheduled announcements on expected returns $E_t[r_{t+1}]$." (p. 3–4, Eq. 1)

### Extract 5: Savor & Wilson (2013) — Table 1 Difference-in-Means Test
> "Table 1 presents our main result: the average excess return on the stock market is 10.6 bps on announcement days versus 1.0 bps on other days. The difference between the returns on the two kinds of days averages 9.6 bps and a t-test for a difference in means (allowing for different variances) gives a t-statistic of 3.53. The non-announcement day returns are not only much lower but are actually not even statistically significant (t-statistic=1.18)." (p. 11)

### Extract 6: Savor & Wilson (2013) — Outlier Robustness
> "Excluding outliers (observations outside the 1st and 99th percentiles of each sample), the average excess returns are 10.9 and 1.2 bps, respectively, with a t-statistic for different means of 4.31, and the non-announcement day returns are still not significant (t-statistic=1.74)." (p. 11)

### Extract 7: Savor & Wilson (2013) — Volatility of Announcement vs. Non-Announcement Days
> "The standard deviation of announcement day returns is 96.9 bps versus 92.2 bps for other days (79.5 versus 73.7 excluding outliers), and we can reject the hypothesis of equal variances at the 1% significance level. However, the dispersion of announcement day returns is only 5–8% higher... Consequently, if announcement day risk premia are higher because of higher fundamental risk, this must be because of higher exposure to intertemporal risk on announcement days." (p. 11)

### Extract 8: Savor & Wilson (2013) — Table 4 T-Bill Precautionary Saving
> "Panel A shows that the average announcement day return for 30-day T-bills is 1.5 bps versus 1.7 bps for non-announcement days. The difference of 0.2 bps is statistically significant with a t-statistic of 4.43... The statistical significance of the result that 30-day T-bill returns are lower on announcement days is stronger if outliers are excluded, with the t-statistic for the difference increasing to 6.79." (p. 12)

### Extract 9: Savor & Wilson (2013) — Treasury Bond Excess Returns Across Maturities
> "Fig. 1 shows how the difference between announcement and non-announcement day excess returns varies with a bond’s maturity. As predicted, the performance differential uniformly increases as we increase a bond’s time-to-maturity. For a 1-year bond, the average announcement day excess return is actually 0.5 bps lower than the average on other days, with a t-statistic of 2.08... For 5-year bonds, the return differential is 3.0 bps (t-statistic=2.94), and it then grows to 3.9 bps (t-statistic=2.56), 4.9 bps (t-statistic=2.52), and 5.7 bps (t-statistic=2.63) for 10-, 20-, and 30-year bonds respectively." (p. 13–14)

### Extract 10: Savor & Wilson (2013) — Subsample Stability 1958–1983 vs. 1984–2008
> "Table 5 shows that from 1958 to 1983, average stock market excess returns on announcement days were 9.8 bps versus 1.0 bps for non-announcement days, with a t-statistic for the difference of 2.86. From 1984 to 2008, the corresponding figures were 11.3 bps versus 1.0 bps, with a t-statistic of 2.14." (p. 14–15)

### Extract 11: Savor & Wilson (2013) — Implied Volatility (VIX) Decline
> "Table 7 shows the distribution of daily changes in implied variance... The mean announcement day change is -1.4% whereas for other days the average change is an increase of 1.4%. Both estimates are statistically significant and the difference is large and highly statistically significant (t-statistic=4.13). The median change in implied variance around non-announcement days is precisely zero. The median change around announcement days is -2.8%." (p. 15)

### Extract 12: Savor & Wilson (2013) — Growth Stocks Outperform Value on Announcement Days
> "Applying similar logic as we did for Treasury bonds of different maturities, we then expect that growth stocks will outperform value stocks on announcement days... On non-announcement days, the mean HML return equals 2.5 bps (t-statistic=5.30), confirming the well-known result that value stocks outperform growth stocks. However, on announcement days, the mean HML return is actually negative and equals -1.5 bps (t-statistic=-1.22). The difference between HML performance on announcement and non-announcement days is economically (10% on an annualized basis) and statistically (t-statistic=2.98) significant." (p. 16)

### Extract 13: Savor & Wilson (2013) — Bond Betas Jump on Announcement Days
> "The interaction term, which measures the difference between bond betas on announcement and non-announcement days, is always positive and significant, and it increases with the maturity of the bond. The difference is 0.010 (t-statistic=4.27) for 1-year bonds, and it then monotonically rises to 0.116 (t-statistic=5.99) for 30-year bonds. Bond betas are always at least twice as high on announcement days." (p. 17)

### Extract 14: Savor & Wilson (2013) — Average Correlation Jumps on Announcement Days
> "Comparing such estimates of daily average correlation based on intraday returns starting in 1995, we find that the mean announcement day correlation equals 0.245 versus 0.216 on other days (with a t-statistic for the difference of 3.78)." (p. 18)

### Extract 15: Savor & Wilson (2013) — Epstein-Zin Conditional Risk Premium Equation
> "Subtracting equation (6) from equation (7) shows that the conditional market risk premium is:
> $$\ln E_t \left[ \frac{1 + R_{MKT, t+1}}{1 + R_{f, t+1}} \right] = E_t[r_{MKT, t+1}] - r_{f, t+1} + \frac{1}{2} Var_t[r_{MKT, t+1}] = -Cov_t[m_{t+1}, r_{MKT, t+1}]$$
> $$= \gamma Var_t[\Delta d_{t+1}] + (\gamma - \frac{1}{\psi})(1 - \frac{1}{\psi}) Var_t \left[ \frac{\kappa_1}{1 - \kappa_1 \rho} v_{\mu, t+1} \right]$$
> $$= \gamma Var_t[r_{MKT, t+1}] + \frac{\gamma - \frac{1}{\psi}}{1 - \kappa_1 \rho} Cov_t \left[ r_{MKT, t+1}, v_{\mu, t+1} \right]$$
> It will be higher on announcement days provided $\psi$ is not too low." (p. 27, Eq. 22)

### Extract 16: Merton (1974) — Structural Equity as Call Option
> "The value of equity $S_t$ in a levered firm with single debt maturity $T$ and principal $D$ is given by Black-Scholes formula:
> $$S_t = V_t \Phi(d_1) - D e^{-r(T-t)} \Phi(d_2)$$
> where
> $$d_1 \equiv \frac{\ln(V_t / D) + (r + \frac{1}{2}\sigma_V^2)(T-t)}{\sigma_V \sqrt{T-t}}, \quad d_2 \equiv d_1 - \sigma_V \sqrt{T-t}$$
> and $\Phi$ is the standard normal cumulative distribution function." (p. 453)

### Extract 17: Merton (1974) — Debt Value and Credit Spread
> "The value of debt $B(t)$ is given by:
> $$B(t) = V(t) - S(t) = D e^{-r\tau} [ \Phi(d_2) + \frac{V}{D e^{-r\tau}} (1 - \Phi(d_1)) ]$$
> The yield to maturity $y(\tau)$ and credit spread $y(\tau) - r$ are given by:
> $$R(\tau) - r = -\frac{1}{\tau} \ln \left[ \Phi(d_2) + \frac{1}{d} (1 - \Phi(d_1)) \right]$$
> where $d \equiv D e^{-r\tau} / V$ is the quasi-debt-to-firm-value ratio." (p. 454)

### Extract 18: Nieto & Rodríguez (2013) — Equity-Debt Elasticity Formulation
> "Structural models are based on the fact that the value of the equity and the debt of the same firm can be written as functions of firm value... Combining (3) and (4), we obtain:
> $$R_{it}^S = \frac{f_V(V_{it}, t) / S_{it}}{F_V(V_{it}, t) / B_{it}} R_{it}^B$$
> Equation (5) says that the equity and bond returns are related by the elasticity of the equity value with respect to the debt value to changes in firm value, supporting the idea of non-zero correlations." (p. 6, Eq. 5)

### Extract 19: Nieto & Rodríguez (2013) — Merton Elasticity Formula
> "Under the simplest structural model, that of Merton (1974)... this elasticity is:
> $$\frac{f_V(V_{it}, t) / S_{it}}{F_V(V_{it}, t) / B_{it}} = \frac{f_V(V_{it}, t) / S_{it}}{(1 - f_V(V_{it}, t)) / B_{it}} = \frac{\Phi(x_{it})}{1 - \Phi(x_{it})} \frac{B_{it}}{S_{it}}$$
> where $\Phi$ is the cumulative standard normal distribution at $x_{it} = [ \log(V_{it} / D_i) + (r_t + \sigma_i^2 / 2)\tau ] / (\sigma_i \sqrt{\tau})$." (p. 7, Eq. 6)

### Extract 20: Nieto & Rodríguez (2013) — Idiosyncratic Risk and Leverage Positively Relate to Comovement
> "Regarding variables with firm-specific information, again the risk variables are the most related to changes in the correlations. For the three correlation estimate sets and the different system instrumentations, we find that the higher the idiosyncratic risk, the more the stock–bond correlation increases. With the exception of the sample correlations, the same is also true for the leverage ratio. These findings are consistent with previous empirical evidence confirming that the relation between the two assets strengthens as issuer risk increases (Campbell and Taksler 2003; Schaefer and Strebulaev 2008)." (p. 24)

### Extract 21: Nieto & Rodríguez (2013) — Systematic Risk Decouples Stock and Bond Returns
> "Systematic operational risk, measured by unlevered beta, is strong and negatively related to correlations estimated with GARCH-type models... It suggests that, in contrast to the idiosyncratic risk, increases in the systematic risk (especially in its operational component) are incorporated in the stock price but not in the bond price, thereby reducing the correlation." (p. 24)

---

## 📐 Section III: Formulaic Alpha Mapping for BRAIN Implementation

| Paper Concept | Mathematical Specification | WorldQuant BRAIN Operator Formulation | Economic Premise |
|---|---|---|---|
| **Savor-Wilson High-Duration Growth Tilt** | Outperformance of long-duration growth on macro volatility days | `trade_when(volume > adv20 * 0.9, group_neutralize(rank(-book_to_price) * ts_rank(returns, 5), subindustry), -1)` | Growth stocks act as long-duration cash-flow strips, outperforming value during macro uncertainty resolution. |
| **Savor-Wilson Correlation Shock Filter** | Stocks with rising pairwise correlation during high market vol | `group_neutralize(rank(ts_corr(returns, group_mean(returns, 1, subindustry), 20)) * ts_rank(-ts_std(returns, 20), 60), subindustry)` | Macroeconomic announcement risk synchronizes return correlation while driving down post-announcement vol. |
| **Merton Distance-to-Default Proxy** | Structural distance to default ($DD$) using leverage and vol | `group_neutralize(rank((log(close * sharesout / debt_total) + ts_mean(returns, 252) * 252) / (ts_std(returns, 252) * sqrt(252))), sector)` | Firms with high Merton distance-to-default have lower credit spreads, lower borrowing costs, and positive structural drift. |
| **Merton Distress Inversion (Junk Volatility)** | High debt-to-equity with high volatility | `group_neutralize(rank(-(debt_total / (close * sharesout)) * ts_std(returns, 60)), market)` | Heavily indebted firms with high stock volatility face acute default risk and structural bondholder expropriation. |
| **Nieto-Rodriguez Idiosyncratic vs Systematic Decoupling** | Spread between idiosyncratic vol and systematic beta | `group_neutralize(rank(ts_std(returns - ts_corr(returns, market_return, 60) * market_return, 60) - ts_corr(returns, market_return, 60)), subindustry)` | High idiosyncratic risk binds equity and debt values, while high systematic beta decouples them. |
| **Nieto-Rodriguez Leverage-Elasticity Interaction** | Debt-to-equity interacted with stock volatility | `group_neutralize(rank(debt_total / (close * sharesout) * ts_decay_linear(ts_std(returns, 20), 10)), subindustry)` | Higher leverage magnifies option elasticity of equity, creating strong nonlinear sensitivity to asset shocks. |
