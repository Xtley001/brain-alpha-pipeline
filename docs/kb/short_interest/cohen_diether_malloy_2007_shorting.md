# Cohen, Diether & Malloy (2007): Supply and Demand Shifts in the Shorting Market

**Citation:** Cohen, Lauren, Karl B. Diether, and Christopher J. Malloy. "Supply and Demand Shifts in the Shorting Market." *The Journal of Finance* 62, no. 5 (2007): 2061-2096.  
**Companion Papers:**
- Engelberg, Joseph E., Adam V. Reed, and Matthew C. Ringgenberg. "How Are Shorts Informed? Short Sellers, News, and Information Processing." *The Journal of Finance* 67, no. 2 (2012): 511-543.
- Rapach, David E., Matthew C. Ringgenberg, and Guofu Zhou. "Short Interest and Aggregate Stock Returns." *Journal of Financial Economics* 121, no. 1 (2016): 46-65.
- Asquith, Paul, Parag A. Pathak, and Jay R. Ritter. "Short Interest, Institutional Ownership, and Stock Returns." *Journal of Financial Economics* 78, no. 2 (2005): 243-276.

**Pillar:** Short Interest / Securities Lending  
**Target Module:** `brain_generators/short_interest/short_interest_p0_combined.py`  
**BRAIN Fields:** `short_interest_ratio`, `institutional_ownership_percentage`, `adv20`, `volume`, `close`, `returns`, `earnings_surprise`

---

## 1. Executive Summary & Institutional Alpha Architecture

Standard empirical literature routinely conflates the **supply** and **demand** for borrowable equities. Prior studies used either the loan fee (price) or short interest (quantity) in isolation, erroneously presuming the opposing curve is perfectly inelastic or stationary.

Cohen, Diether, and Malloy (2007) demonstrate that **loan fees alone are not a sufficient statistic for overpricing**. Overpricing and negative abnormal returns occur primarily when high fees are driven by an outward shift in **shorting demand** (informed institutional betting), rather than an inward contraction of lendable **supply** (administrative passive recall or custodian reallocation).

Using daily contract-level lending data on loan fees (price) and shares on loan (quantity) from a major institutional lender, CDM construct a 4-quadrant identification matrix:
1. **Demand Outward (DOUT):** Fee $\uparrow$ AND Quantity $\uparrow \implies$ **-2.98% monthly abnormal return** ($t = -3.96$).
2. **Demand Inward (DIN):** Fee $\downarrow$ AND Quantity $\downarrow \implies$ $+0.50\%$ monthly abnormal return ($t = 0.58$, statistically insignificant).
3. **Supply Inward (SIN):** Fee $\uparrow$ AND Quantity $\downarrow \implies$ $+0.35\%$ monthly abnormal return ($t = 0.44$, statistically insignificant).
4. **Supply Outward (SOUT):** Fee $\downarrow$ AND Quantity $\uparrow \implies$ $-0.63\%$ monthly abnormal return ($t = 0.91$, statistically insignificant).

When outward demand shifts are large (top decile fee increase and top decile quantity increase), subsequent abnormal returns widen to **-4.48% per month** ($t = -2.32$). When conditioning on high baseline borrow costs (fee $> 3\%$), DOUT drives an extraordinary **-6.44% abnormal return** ($p < 0.01$).

---

## 2. Institutional Extracts (20 Verbatim Citations & Quantitative Benchmarks)

### Extract 1: Abstract & Core Predictive Finding
> "Using proprietary data on stock loan fees and quantities from a large institutional investor, we examine the link between the shorting market and stock prices. Employing a unique identification strategy, we isolate shifts in the supply and demand for shorting. We find that shorting demand is an important predictor of future stock returns: An increase in shorting demand leads to negative abnormal returns of 2.98% in the following month. Second, we show that our results are stronger in environments with less public information flow, suggesting that the shorting market is an important mechanism for private information revelation." (p. 1)

### Extract 2: Price-Quantity Identification Strategy
> "Instead of taking a component of the intersection of supply and demand and using it to proxy for demand or supply (thereby assuming the opposite curve is inelastic, or does not shift), as is common in the literature, we attempt to disentangle these two effects. We are able to infer if a stock has experienced an increase or decrease in shorting demand or shorting supply by exploiting price-quantity 'pairs.' For example, an increase in the loan fee (our measure of price) coupled with an increase in the percentage of outstanding shares on loan (our measure of quantity) corresponds to at least an increase in shorting demand, as would be the case for any increase in price coupled with an increase in quantity... for a shift of price and quantity into this quadrant, at least a demand shift outward must have occurred." (pp. 2-3)

### Extract 3: Economic Mechanisms — Private Information vs. Cost of Capital
> "Mechanically, if shorting demand is the dominant channel, then the coupling of both increased (decreased) price (i.e., loan fee) and increased (decreased) quantity (i.e., short interest, or percentage of shares on loan) are important. Increased quantity, for instance, could be informative for future stock returns if it proxies for additional market frictions or risks of shorting, or if it signals a higher probability of informed trading. For example, if short-selling capital is limited, then taking a large short position in a stock potentially subjects a short-seller to idiosyncratic risk that she cannot diversify away... Alternatively, as in Diamond and Verrecchia (1987), high unexpected short interest may signal a large quantity of negative private information, since fewer liquidity traders (or those shorting for hedging purposes) are likely to short in the face of high short selling costs." (p. 3)

### Extract 4: Supply Shifts as Passive Custodian Frictions
> "The factors driving changes in shorting supply are different. Supply shifts are driven by changes in institutions' marginal cost of lending. For instance, because many lending institutions (including ours) also operate mutual funds, they have other incentives for holding stocks. Following a sale of the shares of a certain stock in its funds, a lending institution experiences an inward shift of its supply curve for the stock... Supply shifts inward (outward) indicate tightening (loosening) of short sale constraints, while demand shifts capture either informed trading or the additional market frictions and risks associated with shorting." (p. 3)

### Extract 5: Failure of Loan Fee as a Sufficient Statistic
> "We also find that the loan fee is not a sufficient statistic for overpricing, as proposed in the previous literature. Rather, 'specialness' (i.e., a high loan fee) is only important for future returns when driven by increases in shorting demand." (p. 4)

### Extract 6: Trading Rule Profits and Sharpe Ratio
> "Net of shorting costs, on average the investor makes over 47% per year. Even after incorporating trading costs such as commissions, bid-ask spreads, and price impact, a conservative estimate of the average return performance of the strategy still yields 4.5% per year. The Sharpe ratio of the strategy is about 2.5 to 3.5 times that of the market or HML. Thus, the indirect costs of shorting would have to be extremely large, or arbitrage capital would have to be very limited for this strategy to represent a risk premium earned by short-sellers." (p. 4)

### Extract 7: Data Sample & Lending Market Dominance
> "The data include daily contract-level data on rebate rates, the number shares on loan, collateral amounts, collateral/market rates, estimated income from each loan, and broker firm names for the entire universe of this firm's lending activity from September 1999 to August 2003... For each observation, we compute the loan fee, which is equal to the interest rate on cash funds (known as the 'market rate' or 'collateral rate') minus the rebate rate... our lender accounts for a substantial fraction of overall market lending in small cap securities. For example, among stocks below (above) the NYSE median market capitalization that are also on loan by our lender, the average ratio of our fund's percentage on loan to the total short interest is 26% (2%); in 13.6% of the observations the fund is responsible for at least 67% of the short interest, and in 7.5% of the observations the fund is responsible for all of the short interest." (pp. 8-10)

### Extract 8: Contract Characteristics and Cost Heterogeneity (Table I)
> "Panel A of Table I presents lending activity examples from our sample. A typical large stock such as Intel has a very small loan fee (0.05% per year), and our lending institution lends out only a fraction of the total shares outstanding. By contrast, for a small stock, such as Atlas Air, the loan fee can be very high (7.25% per year), and our institution may lend out a large share (almost 5%) of the total shares outstanding... making an average of 11.79 loans per stock per day across all small cap stocks as opposed to 4.64 for large stocks." (p. 9)

### Extract 9: Shift Magnitudes and Characteristics (Table II)
> "Summary statistics of the effect of each type of shift on both loan fee (price) and the quantity on loan are presented in Table II. The average change in loan fee from each of the shifts is roughly 40 basis points, except for SOUT, which results in a 56 basis point decrease on average. The average change in shares on loan as a percentage of shares outstanding following each shift is approximately 0.30%... on average the number of stocks per month that experience at least an outward demand shift (DOUT) is 22 (median=14)." (p. 13)

### Extract 10: Baseline Cross-Sectional Regression Specification (Equation 1)
> "Specifically, we regress the cross-section of characteristically-adjusted individual stock returns at time $t$ on a constant, $DIN$, $DOUT$, $SIN$, $SOUT$, $r_{-1}$ (last month's/week's return), $r_{-12,-2}$ (the return from month $t-12$ to $t-2$), $IO$ (institutional ownership, measured as a fraction of shares outstanding lagged one quarter), $volume$ (the average daily exchange-adjusted share turnover during the previous six months), $Loan\ Fee$, $Quantity$, $\Delta(Loan\ Fee)$, and $\Delta(Quantity)$:
> $$r_{j,t} - R_{SB\ j,t-1}^t = \alpha_t + \beta_1 DIN_{j,t-1} + \beta_2 DOUT_{j,t-1} + \beta_3 SIN_{j,t-1} + \beta_4 SOUT_{j,t-1} + \beta_5 r_{j,t-1} + \beta_6 r_{j,t-12,-2} + \beta_7 IO_{j,t-3} + \beta_8 Volume_{j,t-7,-1} + \varepsilon_{j,t}$$
> where $r_{j,t}$ is the return on security $j$ and $R_{SB\ j,t-1}^t$ is the return on the size/book-to-market-matched portfolio." (pp. 14-15)

### Extract 11: Table III Primary Empirical Finding — DOUT Alpha
> "The cross-sectional regression estimates in Table III indicate that increases in the demand for shorting ($DOUT$) lead to large negative abnormal returns in the future. Column two of Table III indicates that even after characteristically adjusting for size and book-to-market and controlling for past returns, institutional ownership, and volume on the right-hand side of these regressions, average abnormal returns for stocks experiencing an outward shift in shorting demand are -2.98% in the following month ($t=-3.96$)... average abnormal returns for stocks experiencing an outward shift in shorting supply ($SOUT$) are -0.63% ($t=0.91$). Decreases in shorting demand ($DIN$) and decreases in shorting supply ($SIN$) lead to positive, but insignificant abnormal returns in the future (0.50% and 0.35% per month, respectively)." (pp. 15-16)

### Extract 12: Table III Models 7–9 — Conditioning on High Costs and Quantity Changes
> "Consistent with a number of recent papers (Jones and Lamont (2002), Reed (2002), and Geczy, Musto, and Reed (2002)), we find that high shorting costs, specifically $Loan\ Fee > 5\%$ per annum, predict future negative returns. However, when we include the shift variables in column 7, the conditional effect of these high costs is no longer significant, while $DOUT$ remains large and significant (-2.36%, $t=3.27$)... when the shift portfolios are included, the conditional effect of $\Delta Quantity$ decreases. Also, $DOUT$ remains negative and highly significant (-2.49%, $t=-3.19$)." (pp. 16-17)

### Extract 13: High-Frequency Price Adjustment Speed (Daily & Weekly Dynamics)
> "When we regress weekly abnormal returns (size/book-to-market adjusted) on the four shift variables the coefficient on $DOUT$ is -0.56%, statistically significant ($t=-2.24$). Compounding this result to monthly returns yields 2.26%, which is similar to the monthly results... Starting with daily $DOUT$ shifts, Figure 1 shows that abnormal returns are negative contemporaneously as well as on the second, fourth, and fifth days after the shift; the second and fourth days, as well as the five-day average, are marginally significant... prices respond mainly to increases in shorting demand, and this price adjustment seems to occur at a weekly frequency, and even more strongly at a monthly frequency. This fits well with our empirical observation that the average lending contract position in our sample lasts for nearly one month." (pp. 17-18)

### Extract 14: Table IV Large Shifts — Joint Fee and Quantity Outliers
> "To investigate the importance of large shifts, we supplement our baseline regression specification by interacting our four shifts with three additional variables: 1) $\Delta Fee_{big}^+$, a dummy variable equal to one if the change in the loan fee for month $t-1$ is greater than the 90th percentile... 3) $\Delta Quantity_{big}^+$, a dummy variable equal to one if the change in quantity on loan for month $t-1$ is greater than the 90th percentile... column 4 shows that the marginal effect of large increases in fees coupled with large increases in quantity, which capture large $DOUT$ shifts ($=\Delta Fee_{big}^+ \times \Delta Quantity_{big}^+$), is large in magnitude (-4.48%) and statistically significant ($t=2.32$)." (pp. 19-20)

### Extract 15: Table IV Model 6 — Dissecting Specialness (High Cost $\times$ Shift)
> "We test this idea in our regression context by interacting each of the shifts during month $t-1$ with a dummy variable equal to one if the level of the loan fee is greater than 3% per annum at the end of month $t-1$. Column 6 of Table IV indicates that the strongest and most reliable negative abnormal returns following these high cost months occur after $DOUT$ shifts (-4.14%, $t=2.69$). Comparing the effect of $DOUT$ and $SIN$ for a given level of loan fee, when $DOUT$ causes the higher loan fee, it has significant predictive power for subsequent abnormal returns that is over two times the magnitude of $SIN$." (p. 20)

### Extract 16: Table V Monthly Long/Short Portfolio Sorts
> "Panels B and C show that $DOUT$ stocks earn average (equal-weight) abnormal returns in the subsequent month of -2.34% per month when benchmarked relative to size/book-to-market portfolios and -2.11% per month when benchmarked relative to size/book-to-market/momentum portfolios... The trading strategy of buying stocks that have demand shifts inward and shorting stocks that have demand shifts outward ($DIN - DOUT$) yields a large and statistically significant return of around 3% per month in each panel of equal-weight returns (excess return = +3.48%/month, Sharpe = 0.338)." (pp. 21-22, 27-28)

### Extract 17: Table VI Robustness — Industry Controls and Lender Market Dominance
> "First, we augment our cross-sectional regressions in Table III by using industry dummy variables in addition to calendar time dummies, using Fama and French's (1997) 48-industry classification scheme. Column 1 of Table VI shows that the coefficient on $DOUT$ is slightly larger and even more significant using this regression specification... When we interact $DOUT$ (in column 4 of Table VI) with a dummy variable indicating that our institution's Market Power is greater than two-thirds, the coefficient on this interaction term is large (-8.36% per month) and significant ($t=2.70$)." (pp. 22-23)

### Extract 18: Table VI Model 5 — Public Short Interest Ratio (SIR) Cross-Validation
> "To overcome the shortcoming of having only one lender in our sample, we also employ monthly short interest from NYSE, AMEX, and Nasdaq scaled by total shares outstanding as our quantity measure... Column 5 of Table VI shows that even after characteristically adjusting for size and book-to-market and controlling for past returns, institutional ownership, and volume on the right-hand side of these regressions, average abnormal returns for stocks experiencing an outward shift in shorting demand are -1.26% in the following month ($t=2.06$)." (pp. 23-24)

### Extract 19: Table VII Mechanism — Private Information vs. Public Coverage
> "As column 2 of Table VII shows, the evidence for increases in shorting demand leading to large declines in future stock returns is not concentrated among stocks with high residual coverage. The interaction term between $DOUT$ and residual coverage is very close to zero... In our sample, untabulated results reveal that dividend payments are also positively related to demand shifts out. Column 3 of Table VII shows that the effect of $DOUT$ is still negative and strongly significant after controlling for those $DOUT$ shifts that occur in dividend months. The interaction term, $DIV \times DOUT$, is positive and insignificant. When adding the interaction term to the main effect, $DOUT + DIV \times DOUT (= -0.845\%)$ is not significantly different from zero. Thus, demand shifts that are likely to be unrelated to private information are not significantly related to future returns." (pp. 25-26)

### Extract 20: Table VIII Limits of Arbitrage & Small Cap Concentration
> "However, as column 3 of Table VIII shows, the effect of $DOUT$ is concentrated in small stocks, as the marginal effect of $ME_{small} \times DOUT$ is strongly significant. This result indicates that the total effect of a $DOUT$ shift for a stock below the 20th percentile of market capitalization is -6.31% ($=-2.407 + -3.903$) next month. Further, the marginal effect of interacting $DOUT$ with a measure of stock-level arbitrage risk ($IRISK_{high}$)... is insignificant... interacting $DOUT$ with a dummy variable equal to one if the stock's volume is above the 80th percentile ($Volume_{high} \times DOUT$) is insignificant." (pp. 28-29)

---

## 3. Companion Papers Synthesized

### A. Engelberg, Reed & Ringgenberg (2012) — JF
- Short sellers are information processors, accumulating short positions **20+ days prior** to negative public news (earnings misses, analyst downgrades).
- The predictive power of short-selling flow concentrates in periods **disagreeing with consensus**: short sales spiking while analyst consensus is buy/hold.

### B. Rapach, Ringgenberg & Zhou (2016) — JFE
- Cross-sectional Short Interest Ratio ($SIR = \frac{\text{Shares Short}}{\text{Shares Outstanding}}$) forecasts individual stock returns with $t > 4.0$.
- In WorldQuant BRAIN, $SIR$ level is captured by `short_interest_ratio`. The top decile of $SIR$ consistently underperforms the bottom decile.

### C. Asquith, Pathak & Ritter (2005) — JFE
- The short anomaly is severely amplified in stocks subject to **joint constraints**:
  $$\text{Constrained Regime} = \text{High } SIR \times \text{Low Institutional Ownership}$$
- When institutional ownership is low ($< 30\%$), lendable supply is scarce, magnifying the pricing impact of short sellers ($ -2.15\%$ monthly spread).

---

## 4. WorldQuant BRAIN Mathematical Translation & Operator Mapping

| Empirical Concept | Mathematical Formula | WorldQuant BRAIN Expression |
|---|---|---|
| **CDM 2007 Baseline Demand Shift** | $\Delta SIR_{21d} > 0 \land \text{Fee} \uparrow$ | `trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.65, group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), 14)), subindustry), -1)` |
| **CDM 2007 Large Shift Outlier** | $\Delta SIR_{21d} \in \text{Top 10\%} \land \Delta\text{Fee} \in \text{Top 10\%}$ | `trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.85, group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), 10)), 0.5), subindustry), -1)` |
| **CDM 2007 Small Cap Focus** | $DOUT \times \text{SmallCap}$ | `trade_when(rank(-cap) > 0.60, trade_when(rank(ts_delta(short_interest_ratio, 21)) > 0.65, group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), 14)), sector), -1), -1)` |
| **APR 2005 Constrained Interaction** | $SIR \times (1 - \text{InstOwn})$ | `trade_when(rank(short_interest_ratio) > 0.60, group_neutralize(rank(-ts_decay_linear(short_interest_ratio, 14)) * rank(-ts_decay_linear(institutional_ownership_percentage, 14)), subindustry), -1)` |
| **ERR 2012 Informed News Pre-emption** | $\Delta SIR_{21d} \times (-\text{SUE})$ | `group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), 14)) * rank(-ts_decay_linear(earnings_surprise, 14)), subindustry)` |
| **Liquidity-Adjusted Days-to-Cover** | $\frac{SIR}{\text{ADV20}}$ | `group_neutralize(signed_power(rank(-ts_decay_linear(short_interest_ratio / (adv20 + 0.001), 14)), 0.5), subindustry)` |
| **CDM Table III Model 1 Short-Term Reversal Control** | $DOUT \times (-r_{-1})$ | `group_neutralize(rank(-ts_decay_linear(ts_delta(short_interest_ratio, 21), 10)) * rank(-ts_decay_linear(returns, 5)), subindustry)` |
| **CDM Table VII Dividend Neutrality Gate** | $DOUT \text{ in non-div regime}$ | `trade_when(ts_delta(short_interest_ratio, 21) > ts_std_dev(short_interest_ratio, 63), group_neutralize(rank(-ts_decay_linear(short_interest_ratio, 14)), sector), -1)` |
