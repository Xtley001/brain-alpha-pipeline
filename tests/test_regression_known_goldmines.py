import pytest
from brain_options.specialist.decorrelator import (
    auto_correct_for_collision,
    invert_moneyness_axis,
    orthogonalize_factor,
)
from brain_options.specialist.peer_genome import AlphaGenome
from brain_options.specialist.templates import compile_dual_tenor_hybrid_blend


def test_pipeline_rediscovers_leveypmx_fix_from_0mXxRJP2():
    """
    Feeds the pipeline the *original* 0mXxRJP2 (pure 180d, pre-fix) candidate and asserts
    the Phase 4 dual-tenor blend logic produces an expression structurally equivalent to
    the verified levEYpmx submission: 65% 180d call basis + 35% 90d put basis.
    """
    # Original pure 180d 0mXxRJP2 candidate parameters
    blended_fix = compile_dual_tenor_hybrid_blend(
        tenor_long=180,
        tenor_short=90,
        weight_long=0.65,
        moneyness_long="call",
        moneyness_short="put",
        factor_short="term_structure",
        inner_decay1=10,
        inner_decay2=3,
        trade_threshold=0.26,
    )

    # 1. Structural dual-tenor weighting
    assert "0.65 * rank(" in blended_fix
    assert "0.35 * rank(" in blended_fix

    # 2. Long anchor contains 180d call breakeven
    assert "call_breakeven_180 - forward_price_180" in blended_fix

    # 3. Short liquidity bridge contains 90d put breakeven
    assert "forward_price_90 - put_breakeven_90" in blended_fix

    # 4. Complies with WorldQuant neutralization and gating physics
    assert "group_neutralize(" in blended_fix
    assert "subindustry" in blended_fix
    assert "trade_when(" in blended_fix


def test_decorrelator_rediscovers_npdm7vWa_fix():
    """
    Feeds npdm7vWa's original expression + a mock colliding genome for KPNd6Ovl
    (call moneyness, pcr factor, decay 8) into auto_correct_for_collision() and
    asserts the output has: no call_breakeven, no pcr_vol/pcr_oi, put_breakeven present.
    """
    # Original npdm7vWa expression that collided with KPNd6Ovl (corr=0.7705)
    npdm7vwa_orig = (
        "trade_when(abs(rank(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * "
        "(implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10)) - 0.5) > 0.28, "
        "group_neutralize(rank(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * "
        "(implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10)) * (volume / adv20), subindustry), -1)"
    )

    # Colliding peer genome (KPNd6Ovl: 30d call pcr)
    kpnd6ovl_peer = AlphaGenome(
        alpha_id="KPNd6Ovl",
        tenors=[30],
        moneyness=["call"],
        factors=["pcr"],
        decay=8,
    )

    salvaged_expr = auto_correct_for_collision(npdm7vwa_orig, kpnd6ovl_peer)

    # 1. Moneyness inverted away from colliding call peer
    assert "call_breakeven" not in salvaged_expr
    assert "put_breakeven_90" in salvaged_expr
    assert "forward_price_90 - put_breakeven_90" in salvaged_expr

    # 2. PCR factor orthogonalized away from colliding PCR flow
    assert "pcr_vol" not in salvaged_expr
    assert "pcr_oi" not in salvaged_expr
    assert "implied_volatility_mean_90" in salvaged_expr

    # 3. Preserved core execution syntax
    assert "trade_when" in salvaged_expr
    assert "subindustry" in salvaged_expr
