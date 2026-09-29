# Category: Sentiment & Analyst Expectations (`sentiment1`)

**WorldQuant BRAIN Category ID:** `sentiment`  
**Platform Value Score:** **`8.0 / 10` (Highest on Entire Platform)**  
**Platform User Count:** **7,839 Users** (Only ~8% of active users)  
**Total Platform Alphas:** **121,727 Alphas** (Virgin territory vs. 5,000,000 Price-Volume)

---

## 1. Strategy Archetypes & Theoretical Foundations

### Archetype S1: Post-Earnings Announcement Drift (PEAD)
* **Citation:** Chan, Jegadeesh, & Lakonishok (1996) — *Momentum Strategies*
* **Core Field:** `snt1_d1_netearningsrevision` (Net % of analysts raising minus lowering estimates)
* **Economic Thesis:** Analysts revise earnings projections gradually over a 60–90 day period rather than instantaneously. This cognitive conservatism produces a multi-month post-revision equity drift.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(\text{ts\_decay\_linear}(\text{snt1\_d1\_netearningsrevision}, 12)\right), \text{subindustry}\right)$$

---

### Archetype S2: Standardized Unexpected Earnings (SUE) Shock
* **Citation:** Bernard & Thomas (1989, 1990) — *Post-Earnings-Announcement Drift*
* **Core Field:** `snt1_d1_earningssurprise` (Actual reported earnings minus consensus expectations)
* **Economic Thesis:** The market systematically underreacts to fundamental earnings surprises, with the largest excess returns accruing to extreme surprises (> 5% shock).
* **Base Formula:**
  $$\alpha = \text{trade\_when}\left(\text{abs}(\text{snt1\_d1\_earningssurprise}) > 0.05, \text{group\_neutralize}\left(\text{rank}(\text{ts\_decay\_linear}(\text{snt1\_d1\_earningssurprise}, 15)), \text{subindustry}\right), -1\right)$$

---

### Archetype S3: Target Price Revision Momentum
* **Citation:** Brav & Lehavy (2003) — *Target Price Revisions and Stock Return Response*
* **Core Field:** `snt1_d1_nettargetpercent` (Net % of analysts raising price targets)
* **Economic Thesis:** Target price updates represent forward-looking valuation re-ratings that contain distinct informational value beyond backward-looking earnings reports.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(\text{ts\_decay\_linear}(\text{snt1\_d1\_nettargetpercent}, 10)\right), \text{subindustry}\right)$$

---

### Archetype S4: Forecast Dispersion Discount (Difference of Opinion)
* **Citation:** Diether, Malloy, & Scherbina (2002) — *Differences of Opinion and Cross-Sectional Stock Returns*
* **Core Field:** `snt1_d1_dtstsespe` (Standard deviation / dispersion among analyst estimates)
* **Economic Thesis:** Stocks with high disagreement among analysts earn significantly lower subsequent returns due to short-sale constraints (overvaluation of optimistic views).
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(-\text{ts\_decay\_linear}\left(\frac{\text{snt1\_d1\_dtstsespe}}{\text{close} + 0.001}, 12\right)\right), \text{subindustry}\right)$$

---

### Archetype S5: Dynamic Analyst Focus & Mood Index
* **Citation:** Da, Engelberg, & Gao (2011) — *In Search of Attention*; Baker & Wurgler (2006)
* **Core Fields:** `snt1_d1_dynamicfocusrank`, `daily_equity_mood_indicator`
* **Economic Thesis:** Dynamic analyst focus captures informed institutional capital allocation rather than retail noise. Fading broad market mood swings monetizes behavioral overreactions.
* **Base Formula:**
  $$\alpha = \text{trade\_when}\left(\text{volume} > \text{adv20} \cdot 0.85, \text{group\_neutralize}\left(\text{rank}(\text{ts\_decay\_linear}(\text{snt1\_d1\_dynamicfocusrank}, 10)), \text{subindustry}\right), -1\right)$$

---

## 2. Platform Checklist & Implementation Rules
1. **Decay Parameter:** Use $d \in [10, 15]$ to smooth analyst revision cycles across bi-weekly reporting windows.
2. **Neutralization:** Use `subindustry` to purge sector-wide macroeconomic sentiment.
3. **Universes:** Deploy across `TOP3000` and `TOP2000` for maximum coverage.
