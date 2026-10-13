"""
Staley (1997) & Engelberg, Reed, Ringgenberg (2018) Short-Selling Alpha Generator.

Implements institutional alpha signals derived from:
- Kathryn F. Staley: 'The Art of Short Selling' (John Wiley & Sons, 1997)
  [Inventory disconnections, receivables/revenue divergence, cash flow vs net income decoupling,
   unsupportable interest burden, and torpedo stock multiple contraction].
- Joseph E. Engelberg, Adam V. Reed, and Matthew C. Ringgenberg: 'Short-Selling Risk'
  (The Journal of Finance 73, no. 2, 2018, pp. 755-786)
  [Dynamic loan fee uncertainty, borrow fee variance (ShortRisk), tail risk VAR99,
   small-cap limit-to-arbitrage concentration, and holding period delay].

All expressions strictly adhere to WorldQuant BRAIN syntax standards.
"""

from typing import List, Dict, Any

SOURCE_KB = "docs/kb/short_interest/staley_short_selling_risk.md"


def generate_staley_short_risk_alphas() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates based on Staley (1997) fundamental forensic red flags
    and Engelberg, Reed & Ringgenberg (2018) short-selling risk dynamics.
    """
    candidates: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Category 1: Staley Fundamental Red Flags — Inventory & Receivables Decoupling
    # -------------------------------------------------------------------------
    staley_accrual_archetypes = [
        # 1. Inventory growth exceeding sales growth (Bloated inventory anomaly)
        (
            "STALEY_INVENTORY_DISCONNECT",
            "Staley_Inv_Sales_Divergence_Subind",
            "group_neutralize(rank(-((ts_delta(inventory, 252) / (ts_decay_linear(inventory, 63) + 0.001)) - (ts_delta(sales, 252) / (ts_decay_linear(sales, 63) + 0.001)))), subindustry)",
            "Staley (1997): Inventories expanding faster than top-line sales indicates unsold goods and unrecorded obsolescence.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "STALEY_INVENTORY_DISCONNECT",
            "Staley_Inv_Sales_Divergence_Sector",
            "group_neutralize(rank(-((ts_delta(inventory, 126) / (ts_decay_linear(inventory, 42) + 0.001)) - (ts_delta(sales, 126) / (ts_decay_linear(sales, 42) + 0.001)))), sector)",
            "Staley (1997): Medium-term inventory-to-sales acceleration anomaly neutralized at sector level.",
            "SECTOR",
            10,
        ),
        (
            "STALEY_INVENTORY_TURNOVER",
            "Staley_Inv_Turnover_Slowdown",
            "group_neutralize(rank(ts_decay_linear(sales / (inventory + 0.001), 63) - ts_decay_linear(sales / (inventory + 0.001), 252)), subindustry)",
            "Staley (1997): Slowing inventory turnover (Crazy Eddie & Kirschner Medical pattern) signals deterioration.",
            "SUBINDUSTRY",
            15,
        ),
        # 2. Receivables growth exceeding revenue growth (DSO expansion / channel stuffing)
        (
            "STALEY_RECEIVABLES_BLOAT",
            "Staley_AR_Sales_Divergence_Subind",
            "group_neutralize(rank(-((ts_delta(accounts_receivable, 252) / (ts_decay_linear(accounts_receivable, 63) + 0.001)) - (ts_delta(sales, 252) / (ts_decay_linear(sales, 63) + 0.001)))), subindustry)",
            "Staley (1997): Accounts receivable growing faster than sales indicates aggressive revenue recognition and uncollectible receivables.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "STALEY_RECEIVABLES_BLOAT",
            "Staley_AR_Sales_Divergence_Sector",
            "group_neutralize(rank(-((ts_delta(accounts_receivable, 126) / (ts_decay_linear(accounts_receivable, 42) + 0.001)) - (ts_delta(sales, 126) / (ts_decay_linear(sales, 42) + 0.001)))), sector)",
            "Staley (1997): Medium-term DSO acceleration anomaly neutralized across sector.",
            "SECTOR",
            10,
        ),
        (
            "STALEY_WORKING_CAPITAL_BLOAT",
            "Staley_Joint_Working_Cap_Bloat",
            "group_neutralize(rank(-((ts_delta(inventory + accounts_receivable, 252) / (ts_decay_linear(inventory + accounts_receivable, 63) + 0.001)) - (ts_delta(sales, 252) / (ts_decay_linear(sales, 63) + 0.001)))), subindustry)",
            "Staley (1997): Joint inventory and receivables bloat relative to revenue expansion.",
            "SUBINDUSTRY",
            10,
        ),
        # 3. Cash flow vs Net income decoupling (The Accrual Burn / Money Sucker)
        (
            "STALEY_ACCRUAL_GAP",
            "Staley_OCF_Net_Income_Accrual_Gap",
            "group_neutralize(rank(ts_decay_linear(operating_cash_flow, 126) - ts_decay_linear(net_income, 126)), subindustry)",
            "Staley (1997): High reported net income without operating cash flow backing identifies earnings manipulation.",
            "SUBINDUSTRY",
            15,
        ),
        (
            "STALEY_DEBT_SOLVENCY_DRAIN",
            "Staley_OCF_to_Debt_Drain",
            "group_neutralize(rank(ts_decay_linear(operating_cash_flow, 252) / (total_debt + 0.001)), subindustry)",
            "Staley (1997): Inability of operating cash flows to support debt obligations predicts solvency distress.",
            "SUBINDUSTRY",
            15,
        ),
        (
            "STALEY_INTEREST_COVERAGE",
            "Staley_Interest_Coverage_Vulnerability",
            "trade_when(ebit < interest_expense, group_neutralize(rank(ebit / (interest_expense + 0.001)), subindustry), -1)",
            "Staley (1997): Operating earnings failing to cover interest expenses creates unviable capital structure.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "STALEY_LEVERAGE_BURDEN",
            "Staley_Debt_to_EBIT_Distress",
            "group_neutralize(rank(-ts_decay_linear(total_debt / (abs(ebit) + 0.001), 63)), sector)",
            "Staley (1997): Excessive leverage multiple relative to operating earnings power.",
            "SECTOR",
            10,
        ),
        # 4. Torpedo stocks: High multiple facing decelerating cash generation
        (
            "STALEY_TORPEDO_STOCK",
            "Staley_Torpedo_PE_Growth_Cliff",
            "trade_when(rank(pe) > 0.80, group_neutralize(rank(ts_delta(operating_cash_flow, 126)), subindustry), -1)",
            "Staley (1997): Hagin torpedo stock effect — high PE stocks experiencing cash flow slowdown suffer massive de-rating.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "STALEY_TORPEDO_STOCK",
            "Staley_Torpedo_PB_Sales_Cliff",
            "trade_when(rank(pb) > 0.80, group_neutralize(rank(ts_delta(sales, 126)), sector), -1)",
            "Staley (1997): High PB glamour stocks with decelerating revenue growth undergo sharp multiple compression.",
            "SECTOR",
            5,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in staley_accrual_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Applied to {universe} with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "short_interest",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 2: Engelberg, Reed & Ringgenberg (2018) — Dynamic Short-Selling Risk
    # -------------------------------------------------------------------------
    err_short_risk_archetypes = [
        # 1. Base ShortRisk: Fee volatility proxy (Standard deviation of Short Interest)
        (
            "ERR_SHORTRISK_VOLATILITY",
            "ERR_ShortRisk_Fee_Volatility_63d",
            "group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63)), subindustry)",
            "ERR (2018): Low ShortRisk (stable borrow) outperforms high ShortRisk (volatile borrow fees) by 1.08%/month.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "ERR_SHORTRISK_VOLATILITY",
            "ERR_ShortRisk_Fee_Volatility_126d",
            "group_neutralize(rank(-ts_std_dev(short_interest_ratio, 126)), subindustry)",
            "ERR (2018): Trailing 6-month loan fee variance proxy predicts 9.6% annual 5-factor alpha spread.",
            "SUBINDUSTRY",
            15,
        ),
        (
            "ERR_SHORTRISK_VOLATILITY",
            "ERR_ShortRisk_Rel_Volatility_Sector",
            "group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63) / (ts_mean(short_interest_ratio, 63) + 0.001)), sector)",
            "ERR (2018): Coefficient of variation of short interest capturing unexpected loan fee shocks.",
            "SECTOR",
            10,
        ),
        # 2. Tail risk of borrow fees: Value-at-Risk formula (TailNewFee = Mean + 2.33 * StDev)
        (
            "ERR_TAIL_BORROW_RISK",
            "ERR_Var99_Tail_Fee_Risk_Subind",
            "group_neutralize(rank(-(ts_mean(short_interest_ratio, 126) + 2.33 * ts_std_dev(short_interest_ratio, 126))), subindustry)",
            "ERR (2018): 99th percentile parametric tail borrow risk proxies for severe borrow spikes and recall hazard.",
            "SUBINDUSTRY",
            15,
        ),
        (
            "ERR_TAIL_BORROW_RISK",
            "ERR_Var99_Tail_Fee_Risk_Sector",
            "group_neutralize(rank(-(ts_mean(short_interest_ratio, 63) + 2.33 * ts_std_dev(short_interest_ratio, 63))), sector)",
            "ERR (2018): Short-horizon 99th percentile borrow tail risk across sector peers.",
            "SECTOR",
            10,
        ),
        # 3. Conditioning ShortRisk on high Short Interest Level (Table III interaction)
        (
            "ERR_SHORTRISK_INTERACTION",
            "ERR_ShortRisk_High_SIR_Gate",
            "trade_when(rank(short_interest_ratio) > 0.70, group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63)), subindustry), -1)",
            "ERR (2018): In high short interest stocks, fee volatility generates the most severe limits to arbitrage.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "ERR_SHORTRISK_INTERACTION",
            "ERR_ShortRisk_Low_Inst_Ownership_Gate",
            "trade_when(rank(-institutional_ownership_percentage) > 0.60, group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63)), subindustry), -1)",
            "ERR (2018) & Asquith (2005): Borrow uncertainty in stocks with sparse institutional lending supply.",
            "SUBINDUSTRY",
            5,
        ),
        # 4. Small and Micro Cap concentration (Table III/IV size breakdown)
        (
            "ERR_LIMITS_TO_ARBITRAGE",
            "ERR_SmallCap_ShortRisk_Concentration",
            "trade_when(rank(-cap) > 0.60, group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63)), sector), -1)",
            "ERR (2018): Short-selling risk premium is heavily concentrated in small-cap stocks (99th fee = 1,119 bps).",
            "SECTOR",
            5,
        ),
        (
            "ERR_LIMITS_TO_ARBITRAGE",
            "ERR_MicroCap_Tail_Risk_Alpha",
            "trade_when(rank(-cap) > 0.80, group_neutralize(rank(-(ts_mean(short_interest_ratio, 63) + 2.33 * ts_std_dev(short_interest_ratio, 63))), subindustry), -1)",
            "ERR (2018): Micro-cap tail borrow risk generates largest abnormal overpricing persistence.",
            "SUBINDUSTRY",
            5,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in err_short_risk_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Applied to {universe} with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "short_interest",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 3: Joint Synthesis — Forensic Accounting Disconnect x Borrow Dynamics
    # -------------------------------------------------------------------------
    joint_synthesis_archetypes = [
        # 1. Staley Inventory Decoupling interacted with High Short Interest
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Inv_Disconnect_x_SIR",
            "group_neutralize(rank(-ts_delta(inventory, 252) / (inventory + 0.001)) * rank(-ts_decay_linear(short_interest_ratio, 21)), subindustry)",
            "Joint Staley-ERR: Inventory accumulation confirming aggressive institutional short accumulation.",
            "SUBINDUSTRY",
            10,
        ),
        # 2. Receivables Decoupling interacted with ShortRisk
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_AR_Disconnect_x_ShortRisk",
            "group_neutralize(rank(-ts_delta(accounts_receivable, 252) / (accounts_receivable + 0.001)) * rank(-ts_std_dev(short_interest_ratio, 63)), subindustry)",
            "Joint Staley-ERR: High receivables bloat compounded by equity borrow fee uncertainty.",
            "SUBINDUSTRY",
            10,
        ),
        # 3. Accrual Gap interacted with Small Cap Limit to Arbitrage
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Accrual_Gap_SmallCap",
            "trade_when(rank(-cap) > 0.50, group_neutralize(rank(operating_cash_flow - net_income), subindustry), -1)",
            "Joint Staley-ERR: Negative operating cash flow and high net income distortion concentrated in small-cap universe.",
            "SUBINDUSTRY",
            5,
        ),
        # 4. Debt Coverage Danger with High Short Interest
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Interest_Distress_x_SIR",
            "trade_when(ebit < interest_expense, group_neutralize(rank(-ts_decay_linear(short_interest_ratio, 21)), subindustry), -1)",
            "Joint Staley-ERR: Firms with insolvent interest coverage subjected to heavy short-seller pressure.",
            "SUBINDUSTRY",
            5,
        ),
        # 5. Torpedo Valuation with High Borrow Risk
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Torpedo_PE_x_ShortRisk",
            "trade_when(rank(pe) > 0.70, group_neutralize(rank(-ts_std_dev(short_interest_ratio, 63)), sector), -1)",
            "Joint Staley-ERR: Glamour multiple stocks facing borrow fee volatility and impending negative shock.",
            "SECTOR",
            5,
        ),
        # 6. Smooth Power-Dampened Composite
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Composite_Forensic_Borrow",
            "group_neutralize(signed_power(rank(-((ts_delta(inventory, 252) / (inventory + 0.001)) - (ts_delta(sales, 252) / (sales + 0.001)))) + rank(-ts_std_dev(short_interest_ratio, 63)), 0.5), subindustry)",
            "Joint Staley-ERR: Nonlinear signed power transformation combining inventory disconnect and borrow risk.",
            "SUBINDUSTRY",
            10,
        ),
        # 7. Volume Liquidity Days-to-Cover with Forensic Accrual
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_DTC_Forensic_Accrual",
            "group_neutralize(rank(-ts_decay_linear(short_interest_ratio / (adv20 + 0.001), 21)) * rank(operating_cash_flow - net_income), subindustry)",
            "Joint Staley-ERR: Days-to-cover short pressure magnified by deteriorating operating cash flow quality.",
            "SUBINDUSTRY",
            10,
        ),
        # 8. Decaying Staley Inventory Ratio across Sector
        (
            "STALEY_ERR_JOINT_SYNTHESIS",
            "Staley_ERR_Inv_Sales_Decay_Sector",
            "group_neutralize(rank(-ts_decay_linear((inventory / (sales + 0.001)), 63)), sector)",
            "Joint Staley-ERR: Sector-neutral inventory-to-sales ratio trend indicating structural margin compression.",
            "SECTOR",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in joint_synthesis_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Applied to {universe} with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "short_interest",
                "source_kb": SOURCE_KB,
            })

    return candidates
