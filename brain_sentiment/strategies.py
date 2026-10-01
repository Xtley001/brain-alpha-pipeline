"""
Brain Sentiment Strategy Module.
WorldQuant BRAIN Category: 'sentiment' (ValueScore: 8.0 / 10 | Ultra-Low Crowding)
Formulations derived from 15 peer-reviewed papers on PEAD, Analyst Revisions, and Attention Dynamics.
Upgraded with Bivariate Feature Interactions, Sub-Universe Liquidity Armor, and Calibrated Decays (12-16).
"""
from typing import Any, Dict, List


def generate_sentiment_candidates() -> List[Dict[str, Any]]:
    """
    Generate orthogonal candidates across 5 institutional sentiment archetypes:
    1. S1: PEAD Revision Momentum x Volatility Decoupling
    2. S2: Standardized Unexpected Earnings Shock x Price Momentum
    3. S3: Net Target Price Revisions x High-Low Spread
    4. S4: Forecast Dispersion Anomaly x Earnings Revision Direction
    5. S5: Dynamic Attention x Liquidity Armor
    """
    candidates = []
    universes = ["TOP3000", "TOP2000"]
    groups = ["subindustry", "sector"]
    decays = [12, 14, 16]

    for u in universes:
        for g in groups:
            for d in decays:
                # -------------------------------------------------------------
                # S1: PEAD Revision Momentum x Price Reversal (Bivariate Interaction)
                # Field: snt1_d1_netearningsrevision
                # -------------------------------------------------------------
                expr_s1_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * "
                    f"rank(-ts_delta(close, 5)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s1_bivariate,
                    "family": "Sent_PEAD_Bivariate_Momentum",
                    "archetype": f"Sent_PEAD_Bivar_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Analyst earnings revisions combined with 5d price reversal filters out stale consensus revisions.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_pead_bivariate_momentum",
                })

                # S1 Variant B: High-Conviction Threshold Filter with Sub-Universe Armor
                expr_s1_gated = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"trade_when(abs(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) - 0.5) > 0.25, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), {g}), -1), -1)"
                )
                candidates.append({
                    "expression": expr_s1_gated,
                    "family": "Sent_PEAD_Gated",
                    "archetype": f"Sent_PEAD_Gated_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Liquidity-armored high-conviction analyst revisions ({d}d decay) capture persistent drift.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_pead_gated",
                })

                # -------------------------------------------------------------
                # S2: Standardized Unexpected Earnings Shock x Volatility Spread
                # Field: snt1_d1_earningssurprise
                # -------------------------------------------------------------
                expr_s2_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})) * "
                    f"rank(-ts_delta(close, 3) / (ts_std_dev(close, 20) + 0.001)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s2_bivariate,
                    "family": "Sent_SUE_Volatility_Bivariate",
                    "archetype": f"Sent_SUE_Bivar_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Earnings surprise scaled by volatility-adjusted price change isolates fundamental earnings momentum.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_sue_volatility_bivariate",
                })

                # -------------------------------------------------------------
                # S3: Net Target Price Revisions x High-Low Intraday Spread
                # Field: snt1_d1_nettargetpercent
                # -------------------------------------------------------------
                expr_s3_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) * "
                    f"rank((high - low) / (close + 0.001)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s3_bivariate,
                    "family": "Sent_Target_Spread_Bivariate",
                    "archetype": f"Sent_Target_Spread_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Price target revision velocity interacting with intraday volatility spread predicts continuation.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_target_spread_bivariate",
                })

                # S3 Variant B: Dual Target and Recommendation Upgrades
                expr_s3_dual = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(0.60 * rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) + "
                    f"0.40 * rank(ts_decay_linear(snt1_d1_netrecpercent, {d}))), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s3_dual,
                    "family": "Sent_Dual_Alignment_Armor",
                    "archetype": f"Sent_Dual_Armor_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Confluence of target price raises and recommendation upgrades with liquidity armor.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_target_rec_confluence_armor",
                })

                # -------------------------------------------------------------
                # S4: Forecast Dispersion Anomaly x Net Revision Interaction
                # Field: snt1_d1_dtstsespe, snt1_d1_netearningsrevision
                # -------------------------------------------------------------
                expr_s4_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(- ts_decay_linear(snt1_d1_dtstsespe / (close + 0.001), {d})) * "
                    f"rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s4_bivariate,
                    "family": "Sent_Dispersion_Revision_Bivariate",
                    "archetype": f"Sent_Disp_Rev_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Low forecast dispersion combined with upward net revision momentum maximizes information ratio.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_dispersion_revision_bivariate",
                })

                # -------------------------------------------------------------
                # S5: Dynamic Analyst Focus x Price Acceleration
                # Field: snt1_d1_dynamicfocusrank
                # -------------------------------------------------------------
                expr_s5_bivariate = (
                    f"trade_when(volume > adv20 * 0.8, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_dynamicfocusrank, {d})) * "
                    f"rank(ts_decay_linear(-ts_zscore(close, 10), 5)), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s5_bivariate,
                    "family": "Sent_Focus_Momentum_Armor",
                    "archetype": f"Sent_Focus_Mom_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Dynamic institutional analyst focus interacting with mean-reverting price z-score.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_focus_momentum_armor",
                })

    return candidates
