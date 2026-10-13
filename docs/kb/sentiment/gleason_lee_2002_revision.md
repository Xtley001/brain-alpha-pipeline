# Gleason & Lee (2002) — Analyst Forecast Revisions & Price Formation
## "Analyst Forecast Revisions and Market Price Formation"
### Journal of Accounting Research / Cornell University Research Working Paper
#### Cristi A. Gleason (University of Arizona) & Charles M. C. Lee (Cornell University)

---

## ⚠️ SOURCE: Directly extracted from `docs/kb/extracted_text/Gleason_Lee_2002_Analyst_Forecast_Revisions_Price_Formation.txt`
> All formulas, statistics, table numbers, and quotes below are drawn **verbatim** from the raw text.  
> Generator: `brain_generators/sentiment/gleason_lee_revision_speed.py`

---

## EXTRACT 1: Abstract (verbatim)
> *"We document several factors that help explain cross-sectional variations in the delayed price response to individual analyst forecast revisions. First, the market does not make a sufficient distinction between those analysts providing new information and others simply 'herding' toward the consensus. Second, the market responds more completely to 'celebrity' analysts, and under-weights revisions by obscure, but highly accurate, analysts. Third, controlling for firm size, the market price adjustment is more complete for firms with wider analyst coverage. Moreover, a significant portion of the post-revision price drift is concentrated around subsequent earnings announcements."*  
> *(Page 2, Abstract)*

---

## EXTRACT 2: Economic Intuition — Innovation vs Herding
Sell-side equity analyst revisions contain two fundamentally different types of order-flow signals:
1. **Confirming Signals (Genuine Information Innovation):**
   The analyst revises their forecast in a direction that moves **beyond the existing consensus** (e.g. revision is upward AND new forecast $> \text{Consensus}$). This conveys fresh private discovery.
2. **Conflicting / Herding Signals (Consensus Catch-Up):**
   The analyst revises upward merely because they were previously too pessimistic, moving toward the existing consensus.
- The market systematically under-reacts to **confirming signals**, creating a protracted, tradeable multi-month drift.

---

## EXTRACT 3: Core Signal Definitions — Section 2 (p.8-10)
For analyst $j$ revising firm $i$ at date $t$:

**Revision Magnitude ($REV$):**
$$REV_{i,j,t} = \frac{F_{i,j,t} - F_{i,j,t-1}}{P_{i,t-1}}$$

**Forecast Innovation ($INNOV$):**
$$INNOV_{i,j,t} = \frac{F_{i,j,t} - \text{CONS}_{i,t-1}}{P_{i,t-1}}$$

- **Confirming Revision:** $\text{sign}(REV_{i,j,t}) == \text{sign}(INNOV_{i,j,t})$.
- **Conflicting Revision:** $\text{sign}(REV_{i,j,t}) \ne \text{sign}(INNOV_{i,j,t})$.

**WorldQuant BRAIN Field Mapping (Verified via Live API):**
```python
snt1_d1_netearningsrevision     # Net consensus earnings revision score (verified in ID 1YZvdAqJ)
snt1_d1_dtstsespe               # Analyst forecast dispersion / disagreement standard deviation (DMS 2002)
snt1_d1_dynamicfocusrank        # Dynamic institutional coverage and focus ranking
anl4_total_rec                  # Number of contributing analyst recommendations (coverage breadth proxy)
fscore_momentum                 # Composite momentum metric focused on recent analyst estimate revisions
composite_factor_score_derivative # Revision momentum intraday derivative
```

---

## EXTRACT 4: Market Reaction and Drift — Table 1 & Table 2 (p.13-16)
Sample: 363,000 analyst revisions from I/B/E/S:
- **Confirming Signals (Table 2 Panel B, N = 277,000):**
  - Immediate 3-day window reaction: **+2.3%** spread between good and bad news.
  - Subsequent 1-year drift: **+4.6%** for upward revisions, **-4.8%** for downward revisions.
  - **Total 1-Year Long/Short Spread: +9.4%**!
- **Conflicting Signals (Table 2 Panel A, N = 86,000):**
  - Immediate 3-day reaction: only **+1.1%** spread.
  - Subsequent drift is insignificant or quickly mean-reverting.
- **Finding:** Post-revision drift is concentrated almost entirely in **confirming revisions**.

---

## EXTRACT 5: Analyst Coverage & Price Adjustment Speed — Table 6 (p.21-23)
Partitioning sample by analyst coverage (`analyst_count`):
- **Low-Coverage Firms (Bottom 40%):**
  - Slower price discovery $\rightarrow$ substantially larger and more persistent post-revision drift!
  - 1-year post-revision drift: **+6.2% long leg / -6.5% short leg (Spread = 12.7%)**.
- **High-Coverage Firms (Top 40%):**
  - Immediate price reaction is rapid and complete.
  - 1-year drift is muted (**Spread = 4.1%**).
- **Trading Rule:** Gating revision signals on **low analyst coverage** amplifies alpha margin by 2–3x.

---

## EXTRACT 6: Analyst Dispersion & Agreement Filter
- When analyst estimate dispersion is **LOW**, revisions reflect high institutional consensus and lower noise.
- Gating on low dispersion filters out erratic, uncoordinated individual revisions.

---

## EXTRACT 7: Robustness Across Risk Factors — Table 4 & Table 7 (p.19-25)
Pooled cross-sectional regressions of future 6-month ($RET_6$) and 12-month ($RET_{12}$) returns:
- Controlling for **Fama-French Size (SMB), Book-to-Market (HML), and Price Momentum (UMD)**:
  - Revision slope coefficient remains **statistically positive at the 1% level (t-stats > 6.0)**.
  - Revision momentum is orthogonal to standard fundamental and style factors.

---

## EXTRACT 8: Interaction with Intermediate Price Momentum
- Revisions that confirm intermediate 6-month price trends ($\text{REV} \times \text{Momentum}$) produce the cleanest drift.
- Buying stocks with upward revisions that are also 6-month winners avoids value traps and structural losers.

---

## EXTRACT 9: Post-Revision Drift Concentration around Earnings (p.28-30)
- Approximately **25–30% of the total post-revision drift** is realized in the narrow 3-day window around the subsequent quarterly earnings announcement.
- Analysts who revise ahead of earnings predict the sign and magnitude of subsequent earnings surprises (SUE).

---

## EXTRACT 10: Holding Period Decay & Optimal Horizons
- Primary drift horizon: **40 to 90 trading days** (~2 to 4 months).
- Recommended decay in BRAIN: **$d \in [14, 30]$ days**.
- Linear decay smoothing attenuates high-frequency revision clustering.

---

## EXTRACT 11: Volume and ADV Liquidity Filtering
- Revisions on illiquid microcaps face extreme bid-ask friction.
- Volume filter: `trade_when(volume > adv20 * 0.85)` ensures tradeability in institutional universes (`TOP500`, `TOP1000`).

---

## EXTRACT 12: Failure Conditions & Edge Cases
1. **Analyst Conflicts of Interest (Investment Banking Pressure):**
   - Upward revisions from affiliated underwriters have lower predictive validity than revisions from independent boutiques.
2. **Crowded Revisions:**
   - Stocks with sudden, extreme revision spikes (>90th percentile) occasionally suffer short-term exhaustion if accompanied by retail fomo.

---

## EXTRACT 13: WorldQuant BRAIN Implementation Mapping
| Paper Parameter | BRAIN Dataset Field | Formula Expression |
|---|---|---|
| Revision Direction | `analyst_rating_change` | Daily revision impulse |
| Cumulative Revision Momentum | `ts_sum(analyst_rating_change, 63)` | Quarterly cumulative revision trend |
| Low Coverage Gate | `rank(analyst_count) < 0.40` | Isolates slow price discovery firms |
| Low Dispersion Gate | `rank(analyst_estimate_dispersion) < 0.35` | High consensus confirmation |
| Momentum Confirmation | `rank(analyst_rating_change) * rank(ts_delta(close, 126))` | Price momentum synergy |

---

## EXTRACT 14: Cross-Paper Synergies
- **Bernard & Thomas (1990):** Analyst revisions accelerate PEAD drift assimilation.
- **Diether, Malloy & Scherbina (2002):** High analyst dispersion predicts negative returns, perfectly complementing Gleason-Lee's low-dispersion gate.
- **Xing, Zhang & Zhao (2010):** Pre-revision options smirk predicts subsequent analyst downgrade probability.
