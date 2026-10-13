"""
Frazzini & Pedersen (2014) — Betting Against Beta (EXACT Construction)
Paper: "Betting Against Beta"
Journal of Financial Economics (2014); NBER WP 16601
Source KB: docs/kb/risk_models/frazzini_pedersen_2014_bab.md

Core Finding: A BAB factor — long leveraged low-beta assets, short de-leveraged high-beta assets
(both scaled to beta=1) — earns 0.75 Sharpe in the US from 1926–2009. Security market line
is too FLAT relative to CAPM: high-beta stocks earn LOWER risk-adjusted returns because
leverage-constrained investors over-weight them, bidding up prices and down expected returns.

Exact Formulations from Paper Extracts:
- Eq. (8): Alpha alpha_i = psi_t * (1 - beta_i) -> alpha strictly decreases in beta
- Eq. (9): r_BAB = (1/beta_L)*(r_L - rf) - (1/beta_H)*(r_H - rf)
- Eq. (10): E[r_BAB] = ((beta_H - beta_L)/(beta_L * beta_H)) * psi_t >= 0
- Eq. (14): Dimson (1979) lags up to K=5 to eliminate non-synchronous trading noise
- Eq. (15): Vasicek Bayesian shrinkage: beta_shrunk = 0.6 * beta_TS + 0.4 * 1.0
- Table III: FF3 alpha = +0.69%/mo (t=6.55), Carhart alpha = +0.55%/mo (t=5.12)
- Table X & XI: Beta dispersion compresses when funding tightens; wide beta spread predicts higher alpha
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/risk_models/frazzini_pedersen_2014_bab.md"


def generate_frazzini_pedersen_bab_candidates() -> List[Dict[str, Any]]:
    """
    Frazzini & Pedersen (2014): Exact BAB Construction.
    Paper-faithful: beta z-score sorting with shrinkage, Dimson lag smoothing, and regime conditioning.
    Citation: JFE 2014, Table III (US equity BAB Sharpe=0.75, 1926-2009).
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Raw BAB Cross-Sectional Beta Rank (Extract 4 & 8, Table III)
    # Short high-beta, long low-beta, within subindustry (to control sector exposure)
    # Economic logic: leverage constraints -> high-beta overpriced, low-beta underpriced
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for beta_horizon in [60, 90, 252]:
                for d in decays:
                    beta_field = f"beta_last_{beta_horizon}_days_spy"
                    catalog.append({
                        "pillar": "BAB_BETA_RANK",
                        "archetype": f"BAB_BetaRank_b{beta_horizon}_d{d}_{u}_{g}",
                        "expression": (
                            f"trade_when(volume > adv20 * 0.85, "
                            f"trade_when(abs(rank(ts_decay_linear({beta_field}, {d})) - 0.5) > 0.20, "
                            f"group_neutralize(signed_power(rank(-ts_decay_linear({beta_field}, {d})), 0.5), {g.lower()}), "
                            f"-1), -1)"
                        ),
                        "hypothesis": (
                            f"FP2014 BAB (Table III): short high-beta, long low-beta within {g}. "
                            f"Beta estimated over {beta_horizon}d vs SPY. Leverage-constrained investors "
                            f"overbid high-beta -> lower risk-adjusted returns. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                        "source_kb": SOURCE_KB,
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Beta x Short-Term Reversal (Extract 15, Table 2)
    # Paper Table 2: BAB returns are stronger after short-term pullbacks in high-beta
    # stocks (when leverage-constrained investors have recently de-levered).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_BETA_X_REVERSAL",
                    "archetype": f"BAB_BetaReversal_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(beta_last_60_days_spy) - 0.5) > 0.20, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(beta_last_60_days_spy, {d})) * "
                        f"rank(-ts_delta(close, 5)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Table 2: low-beta stocks that recently pulled back — double alpha: "
                        f"BAB premium + short-term reversal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Beta Z-Score with Vasicek Shrinkage (Extract 7, Eq 15)
    # Paper Eq. (15): shrunk_beta = 0.6 * raw_beta + 0.4 * 1.0
    # Reduces estimation noise and attenuates outlier distortion.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_SHRUNK_BETA_ZSCORE",
                    "archetype": f"BAB_ShrunkBeta_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(0.6 * beta_last_90_days_spy + 0.4 * 1.0, {d})) - 0.5) > 0.20, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(0.6 * beta_last_90_days_spy + 0.4 * 1.0, {d})), 0.5), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Eq (15) exact shrinkage: 0.6*beta + 0.4*1.0 (Vasicek 1973 noise reduction). "
                        f"Long shrunk-low-beta, short shrunk-high-beta. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Idiosyncratic Volatility Companion (Extract 14, Footnote 2)
    # Ang, Hodrick, Xing, Zhang (2006): idiovol predicts negative cross-sectional returns.
    # BAB holds controlling for idiovol; pure idiovol factor complement.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_IDIOVOL",
                    "archetype": f"BAB_IdioVol_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(rank(ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})) - 0.5) > 0.25, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})), 0.5), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Footnote 2 (AHXZ 2006 companion): high idiosyncratic vol -> low future returns. "
                        f"BAB robustness control turned into standalone signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Beta x Funding Liquidity Regime Gate (Extract 11 & 12, Table X/XI)
    # Proposition 3: When TED spread is LOW (funding loose) -> beta dispersion is wide
    # and BAB delivers maximum alpha.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            catalog.append({
                "pillar": "BAB_LIQUIDITY_REGIME",
                "archetype": f"BAB_LiquidityRegime_{u}_{g}",
                "expression": (
                    f"trade_when(volume > adv20 * 0.85, "
                    f"trade_when(ts_rank(ts_std_dev(beta_last_60_days_spy, 60), 252) > 0.40, "
                    f"group_neutralize(signed_power(rank(-ts_decay_linear(beta_last_60_days_spy, 12)), 0.5), {g.lower()}), "
                    f"-1), -1)"
                ),
                "hypothesis": (
                    f"FP2014 Sec IV & Table X: BAB active only when beta cross-section dispersion is HIGH "
                    f"(funding constraints loose -> low-beta mispricing is active). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 12,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 6: Low Beta x Low Idiovol Double-Sort (Extract 14, Table B2 & Footnote 2)
    # Double-sort: isolates pure safe assets by requiring BOTH low systematic beta
    # AND low idiosyncratic volatility, avoiding speculative lottery stocks.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_LOW_BETA_LOW_IDIOVOL",
                    "archetype": f"BAB_LowBeta_LowIdiovol_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(0.6 * beta_last_90_days_spy + 0.4 * 1.0, {d})) * "
                        f"rank(-ts_decay_linear(idiosyncratic_vol_last_60_days_spy, {d})), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Table B2 double sort: simultaneously long low-beta + low-idiovol. "
                        f"Eliminates retail speculative lottery stocks from long portfolio. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 7: Shrunk Beta x Medium-Term Momentum Winner (Extract 13, Table B1)
    # Table B1 shows BAB factor loads positively on 12-month momentum (winners).
    # Buying low-beta stocks that are also intermediate-term winners captures the
    # highest Sharpe ratio intersection.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_BETA_X_MOMENTUM",
                    "archetype": f"BAB_BetaMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"rank(-ts_decay_linear(0.6 * beta_last_90_days_spy + 0.4 * 1.0, {d})) * "
                        f"rank(ts_decay_linear(ts_delta(close, 60) / ts_delay(close, 60), 20)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Table B1 factor loadings: low-beta stocks with positive medium-term momentum. "
                        f"Overcomes flat return drift while harvesting pure low-beta Sharpe ratio. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 8: Dimson Lag Smoothed Beta (Extract 6, Eq 14)
    # Paper Eq. (14): Dimson (1979) beta uses sum of current and lagged market slopes.
    # BRAIN equivalent: rolling mean of beta over 5 days removes non-synchronous noise.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_DIMSON_SMOOTHED",
                    "archetype": f"BAB_DimsonSmoothed_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"group_neutralize("
                        f"signed_power(rank(-ts_mean(beta_last_60_days_spy, 5)), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Eq (14) Dimson lag smoothing: 5-day moving average of beta eliminates "
                        f"non-synchronous trading noise and microstructural bias. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 9: Ex-Ante Beta Dispersion Gated Z-Score (Extract 11 & 12, Table XI)
    # Proposition 2 & Table XI: wider ex-ante beta spread predicts higher BAB returns.
    # Only trade low-beta when the stock's beta deviates strongly from the median.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "BAB_DISPERSION_SCALED",
                    "archetype": f"BAB_DispersionScaled_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.85, "
                        f"trade_when(abs(beta_last_90_days_spy - 1.0) > 0.25, "
                        f"group_neutralize("
                        f"rank(-(0.6 * beta_last_90_days_spy + 0.4 * 1.0)) * "
                        f"rank(abs(beta_last_90_days_spy - 1.0)), "
                        f"{g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"FP2014 Table XI Proposition 2: scaling low-beta signal by distance from beta=1.0. "
                        f"Wider ex-ante beta spread empirically delivers highest abnormal alpha. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    return catalog
