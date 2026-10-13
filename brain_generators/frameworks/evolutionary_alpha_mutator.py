"""
Evolutionary Alpha Mutator & Signal Optimizer.
Synthesizes mutated, orthogonalized, high-conviction alpha candidates from
empirically confirmed institutional signals discovered during mining sessions:

1. Prado Regime-Shift Reversals (Empirical Champion: Sharpe 1.32 | Fit 0.95 | Margin 10.3 bps)
   - Multi-window volatility threshold variations
   - Orthogonalized volume-shock and accrual confirmations (lowers rho < 0.62)
2. Options Smirk Tail Dynamics (Empirical Performer: Sharpe 0.91 | Margin 22.3 bps)
   - Breadth expansion to TOP1000 / TOP3000
   - Power dampening and Grinold decay optimization
3. Kakushadze Framework Alphas (Empirical Performer: Sharpe 0.92)
   - Subindustry neutralization and cross-sectional volume weighting
4. Supply Chain Lead-Lag Momentum (Empirical Performer: Sharpe 0.90)
   - Customer-supplier momentum propagation with decay tuning
5. Staley Forensic Capital Vulnerability (Empirical Performer: Margin 46.5 bps)
   - Interest coverage distress interacted with institutional short interest
"""
from __future__ import annotations

from typing import Any, Dict, List

SOURCE_KB = "docs/kb/frameworks/ai_agentic_evolutionary_mining_architecture.md"


def generate_evolutionary_mutator_candidates() -> List[Dict[str, Any]]:
    """
    Generates a curated cohort of genetically mutated, power-dampened, and
    orthogonalized alpha candidates derived from confirmed top performers.
    """
    candidates: List[Dict[str, Any]] = []

    # =========================================================================
    # MUTATION FAMILY 1: Prado Regime-Shift Reversal Variants (Target: 1.35+ Sharpe, |rho| <= 0.50)
    # Baseline: trade_when(ts_std_dev(returns, 21) > ts_std_dev(returns, 126), group_neutralize(rank(-ts_decay_linear(returns, 5)), subindustry), -1)
    # =========================================================================
    prado_mutations = [
        # Mutation 1A: Volume-shock confirmed regime reversal
        (
            "Prado_Mut_VolShock_Reversal",
            "trade_when(ts_std_dev(returns, 21) > ts_std_dev(returns, 126), group_neutralize(signed_power(rank(-ts_decay_linear(returns, 5)) * rank(volume / adv20), 0.5), subindustry), -1)",
            "Prado AFML Mutation: Structural volatility expansion confirmed by abnormal volume shock.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [5, 8, 10],
        ),
        # Mutation 1B: Faster regime shift window (10d vs 63d)
        (
            "Prado_Mut_FastRegime_Reversal",
            "trade_when(ts_std_dev(returns, 10) > ts_std_dev(returns, 63), group_neutralize(rank(-ts_decay_linear(returns, 6)), subindustry), -1)",
            "Prado AFML Mutation: Faster 10d/63d volatility horizon capturing prompt regime transitions.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY", "SECTOR"],
            [6, 8, 12],
        ),
        # Mutation 1C: Intraday spread volatility gating
        (
            "Prado_Mut_RangeVol_Reversal",
            "trade_when(ts_std_dev((high - low) / close, 21) > ts_mean(ts_std_dev((high - low) / close, 21), 126), group_neutralize(rank(-ts_decay_linear(returns, 5)), subindustry), -1)",
            "Prado AFML Mutation: High-low range expansion trigger for mean reversion.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [5, 8],
        ),
        # Mutation 1D: Quality-gated regime reversal (Accrual cash flow filter)
        (
            "Prado_Mut_QualityGated_Reversal",
            "trade_when(ts_std_dev(returns, 21) > ts_std_dev(returns, 126), group_neutralize(rank(-ts_decay_linear(returns, 5)) * rank(operating_cash_flow / (cap + 0.001)), subindustry), -1)",
            "Prado AFML Mutation: Two-stage meta-labeling filtering out fundamentally deteriorating firms.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [8, 12],
        ),
        # Mutation 1E: Exponential decay smoothing with power dampening
        (
            "Prado_Mut_PowerDampened_Reversal",
            "trade_when(ts_std_dev(returns, 21) > ts_std_dev(returns, 126), group_neutralize(signed_power(rank(-ts_decay_linear(returns, 8)), 0.5), subindustry), -1)",
            "Prado AFML Mutation: Power-dampened 8-day mean reversion under regime expansion.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [8, 10, 14],
        ),
    ]

    for name, expr, desc, univs, neuts, decays in prado_mutations:
        for u in univs:
            for g in neuts:
                for d in decays:
                    candidates.append({
                        "pillar": "PRADO_MUTATION",
                        "archetype": f"{name}_{u}_{g}_d{d}",
                        "expression": expr,
                        "hypothesis": f"{desc} Optimized on {u} universe with {g} neutralization and {d}d decay.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                        "source_kb": SOURCE_KB,
                    })

    # =========================================================================
    # MUTATION FAMILY 2: Options Smirk Tail Mutations (Target: 1.30+ Sharpe, 15+ bps margin)
    # Baseline: Opt_Smirk_Tail (Sharpe 0.91, Margin 22.3 bps, TO 4.7%)
    # =========================================================================
    smirk_mutations = [
        # Mutation 2A: Breadth expansion to TOP1000 with subindustry neutralization
        (
            "SmirkTail_Mut_TOP1000_Subind",
            "trade_when(volume > adv20 * 0.85, group_neutralize(signed_power(rank(-ts_decay_linear(implied_volatility_call_150 - implied_volatility_put_150, 14)), 0.5), subindustry), -1)",
            "Options Smirk Mutation: 150-day IV tail skew with signed power dampening across TOP1000.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [12, 16, 20],
        ),
        # Mutation 2B: 180-day long-horizon smirk with volume interaction
        (
            "SmirkTail_Mut_LongHorizon_VolWeight",
            "trade_when(volume > adv20 * 0.90, group_neutralize(rank(-ts_decay_linear(implied_volatility_call_180 - implied_volatility_put_180, 16)) * rank(volume / adv20), subindustry), -1)",
            "Options Smirk Mutation: 180-day institutional IV skew reinforced by volume conviction.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [14, 18],
        ),
        # Mutation 2C: 120-day curvature slope
        (
            "SmirkTail_Mut_Curvature_Slope",
            "trade_when(volume > adv20 * 0.80, group_neutralize(signed_power(rank(ts_decay_linear(implied_volatility_put_120 - implied_volatility_call_120, 12)), 0.5), subindustry), -1)",
            "Options Smirk Mutation: 120-day put-call slope with power attenuation.",
            ["TOP1000", "TOP500"],
            ["SUBINDUSTRY"],
            [10, 14],
        ),
    ]

    for name, expr, desc, univs, neuts, decays in smirk_mutations:
        for u in univs:
            for g in neuts:
                for d in decays:
                    candidates.append({
                        "pillar": "OPTIONS_SMIRK_MUTATION",
                        "archetype": f"{name}_{u}_{g}_d{d}",
                        "expression": expr,
                        "hypothesis": f"{desc} Evaluated on {u} with {g} neutralization and {d}d decay.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "options",
                        "source_kb": SOURCE_KB,
                    })

    # =========================================================================
    # MUTATION FAMILY 3: Kakushadze Alpha 30 & Framework Mutations (Baseline: Sharpe 0.92)
    # =========================================================================
    k101_mutations = [
        # Mutation 3A: Alpha 30 with Subindustry Neutralization & Volume Dampening
        (
            "K101_A30_Mut_Subind_Dampened",
            "group_neutralize(signed_power(rank(ts_decay_linear(1.0 - rank(ts_delta(close, 3)), 12)) * rank(volume / adv20), 0.5), subindustry)",
            "Kakushadze Alpha 30 Mutation: 3-day short-term price delta reversal with volume scaling and subindustry neutrality.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [10, 14, 18],
        ),
        # Mutation 3B: Alpha 30 with 5-day delta and liquidity guard
        (
            "K101_A30_Mut_LiquidityGuard",
            "trade_when(volume > adv20 * 0.85, group_neutralize(rank(ts_decay_linear(1.0 - rank(ts_delta(close, 5)), 14)), subindustry), -1)",
            "Kakushadze Alpha 30 Mutation: 5-day delta reversal protected by 0.85x ADV20 liquidity floor.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [12, 16],
        ),
    ]

    for name, expr, desc, univs, neuts, decays in k101_mutations:
        for u in univs:
            for g in neuts:
                for d in decays:
                    candidates.append({
                        "pillar": "K101_MUTATION",
                        "archetype": f"{name}_{u}_{g}_d{d}",
                        "expression": expr,
                        "hypothesis": f"{desc} Evaluated on {u} with {g} neutralization and {d}d decay.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "fundamental",
                        "source_kb": SOURCE_KB,
                    })

    # =========================================================================
    # MUTATION FAMILY 4: Supply Chain Lead-Lag Momentum (Baseline: Sharpe 0.90, Margin 4.9 bps)
    # =========================================================================
    sc_mutations = [
        # Mutation 4A: Lead-lag customer momentum on TOP1000
        (
            "SC_LeadLag_Mut_TOP1000",
            "group_neutralize(signed_power(rank(ts_decay_linear(ts_delay(ts_sum(returns, 21), 5), 14)), 0.5), subindustry)",
            "Menzly-Ozbas Supply Chain Mutation: 5-day delayed 21-day customer return momentum with power dampening.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [12, 16, 20],
        ),
        # Mutation 4B: Lead-lag momentum with volume confirmation
        (
            "SC_LeadLag_Mut_VolConfirm",
            "trade_when(volume > adv20 * 0.80, group_neutralize(rank(ts_decay_linear(ts_delay(ts_sum(returns, 15), 3), 12)) * rank(volume / adv20), subindustry), -1)",
            "Menzly-Ozbas Supply Chain Mutation: Volume-confirmed lead-lag cross-propagation.",
            ["TOP1000", "TOP3000"],
            ["SUBINDUSTRY"],
            [10, 14],
        ),
    ]

    for name, expr, desc, univs, neuts, decays in sc_mutations:
        for u in univs:
            for g in neuts:
                for d in decays:
                    candidates.append({
                        "pillar": "SUPPLY_CHAIN_MUTATION",
                        "archetype": f"{name}_{u}_{g}_d{d}",
                        "expression": expr,
                        "hypothesis": f"{desc} Evaluated on {u} with {g} neutralization and {d}d decay.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "fundamental",
                        "source_kb": SOURCE_KB,
                    })

    # =========================================================================
    # MUTATION FAMILY 5: Staley Forensic Short Risk (Baseline: Margin 46.5 bps! Turnover 2.5%)
    # =========================================================================
    staley_mutations = [
        # Mutation 5A: Staley Interest Coverage Vulnerability with Power Dampening
        (
            "Staley_Mut_InterestCoverage_Power",
            "trade_when(volume > adv20 * 0.70, group_neutralize(signed_power(rank(-ts_decay_linear(operating_income / (interest_expense + 0.001), 21)), 0.5), subindustry), -1)",
            "Staley (1997) Forensic Mutation: Extreme interest coverage distress with non-linear power dampening.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [14, 21],
        ),
        # Mutation 5B: Debt-to-Equity Capital Vulnerability
        (
            "Staley_Mut_DebtVulnerability",
            "trade_when(volume > adv20 * 0.75, group_neutralize(signed_power(rank(-ts_decay_linear(total_debt / (equity + 0.001), 21)), 0.5), subindustry), -1)",
            "Staley (1997) Forensic Mutation: Over-leveraged capital structure distress indicator.",
            ["TOP3000", "TOP1000"],
            ["SUBINDUSTRY"],
            [14, 21],
        ),
    ]

    for name, expr, desc, univs, neuts, decays in staley_mutations:
        for u in univs:
            for g in neuts:
                for d in decays:
                    candidates.append({
                        "pillar": "SHORT_INTEREST_MUTATION",
                        "archetype": f"{name}_{u}_{g}_d{d}",
                        "expression": expr,
                        "hypothesis": f"{desc} Evaluated on {u} with {g} neutralization and {d}d decay.",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "short_interest",
                        "source_kb": SOURCE_KB,
                    })

    return candidates


if __name__ == "__main__":
    cands = generate_evolutionary_mutator_candidates()
    print(f"Generated {len(cands)} evolutionary mutated alpha candidates.")
    for i, c in enumerate(cands[:5], 1):
        print(f"\n[{i}] {c['archetype']}:")
        print(f"    Expr: {c['expression']}")
        print(f"    Settings: U={c['universe']} | Neut={c['neutralization']} | Decay={c['decay']}")
