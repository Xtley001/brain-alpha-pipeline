"""
Natenberg, Sinclair, Derman & Bennett — Institutional Volatility Surface & Greeks Treatises
Source KB: docs/kb/options/natenberg_sinclair_derman_bennett_vol_treatise.md

Key Institutional Empirical Findings:
1. Sheldon Natenberg (2015, McGraw-Hill):
   - Higher-order Greeks: Vanna (dDelta/dSigma), Volga/Vomma (dVega/dSigma), Charm (dDelta/dt), Color (dGamma/dt).
   - Forward volatility term-structure carry and calendar arbitrage.
2. Euan Sinclair (2008 & 2010, Wiley):
   - Extreme-value volatility estimators: Parkinson (1980, 5x efficiency), Garman-Klass (1980, 7.4x efficiency),
     Rogers-Satchell (1991, drift-independent), Yang-Zhang (2000, jump-robust).
   - Volatility half-life mean-reversion (15-45 trading days).
   - Whalley-Wilmott optimal no-hedging delta bands.
3. Emanuel Derman & Michael B. Miller (2016, Wiley):
   - Dupire local volatility equation and 2x slope rule: dSigma_L/dK = 2 * dSigma_imp/dK.
   - P&L of delta-hedged option positions driven by dollar gamma * (realized_vol^2 - implied_vol^2).
4. Colin Bennett (2014, Santander / Risk Books):
   - Dispersion trading: implied correlation systematically exceeds realized correlation.
   - Variance swap notional conversion: N_var = N_vega / (2 * sigma_strike).
   - Term structure and skew square root of time link: Skew(T) approx Skew(T0) / sqrt(T / T0).
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/options/natenberg_sinclair_derman_bennett_vol_treatise.md"


def generate_institutional_surface_treatise_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Natenberg (2015), Sinclair (2008, 2010),
    Derman & Miller (2016), and Bennett (2014).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    lookbacks = [10, 20, 60]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Sinclair (2008): Parkinson (1980) Extreme-Value Volatility Anomaly
    # 5x efficiency relative to close-to-close volatility
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for w in [10, 20]:
                catalog.append({
                    "pillar": "PARKINSON_VOL_ANOMALY",
                    "archetype": f"Sinclair_Parkinson_Vol_w{w}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(-ts_mean(power(log(high / low), 2) / (4.0 * log(2.0)), {w})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Sinclair (2008) Chapter 2: Parkinson (1980) extreme-value volatility estimator (5x efficiency) "
                        f"captures low-volatility anomaly. Window {w}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 5,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Sinclair (2008) & Bennett (2014): Garman-Klass (1980) OHLC Variance Risk Premium
    # 7.4x efficiency relative to close-to-close sample variance
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for w in [20, 40]:
                catalog.append({
                    "pillar": "GARMAN_KLASS_VRP",
                    "archetype": f"Sinclair_Garman_Klass_VRP_w{w}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear((iv_atm_30^2) - ts_mean(0.5 * power(log(high / low), 2) - (2.0 * log(2.0) - 1.0) * power(log(close / open), 2), {w}) * 252.0, 10)), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Sinclair (2008) / Bennett (2014): Garman-Klass (1980) OHLC Variance Risk Premium "
                        f"isolating market variance risk premium with 7.4x efficiency. Window {w}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Sinclair (2008): Rogers-Satchell (1991) Drift-Independent Volatility Spread
    # Unbiased in trending/drifting equities
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            for w in [20, 60]:
                catalog.append({
                    "pillar": "ROGERS_SATCHELL_DRIFT_FREE",
                    "archetype": f"Sinclair_Rogers_Satchell_Spread_w{w}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(ts_decay_linear(iv_atm_30 - sqrt(max(ts_mean(log(high / close) * log(high / open) + log(low / close) * log(low / open), {w}), 0.00001)) * sqrt(252.0), 10)), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Sinclair (2008) Chapter 2: Rogers-Satchell (1991) drift-independent volatility spread "
                        f"eliminating upward bias in trending markets. Window {w}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": 10,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Natenberg (2015) & Derman (2016): Vanna Hedging Cross-Sensitivity Proxy
    # Market-maker delta rebalancing due to spot-volatility correlation (dDelta/dSigma)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "VANNA_HEDGING_FLOW",
                    "archetype": f"Natenberg_Vanna_Flow_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(rank(-ts_decay_linear(ts_delta(close, 5) * ts_delta(iv_atm_30, 5) / (close * iv_atm_30 + 0.001), {d})), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Natenberg (2015) Chapter 9 / Derman & Miller (2016): Vanna cross-sensitivity (dDelta/dSigma) "
                        f"inducing market-maker systematic hedging flows. Decay {d}, {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "options",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Natenberg (2015): Forward Volatility Term-Structure Carry
    # Forward volatility sigma_1,2 = sqrt((sigma_2^2 * t2 - sigma_1^2 * t1) / (t2 - t1))
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "FORWARD_VOL_CARRY",
                "archetype": f"Natenberg_Forward_Vol_Carry_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(ts_decay_linear(sqrt(max(iv_atm_60^2 * 60.0 - iv_atm_30^2 * 30.0, 0.0001) / 30.0) - iv_atm_30, 10)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Natenberg (2015) Chapter 20: Forward implied volatility term-structure carry isolating calendar "
                    f"risk premia. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Bennett (2014): Single-Stock Dispersion Relative to Sector Basket
    # Capturing single-stock idiosyncratic volatility premium over index/sector
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "BENNETT_DISPERSION_PREMIUM",
                "archetype": f"Bennett_Dispersion_Spread_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.80, "
                    f"group_neutralize(rank(ts_decay_linear(iv_atm_30 - group_mean(iv_atm_30, 1, {g.lower()}), 10)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Bennett (2014) Chapter 6: Single-stock equity dispersion alpha capturing idiosyncratic implied "
                    f"volatility spread over the sector/index basket. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Derman & Miller (2016): Dollar Gamma Scaled Excess Return Predictor
    # Instantaneous P&L = 0.5 * Gamma * S^2 * (RV^2 - IV^2)
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "DERMAN_DOLLAR_GAMMA_PNL",
                "archetype": f"Derman_Dollar_Gamma_Alpha_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.85, "
                    f"group_neutralize(rank(ts_decay_linear((ts_mean(returns^2, 22) * 252.0 - iv_atm_30^2) / (iv_atm_30 + 0.001), 10)), {g.lower()}), "
                    f"-1)"
                ),
                "hypothesis": (
                    f"Derman & Miller (2016) Chapter 5: Instantaneous delta-hedged P&L alpha scaled by normalized dollar "
                    f"gamma and realized-implied variance differential. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 10,
                "category": "options",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_institutional_surface_treatise_candidates()
    print(f"Generated {len(candidates)} Institutional Volatility Treatise alpha candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
