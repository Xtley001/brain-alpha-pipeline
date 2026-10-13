"""
Cohen, Malloy & Pomorski (2012) — Decoding Inside Information
Lakonishok & Lee (2001) — Are Insider Trades Informative?
Fried (2024) — Insider Trading Against the Corporation
Kolasinski, Reed & Ringgenberg (2013) — Supply, Search, and the Efficiency of Equity Lending

Papers:
  1. CMP (2012): "Decoding Inside Information" — JF
     Core: Routine insiders (who trade at the same time every year = personal liquidity)
     vs. Opportunistic insiders (who trade only occasionally = true private information).
     Opportunistic insider trades predict returns: +82bps/month for opportunistic BUYS.
     BRAIN approximation: concentrated insider-buy periods (large position size + short window).

  2. Lakonishok & Lee (2001): "Are Insider Trades Informative?" — RFS
     Core: The NET PURCHASE RATIO (NPR) of insiders is a robust predictor.
     NPR = (insider_buys - insider_sells) / (insider_buys + insider_sells)
     High NPR → insiders are net buyers → positive future returns.
     Effect concentrated in: SMALL stocks, where information advantage is larger.

  3. Fried (2024): "Insider Trading Against the Corporation"
     Core: Corporate insiders trade against their own corporations' interests —
     selling before bad news, buying before buybacks. Their SELL signals are especially
     informative in governance-weak firms.

  4. Kolasinski-Reed-Ringgenberg (2013): Short-Selling Supply Search Friction
     Core: When shares are HARD TO BORROW (low supply, high search friction),
     prices take longer to incorporate negative information.
     Signal: high loan fee (specialness) combined with high short interest = max friction
     → stocks are most overpriced and will correct most sharply.
"""
from typing import Any, Dict, List


def generate_short_interest_p1_candidates() -> List[Dict[str, Any]]:
    """
    Insider trading + lending market P1 generators.
    Citation: CMP JF 2012, LL RFS 2001, Fried 2024, KRR JFE 2013.
    """
    catalog: List[Dict[str, Any]] = []

    universes   = ["TOPSP500", "TOP500", "TOP1000", "TOP3000"]
    neut_groups = ["SUBINDUSTRY", "SECTOR", "MARKET"]
    decays      = [10, 14, 20, 30]

    # ─────────────────────────────────────────────────────────────────────────
    # LAKONISHOK & LEE (2001): Net Purchase Ratio
    # NPR = (buys - sells) / (buys + sells) from SEC Form 4 filings
    # BRAIN: insider_buy_transactions, insider_sell_transactions (if available)
    # Approximation: net insider transaction flow directional signal
    # ─────────────────────────────────────────────────────────────────────────
    for u in universes:
        for g in neut_groups:
            for d in decays:
                catalog.append({
                    "pillar": "INSIDER_NPR",
                    "archetype": f"Insider_NPR_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.60, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"insider_buy_transactions - insider_sell_transactions, {d}"
                        f")), 0.5), {g.lower()}), -1)"
                    ),
                    "hypothesis": (
                        f"Lakonishok-Lee2001: Net Purchase Ratio = insider buys minus sells. "
                        f"High NPR = insiders are net buyers = informed optimism. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # LAKONISHOK & LEE: Small-Stock Effect
    # Paper Table 4: NPR effect strongest in SMALL stocks (less efficient, more
    # information advantage for insiders). Gate on market cap.
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOP1000", "TOP3000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20, 30]:
                catalog.append({
                    "pillar": "INSIDER_NPR_SMALL",
                    "archetype": f"Insider_NPR_Small_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.60, "
                        f"trade_when(rank(market_cap) < 0.40, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear("
                        f"insider_buy_transactions - insider_sell_transactions, {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Lakonishok-Lee2001: NPR effect concentrated in small stocks. "
                        f"Insiders have larger information advantage in small, less-followed firms. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # COHEN-MALLOY-POMORSKI (2012): Opportunistic vs Routine Insider Trades
    # Opportunistic insiders = trade only in specific months (not same time every year)
    # Approximation: concentrated large insider buys in non-routine months
    # BRAIN: use ts_zscore of insider_buy_transactions to identify opportunistic spikes
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14, 20]:
                catalog.append({
                    "pillar": "INSIDER_OPPORTUNISTIC",
                    "archetype": f"Insider_Opport_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.60, "
                        f"trade_when(rank(insider_buy_transactions / (ts_mean(insider_buy_transactions, 252) + 0.001)) > 0.75, "
                        f"group_neutralize(signed_power(rank(ts_decay_linear(insider_buy_transactions, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Cohen-Malloy-Pomorski2012: opportunistic insider buys (large spike vs normal). "
                        f"Gate: current insider buys > 75th pctile of 1yr avg = non-routine = informative. "
                        f"+82bps/month in paper. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # FRIED (2024): Insider SELL Signal (governance-weak firms)
    # Large insider sells in firms with weak governance = trading against corporation.
    # Approximation: large insider sells combined with high book-to-market (value trap)
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14]:
                catalog.append({
                    "pillar": "FRIED_INSIDER_SELL",
                    "archetype": f"Fried_InsiderSell_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.60, "
                        f"trade_when(rank(insider_sell_transactions / (insider_buy_transactions + 0.001)) > 0.70, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear(insider_sell_transactions, {d})), 0.5), {g.lower()}), "
                        f"-1), -1)"
                    ),
                    "hypothesis": (
                        f"Fried2024: large insider sell-to-buy ratio = insiders exiting ahead of bad news. "
                        f"High insider sells relative to buys = informed negative signal. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "fundamental",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # KOLASINSKI-REED-RINGGENBERG (2013): Lending Supply Search Friction
    # Hard-to-borrow stocks have maximum search friction → prices slowest to
    # incorporate negative info → most overpriced → biggest correction when shorts finally access.
    # Signal: high short interest + low/declining institutional ownership = hardest to borrow
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [10, 14, 20]:
                catalog.append({
                    "pillar": "KRR_LENDING_FRICTION",
                    "archetype": f"KRR_LendFriction_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(short_interest_ratio) > 0.60, "
                        f"trade_when(rank(institutional_ownership_percentage) < 0.40, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"short_interest_ratio / (institutional_ownership_percentage + 0.001), {d}"
                        f")), 0.5), {g.lower()}), -1), -1), -1)"
                    ),
                    "hypothesis": (
                        f"KRR2013: high SI / low inst.own = maximum lending search friction. "
                        f"Hard-to-borrow stocks correct most when constraints ease. {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    # ─────────────────────────────────────────────────────────────────────────
    # CHEN, HONG & STEIN (2002): Breadth of Ownership
    # Paper: "Breadth of Ownership and Stock Returns" — JFE
    # Core: When BREADTH (number of mutual funds holding stock) DECREASES, it signals
    # pessimists are exiting quietly (can't short openly) → overpricing ahead.
    # Short stocks with declining mutual fund breadth + high short interest.
    # BRAIN: institutional_ownership_percentage as breadth proxy
    # ─────────────────────────────────────────────────────────────────────────
    for u in ["TOPSP500", "TOP500", "TOP1000"]:
        for g in ["SUBINDUSTRY", "SECTOR"]:
            for d in [14, 20, 30]:
                catalog.append({
                    "pillar": "CHS_BREADTH_DECLINE",
                    "archetype": f"CHS_BreadthDecline_d{d}_{u}_{g}",
                    "expression": (
                        f"trade_when(volume > adv20 * 0.70, "
                        f"trade_when(rank(ts_delta(institutional_ownership_percentage, 63)) < 0.30, "
                        f"group_neutralize(signed_power(rank(-ts_decay_linear("
                        f"ts_delta(institutional_ownership_percentage, 63), {d}"
                        f")), 0.5), {g.lower()}), -1), -1)"
                    ),
                    "hypothesis": (
                        f"Chen-Hong-Stein2002: declining mutual fund breadth = pessimists exiting quietly. "
                        f"Short stocks with sharpest ownership breadth decline (63d). {u}."
                    ),
                    "universe": u,
                    "neutralization": g,
                    "decay": d,
                    "category": "short_interest",
                })

    return catalog
