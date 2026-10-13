"""
Systematic Risk & Factor Models Strategy Generator.
WorldQuant BRAIN Category: 'model' (ValueScore: 8.0 / 10 | Low Crowding)
Derived from: Frazzini & Pedersen (2014), Ang et al. (2006), Baker et al. (2011), Blitz & van Vliet (2007).
"""
from typing import Any, Dict, List


SOURCE_KB_BAB = "docs/kb/risk_models/frazzini_pedersen_2014_bab.md"
SOURCE_KB_AHXZ = "docs/kb/risk_models/ahxz_2006_idiovol_and_derivatives.md"


def generate_risk_model_vault_candidates() -> List[Dict[str, Any]]:
    """Generates 100+ systematic risk and factor model candidates."""
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP200", "TOP1000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR"]
    decays = [10, 14, 18]

    for u in universes:
        for g in neut_groups:
            for d in decays:
                # 1. Betting Against Beta (BAB) x Short-Term Reversal Armor
                for b_horizon in [60, 90]:
                    beta_field = f"beta_last_{b_horizon}_days_spy"
                    catalog.append({
                        "pillar": "RISK_BAB_REVERSAL",
                        "archetype": f"Risk_BAB_Rev_{b_horizon}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear({beta_field}, {d})) - 0.5) > 0.25, "
                            f"group_neutralize(rank(- ts_decay_linear({beta_field}, {d})) * rank(- ts_delta(close, 5)), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": f"Low-beta stocks ({b_horizon}d) conditioned on short-term price pullbacks ({u}).",
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                        "source_kb": SOURCE_KB_BAB,
                    })

                # 2. Idiosyncratic Volatility Anomaly (Ang et al. 2006)
                catalog.append({
                    "pillar": "RISK_IDIO_VOL",
                    "archetype": f"Risk_IdioVol_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(rank(- ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": f"Idiosyncratic volatility anomaly with RL tail gating ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB_AHXZ,
                })

                # 3. Market Beta & Correlation Decoupling
                catalog.append({
                    "pillar": "RISK_CORR_DECOUPLING",
                    "archetype": f"Risk_CorrDecouple_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize(rank(- 0.60 * rank(ts_decay_linear(beta_last_60_days_spy, {d})) - 0.40 * rank(ts_decay_linear(correlation_last_60_days_spy, {d}))), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": f"Systematic market beta and correlation decoupling engine ({u}).",
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB_AHXZ,
                })

    return catalog
