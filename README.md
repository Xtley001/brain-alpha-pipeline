---
title: WorldQuant BRAIN Alpha Pipeline
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# `brain_options`: WorldQuant BRAIN Options Alpha Specialist Pipeline

A standalone, hyper-specialized quantitative alpha discovery and simulation pipeline for **WorldQuant BRAIN**, focused exclusively on the **Options** category (Platform Value Score: **6.0**, 13x less crowded than Price/Volume).

---

## 1. Why Options?

| Metric | Price/Volume (`pv`) | Options (`option`) | Edge |
| :--- | :---: | :---: | :--- |
| **Brain Value Score** | `2.0` (Lowest tier) | **`6.0` (3x higher)** | Huge platform allocation multiplier |
| **Platform Alphas** | `4,775,794` (Saturated) | **`353,031` (Uncrowded)** | 13x less platform correlation penalty |
| **Available Fields** | `32` pure PV fields | **`138` institutional fields** | Smart money derivatives positioning |

The Options category unlocks institutional derivatives pricing data—including put-call ratios, volatility skew steepness, call breakeven prices, and synthetic forward expectations—that pure technical price-volume formulas cannot capture.

---

## 2. Quantitative Archetypes

`brain_options` generates alpha expressions strictly across 5 proven derivatives-pricing phenomena:

1. **Synthetic Forward Basis Spread (Market-Implied Stock Drift)**:
   $$\text{group\_neutralize}(\text{rank}((\text{forward\_price\_30} - \text{close}) / \text{close}), \text{sector})$$
   *Quant Logic:* Compares institutional synthetic forward expectations against spot prices.

2. **Put-Call Volume & Open Interest Ratios (Smart Money Flow & Squeezes)**:
   $$\text{group\_neutralize}(\text{rank}(-\text{ts\_zscore}(\text{pcr\_vol\_20}, 40)), \text{sector})$$
   *Quant Logic:* Identifies capitulation / excessive put buying (bullish squeeze) vs euphoria / call speculation (bearish top).

3. **Implied Volatility Skew Acceleration (Downside Tail Risk)**:
   $$\text{group\_neutralize}(\text{rank}(-\text{ts\_delta}(\text{implied\_volatility\_mean\_skew\_30}, 5)), \text{subindustry})$$
   *Quant Logic:* Sudden steepening of OTM put skew signals institutional crash-protection buying prior to breakdowns.

4. **Call Breakeven Hurdle Rate Gating**:
   $$\text{trade\_when}(\text{volume} > \text{adv20}, \text{group\_neutralize}(\text{rank}((\text{call\_breakeven\_30} - \text{close}) / \text{close}), \text{sector}), -1)$$
   *Quant Logic:* Evaluates upside potential to reach option writers' breakeven hurdle price, confirmed by volume.

5. **Volatility Term Structure & Variance Risk Premium (VRP)**:
   $$\text{group\_neutralize}(\text{rank}(-(\text{implied\_volatility\_mean\_30} / (\text{implied\_volatility\_mean\_90} + 0.001) - 1.0)), \text{sector})$$
   *Quant Logic:* Exploits mean-reverting shocks in front-month vs 3-month implied volatility.

---

## 3. Architecture & Screening Funnel

```
[Options Candidate: Templates & LLM Reasoning]
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  STAGE 0: Fast Screen (1 Simulation)         │  Settings: Universe=TOP3000, Delay=1, Decay=8, Neut=SUBINDUSTRY
│  Criteria: Sharpe ≥ 0.35, Fitness ≥ 0.20     │  Purpose: Weed out unviable noise quickly
└──────────────────────┬───────────────────────┘
                       │ (PASS)
                       ▼
┌──────────────────────────────────────────────┐
│  STAGE 1: Neutralization × Decay Grid        │  Sweeps: 5 Neutralizations (SUBINDUSTRY, INDUSTRY, SECTOR,
│  Optimization (25-30 Simulations)            │          MARKET, NONE) × 5 Decays (0, 4, 8, 15, 20)
│  Criteria: Pick highest Fitness combo        │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  LOCAL FILTER & CORRELATION GATES            │  Criteria: Sharpe ≥ 1.25, Fitness ≥ 1.00,
│  Final Acceptance Bar                        │            Turnover 1% - 70%, Max Pool Correlation < 0.70
└──────────────────────┬───────────────────────┘
                       │ (PASS)
                       ▼
⭐ [PASSED ALPHA: Saved to store & Alerted via Telegram with full BRAIN parameters]
```

---

## 4. Usage

### Quick Test / Dry Run (No simulation quota spent)
```bash
python -m brain_options.run --dry-run --candidates 6
```

### Single Bounded Batch (Render Cron Mode)
Runs one bounded batch of candidates (5-10 candidates), optimizes any passing candidates, and exits:
```bash
python -m brain_options.run --single-batch
```

### Continuous Daemon Mode
Runs continuously with rest periods between batches:
```bash
python -m brain_options.run --daemon
```

---

## 5. Storage & Past Alphas

- **Passed Options Alphas:** `brain_options/data/passed_options_alphas.csv` and `.json`.
- **Evaluated History:** `brain_options/data/evaluated_candidates.csv`.
- **Legacy Price/Volume Alphas:** Safely preserved in `legacy_archive/all_generated_alphas.csv` and `legacy_archive/exported_alphas/`.
