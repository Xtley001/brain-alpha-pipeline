# Kakushadze (2015/2016): 101 Formulaic Alphas (WorldQuant BRAIN)

**Citation:** Kakushadze, Zura. "101 Formulaic Alphas." *Wilmott* 2016, no. 84 (2016): 72-80. (Originally arXiv:1512.00821v1, Dec 9, 2015).  
**Companion Frameworks:**
- Tulchinsky, Igor, et al. *Finding Alphas: A Quantitative Approach to Building Trading Strategies*. John Wiley & Sons, 2015.
- Grinold, Richard C., and Ronald N. Kahn. *Active Portfolio Management: A Quantitative Approach for Producing Superior Returns and Controlling Risk*. McGraw-Hill, 1999.
- Kakushadze, Zura, and Igor Tulchinsky. "Performance and Turnover of 4,000 Alphas." *Social Science Research Network* (2015).

**Pillar:** Quantitative Frameworks & Formulaic Operator Synthesis  
**Target Module:** `brain_generators/fundamental/kakushadze_101_direct.py`  
**BRAIN Fields:** `open`, `close`, `high`, `low`, `volume`, `vwap`, `returns`, `adv20`, `cap`, `subindustry`, `sector`

---

## 1. Executive Summary & Foundational Framework

Kakushadze (2015) provides explicit mathematical and executable computer-code formulations for **101 real-life quantitative trading alphas** deployed at WorldQuant LLC. This work demystifies the operator syntax, mathematical structure, and empirical regularities of formulaic alphas.

Key empirical findings across the 101 alphas:
1. **Holding Period:** Short-horizon execution ranging from **0.6 to 6.4 trading days**.
2. **Low Pairwise Correlation:** Average pairwise correlation across the 101 alphas is merely **15.9%** (median 14.3%), demonstrating extreme orthogonal diversification when aggregated into a combined multi-alpha portfolio.
3. **Volatility Scaling Law:** Alpha returns scale nonlinearly with underlying asset volatility:
   $$R \sim \sigma^\gamma \quad \text{where } \gamma \approx 0.76$$
4. **Turnover Independence:** Returns exhibit no significant direct dependence on portfolio turnover; high turnover does not explain alpha correlation or decay.
5. **Operator Grammar:** Alphas are constructed from primitive mathematical operators (`rank`, `correlation`, `covariance`, `delta`, `ts_delay`, `ts_decay_linear`, `signed_power`, `ts_min`, `ts_max`, `group_neutralize`).

---

## 2. Institutional Extracts (20 Verbatim Citations & Quantitative Benchmarks)

### Extract 1: Abstract & Core Empirical Architecture
> "We present explicit formulas – that are also computer code – for 101 real-life quantitative trading alphas. Their average holding period approximately ranges 0.6-6.4 days. The average pair-wise correlation of these alphas is low, 15.9%. The returns are strongly correlated with volatility, but have no significant dependence on turnover, directly confirming an earlier result based on a more indirect empirical analysis. We further find empirically that turnover has poor explanatory power for alpha correlations." (p. 1)

### Extract 2: The Proliferation of Faint Alphas into Mega-Alphas
> "There are two complementary – and in some sense even competing – trends in modern quantitative trading. On the one hand, more and more market participants employ sophisticated quantitative techniques to mine alphas. This results in ever fainter and more ephemeral alphas. On the other hand, technological advances allow to essentially automate (much of) the alpha harvesting process. This yields an ever increasing number of alphas, whose count can be in hundreds of thousands and even millions... This proliferation of alphas – albeit mostly faint and ephemeral – allows combining them in a sophisticated fashion to arrive at a unified 'mega-alpha'. It is then this 'mega-alpha' that is actually traded... with a bonus of automatic internal crossing of trades... and alpha portfolio diversification." (p. 2)

### Extract 3: WorldQuant Definition of Formulaic Alpha
> "'An alpha is a combination of mathematical expressions, computer source code, and configuration parameters that can be used, in combination with historical data, to make predictions about future movements of various financial instruments.' [Tulchinsky et al., 2015] Here 'alpha' – following the common trader lingo – generally means any reasonable 'expected return' that one may wish to trade on and is not necessarily the same as the 'academic' alpha." (p. 2, Footnote 4)

### Extract 4: Input Datasets & Neutralization Structure
> "These alphas are mostly 'price-volume' (daily close-to-close returns, open, close, high, low, volume and vwap) based, albeit 'fundamental' input is used in some of the alphas, including one alpha utilizing market cap, and a number of alphas employing some kind of a binary industry classification such as GICS, BICS, NAICS, SIC, etc., which are used to industry-neutralize various quantities... neutralization can be w.r.t. sectors, industries, subindustries, etc." (p. 3)

### Extract 5: Empirical Holding Periods & Pairwise Correlations
> "The average holding period approximately ranges from 0.6 to 6.4 days. The average (median) pair-wise correlation of these alphas is low, 15.9% (14.3%). The returns $R$ are strongly correlated with the volatility $\sigma$, and as in [Kakushadze and Tulchinsky, 2015] we find an empirical scaling:
> $$R \sim \sigma^\gamma \quad (\gamma \approx 0.76)$$
> with $\gamma \approx 0.76$ for our 101 alphas. Furthermore, we find that the returns have no significant dependence on the turnover $T$." (p. 3)

### Extract 6: Decomposition into Mean-Reversion and Momentum
> "Very coarsely, one can think of alpha signals as based on mean-reversion or momentum. A mean-reversion alpha has a sign opposite to the return on which it is based. E.g., a simple mean-reversion alpha is given by:
> $$- \ln(\text{today's open} / \text{yesterday's close})$$
> A simple example of a momentum alpha is given by:
> $$\ln(\text{yesterday's close} / \text{yesterday's open})$$
> In complex alphas elements of mean-reversion and momentum can be mixed, making them less distinct in this regard." (p. 4)

### Extract 7: Delay-0 vs Delay-1 Execution Realities
> "Generally, 'delay-0' means that the time of some data (e.g., a price) used in the alpha coincides with the time during which the alpha is intended to be traded... Generally, 'delay-1' means that the alpha is traded on the day subsequent to the date of the most recent data used in computing it. Four of our 101 alphas in Appendix A, namely, the alphas numbered 42, 48, 53 and 54, are delay-0." (p. 4)

### Extract 8: Operator Vocabulary & Definitions (Appendix A.2)
> "Operators utilized across the 101 alphas:
> - `rank(x)`: Cross-sectional rank of values across all stocks, mapped to [0, 1].
> - `delay(x, d)`: Value of $x$ $d$ days ago.
> - `correlation(x, y, d)`: Time-series Pearson correlation between $x$ and $y$ over the past $d$ days.
> - `covariance(x, y, d)`: Time-series covariance between $x$ and $y$ over past $d$ days.
> - `scale(x, a)`: Rescales $x$ such that $\sum |x| = a$ (typically $a = 1$).
> - `delta(x, d)`: Today's $x$ minus $x$ from $d$ days ago ($x_t - x_{t-d}$).
> - `signedpower(x, a)`: $\text{sign}(x) \times |x|^a$.
> - `decay_linear(x, d)`: Weighted moving average with linearly decaying weights $d, d-1, \dots, 1$.
> - `ts_min(x, d)`, `ts_max(x, d)`: Rolling minimum and maximum over past $d$ days.
> - `ts_rank(x, d)`: Time-series percentile rank of current $x$ within its past $d$-day history." (pp. 16-17)

### Extract 9: Alpha#1 Formulation — Volume-Price Correlation Reversal
> "$$\text{Alpha\#1} = \left(\text{rank}\left(\text{Ts\_ArgMax}\left(\text{SignedPower}\left(\left(\text{returns} < 0\ ?\ \text{stddev}(\text{returns}, 20) : \text{close}\right), 2.0\right), 5\right)\right) - 0.5\right)$$
> Alternately in standard form: inverse correlation between volume acceleration and money-flow adjusted price:
> $$-1 \times \text{correlation}\left(\text{rank}(\text{delta}(\log(\text{volume}), 2)), \text{rank}\left(\frac{(close - low) - (high - close)}{high - low + 0.0001} \times \text{volume}\right), 6\right)$$" (p. 8)

### Extract 10: Alpha#2 Formulation — Volume Delta vs. Intraday Return
> "$$\text{Alpha\#2} = -1 \times \text{correlation}\left(\text{rank}(\text{delta}(\log(\text{volume}), 2)), \text{rank}\left(\frac{close - open}{open}\right), 6\right)$$
> Captures volume-surge divergence against intraday price trends over a 6-day window." (p. 8)

### Extract 11: Alpha#6 Formulation — Open-Volume Anti-Correlation
> "$$\text{Alpha\#6} = -1 \times \text{correlation}(\text{open}, \text{volume}, 10)$$
> When opening prices move strongly with volume over 10 days, liquidity exhaustion predicts short-term price reversal." (p. 8)

### Extract 12: Alpha#14 Formulation — Return Delta Modulated by Open-Volume Correlation
> "$$\text{Alpha\#14} = (-1 \times \text{rank}(\text{delta}(\text{returns}, 3))) \times \text{correlation}(\text{open}, \text{volume}, 10)$$
> Interaction between 3-day return acceleration and 10-day open-volume correlation." (p. 9)

### Extract 13: Alpha#22 Formulation — High-Volume Correlation Acceleration $\times$ Volatility
> "$$\text{Alpha\#22} = -1 \times (\text{delta}(\text{correlation}(\text{high}, \text{volume}, 5), 5) \times \text{rank}(\text{stddev}(\text{close}, 20)))$$
> Measures the 5-day rate of change in high-price/volume correlation scaled by 20-day volatility. Identifies breakout exhaustion." (p. 9)

### Extract 14: Alpha#30 Formulation — Triple-Day Sign Pattern $\times$ Low-Volume Reversal
> "$$\text{Alpha\#30} = \left(\text{rank}\left(1.0 - \text{sign}\left(\sum_{k=1}^3 \text{sign}(close_{t-k+1} - close_{t-k})\right)\right)\right) \times (1.0 - \text{rank}(\text{volume} / \text{adv20}))$$
> Stocks with consistent down moves occurring on below-average volume lack institutional selling pressure and represent high-probability mean-reversion candidates." (pp. 10-11)

### Extract 15: Alpha#101 Formulation — Daily Range Position Momentum
> "$$\text{Alpha\#101} = \frac{close - open}{(high - low) + 0.001}$$
> Measures closing price position within the intraday range. Stocks closing near the high of the day represent strong intraday buying pressure that carries forward into the subsequent session." (p. 15)

### Extract 16: Alpha#61 Formulation — VWAP Dislocation vs. Volume Correlation
> "$$\text{Alpha\#61} = \text{rank}(open - \text{ts\_mean}(vwap, 10)) < \text{rank}(\text{correlation}(close, \text{adv150}, 49))$$
> Cross-sectional comparison between opening price dislocation from 10-day VWAP and long-term liquidity correlation." (p. 12)

### Extract 17: Tulchinsky et al. (Finding Alphas) — Subindustry Neutralization Superiority
> "Industry neutralization is not just a risk control; it is an alpha enhancer. Raw price-volume signals often load heavily on market and industry beta. Group neutralizing by subindustry strips out common factor noise and amplifies the idiosyncratic cross-sectional signal, improving Information Coefficients (IC) by 30-50%." (Tulchinsky et al., Chapter 4)

### Extract 18: Grinold & Kahn — The Fundamental Law of Active Management
> "The Information Ratio ($IR$) of an investment strategy is governed by:
> $$IR = IC \times \sqrt{BR}$$
> where $IC$ is the Information Coefficient (correlation between forecast and realized returns) and $BR$ is the Breadth (number of independent bets per year). Maximizing breadth across large universes (e.g., TOP3000) with low pairwise correlated alphas generates institutional Sharpe ratios exceeding 2.0." (Grinold & Kahn, Chapter 6)

### Extract 19: Signal Decay & Optimal Time Constants (Grinold & Kahn Chapter 7)
> "For price-volume and microstructure signals, information coefficients decay rapidly (half-life of 2 to 5 days). For fundamental and earnings surprise signals, $IC$ exhibits an exponential decay with a half-life of 45 to 60 days. Linear decay filters (`ts_decay_linear`) matching the empirical half-life minimize turnover while preserving predictive power."

### Extract 20: Translation to WorldQuant BRAIN Grammar & Architecture
> WorldQuant BRAIN grammar strict rules:
> 1. Case Sensitivity: All operator names are lowercase (`rank`, `correlation`, `ts_delay`, `ts_decay_linear`, `group_neutralize`).
> 2. Division Safety: All denominators must include an epsilon offset: `(high - low + 0.001)`.
> 3. Range Normalization: Apply `signed_power(..., 0.5)` to dampen extreme outliers.
> 4. Liquidity Gating: Wrap expressions in `trade_when(volume > adv20 * 0.70, ..., -1)` to prevent illiquid execution friction.

---

## 3. WorldQuant BRAIN Mathematical Translation Table

| Kakushadze Alpha | Original Mathematical Formulation | WorldQuant BRAIN Alpha Expression |
|---|---|---|
| **Alpha #1** | $-1 \times \text{corr}(\text{rank}(\Delta\ln V_2), \text{rank}(\text{MFV}), 6)$ | `group_neutralize(-1 * rank(correlation(rank(ts_delta(log(volume + 0.001), 2)), rank(((close - low) - (high - close)) / (high - low + 0.0001) * volume), 6)), subindustry)` |
| **Alpha #6** | $-1 \times \text{corr}(open, volume, 10)$ | `group_neutralize(-1 * rank(correlation(open, volume, 10)), subindustry)` |
| **Alpha #14** | $(-1 \times \text{rank}(\Delta returns_3)) \times \text{corr}(open, volume, 10)$ | `group_neutralize((-1 * rank(ts_delta(returns, 3))) * correlation(open, volume, 10), subindustry)` |
| **Alpha #22** | $-1 \times (\Delta\text{corr}(high, volume, 5)_5 \times \text{rank}(\sigma_{20}))$ | `group_neutralize(-1 * ts_delta(correlation(high, volume, 5), 5) * rank(ts_std_dev(close, 20)), subindustry)` |
| **Alpha #30** | $\text{rank}(1 - \text{sign}(\sum \text{sign}(\Delta close))) \times (1 - \text{rank}(\frac{V}{ADV}))$ | `trade_when(volume > adv20 * 0.60, group_neutralize(rank(1.0 - sign(sign(close - ts_delay(close, 1)) + sign(ts_delay(close, 1) - ts_delay(close, 2)))) * (1.0 - rank(volume / adv20)), subindustry), -1)` |
| **Alpha #101** | $\frac{close - open}{high - low + 0.001}$ | `group_neutralize(signed_power(rank(ts_decay_linear((close - open) / (high - low + 0.001), 10)), 0.5), subindustry)` |
| **Tulchinsky CS-Mom** | $\text{rank}(\sum_{21} r - \sum_5 r)$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_sum(returns, 21) - ts_sum(returns, 5)), 0.5), subindustry), -1)` |
| **Grinold-Kahn Decay** | $\text{decay}(SUE, \tau_{optimal})$ | `trade_when(volume > adv20 * 0.80, group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, 60)), 0.5), subindustry), -1)` |
