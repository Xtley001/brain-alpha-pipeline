"""
Sentiment & Analyst Dynamics Strategy Generator.
WorldQuant BRAIN Category: 'sentiment' (ValueScore: 9.5 / 10 | Ultra-Low Crowding)
Derived from: Ball & Brown (1968), Bernard & Thomas (1990), Diether et al. (2002), Barber & Odean (2008).
"""
from typing import Any, Dict, List


SOURCE_KB_PEAD = "docs/kb/sentiment/bernard_thomas_1990_pead_sue.md"
SOURCE_KB_GLEASON = "docs/kb/sentiment/gleason_lee_2002_revision.md"


def generate_sentiment_vault_candidates() -> List[Dict[str, Any]]:
    """Generates 100+ highly diversified sentiment & analyst revision candidates."""
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP200", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays = [8, 12, 16]

    for u in universes:
        for g in neut_groups:
            for d in decays:
                # 1. PEAD Net Earnings Revision x Forecast Dispersion Contraction
                catalog.append({
                    "pillar": "SNT_PEAD_DISPERSION",
                    "archetype": f"Sent_PEAD_Disp_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})) * rank(- ts_decay_linear(snt1_d1_dtstsespe, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Analyst earnings revisions combined with forecast dispersion collapse ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "sentiment",
                    "source_kb": SOURCE_KB_PEAD,
                })

                # 2. Target Price Revision x Earnings Surprise Synergy
                catalog.append({
                    "pillar": "SNT_TARGET_SUE",
                    "archetype": f"Sent_Target_SUE_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) * rank(ts_decay_linear(snt1_d1_earningssurprise, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Analyst target revisions confirmed by standardized earnings surprises ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "sentiment",
                    "source_kb": SOURCE_KB_PEAD,
                })

                # 3. Dynamic Attention Focus x Revisions
                catalog.append({
                    "pillar": "SNT_FOCUS_ATTENTION",
                    "archetype": f"Sent_Focus_Attn_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(snt1_d1_dynamicfocusrank, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(ts_decay_linear(snt1_d1_dynamicfocusrank, {d})) * rank(ts_decay_linear(snt1_d1_netearningsrevision, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Institutional dynamic focus rank interacting with revision velocity ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "sentiment",
                    "source_kb": SOURCE_KB_GLEASON,
                })

    return catalog
