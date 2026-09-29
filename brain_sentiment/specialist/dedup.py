"""
Pre-Simulation In-Memory Deduplication Module for Sentiment Alphas.
Extracts canonical AST structure to reject cosmetically mutated clones in <1ms.
"""
from __future__ import annotations

import ast
import hashlib
import logging
from typing import Set

log = logging.getLogger("brain_sentiment.dedup")


class _ASTConstantNormalizer(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant):
        val = node.value
        if isinstance(val, bool):
            return node
        elif isinstance(val, float):
            return ast.Constant(value=0.0)
        elif isinstance(val, int):
            if val in (0, 1, -1):
                return node
            elif val <= 8:
                return ast.Constant(value=5)
            elif val <= 18:
                return ast.Constant(value=10)
            else:
                return ast.Constant(value=20)
        return node

    def visit_Name(self, node: ast.Name):
        node.id = node.id.lower()
        return node


class SentimentDeduplicator:
    def __init__(self):
        self._seen_hashes: Set[str] = set()

    def hash(self, expr: str) -> str:
        try:
            tree = ast.parse(expr.strip(), mode="eval")
            normalizer = _ASTConstantNormalizer()
            norm_tree = normalizer.visit(tree)
            canonical = ast.dump(norm_tree)
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
        except Exception:
            return hashlib.sha256(expr.strip().lower().encode("utf-8")).hexdigest()[:16]

    def is_duplicate(self, expr: str) -> bool:
        h = self.hash(expr)
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False
