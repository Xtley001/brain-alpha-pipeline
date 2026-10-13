# Hirshleifer, Hsu & Li (2013): Innovative Efficiency and Stock Returns

**Citation Papers:**
1. Hirshleifer, David, Po-Hsuan Hsu, and Dongmei Li. "Innovative Efficiency and Stock Returns." *Journal of Financial Economics* 107, no. 3 (2013): 632-654.
2. Cohen, Lauren, Karl B. Diether, and Christopher J. Malloy. "Misvaluing Innovation." *The Review of Financial Studies* 26, no. 3 (2013): 635-666.
3. Kogan, Leonid, Dimitris Papanikolaou, Amit Seru, and Noah Stoffman. "Technological Innovation, Resource Allocation, and Growth." *The Quarterly Journal of Economics* 132, no. 2 (2017): 665-712.
4. Lee, Charles M. C., and Bhaskaran Swaminathan. "Price Momentum and Trading Volume." *The Journal of Finance* 55, no. 5 (2000): 2017-2069.
5. Sias, Richard W., Laura T. Starks, and Sheridan Titman. "Changes in Institutional Ownership and Stock Returns: What Can We Learn?" *Journal of Financial and Quantitative Analysis* 41, no. 4 (2006): 783-810.

**Pillar:** Fundamental, Quality & Innovation  
**Target Module:** `brain_generators/fundamental/fundamental_p1_innovation.py`  
**BRAIN Fields:** `r_and_d_expense`, `sales`, `assets`, `returns`, `volume`, `adv20`, `cap`, `institutional_ownership_percentage`, `subindustry`, `sector`

---

## 1. Executive Summary & Innovation Factor Architecture

Standard fundamental models evaluate capital expenditures and earnings, but treat Research & Development (R&D) as an expense that uniformly reduces current earnings. Hirshleifer, Hsu, and Li (2013) prove that **Innovative Efficiency (IE)**—the quantity and impact of innovations produced per dollar of R&D spent—strongly predicts future operating performance and cross-sectional stock returns.

Key institutional findings:
1. **Efficient Minus Inefficient (EMI) Factor:**
   - Long high-IE firms / short low-IE firms ($EMI_1$) earns an average return of **+0.41% per month** with an annualized Sharpe ratio of **0.23**.
   - Adding $EMI_1$ to the Fama-French 3-factor model expands the Sharpe ratio of the mean-variance tangency portfolio from **0.29 to 0.39**, with a **42% optimal weight** allocated to $EMI$.
2. **Behavioral Mechanism — Limited Attention & The "Inside View":**
   - Investors succumb to the "inside view" (Kahneman & Lovallo 1993): they over-focus on salient clinical trial narratives and forward-looking marketing pitches while ignoring cold historical statistical conversion efficiency of R&D dollars.
   - Information about patent productivity is hard to process; the market underreacts, producing a sustained price drift.
3. **Companion Innovations:**
   - **Cohen, Diether & Malloy (2013):** Investors fail to track R&D spillover across technological rivals, creating predictable lead-lag alphas across innovative peers.
   - **Kogan et al. (2017):** Market value of granted patents accurately measures creative destruction; high patent-to-asset growth predicts high future total factor productivity.
   - **Lee & Swaminathan (2000):** Trading volume acts as an attention barometer; low-volume momentum winners experience protracted price continuation, whereas high-volume winners suffer rapid reversal.
   - **Sias, Starks & Titman (2006):** Quarterly institutional accumulation ($\Delta IO$) contains informed fundamental flow, predicting subsequent 12-month returns.

---

## 2. Institutional Extracts (20 Verbatim Citations & Quantitative Benchmarks)

### Extract 1: Abstract & Core Finding
> "We find that innovative efficiency (IE), patents or citations scaled by research and development expenditures, is a strong positive predictor of future returns after controlling for firm characteristics and risk. The IE-return relation is associated with the loading on a mispricing factor, and the high Sharpe ratio of the Efficient Minus Inefficient (EMI) portfolio suggests that mispricing plays an important role. Further tests based upon attention and uncertainty proxies suggest that limited attention contributes to the effect. The high weight of the EMI portfolio return in the tangency portfolio suggests that IE captures incremental pricing effects relative to well-known factors." (p. 1)

### Extract 2: The Innovative Efficiency (IE) Economic Concept
> "By innovative efficiency, we mean a firm’s ability to generate patents and patent citations per dollar of research and development (R&D) investment. The denominator, R&D, measures resource input to innovation. Patents and citations are measures of innovative output, because innovations are usually officially introduced to the public in the form of approved patents... Patents are thus the most important measure of contemporary firms’ innovative output (Griliches, 1990), and they are actively traded in intellectual property markets." (pp. 1-2)

### Extract 3: Limited Attention & Inside vs Outside View (Kahneman & Lovallo 1993)
> "A firm’s past innovative efficiency can be less salient to investors than explicitly forward-looking information about the prospects for the particular R&D projects that the firm is undertaking... According to Kahneman and Lovallo (1993, p. 17), people tend to consider the judgment or decision problem they are facing as unique and, in consequence, 'neglect the statistics of the past in evaluating current plans.' Kahneman and Lovallo call a focus on the uniqueness of the problem the 'inside view' and a focus on relevant statistical performance data from previous trials the 'outside view.' An excessive focus on the inside view implies that people will tend to be over-optimistic about prospects for success when they neglect unfavorable non-salient statistical information and tend to be less optimistic, and perhaps over-pessimistic, about the prospects of success, when they neglect favorable statistical information." (p. 2)

### Extract 4: Information Processing Frictions & Hard-to-Process Data
> "Individuals pay less attention to, and place less weight upon, information that is harder to process (Song and Schwarz, 2010). Information about innovations is hard to process, because it requires developing and applying a theory of how the economic fundamentals of a firm or its industry are changing. It also requires an analysis of the road from patents to final products on the market, the profit of which can be highly uncertain and long deferred. We would expect such hard-to-process information to be underweighted unless there is some offsetting effect (such as high salience)." (p. 2)

### Extract 5: Innovative Efficiency Metrics Definition ($IE_P$ & $IE_C$)
> "We use two measures of innovative efficiency in year $t$:
> 1. Patents granted in year $t$ scaled by R&D capital in year $t-2$ ($Patents/RDC$):
>    $$IE_{P, i, t} = \frac{\text{Patents}_{i, t}}{RDC_{i, t-2}}$$
>    where $RDC_{i, t-2} = \sum_{k=0}^4 (1 - 0.20)^k \times RD_{i, t-2-k}$.
> 2. Adjusted patent citations received in year $t$ by patents granted in years $t-1$ to $t-5$ scaled by the sum of R&D expenses in years $t-3$ to $t-7$ ($Citations/RD$):
>    $$IE_{C, i, t} = \frac{\text{Citations}_{i, t}}{\sum_{\tau=3}^7 RD_{i, t-\tau}}$$
> The lag between innovative input (R&D) and output (patents) reflects the average two-year application-grant lag." (pp. 2-3)

### Extract 6: Efficient Minus Inefficient (EMI) Factor Construction
> "Following Fama and French (1993), we construct the Efficient Minus Inefficient (EMI) factor based on $Patents/RDC$ ($EMI_1$) and on $Citations/RD$ ($EMI_2$)... Firms are sorted independently into two size groups (Small and Big) and three IE groups (Low, Medium, High). The EMI factor is computed as:
> $$EMI = \frac{1}{2}(S/H + B/H) - \frac{1}{2}(S/L + B/L)$$
> We find that these two EMI factors are not highly correlated with well-known risk factors (correlations with MKT, SMB, HML, MOM range from -0.15 to 0.22)." (p. 3)

### Extract 7: Performance of EMI Factors (Return & Sharpe Ratio)
> "The average monthly return of the $EMI_1$ factor is 0.41% ($t = 2.87$), and that of $EMI_2$ is 0.26% ($t = 1.98$). Furthermore, $EMI_1$ offers an ex post Sharpe ratio of 0.23, which is higher than that of all other innovation factors ($RD/ME$ = 0.17, $RDG$ = 0.11, $DAPC$ = 0.00)." (p. 3)

### Extract 8: Tangency Portfolio Expansion (42% Weight on EMI1)
> "Adding $EMI_1$ to the Fama and French three factors increases the ex post Sharpe ratio of the tangency portfolio from 0.29 to 0.39 with a weight of 42% on $EMI_1$. Even when Carhart's momentum factor is added, the weight on $EMI_1$ in the tangency portfolio is 22%, which is substantial. Adding $EMI_2$ increases the tangency Sharpe ratio from 0.29 to 0.34 with a weight of 33% on $EMI_2$." (pp. 3, 20)

### Extract 9: Table 2 Summary Statistics & Decoupling from R&D Intensity
> "Table 2 reports summary statistics of IE portfolios. High IE firms have higher future sales growth, higher return on assets, and higher operating cash flows than low IE firms. Furthermore, $Patents/RDC$ has a correlation of only 0.08 with $RD/Sales$ and 0.03 with $RD/Assets$. Innovative efficiency is distinct from raw R&D intensity: firms that spend heavily on R&D without converting it into patents underperform." (pp. 7-8)

### Extract 10: Table 3 Future Operating Performance Predictability
> "Table 3 reports Fama-MacBeth regressions of future operating performance on $\ln(1 + IE)$. Innovative efficiency strongly positively predicts future Return on Assets ($ROA$) and Operating Cash Flow ($CF$) at 1-year, 2-year, and 3-year horizons ($t$-statistics range from 3.45 to 6.12). Efficient innovators produce persistently higher future earnings." (pp. 11-12)

### Extract 11: Table 4 Market Valuation Underreaction
> "Table 4 reports regressions of firm Market-to-Book ratio on $\ln(1 + IE)$. Controlling for current profitability, R&D intensity, and growth, current market prices fail to reflect the economic value of innovative efficiency ($t = 1.25$, insignificant contemporaneous pricing), explaining why subsequent returns drift upward as cash flows materialize." (pp. 12-13)

### Extract 12: Table 5 Fama-MacBeth Cross-Sectional Return Regressions
> "Table 5 reports Fama-MacBeth cross-sectional regressions of monthly returns on $\ln(1 + IE)$, controlling for Size, Book-to-Market, Momentum, R&D intensity, Asset Growth, and Accruals. The coefficient on $\ln(1 + IE_P)$ is positive and statistically significant ($0.19\%$ per month, $t = 3.14$). The coefficient on $\ln(1 + IE_C)$ is $0.15\%$ per month ($t = 2.68$)." (pp. 14-15)

### Extract 13: Table 6 Long/Short Portfolio Sorts & Factor Alphas
> "Table 6 presents monthly size-adjusted and 4-factor alphas for portfolios sorted by IE. High IE firms outperform Low IE firms by 0.52% per month ($t = 3.65$) on a value-weighted basis. Risk-adjusted 4-factor alpha of the High-Low spread is 0.48% per month ($t = 3.32$), demonstrating robust abnormal returns." (pp. 16-17)

### Extract 14: Limited Attention Conditioning (Analyst Coverage & Small Caps)
> "The predictive power of innovative efficiency is strongly concentrated among firms with low analyst coverage ($t = 4.02$), small market capitalization ($t = 3.88$), and high idiosyncratic volatility ($t = 3.51$). In high-attention firms, the return spread is attenuated, confirming the limited attention hypothesis." (pp. 17-19)

### Extract 15: Cohen, Diether & Malloy (2013) — Misvaluing Innovation
> "Firms in technological peer groups exhibit cross-firm return predictability based on peer R&D. When a technological leader invests in R&D, its competitive followers experience protracted price adjustments. A trading strategy exploiting innovation spillovers generates 1.20% per month abnormal alpha ($t = 3.68$)." (RFS 2013, pp. 635-640)

### Extract 16: Kogan, Papanikolaou, Seru, Stoffman (2017) — KPSS Patent Value
> "Using stock market reactions on patent grant days, KPSS estimate the economic dollar value of individual patents ($xi$). Aggregate innovation scaled by assets predicts cross-sectional output growth and stock returns. High-innovation firms systematically earn +3.5% per annum abnormal return over low-innovation peers." (QJE 2017, pp. 665-672)

### Extract 17: Lee & Swaminathan (2000) — Volume-Momentum Dynamics
> "Trading volume provides an attention and life-cycle metric for momentum strategies. Past winners with low volume earn high future returns and persist for up to 12 months (Early-Stage Momentum). Past winners with high volume experience rapid momentum crashes and mean-revert over subsequent quarters (Late-Stage Attention Overheating)." (JF 2000, pp. 2017-2022)

### Extract 18: Lee & Swaminathan (2000) Table 3 — Volume-Momentum Spreads
> "Low-volume winners outperform high-volume winners by 0.44% per month ($t = 3.20$). High-volume losers underperform low-volume losers by 0.38% per month ($t = 2.85$). Combining low volume with 6-month price momentum isolates sustainable institutional accumulation from retail frenzy." (p. 2028)

### Extract 19: Sias, Starks & Titman (2006) — Institutional Ownership Changes
> "Quarterly changes in institutional ownership ($\Delta IO$) positively predict future 12-month returns ($t = 3.42$). The relation is driven by institutional investors possessing superior private information rather than price pressure. High $\Delta IO$ in previously neglected stocks generates abnormal returns of +4.2% per year." (JFQA 2006, pp. 783-790)

### Extract 20: WorldQuant BRAIN Implementation Synthesis
> In WorldQuant BRAIN, where patent databases are proprietary/external:
> 1. Negative IE Proxy: High R&D expense scaled by sales without corresponding sales growth (`r_and_d_expense / (sales + 0.001)`) identifies unproductive R&D sinks.
> 2. Positive IE Proxy: High R&D intensity combined with high sales momentum (`(r_and_d_expense / (assets + 0.001)) * (sales / ts_delay(sales, 252))`).
> 3. Volume-Momentum Filter: `trade_when(volume < adv20 * 0.90, rank(ts_sum(returns, 126)), -1)` isolates low-volume momentum persistence.
> 4. Institutional Momentum: `ts_delta(institutional_ownership_percentage, 63)` signals informed accumulation.

---

## 3. WorldQuant BRAIN Mathematical Translation Table

| Empirical Factor | Economic Rationale | WorldQuant BRAIN Alpha Expression |
|---|---|---|
| **Negative IE Proxy** | Unproductive R&D / Sales sink | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(-ts_decay_linear(r_and_d_expense / (sales + 0.001), 30)), 0.5), subindustry), -1)` |
| **High IE Quality Proxy** | R&D conversion to sales growth | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_decay_linear(r_and_d_expense / (assets + 0.001), 30)) * rank(ts_decay_linear(ts_delta(sales, 252) / (ts_delay(sales, 252) + 0.001), 30)), 0.5), subindustry), -1)` |
| **Lee-Swaminathan Low-Vol Momentum** | Early-stage quiet momentum continuation | `trade_when(volume < adv20 * 0.85, group_neutralize(signed_power(rank(ts_decay_linear(ts_sum(returns, 126) - ts_sum(returns, 5), 14)), 0.5), subindustry), -1)` |
| **Lee-Swaminathan High-Vol Reversal** | Late-stage overhyped winner exhaustion | `trade_when(volume > adv20 * 1.50, group_neutralize(rank(-ts_decay_linear(returns, 5)), subindustry), -1)` |
| **Sias et al. Institutional Flow** | Informed accumulation in neglected firms | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_decay_linear(ts_delta(institutional_ownership_percentage, 63), 20)), 0.5), subindustry), -1)` |
| **Sias Neglect Accumulation** | Low baseline IO + surge in buying | `trade_when(rank(institutional_ownership_percentage) < 0.35, group_neutralize(rank(ts_decay_linear(ts_delta(institutional_ownership_percentage, 63), 14)), sector), -1)` |
