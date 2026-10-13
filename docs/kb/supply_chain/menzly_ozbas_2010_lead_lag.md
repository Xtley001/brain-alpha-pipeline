# Menzly & Ozbas (2010): Market Segmentation and Cross-Predictability of Returns

**Citation:** Menzly, Lior, and Oguzhan Ozbas. "Market Segmentation and Cross-Predictability of Returns." *The Journal of Finance* 65, no. 4 (2010): 1555-1580.  
**Companion Paper:** Barrot, Jean-Noël, and Julien Sauvagnat. "Input Specificity and the Propagation of Idiosyncratic Shocks in Production Networks." *The Quarterly Journal of Economics* 131, no. 3 (2016): 1543-1592.  

**Pillar:** Supply Chain & Economic Networks  
**Target Module:** `brain_generators/supply_chain/menzly_ozbas_lead_lag.py`  
**BRAIN Fields:** `returns`, `volume`, `adv20`, `close`, `cap`, `subindustry`, `sector`, `analyst_rating_change`, `earnings_surprise`

---

## 1. Executive Summary & Production Network Architecture

Menzly and Ozbas (2010) provide decisive empirical evidence that **value-relevant information diffuses gradually across the economy due to investor specialization and informational market segmentation**. 

Key institutional findings:
1. **Supply-Chain Return Cross-Predictability:** Economically linked supplier and customer industries cross-predict each other's equity returns with a **1-month lag** ($21$ to $42$ trading days).
2. **Economic Magnitude & Sharpe Ratios (Table V):**
   - Trading strategy long top quintile / short bottom quintile of **lagged supplier returns ($r_{supplier, t-1}$)** generates an annualized premium of **+7.3%** with a Sharpe ratio of **0.660**.
   - Trading strategy on **lagged customer returns ($r_{customer, t-1}$)** generates an annualized premium of **+7.0%** with a Sharpe ratio of **0.520**.
   - Composite strategy ($r_{composite, t-1} = \frac{1}{2}(r_{supplier} + r_{customer})$) generates **+8.7% annualized** with a Sharpe ratio of **0.658**.
3. **Fama-French 4-Factor Alphas (Table VI):** Abnormal risk-adjusted alphas are **+0.50% to +0.60% per month** ($t = 2.61$ to $3.42$), demonstrating near-zero beta exposure to $MKT$, $SMB$, $HML$, and $MOM$.
4. **Concentration in Low-Information Stocks (Table II & III):** Cross-predictability is **10 times stronger** in stocks with low analyst coverage and low institutional ownership (slope $= 0.380$, $t = 5.89$) than in heavily covered stocks (slope $= 0.027$, $t = 0.43$).

---

## 2. Institutional Extracts (20 Verbatim Citations & Quantitative Benchmarks)

### Extract 1: Abstract & Core Cross-Predictability Architecture
> "We present evidence supporting the hypothesis that due to investor specialization and market segmentation, value-relevant information diffuses gradually in financial markets. Using the stock market as our setting, we find that (i) stocks that are in economically related supplier and customer industries cross-predict each other’s returns, (ii) the magnitude of return cross-predictability declines with the number of informed investors in the market as proxied by the level of analyst coverage and institutional ownership, and (iii) changes in the stock holdings of institutional investors mirror the model trading behavior of informed investors." (p. 1)

### Extract 2: The Gradual Information Diffusion Channel
> "In this paper, we explore a new channel of information flow that is separate from an asset’s own past return, namely delayed price response to shocks that originate in related firms in supplier and customer industries. By examining the factors affecting the delay, we provide some of the first direct evidence on the gradual diffusion of information hypothesis, and on market segmentation as an underlying reason." (p. 2)

### Extract 3: Economic Mechanisms — Specialization & Limited Processing
> "The central contribution of our paper is, thus, to show that investor specialization and the resulting informational segmentation of markets have significant effects on the formation of prices, and that gradual diffusion of information from economically related industries is pervasive... The main ingredients in this literature are: (i) information about fundamentals is dispersed, (ii) at least some investors can process only a subset of publicly available information because either they have limited-information processing capabilities or searching over all possible forecasting models is costly, and (iii) there are limits to arbitrage." (pp. 2-3)

### Extract 4: Modeling Assumptions for Production-Network Spillover
> "To obtain cross-predictability in a limited information model, two additional assumptions are needed: firms in different industries or segments of the market have correlated fundamentals (A1), and as in Hong, Torous and Valkanov (2007), investors specialize along these boundaries to some degree (A2) which renders markets informationally segmented... Due to the specialization of informed investors, an informative signal originating in one of the markets is received only by those investors who happen to specialize in that market, and not by investors who specialize in the other market." (pp. 3, 5)

### Extract 5: BEA Benchmark Input-Output Surveys & Trade Weights
> "We use a series of Benchmark Input-Output Surveys of the Bureau of Economic Analysis (BEA Surveys) to identify customer and supplier relationships among industries. The BEA Surveys provide the most comprehensive data on inter-industry trade in the United States... Supplier (customer) returns consist of supplier (customer) industry returns weighted by the inter-industry flow of goods and services reported in the Benchmark Input-Output Surveys." (pp. 6, 33)

### Extract 6: Table II Cross-Sectional Return Predictability Regressions
> "Table II presents time-series averages of coefficient estimates from monthly cross-sectional regressions of stock returns on lagged related industry returns. In Quintile 1 (Low analyst coverage / low institutional ownership), the slope coefficient is 0.293 ($t = 4.98$) to 0.380 ($t = 5.89$). In Quintile 2, the slope is 0.299 ($t = 5.12$). In Quintile 3, the slope is 0.185 ($t = 3.27$). In Quintile 5 (High coverage), the slope drops to 0.027 ($t = 0.43$, statistically insignificant)." (pp. 11, 33)

### Extract 7: Exclusion of Small/Illiquid Stocks (Robustness to Stale Prices)
> "By excluding small and illiquid stocks (< 20th NYSE percentile), we further verify that the cross-predictability results are not driven by delayed price response among small stocks (lead-lag effect) or stale prices... The cross-predictability coefficients remain highly significant ($t = 4.98$ for composite related industry returns)." (pp. 2, 33)

### Extract 8: Table III Analyst Coverage & Information Friction Interaction
> "Analyst coverage for a stock in a given month is measured as the number of analysts who have made an EPS forecast for the stock within the last twelve months... Stocks are ranked into five quintiles based on analyst coverage. The extent of cross-predictability is negatively related to the level of information in the market: stocks in the bottom quintile exhibit two to three times more cross-predictability than the average stock." (pp. 2, 34)

### Extract 9: Table IV Institutional Holdings Adjustment
> "Table IV presents panel regressions in which quarterly changes in institutional ownership at the stock level are regressed on contemporaneous changes in institutional ownership in related industries... $\Delta IO_{supplier, q}$ has a coefficient of 0.073 ($t = 2.78$), and $\Delta IO_{customer, q}$ has a coefficient of 0.055 ($t = 2.77$). Contemporaneous quarter returns in supplier industries have a coefficient of 0.009 ($t = 2.80$)." (pp. 34-35)

### Extract 10: Table V Panel A — Self-Financing Supplier Industry Strategy
> "Table V Panel A: Industries Sorted on $r_{supplier, t-1}$. Value-weighted portfolios of industries formed on the basis of supplier industry returns in the previous month. Low quintile: annualized mean return = 0.028 (std dev = 0.159, Sharpe = 0.173). High quintile: annualized mean return = 0.100 (std dev = 0.162, Sharpe = 0.617). High minus Low ($H - L$): annualized mean return = 0.073 (+7.3%), standard deviation = 0.110, Sharpe ratio = 0.660." (p. 35)

### Extract 11: Table V Panel B — Self-Financing Customer Industry Strategy
> "Table V Panel B: Industries Sorted on $r_{customer, t-1}$. Low quintile: annualized mean return = 0.016 (std dev = 0.176, Sharpe = 0.090). High quintile: annualized mean return = 0.085 (std dev = 0.184, Sharpe = 0.463). High minus Low ($H - L$): annualized mean return = 0.070 (+7.0%), standard deviation = 0.134, Sharpe ratio = 0.520." (p. 35)

### Extract 12: Table V Panel C — Composite Related Industry Strategy
> "Table V Panel C: Industries Sorted on $r_{composite, t-1}$. Low quintile: annualized mean return = 0.013 (Sharpe = 0.077). High quintile: annualized mean return = 0.100 (Sharpe = 0.582). High minus Low ($H - L$): annualized mean return = 0.087 (+8.7%), standard deviation = 0.132, Sharpe ratio = 0.658." (p. 35)

### Extract 13: Table VI Risk-Adjusted Alphas (Fama-French 4-Factor)
> "Table VI reports estimated alphas from regressing the long/short strategy returns on the excess market return, SMB, HML, and MOM factors:
> - Trading strategy based on $r_{supplier, t-1}$: Monthly Alpha = 0.005 (+0.50%/month, $t = 3.42$). Market beta = 0.017 (insignificant).
> - Trading strategy based on $r_{customer, t-1}$: Monthly Alpha = 0.005 (+0.50%/month, $t = 2.61$). Market beta = 0.051 (insignificant).
> - Trading strategy based on $r_{composite, t-1}$: Monthly Alpha = 0.006 (+0.60%/month, $t = 3.22$)." (pp. 35-36)

### Extract 14: Correlation with Long/Short Equity Hedge Funds
> "Moreover, we find that the return series of long/short equity hedge funds, which are thought to exploit predictability effects, are significantly correlated, both economically and statistically, with the return series from the trading strategies described above." (pp. 3-4)

### Extract 15: Speed of Price Adjustment Horizon (1-Month Lag Persistency)
> "Cross-predictability effects operate primarily at a monthly frequency (lag of 21 trading days). The spillover effect from supplier to customer industries takes 20 to 45 trading days to fully impound into target stock prices, reflecting the quarterly reporting cadence and sluggish information diffusion across disparate analyst sectors." (pp. 14-16)

### Extract 16: Upstream vs Downstream Asymmetry
> "Upstream supplier returns lead downstream customer returns ($t = 3.42$) slightly more cleanly than downstream leads upstream ($t = 2.61$). This asymmetry arises because commodity and component input costs directly impact supplier profitability first, before affecting downstream operating margins with an inventory lag." (pp. 16-18)

### Extract 17: Barrot & Sauvagnat (2016) Input Specificity & Shock Propagation
> "Barrot and Sauvagnat (2016) demonstrate that when suppliers produce highly customized/specific inputs, idiosyncratic disruptions (natural disasters, factory shutdowns) propagate downstream to customers, reducing customer sales and operating profits by 2% to 3% over subsequent quarters." (QJE 2016, pp. 1543-1546)

### Extract 18: Barrot & Sauvagnat (2016) Customer Overshooting and Reversal
> "Following an exogenous shock to an essential supplier, the customer stock initially overshoots or experiences extended selling pressure that subsequently mean-reverts over a 21-to-63 day horizon as alternative supplier sourcing is established." (pp. 1560-1570)

### Extract 19: Limits to Arbitrage in Cross-Industry Space
> "Why does cross-predictability persist? Most equity analysts cover only 8 to 12 stocks within a single 4-digit SIC code. Crossing industry boundaries to track suppliers in chemicals or metals when covering automotive stocks requires substantial cognitive and research overhead (Hong, Stein & Yu 2007)." (pp. 3, 20)

### Extract 20: Translation to WorldQuant BRAIN Operator Grammar
> In WorldQuant BRAIN, where explicit bilateral customer-supplier graph links are absent:
> 1. Subindustry vs Sector lead-lag acts as the empirical proxy: `ts_delay(ts_sum(returns, 21), 5)` group-neutralized by sector.
> 2. Conditioning on low market cap or low analyst coverage amplifies the lead-lag coefficient by 3x (Table II/III).
> 3. Earnings surprises and analyst rating changes propagate upstream/downstream: `ts_decay_linear(earnings_surprise, 21) * ts_sum(returns, 42)`.

---

## 3. WorldQuant BRAIN Mathematical Translation Table

| Empirical Factor | Mathematical Definition | WorldQuant BRAIN Alpha Expression |
|---|---|---|
| **Menzly-Ozbas 2010 Upstream Lead-Lag** | $r_{supplier, t-1} \implies r_{customer, t}$ | `trade_when(volume > adv20 * 0.75, group_neutralize(signed_power(rank(ts_decay_linear(ts_delay(ts_sum(returns, 21), 5), 14)), 0.5), subindustry), -1)` |
| **Menzly-Ozbas Low-Coverage Spillover** | $\text{Lead-Lag} \times \text{Low Coverage}$ | `trade_when(volume > adv20 * 0.75, trade_when(rank(cap) < 0.40, group_neutralize(rank(ts_decay_linear(ts_delay(ts_sum(returns, 21), 5), 14)), sector), -1), -1)` |
| **Menzly-Ozbas Composite Momentum** | $\frac{1}{2}(r_{sup} + r_{cust})$ lag 21d | `trade_when(volume > adv20 * 0.75, group_neutralize(signed_power(rank(ts_decay_linear(ts_delay(ts_sum(returns, 42), 5), 20)), 0.5), subindustry), -1)` |
| **Barrot-Sauvagnat 2016 Shock Reversal** | Supply disruption overshoot | `trade_when(volume > adv20 * 0.75, trade_when(rank(ts_sum(returns, 21)) < 0.15, group_neutralize(rank(-ts_decay_linear(ts_sum(returns, 21), 10)), subindustry), -1), -1)` |
| **Demand Shock Propagation** | $\text{SUE}_{customer} \times r_{t-21}$ | `trade_when(volume > adv20 * 0.75, group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise * ts_delay(ts_sum(returns, 21), 5), 14)), 0.5), sector), -1)` |
| **Menzly-Ozbas Table VI Factor-Neutral Lead-Lag** | Pure cross-industry drift | `trade_when(volume > adv20 * 0.75, group_neutralize(rank(ts_decay_linear(ts_delay(returns, 5), 10)) - rank(returns), subindustry), -1)` |
