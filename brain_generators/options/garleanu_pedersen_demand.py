"""
Garleanu, Pedersen & Poteshman (2009) — Demand-Based Option Pricing
Source KB: docs/kb/options/garleanu_pedersen_demand_pricing.md

Key Institutional Empirical Findings (RFS 2009):
1. Demand-pressure pricing kernel: option prices deviate from no-arbitrage values by an amount
   proportional to the variance of dealer unhedgeable risk:
   - Discrete trading (Gamma risk): t = 3.85, R^2 = 18.5%.
   - Jump risk (Kappa risk): t = 3.68, R^2 = 25.9%.
   - Stochastic volatility (Vega risk): t = 2.74, R^2 = 15.7%.
2. Dealer P&L interaction: When market makers suffer trading losses over past 20 days,
   effective risk aversion spikes and the demand-price sensitivity doubles (t = -2.72).
3. Cross-sectional equity options: Retail/institutional covered-call selling pushes single-stock
   call IV below fair value; negative demand stocks trade at the deepest volatility discount.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/garleanu_pedersen_demand_pricing.md"


def generate_garleanu_pedersen_demand_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Garleanu, Pedersen & Poteshman (2009).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    tenors = [30, 60]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. GPP (2009): Jump-Risk Weighted Demand Pressure (Kappa Risk Channel)
    # Jumps cannot be locally hedged; unhedgeable kappa drives skew and pricing (t = 3.68, R^2 = 25.9%)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for t in tenors:
                for d in decays[:2]:
                    catalog.append({
                        "pillar": "DEMAND_OPTION_PRICING",
                        "archetype": f"GPP_Jump_Demand_t{t}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.80, "
                            f"group_neutralize(rank(ts_decay_linear((iv_put_{t} - iv_atm_{t}) * option_volume / (adv20 + 1), {d})), {g.lower()}), "
                            f"-1)"
                        ),
                        "hypothesis": (
                            f"Garleanu-Pedersen-Poteshman (2009) Table 2: Jump-risk (kappa) weighted demand pressure "
                            f"predicts option expensiveness and underlying drift (t=3.68, R2=25.9%). {t}d tenor, decay {d}, {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. GPP (2009): Discrete-Trading Gamma Friction Channel
    # Dealer rebalancing frictions scale with Gamma^2 * Var(Delta S^2) (t = 3.85, R^2 = 18.5%)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "DEMAND_OPTION_PRICING",
                    "archetype": f"GPP_Gamma_Friction_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.75, "
                        f"group_neutralize(rank(ts_decay_linear(option_volume * (high - low) / (close * volume + 1), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Garleanu-Pedersen-Poteshman (2009) Case 1: Discrete-trading gamma hedging frictions "
                        f"increase dealer inventory cost and demand-based markup (t=3.85). Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. GPP (2009): Stochastic Volatility Vega Demand Channel
    # Demand pressure weighted by mean-reverting vega exposure (t = 2.74, R^2 = 15.7%)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "DEMAND_OPTION_PRICING",
                    "archetype": f"GPP_Vega_Demand_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank(ts_decay_linear(iv_atm_{t} * option_volume / (adv20 + 1), 10)), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Garleanu-Pedersen-Poteshman (2009) Case 3: Vega-weighted stochastic volatility inventory "
                        f"demand pressure (t=2.74). {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. GPP (2009): State-Dependent Dealer Loss Squeeze (P&L x Demand Interaction)
    # Following market maker losses, effective risk aversion spikes and sensitivity doubles (t = -2.72)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "MARKET"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "DEMAND_OPTION_PRICING",
                    "archetype": f"GPP_Dealer_Loss_Squeeze_t{t}_{u}_{g}",
                    "expression": (
                        f"trade_when(ts_mean(returns, 20) < 0, "
                        f"group_neutralize(rank(iv_call_{t} - iv_put_{t}) * rank(option_volume / (adv20 + 1)), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Garleanu-Pedersen-Poteshman (2009) Table 3: Dealer loss interaction (P&L x Demand). "
                        f"Following market maker losses, price response doubles (t=-2.72). {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. GPP (2009): Single-Stock Covered Call Depression Arbitrage
    # Non-market makers are net sellers of single-stock options (covered calls), depressing OTM call IV
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for t in [30, 60]:
                catalog.append({
                    "pillar": "DEMAND_OPTION_PRICING",
                    "archetype": f"GPP_Covered_Call_Discount_t{t}_{u}_{g}",
                    "expression": (
                        f"group_neutralize(rank(-(iv_call_{t} - historical_volatility_{t}) / (historical_volatility_{t} + 0.001)), {g.lower()})"
                    ),
                    "hypothesis": (
                        f"Garleanu-Pedersen-Poteshman (2009) Section 3.2: Single-stock covered call selling "
                        f"artificially depresses call implied volatility relative to physical volatility. {t}d tenor, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 5,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. GPP (2009): Net Demand Imbalance Ratio
    # (Call Vol - Put Vol) / (Call Vol + Put Vol) weighted by ATM IV expensiveness
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in neut_groups:
            catalog.append({
                "pillar": "DEMAND_OPTION_PRICING",
                "archetype": f"GPP_Net_Demand_Imbalance_{u}_{g}",
                "expression": (
                    f"group_neutralize(rank(ts_decay_linear((iv_call_30 - iv_put_30) / (iv_atm_30 + 0.001), 10) * "
                    f"rank(option_volume / (adv20 + 1))), {g.lower()})"
                ),
                "hypothesis": (
                    f"Garleanu-Pedersen-Poteshman (2009) Equation 25: Net demand pressure scaled by relative "
                    f"skew and liquidity turnover. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    return catalog
