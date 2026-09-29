# Category: Systematic Risk Models & Factor Surface (`model51`)

**WorldQuant BRAIN Category ID:** `model`  
**Platform Value Score:** **`7.0 / 10` (Second Highest on Entire Platform)**  
**Platform User Count:** **29,584 Users**  
**Total Platform Alphas:** **60,349 Alphas** (Zero crowding in systematic risk derivatives)

---

## 1. Strategy Archetypes & Theoretical Foundations

### Archetype R1: Betting Against Beta (BAB)
* **Citation:** Frazzini & Pedersen (2014) — *Betting Against Beta*
* **Core Field:** `beta_last_60_days_spy`, `beta_last_90_days_spy`
* **Economic Thesis:** Leverage-constrained investors (retail, mutual funds) are restricted from applying leverage to low-beta assets. To achieve high nominal returns, they over-allocate to high-beta stocks, causing high-beta assets to be fundamentally overpriced. Going long low-beta assets and short high-beta assets yields an alpha Sharpe ratio $> 1.50$ globally.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(-\text{ts\_decay\_linear}(\text{beta\_last\_60\_days\_spy}, 12)\right), \text{subindustry}\right)$$

---

### Archetype R2: Market Decoupling & Idiosyncratic Variance
* **Citation:** Ang, Hodrick, Xing, & Zhang (2006) — *The Cross-Section of Volatility & Expected Returns*
* **Core Fields:** `correlation_last_60_days_spy`, `returns`
* **Economic Thesis:** Decomposing rolling market correlation from total realized variance isolates the idiosyncratic volatility puzzle: stocks with extreme unsystematic risk underperform their peers over subsequent holding periods.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(\text{ts\_decay\_linear}(\text{correlation\_last\_60\_days\_spy} \cdot (\text{ts\_std\_dev}(\text{returns}, 60) \cdot \sqrt{252}), 15)\right), \text{subindustry}\right)$$

---

### Archetype R3: Multi-Horizon Beta Term Divergence
* **Citation:** Black (1972) — *Capital Market Equilibrium with Restricted Borrowing*
* **Core Fields:** `beta_last_30_days_spy`, `beta_last_360_days_spy`
* **Economic Thesis:** Short-term beta spikes reflect transient liquidity or sentiment pressure. Fading the divergence between 30-day rolling beta and 360-day structural beta captures mean-reversion toward long-term asset equilibrium.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(-\text{ts\_decay\_linear}(\text{beta\_last\_30\_days\_spy} - \text{beta\_last\_360\_days\_spy}, 10)\right), \text{subindustry}\right)$$

---

### Archetype R4: Quality Surface Acceleration Derivative
* **Citation:** Piotroski (2000) — *Value Investing (F-Score)*; Novy-Marx (2013)
* **Core Fields:** `fscore_surface_accel`, `fscore_bfl_quality`
* **Economic Thesis:** Aggregate fundamental factor surfaces provide static quality scores. The *acceleration derivative* (`fscore_surface_accel`) isolates companies crossing the positive inflection point from balance-sheet stress to rapid operational recovery.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(0.60 \cdot \text{rank}(\text{fscore\_surface\_accel}) + 0.40 \cdot \text{rank}(\text{fscore\_bfl\_quality})\right), \text{subindustry}\right)$$

---

### Archetype R5: Operational Cashflow Efficiency & Profitability
* **Citation:** Novy-Marx (2013) — *The Gross Profitability Premium*
* **Core Fields:** `fscore_bfl_profitability`, `cashflow_efficiency_rank_derivative`
* **Economic Thesis:** Highly profitable firms generate persistent excess risk-adjusted returns. Blending operating profitability with operational cashflow efficiency filters out accrual manipulation.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(0.50 \cdot \text{rank}(\text{fscore\_bfl\_profitability}) + 0.50 \cdot \text{rank}(\text{cashflow\_efficiency\_rank\_derivative})\right), \text{subindustry}\right)$$

---

## 2. Platform Checklist & Implementation Rules
1. **Decay Floor:** Use $d \ge 10$ to prevent turnover spikes on rolling covariance estimates.
2. **Neutralization:** Use `subindustry` to isolate firm-specific beta anomalies from broad industry betas (e.g., Tech vs. Utilities).
3. **Universes:** Deploy across `TOP3000` and `TOP2000`.
