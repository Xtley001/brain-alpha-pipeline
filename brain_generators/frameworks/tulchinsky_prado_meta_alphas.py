"""
Tulchinsky (2020) & López de Prado (2018) Meta-Alpha Generator.

Implements institutional alpha signals derived from:
- Igor Tulchinsky et al.: 'Finding Alphas: A Quantitative Approach to Building Trading Strategies'
  (WorldQuant Virtual Research Center / Wiley Finance, 2020)
  [Operator tree representations, 4 cardinal metrics, Triple-Axis Plan, loss cutting, group neutralization].
- Marcos López de Prado: 'Advances in Financial Machine Learning' (Wiley Finance, 2018)
  [Triple-barrier volatility thresholds, meta-labeling confidence gates, fractional differentiation memory,
   structural break volatility filters, and deflated Sharpe ratio robustness].

All expressions strictly adhere to WorldQuant BRAIN syntax standards.
"""

from typing import List, Dict, Any

SOURCE_KB = "docs/kb/frameworks/tulchinsky_lopez_de_prado_afml.md"


def generate_tulchinsky_prado_meta_alphas() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates based on Tulchinsky's WorldQuant alpha design
    and López de Prado's financial machine learning meta-labeling & risk architecture.
    """
    candidates: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Category 1: Tulchinsky WorldQuant Alpha Factory Archetypes
    # -------------------------------------------------------------------------
    tulchinsky_archetypes = [
        # 1. Multi-factor Quality-Value Core: Book-to-Price x Operating Cash Flow Yield
        (
            "TULCHINSKY_QUALITY_VALUE_CORE",
            "Tulchinsky_Quality_Value_Core_Subind",
            "group_neutralize(rank(book_to_price) * rank(operating_cash_flow / (cap + 0.001)), subindustry)",
            "Tulchinsky (2020): Core multi-factor alpha combining fundamental cheapness with operating cash flow backing.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "TULCHINSKY_QUALITY_VALUE_CORE",
            "Tulchinsky_Quality_Value_Core_Sector",
            "group_neutralize(rank(book_to_price) * rank(operating_cash_flow / (cap + 0.001)), sector)",
            "Tulchinsky (2020): Sector-neutral quality-value cross-sectional score.",
            "SECTOR",
            10,
        ),
        # 2. Volatility-Scaled Alpha: alpha_i = Vol_i * IC * Score_i
        (
            "TULCHINSKY_VOL_SCALED_MOMENTUM",
            "Tulchinsky_Vol_Scaled_Reversal_Subind",
            "group_neutralize(rank(ts_std_dev(returns, 21)) * rank(-ts_decay_linear(returns, 5)), subindustry)",
            "Tulchinsky (2020): Short-term mean reversal score scaled by individual asset volatility.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "TULCHINSKY_VOL_SCALED_MOMENTUM",
            "Tulchinsky_Vol_Scaled_Momentum_Sector",
            "group_neutralize(rank(ts_std_dev(returns, 63)) * rank(ts_decay_linear(returns, 21)), sector)",
            "Tulchinsky (2020): Volatility-scaled intermediate momentum across sector peers.",
            "SECTOR",
            10,
        ),
        # 3. Cutting Losses & Risk Drawdown Gating (Chapter 3 / 14)
        (
            "TULCHINSKY_LOSS_CUTTING_GATE",
            "Tulchinsky_Loss_Cutting_Vol_Gate",
            "trade_when(ts_std_dev(returns, 10) < ts_mean(ts_std_dev(returns, 10), 63), group_neutralize(rank(ts_decay_linear(returns, 10)), subindustry), -1)",
            "Tulchinsky (2020): Risk-gated alpha that cuts exposure during sudden volatility spikes.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "TULCHINSKY_LOSS_CUTTING_GATE",
            "Tulchinsky_Drawdown_Protection_Gate",
            "trade_when(ts_decay_linear(returns, 5) > -0.05, group_neutralize(rank(book_to_price), subindustry), -1)",
            "Tulchinsky (2020): Drawdown protection gating preventing aggressive accumulation of sharp losers.",
            "SUBINDUSTRY",
            10,
        ),
        # 4. Power Dampening Non-Linear Transformation (Chapter 12)
        (
            "TULCHINSKY_POWER_DAMPENED",
            "Tulchinsky_Signed_Power_Value_Flow",
            "group_neutralize(signed_power(rank(book_to_price) - rank(ts_decay_linear(returns, 21)), 0.5), subindustry)",
            "Tulchinsky (2020): Signed power transformation smoothly attenuating extreme outlier leverage.",
            "SUBINDUSTRY",
            10,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in tulchinsky_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 2: López de Prado (2018) AFML Machine Learning & Barrier Archetypes
    # -------------------------------------------------------------------------
    prado_archetypes = [
        # 1. Triple-Barrier Dynamic Volatility Thresholding
        (
            "PRADO_TRIPLE_BARRIER_VOL",
            "Prado_Triple_Barrier_Vol_Ratio_Subind",
            "group_neutralize(rank(ts_decay_linear(returns, 5) / (ts_std_dev(returns, 21) + 0.001)), subindustry)",
            "López de Prado (2018): Volatility-standardized return metric reflecting horizontal barrier touches.",
            "SUBINDUSTRY",
            5,
        ),
        (
            "PRADO_TRIPLE_BARRIER_VOL",
            "Prado_Triple_Barrier_Vol_Ratio_Sector",
            "group_neutralize(rank(ts_decay_linear(returns, 10) / (ts_std_dev(returns, 63) + 0.001)), sector)",
            "López de Prado (2018): Medium-horizon volatility-adjusted hurdle rate across sector.",
            "SECTOR",
            10,
        ),
        # 2. Meta-Labeling Confidence Gate (Chapter 3)
        (
            "PRADO_META_LABELING_GATE",
            "Prado_Meta_Gated_Cash_Flow_Quality",
            "trade_when(rank(operating_cash_flow / (cap + 0.001)) > 0.65, group_neutralize(rank(ts_decay_linear(returns, 10)), subindustry), -1)",
            "López de Prado (2018): Two-stage meta-labeling: price momentum only traded when cash flow quality confirms high precision.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "PRADO_META_LABELING_GATE",
            "Prado_Meta_Gated_Value_Precision",
            "trade_when(rank(operating_cash_flow / (net_income + 0.001)) > 0.60, group_neutralize(rank(book_to_price), subindustry), -1)",
            "López de Prado (2018): Deep value signal gated by accrual quality probability filter.",
            "SUBINDUSTRY",
            15,
        ),
        # 3. Fractional Memory Approximation (Chapter 5)
        (
            "PRADO_FRACTIONAL_MEMORY",
            "Prado_Fractional_Memory_Composite_Subind",
            "group_neutralize(0.5 * rank(close / (ts_decay_linear(close, 252) + 0.001)) + 0.5 * rank(ts_delta(close, 21)), subindustry)",
            "López de Prado (2018): Long-memory price level preserved alongside short-term delta for stationary memory.",
            "SUBINDUSTRY",
            10,
        ),
        (
            "PRADO_FRACTIONAL_MEMORY",
            "Prado_Fractional_Memory_Composite_Sector",
            "group_neutralize(0.6 * rank(close / (ts_decay_linear(close, 126) + 0.001)) + 0.4 * rank(ts_delta(close, 10)), sector)",
            "López de Prado (2018): Intermediate fractional memory proxy across sector peers.",
            "SECTOR",
            10,
        ),
        # 4. Structural Break & Regime Shift Filter (Chapter 17)
        (
            "PRADO_STRUCTURAL_BREAK_FILTER",
            "Prado_Regime_Shift_Reversal_Subind",
            "trade_when(ts_std_dev(returns, 21) > ts_std_dev(returns, 126), group_neutralize(rank(-ts_decay_linear(returns, 5)), subindustry), -1)",
            "López de Prado (2018): Structural break filter triggering sharp mean reversion during regime volatility expansions.",
            "SUBINDUSTRY",
            5,
        ),
    ]

    for pillar, name, expr, desc, neut, decay in prado_archetypes:
        for universe in ["TOP3000", "TOP1000"]:
            candidates.append({
                "pillar": pillar,
                "archetype": f"{name}_{universe}",
                "expression": expr,
                "hypothesis": f"{desc} Evaluated on {universe} universe with {neut} neutralization.",
                "universe": universe,
                "neutralization": neut,
                "decay": decay,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # -------------------------------------------------------------------------
    # Category 3: Master Synthesis — Tulchinsky Factory Scale x Prado ML Meta-Logic
    # -------------------------------------------------------------------------
    synthesis_archetypes = [
        # 1. Master Meta-Alpha: Meta-Gated Quality-Value with Volatility Scaling
        (
            "TULCHINSKY_PRADO_MASTER_SYNTHESIS",
            "TP_Master_Meta_Gated_Quality_Value",
            "trade_when(rank(operating_cash_flow / (net_income + 0.001)) > 0.50, group_neutralize(signed_power(rank(book_to_price) * rank(ts_std_dev(returns, 63)), 0.5), subindustry), -1)",
            "Master Synthesis: Prado accrual confidence gate controlling Tulchinsky volatility-scaled quality-value score.",
            "SUBINDUSTRY",
            10,
        ),
        # 2. Fractional Memory x Loss Cutting Gate
        (
            "TULCHINSKY_PRADO_MASTER_SYNTHESIS",
            "TP_Fractional_Memory_Loss_Cutting",
            "trade_when(ts_std_dev(returns, 10) < ts_mean(ts_std_dev(returns, 10), 42), group_neutralize(rank(close / (ts_decay_linear(close, 126) + 0.001)), subindustry), -1)",
            "Master Synthesis: Long-memory trend capture combined with Tulchinsky loss-cutting volatility protection.",
            "SUBINDUSTRY",
            10,
        ),
        # 3. Triple-Barrier Vol Ratio x Power Dampened Momentum
        (
            "TULCHINSKY_PRADO_MASTER_SYNTHESIS",
            "TP_Triple_Barrier_Power_Momentum",
            "group_neutralize(signed_power(rank(ts_decay_linear(returns, 21) / (ts_std_dev(returns, 21) + 0.001)), 0.5), sector)",
            "Master Synthesis: Signed power transformation applied to volatility-standardized triple-barrier return ratio.",
            "SECTOR",
            10,
        ),
        # 4. Multi-Horizon Factory Composite
        (
            "TULCHINSKY_PRADO_MASTER_SYNTHESIS",
            "TP_Multi_Horizon_Factory_Composite",
            "group_neutralize(0.4 * rank(book_to_price) + 0.3 * rank(operating_cash_flow / (cap + 0.001)) + 0.3 * rank(ts_decay_linear(returns, 10) / (ts_std_dev(returns, 21) + 0.001)), subindustry)",
            "Master Synthesis: Complete factory multi-axis composite combining value, cash yield, and volatility-adjusted momentum.",
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
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    return candidates
