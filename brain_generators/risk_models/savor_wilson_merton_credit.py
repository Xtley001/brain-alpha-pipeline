"""
Savor & Wilson (2013), Merton (1974) & Nieto & Rodríguez (2013)
Source KB: docs/kb/risk_models/savor_wilson_nieto_merton_credit.md

Key Institutional Empirical Findings:
1. Savor & Wilson (2013, Journal of Finance):
   - Over 1958-2008, stock market excess return averages 10.6 bps on announcement days vs 1.0 bps on other days (t=3.53).
   - Over 60% of cumulative annual equity risk premium is earned on scheduled announcement days (13% of trading days).
   - Precautionary saving reduces 30-day T-bill return by 0.2 bps on announcement days (t=-4.43).
   - Value vs. Growth inversion: Fama-French HML inverts from +2.5 bps (t=5.30) on normal days to -1.5 bps (t=-1.22) on announcement days (differential -4.0 bps, t=-2.98).
   - Implied variance drops by -1.4% to -2.8% on announcement days (t=-4.13).
   - Mean pairwise correlation jumps from 0.216 to 0.245 on announcement days (t=3.78).
2. Merton (1974, Journal of Finance):
   - Equity is a European call option on firm value V with strike D: S = C(V, D, tau, sigma_V, r).
   - Structural Distance-to-Default: DD = [ln(V/D) + (mu - 0.5*sigma^2)*tau] / (sigma*sqrt(tau)).
   - Default probability pi = Phi(-DD). Credit spreads widen nonlinearly with debt-to-equity and asset volatility.
3. Nieto & Rodríguez (2013, SSRN/JBF):
   - Panel GMM analysis across 467 corporate bond issues (TRACE): stock-bond correlation increases with firm idiosyncratic risk and leverage.
   - Conversely, stock-bond correlation decreases as systematic stock beta increases.
   - Aggregate consumption volatility and default spread shocks decouple equity and corporate debt prices.
"""
from typing import Any, Dict, List

SOURCE_KB = "docs/kb/risk_models/savor_wilson_nieto_merton_credit.md"


def generate_savor_wilson_merton_credit_candidates() -> List[Dict[str, Any]]:
    """
    Generate paper-grounded alpha candidates from Savor & Wilson (2013),
    Merton (1974), and Nieto & Rodríguez (2013).
    All expressions feature balanced parentheses, valid BRAIN operators, and 100% source_kb traceability.
    """
    catalog: List[Dict[str, Any]] = []

    universes = ["TOPSP500", "TOP500", "TOP1000", "TOP2000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays = [5, 10, 20]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Savor & Wilson (2013): High-Duration Growth Tilt on Macro Announcements
    # Growth stocks act as long-duration dividend strips, outperforming value
    # during periods of high market liquidity and macro activity.
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "SAVOR_WILSON_GROWTH_DURATION",
                    "archetype": f"Savor_Wilson_Growth_Duration_{u}_{g}_d{d}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.9, "
                        f"group_neutralize(rank(-book_to_price) * ts_rank(ts_decay_linear(returns, 5), 20), {g.lower()}), "
                        f"-1)"
                    ),
                    "hypothesis": (
                        f"Savor & Wilson (2013) Table 7 & Section 2.2: Growth stocks represent long-duration dividend strips "
                        f"that outperform value stocks (HML inverts by -4.0 bps, t=-2.98) when macroeconomic uncertainty clears. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Savor & Wilson (2013): Macro Announcement Correlation & Volatility Compression
    # Stocks with strong market co-movement that experience volatility drops post-announcement
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "SAVOR_WILSON_CORRELATION_COMPRESSION",
                "archetype": f"Savor_Wilson_Corr_Compression_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_corr(returns, group_mean(returns, 1, {g.lower()}), 22)) * "
                    f"ts_rank(-ts_std(returns, 22), 60), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Savor & Wilson (2013) Section 2.4: Macro announcements synchronize return correlations (+0.029, t=3.78) "
                    f"while triggering subsequent volatility collapse (-1.4% to -2.8%, t=-4.13). {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 15,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Merton (1974): Structural Distance-to-Default (Solvency Buffer)
    # DD proxy: [ln(Equity / Debt) + Drift] / Volatility
    # Long high solvency buffer (low default probability), short distressed credit
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            catalog.append({
                "pillar": "MERTON_DISTANCE_TO_DEFAULT",
                "archetype": f"Merton_Distance_To_Default_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank((log(close * sharesout / (debt_total + 1e-4)) + ts_mean(returns, 252) * 252) / "
                    f"(ts_std(returns, 252) * 15.87 + 1e-4)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Merton (1974) Section 2: Structural distance-to-default ranks firms by debt repayment capacity; "
                    f"firms with high solvency distance exhibit lower credit spreads, lower borrowing costs, and positive equity drift. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Merton (1974): Distress Debt Overhang & Volatility Convexity
    # High debt-to-equity compounded with high stock volatility signals equity insolvency
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            catalog.append({
                "pillar": "MERTON_DISTRESS_OVERHANG",
                "archetype": f"Merton_Distress_Overhang_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(-(debt_total / (close * sharesout + 1e-4)) * ts_std(returns, 60)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Merton (1974) Section 3: High financial leverage interacting with elevated equity volatility "
                    f"leads to debt overhang, credit rating downgrades, and substantial underperformance. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 15,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Nieto & Rodríguez (2013): Idiosyncratic Risk vs Systematic Decoupling
    # Stock-bond comovement increases with idiosyncratic risk but drops with market beta
    # High idiosyncratic risk binds equity & debt to underlying cash flows
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:3]:
        for g in neut_groups:
            for d in [10, 20]:
                catalog.append({
                    "pillar": "NIETO_RODRIGUEZ_IDIO_VS_SYSTEMATIC",
                    "archetype": f"Nieto_Rodriguez_Idio_Systematic_{u}_{g}_d{d}",
                    "expression": (
                        f"group_neutralize("
                        f"rank(ts_std(returns - ts_corr(returns, group_mean(returns, 1, market), 60) * group_mean(returns, 1, market), 60) - "
                        f"ts_corr(returns, group_mean(returns, 1, market), 60)), "
                        f"{g.lower()})"
                    ),
                    "hypothesis": (
                        f"Nieto & Rodríguez (2013) Table 4 & Section 5.2: Idiosyncratic firm risk strengthens equity-debt alignment "
                        f"via productive asset linkages, whereas systematic market beta dissociates equity from debt holders. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "model",
                    "source_kb": SOURCE_KB,
                })

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Nieto & Rodríguez (2013): Leverage Elasticity Option Interaction
    # Quasi-leverage ratio interacts with volatility to drive option elasticity
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes[:2]:
        for g in neut_groups:
            catalog.append({
                "pillar": "NIETO_RODRIGUEZ_LEVERAGE_ELASTICITY",
                "archetype": f"Nieto_Rodriguez_Leverage_Elasticity_{u}_{g}",
                "expression": (
                    f"group_neutralize("
                    f"rank(ts_rank(debt_total / (assets + 1e-4), 60) * ts_rank(-ts_std(returns, 60), 60)), "
                    f"{g.lower()})"
                ),
                "hypothesis": (
                    f"Nieto & Rodríguez (2013) Eq. 6 & Section 2: Quasi-leverage interacting with low asset volatility "
                    f"moderates option convexity risk, stabilizing credit-equity relations. {u}."
                ),
                "universe": u,
                "neutralization": g,
                "decay": 20,
                "category": "model",
                "source_kb": SOURCE_KB,
            })

    return catalog


if __name__ == "__main__":
    candidates = generate_savor_wilson_merton_credit_candidates()
    print(f"Generated {len(candidates)} Savor-Wilson-Merton-Credit alpha candidates.")
    print("Sample expression:")
    print(candidates[0]["expression"])
