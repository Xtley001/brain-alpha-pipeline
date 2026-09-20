"""
Pre-Simulation In-Memory Deduplication Module.
Extracts canonical Abstract Syntax Tree (AST) structure and normalizes floating-point
constants, lookback windows, and variable casing to reject cosmetically mutated formula
clones in <1ms before consuming WorldQuant BRAIN simulation API slots.
"""
from __future__ import annotations

import ast
import logging
import re
import threading
from typing import Iterable, Optional, Set

log = logging.getLogger("brain_options.dedup")


class _ASTConstantNormalizer(ast.NodeTransformer):
    """
    Transforms an AST to isolate its canonical operational structure:
    1. Floats (arbitrary thresholds/constants) are mapped to 0.0.
    2. Small integer flags (0, 1, -1) are preserved (e.g. delay=1, sign flips).
    3. Lookback window integers are discretized into speed buckets:
       - Fast: <= 8 -> 5
       - Medium: 9 to 18 -> 10
       - Slow: > 18 -> 20
    4. Identifiers and function names are lowercased.
    """

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

    def visit_Attribute(self, node: ast.Attribute):
        node.attr = node.attr.lower()
        return self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        """Sort commutative binary operands alphabetically so (a + b) == (b + a)."""
        self.generic_visit(node)
        if isinstance(node.op, (ast.Add, ast.Mult)):
            left_repr = ast.dump(node.left)
            right_repr = ast.dump(node.right)
            if left_repr > right_repr:
                node.left, node.right = node.right, node.left
        return node


class ASTDeduplicator:
    """
    Thread-safe in-memory deduplicator.
    Maintains a set of structural AST fingerprints across all evaluated and candidate expressions.
    """

    def __init__(self, initial_expressions: Optional[Iterable[str]] = None):
        self._lock = threading.Lock()
        self._fingerprints: Set[str] = set()
        self._normalizer = _ASTConstantNormalizer()
        if initial_expressions:
            self.populate(initial_expressions)

    def _preprocess_expression(self, expression: str) -> str:
        """Strips cosmetic whitespace, semicolons, and converts BRAIN ternary syntax."""
        cleaned = expression.strip().rstrip(";")
        # Convert ternary syntax (cond ? a : b) to if_else(cond, a, b) for standard AST parsing
        for _ in range(5):
            if "?" in cleaned and ":" in cleaned:
                prev = cleaned
                cleaned = re.sub(
                    r"([^?(),]+)\?([^?():,]+)\:([^?(),;]+)",
                    r"if_else(\1, \2, \3)",
                    cleaned,
                )
                if cleaned == prev:
                    cleaned = re.sub(
                        r"([^\?]+)\?([^\:]+)\:([^\;,\)]+)",
                        r"if_else(\1, \2, \3)",
                        cleaned,
                    )
                    break
            else:
                break
        return cleaned

    def get_fingerprint(self, expression: str) -> str:
        """
        Computes the canonical structural fingerprint of a BRAIN formula.
        Uses Python AST parsing with graceful regex fallback.
        """
        cleaned = self._preprocess_expression(expression)
        try:
            tree = ast.parse(cleaned, mode="eval")
            normalized = self._normalizer.visit(tree)
            return ast.dump(normalized)
        except Exception:
            # Fallback for non-standard syntax: normalize numbers and whitespace
            lower_expr = cleaned.lower()
            no_floats = re.sub(r"\b\d+\.\d+\b", "0.0", lower_expr)
            # Normalize integers
            def _bucket_int(m: re.Match) -> str:
                val = int(m.group(0))
                if val in (0, 1, -1):
                    return str(val)
                elif val <= 8:
                    return "5"
                elif val <= 18:
                    return "10"
                return "20"

            no_ints = re.sub(r"\b\d+\b", _bucket_int, no_floats)
            return re.sub(r"\s+", "", no_ints)

    def is_duplicate(self, expression: str) -> bool:
        """Returns True if the expression shares its canonical structure with an existing formula."""
        fp = self.get_fingerprint(expression)
        with self._lock:
            return fp in self._fingerprints

    def add(self, expression: str) -> bool:
        """
        Adds an expression's structural fingerprint.
        Returns True if newly added, False if it was already present.
        """
        fp = self.get_fingerprint(expression)
        with self._lock:
            if fp in self._fingerprints:
                return False
            self._fingerprints.add(fp)
            return True

    def populate(self, expressions: Iterable[str]) -> int:
        """Bulk adds expressions to the deduplicator. Returns count of unique structures added."""
        added = 0
        for expr in expressions:
            if expr and expr.strip():
                if self.add(expr):
                    added += 1
        return added

    def __len__(self) -> int:
        with self._lock:
            return len(self._fingerprints)
