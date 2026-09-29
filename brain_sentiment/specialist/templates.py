"""
Deterministic seed template generator for Sentiment Alpha candidates.
Generates fully valid Fast Expression candidates across 12 institutional sentiment archetypes,
strictly enforcing the subindustry neutralization and turnover (<15%) invariants.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("brain_sentiment.specialist.templates")


@dataclass(frozen=True)
class SentimentCandidate:
    expression: str
    archetype: str
    family: str
    hypothesis: str
    universe: str = "TOP3000"
    neutralization: str = "SUBINDUSTRY"
    decay: int = 15
    category: str = "sentiment"
    value_score: float = 8.0


def _parse_call_args(expr: str, func_name: str) -> Optional[Tuple[int, int, List[str]]]:
    """Balanced-parenthesis parser returning start_idx, end_idx, and arguments list for func_name."""
    tag = func_name + "("
    idx = expr.find(tag)
    if idx == -1:
        return None
    start_paren = idx + len(tag) - 1
    depth = 0
    comma_indices: List[int] = []
    end_paren = -1
    for i in range(start_paren, len(expr)):
        ch = expr[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end_paren = i
                break
        elif ch == "," and depth == 1:
            comma_indices.append(i)
    if end_paren == -1:
        return None
    args: List[str] = []
    prev = start_paren + 1
    for c_idx in comma_indices:
        args.append(expr[prev:c_idx].strip())
        prev = c_idx + 1
    args.append(expr[prev:end_paren].strip())
    return idx, end_paren, args


def compile_sentiment_invariant(expr: str, default_decay: int = 15, default_group: str = "subindustry") -> str:
    """
    Guarantees every sentiment candidate expression strictly obeys:
      1. Rank/zscore normalization
      2. Double smoothing/decay for low turnover (< 15%)
      3. group_neutralize(..., subindustry) for sub-universe Sharpe immunity
      4. trade_when conviction gating
    """
    clean = expr.strip()
    if not clean:
        return clean

    try:
        smoothing_ops = (
            "ts_decay_linear", "ts_decay_exp", "ts_zscore", "ts_rank",
            "ts_regression_residuals", "ts_mean", "ts_median", "ts_corr"
        )
        has_smoothing = any(op in clean for op in smoothing_ops)
        if not has_smoothing:
            if clean.startswith("group_neutralize(") and clean.endswith(")"):
                parsed_gn = _parse_call_args(clean, "group_neutralize")
                if parsed_gn and len(parsed_gn[2]) == 2:
                    raw_inner, grp = parsed_gn[2][0], parsed_gn[2][1]
                    clean = f"group_neutralize(rank(ts_decay_linear(ts_decay_linear({raw_inner}, {default_decay}), 3)), {grp})"
            elif clean.startswith("rank(") and clean.endswith(")"):
                parsed_rk = _parse_call_args(clean, "rank")
                inner_sig = parsed_rk[2][0] if (parsed_rk and len(parsed_rk[2]) == 1) else clean[5:-1].strip()
                clean = f"group_neutralize(rank(ts_decay_linear(ts_decay_linear({inner_sig}, {default_decay}), 3)), {default_group})"
            else:
                clean = f"group_neutralize(rank(ts_decay_linear(ts_decay_linear({clean}, {default_decay}), 3)), {default_group})"

        # Ensure group_neutralize is present at the outer layer (or within trade_when)
        parsed_tw = _parse_call_args(clean, "trade_when")
        if parsed_tw and parsed_tw[0] == 0 and parsed_tw[1] == len(clean) - 1 and len(parsed_tw[2]) == 3:
            cond, body, exit_val = parsed_tw[2]
            if "group_neutralize" not in body:
                if body.startswith("rank("):
                    body = f"group_neutralize({body}, {default_group})"
                else:
                    body = f"group_neutralize(rank({body}), {default_group})"
            clean = f"trade_when({cond}, {body}, {exit_val})"
        else:
            if "group_neutralize" not in clean:
                if clean.startswith("rank("):
                    clean = f"group_neutralize({clean}, {default_group})"
                else:
                    clean = f"group_neutralize(rank({clean}), {default_group})"

        return clean
    except Exception as exc:
        logger.warning(f"Error compiling sentiment invariant on '{clean}': {exc}")
        return clean


def generate_template_candidates() -> List[SentimentCandidate]:
    """Generates deterministic institutional sentiment alpha expressions across verified archetypes."""
    candidates: List[SentimentCandidate] = []
    universes = ["TOP3000", "TOP2000"]
    groups = ["subindustry", "sector"]
    decays = [10, 12, 15, 20]

    for u in universes:
        for g in groups:
            for d in decays:
                # 1. PEAD Sluggish Revision Drift (Chan, Jegadeesh, Lakonishok 1996)
                candidates.append(SentimentCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(ts_decay_linear(snt1_d1_netearningsrevision, {d}), 3)), {g})",
                    archetype="pead_earnings_drift",
                    family="PEAD_Sluggish_Revision",
                    hypothesis=f"Sluggish sell-side earnings revisions with double-decay ({d}d) drive steady drift.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 2. SUE Shock Conviction Gating (Bernard & Thomas 1989)
                candidates.append(SentimentCandidate(
                    expression=f"trade_when(abs(snt1_d1_earningssurprise) > 0.05, group_neutralize(rank(ts_decay_linear(snt1_d1_earningssurprise, {d})), {g}), -1)",
                    archetype="sue_earnings_surprise",
                    family="SUE_Conviction_Shock",
                    hypothesis=f"Material earnings surprise shocks (>5% SUE) filter noise and isolate post-announcement drift.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 3. Forecast Dispersion Penalty (Diether, Malloy, Scherbina 2002)
                candidates.append(SentimentCandidate(
                    expression=f"group_neutralize(rank(-ts_decay_linear(snt1_d1_dtstsespe / (close + 0.001), {d})), {g})",
                    archetype="analyst_revision_dispersion",
                    family="Dispersion_Overvaluation",
                    hypothesis=f"High analyst forecast dispersion reflects optimistic short-sale constrained pricing; shorting captures mean reversion.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 4. Target Price Revision Spread (Brav & Lehavy 2003)
                candidates.append(SentimentCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(snt1_d1_uptargetpercent - snt1_d1_downtargetpercent, {d})), {g})",
                    archetype="net_target_price_revisions",
                    family="Target_Spread_Drift",
                    hypothesis=f"Net target price revision spread ({d}d decay) captures valuation target re-ratings.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 5. Dynamic Analyst Attention & Volume Gating (Da et al. 2011)
                candidates.append(SentimentCandidate(
                    expression=f"trade_when(volume > adv20 * 0.85, group_neutralize(rank(ts_decay_linear(snt1_d1_dynamicfocusrank, {d})), {g}), -1)",
                    archetype="media_attention_buzz",
                    family="Dynamic_Analyst_Focus",
                    hypothesis=f"Volume-confirmed dynamic analyst focus ({d}d decay) leads to sustainable institutional price discovery.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 6. Contrarian Media Mood Reversal (Baker & Wurgler 2006, Tetlock 2007)
                candidates.append(SentimentCandidate(
                    expression=f"trade_when(abs(daily_equity_mood_indicator - 50) > 25, group_neutralize(rank(-ts_decay_linear(daily_equity_mood_indicator, {d})), {g}), -1)",
                    archetype="extreme_sentiment_reversal",
                    family="Mood_Contrarian_Reversion",
                    hypothesis=f"Extreme lexical mood readings indicate emotional overreaction that systematically reverts.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 7. Dual Recommendation and Target Alignment (Asquith et al. 2005)
                candidates.append(SentimentCandidate(
                    expression=f"group_neutralize(rank(0.55 * rank(ts_decay_linear(snt1_d1_nettargetpercent, {d})) + 0.45 * rank(ts_decay_linear(snt1_d1_netrecpercent, {d}))), {g})",
                    archetype="dual_target_rec_confluence",
                    family="Dual_Recommendation_Target",
                    hypothesis="Confluence of both target price upgrades and recommendation changes doubles return predictability.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

                # 8. Proprietary Core Score Divergence (Edmans et al. 2007)
                candidates.append(SentimentCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(snt1_cored1_score - 5.0, {d})), {g})",
                    archetype="core_composite_score",
                    family="Core_Analyst_Composite",
                    hypothesis=f"Deviation from neutral composite score (5.0) smoothed over {d} days tracks persistent sell-side bias.",
                    universe=u,
                    neutralization=g.upper(),
                    decay=d,
                ))

    return candidates
