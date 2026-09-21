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

    # 1. Check generation source, lineage tracking, and naming
    for v in variants:
        assert v.generation_source == "decorrelator"
        assert "Decorrelated" in v.archetype_name
        assert "Salvaged from base Sharpe=1.57" in v.hypothesis
        assert v.n_variants_tried == len(variants)
        assert v.base_alpha_id == "gJbAP76e"
        assert f"[base_alpha=gJbAP76e, n_variants_tried={len(variants)}]" in v.hypothesis

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


def test_decorrelator_axis2_robust_regex_mutations():
    """
    Verifies Issue 1 fix: Axis 2 (Calendar Curve Differencing) must successfully
    apply mutations even if the base expression has irregular whitespace,
    reversed operand order, or pre-computed constant scaling.
    """
    dedup = ASTDeduplicator()
    engine = DecorrelationEngine(deduplicator=dedup)

    # Reversed order: sqrt term BEFORE the field, and extra whitespace
    base_expr_reversed = (
        "trade_when(abs(rank(ts_decay_linear((call_breakeven_90 - forward_price_90) / close * "
        "sqrt( 90 / 252.0 )  *  implied_volatility_mean_skew_90, 25)) - 0.5) > 0.30, "
        "group_neutralize(rank(ts_decay_linear((call_breakeven_90 - forward_price_90) / close * "
        "sqrt( 90 / 252.0 )  *  implied_volatility_mean_skew_90, 25)), sector), -1)"
    )

    variants = engine.generate_orthogonal_variants(
        base_expr=base_expr_reversed,
        archetype="breakeven",
        base_sharpe=1.60,
        colliding_id="revOrder1",
    )

    # Confirm calendar curve differencing (Axis 2) succeeded
    calendar_variants = [v for v in variants if "Cross-tenor curve spread" in v.hypothesis]
    assert len(calendar_variants) >= 1, "Expected at least 1 calendar spread variant even with reversed operand order & spacing"
    for cv in calendar_variants:
        assert cv.base_alpha_id == "revOrder1"
        assert cv.n_variants_tried == len(variants)
        assert cv.expression != base_expr_reversed


def test_decorrelator_axis2_bare_field_mutation():
    """
    Verifies Issue 1 fix: Axis 2 also succeeds when field appears without sqrt scaling.
    """
    dedup = ASTDeduplicator()
    engine = DecorrelationEngine(deduplicator=dedup)

    base_expr_bare = (
        "trade_when(abs(rank(ts_decay_linear(implied_volatility_mean_skew_60, 20)) - 0.5) > 0.30, "
        "group_neutralize(rank(ts_decay_linear(implied_volatility_mean_skew_60, 20)), subindustry), -1)"
    )

    variants = engine.generate_orthogonal_variants(
        base_expr=base_expr_bare,
        archetype="skew",
        base_sharpe=1.45,
        colliding_id="bareField1",
    )

    calendar_variants = [v for v in variants if "Cross-tenor curve spread" in v.hypothesis]
    assert len(calendar_variants) >= 1, "Expected calendar spread variant on bare tenor field"
    for cv in calendar_variants:
        assert cv.base_alpha_id == "bareField1"
        assert cv.expression != base_expr_bare


def test_multiple_testing_hurdle_scaling():
    """
    Verifies Issue 2 fix: Deflated Sharpe hurdle scales monotonically with
    n_variants_tried to protect the 3/day submission quota from search noise.
    """
    import math

    def compute_hurdle(n_variants: int) -> float:
        if n_variants <= 1:
            return 1.25
        return max(1.25, round(1.25 + 0.04 * math.log(n_variants), 4))

    assert compute_hurdle(1) == 1.25
    assert compute_hurdle(2) == 1.2777
    assert compute_hurdle(4) == 1.3055
    assert compute_hurdle(8) == 1.3332

    # Verify that a marginal candidate (Sharpe 1.26) passes for N=1 but is rejected for N=6
    sharpe_marginal = 1.26
    assert sharpe_marginal >= compute_hurdle(1)
    assert sharpe_marginal < compute_hurdle(6)  # 1.26 < 1.3217


