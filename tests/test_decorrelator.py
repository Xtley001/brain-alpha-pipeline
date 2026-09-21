"""
Unit tests for the Decorrelation Optimizer Engine.
Verifies that orthogonal transforms produce valid expressions,
shift frequency, cross-tenor curves, and apply regime gates.
"""
from brain_options.specialist.decorrelator import DecorrelationEngine
from brain_options.specialist.dedup import ASTDeduplicator


def test_decorrelator_generates_orthogonal_variants():
    dedup = ASTDeduplicator()
    engine = DecorrelationEngine(deduplicator=dedup)

    base_expr = (
        "trade_when(abs(rank(ts_decay_linear((call_breakeven_90 - forward_price_90) / close * "
        "implied_volatility_mean_skew_90 * sqrt(90/252.0), 25)) - 0.5) > 0.30, "
        "group_neutralize(rank(ts_decay_linear((call_breakeven_90 - forward_price_90) / close * "
        "implied_volatility_mean_skew_90 * sqrt(90/252.0), 25)), sector), -1)"
    )

    variants = engine.generate_orthogonal_variants(
        base_expr=base_expr,
        archetype="breakeven",
        base_sharpe=1.57,
        colliding_id="gJbAP76e",
    )

    assert len(variants) >= 4

    # 1. Check generation source and naming
    for v in variants:
        assert v.generation_source == "decorrelator"
        assert "Decorrelated" in v.archetype_name
        assert "Salvaged from base Sharpe=1.57" in v.hypothesis

    # 2. Check that at least one variant applies velocity shift (ts_delta)
    has_velocity = any("ts_delta" in v.expression for v in variants)
    assert has_velocity, "Expected at least one velocity transform variant with ts_delta"

    # 3. Check that at least one variant applies volume regime gating
    has_volume_gate = any("volume > adv20" in v.expression for v in variants)
    assert has_volume_gate, "Expected at least one volume regime gating variant"

    # 4. Check that at least one variant applies neutralization rotation (sector -> subindustry)
    has_subindustry = any("subindustry" in v.expression for v in variants)
    assert has_subindustry, "Expected at least one subindustry rotation variant"

    # 5. Check syntax sanity: balanced parentheses and non-empty
    for v in variants:
        assert v.expression.count("(") == v.expression.count(")"), f"Unbalanced parens in: {v.expression}"
        assert v.expression.startswith("trade_when(") or v.expression.startswith("group_neutralize(")
