# WorldQuant BRAIN — Operational Directives: Rebirth Masterplan

> [!IMPORTANT]
> **PERMANENT REBIRTH MANDATE:**
> 1. **Focus Exclusively on BRAIN's Top 3 Highest Value-Score Categories:**
>    - **Model (`model`) — Value Score: 7.0**: Systematic Risk Metrics (`model51`), Fundamental Scores & Valuation Models (`model16`).
>    - **Option (`option`) — Value Score: 6.0**: Volatility Data (`option8`), Option Analytics & Informed Flow (`option9`).
>    - **Analyst (`analyst`) — Value Score: 5.0**: Analyst Estimate Data, Revisions & Dispersion (`analyst4`).
> 2. **Permanently Banned / Delisted Fields:**
>    - NEVER simulate delisted or degraded sentiment fields (`snt_value`, `snt1_*`, `snt_buzz`, or third-party web sentiment).
> 3. **Primary Mission:**
>    - Escalate user standing in **Challenge - Nigeria** from **#404 (Score 0.37)** into the **Top 10** through systematic, daily submissions of high-CQS, low-correlation alphas.

---

## 1. Top 3 Categories & Field Matrix

### Category 1: MODEL (`model`, Value Score: 7.0)
- **`model51` (Systematic Risk Metrics):**
  - Beta vs SPY: `beta_last_30_days_spy`, `beta_last_60_days_spy`, `beta_last_90_days_spy`, `beta_last_360_days_spy`
  - Correlation vs SPY: `correlation_last_30_days_spy`, `correlation_last_60_days_spy`, `correlation_last_90_days_spy`
  - Systematic & Unsystematic Variance: `systematic_risk_last_30_days`, `unsystematic_risk_last_30_days`, `unsystematic_risk_last_60_days`
- **`model16` (Valuation Models & Fundamental Scores):**
  - Pentagon Style Surfaces: `fscore_bfl_growth`, `fscore_bfl_momentum`, `fscore_bfl_profitability`, `fscore_bfl_quality`, `fscore_bfl_value`, `fscore_bfl_surface`, `fscore_bfl_surface_accel`, `fscore_bfl_total`
  - Derivative Ranks: `analyst_revision_rank_derivative`, `cashflow_efficiency_rank_derivative`, `earnings_certainty_rank_derivative`

### Category 2: OPTION (`option`, Value Score: 6.0)
- **`option8` (Volatility Data):**
  - ATM Implied Volatility: `implied_volatility_mean_10`, `implied_volatility_mean_20`, `implied_volatility_mean_30`, `implied_volatility_mean_60`, `implied_volatility_mean_90`, `implied_volatility_mean_180`, `implied_volatility_mean_360`
  - Call/Put IV: `implied_volatility_call_{tenor}`, `implied_volatility_put_{tenor}`
  - Volatility Smirk & Skew: `implied_volatility_mean_skew_{tenor}`
  - Realized Historical Vol: `historical_volatility_{tenor}`
- **`option9` (Option Analytics):**
  - Informed Order Flow: `pcr_vol_10`, `pcr_vol_20`, `pcr_vol_30`, `pcr_vol_60`, `pcr_vol_all`
  - Open Interest Imbalances: `pcr_oi_10`, `pcr_oi_20`, `pcr_oi_30`, `pcr_oi_60`, `pcr_oi_all`
  - Breakeven Support: `option_breakeven_{tenor}`, `call_breakeven_{tenor}`, `forward_price_{tenor}`

### Category 3: ANALYST (`analyst`, Value Score: 5.0)
- **`analyst4` (Analyst Estimates):**
  - Revision Momentum: `anl4_adxqfv110_pu` (Up revisions), `anl4_adxqfv110_down` (Down revisions), `anl4_adxqfv110_numest` (Coverage)
  - Forecast Dispersion & Harmony: `anl4_afv4_dts_spe` (Std dev), `anl4_afv4_eps_high`, `anl4_afv4_cfps_mean`
  - Actuals vs Guidance: `actual_eps_value_quarterly`, `actual_sales_value_quarterly`

---

## 2. In-Sample Quality Criteria (Strict Platform Gates)

Every candidate generated must satisfy the institutional BRAIN criteria:
- **Sharpe Ratio:** $\ge 1.25$ (Target: $\ge 1.50$)
- **Fitness:** $\ge 1.00$ (Target: $\ge 1.20$)
- **Turnover:** $1\% \le \text{Turnover} \le 70\%$ (Target: $\le 30\%$)
- **Margin:** $\ge 0.0015$ (15 bps)
- **Sub-universe Sharpe:** Positive across `TOP3000`, `TOP1000`, and `TOP500`
- **Self-Correlation:** $|\rho| < 0.70$ against all existing vault alphas
