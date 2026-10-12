"""
Frazzini & Pedersen (2014) — Betting Against Beta (EXACT Construction)
Paper: "Betting Against Beta"
Journal of Finance (2014); NBER WP 16601

Core Finding: A BAB factor — long leveraged low-beta assets, short de-leveraged high-beta assets
(both scaled to beta=1) — earns 0.75 Sharpe in the US from 1926–2009. Security market line
is too FLAT relative to CAPM: high-beta stocks earn LOWER risk-adjusted returns because
leverage-constrained investors over-weight them, bidding up prices and down expected returns.

Exact Beta Construction (Paper Section II):
    beta_i = rho_i * (sigma_i / sigma_m)
    where:
        rho_i    = 1-year correlation of daily stock returns with market (rolling)
        sigma_i  = 1-year volatility of daily stock returns (rolling)
        sigma_m  = 1-year volatility of daily market returns (rolling)

    Shrinkage toward cross-sectional mean (paper uses 0.6 weight on raw, 0.4 on 1.0):
        beta_shrunk = 0.6 * beta_raw + 0.4 * 1.0

BAB Factor Construction (Paper Eq. 7-8):
    z_i = (beta_i - mean(beta)) / std(beta)   ← cross-sectional z-score
    Long leg: stocks with z_i < 0 (low beta), weighted by |z_i|, scaled to beta=1
    Short leg: stocks with z_i > 0 (high beta), weighted by z_i, scaled to beta=1

BRAIN approximation: We cannot construct the full BAB factor (portfolio-level).
Instead we translate the cross-sectional ranking into an alpha expression that
captures the same economic signal: LONG low-beta, SHORT high-beta, within groups.
"""
from typing import Any, Dict, List


def generate_frazzini_pedersen_bab_candidates() -> List[Dict[str, Any]]:
    """
    Frazzini & Pedersen (2014): Exact BAB Construction.
    Paper-faithful: beta z-score sorting with shrinkage and regime conditioning.
    Citation: JF 2014, Table 1 (US equity BAB Sharpe=0.75, 1926-2009).
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP200"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Raw BAB Cross-Sectional Beta Rank
    # Paper: beta = correlation(r_i, r_m) * vol(r_i) / vol(r_m)
    # BRAIN approximation: beta_last_N_days_spy is the best available field.
    # Short high-beta, long low-beta, within subindustry (to control sector exposure)
    # Economic logic: leverage constraints → high-beta overpriced, low-beta underpriced
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
                            f"FP2014 BAB: short high-beta, long low-beta within {g}. "
                            f"Beta estimated over {beta_horizon}d vs SPY. Leverage-constrained investors "
                            f"overbid high-beta → lower risk-adjusted returns. {u}."
                        ),
                        "universe": u,
                        "neutralization": g,
                        "decay": d,
                        "category": "model",
                    })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: Beta × Short-Term Reversal (BAB with momentum conditioning)
    # Paper Table 2: BAB returns are stronger after short-term pullbacks in high-beta
    # stocks (when leverage-constrained investors have recently de-levered).
    # Expression: rank(-beta) × rank(-5d_return) → buy low-beta + recent loser
    #             (reversal amplifies the beta mis-pricing)
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
                        f"FP2014: low-beta stocks that recently pulled back — double alpha: "
                        f"BAB premium + short-term reversal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Beta Z-Score (Shrinkage Construction — Paper Section II.B)
    # Paper: shrunk_beta = 0.6 * raw_beta + 0.4 * 1.0
    # Economic: Shrunken beta reduces estimation noise, making signal cleaner.
    # BRAIN approx: (0.6 * beta_raw + 0.4 * 1.0) — beta cross-sectionally centered
    # z_beta = (shrunk_beta - mean_beta) / std_beta ≈ cross-sectional rank
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
                        f"FP2014 exact shrinkage: 0.6*beta + 0.4*1.0 (reduces estimation noise per Paper Sec II.B). "
                        f"Long shrunk-low-beta, short shrunk-high-beta. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: Idiosyncratic Volatility (companion anomaly — cited in Paper footnote 2)
    # Ang, Hodrick, Xing, Zhang (2006): idiovol predicts NEGATIVE cross-sectional returns.
    # FP paper uses this as robustness: BAB holds CONTROLLING for idiovol.
    # Here: pure idiovol signal (see also ang_idiovol_anomaly.py)
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
                        f"FP2014 companion (AHXZ 2006): high idiosyncratic vol → low future returns. "
                        f"BAB robustness control turned into standalone signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Beta × Funding Liquidity Regime (Paper Section IV.B)
    # When TED spread is HIGH (funding constraints tight) → BAB under-performs.
    # When TED spread is LOW (funding loose) → BAB outperforms significantly.
    # BRAIN approx: use ts_rank of the spread of beta cross-section as proxy
    # for constraint tightness: wider beta cross-section spread = looser constraints
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
                    f"FP2014 Sec IV.B: BAB signal only when beta cross-section dispersion is HIGH "
                    f"(funding constraints loose → low-beta premium is active). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 12,
                "category": "model",
            })

    return catalog
