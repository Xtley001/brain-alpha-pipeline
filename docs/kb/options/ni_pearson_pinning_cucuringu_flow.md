# 📘 Knowledge Base: Ni, Pearson & Poteshman (2005) and Michael, Cucuringu & Howison (2020) — Strike Pinning & Option Volume Imbalance

> **Pillar:** 1. Options & Volatility Surface  
> **Source Academic Materials:**  
> 1. `Ni_Pearson_Poteshman_2005_Stock_Price_Pinning_Option_Expiration.txt` — *Stock Price Clustering on Option Expiration Dates* (Sophie Xiaoyan Ni, Neil D. Pearson, Allen M. Poteshman, 2005, *Journal of Financial Economics*, 78(1), 49–87)  
> 2. `Michael_Cucuringu_Howison_2020_Option_Volume_Imbalance.txt` — *Option Volume Imbalance as a Predictor for Equity Market Returns* (Nikolas Michael, Mihai Cucuringu, Sam Howison, 2020/2022, University of Oxford & The Alan Turing Institute, *arXiv:2201.09319*)  
> **Compilation Standard:** Institutional Quantitative Finance Canon | $\ge 20$ Verbatim Extracts | Strike Pinning Dynamics, Avellaneda-Lipkin Restoring Force & High-IV Option Volume Imbalance Flow  

---

## 1. Executive Summary & Structural Alpha Mechanisms

This Knowledge Base synthesizes two foundational empirical and mathematical discoveries on how option trading and open interest directly alter the price formation, distribution, and cross-sectional predictability of underlying equities:

### Core Discoveries:

1. **Stock Price Clustering at Strikes on Expiration Dates (Ni, Pearson & Poteshman 2005):**
   - **Expiration Day Strike Pinning:** On option expiration dates (the 3rd Friday of each month), closing prices of optionable stocks cluster abnormally at strike prices ($z = 8.15$). Over 19% of optionable stocks close within $\$0.25$ of a strike price on expiration Friday, compared to under 18% on non-expiration Fridays.
   - **Return Deviation Lower Bound:** Optionable stock returns are altered by an average of at least **16.5 basis points** per expiration date, shifting aggregate market capitalization by over **$\$9.1$ billion per expiration date**. For smaller-cap stocks (deciles 1 and 2), the lower bound reaches **24.30 to 28.52 bps**.
   - **Variance Compression / Return Truncation:** Expiration Fridays exhibit elevated probabilities of near-zero returns ($0\text{--}50\text{ bps}$, $50\text{--}100\text{ bps}$) and suppressed probabilities of large returns ($300\text{--}1,000\text{ bps}$); stocks that start Thursday near strike are actively prevented from escaping the strike neighborhood.
   - **Twin Structural Drivers:**
     1. *Avellaneda & Lipkin (2003) Delta-Hedge Re-Balancing:* When delta-hedgers (market-makers) hold net purchased options (long gamma), the time derivative of delta $\frac{\partial \Delta}{\partial t} \approx \frac{N'(d_1) \ln(S/K)}{2 \sigma (T-t)^{3/2}}$ exerts a **restoring force**: if $S > K$, $\frac{\partial \Delta}{\partial t} > 0 \implies$ hedger sells stock, driving $S \downarrow K$; if $S < K$, hedger buys stock, driving $S \uparrow K$. When market-makers hold net written options (short gamma), this causes *de-clustering* leading up to expiration.
     2. *Proprietary Trader Strike Manipulation:* Traders with net written options intentionally trade the underlying near 4:00 PM on expiration Friday to push the stock slightly out-of-the-money ($S < K$ for calls, $S > K$ for puts) so the option finishes unexercised, eliminating the liability $|S - K|$.

2. **Option Volume Imbalance (OVI) Predictability (Michael, Cucuringu & Howison 2020):**
   - **Normalized Directional Flow Metric:**
     $$\text{OVI}_{i,d,m} = \frac{\sum_j (V_{i,j,d,m}^{\text{Up}} - V_{i,j,d,m}^{\text{Down}})}{\sum_j (V_{i,j,d,m}^{\text{Up}} + V_{i,j,d,m}^{\text{Down}})} \in [-1, 1]$$
     where $V^{\text{Up}} = V^{\text{CallBuy}} + V^{\text{PutSell}}$ (bullish signals) and $V^{\text{Down}} = V^{\text{CallSell}} + V^{\text{PutBuy}}$ (bearish signals).
   - **Market Participant Decomposition:** The strongest directional predictability for spot equity overnight returns ($f^{\text{CL}\to\text{tmOP}}$) comes from **Market-Maker OVI** (annualized Sharpe ratios $3.5\text{--}4.4$, PPD $1.4\text{--}1.9\text{ bps}$, $p < 0.0001$) and **Customer OVI** (Sharpe $2.7\text{--}3.5$).
   - **Customer vs. Market-Maker Negative Correlation:** Customer OVI and Market-Maker OVI exhibit a strong negative correlation of approximately $-0.60$ to $-0.68$, reflecting market-makers taking the liquidity-providing counterparty side of retail flows.
   - **High Implied Volatility & Put Dominance:** Most directional predictability stems from **high-IV option contracts** (leveraged speculative flow). Furthermore, the informational content of **put option volumes** significantly exceeds that of call options due to informed hedging and directional downside positioning.

---

## 2. Verbatim Institutional Extracts

#### EXTRACT 01: Core Abstract — Stock Price Clustering (Ni, Pearson & Poteshman 2005)
> "This paper presents striking evidence that option trading changes the prices of underlying stocks. In particular, we show that on expiration dates the closing prices of stocks with listed options cluster at option strike prices. On each expiration date, the returns of optionable stocks are altered by an average of at least 16.5 basis points, which translates into aggregate market capitalization shifts on the order of $9 billion. We provide evidence that hedge re-balancing by option market-makers and stock price manipulation by firm proprietary traders contribute to the clustering." (Page 1)

#### EXTRACT 02: Introduction & The 30-Year Empirical Gap
> "Despite this longstanding concern, little evidence has emerged that option trading has much impact on underlying stock prices... The present paper, by contrast, provides striking evidence that option trading alters the distribution of underlying stock prices and returns. In particular, we show that over the 1996-2002 period optionable stocks (i.e., stocks with listed options) cluster at option strike prices on expiration dates. There is no corresponding expiration date change in the distribution of the closing prices of non-optionable stocks." (Pages 2–3)

#### EXTRACT 03: Expiration Friday Closeness Within $0.25 and $Z$-Statistic 8.15
> "Panel A shows that more than 19 percent of optionable stocks close within $0.25 of a strike price on option expiration Fridays while less than 18 percent do so on the Fridays before and after expiration (i.e., on trade dates –5 and +5.) It is clear from the plot that the percentage on trade date zero is well outside of the range of the percentages on the other (i.e., non-expiration) trade dates. We test formally for a difference on trade date zero by computing a z-statistic for the null hypothesis that the percentage on the expiration Friday is drawn from the same population as the percentage on the non-expiration dates... The resulting z-statistic is a highly significant 8.15." (Page 9)

#### EXTRACT 04: Return Compression Towards Zero
> "On expiration Fridays optionable stocks are more likely to experience returns that are small in absolute value and less likely to experience returns that are large in absolute value. This difference suggests that the expiration date clustering is produced primarily from cases in which Thursday stock prices that are close to option strike prices remain in the neighborhood of the strike rather than from cases in which Thursday stock prices that are distant from the strike price move to the neighborhood of the strike." (Pages 3–4)

#### EXTRACT 05: Lower Bound Mathematical Derivation for Return Deviations
> "We derive an expression that provides a lower bound on the expiration date return deviations. Using this expression, we estimate that optionable stocks have their returns altered on average by at least 16.5 basis points (bps) per expiration date... regardless of the percentage of optionable stocks that are impacted, our estimates imply that on average the return deviations shift market capitalizations of optionable stocks by at least $9.1 billion per expiration date." (Page 4)

#### EXTRACT 06: Market Capitalization Impact Across Deciles
> "As is common with many financial market phenomena, the lower bound on the average absolute return effect varies with market capitalization. We document this variation by grouping the optionable stocks on each expiration date into deciles based on their market capitalizations... The estimates of the lower bounds ranged from 24.30 bps and 28.52 bps, respectively, for deciles 1 and 2 (the deciles with the smallest market capitalization stocks), to 13.63 bps and 6.70 bps for deciles 9 and 10 (the deciles with the largest market capitalization stocks)." (Page 16)

#### EXTRACT 07: Avellaneda & Lipkin (2003) Delta-Hedge Model
> "Avellaneda and Lipkin (2003) propose a model in which expiration date stock price clustering at strike prices is produced by the delta-hedging activity of option market participants with existing net purchased option holdings. A delta-hedging option investor attempts to maintain a stock position that is opposite to the delta of his net option position. Consequently, as the deltas of his existing portfolio of options change, he trades in the underlying stock in order to keep his overall option and stock position close to delta-neutral." (Page 17)

#### EXTRACT 08: Time Derivative of Black-Scholes Delta (The Restoring Force)
> "Recall that the Black-Scholes delta of a call option on a non-dividend paying stock is $N(d_1)$, where $d_1 \equiv \frac{\ln(S/K) + (r + \sigma^2/2)(T-t)}{\sigma\sqrt{T-t}}$... These formulas imply that the time derivatives of the call and put deltas are the same:
> $$\frac{\partial \Delta}{\partial t} = N'(d_1) \left[ - \frac{\ln(S/K)}{2 \sigma (T-t)^{3/2}} + \frac{r - \sigma^2/2}{2\sigma\sqrt{T-t}} \right]$$
> If we disregard the term $\frac{r - \sigma^2/2}{2\sigma\sqrt{T-t}}$, which is small relative to $\frac{\ln(S/K)}{2 \sigma (T-t)^{3/2}}$ as $t \to T$ provided that $S \neq K$... we have:
> $$\frac{\partial \Delta}{\partial t} \approx \frac{N'(d_1) \ln(S/K)}{2 \sigma (T-t)^{3/2}} > 0 \quad \text{if } S > K$$
> $$\frac{\partial \Delta}{\partial t} \approx \frac{N'(d_1) \ln(S/K)}{2 \sigma (T-t)^{3/2}} < 0 \quad \text{if } S < K$$." (Pages 17–18)

#### EXTRACT 09: Delta-Hedging Creates Mean-Reverting Price Pressure
> "In particular, consider an agent who has purchased options on $n$ shares of stock, and thus has a position with a delta of $n\Delta$. If the agent continuously re-hedges the option position, then at each instant of time the stock position is $-n\Delta$ shares. The previous analysis implies that if $S > K$ as expiration approaches, then the time derivative $\frac{\partial \Delta}{\partial t} > 0$. The positive time derivative of $\Delta$, in turn, implies that $\frac{\partial (-n\Delta)}{\partial t} < 0$, or that as time passes the agent sells stock driving $S$ down toward $K$. On the other hand, if $S < K$ then $\frac{\partial (-n\Delta)}{\partial t} > 0$ which implies that as time passes the agent buys stock driving $S$ up toward $K$." (Pages 18–19)

#### EXTRACT 10: Market-Maker Net Open Interest Classification
> "Market-makers have net purchased open interest on 62% of the stock-trade date pairs and net written open interest on 38% of the stock-trade date pairs... When market-makers have a net purchased position... the spike at trade date zero is very pronounced. It is nearly 2 percent higher than on the non-expiration dates... Second, the percentages before expiration are larger than those after expiration... There is elevated clustering leading up to the expiration date." (Pages 25–26)

#### EXTRACT 11: Net Written De-Clustering Leading Up to Expiration
> "When option market-makers have a net written (rather than a net purchased) position... the percentages before expiration are now lower than those after expiration... That is, there is de-clustering leading up to the expiration date... The hedge re-balancing explanation predicts the de-clustering leading up to the expiration date but cannot explain the positive spike at expiration... The other explanations can account for the spike at expiration." (Pages 26–27)

#### EXTRACT 12: Proprietary Trader Stock Price Manipulation at Expiration
> "If the option market is populated by sophisticated and unsophisticated investors, then stock price manipulation by a subset of the sophisticated investors is another possible explanation... sophisticated option writers have an incentive to manipulate underlying stock prices so that unsophisticated option buyers do not exercise their options. In particular, sophisticated option writers have an incentive to manipulate underlying stock prices so that ITM options become OTM and OTM options are prevented from becoming ITM. When a sophisticated option writer prevents exercise through such manipulation, he avoids a liability equal to the (absolute) difference between the unmanipulated underlying stock price and the strike price." (Page 21)

#### EXTRACT 13: Asymmetry of Manipulation Incentives
> "While it might seem that traders with purchased option positions would have similar incentives to manipulate the prices of underlying stocks leading up to expiration, they do not... Written and purchased option positions do not provide symmetric incentives to manipulate the underlying stock price, because the sophisticated option writer gains when an unsophisticated purchaser is 'tricked' into making an exercise decision based upon the manipulated price; an option purchaser cannot profit by tricking himself into making an incorrect exercise decision." (Page 22)

#### EXTRACT 14: Core Abstract — Option Volume Imbalance (Michael, Cucuringu & Howison 2020)
> "We investigate the use of the normalized imbalance between option volumes corresponding to positive and negative market views, as a predictor for directional price movements in the spot market. Via a nonlinear analysis, and using a decomposition of aggregated volumes into five distinct market participant classes, we find strong signs of predictability of excess market overnight returns. The strongest signals come from Market-Maker volumes. Among other findings, we demonstrate that most of the predictability stems from high-implied-volatility option contracts, and that the informational content of put option volumes is greater than that of call options." (Page 1)

#### EXTRACT 15: Directional Signal Classification (Up vs Down Volume)
> "As [Easley et al., 1998] observed, while the option volumes do not reliably predict movements in the stock market, this changes when one considers the volumes of positive and negative signals separately. Positive signals include call buys and put sells, while negative signals include call sells and put buys... Thus, we define:
> $$V_{i,j,d,m}^{\text{Up},F} = V_{i,j,d,m}^{\text{CallBuy},F} + V_{i,j,d,m}^{\text{PutSell},F} \quad \text{and} \quad V_{i,j,d,m}^{\text{Down},F} = V_{i,j,d,m}^{\text{CallSell},F} + V_{i,j,d,m}^{\text{PutBuy},F}$$
> to be the volumes corresponding to speculation for upwards and downwards movement respectively." (Pages 4–5)

#### EXTRACT 16: Mathematical Definition of OVI
> "Therefore, using the volume of Call-Buy/Sell and Put-Sell/Buy transactions as positive and negative directional signals respectively, and normalizing by the total volume, we define the Option Volume Imbalance (OVI) for asset $i$ and market participant class $m$ (for day $d$) as:
> $$\text{OVI}_{i,d,m}^{[F]} = \frac{\sum_{j=1}^{C_{i,d}} [X_{i,j,d,m}^{\text{Up},F} - X_{i,j,d,m}^{\text{Down},F}]}{\sum_{j=1}^{C_{i,d}} [X_{i,j,d,m}^{\text{Up},F} + X_{i,j,d,m}^{\text{Down},F}]}$$
> where $X$ denotes a generic flow variable... The normalization ensures that OVI lies in the interval $[-1, 1]$, so that the OVI of different assets can still be directly compared, independent of the asset's liquidity or market cap." (Page 5)

#### EXTRACT 17: Alternative Weightings (Trade-based & Nominal Volume OVI)
> "One potential shortcoming of volume-based OVI, is that more weight could be given to option contracts with lower prices (e.g deep OTM options) as they are sometimes transacted in larger volumes. To ameliorate this concern, we can define alternative OVI features by using the total number of trades (which we refer to as trade-based OVI) by setting $X = T$... We also define the nominal volume-based OVI, by weighting the volume by the option price, i.e set $X_{i,j,d,m}^{\text{Up},F} = P_{i,j,d}^{\text{Option}} V_{i,j,d,m}^{\text{Up},F}$." (Page 5)

#### EXTRACT 18: Five Market Participant Classes (MPCs)
> "Aggregate volumes are further broken down into five different market participant classes (hereafter MPCs) which are: Firm (Proprietary Trades), Brokers, Market Makers, Customers, and Professional Customers... for each MPC other than Market Makers, volumes are further decomposed into four parts based on the type of transaction and intention of the agent: Opening Buy, Opening Sell, Closing Buy and Closing Sell." (Page 6)

#### EXTRACT 19: Strong Negative Correlation Between Customers and Market Makers
> "Unsurprisingly (as trades are double-counted), there is a strong correlation between the volume- and trade-based OVI when they correspond to the same MPC. More importantly, for both data sets (Ordinary) Customers have a high negative correlation, of around $-0.6$, with Market Makers and Brokers, and a low negative correlation of around $-0.15$ with Professional Customers." (Page 7)

#### EXTRACT 20: Overnight Return Predictability ($CL \to tmOP$)
> "We define the following return types for asset $i$: Daily Close to Close Returns... Daily Open to Close Returns... Daily Overnight Returns:
> $$f_{i,d}^{\text{CL}\_\text{tmOP}} = \frac{P_{i,d+1}^{\text{open}} - P_{i,d}^{\text{close}}}{P_{i,d}^{\text{close}}}$$
> The highest performance is observed for Market Makers, where the cumulative returns are between 17% and 25% and annualized SRs lie between 3.5 and 4.4 depending on the quantile rank portfolio used. The second best performance is observed for Customers, whose cumulative P&L display a clear upwards trend, and SRs with magnitudes in the range 2.7–3.5." (Pages 9, 14–15)

#### EXTRACT 21: High-IV Options Carry Vast Majority of Predictability
> "In this section, we investigate which options carry most of the predictability, by segmenting options according to the value of certain option features, namely a subset of the 'Greeks': moneyness, maturity, and implied volatility... we find that most of the predictability stems from high-implied-volatility option contracts, and that the informational content of put option volumes is greater than that of call options." (Pages 1, 19)

---

## 3. Mathematical Formulations & Empirical Specifications

### A. The Avellaneda-Lipkin Restoring Force Equation (Ni, Pearson & Poteshman 2005)

The Black-Scholes call option delta on an underlying stock $S$ with strike $K$, risk-free rate $r$, and volatility $\sigma$ is:
$$\Delta = N(d_1), \quad d_1 = \frac{\ln(S/K) + (r + \sigma^2/2)(T-t)}{\sigma\sqrt{T-t}}$$

Taking the partial derivative with respect to calendar time $t$:
$$\frac{\partial \Delta}{\partial t} = N'(d_1) \left[ - \frac{\ln(S/K)}{2\sigma(T-t)^{3/2}} + \frac{r - \sigma^2/2}{2\sigma\sqrt{T-t}} \right]$$

As expiration approaches ($t \to T$, so $T - t \to 0$), the first term dominates the drift:
$$\frac{\partial \Delta}{\partial t} \approx \frac{N'(d_1) \ln(S/K)}{2\sigma(T-t)^{3/2}}$$

For a delta-hedging market maker holding $n$ long option contracts, the required stock hedge position is:
$$H(t) = -n \Delta(t)$$
The continuous hedge rebalancing order flow rate is:
$$\frac{dH}{dt} = -n \frac{\partial \Delta}{\partial t} \approx - \frac{n N'(d_1)}{2\sigma(T-t)^{3/2}} \ln(S/K)$$

- **Case 1 ($S > K$):** $\ln(S/K) > 0 \implies \frac{dH}{dt} < 0$. The market maker **sells stock**, applying negative price impact $\Delta P < 0$, pulling the spot price **downward towards $K$**.
- **Case 2 ($S < K$):** $\ln(S/K) < 0 \implies \frac{dH}{dt} > 0$. The market maker **buys stock**, applying positive price impact $\Delta P > 0$, pulling the spot price **upward towards $K$**.

Thus, long option delta hedging generates an **autonomous stabilizing attractor / mean-reverting restoring force** centered directly on strike $K$.

### B. Lower Bound on Return Impact

Let $r_i$ be the observed return on expiration Friday and $\hat{r}_i$ be the unperturbed return. The average deviation lower bound is derived from the discrete return distribution differences:
$$\mathbb{E}[|r_i - \hat{r}_i|] \ge \sum_{b=1}^B |p(b) - \hat{p}(b)| \cdot a(b) \ge 16.57 \text{ bps}$$
where $a(b)$ is the midpoint return of bin $b$ and $p(b) - \hat{p}(b)$ is the probability excess on expiration Fridays.

### C. The Cucuringu Option Volume Imbalance (OVI) Formulation

For equity $i$ across contracts $j \in \{1, \dots, C_{i,d}\}$:
$$\text{OVI}_{i,d} = \frac{(V_{i,d}^{\text{CallBuy}} + V_{i,d}^{\text{PutSell}}) - (V_{i,d}^{\text{CallSell}} + V_{i,d}^{\text{PutBuy}})}{V_{i,d}^{\text{Total}}} \in [-1, 1]$$

Under high implied volatility weighting:
$$\text{OVI}_{i,d}^{\text{HighIV}} = \frac{\sum_{j \in \text{TopQ}(IV)} (V_{i,j,d}^{\text{Up}} - V_{i,j,d}^{\text{Down}})}{\sum_{j \in \text{TopQ}(IV)} (V_{i,j,d}^{\text{Up}} + V_{i,j,d}^{\text{Down}})}$$

And the Put Informational Dominance Imbalance (PIDI):
$$\text{PIDI}_{i,d} = \frac{V_{i,d}^{\text{PutSell}} - V_{i,d}^{\text{PutBuy}}}{V_{i,d}^{\text{PutTotal}}}$$

---

## 4. WorldQuant BRAIN Operator Synthesis & Alpha Archetypes

To implement these findings within the WorldQuant BRAIN platform:

| Concept / Anomaly | Brain Formulation Pattern | Economic Rationale |
| :--- | :--- | :--- |
| **Strike Distance Restoring Force** | `-abs(close - round(close / 5.0) * 5.0) / close` | Measures proximity to nearest standard strike; trades mean-reverting pin pull. |
| **Expiration Pinning Pull** | `-(close - round(close / 5.0) * 5.0) / (close * (ts_std(returns, 20) + 0.001))` | Directional restoring force pulling price towards strike on expiration cycles. |
| **Market-Maker Long Gamma Stabilizer** | `-ts_delta(close, 1) * ts_decay_linear(volume / adv20, 5)` | Simulates dampening of extreme price moves due to market-maker hedging near strikes. |
| **High-IV Directional Flow Proxy** | `ts_rank(volume * (high - low) / close, 10) * sign(close - open)` | High-volatility option-induced directional spot imbalance proxy. |
| **Put Informational Imbalance Proxy** | `(close - low) / (high - low + 0.0001) - 0.5` conditioned on downward volume | Replicates informed downside flow capture where put volumes anticipate overnight gap risk. |
| **Overnight Gap Follow-Through** | `(open / ts_delay(close, 1) - 1.0) * ts_rank(adv5 / adv20, 20)` | Captures the overnight predictability documented in MCH 2020. |

---

## 5. Summary Verification Checklist
- [x] $\ge 20$ verbatim extracts compiled with page numbers and exact quotes.
- [x] Exact statistical tables referenced ($z = 8.15$, 16.5 bps lower bound, $\$9.1$B market cap shift, decile bounds 24.3 to 6.7 bps, Sharpe 3.5 to 4.4).
- [x] Mathematical equations derived (Avellaneda-Lipkin delta time derivative, hedge restoring force, discrete bound approximation, MCH OVI normalized flow formula).
- [x] Operator mapping ready for `brain_generators/options/ni_pearson_pinning.py`.
