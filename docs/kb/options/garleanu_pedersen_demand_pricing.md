# 📘 Knowledge Base: Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing & Inventory Risk

> **Pillar:** 1. Options & Volatility Surface  
> **Source Academic Materials:**  
> 1. `Garleanu_Pedersen_Demand_Based_Option_Pricing.txt` — *Demand-Based Option Pricing* (Nicolae Gârleanu, Lasse Heje Pedersen, Allen M. Poteshman, 2009, *Review of Financial Studies*, 22(10), 4259–4299)  
> 2. `Garleanu_Pedersen_Poteshman_2009_Demand_Based_Option_Pricing_v2.txt` — Companion working paper & mathematical appendix  
> **Compilation Standard:** Institutional Quantitative Finance Canon | $\ge 20$ Verbatim Extracts | Exact Closed-Form Pricing Kernels & Empirical Estimations  

---

## 1. Executive Summary & Core Theoretical Mechanism

Garleanu, Pedersen & Poteshman (2009, *RFS*) overturn the classical Black-Scholes-Merton no-arbitrage paradigm by modeling the reality of financial intermediation: **option market makers cannot hedge their inventories perfectly**. Because of discrete trading intervals, stochastic volatility, and discrete price jumps, options are non-redundant securities. 

### Key Theoretical Theorems:
1. **The Demand-Pressure Pricing Kernel (Theorems 1 & 2):**
   - A marginal increase in end-user net demand $d_t^j$ in option $j$ increases its own price by an amount strictly proportional to the **variance of its unhedgeable risk**:
     $$\frac{\partial p_t^j}{\partial d_t^j} = \gamma (R_f - 1) \text{Var}_t^d(\bar{p}_{t+1}^j) \ge 0$$
   - Demand pressure in option $j$ also increases the price of any other option $i$ on the same underlying by an amount proportional to the **covariance of their unhedgeable parts**:
     $$\frac{\partial p_t^i}{\partial d_t^j} = \gamma (R_f - 1) \text{Cov}_t^d(\bar{p}_{t+1}^i, \bar{p}_{t+1}^j) \ge 0$$
2. **Three Structural Channels of Unhedgeable Risk:**
   - **Discrete Trading (Gamma Risk):** $\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} \propto \frac{\Gamma^i}{\nu^i} \Gamma^j \text{Var}_t((\Delta S)^2)$. Affects the **level** of implied volatility ($t = 3.85, R^2 = 18.5\%$).
   - **Jump Risk ($\kappa$ / Kappa Risk):** $\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} \propto \frac{\pi \Delta t E_t[\kappa^i \kappa^j]}{\nu^i}$. Jumps cannot be hedged locally and generate the **volatility skew/smirk** ($t = 3.68, R^2 = 25.9\%$).
   - **Stochastic Volatility (Vega $\nu$ Risk):** $\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} \propto \text{Var}(\Delta \sigma) \nu^j \left(\frac{1 - e^{-\phi T}}{\phi T}\right)$ ($t = 2.74, R^2 = 15.7\%$).
3. **Dealer P&L Interaction & Capital Constraints:**
   - Market maker risk aversion $\gamma$ is state-dependent. Following dealer trading losses (negative delta-hedged P&L), effective risk aversion spikes: the regression slope of demand on option prices **doubles** ($t = -2.72$).
4. **Single-Stock vs. Index Demand Asymmetry:**
   - While end users are net **long** index options (paying high premia for crash protection), end users are net **short** single-stock options (substantially selling OTM calls via institutional covered-call strategies). This explains why single-stock options are cheaper and display flatter skew curves.

---

## 2. Verbatim Institutional Extracts

#### EXTRACT 01: Core Abstract
> "We model demand-pressure effects on option prices. The model shows that demand pressure in one option contract increases its price by an amount proportional to the variance of the unhedgeable part of the option. Similarly, the demand pressure increases the price of any other option by an amount proportional to the covariance of the unhedgeable parts of the two options. Empirically, we identify aggregate positions of dealers and end users using a unique dataset, and show that demand-pressure effects make a contribution to well-known option-pricing puzzles." (Page 1)

#### EXTRACT 02: Motivation Against Affine No-Arbitrage Models
> "Building on the seminal contributions of Black and Scholes (1973) and Merton (1973), a large literature develops various parametric implementations of the theory. This literature is surveyed by Bates (2003) who emphasizes that it cannot fully capture — much less explain — the empirical properties of option prices and concludes that there is a need for a new approach to pricing derivatives. He writes: 'To blithely attribute divergences between objective and risk-neutral probability measures to the free risk premium parameters within an affine model is to abdicate one's responsibilities as a financial economist... a renewed focus on the explicit financial intermediation of the underlying risks by option market makers is needed.' We take on this challenge." (Page 3)

#### EXTRACT 03: Market Incompleteness and Dealer Unhedgeable Risk
> "If competitive intermediaries can hedge perfectly — as in a Black-Scholes-Merton economy — then option prices are determined by no-arbitrage and demand pressure has no effect. In reality, however, even intermediaries cannot hedge options perfectly — that is, even they face incomplete markets — because of the impossibility of trading continuously, stochastic volatility, jumps in the underlying, and transaction costs (Figlewski (1989)). In addition, intermediaries are sensitive to risk, e.g., because of capital constraints and agency problems (Shleifer and Vishny (1997))." (Page 3)

#### EXTRACT 04: The Pricing-Kernel Mechanism of Demand Pressure
> "We compute equilibrium prices as functions of demand pressure, that is, the prices that induce the utility-maximizing dealers to supply precisely the option quantities that the end users demand. We show explicitly how demand pressure enters into the pricing kernel. Intuitively, a positive demand pressure in an option increases the pricing kernel in the states of nature in which an optimally hedged position has a positive payoff. This pricing-kernel effect increases the price of the option, which entices the dealers to sell it." (Page 4)

#### EXTRACT 05: Aggregate Dealer Holdings and End-User Crashophobia
> "We use a unique dataset to identify aggregate daily positions of dealers and end users. In particular, we define dealers as market makers and end users as proprietary traders and customers of brokers. We are the first to document that end users have a net long position in S&P500 index options with large net positions in out-of-the-money puts. Since options are in zero net supply, this implies that dealers are short index options... We estimate that these large short dealer positions lead to daily delta-hedged profits and losses varying between $100 million and -$100 million, and cumulative dealer profits of approximately $800 million over our 6 year sample." (Pages 4–5)

#### EXTRACT 06: Resolving the Index vs Single-Stock Pricing Puzzle
> "Another option-pricing puzzle is the significant difference between index-option prices and the prices of single-stock options, despite the relative similarity of the underlying distributions (e.g., Bakshi, Kapadia, and Madan (2003) and Bollen and Whaley (2004)). In particular, single-stock options appear cheaper and their smile is flatter. Consistently, we find that the demand pattern for single-stock options is very different from that of index options. For instance, end users are net short single-stock options — not long, as in the case of index options." (Pages 5–6)

#### EXTRACT 07: Institutional Covered Call Marketing
> "Lakonishok, Lee, Pearson, and Poteshman (2007) document that for both individual equity puts and calls end users are more short than long. They show that for customers of a major discount brokerage house most individual equity written calls are part of covered call positions. They suggest that the predominance of end-user put and call selling results from the brokerage industry marketing these positions as win-win propositions — in the case of call sales as part of covered call positions and in the case of put sales as naked option positions on underlying value stocks." (Page 6)

#### EXTRACT 08: Definition of Unhedgeable Price Change
> "Definition 2: The unhedgeable price change $\bar{p}_{t+1}^k$ of any security $k$ is defined as its excess return $p_{t+1}^k - R_f p_t^k$ optimally hedged with the stock position $\frac{\text{Cov}_t^d(p_{t+1}^k, R_{t+1}^e)}{\text{Var}_t^d(R_{t+1}^e)}$:
$$\bar{p}_{t+1}^k = R_f^{-1} \left( p_{t+1}^k - R_f p_t^k - \frac{\text{Cov}_t^d(p_{t+1}^k, R_{t+1}^e)}{\text{Var}_t^d(R_{t+1}^e)} R_{t+1}^e \right)$$." (Page 13)

#### EXTRACT 09: Theorem 2 — Exact Sensitivity of Price to Demand Pressure
> "Theorem 2: The sensitivity of the price of security $i$ to demand pressure in security $j$ is proportional to the covariance of their unhedgeable risks:
$$\frac{\partial p_t^i}{\partial d_t^j} = \gamma (R_f - 1) E_t^d[\bar{p}_{t+1}^i \bar{p}_{t+1}^j] = \gamma (R_f - 1) \text{Cov}_t^d(\bar{p}_{t+1}^i, \bar{p}_{t+1}^j)$$." (Page 13)

#### EXTRACT 10: Proposition 3 — Positive Own and Cross-Option Price Impacts
> "Proposition 3: Demand pressure in any security $j$:
(i) increases its own price, that is, $\frac{\partial p_t^j}{\partial d_t^j} \ge 0$;
(ii) increases the price of another security $i$, that is, $\frac{\partial p_t^i}{\partial d_t^j} \ge 0$, provided that $E_t^d[p_{t+1}^i | S_{t+1}]$ and $E_t^d[p_{t+1}^j | S_{t+1}]$ are convex functions of $S_{t+1}$ and $\text{Cov}_t^d(p_{t+1}^i, p_{t+1}^j | S_{t+1}) \ge 0$." (Page 13)

#### EXTRACT 11: Convexity / Gamma as the Heart of Demand Pressure
> "Convexity lies at the heart of this result, which, informally speaking, states that higher demand for convexity (or gamma, in option-trader lingo) increases its price, and therefore those of all options." (Pages 13–14)

#### EXTRACT 12: Total Quadratic Cost Paid by End Users for Demand
> "Hence, the total price paid for the $d_t$ derivatives is:
$$d_t' p_t = d_t' p_t(d_t = 0) + \gamma (R_f - 1) \text{Var}_t^d(d_t' \bar{p}_{t+1})$$
The first term $d_t' p_t(d_t = 0)$ is the price that end users would pay if their demand pressure did not affect prices. The second term is total variance of the unhedgeable part of all of the end users' positions." (Page 14)

#### EXTRACT 13: Proposition 4 — Asymmetric Impact on Out-of-the-Money Options
> "Proposition 4: Assume that the one-period risk-neutral distribution of the underlying return is symmetric and consider demand pressure $d > 0$ in an option with strike $K < R_f S_t$ that matures after one trading period. Then there exists a value $\bar{K}$ such that... the price of the out-of-the-money put $p(p, K', \cdot)$ is more affected by the demand pressure than the price of out-of-the-money call $p(c, K'', \cdot)$. The reverse conclusion applies if there is demand for a high-strike option." (Page 15)

#### EXTRACT 14: Case 1 — Discrete Trading and Black-Scholes Gamma
> "The covariance of the unhedgeable parts of two options $i$ and $j$ is:
$$\text{Cov}_t(e^{r \Delta t} \bar{p}_{t+1}^i, e^{r \Delta t} \bar{p}_{t+1}^j) \cong \frac{1}{4} f_{SS}^i f_{SS}^j \text{Var}_t((\Delta S)^2)$$
so that, by Theorem 2, we conclude that the effect on the Black-Scholes implied volatility $\hat{\sigma}_t^i$ is:
$$\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} = \frac{\gamma r \text{Var}_t((\Delta S)^2)}{4} \frac{f_{SS}^i}{\nu^i} f_{SS}^j + o(\Delta t^2)$$
where $\nu^i$ is Black-Scholes vega." (Pages 16–17)

#### EXTRACT 15: Case 2 — Jumps in the Underlying and the Kappa ($\kappa$) Risk
> "If the jump probability is small, however, then this effect is small... In this case, the main effect comes from the jump risk $\kappa$ ('kappa'):
$$\kappa^i = f^i(S_t + \Delta S) - f^i - \theta^i \Delta S$$
and the effect on the Black-Scholes implied volatility $\hat{\sigma}_t^i$ is:
$$\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} = \frac{\gamma r}{\nu^i} \left( (f_{SS}^i S_t - \theta^i)(f_{SS}^j S_t - \theta^j)\text{Var}_t(\Delta S) + \pi \Delta t E_t[\kappa^i \kappa^j] \right) + o(\Delta t)$$
Large jumps have qualitatively different implications captured by kappa... It can be shown that this jump-risk effect means that demand can affect the slope of the implied-volatility curve to the first order and generate a smile." (Pages 17–18)

#### EXTRACT 16: Case 3 — Stochastic Volatility Risk and Vega ($\nu$)
> "The option price $p_t^i = f^i(t, S_t, \sigma_t)$ has unhedgeable risk... and the effect on the Black-Scholes implied volatility $\hat{\sigma}_t^i$ is:
$$\frac{\partial \hat{\sigma}_t^i}{\partial d_t^j} = \gamma r \text{Var}(\Delta \sigma) \frac{f_\sigma^i}{\nu^i} f_\sigma^j + o(\Delta t)$$
For an option with maturity at time $t + T$, we have $f_\sigma^i \cong \nu^i \frac{1 - e^{-\phi T}}{\phi T}$. Stochastic volatility risk affects the level, but not the slope, of the implied volatility curves to the first order." (Pages 18–19)

#### EXTRACT 17: Empirical Regressions and Model Performance (Table 2)
> "Table 2: The relationship between the SPX Excess Implied Volatility and demand pressure... Over the longer subsample (1997/10–2001/12):
- Discrete Trading (DiscTrade): coefficient = $2.8 \times 10^{-9}$, $t = 3.85$, $R^2 = 18.5\%$.
- Jump Risk (JumpRisk): coefficient = $3.2 \times 10^{-5}$, $t = 3.68$, $R^2 = 25.9\%$.
- Stochastic Volatility (StochVol): coefficient = $1.1 \times 10^{-5}$, $t = 2.74$, $R^2 = 15.7\%$.
The model based on jumps explains about 5.6 percentage points of excess implied volatility across its extreme range, accounting for more than a third of the estimated average level of excess implied volatility." (Pages 30–32)

#### EXTRACT 18: State-Dependent Dealer Risk Aversion & P&L Interaction (Table 3)
> "Further support for the hypothesis that the supply for options is upward sloping comes from the comparison between the estimated supply-curve slopes following market maker losses and, respectively, gains... In Table 3, there is a negative coefficient on the interaction between market-maker profits and demand pressure:
$$\text{P\&L} \times \text{Demand} = -1.40 \times 10^{-13}, \quad t = -2.28 \text{ to } -2.72$$
This means that the effect of demand is larger following market maker losses (i.e., negative profits) and smaller following positive profits. Following losses, market makers are more risk averse and therefore option prices are more sensitive to demand." (Pages 32–34)

#### EXTRACT 19: Market Maker Supply Slope Doubling Following Losses
> "Breaking the daily sample in two subsamples depending on whether the hedged market maker profits over the previous 20 trading days is positive or negative, we find that, following losses, the $b$ coefficient is approximately twice as large as the coefficient obtained in the other subsample. In the jump model, the regression coefficient following losses is $2.6 \times 10^{-5}$ ($t = 3.7$), compared to a value of $1.1 \times 10^{-5}$ ($t = 6.1$) following gains." (Page 33)

#### EXTRACT 20: Cross-Sectional Single-Stock Option Demand Implications
> "The excess implied volatility line is downward sloping but only varies by about 5% across moneyness categories for equity options, compared to 15% for SPX options... Non-market makers are net sellers of equity options on average, consistent with these options being cheap. Further, non-market makers sell mostly high-strike options, consistent with these options being especially cheap... Stocks with the most negative end-user demand trade at the deepest discount relative to GARCH(1,1) fair volatility." (Pages 27–28)

---

## 3. Mathematical Formulations & WorldQuant BRAIN Operator Canon

### Formula 1: Jump-Weighted End-User Demand Pressure ($\text{JumpDemand}$)
$$\text{JumpDemand}_{i,t} = \sum_{k} d_{i,t}^k \cdot \kappa_k$$
- **Economic Intuition:** Weighting option contract demand by crash jump exposure ($\kappa$) captures unhedgeable tail risk pricing ($t = 3.68, R^2 = 25.9\%$).
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(ts_decay_linear((iv_put_30 - iv_atm_30) * option_volume / (adv20 + 1), 10)), subindustry)
  ```

### Formula 2: Gamma Inventory Frictional Demand Pressure ($\text{GammaDemand}$)
$$\text{GammaDemand}_{i,t} = \text{NetDemand}_{i,t} \cdot \Gamma_{i,t}^2 \cdot \text{stddev}(\text{returns}, 20)^2$$
- **Economic Intuition:** Dealer rebalancing frictions scale with $\Gamma^2 \text{Var}((\Delta S)^2)$ ($t = 3.85$).
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(ts_decay_linear(option_volume * (high - low) / (close * volume + 1), 5)), subindustry)
  ```

### Formula 3: Vega-Weighted Stochastic Volatility Demand ($\text{VegaDemand}$)
$$\text{VegaDemand}_{i,t} = \text{NetDemand}_{i,t} \cdot \nu_{i,t} \cdot \frac{1 - e^{-\phi T}}{\phi T}$$
- **Economic Intuition:** Demand pressure driven by mean-reverting volatility inventory risk ($t = 2.74$).
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(ts_decay_linear(iv_atm_30 * option_volume / (adv20 + 1), 10)), sector)
  ```

### Formula 4: State-Dependent Dealer Loss Squeeze ($\text{Demand} \times \text{Loss}$)
$$\text{DealerSqueeze}_{i,t} = \text{Demand}_{i,t} \cdot \max(0, -\text{DealerP\&L}_{20d})$$
- **Economic Intuition:** Demand pressure impact doubles when market makers are in drawdown and suffering capital depletion ($t = -2.72$).
- **BRAIN Expression:**
  ```python
  trade_when(ts_mean(returns, 20) < 0, group_neutralize(rank(iv_call_30 - iv_put_30) * rank(option_volume), subindustry), -1)
  ```

### Formula 5: Single-Stock Covered-Call Discount Arbitrage
$$\text{CoveredCallDiscount}_{i,t} = \frac{IV_{i,t}^{\text{OTM Call}} - \text{GARCH}_{i,t}}{\text{GARCH}_{i,t}}$$
- **Economic Intuition:** End users oversell OTM calls for yield enhancement, driving single-stock call IV below fair fundamental volatility.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(-(iv_call_30 - historical_volatility_30) / (historical_volatility_30 + 0.001)), subindustry)
  ```
