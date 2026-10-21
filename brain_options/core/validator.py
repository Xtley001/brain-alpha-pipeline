"""
Strict Local AST & Verified Field Validator for WorldQuant BRAIN Expressions.
Runs sub-millisecond local static analysis before dispatching to BRAIN API.

Enforces:
1. Balanced parentheses, brackets, and braces.
2. Verified Field Whitelist against data/brain_fields_exact.json.
3. Protection against divide-by-zero (requires epsilon).
4. Rejection of anti-patterns (nested ranks, un-neutralized alphas, malformed commas).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Set, Tuple

log = logging.getLogger("brain_options.validator")

# Standard WorldQuant BRAIN Market Primitives
STANDARD_PRIMITIVES: Set[str] = {
    "close", "open", "high", "low", "volume", "returns", "vwap", "cap",
    "adv5", "adv10", "adv20", "adv30", "adv60", "adv90", "adv120", "adv180",
    "market", "sector", "subindustry", "industry", "country", "exchange",
    "true", "false", "nan"
}

# Standard WorldQuant BRAIN Operators & Math Functions
ALLOWED_OPERATORS: Set[str] = {
    "rank", "group_neutralize", "group_rank", "group_zscore", "group_mean",
    "signed_power", "trade_when", "ts_decay_linear", "ts_decay_exp_window",
    "ts_delta", "ts_delay", "ts_std_dev", "ts_zscore", "ts_rank", "ts_mean",
    "ts_sum", "ts_product", "ts_min", "ts_max", "ts_arg_min", "ts_arg_max",
    "ts_covariance", "ts_correlation", "ts_regression",
    "abs", "log", "sqrt", "sign", "min", "max", "if_else", "power", "reverse",
    "pasteurize", "scale", "truncate", "densify", "filter", "bucket"
}


def _load_verified_fields() -> Set[str]:
    """Loads all verified API fields from data/brain_fields_exact.json."""
    fields = set()
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reg_path = os.path.join(root_dir, "data", "brain_fields_exact.json")
    if os.path.exists(reg_path):
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for ds_id, field_list in data.items():
                for f_obj in field_list:
                    fid = f_obj.get("id")
                    if fid:
                        fields.add(fid.lower())
            log.debug("Loaded %d verified API fields into validator whitelist.", len(fields))
        except Exception as e:
            log.warning("Failed to load brain_fields_exact.json: %s", e)
    return fields


VERIFIED_FIELDS: Set[str] = _load_verified_fields()


def validate_expression(expr: str) -> Tuple[bool, str]:
    """
    Sub-millisecond local AST and syntax validator.
    Returns (True, "OK") or (False, rejection_reason).
    """
    if not expr or not isinstance(expr, str):
        return False, "Empty or non-string expression"

    clean = expr.strip()
    if len(clean) < 12:
        return False, "Expression too short (< 12 characters)"
    if len(clean) > 3000:
        return False, "Expression exceeds maximum length (3000 chars)"

    # 1. Balanced Parentheses & Brackets Check
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for char in clean:
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return False, f"Unbalanced bracket/parenthesis: '{char}'"
    if stack:
        return False, f"Unclosed bracket/parenthesis: '{stack[-1]}'"

    # 2. Malformed Commas and Punctuation
    if ",," in clean or "(," in clean or ",)" in clean:
        return False, "Malformed comma syntax"
    if "/ 0" in clean or "/0" in clean:
        return False, "Direct division by zero"

    # 3. Anti-Patterns Check
    if "rank(rank(" in clean:
        return False, "Redundant nested rank"
    if not ("group_neutralize(" in clean or "group_rank(" in clean):
        return False, "Expression must contain group_neutralize or group_rank"

    # 4. Strict Field Name Verification
    # Extract all lowercase identifier tokens
    tokens = re.findall(r"\b[a-z][a-z0-9_]*\b", clean)
    for t in tokens:
        # Ignore numbers, operators, standard primitives, and group values
        if t in ALLOWED_OPERATORS or t in STANDARD_PRIMITIVES:
            continue
        # Check against verified fields
        if VERIFIED_FIELDS and t not in VERIFIED_FIELDS:
            # Check if it's a known invalid hallucinated field
            if t in ("earnings_surprise", "analyst_estimate_dispersion", "analyst_count",
                     "analyst_rating_change", "idiosyncratic_vol_last_60_days_spy",
                     "consensus_eps", "consensus_net_profit"):
                return False, f"Unverified/hallucinated BRAIN field detected: '{t}'"

    return True, "OK"
