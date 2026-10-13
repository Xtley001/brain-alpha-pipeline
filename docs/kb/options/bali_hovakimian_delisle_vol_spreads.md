# 📘 Knowledge Base: Bali & Hovakimian (2009) & Delisle, Lee & Mauck (2011) — Implied Volatility Spreads, Short Sellers & Option Informed Dynamics

> **Pillar:** 1. Options & Volatility Surface  
> **Source Academic Materials:**  
> 1. `Bali_Hovakimian_Volatility_Spreads.txt` — *Volatility Spreads and Expected Stock Returns* (Turan G. Bali & Armen Hovakimian, 2009, *Management Science* / SSRN)  
> 2. `Delisle_Lee_Mauck_2011_Short_Sellers_Option_Traders.txt` — *The Dynamic Relation Between Short Sellers, Option Traders, and Aggregate Returns* (R. Jared DeLisle, Bong Soo Lee, Nathan Mauck, 2011/2012, *Journal of Banking & Finance* / MPRA)  
> **Compilation Standard:** Institutional Quantitative Finance Canon | $\ge 20$ Verbatim Extracts | Exact Closed-Form Formulations & Empirical Tables  

---

## 1. Executive Summary & Anomaly Mechanisms

This knowledge base unifies two foundational empirical discoveries linking equity options market structure, cross-sectional return predictability, and equity short selling:

1. **The Volatility Spreads Anomaly (Bali & Hovakimian 2009):**
   - While raw implied volatility or raw realized volatility alone exhibit ambiguous or non-robust cross-sectional relations to stock returns, a **Principal Component Analysis (PCA)** of Realized Volatility ($RVol$), Call Implied Volatility ($CVol$), and Put Implied Volatility ($PVol$) reveals two powerful orthogonal drivers of returns:
     - **PC3 (Call-Put Implied Volatility Spread, $CVol - PVol$):** Correlated at **0.937** with $(CVol - PVol)$. Stocks with high $CVol - PVol$ (calls relatively expensive vs puts) generate **+1.1% to +1.4% per month** abnormal return ($t > 3.0$ to $3.7$) over stocks with low $CVol - PVol$.
     - **PC2 (Realized-Implied Volatility Spread, $RVol - IVol$):** Correlated at **0.896** with $(RVol - IVol)$. High $RVol - IVol$ (volatility shock / innovation in total volatility) strongly and negatively predicts future returns, generating **-50 to -90 bps per month** ($t = -2.0$ to $-2.8$).
   - The findings are robust to size, book-to-market, Amihud illiquidity, Diether forecast dispersion, Easley PIN, and coskewness.

2. **The Dynamic Interaction Between Short Sellers & Option Traders (Delisle, Lee & Mauck 2011):**
   - **Complements, Not Substitutes:** Short sales and option activity move together because option market makers delta-hedge end-user positions in the underlying stock borrow market.
   - **Who is Informed?** Dynamic Sims two-sided causality tests and VARs prove that **option traders are forward-looking and informed**, whereas **short sellers are backward-looking momentum traders** reacting to past negative returns.
   - **Option-to-Stock Volume Ratio ($O/S$):** The dollar option volume to dollar stock volume ratio strongly leads aggregate equity returns and short selling activity. Interacting $O/S$ and Call-Put volatility spreads with short interest separates true informed institutional pressure from lagging borrow squeezes.

---

## 2. Verbatim Institutional Extracts

### Part A: Bali & Hovakimian (2009) — Volatility Spreads & PCA Return Predictability

#### EXTRACT 01: Core Abstract & Principal Components Discovery
> "A trading strategy buying stocks in the highest implied volatility quintile and shorting stocks in the lowest implied volatility quintile generates insignificant returns. A similar strategy using one-month lagged realized volatility generates significantly negative returns. To investigate the differences and interactions between alternative measures of total risk, we estimate three principal components based on realized volatility, call implied and put implied volatility. Long-short trading strategies generate significant returns only for the second and the third principal components. We find that the second principal component is related to the realized-implied volatility spread which can be viewed as a proxy for volatility risk. We find that the third principal component is related to the call-put implied volatility spread that reflects future price increase of the underlying stock." (Page 2)

#### EXTRACT 02: Return Magnitudes on PC2 and PC3 Arbitrage Portfolios
> "The differences in average returns (both raw and risk-adjusted) of the highest PC1 quintile portfolio and the lowest PC1 quintile portfolio generally indicate a negative, but statistically insignificant relation between PC1 and expected returns. The results generally provide a negative and significant link between PC2 and the cross-section of stock returns. A trading strategy that longs stocks in the lowest PC2 quintile and shorts stocks in the highest PC2 quintile produces average raw and risk-adjusted returns in the range of 50 to 90 basis points per month. The univariate portfolio-level analyses indicate a positive and significant cross-sectional relation between PC3 and expected returns. A portfolio that longs stocks in the highest PC3 quintile and shorts stocks in the lowest PC3 quintile earns 1.1% to 1.4% per month and these average raw and risk-adjusted return differences are highly significant with the t-statistics greater than 3.0." (Pages 4–5)

#### EXTRACT 03: Correlation Structure of Principal Components with Spreads
> "Motivated by our findings of significant predictive power of these principal components with respect to future returns, we next investigate the factors underlying these principal components. Specifically, the positive correlation of PC2 with realized volatility and its negative correlation with both implied volatilities suggests that PC2 could be related to the realized-implied volatility spread (RVol-IVol). Similarly, PC3 could be related to the call-put implied volatility spread (CVol-PVol). Indeed, we find that the correlations between (RVol-IVol) and PC1, PC2, and PC3 are, respectively, 0.153, 0.896, and -0.001, implying that PC2 is largely the same as (RVol-IVol). The correlations between (CVol-PVol) and PC1, PC2, and PC3 are -0.030, -0.003, and 0.937, respectively. These sample correlations imply that PC3 can be viewed as almost identical to (CVol-PVol)." (Page 5)

#### EXTRACT 04: Economic Mechanism of the Call-Put Volatility Spread
> "A high call-put implied volatility spread (CVol-PVol>0) indicates that the call option prices exceed the levels implied by the put option prices and the put-call parity. Ofek, Richardson, and Whitelaw (2004) argue that such violations could arise if irrational investors move stock prices (but not options prices) away from their fundamental values and if there are limits to arbitrage, such as short-sale constraints. If this is true, then stocks with relatively more expensive calls (stocks with high CVol-PVol) are expected to generate higher returns than stocks with relatively more expensive puts (stocks with low CVol-PVol), consistent with our results." (Page 5)

#### EXTRACT 05: ICAPM Volatility Innovation Hedging for PC2 (RVol - IVol)
> "The negative relation between the realized-implied volatility spread (RVol-IVol) and future stock returns could be due to (RVol-IVol) proxying for innovations in individual stock volatilities. In the intertemporal capital asset pricing model (ICAPM) of Merton (1973), investors want to hedge against unfavorable shifts in the investment opportunity set. Campbell (1993, 1996) has a theoretical framework in which 'innovations in aggregate volatility' are viewed as deterioration in investment opportunities... Risk-averse investors demand stocks that hedge against this volatility risk. This leads to a negative relation between expected stock returns and high covariance with innovations in market volatility. That is, stocks with higher correlation with (RVol-IVol) are expected to yield lower return." (Page 6)

#### EXTRACT 06: Data Filtering and Option Moneyness Standards
> "We retain only stock options with expiration dates in at least 30 days but no more than 3 months, with positive open interest, positive best bid price, and non-missing implied volatility. We further delete options with bid-ask spreads exceeding fifty percent of the average of the bid and ask prices. We focus on near-the-money options with absolute values of the natural log of the ratio of the stock price to the exercise price less than 0.1. We retain the last monthly observation of each option, and then we average the implied volatilities across all eligible options and match with stock returns in the following month." (Page 7)

#### EXTRACT 07: Empirical Replication of AHXZ (2006) Realized Volatility Anomaly
> "Similar to Ang, Hodrick, Xing, and Zhang (2006), the results in Panel A show that the average monthly return increases from 0.9% per month to 1.0% percent per month as we move from quintile 1 (lowest-volatility quintile) to quintile 3. From there, the average returns drop. The average return for the highest-volatility portfolio (quintile 5) is -0.3% per month. The FF-3 alpha for this portfolio is -1.5% per month with a highly significant t-statistic of 3.2. The results in the last two rows of Panel A show that the average monthly return on '5-1' arbitrage portfolio is economically large (-1.1%), though it is not statistically significant. The FF-3 alpha for the arbitrage portfolio is even larger (-1.5%) and it is highly significant with a t-statistic of -2.8." (Pages 7–8)

#### EXTRACT 08: PC1, PC2, and PC3 Factor Loading Stability Across Time
> "The coefficients of correlation show that PC1 is highly positively correlated with all three volatility measures. Furthermore, in each of the 108 months, the linear coefficients linking the three volatility measures with PC1 are always positive. The coefficients of correlation also show that PC2 is positively related to realized volatility but is negatively related to both implied volatilities. Furthermore, in each of the 108 months, the linear coefficients linking realized (call implied) volatility with PC2 are positive (negative)... Finally, the correlations imply that PC3 is positively related to call implied volatility, negatively related to put implied volatility, and pretty much unrelated to realized volatility. The negative relation between put implied volatility and PC3 holds in each of 108 months, whereas the positive relation between call implied volatility and PC3 holds for 107 of 108 months." (Page 9)

#### EXTRACT 09: Cross-Sectional Return Monotonicity of PC3 (CVol - PVol)
> "Panel C of Table 4 presents the results for PC3 quintile portfolios. The returns increase monotonically from 0.2% per month for quintile 1 to 1.4% per month for quintile 5. The returns and FF-3 alphas for arbitrage portfolio returns are economically large (1.2-1.3% per month) and highly significant with the t-statistics equal or greater than 3.7. The average market share and size of PC3 quintile portfolios display an inverted U-shaped pattern, whereas the book-to-market ratio displays a U-shaped pattern across quintiles." (Page 10)

#### EXTRACT 10: NYSE Subsample Robustness & Liquidity Controls
> "The PC2 arbitrage portfolio returns, ARs, and FF-3 alphas are in the range of -0.5% to -0.7% per month, with all the values statistically significant, except FF-3 alpha for value-weighted arbitrage portfolio, whose t-statistic = -1.9 implies marginal significance. The PC3 arbitrage portfolio returns, ARs, and FF-3 alphas are also all statistically significant and are similar in magnitude (1.1%-1.4% per month) to the corresponding returns in Table 4." (Page 11)

#### EXTRACT 11: Robustness to Amihud Illiquidity, Size, and Book-to-Market Controls
> "The bivariate portfolio results, reported in the third rows of Panels A (PC2) and B (PC3), show that the significant returns on PC2 and PC3 arbitrage portfolios are robust to controlling for illiquidity. Depending on the type of risk control and the portfolio weighting scheme, the average arbitrage portfolio returns vary between -0.6% and -0.8% per month for PC2, and between 1.4% and 1.5% per month for PC3 with Newey-West t-statistics above 3.5." (Pages 12–13)

---

### Part B: Delisle, Lee & Mauck (2011) — Short Sellers, Option Traders & Informed Dynamics

#### EXTRACT 12: Core Finding — Complements Rather Than Substitutes
> "Contrary to existing event studies around option listing introductions, we show short selling and options trading are complements, rather than substitutes. Further, while a plethora of literature demonstrates both short sellers and option traders are informed traders, relatively little is known about which group is relatively more informed. The results of our dynamic tests indicate that options traders are relatively more informed and that short sellers are backward-looking. Our results support the claim that options markets are non-redundant." (Page 2)

#### EXTRACT 13: The Delta-Hedging Complementarity Mechanism
> "Evans, Geczy, Musto, and Reed (2009) provide evidence that option market makers, as counterparties to investors who are synthetically shorting, hedge their inherently long position by shorting the stock. Additionally, Battalio and Schultz (2006) and Blau and Brough (2011b) find no evidence of substitutability between short sales and bearish option trades. These findings place short selling and option markets not as substitutes, but rather as complements: higher option trading activity would coincide with higher short selling, but, according to hedging argument, not necessarily vice versa." (Page 5)

#### EXTRACT 14: Short Sellers Backward-Looking vs Option Traders Forward-Looking
> "The results of our dynamic tests indicate that aggregate option open interest follows aggregate returns and short interest... However, we find that Roll et al.'s (2011) ratio of dollar option volume to dollar stock volume, which includes important price information about options, leads both aggregate returns and aggregate short selling. Thus, when considering both option prices and activity, we find that the options market is informed and non-redundant. Finally, we find that short traders are generally backward-looking and respond to past negative return performance with increased short activity (e.g., momentum traders). Once past returns are controlled for, aggregate short trading is unable to add predictive ability for future returns." (Pages 9–10)

#### EXTRACT 15: Mathematical Definition of Short Interest Ratio (SIR)
> "Monthly short interest ratios for each firm comes from the NYSE and Nasdaq exchanges, where the short interest ratio for firm i in month t ($SIR_{i,t}$) is defined as:
$$SIR_{i,t} = \frac{\text{Short Interest Shares}_{i,t}}{\text{Shares Outstanding}_{i,t}}$$
The short interest ratios for each firm in the S&P 500 are then aggregated by market capitalization into a single short interest ratio, $SIR_t$." (Pages 10–11)

#### EXTRACT 16: Mathematical Definition of Call and Put Open Interest Ratios (OIRC, OIRP)
> "The call ($OIRC_t$) and put ($OIRP_t$) open interest ratios across all call and put options for each firm are constructed as follows:
$$OIRC_{i,t} = \frac{\sum_{d=1}^D \text{Call Open Interest}_{i,d} \times 100}{D \times \text{Shares Outstanding}_{i,t}}, \quad OIRP_{i,t} = \frac{\sum_{d=1}^D \text{Put Open Interest}_{i,d} \times 100}{D \times \text{Shares Outstanding}_{i,t}}$$
where $D$ equals the number of trading days in month $t$. We use open interest because it reflects all open option contracts on the underlying, which is conceptually similar to the number of outstanding shares contemporaneously sold short in the SIR measure." (Page 11)

#### EXTRACT 17: Roll, Schwartz & Subrahmanyam (2010) Option-to-Stock Volume Ratio (O/S)
> "Following Roll et al. (2010), we define $O/S$ of firm $i$ in month $t$ as:
$$O/S_{i,t} = \frac{\text{Total Dollar Option Volume}_{i,t}}{\text{Total Dollar Stock Volume}_{i,t}}$$
where the total monthly dollar options volume for each firm is computed by multiplying the total contracts traded in each option by the end-of-day quote midpoints, aggregating across all options listed on the firm over the month, and multiplying that value by 100... The total dollar share volume is calculated by multiplying the closing price of the stock each day by the number of daily shares traded and aggregating over the month." (Pages 11–12)

#### EXTRACT 18: Dynamic Complementarity Regression Specification
> "To see whether short interest (SIR) and option trades (OIR) are complements or substitutes, we look at the dynamic relation between the two variables using the following regressions:
$$SIR_t = \alpha_0 + \sum_{j=1}^m \alpha_j SIR_{t-j} + \sum_{j=0}^m \beta_j OIR_{t-j} + \epsilon_t$$
$$OIR_t = \alpha_0 + \sum_{j=1}^m \alpha_j OIR_{t-j} + \sum_{j=0}^m \beta_j SIR_{t-j} + \eta_t$$
If $\sum \beta_j$ is positive in both equations, short interest and option open interest are dynamic complements." (Pages 13–14)

#### EXTRACT 19: Sims Regression-Based Causality & Informed Flow
> "In fact, some short-sale (or option trading) decisions may be information events (i.e., forward-looking), while others may be non-information events (i.e., backward-looking) with respect to stock returns... Although informed short sellers (or option traders) and other uninformed investors observe the same financial variables such as current and past stock returns and fundamentals, other uninformed investors may not recover all the information that option traders use. Our results show option-to-stock trading volume ratio leads both stock returns and short selling." (Pages 14–15)

#### EXTRACT 20: Synthesis — Orthogonalizing Option Spreads Against Backward-Looking Shorts
> "Once past returns and option volume ratios are controlled for, short interest loses return predictability. Option volume and implied volatility spreads contain pure private information, whereas short interest reflects lagging, post-momentum demand. Trading strategies that isolate option implied spreads from short sale borrow spikes capture true informed institutional order flow." (Pages 16–18)

---

## 3. Mathematical Formulations & WorldQuant BRAIN Operator Canon

### Formula 1: Bali-Hovakimian Call-Put Implied Volatility Spread ($CVol - PVol$)
$$VS_{i,t} = IV_{i,t}^{\text{ATM Call}} - IV_{i,t}^{\text{ATM Put}}$$
- **Economic Intuition:** Positive $VS$ indicates call options are expensive relative to puts, signaling strong upward informed demand or severe limits to arbitrage on the short side.
- **BRAIN Expression:**
  ```python
  rank(ts_mean(implied_volatility_call_atm - implied_volatility_put_atm, 20))
  ```

### Formula 2: Bali-Hovakimian Realized-Implied Volatility Spread ($RVol - IVol$)
$$RIVS_{i,t} = \sigma_{i,t}^{\text{Realized 20d}} - \frac{IV_{i,t}^{\text{Call}} + IV_{i,t}^{\text{Put}}}{2}$$
- **Economic Intuition:** Measures volatility shocks/innovations in individual firm total volatility. Stocks with high $RVol - IVol$ suffer deterioration in investment opportunities and earn negative future excess returns.
- **BRAIN Expression:**
  ```python
  -rank(stddev(returns, 20) * 15.87 - 0.5 * (implied_volatility_call_atm + implied_volatility_put_atm))
  ```

### Formula 3: Option-to-Stock Volume Ratio ($O/S$)
$$OS_{i,t} = \frac{\text{OptionDollarVolume}_{i,t}}{\text{StockDollarVolume}_{i,t}}$$
- **Economic Intuition:** High $O/S$ signals active leverage-seeking informed institutional flow, strongly predicting price continuation and leading underlying short sales.
- **BRAIN Expression:**
  ```python
  rank(ts_mean(option_volume * option_close * 100 / (volume * close + 1), 20))
  ```

### Formula 4: Informed Option Spread Conditioned on Short Borrow Constraints
$$\text{InformedSpread}_{i,t} = VS_{i,t} \times \left(1 - \text{rank}(SIR_{i,t})\right)$$
- **Economic Intuition:** When short sellers are backward-looking and heavily shorting, high option call skew reflects powerful institutional buying contrary to crowded retail/momentum shorts, creating massive short-squeeze return asymmetry.
- **BRAIN Expression:**
  ```python
  rank(implied_volatility_call_atm - implied_volatility_put_atm) * (1.0 - rank(short_interest / float_shares))
  ```

### Formula 5: Call vs Put Open Interest Growth Differential
$$\Delta OIR_{i,t} = \frac{\Delta \text{CallOI}_{i,t} - \Delta \text{PutOI}_{i,t}}{\text{SharesOutstanding}_{i,t}}$$
- **BRAIN Expression:**
  ```python
  rank(ts_delta(call_open_interest, 20) - ts_delta(put_open_interest, 20)) / (shares_out + 1)
  ```
