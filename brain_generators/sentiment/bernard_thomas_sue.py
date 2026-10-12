"""
Bernard & Thomas (1990) + Chan, Jegadeesh & Lakonishok (1996) — SUE & PEAD Generators
Papers:
  1. Bernard & Thomas (1990): "Evidence That Stock Prices Do Not Fully Reflect the
     Implications of Current Earnings for Future Earnings" — JAE
  2. Chan, Jegadeesh & Lakonishok (1996): "Momentum Strategies" — JF

Core Finding (BT 1990):
    Stock prices systematically UNDER-REACT to earnings surprises. The drift continues
    for at least 6 months post-announcement. The sign and magnitude of the drift is
    related to the autocorrelation structure of seasonal earnings — markets act as if
    earnings follow a seasonal random walk when they don't.

    Estimated annualized abnormal return: 18% (pre-costs) in first quarter post-announcement.

Standardized Unexpected Earnings (SUE) Formula (Bernard & Thomas, p. 308):
    UE_{i,q} = EPS_{i,q} - EPS_{i,q-4}          ← seasonal change
    SUE_{i,q} = UE_{i,q} / σ(UE_{i,q}, last 8 quarters)

Chan-Jegadeesh-Lakonishok (1996) Extension:
    - SUE6: 6-month momentum from earnings surprise (quarterly SUE × price momentum)
    - Revision signal: sum of analyst estimate revisions over past 6 months / price
    - Combined: SUE-based momentum + price momentum = dual confirmation
"""
from typing import Any, Dict, List


def generate_bernard_thomas_sue_candidates() -> List[Dict[str, Any]]:
    """
    Bernard & Thomas (1990) / Chan-Jegadeesh-Lakonishok (1996):
    Standardized Unexpected Earnings (SUE) and PEAD signals.
    Citation: JAE 1990, JF 1996. 18% annualized pre-cost in BT's first-quarter window.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20, 30]

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 1: Pure SUE — Standardized Unexpected Earnings (BT 1990 Eq. 1)
    # UE = EPS_q - EPS_{q-4}  (year-over-year seasonal change)
    # SUE = UE / std(UE, 8 quarters)
    # BRAIN: earnings_surprise ≈ UE; earnings_surprise_std ≈ σ(UE)
    # Approximation: rank(earnings_surprise / (ts_std_dev(earnings_surprise, 8q) + eps))
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "PEAD_SUE",
                    "archetype": f"PEAD_SUE_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(earnings_surprise, {d})) - 0.5) > 0.20, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990: Post-earnings-announcement drift on earnings_surprise (SUE proxy). "
                        f"Market under-reacts to earnings: drift up to 6 months post-announcement. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 2: SUE × Price Momentum (Chan-Jegadeesh-Lakonishok 1996 Sec. III)
    # CJL find that BOTH earnings momentum (SUE) and price momentum are independently
    # predictive. Their combination ('dual confirmation') is the strongest predictor.
    # Expression: rank(SUE) * rank(6m_price_return) — both positive = buy
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_DUAL_CONFIRM",
                    "archetype": f"PEAD_DualConfirm_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize("
                        f"rank(ts_decay_linear(earnings_surprise, {d})) * "
                        f"rank(ts_sum(returns, 126) - ts_sum(returns, 5)), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996: Dual confirmation — positive earnings surprise + positive 6m price momentum. "
                        f"Both independently predict; combined signal strongest. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 3: Analyst Revision Momentum (CJL 1996 Sec. III.B)
    # REV6 = Σ(analyst_revision_i) over 6 months / price
    # CJL: revision signal has Sharpe ~1.4 standalone, complementary to price momentum.
    # BRAIN: analyst_rating_change is the best proxy for revision direction.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20, 30]:
                catalog.append({
                    "pillar": "PEAD_REVISION_MOMENTUM",
                    "archetype": f"PEAD_RevMom_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(ts_sum(analyst_rating_change, 63), {d})), 0.5), "
                        f"{g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"CJL1996: 3-month cumulative analyst rating revision momentum — "
                        f"analysts systematically revise upward after positive earnings. Drift up to 6m. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 4: PEAD Persistence (BT 1990 Finding: drift delayed to NEXT earnings)
    # BT find that a disproportionately large fraction of PEAD is delayed until
    # the announcement for Q+1. Markets fail to update Q+1 expectations based on Q's news.
    # Signal: buy positive-SUE stocks 5 days BEFORE next quarter's earnings announcement.
    # BRAIN: use earnings_surprise with ts_delay to look at lagged signal fresh each quarter.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [5, 10]:
                catalog.append({
                    "pillar": "PEAD_NEXT_QUARTER_DRIFT",
                    "archetype": f"PEAD_NextQ_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(abs(rank(ts_decay_linear(ts_delay(earnings_surprise, 63), {d})) - 0.5) > 0.20, "
                        f"group_neutralize(rank(ts_decay_linear(ts_delay(earnings_surprise, 63), {d})), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 Sec 4: drift concentrated at NEXT quarter's announcement. "
                        f"Use 63-day lagged earnings_surprise to load up before next earnings. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # SIGNAL 5: Earnings Surprise × Analyst Dispersion Gate (Diether-Malloy-Scherbina 2002 Link)
    # BT: under-reaction is larger among stocks with HIGH analyst disagreement
    # (less efficient price discovery in high-dispersion stocks).
    # Gate: only trade PEAD when analyst dispersion is LOW (consensus = cleaner signal).
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20]:
                catalog.append({
                    "pillar": "PEAD_LOW_DISPERSION_GATE",
                    "archetype": f"PEAD_LowDisp_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.80, "
                        f"trade_when(rank(analyst_estimate_dispersion) < 0.30, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(earnings_surprise, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"BT1990 + DMS2002: PEAD signal gated on LOW analyst dispersion. "
                        f"High-consensus earnings surprises have cleaner PEAD; high-dispersion stocks confound. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "analyst",
                })

    return catalog
