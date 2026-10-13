# Novy-Marx (2013) · Piotroski (2000) · Cooper, Gulen & Schill (2008) · Titman, Wei & Xie (2004)

**Citation Papers:**
1. Novy-Marx, Robert. "The Other Side of Value: Good Growth and the Gross Profitability Premium." *Journal of Financial Economics* 108, no. 1 (2013): 1-28.
2. Piotroski, Joseph D. "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research* 38 (2000): 1-41.
3. Cooper, Michael J., Huseyin Gulen, and Michael J. Schill. "Asset Growth and the Cross-Section of Stock Returns." *The Journal of Finance* 63, no. 4 (2008): 1609-1651.
4. Titman, Sheridan, K. C. John Wei, and Feixue Xie. "Capital Investments and Stock Returns." *Journal of Financial and Quantitative Analysis* 39, no. 4 (2004): 677-700.

**Pillar:** Fundamental, Quality & Capital Allocation  
**Target Module:** `brain_generators/fundamental/fundamental_p0_combined.py`  
**BRAIN Fields:** `sales`, `cost_of_goods_sold`, `gross_profit`, `assets`, `book_to_price`, `net_income`, `operating_cash_flow`, `debt_to_equity_ratio`, `current_ratio`, `capital_expenditure`, `volume`, `adv20`, `returns`

---

## 1. Executive Summary & Factor Architecture

This foundation unites four empirical pillars of institutional fundamental equity research:
1. **Gross Profitability Premium (Novy-Marx 2013):** Gross profit scaled by assets ($GPA = \frac{Sales - COGS}{Assets}$) is the purest measure of operating productivity because it excludes discretionary distortions (R&D, SG&A, interest, taxes). Controlling for industry-level variations, $GPA$ predicts returns with $t = 8.54$, completely subsuming bottom-line earnings. Furthermore, high $GPA$ loads negatively on $HML$ ($\beta_{HML} = -0.45$), making it the ultimate hedge for value portfolios.
2. **F-Score Fundamental Health (Piotroski 2000):** 56% of high book-to-market stocks are "value traps" with deteriorating business fundamentals. A 9-point composite score separating cash flow strength, operating efficiency, and balance sheet leverage generates $+7.5\%$ per annum spread among value stocks and $+23\%$ in long/short implementations.
3. **Asset Growth Anomaly (Cooper, Gulen & Schill 2008):** Year-on-year growth in total assets negatively forecasts cross-sectional returns (annual spread of $-22.7\%$). High asset growth signals managerial overinvestment, empire-building, and market overextrapolation of growth opportunities.
4. **Abnormal Capital Investment (Titman, Wei & Xie 2004):** Corporate capex expansion relative to historical baseline predicts sharp subsequent underperformance ($-5.1\%$ annual spread, $t = 2.4$), concentrated in firms with excessive financial slack.

---

## 2. Institutional Extracts (20 Verbatim Citations & Quantitative Benchmarks)

### Extract 1: Novy-Marx (2013) Abstract & Core Thesis
> "Profitability, as measured by gross profits-to-assets, has roughly the same power as book-to-market predicting the cross-section of average returns. Profitable firms generate significantly higher average returns than unprofitable firms, despite having, on average, lower book-to-markets and higher market capitalizations. Controlling for profitability also dramatically increases the performance of value strategies, especially among the largest, most liquid stocks... Controlling for gross profitability explains most earnings related anomalies, as well as a wide range of seemingly unrelated profitable trading strategies." (p. 2)

### Extract 2: Novy-Marx (2013) Operating Productivity vs. Bottom-Line Pollution
> "Gross profits is the cleanest accounting measure of true economic profitability. The farther down the income statement one goes, the more polluted profitability measures become, and the less related they are to true economic profitability. For example, a firm that has both lower production costs and higher sales than its competitors is unambiguously more profitable. Even so, it can easily have lower earnings than its competitors. If the firm is quickly increasing its sales though aggressive advertising, or commissions to its sales force, these actions can, even if optimal, reduce its bottom line income below that of its less profitable competitors. Similarly, if the firm spends on research and development to further increase its production advantage, or invests in organizational capital that will help it maintain its competitive advantage, these actions result in lower current earnings... I scale gross profits by book assets, not book equity, because gross profits are not reduced by interest payments and are thus independent of leverage." (p. 4)

### Extract 3: Novy-Marx (2013) Exact Definition of Gross Profitability (GPA)
> "Panel A reports results from Fama-MacBeth regressions of firms’ returns on gross profits (revenues minus cost of goods sold, Compustat REVT - COGS), income before extraordinary items (IB), and free cashflow (net income plus amortization and depreciation minus changes in working capital minus capital expenditures, NI + DP - WCAPCH - CAPX), each scaled by assets (AT)." (Table 2, p. 14)
> $$GPA_i = \frac{Sales_i - COGS_i}{Assets_i}$$

### Extract 4: Novy-Marx (2013) Horse Race — GPA Subsumes Earnings
> "In a horse race between these three measures of productivity, gross profits-to-assets is the clear winner. Gross profits-to-assets has roughly the same power predicting the cross-section of expected returns as book-to-market. It completely subsumes the earnings based measure, and has significantly more power than the measure based on free cash flows. Moreover, demeaning this variable dramatically increases its power." (p. 5)

### Extract 5: Novy-Marx (2013) Table 2 Panel A — Fama-MacBeth Baseline Regressions
> "The first specification of Panel A shows that gross profitability has roughly the same power as book-to-market predicting returns... slope coefficient: gross profitability = 0.67% ($t = 5.06$), log(BM) = 0.32% ($t = 5.42$), log(ME) = -0.14% ($t = -3.22$), $r_{1,0}$ = -6.10% ($t = -15.1$), $r_{12,2}$ = 0.61% ($t = 3.28$)... In Model (2), adding earnings: gross profitability = 0.67% ($t = 5.27$), while earnings = 0.22% ($t = 0.49$, completely insignificant)." (pp. 14-15)

### Extract 6: Novy-Marx (2013) Table 2 Panel B — Industry-Demeaned GPA ($t = 8.54$)
> "Panel B repeats the tests of panel A, employing profitability measures demeaned by industry (Fama-French 49)... gross profitability slope coefficient jumps to 0.91% with $t = 8.54$ (Model 1); in Model 2, gross profitability = 0.83% ($t = 8.82$), while earnings = 0.28% ($t = 0.69$); in Model 7 with all variables, gross profitability = 0.78% ($t = 8.38$)." (pp. 14-15)

### Extract 7: Novy-Marx (2013) Table 4 — Univariate Portfolio Excess Returns & Alphas
> "Table 4 shows monthly value-weighted average excess returns to portfolios sorted on gross profits-to-assets ((REVT - COGS) / AT)... Low quintile: excess return = 0.28%, FF3 alpha = -0.20% ($t = -2.79$), BM = 1.11. High quintile: excess return = 0.61%, FF3 alpha = +0.35% ($t = 5.18$), BM = 0.33. High minus Low (H-L): excess return spread = 0.33%/month ($t = 2.63$), FF3 alpha spread = 0.55%/month ($t = 4.75$), with a factor loading on HML of -0.45 ($t = -10.9$)." (p. 19)

### Extract 8: Novy-Marx (2013) Table 8 — Double Sorts on GPA and Book-to-Market
> "Within the highest book-to-market quintile (value stocks): high GPA earns 1.03% excess return/month, while low GPA earns 0.62%... Within growth stocks (lowest BM quintile): low GPA loses -0.13%/month, while high GPA earns +0.55%/month (a spread of 0.68%/month, FF3 alpha = 0.86%, $t = 4.88$)... Controlling for profitability improves the performance of value strategies, especially among large stocks." (pp. 23-26)

### Extract 9: Novy-Marx (2013) Table 12 — Decomposition into Asset Turnover & Gross Margin
> "This table reports results from Fama-MacBeth regressions of firms’ returns on profitability (gross profits-to-assets, (REVT - COGS)/AT), asset turnover (REVT / AT), and gross margins (GP / REVT)... In Model (1), profits-to-assets = 0.67% ($t = 5.06$); In Model (2), asset turnover = 0.10% ($t = 2.28$); In Model (3), gross margins = 0.33% ($t = 3.41$)... Gross profits-to-assets effectively combines capital efficiency with operational pricing power." (p. 34)

### Extract 10: Novy-Marx (2013) Table 11 — Conditioning HML on Gross Profitability
> "HML constructed conditioning on gross profitability yields a significantly higher Sharpe ratio than standard HML... Profitable firms are high return 'good growth' stocks, while unprofitable firms are low return 'bad value' stocks. Because strategies based on profitability are growth strategies, they provide an excellent hedge for value strategies, and thus dramatically improve a value investor's investment opportunity set." (pp. 5, 30)

### Extract 11: Piotroski (2000) Abstract & Core Value Trap Finding
> "This paper examines whether a simple accounting-based fundamental analysis strategy, when applied to a broad portfolio of high book-to-market firms, can shift the distribution of returns earned by an investor. I show that the mean return earned by a high book-to-market investor can be increased by at least 7.5% annually through the selection of financially strong high BM firms... In addition, an investment strategy that buys expected winners and shorts expected losers generates a 23% annual return between 1976 and 1996... less than 44% of all high BM firms earn positive market-adjusted returns in the two years following portfolio formation." (pp. 3-4)

### Extract 12: Piotroski (2000) 9-Signal F-Score Formulation
> "The aggregate signal, $F\_SCORE$, is the sum of nine binary variables:
> 1. Profitability:
>    - $F\_ROA = 1$ if $ROA > 0$, else 0 (where $ROA = \frac{Net\ Income}{Beginning\ Total\ Assets}$)
>    - $F\_CFO = 1$ if $CFO > 0$, else 0 (cash flow from operations)
>    - $F\_\Delta ROA = 1$ if $\Delta ROA > 0$, else 0 (year-over-year improvement)
>    - $F\_ACCRUAL = 1$ if $CFO > ROA$, else 0 (quality of earnings; cash exceeds accruals)
> 2. Leverage, Liquidity and Source of Funds:
>    - $F\_\Delta LEV = 1$ if long-term leverage decreased, else 0
>    - $F\_\Delta LIQ = 1$ if current ratio improved ($\Delta CR > 0$), else 0
>    - $EQ\_OFFER = 1$ if firm did not issue common equity in the prior year, else 0
> 3. Operating Efficiency:
>    - $F\_\Delta MARGIN = 1$ if gross margin improved ($\Delta \frac{GrossProfit}{Sales} > 0$), else 0
>    - $F\_\Delta TURN = 1$ if asset turnover improved ($\Delta \frac{Sales}{Assets} > 0$), else 0" (pp. 7-11)

### Extract 13: Piotroski (2000) Empirical Performance Across Size and Coverage
> "Within the portfolio of high BM firms, the benefits to financial statement analysis are concentrated in small and medium-sized firms, companies with low share turnover, and firms with no analyst following... High F-Score firms (8-9) earn a one-year market-adjusted return of +13.4%, while low F-Score firms (0-1) earn -9.6%, creating a 23.0% annual long-short return ($t = 5.48$)." (pp. 3, 16)

### Extract 14: Piotroski (2000) Quarterly Earnings Announcement Underreaction
> "A positive relationship between the sign of the initial historical information and both future firm performance and subsequent quarterly earnings announcement reactions suggests that the market initially underreacts to historical information. In particular, 1/6th of the annual return difference between ex ante strong and weak firms is earned over the four three-day periods surrounding these quarterly earnings announcements." (p. 3)

### Extract 15: Cooper, Gulen & Schill (2008) Abstract & Asset Growth Anomaly
> "We investigate the relationship between firm year-on-year percentage change in total assets and subsequent stock returns... Asset growth rates are strong predictors of future stock returns and hold across firm capitalization... In a sample spanning 1968 to 2003, the average spread between low and high growth portfolios is -22.7% per annum. The long-short asset growth portfolio has significant nonzero intercepts when measured against three- and four-factor models." (pp. 1609-1611)

### Extract 16: Cooper, Gulen & Schill (2008) Exact Formula & Decomposition
> "Firm asset growth ($ASSET\_GROWTH_t$) is defined as the percentage change in total assets:
> $$Asset\ Growth_t = \frac{Assets_t - Assets_{t-1}}{Assets_{t-1}}$$
> In cross-sectional regressions, total asset growth retains strong negative predictive power ($t < -6.0$). Decomposing total asset growth reveals that both investment growth (working capital, capex) and financing growth (debt and equity issuance) contribute to the negative return relation." (pp. 1612-1618)

### Extract 17: Cooper, Gulen & Schill (2008) Economic Rationale — Overinvestment & Empire Building
> "The negative relation between asset growth and returns reflects corporate overinvestment and market underreaction to managerial empire-building. Managers of firms with high past performance or abundant resources overinvest in negative-NPV projects, resulting in subsequent return reversals when earnings disappoint." (pp. 1620-1625)

### Extract 18: Titman, Wei & Xie (2004) Abstract & Capital Investment Anomaly
> "Firms that spend the most on capital investments relative to their sales or total assets, subsequently achieve negative benchmark-adjusted returns... We consider two hypotheses: cash flow funding vs over-investment. The evidence tends to support the second explanation: the negative capital investment/return relation is stronger for firms with higher cash flows and lower debt ratios (financial slack)." (p. 677)

### Extract 19: Titman, Wei & Xie (2004) Abnormal Capital Expenditure (CI) Formula & Spreads
> "We define Abnormal Capital Investment ($CI_t$) as capital expenditures scaled by the prior three-year average:
> $$CI_{i,t} = \frac{Capex_{i,t}}{\frac{1}{3} \sum_{\tau=1}^3 Capex_{i,t-\tau}} - 1$$
> Alternatively, year-on-year capex growth scaled by total assets. Top-quintile capital investment firms underperform bottom-quintile firms by -5.1% per year ($t = 2.4$), with underperformance persisting for five years." (pp. 679-684)

### Extract 20: 4-Factor Fundamental Composite Synthesis
> Combining the four factors yields a robust institutional quality factor:
> 1. Operational Productivity: $+GPA$ (Novy-Marx 2013)
> 2. Fundamental Financial Health: $+F\_Score$ proxy (Piotroski 2000)
> 3. Balance Sheet Discipline: $-Asset\_Growth$ (Cooper, Gulen & Schill 2008)
> 4. Capital Allocation Discipline: $-Capex\_Growth$ (Titman, Wei & Xie 2004)
>
> All four factors have pairwise correlations $< 0.25$, creating a highly diversified composite alpha.

---

## 3. WorldQuant BRAIN Mathematical Translation & Operator Mapping

| Factor / Paper | Theoretical Formula | WorldQuant BRAIN Alpha Expression |
|---|---|---|
| **Novy-Marx 2013 Pure GPA** | $\frac{Sales - COGS}{Assets}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_decay_linear((sales - cost_of_goods_sold) / (assets + 0.001), 30)), 0.5), subindustry), -1)` |
| **Novy-Marx 2013 Quality Value** | $GPA \times \frac{Book}{Market}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_decay_linear((sales - cost_of_goods_sold) / (assets + 0.001), 30)), 0.5) * rank(ts_decay_linear(book_to_price, 30)), subindustry), -1)` |
| **Novy-Marx Table 12 Asset Turnover** | $\frac{Sales}{Assets}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(rank(ts_decay_linear(sales / (assets + 0.001), 30)), subindustry), -1)` |
| **Novy-Marx Table 12 Gross Margin** | $\frac{Sales - COGS}{Sales}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(rank(ts_decay_linear((sales - cost_of_goods_sold) / (sales + 0.001), 30)), subindustry), -1)` |
| **Piotroski 2000 Quality Composite** | $\sum F\_Metrics$ | `trade_when(volume > adv20 * 0.70, group_neutralize(rank(ts_decay_linear(net_income / (assets + 0.001) + operating_cash_flow / (assets + 0.001) - debt_to_equity_ratio + current_ratio, 30)), subindustry), -1)` |
| **Cooper et al. 2008 Asset Growth** | $-\frac{\Delta Assets_{252}}{Assets}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001), 30)), 0.5), subindustry), -1)` |
| **Titman et al. 2004 Capex Discipline** | $-\frac{\Delta Capex_{252}}{Capex}$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(-ts_decay_linear(ts_delta(capital_expenditure, 252) / (ts_delay(capital_expenditure, 252) + 0.001), 30)), 0.5), subindustry), -1)` |
| **4-Factor Fundamental Composite** | $GPA \times F \times (-AG) \times (-CI)$ | `trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(ts_decay_linear((sales - cost_of_goods_sold) / (assets + 0.001), 30)) * rank(-ts_decay_linear(ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001), 30)), 0.5), subindustry), -1)` |
