"""
Brain Sentiment Strategy Module.
WorldQuant BRAIN Category: 'sentiment' (ValueScore: 8.0 / 10 | Ultra-Low Crowding)
Formulations derived from 15 peer-reviewed papers on PEAD, Analyst Revisions, and Attention Dynamics.
"""
from typing import Any, Dict, List


def generate_sentiment_candidates() -> List[Dict[str, Any]]:
    """
    Generate orthogonal candidates across 5 institutional sentiment archetypes:
    1. S1: PEAD Revision Momentum (Chan, Jegadeesh, Lakonishok 1996)
    2. S2: Standardized Unexpected Earnings Shock (Bernard & Thomas 1989, 1990)
    3. S3: Net Target Price Revisions (Brav & Lehavy 2003, Givoly & Lakonishok 1979)
    4. S4: Forecast Dispersion Anomaly (Diether, Malloy, Scherbina 2002)
    5. S5: Dynamic Attention & Mood Index (Da, Engelberg, Gao 2011, Baker & Wurgler 2006)
    """
    candidates = []
    universes = ["TOP3000", "TOP2000"]
    groups = ["subindustry", "sector"]
    decays = [10, 12, 15]

    for u in universes:
        for g in groups:
            for d in decays:
                # -------------------------------------------------------------
                # S1: PEAD Revision Momentum (Chan, Jegadeesh, & Lakonishok 1996)
                # Field: snt1_d1_netearningsrevision
                # -------------------------------------------------------------
                # Variant A: Pure Rank Smoothing
                expr_s1a = f"group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), {g})"
                candidates.append({
                    "expression": expr_s1a,
                    "family": "Sent_PEAD_Rev",
                    "archetype": f"Sent_PEAD_Rev_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Sluggish analyst earnings revisions ({d}d decay) create persistent post-announcement drift.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_pead_revision_momentum",
                })

                # Variant B: Selective Filtered Revision
                expr_s1b = (
                    f"trade_when(abs(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) - 0.5) > 0.20, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s1b,
                    "family": "Sent_PEAD_Filter",
                    "archetype": f"Sent_PEAD_Filter_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Selective high-conviction analyst revisions ({d}d) capture institutional tail revisions.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_pead_revision_filtered",
                })

                # -------------------------------------------------------------
                # S2: Standardized Unexpected Earnings Shock (Bernard & Thomas 1989, 1990)
                # Field: snt1_d1_earningssurprise
                # -------------------------------------------------------------
                expr_s2a = f"group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})), {g})"
                candidates.append({
                    "expression": expr_s2a,
                    "family": "Sent_SUE_Surprise",
                    "archetype": f"Sent_SUE_Surprise_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Reported earnings surprises relative to consensus consensus generate 60-day delayed drift.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_sue_earnings_surprise",
                })

                expr_s2b = (
                    f"trade_when(abs(snt1_d1_earningssurprise) > 0.05, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s2b,
                    "family": "Sent_SUE_Threshold",
                    "archetype": f"Sent_SUE_Threshold_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Material earnings surprise shocks (>5% SUE) filter out noise and isolate fundamental re-ratings.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_sue_threshold_shock",
                })

                # -------------------------------------------------------------
                # S3: Net Target Price Revisions (Brav & Lehavy 2003, Givoly & Lakonishok 1979)
                # Field: snt1_d1_nettargetpercent
                # -------------------------------------------------------------
                expr_s3a = f"group_neutralize(rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})), {g})"
                candidates.append({
                    "expression": expr_s3a,
                    "family": "Sent_Target_Drift",
                    "archetype": f"Sent_Target_Drift_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Net analyst price target revisions ({d}d decay) predict equity return continuation.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_target_price_revisions",
                })

                expr_s3b = (
                    f"group_neutralize(rank(0.55 * rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) + "
                    f"0.45 * rank(ts_decay_linear(snt1_d1_netrecpercent, {d}))), {g})"
                )
                candidates.append({
                    "expression": expr_s3b,
                    "family": "Sent_Dual_Alignment",
                    "archetype": f"Sent_Dual_Align_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Confluence of target price raises and recommendation upgrades (Asquith et al. 2005).",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_target_rec_confluence",
                })

                # -------------------------------------------------------------
                # S4: Forecast Dispersion Anomaly (Diether, Malloy, & Scherbina 2002)
                # Field: snt1_d1_dtstsespe (Standard Deviation of EPS estimates)
                # -------------------------------------------------------------
                expr_s4a = f"group_neutralize(rank(- ts_decay_linear(snt1_d1_dtstsespe / (close + 0.001), {d})), {g})"
                candidates.append({
                    "expression": expr_s4a,
                    "family": "Sent_Dispersion_Discount",
                    "archetype": f"Sent_Dispersion_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"High analyst earnings forecast dispersion reflects overvaluation due to short-sale constraints.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_forecast_dispersion",
                })

                # -------------------------------------------------------------
                # S5: Dynamic Attention & Mood Index (Da et al. 2011, Baker & Wurgler 2006)
                # Fields: snt1_d1_dynamicfocusrank, daily_equity_mood_indicator
                # -------------------------------------------------------------
                expr_s5a = (
                    f"trade_when(volume > adv20 * 0.85, "
                    f"group_neutralize(rank(ts_decay_linear(snt1_d1_dynamicfocusrank, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s5a,
                    "family": "Sent_Dynamic_Focus",
                    "archetype": f"Sent_DynFocus_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Volume-confirmed dynamic analyst focus isolates high-conviction institutional coverage.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_dynamic_analyst_focus",
                })

                expr_s5b = (
                    f"trade_when(abs(daily_equity_mood_indicator - 50.0) > 20.0, "
                    f"group_neutralize(rank(- ts_decay_linear(daily_equity_mood_indicator - 50.0, {d})), {g}), -1)"
                )
                candidates.append({
                    "expression": expr_s5b,
                    "family": "Sent_Mood_Contrarian",
                    "archetype": f"Sent_MoodContr_d{d}_{u}_{g.upper()}",
                    "hypothesis": f"Fading extreme market equity mood waves monetizes behavioral retail sentiment overreaction.",
                    "universe": u,
                    "neutralization": g.upper(),
                    "decay": d,
                    "category": "sentiment",
                    "strategy": "snt_mood_contrarian",
                })

    return candidates
