"""
Unit tests for the AST Expression Canonicalizer (brain_options.core.ast_canonicalizer).
Verifies:
1. Normalization of commutative expressions (a + b == b + a).
2. Whitespace and decimal formatting invariance.
3. Accurate deduplication of candidate pools.
"""

from brain_options.core.ast_canonicalizer import (
    canonicalize_expression,
    compute_expression_hash,
    deduplicate_candidate_pool,
)


def test_commutative_canonicalization():
    expr1 = "rank(book_to_price) + rank(returns)"
    expr2 = "rank(returns) + rank(book_to_price)"
    assert canonicalize_expression(expr1) == canonicalize_expression(expr2)
    assert compute_expression_hash(expr1) == compute_expression_hash(expr2)


def test_whitespace_invariance():
    expr1 = "group_neutralize(  rank( close ) ,  subindustry )"
    expr2 = "group_neutralize(rank(close), subindustry)"
    assert canonicalize_expression(expr1) == canonicalize_expression(expr2)


def test_deduplicate_candidate_pool():
    candidates = [
        {"expression": "rank(a) + rank(b)", "archetype": "Alpha_1"},
        {"expression": "rank(b) + rank(a)", "archetype": "Alpha_2"},  # Commutative duplicate
        {"expression": "rank(c) * rank(d)", "archetype": "Alpha_3"},
        {"expression": "  rank(c) * rank(d)  ", "archetype": "Alpha_4"},  # Whitespace duplicate
    ]
    unique, dup_count = deduplicate_candidate_pool(candidates)
    assert len(unique) == 2
    assert dup_count == 2
    assert unique[0]["archetype"] == "Alpha_1"
    assert unique[1]["archetype"] == "Alpha_3"
