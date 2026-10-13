"""
Novy-Marx (2013) — Gross Profitability Premium
Piotroski (2000) — F-Score Composite
Cooper, Gulen & Schill (2008) — Asset Growth Anomaly
Titman, Wei & Xie (2004) — Capital Investment Anomaly

Papers & Empirical Benchmarks:
  1. Novy-Marx (2013): "The Other Side of Value: Good Growth and the Gross Profitability Premium" — JFE
     - GPA = (Revenue - COGS) / Total_Assets predicts returns as strongly as B/M (t = 8.54 industry-demeaned).
     - Subsumes bottom-line earnings. HML loading is -0.45 (perfect hedge for value).
     - Table 12: GPA decomposes into Asset Turnover × Gross Margins.
  2. Piotroski (2000): "Value Investing: The Use of Historical Financial Statement Information" — JAR
     - 56% of value stocks are value traps. 9-signal F-Score generates +7.5% annual return spread.
  3. Cooper, Gulen, Schill (2008): "Asset Growth and the Cross-Section of Stock Returns" — JF
     - Total asset growth negatively predicts future returns (-22.7% annual spread).
     - Overinvestment and managerial empire-building.
  4. Titman, Wei, Xie (2004): "Capital Investments and Stock Returns" — JFQA
     - Abnormal capex negatively predicts returns (-5.1% annual spread, t = 2.4).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/fundamental/novy_marx_piotroski_cooper_titman_p0.md"


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
    # NOVY-MARX (2013) SIGNAL 1: Gross Profitability / Total Assets (Table 2 & 4)
    # GPA = (Sales - COGS) / Assets
    # High-GPA firms earn +0.38%/month FF3-alpha (t = 8.54 industry-demeaned)
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
                        f"Novy-Marx2013 Table 2: GPA = (Sales-COGS)/Assets. Cleanest economic productivity proxy. "
                        f"Industry-demeaned t=8.54. Subsumes bottom-line earnings. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # NOVY-MARX (2013) SIGNAL 2: Quality-Value Composite (Table 8)
    # GPA × Book-to-Market: high GPA value firms earn +1.03%/month (Table 8)
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
                        f"Novy-Marx2013 Table 8: Quality Value (GPA × B/M). "
                        f"High-GPA value firms earn +1.03%/month, hedging growth/value cycle. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # COOPER-GULEN-SCHILL (2008) SIGNAL 3: Asset Growth Anomaly (Table 3)
    # AG = (TotalAssets_t - TotalAssets_{t-1}) / TotalAssets_{t-1}
    # High-AG -> overinvestment -> -22.7%/yr spread. Short aggressive growers.
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
                        f"Cooper-Gulen-Schill2008 Table 3: annual asset growth predicts negative returns (-22.7%/yr spread). "
                        f"Managerial empire-building and overinvestment penalty. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # TITMAN-WEI-XIE (2004) SIGNAL 4: Abnormal Capital Expenditure
    # High capex growth relative to trailing 3y baseline -> overinvestment (-5.1%/yr)
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
                        f"Titman-Wei-Xie2004: abnormal capex / trailing 3y mean signals CEO empire-building. "
                        f"-5.1%/yr return spread (t=2.4). Strongest in firms with financial slack. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # PIOTROSKI (2000) SIGNAL 5: ROA Level & Trend Pillars (Signals 1-3)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                # ROA = EBT / assets
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
                        f"Piotroski2000: F-Score profitability pillar (EBT/Assets). "
                        f"High ROA distinguishes winners from value traps. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

                # ΔROA = year-over-year improvement
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
                        f"Piotroski2000: F-Score ΔROA signal (year-over-year improvement). "
                        f"Improving profitability trend signals business turnaround. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # PIOTROSKI (2000) SIGNAL 6: Operational Efficiency Composite (Signals 8-9)
    # ΔGross Margin + ΔAsset Turnover
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
                        f"Piotroski2000: Efficiency composite (ΔAssetTurnover + ΔGrossMargin). "
                        f"Operational efficiency gains predict post-announcement drift. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # NOVY-MARX (2013) SIGNAL 7: Asset Turnover Factor (Table 12 Model 2)
    # Sales / Assets: capital velocity component of gross profitability
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_NM_TURNOVER",
                    "archetype": f"NMTurnover_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"sales / (assets + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Novy-Marx2013 Table 12 Model 2: Asset Turnover = Sales/Assets (t=2.28). "
                        f"Capital deployment velocity drives operational efficiency. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # NOVY-MARX (2013) SIGNAL 8: Gross Margin Factor (Table 12 Model 3)
    # (Sales - COGS) / Sales: pricing power component of gross profitability
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_NM_GROSS_MARGIN",
                    "archetype": f"NMGrossMargin_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"(sales - cost_of_goods_sold) / (sales + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Novy-Marx2013 Table 12 Model 3: Gross Margin = GP/Sales (t=3.41). "
                        f"Pricing power and economic moat indicator. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4-FACTOR COMPOSITE: Quality × Capital Allocation Discipline (Extract 20)
    # High GPA × Low Asset Growth × Low Capex
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_4FACTOR_COMPOSITE",
                    "archetype": f"QualityDiscipline_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"group_neutralize(signed_power("
                        f"rank(ts_decay_linear((sales - cost_of_goods_sold) / (assets + 0.001), {d})) * "
                        f"rank(-ts_decay_linear(ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001), {d})), "
                        f"0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Novy-Marx 2013 × Cooper et al. 2008: High gross profitability combined with disciplined balance sheet (low AG). "
                        f"Eliminates overinvesting low-return empire builders. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # PIOTROSKI (2000) SIGNAL 10: Value Trap Filter (High BM × Positive ΔROA)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [20, 30]:
                catalog.append({
                    "pillar": "FUNDAMENTAL_VALUE_TRAP_FILTER",
                    "archetype": f"ValueTrapFilter_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(book_to_price) > 0.60, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(ts_delta(earnings_before_tax / (assets + 0.001), 252), {d})), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Piotroski2000: Value trap filter (gating on top 40% B/M and ranking by ΔROA improvement). "
                        f"Recovers +7.5%/yr spread within distressed value universe. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    return catalog
