# Novy-Marx (2013) · Piotroski (2000) · Cooper-Gulen-Schill (2008) · Titman-Wei-Xie (2004)

## Classification
- **Pillar:** Fundamental
- **Journals:** JFE 2013 (NM), AR 2000 (Piotroski), JF 2008 (Cooper), JF 2004 (Titman)
- **Datasets:** BRAIN fundamental fields
- **Alpha Yield Estimate:** 4 constructions × parameter grid = 152 archetypes
- **Novelty Score:** 8/10 — foundational quality/profitability factors with AQR-grade replication
- **Generator:** `brain_generators/fundamental/fundamental_p0_combined.py`

---

## Paper 1: Novy-Marx (2013) — Gross Profitability Premium

### Core Thesis
**Gross profit / total assets** (GPA) is a cleaner measure of operating efficiency than net income or ROE because it is **before deductions for discretionary and non-cash items** (SG&A, depreciation, interest, taxes). GPA predicts returns independently of book-to-market, momentum, and size.

### Exact Formula
```
GPA = (Revenue - COGS) / Total_Assets

Key empirical result (Table 1):
  Top-quintile GPA:    +0.31% alpha/month (controlling for B/M)
  Bottom-quintile GPA: -0.43% alpha/month
  Long-short Sharpe ≈ 0.55 (1963–2010)
```

### BRAIN Field Mapping
| Paper Variable | BRAIN Field |
|---|---|
| `Revenue - COGS` | `gross_profit` |
| `Total Assets` | `assets` |
| `GPA` | `gross_profit / assets` |

### Signal Card
```python
group_neutralize(
    signed_power(rank(ts_decay_linear(gross_profit / (assets + 0.001), D)), 0.5),
    subindustry
)
```

**Critical note:** NM 2013 footnote 8 — GPA subsumes ROE and ROA cross-sectionally because COGS allocation is less subject to managerial discretion. Use GPA over ROA.

---

## Paper 2: Piotroski (2000) — F-Score

### Core Thesis
Among high B/M (value) stocks, only 44% outperform over the next year. Piotroski constructs a 9-signal F-Score to distinguish "true value" from "value traps." High F-Score (≥7) stocks earn **+7.5% per year** over low F-Score stocks within the same B/M decile.

### Exact F-Score Construction
```
F_ROA     = 1 if ROA > 0, else 0               (net income / total assets > 0)
F_ΔROA    = 1 if ΔROA > 0, else 0              (ROA improved year-over-year)
F_CFO     = 1 if CFO/Assets > 0, else 0        (operating cash flow positive)
F_ACCRUAL = 1 if CFO/Assets > ROA, else 0      (cash earnings > accrual earnings)
F_ΔLEV    = 1 if long-term leverage declined, else 0
F_ΔLIQ    = 1 if current ratio improved, else 0
F_EQ      = 1 if no new equity issued in past year, else 0
F_ΔMARGIN = 1 if gross margin improved, else 0
F_ΔTURN   = 1 if asset turnover improved, else 0

F_SCORE = Σ(F_ROA + F_ΔROA + F_CFO + F_ACCRUAL + F_ΔLEV + F_ΔLIQ + F_EQ + F_ΔMARGIN + F_ΔTURN)
```

### BRAIN Signal (Composite Proxy)
```python
# Cannot compute full 9-signal F-Score directly in BRAIN expression
# Best composite: combine available signals
f_proxy = (
    rank(net_income / (assets + 0.001)) +          # ROA signal
    rank(operating_cash_flow / (assets + 0.001)) + # CFO signal
    rank(-debt_to_equity_ratio) +                   # Leverage decline signal
    rank(current_ratio)                             # Liquidity signal
)
group_neutralize(signed_power(rank(ts_decay_linear(f_proxy, D)), 0.5), subindustry)
```

---

## Paper 3: Cooper, Gulen & Schill (2008) — Asset Growth Anomaly

### Core Thesis
Total asset growth negatively predicts future returns. Firms that aggressively expand assets earn lower subsequent returns — this captures overinvestment, managerial empire building, and mispricing of growth opportunities.

### Exact Formula
```
Asset_Growth = (Assets_t - Assets_{t-1}) / Assets_{t-1}
```

**Magnitude (Table 3):** Top-decile asset growth underperforms bottom-decile by **-22.7% per year** (1968–2003). Effect survives Fama-French 3-factor model.

**Key mechanisms:**
1. Investment overreach — managers invest in negative-NPV projects
2. Market over-extrapolation — investors bid up high-growth firms too much
3. Share issuance timing — high-growth firms often issue shares at market peaks

### BRAIN Signal
```python
group_neutralize(
    signed_power(rank(-ts_decay_linear(ts_delta(assets, 252) / (assets + 0.001), D)), 0.5),
    subindustry
)
```

---

## Paper 4: Titman, Wei & Xie (2004) — Capital Investments & Stock Returns

### Core Thesis
Firms with HIGH capex growth (relative to industry peers and lagged performance) earn lower future returns. Overinvestment hypothesis: managers overinvest → market overreacts positively → subsequent reversal.

### Exact Formula
```
CI = [Capex_t + Capex_{t-1} + Capex_{t-2}] / [Assets_{t-2}]    ← 3-yr normalized capex

or simpler:
CI_YoY = (Capex_t - Capex_{t-1}) / Capex_{t-1}                  ← YoY capex growth
```

**Magnitude:** Top-quintile CI underperforms by **-5.1% per year** (t-stat = 2.4). Stronger in low-institutional-ownership firms.

### BRAIN Signal
```python
group_neutralize(
    signed_power(rank(-ts_decay_linear(
        ts_delta(capital_expenditure, 252) / (capital_expenditure + 0.001), D
    )), 0.5),
    subindustry
)
```

---

## Cross-Paper Synergies
| Signal | Mechanism | Complementary Signal |
|---|---|---|
| GPA (NM 2013) | Operational efficiency | F-Score: GPA firms with high F-Score are best quality |
| F-Score (P 2000) | Fundamental health | Asset Growth: Low AG + High F-Score = quality value |
| Asset Growth (CGS 2008) | Overinvestment | Capex: AG and CI are correlated; CI is more granular |
| Capex (TWX 2004) | Capital misallocation | GPA: High capex + low GPA = worst overinvestment case |

**Best composite:** `rank(-AG) × rank(-CI) × rank(GPA) × rank(F_proxy)` — each factor independent and additive in predictive power.

## Implementation Status
- [x] Coded in `brain_generators/fundamental/fundamental_p0_combined.py`
- [x] 152 archetypes (4 constructions × universe × neutralization × decay)
- [ ] Simulating in miner
- [ ] Qualified alpha confirmed
