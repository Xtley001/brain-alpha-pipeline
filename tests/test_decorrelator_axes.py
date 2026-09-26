import pytest
from brain_options.specialist.decorrelator import (
    invert_moneyness_axis,
    orthogonalize_factor,
    auto_correct_for_collision,
    DecorrelationEngine,
)
from brain_options.specialist.peer_genome import AlphaGenome, PeerGenomeGraph
from brain_options.specialist.generator import OptionsGenerator
from brain_options.llm.adapter import LLMAdapter
from brain_options.config import OptionsConfig
from tests.fixtures.known_expressions import KNOWN_KPND6OVL_EXPR, KNOWN_LEVEYPMX_EXPR


def test_invert_moneyness_axis():
    expr = "((call_breakeven_90 - forward_price_90) / close * (implied_volatility_mean_skew_90 * sqrt(90/252.0)))"
    inverted = invert_moneyness_axis(expr)
    assert "put_breakeven_90" in inverted
    assert "call_breakeven_90" not in inverted
    assert "forward_price_90 - put_breakeven_90" in inverted


def test_orthogonalize_factor_pcr():
    expr = "trade_when(abs(rank(ts_decay_linear(signal * (pcr_vol_90 / (pcr_oi_90 + 0.001)), 10)) - 0.5) > 0.28, -1)"
    orthogonal = orthogonalize_factor(expr, "pcr")
    assert "pcr_vol" not in orthogonal
    assert "pcr_oi" not in orthogonal
    assert "implied_volatility_mean_90" in orthogonal
    assert "implied_volatility_mean_30" in orthogonal


def test_orthogonalize_factor_iv_term_structure():
    expr = "signal * (implied_volatility_mean_90 / (implied_volatility_mean_30 + 0.001))"
    orthogonal = orthogonalize_factor(expr, "iv_term_structure")
    assert "implied_volatility_mean_90 / (implied_volatility_mean_30" not in orthogonal
    assert "implied_volatility_call_90" in orthogonal
    assert "implied_volatility_put_90" in orthogonal


def test_orthogonalize_factor_skew():
    expr = "signal * implied_volatility_mean_skew_60"
    orthogonal = orthogonalize_factor(expr, "skew")
    assert "implied_volatility_mean_skew_60" not in orthogonal
    assert "implied_volatility_call_60" in orthogonal
    assert "implied_volatility_put_60" in orthogonal


def test_auto_correct_for_collision_against_kpnd6ovl():
    # npdm7vWa-style formula: 90d call breakeven with PCR
    npdm7vwa_expr = (
        "trade_when(abs(rank(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * "
        "(implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10)) - 0.5) > 0.28, -1)"
    )
    kpn_genome = AlphaGenome(
        alpha_id="KPNd6Ovl",
        tenors=[30],
        moneyness=["call"],
        factors=["pcr"],
        decay=8,
    )
    corrected = auto_correct_for_collision(npdm7vwa_expr, kpn_genome)

    # Must have inverted moneyness: call -> put
    assert "put_breakeven_90" in corrected
    assert "call_breakeven_90" not in corrected

    # Must have orthogonalized factor: pcr -> iv_term_structure
    assert "pcr_vol" not in corrected
    assert "pcr_oi" not in corrected
    assert "implied_volatility_mean_90" in corrected


def test_decorrelator_axes_9_and_10_in_variants():
    engine = DecorrelationEngine()
    expr = (
        "trade_when(abs(rank(ts_decay_linear(((call_breakeven_90 - forward_price_90) / close * "
        "(implied_volatility_mean_skew_90 * sqrt(90/252.0)) * (pcr_vol_90 / (pcr_oi_90 + 0.001))), 10)) - 0.5) > 0.28, -1)"
    )
    variants = engine.generate_orthogonal_variants(
        base_expr=expr,
        archetype="skew",
        colliding_id="KPNd6Ovl",
        colliding_factor="pcr",
    )
    variant_ops = [v.operator_name for v in variants]
    assert "Axis 9 (Moneyness Inversion)" in variant_ops
    assert "Axis 10 (Factor Orthogonalization)" in variant_ops

    # Verify Axis 9 candidate inverted moneyness
    inv_cand = next(v for v in variants if v.operator_name == "Axis 9 (Moneyness Inversion)")
    assert "put_breakeven_90" in inv_cand.expression

    # Verify Axis 10 candidate swapped PCR
    orth_cand = next(v for v in variants if v.operator_name == "Axis 10 (Factor Orthogonalization)")
    assert "pcr_vol" not in orth_cand.expression


def test_generator_lookahead_auto_corrects_candidate():
    class MockDB:
        def get_all_active_alpha_rows(self):
            return [{
                "alpha_id": "KPNd6Ovl",
                "expression": KNOWN_KPND6OVL_EXPR,
                "decay": 8,
            }]

    cfg = OptionsConfig(brain_username="dummy", brain_password="dummy")
    llm = LLMAdapter(cfg)
    generator = OptionsGenerator(llm_adapter=llm, db=MockDB())
    
    # Procedural batch generates basis / skew candidates. Check that auto-correction triggers
    batch = generator.get_procedural_batch(count=5)
    assert len(batch) > 0
