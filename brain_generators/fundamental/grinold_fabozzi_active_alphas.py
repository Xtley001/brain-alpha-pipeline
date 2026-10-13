"""
Grinold & Kahn (1995/2020), Fabozzi et al. (2010), Kruger (2007) Active Alpha Generator.

Implements institutional alpha signals derived from:
- Richard C. Grinold and Ronald N. Kahn: 'Active Portfolio Management' & 'Advances in Active Portfolio Management'
  [Fundamental Law IR = IC * sqrt(BR) * TC, volatility scaling, decay-weighted signals, factor crowding].
- Frank J. Fabozzi, Sergio M. Focardi, Petter N. Kolm: 'Quantitative Equity Investing'
  [Cash flow yield dominance, operating profitability x value, investment discipline, robust group neutralization].
- Samuel Kruger: 'Persistence in Mutual Fund Performance: Analysis of Holdings Returns' (2007)
  [Holdings persistence, institutional accumulation vs forced liquidation fire sales, Carhart momentum].

All expressions strictly adhere to WorldQuant BRAIN syntax standards.
"""

from typing import List, Dict, Any

SOURCE_KB = "docs/kb/fundamental/grinold_fabozzi_kruger_active_quant.md"


def generate_grinold_fabozzi_active_alphas() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates based on Grinold & Kahn active portfolio theory,
    Fabozzi multi-factor fundamental equity architecture, and Kruger holdings persistence.
    """
    candidates: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Category 1: Grinold & Kahn — Volatility-Scaled Alpha & Multi-Horizon Decay
    # -------------------------------------------------------------------------
    grinold_archetypes = [
        # 1. Volatility-scaled value alpha: alpha_i = Vol_i * IC * Score_i
        (
            "GRINOLD_VOL_SCALED_VALUE",
            "Grinold_Vol_Scaled_Book_to_Price",
            "group_neutralize(rank(ts_std_dev(returns, 63)) * rank(book_to_price), subindustry)",
            "Grinold & Kahn (1995/2020): Optimal alpha formula scales standardized score by asset residual volatility.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "GRINOLD_VOL_SCALED_VALUE",
            "Grinold_Vol_Scaled_Cash_Flow_Yield",
            "group_neutralize(rank(ts_std_dev(returns, 63)) * rank(operating_cash_flow / (cap + 0.001)), sector)",
            "Grinold & Kahn (1995/2020): Volatility-scaled cash flow yield allocating active risk budget across sector.",
            "SECTOR",
            10,
        ),
        # 2. Multi-horizon information decay weighting (Combining slow fundamental + fast price)
        (
            "GRINOLD_MULTI_HORIZON_DECAY",
            "Grinold_Multi_Horizon_Slow_Fast_Composite",
            "group_neutralize(0.7 * rank(ts_decay_linear(operating_cash_flow / (sales + 0.001), 126)) + 0.3 * rank(ts_decay_linear(returns, 10)), subindustry)",
            "Grinold & Kahn (2020): Optimal signal weighting combining slow fundamental cash flow margin with fast price momentum.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "GRINOLD_MULTI_HORIZON_DECAY",
            "Grinold_Multi_Horizon_Sales_Turnover_Decay",
            "group_neutralize(0.6 * rank(ts_decay_linear(sales / (inventory + 0.001), 63)) + 0.4 * rank(ts_decay_linear(returns, 5)), sector)",
            "Grinold & Kahn (2020): Decay-weighted composite of inventory turnover acceleration and short-term price flow.",
            "SECTOR",
            5,
        ),
        # 3. Breadth optimization: Non-linear signed power signal transformation
        (
            "GRINOLD_BREADTH_TRANSFORMATION",
            "Grinold_Signed_Power_Value_Momentum",
            "group_neutralize(signed_power(rank(book_to_price) + rank(ts_decay_linear(returns, 21)), 0.5), subindustry)",
            "Grinold & Kahn (2020): Non-linear score compression maximizing effective breadth and transfer coefficient.",
            "SUBINDUSTRY",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in grinold_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 2: Fabozzi, Focardi & Kolm — Multi-Factor Quality, Value & Investment
    # -------------------------------------------------------------------------
    fabozzi_archetypes = [
        # 1. Cash flow yield dominance over reported net income
        (
            "FABOZZI_CASH_FLOW_YIELD",
            "Fabozzi_CFO_to_Cap_Yield_Subind",
            "group_neutralize(rank(ts_decay_linear(operating_cash_flow / (cap + 0.001), 63)), subindustry)",
            "Fabozzi et al. (2010): Operating cash flow yield dominates unadjusted net income with higher empirical IC (0.052 vs 0.031).",
            "SUBINDUSTRY",
            15,
        ),
        (
            "FABOZZI_CASH_FLOW_YIELD",
            "Fabozzi_CFO_to_Cap_Yield_Sector",
            "group_neutralize(rank(ts_decay_linear(operating_cash_flow / (cap + 0.001), 126)), sector)",
            "Fabozzi et al. (2010): Long-horizon cash flow yield neutralized across sector peers.",
            "SECTOR",
            15,
        ),
        # 2. Operating profitability x Book-to-Price quality-value composite
        (
            "FABOZZI_QUALITY_VALUE_COMPOSITE",
            "Fabozzi_Gross_Profitability_x_Book_Value",
            "group_neutralize(rank(ts_decay_linear((sales - inventory) / (cap + 0.001), 63)) * rank(book_to_price), subindustry)",
            "Fabozzi et al. (2010): Interaction between operating economic profitability and fundamental valuation cheapness.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "FABOZZI_QUALITY_VALUE_COMPOSITE",
            "Fabozzi_Operating_Margin_x_Book_Value_Sector",
            "group_neutralize(rank(ts_decay_linear(ebit / (sales + 0.001), 63)) * rank(book_to_price), sector)",
            "Fabozzi et al. (2010): High operating margin firms trading at attractive book-to-price ratios.",
            "SECTOR",
            10,
        ),
        # 3. Capital investment discipline (Negative asset and debt growth)
        (
            "FABOZZI_INVESTMENT_DISCIPLINE",
            "Fabozzi_Capital_Discipline_Asset_Growth",
            "group_neutralize(rank(-ts_delta(total_debt + cap, 252) / (total_debt + cap + 0.001)), subindustry)",
            "Fabozzi et al. (2010): Conservative asset expansion avoids managerial empire-building and subsequent de-rating.",
            "SUBINDUSTRY",
            20,
        ),
        (
            "FABOZZI_INVESTMENT_DISCIPLINE",
            "Fabozzi_Debt_Expansion_Discipline_Sector",
            "group_neutralize(rank(-ts_delta(total_debt, 252) / (total_debt + 0.001)), sector)",
            "Fabozzi et al. (2010): Restraint in debt issuance signals sustainable capital allocation.",
            "SECTOR",
            20,
        ),
        # 4. Working capital efficiency: Sales growth exceeding working capital bloat
        (
            "FABOZZI_WORKING_CAPITAL_EFFICIENCY",
            "Fabozzi_Working_Cap_Efficiency_Subind",
            "group_neutralize(rank((ts_delta(sales, 252) / (sales + 0.001)) - (ts_delta(accounts_receivable + inventory, 252) / (accounts_receivable + inventory + 0.001))), subindustry)",
            "Fabozzi et al. (2010): Top-line revenue growth outpacing working capital requirements proves operational leverage.",
            "SUBINDUSTRY",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in fabozzi_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 3: Kruger (2007) — Institutional Holdings Persistence & Fire-Sale Avoidance
    # -------------------------------------------------------------------------
    kruger_archetypes = [
        # 1. Institutional Net Accumulation (Holding persistence)
        (
            "KRUGER_INSTITUTIONAL_PERSISTENCE",
            "Kruger_Inst_Net_Accumulation_63d",
            "group_neutralize(rank(ts_delta(institutional_ownership_percentage, 63)), subindustry)",
            "Kruger (2007): Net accumulation by institutional funds forecasts persistent stock outperformance.",
            "SUBINDUSTRY",
            15,
        ),
        (
            "KRUGER_INSTITUTIONAL_PERSISTENCE",
            "Kruger_Inst_Net_Accumulation_126d",
            "group_neutralize(rank(ts_delta(institutional_ownership_percentage, 126)), sector)",
            "Kruger (2007): Semi-annual institutional accumulation across sector peers.",
            "SECTOR",
            15,
        ),
        # 2. Distressed Fire-Sale Avoidance: Shorting bottom decile holdings facing outflow pressure
        (
            "KRUGER_FIRE_SALE_AVOIDANCE",
            "Kruger_Fire_Sale_Low_Inst_High_Shorts",
            "trade_when(rank(-institutional_ownership_percentage) > 0.60, group_neutralize(rank(-ts_decay_linear(short_interest_ratio, 21)), subindustry), -1)",
            "Kruger (2007): Underperformance of bottom decile funds is driven by forced fire-sale selling of short-heavy stocks.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "KRUGER_FIRE_SALE_AVOIDANCE",
            "Kruger_Outflow_Spiral_Volume_Pressure",
            "trade_when(rank(-institutional_ownership_percentage) > 0.60, group_neutralize(rank(-ts_decay_linear(returns, 5) * rank(volume / (adv20 + 0.001))), sector), -1)",
            "Kruger (2007): Fire-sale liquidation spikes selling volume and causes persistent downward price pressure.",
            "SECTOR",
            5,
        ),
        # 3. Holdings Carhart Momentum Persistence
        (
            "KRUGER_HOLDINGS_MOMENTUM",
            "Kruger_Carhart_Holdings_Momentum",
            "group_neutralize(rank(ts_decay_linear(returns, 252) - ts_decay_linear(returns, 21)), subindustry)",
            "Kruger (2007) & Carhart (1997): 12-month momentum excluding immediate 1-month reversal captures holdings persistence.",
            "SUBINDUSTRY",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in kruger_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 4: Master Synthesis — Grinold Skill x Fabozzi Quality x Kruger Flow
    # -------------------------------------------------------------------------
    synthesis_archetypes = [
        # 1. Institutional Accumulation x Cash Flow Yield
        (
            "GRINOLD_FABOZZI_KRUGER_SYNTHESIS",
            "GFK_Inst_Accumulation_x_Cash_Yield",
            "group_neutralize(signed_power(rank(ts_delta(institutional_ownership_percentage, 63)) + rank(operating_cash_flow / (cap + 0.001)), 0.5), subindustry)",
            "Master Synthesis: Non-linear composite of institutional smart money accumulation and high operating cash flow yield.",
            "SUBINDUSTRY",
            10,
        ),
        # 2. Volatility-Scaled Accrual Quality x Holdings Momentum
        (
            "GRINOLD_FABOZZI_KRUGER_SYNTHESIS",
            "GFK_Vol_Scaled_Accrual_x_Momentum",
            "group_neutralize(rank(ts_std_dev(returns, 63)) * rank(operating_cash_flow - net_income) * rank(ts_decay_linear(returns, 63)), subindustry)",
            "Master Synthesis: Grinold volatility scaling applied to Fabozzi accrual quality backed by Kruger holdings momentum.",
            "SUBINDUSTRY",
            10,
        ),
        # 3. Capital Discipline x Institutional Accumulation
        (
            "GRINOLD_FABOZZI_KRUGER_SYNTHESIS",
            "GFK_Capital_Discipline_x_Inst_Accumulation",
            "group_neutralize(rank(-ts_delta(total_debt, 252) / (total_debt + 0.001)) * rank(ts_delta(institutional_ownership_percentage, 63)), sector)",
            "Master Synthesis: Restraint in debt financing reinforced by institutional manager net buying.",
            "SECTOR",
            15,
        ),
        # 4. Quality Value x Low Fire-Sale Risk in Small Caps
        (
            "GRINOLD_FABOZZI_KRUGER_SYNTHESIS",
            "GFK_Quality_Value_SmallCap_Gated",
            "trade_when(rank(-cap) > 0.50, group_neutralize(rank(book_to_price) * rank(operating_cash_flow / (sales + 0.001)), subindustry), -1)",
            "Master Synthesis: Deep value high cash margin small-cap stocks insulated from institutional fire sales.",
            "SUBINDUSTRY",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in synthesis_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "fundamental",
                "source_kb": SOURCE_KB,
            })

    return candidates
