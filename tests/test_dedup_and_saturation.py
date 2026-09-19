"""
Unit tests for In-Memory AST Deduplication, Dynamic Archetype Daily Caps,
and 5-Channel Orthogonal Multi-Category Templates.
"""
import pytest
from brain_options.specialist.dedup import ASTDeduplicator
from brain_options.specialist.generator import CORE_ARCHETYPES, OptionsGenerator
from brain_options.specialist.templates import generate_template_candidates
from brain_options.store.db import map_archetype_to_core


def test_ast_deduplicator_exact_match():
    dedup = ASTDeduplicator()
    expr1 = "group_neutralize(rank(close - open), sector)"
    assert dedup.is_duplicate(expr1) is False
    assert dedup.add(expr1) is True
    assert dedup.is_duplicate(expr1) is True
    assert dedup.add(expr1) is False


def test_ast_deduplicator_whitespace_and_casing():
    dedup = ASTDeduplicator()
    expr1 = "group_neutralize(rank(close - open), sector)"
    expr2 = "  GROUP_NEUTRALIZE( rank( CLOSE - OPEN ) ,  SECTOR ) ; "
    dedup.add(expr1)
    assert dedup.is_duplicate(expr2) is True


def test_ast_deduplicator_constant_normalization():
    dedup = ASTDeduplicator()
    # Varying floating-point thresholds/constants should be recognized as duplicate structure
    expr1 = "trade_when(volume > 1000000.0, group_neutralize(rank((call_breakeven_20 - close) / (close + 0.001)), subindustry), -1)"
    expr2 = "trade_when(volume > 5000000.0, group_neutralize(rank((call_breakeven_20 - close) / (close + 0.05)), subindustry), -1)"
    dedup.add(expr1)
    assert dedup.is_duplicate(expr2) is True


def test_ast_deduplicator_window_bucketing():
    dedup = ASTDeduplicator()
    # Fast window: 5 vs 6 should map to same speed bucket
    expr_fast1 = "group_neutralize(rank(ts_decay_linear(close - open, 5)), subindustry)"
    expr_fast2 = "group_neutralize(rank(ts_decay_linear(close - open, 6)), subindustry)"
    # Slow window: 20 should map to a distinct speed bucket
    expr_slow = "group_neutralize(rank(ts_decay_linear(close - open, 20)), subindustry)"

    dedup.add(expr_fast1)
    assert dedup.is_duplicate(expr_fast2) is True
    assert dedup.is_duplicate(expr_slow) is False


def test_ast_deduplicator_ternary_preprocessor():
    dedup = ASTDeduplicator()
    expr1 = "volume > adv20 ? close - open : 0"
    expr2 = "if_else(volume > adv20, close - open, 0)"
    dedup.add(expr1)
    assert dedup.is_duplicate(expr2) is True


def test_map_archetype_to_core():
    assert map_archetype_to_core("Call Breakeven Hurdle Spread") == "breakeven"
    assert map_archetype_to_core("Sqrt-T Normalized Skew Acceleration") == "skew"
    assert map_archetype_to_core("Volatility Smirk Smear") == "skew"
    assert map_archetype_to_core("Variance Risk Premium (IV vs RV)") == "term_structure"
    assert map_archetype_to_core("Volatility Term Structure Slope") == "term_structure"
    assert map_archetype_to_core("Forward Basis Spread") == "forward_basis"
    assert map_archetype_to_core("Put-Call Ratio Contrarian Reversal") == "pcr_flow"
    assert map_archetype_to_core("Pan-Poteshman Informed Option Flow") == "pcr_flow"
    assert map_archetype_to_core("Analyst Revision Momentum") == "analyst_revisions"
    assert map_archetype_to_core("Price Target Implied Upside") == "analyst_revisions"
    assert map_archetype_to_core("Short Demand Borrow Surge") == "short_interest"
    assert map_archetype_to_core("Days-to-Cover Short Squeeze Breakout") == "short_interest"
    assert map_archetype_to_core("Volatility Smirk Borrow Fee Hybrid") == "hybrid_confluence"
    assert map_archetype_to_core("Revision vs Skew Divergence Hybrid") == "hybrid_confluence"


def test_dynamic_archetype_daily_cap():
    class DummyLLM:
        def generate(self, **kwargs):
            return None

    generator = OptionsGenerator(DummyLLM())
    
    # Saturated archetypes: simulate breakeven and skew having 1 qualified alpha today
    saturated = ["Call Breakeven Hurdle Spread", "Sqrt-T Normalized Skew Acceleration"]
    
    # Run 100 choices and count occurrences
    counts = {arch: 0 for arch in CORE_ARCHETYPES}
    for _ in range(200):
        chosen = generator.choose_archetype(saturated_archetypes=saturated)
        counts[chosen] += 1

    # Saturated archetypes (breakeven, skew) should have dropped weights to 0.02
    assert counts["breakeven"] < 25
    assert counts["skew"] < 25
    # Unsaturated channels should absorb majority of generation budget
    unsaturated_total = sum(counts[a] for a in CORE_ARCHETYPES if a not in ("breakeven", "skew"))
    assert unsaturated_total > 150


def test_multi_category_seed_templates():
    templates = generate_template_candidates()
    assert len(templates) >= 150

    # Ensure coverage of all 5 orthogonal channels
    categories_present = set()
    for cand in templates:
        cat = map_archetype_to_core(cand.archetype_name)
        categories_present.add(cat)

    assert "breakeven" in categories_present
    assert "skew" in categories_present
    assert "term_structure" in categories_present
    assert "forward_basis" in categories_present
    assert "pcr_flow" in categories_present
    assert "analyst_revisions" in categories_present
    assert "short_interest" in categories_present
    assert "hybrid_confluence" in categories_present
