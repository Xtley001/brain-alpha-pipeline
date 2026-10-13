"""
Fundamental Quality, Gross Profitability & Capital Discipline Strategy Generator.
WorldQuant BRAIN Category: 'fundamental' (ValueScore: 7.5 - 8.5 / 10 | Low Crowding)
Derived from:
  - Novy-Marx (2013): The Other Side of Value: The Gross Profitability Premium
  - Piotroski (2000): Value Investing: The Use of Historical Financial Statement Information (F-Score)
  - Cooper, Gulen, Schill (2008): Asset Growth and the Cross-Section of Stock Returns
  - Titman, Wei, Xie (2004): Capital Investments and Stock Returns
  - Hirshleifer, Hsu, Li (2013): Innovative Efficiency and Stock Returns
"""
from typing import Any, Dict, List


SOURCE_KB = "docs/kb/fundamental/novy_marx_piotroski_cooper_titman_p0.md"


def generate_fundamental_vault_candidates() -> List[Dict[str, Any]]:
    """Generates 100+ institutional fundamental quality & capital discipline candidates."""
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays = [12, 16, 20]

    for u in universes:
        for g in neut_groups:
            for d in decays:
                # -------------------------------------------------------------
                # 1. Novy-Marx (2013) Gross Profitability Premium
                # Gross Profit / Total Assets. High profitability yields excess returns.
                # Combined with short-term price pullbacks for optimal entry.
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "FUND_GROSS_PROFITABILITY",
                    "archetype": f"Fund_GrossProfit_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(gross_profit / (assets + 0.001), {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear(gross_profit / (assets + 0.001), {d})) * rank(- ts_delta(close, 5)), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Novy-Marx gross profitability scaled by total assets conditioned on short-term price pullback ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

                # -------------------------------------------------------------
                # 2. Cooper, Gulen & Schill (2008) Asset Growth Anomaly
                # High asset expansion penalizes forward returns (overinvestment / empire building).
                # Long low-asset-growth / disciplined capital allocators.
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "FUND_ASSET_GROWTH_PENALTY",
                    "archetype": f"Fund_AssetGrowth_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001)) - 0.5) > 0.25, "
                        f"group_neutralize(rank(- ts_decay_linear(ts_delta(assets, 252) / (ts_delay(assets, 252) + 0.001), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Firms with aggressive asset growth underperform disciplined capital allocators ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

                # -------------------------------------------------------------
                # 3. Piotroski (2000) Cashflow Quality Decoupling
                # Operating Cashflow exceeding Net Income signals high earnings quality
                # (Accruals anomaly: Sloan 1996 / Piotroski 2000).
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "FUND_CASHFLOW_QUALITY",
                    "archetype": f"Fund_CashflowQuality_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear((cashflow_op - net_income) / (assets + 0.001), {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear((cashflow_op - net_income) / (assets + 0.001), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Operating cashflow exceeding net income filters out accrual-driven accounting manipulation ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

                # -------------------------------------------------------------
                # 4. Titman, Wei & Xie (2004) Capex Discipline
                # Fading aggressive Capex expansion
                # -------------------------------------------------------------
                catalog.append({
                    "pillar": "FUND_CAPEX_DISCIPLINE",
                    "archetype": f"Fund_CapexDiscipline_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize(rank(- ts_decay_linear(capex / (assets + 0.001), {d})) * rank(ts_decay_linear(gross_profit / (assets + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": f"Low Capex intensity interacting with gross profitability isolates capital-efficient compounders ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                    "source_kb": SOURCE_KB,
                })

    return catalog
