"""
AST Expression Canonicalizer & Deduplication Engine.

Provides normalization, hashing, and deduplication for WorldQuant BRAIN formulaic expressions
to eliminate redundant simulations and conserve daily platform simulation quotas.
"""

from __future__ import annotations

import ast
import hashlib
import re
from typing import List, Dict, Any, Tuple


class ExpressionTransformer(ast.NodeTransformer):
    """
    Transforms a parsed Python AST of an alpha expression into canonical form:
    1. Sorts operands of commutative operators (+, *) alphabetically by string representation.
    2. Strips redundant parentheses and normalizes constant values.
    """
    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        # Commutative operators: Add (+), Mult (*)
        if isinstance(node.op, (ast.Add, ast.Mult)):
            left_str = ast.unparse(node.left) if hasattr(ast, "unparse") else str(node.left)
            right_str = ast.unparse(node.right) if hasattr(ast, "unparse") else str(node.right)
            if left_str > right_str:
                node.left, node.right = node.right, node.left
        return node


def canonicalize_expression(expression: str) -> str:
    """
    Produce a canonicalized representation of a BRAIN formulaic expression.
    Handles whitespace stripping, decimal normalization, and commutative sorting.
    """
    # 1. Clean whitespace
    clean_expr = re.sub(r"\s+", " ", expression.strip())

    # 2. Try parsing with Python AST (BRAIN syntax is a subset of Python expressions)
    try:
        tree = ast.parse(clean_expr, mode="eval")
        transformer = ExpressionTransformer()
        canonical_tree = transformer.visit(tree)
        ast.fix_missing_locations(canonical_tree)
        if hasattr(ast, "unparse"):
            canon_str = ast.unparse(canonical_tree)
        else:
            canon_str = clean_expr
        # Normalize whitespace in unparsed output
        return re.sub(r"\s+", "", canon_str)
    except Exception:
        # Fallback to normalized string if expression contains non-Python symbols
        return re.sub(r"\s+", "", clean_expr)


def compute_expression_hash(expression: str) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of the canonicalized expression.
    """
    canonical = canonicalize_expression(expression)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def deduplicate_candidate_pool(candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplicates a candidate pool using AST canonical fingerprints.
    Returns:
        (unique_candidates, duplicates_removed_count)
    """
    seen_hashes = set()
    unique: List[Dict[str, Any]] = []
    duplicates = 0

    for cand in candidates:
        expr = cand.get("expression", "")
        expr_hash = compute_expression_hash(expr)
        if expr_hash in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(expr_hash)
        unique.append(cand)

    return unique, duplicates
