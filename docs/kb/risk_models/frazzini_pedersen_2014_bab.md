# Frazzini & Pedersen (2014) — Betting Against Beta (BAB)
## "Betting Against Beta"
### Journal of Financial Economics (2014) / NBER Working Paper 16601
#### Andrea Frazzini (AQR Capital Management) & Lasse Heje Pedersen (NYU Stern, Copenhagen Business School, AQR)

---

## ⚠️ SOURCE: Directly extracted from `docs/kb/extracted_text/Frazzini_Pedersen_2014_Betting_Against_Beta.txt`
> All formulas, statistics, table numbers, and quotes below are drawn **verbatim** from the raw text.  
> Generator: `brain_generators/risk_models/frazzini_pedersen_bab_exact.py`

---

## EXTRACT 1: Abstract (verbatim)
> *"We present a model in which some investors are prohibited from using leverage and other investors' leverage is limited by margin requirements. The former investors bid up high-beta assets while the latter agents trade to profit from this, but must de-lever when they hit their margin constraints. We test the model's predictions within U.S. equities, across 20 global equity markets, for Treasury bonds, corporate bonds, and futures. Consistent with the model, we find in each asset class that a betting-against-beta (BAB) factor which is long a leveraged portfolio of low-beta assets and short a portfolio of high-beta assets produces significant risk-adjusted returns. When funding constraints tighten, betas are compressed towards one, and the return of the BAB factor is low."*  
> *(Page 2, Abstract)*

---

## EXTRACT 2: Economic Intuition — Why the Security Market Line is Flat
> *"A basic premise of the capital asset pricing model (CAPM) is that all agents invest in the portfolio with the highest expected excess return per unit of risk (Sharpe ratio), and lever or de-lever it to suit their risk preferences. However, many investors — such as individuals, pension funds, and mutual funds — are constrained in the leverage they can take, and therefore over-weight risky securities instead of using leverage... This behavior of tilting towards high-beta assets suggests that risky high-beta assets require lower risk-adjusted returns than low-beta assets, which require leverage. Consistently, the security market line for U.S. stocks is too flat relative to the CAPM (Black, Jensen, and Scholes 1972) and is better explained by the CAPM with restricted borrowing than the standard CAPM (Black 1972, 1993; Brennan 1971)."*  
> *(Page 2-3)*

---

## EXTRACT 3: Model Equations & Proposition 1 — Equilibrium Returns (p.10)
Under leverage constraints with Lagrange multiplier $\psi_t$ (tightness of funding constraints):

**Equation (8) — Expected Excess Return:**
$$E_t(r_{t+1}^s - r^f) = \psi_t + \beta_t^s \lambda_t$$
where the market risk premium is:
$$\lambda_t = E_t(r_{t+1}^M - r^f) - \psi_t$$

**Security Alpha with Respect to Market:**
$$\alpha_t^s = \psi_t (1 - \beta_t^s)$$
- If $\beta_t^s < 1$ (low-beta asset): $\alpha_t^s > 0$ (positive alpha!)
- If $\beta_t^s > 1$ (high-beta asset): $\alpha_t^s < 0$ (negative alpha!)
- **Proposition 1(ii):** Alpha strictly decreases with market beta $\beta_t^s$.
- **Proposition 1(iii):** Sharpe ratio is highest for efficient portfolios with beta less than 1 and decreases monotonically for higher betas.

---

## EXTRACT 4: Core Formula — Equation (9), The BAB Factor Construction (p.11)
To construct a zero-cost, market-neutral factor:
$$r_{t+1}^{BAB} = \frac{1}{\beta_t^L} (r_{t+1}^L - r^f) - \frac{1}{\beta_t^H} (r_{t+1}^H - r^f)$$

- **Long leg:** Low-beta portfolio $L$, levered by $\frac{1}{\beta_t^L}$ (scaled to beta = 1).
- **Short leg:** High-beta portfolio $H$, de-levered by $\frac{1}{\beta_t^H}$ (scaled to beta = 1).
- **Net Market Beta:** $\frac{1}{\beta_t^L} \beta_t^L - \frac{1}{\beta_t^H} \beta_t^H = 1 - 1 = 0$ (Beta Neutral).
- **Dollar Holdings (p.18):** On average, the U.S. BAB factor is long $\$1.52$ of low-beta stocks and short $\$0.71$ of high-beta stocks.

---

## EXTRACT 5: Proposition 2 — Expected Returns and Funding Shocks (p.12)
**Equation (10) — Expected BAB Return:**
$$E_t(r_{t+1}^{BAB}) = \frac{\beta_t^H - \beta_t^L}{\beta_t^L \beta_t^H} \psi_t \ge 0$$
- The expected excess return is strictly positive and proportional to:
  1. The ex-ante **Beta Spread** $\frac{\beta_t^H - \beta_t^L}{\beta_t^L \beta_t^H}$
  2. The **Funding Constraint Tightness** $\psi_t$.

**Equation (11) & (12) — Shocks to Margin Requirements $m_t^k$:**
$$\frac{\partial r_t^{BAB}}{\partial m_t^k} \le 0 \quad \text{(Contemporaneous loss during liquidity crunch)}$$
$$\frac{\partial E_t(r_{t+1}^{BAB})}{\partial m_t^k} \ge 0 \quad \text{(Higher future expected return following margin shock)}$$

---

## EXTRACT 6: Beta Estimation & Dimson Lags — Equation (14) (p.16)
To capture non-synchronous trading and microstructural noise:
> *"Following Dimson (1979) and Fama and French (1992) we estimate betas as the sum of the slopes in a regression of the asset's excess return of the current and prior market excess returns... We include lags up to K = 5 trading days."*

$$\hat{\beta}_i^{TS} = \sum_{k=0}^K \hat{\beta}_k$$
- Rolling 1-year window (requiring at least 200 trading days).
- $\rho_i$: correlation with market over 1-year rolling window.
- $\sigma_i, \sigma_M$: standard deviations over 1-year rolling window.

---

## EXTRACT 7: Vasicek Bayesian Shrinkage — Equation (15) (p.16-17)
To reduce estimation noise and outlier distortion:
$$\hat{\beta}_i = w \hat{\beta}_i^{TS} + (1 - w) \beta^{XS}$$
- Paper baseline parameters: $w = 0.5$ (or $0.6$), $\beta^{XS} = 1.0$.
- Footnote 11: Bayesian empirical shrinkage factor $w_i = 1 - \sigma_{i,TS}^2 / (\sigma_{i,TS}^2 + \sigma_{XS}^2)$ has median 0.49 and mean 0.51 in U.S. data.
- **BRAIN Expression Translation:**
  ```python
  beta_shrunk = 0.6 * beta_last_90_days_spy + 0.4 * 1.0
  ```

---

## EXTRACT 8: Portfolio Sort Results — Table III U.S. Equities (p.18-19)
Sample period: January 1926 to December 2009 (84 years of U.S. equities):
- 10 beta-sorted decile portfolios:
  - Decile 1 (lowest beta): Highest Sharpe ratio, highest alphas.
  - Decile 10 (highest beta): Lowest Sharpe ratio, lowest alphas.
- **BAB Factor Performance (Rightmost column Table III):**
  - **Fama-French 3-Factor Alpha:** **+0.69% per month (t-stat = 6.55)**
  - **Carhart 4-Factor Alpha:** **+0.55% per month (t-stat = 5.12)**
  - **Pastor-Stambaugh 5-Factor Alpha:** **+0.46% per month (t-stat = 2.93)**
  - **Annualized Sharpe Ratio:** **0.75** (vs. Market 0.41, HML 0.43, SMB 0.25).

---

## EXTRACT 9: Global Equity Robustness — Table IV & Table V (p.19-20)
- Pooled Global Equities (Table IV): 19 MSCI developed countries, country-neutral sorts.
  - BAB abnormal returns: **+0.42% to +0.71% per month (t-stat = 2.22 to 3.72)**.
- Country-by-Country (Table V):
  - **18 of 19 countries** exhibit positive Sharpe ratios.
  - **16 of 19 countries** exhibit positive Carhart 4-factor alphas.
  - Statistically significant in 9 countries despite small sample cross-sections.

---

## EXTRACT 10: Cross-Asset Evidence — Treasuries, Credit, Futures (p.20-23)
- **U.S. Treasury Bonds (Table VI):**
  - Ranking on beta is equivalent to duration/maturity.
  - Alphas and Sharpe ratios decline monotonically with beta.
  - Bond BAB Factor: **+0.16% per month (t-stat = 6.37), Annual Sharpe = 0.85**.
- **Corporate Credit Indices (Table VII):**
  - Credit BAB Factor: **+0.13% per month (t-stat = 4.91), Annual Sharpe = 0.88**.
- **Commodities & FX Futures (Table IX):**
  - Positive risk-adjusted return in every tested asset class.

---

## EXTRACT 11: Beta Compression & Funding Liquidity — Section IV & Table X (p.24-25)
**Proposition 3:** When funding liquidity dries up (margin constraints bind), cross-sectional dispersion in betas compresses toward 1.0.
- Empirical Proxy: **TED Spread** (3-month LIBOR minus 3-month Treasury bill).
- Cross-sectional standard deviation of U.S. betas:
  - Low TED spread (loose funding): **$\sigma(\beta) = 0.47$**
  - High TED spread (tight funding): **$\sigma(\beta) = 0.35$**
  - Difference: **$-0.12$, t-stat = $-10.72$** (Statistically overwhelming).
- **Trading Implication:** BAB generates maximum alpha when beta dispersion is wide (regime where funding constraints are loose and low-beta mispricing is active).

---

## EXTRACT 12: Predictability Regressions — Table XI (p.26-27)
Regressing BAB monthly returns on credit & liquidity variables:
1. **Contemporaneous TED Spread:** Strongly negative relation. When liquidity shocks occur, BAB suffers contemporaneous mark-to-market drawdown.
2. **Ex-Ante Beta Spread $\frac{\beta^H - \beta^L}{\beta^H \beta^L}$:** Positive coefficient in all specifications. Wider ex-ante beta dispersion predicts higher subsequent BAB profits!
3. **Lagged TED Spread:** Negative coefficient in predictive panel regressions (as banking constraints compound over subsequent months).

---

## EXTRACT 13: Factor Loadings & Characterization — Table B1 & B2 (p.20)
Regressing U.S. BAB on traditional factors reveals:
- Long leg: tends to load on smaller cap, higher book-to-market (value), and prior 12-month winners (momentum).
- Short leg: loads heavily on high-volatility, low-profitability speculative firms.
- Even after fully controlling for Size, Value, Momentum, and Liquidity, BAB retains an unexplained alpha of **+55 to +69 bps per month**.

---

## EXTRACT 14: Interaction with Idiosyncratic Volatility (AHXZ 2006)
- Footnote 2 & Appendix: BAB results hold controlling for idiosyncratic volatility (both level and changes).
- **Economic distinction:**
  - Beta captures systematic market covariance (leverage constraint mechanism).
  - Idiovol captures firm-specific variance (lottery demand / retail overpricing mechanism).
  - **Synergy:** Double-sorting or conditioning Low Beta $\times$ Low Idiovol yields superior information ratio with drastically lower tail drawdown.

---

## EXTRACT 15: Interaction with Short-Term Reversal & Momentum
- Table 2 & Section II:
  - Low-beta stocks that experienced recent short-term pullbacks (`ts_delta(close, 5) < 0`) offer immediate entry alpha as arbitrageurs provide liquidity.
  - High-beta stocks experiencing short-term speculative run-ups are prime short targets.

---

## EXTRACT 16: Failure Conditions & Tail Risk
1. **Sudden Liquidity Crises / Margin Call Cascades (Eq. 11):**
   - In 1998 (LTCM) and 2007-2008 (Quant Meltdown / Lehman), leverage-constrained funds were forced to liquidate low-beta safe assets to meet margin calls, creating temporary BAB drawdowns.
2. **Beta Estimation Lag:**
   - Rapid regime transitions (e.g., sudden vol spikes) can distort rolling 60d/90d betas. Dimson lags and shrinkage are essential defenses.

---

## EXTRACT 17: WorldQuant BRAIN Implementation Mapping
| Paper Parameter | BRAIN Dataset Field | Formula Expression |
|---|---|---|
| Market Beta (rolling 1-year) | `beta_last_252_days_spy` | Primary long-term systematic beta |
| Market Beta (quarterly) | `beta_last_60_days_spy` / `beta_last_90_days_spy` | Responsive tactical beta |
| Vasicek Shrinkage | `0.6 * beta + 0.4 * 1.0` | Noise-attenuated beta |
| Idiosyncratic Volatility | `idiosyncratic_vol_last_60_days_spy` | AHXZ orthogonality control |
| Beta Dispersion Gate | `ts_std_dev(beta, 60)` | Proxy for funding constraint loose regime |
| Reversal Conditioner | `ts_delta(close, 5)` | Tactical entry timing |

---

## EXTRACT 18: Cross-Paper Synergies
- **Baker, Bradley & Wurgler (2011):** Explains that institutional benchmark tracking error constraints force mutual fund managers to avoid low-beta stocks, institutionalizing the BAB edge.
- **Ang, Hodrick, Xing & Zhang (2006):** Orthogonal companion factor — high beta + high idiovol is the toxic quadrant.
- **Xing, Zhang & Zhao (2010):** High-beta stocks with steep options volatility smirks have the highest default/downgrade probability.
