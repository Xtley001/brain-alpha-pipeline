"""
Novy-Marx (2013) — Gross Profitability Premium
Piotroski (2000) — F-Score Composite
Cooper, Gulen & Schill (2008) — Asset Growth Anomaly
Titman, Wei & Xie (2004) — Capital Investment Anomaly

Papers:
  1. Novy-Marx (2013): "The Other Side of Value: Good Growth and the Gross Profitability Premium" — JF
  2. Piotroski (2000): "Value Investing: The Use of Historical Financial Statement Information" — JAR
  3. Cooper, Gulen, Schill (2008): "Asset Growth and the Cross-Section of Stock Returns" — JF
  4. Titman, Wei, Xie (2004): "Capital Investments and Stock Returns" — JFQA

Core Findings:
  - Novy-Marx: GPA = (Revenue - COGS) / Total_Assets predicts returns as strongly as B/M.
    Mechanism: gross profits avoid accounting manipulation, proxy true productive capacity.
    High-GPA stocks earn +0.31%/month alpha (CAPM), +0.38%/month (FF3).
    Formula (Paper Eq. 1): GP/A = (Revenue - COGS) / Book_Assets (total, not equity)

  - Piotroski: F-Score = sum of 9 binary signals across:
      Profitability (4): ROA, ΔCashFlow, ΔROA, Accruals
      Leverage/Liquidity (3): ΔLeverage, ΔLiquidity, Equity Issuance
      Operating Efficiency (2): ΔMargin, ΔTurnover
    High F-Score (8-9) → long; Low F-Score (0-1) → short. 7.5% annual return spread.

  - Cooper-Gulen-Schill: Total asset growth negatively predicts future returns.
    AG = (Total_Assets_t - Total_Assets_{t-1}) / Total_Assets_{t-1}
    High-AG firms earn -21% less per year than low-AG firms. Over-investment theory.

  - Titman-Wei-Xie: Abnormal capital expenditure (capex / avg(capex last 3y)) negatively
    predicts returns. CEO empire-building / over-investment in capital.
"""
from typing import Any, Dict, List


def generate_fundamental_p0_candidates() -> List[Dict[str, Any]]:
    """
    Generates paper-faithful fundamental quality signals from 4 P0 papers.
    All formulas directly derived from cited academic constructions.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 20, 30, 60]

    # ─────────────────────────────────────────────────────────────────────────
    # NOVY-MARX (2013): Gross Profitability / Total Assets
    # GPA = (Revenue - COGS) / Total_Assets
    # BRAIN: revenue=sales, cogs=cost_of_goods_sold, assets=total_assets
    # Annual rebalancing → use longer decay to reduce turnover.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "FUNDAMENTAL_GPA",
                    "archetype": f"GPA_NovyMarx_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"(sales - cost_of_goods_sold) / (assets + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Novy-Marx2013: GPA = (Revenue-COGS)/TotalAssets. Cleanest economic profitability proxy. "
                        f"High-GPA firms earn +0.38%/month FF3-alpha. Avoids accounting manipulation. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # NOVY-MARX VARIANT: Industry-Demeaned GPA (Paper Table 4)
    # Paper finds GPA is strongest WITHIN industry (industry-adjusted).
    # The group_neutralize(subindustry) achieves this by design.
    # Additional: combine GPA with B/M for "quality value" (Paper Sec IV)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_GPA_VALUE",
                    "archetype": f"GPA_Value_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"(sales - cost_of_goods_sold) / (assets + 0.001), {d}"
                        f")), 0.5) * rank(ts_decay_linear(book_to_price, {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Novy-Marx2013 Sec IV: GPA × B/M (quality-value composite). "
                        f"Profitable value firms earn highest returns. Profitable growth firms are not cheap. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # COOPER-GULEN-SCHILL (2008): Asset Growth Anomaly
    # AG = (TotalAssets_t - TotalAssets_{t-1}) / TotalAssets_{t-1}
    # Short high-AG (aggressive balance sheet expansion = over-investment)
    # BRAIN: ts_delta(assets, 252) / ts_delay(assets, 252) ≈ annual asset growth
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "FUNDAMENTAL_ASSET_GROWTH",
                    "archetype": f"AssetGrowth_Cooper_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Cooper-Gulen-Schill2008: annual asset growth predicts NEGATIVE returns. "
                        f"High-AG → over-investment → -21%/yr underperformance vs low-AG. Short asset-growers. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # TITMAN-WEI-XIE (2004): Abnormal Capital Expenditure
    # CAPX_abnormal = CAPX_t / avg(CAPX_{t-1}, CAPX_{t-2}, CAPX_{t-3})
    # High abnormal capex → empire-building → negative future returns (-22%/yr spread)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_CAPEX_OVERINVESTMENT",
                    "archetype": f"CapexOverInvest_TWX_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"capital_expenditure / (ts_mean(capital_expenditure, 756) + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Titman-Wei-Xie2004: capex/3yr-avg-capex > 1.0 = over-investment. "
                        f"CEO empire-building predicts -22%/yr underperformance. Short high-capex firms. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # PIOTROSKI (2000): F-Score Binary Signal Approximation
    # Full 9-signal F-Score not directly constructible in BRAIN (requires lag comparisons).
    # Best approximation: ROA trend + ΔROA + accruals composite.
    # Paper: long high-F-score B/M stocks, short low-F-score B/M stocks → 7.5%/yr spread.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                # ROA = earnings / assets (profitability pillar of F-score)
                catalog.append({
                    "pillar": "FUNDAMENTAL_FSCORE_ROA",
                    "archetype": f"FScore_ROA_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"earnings_before_tax / (assets + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Piotroski2000: F-Score ROA pillar — ROA = EBT/Assets signals profitability quality. "
                        f"High ROA within B/M universe → high future returns. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

                # ΔROA = ROA improvement year-over-year (F-Score signal 3)
                catalog.append({
                    "pillar": "FUNDAMENTAL_FSCORE_DELTA_ROA",
                    "archetype": f"FScore_DeltaROA_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"ts_delta(earnings_before_tax / (assets + 0.001), 252), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Piotroski2000: F-Score signal 3 (ΔROA): year-over-year ROA improvement. "
                        f"Improving profitability trend predicts outperformance. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # PIOTROSKI: Leverage/Accruals Composite (F-Score signals 5-9)
    # Operating leverage signal: ΔGross Margin + ΔAsset Turnover
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_FSCORE_EFFICIENCY",
                    "archetype": f"FScore_Efficiency_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(ts_delta(sales / (assets + 0.001), 252), {d})) + "
                        f"rank(ts_decay_linear(ts_delta((sales - cost_of_goods_sold) / (sales + 0.001), 252), {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Piotroski2000: Efficiency composite (F-Score signals 8-9): "
                        f"ΔAssetTurnover + ΔGrossMargin. Improving operational efficiency predicts outperformance. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    return catalog
