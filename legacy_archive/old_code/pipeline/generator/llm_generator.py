"""
Tier-2 generator: LLM-driven. Two distinct jobs, routed to the two tiers in
pipeline/llm/adapter.py per the LLM-providers-and-keys design:

- propose_new_ideas(): reasoning tier (Gemini Flash first). Given a summary
  of what's already in the pool and which recent candidates failed and why,
  propose genuinely different economic ideas — not just field swaps on an
  existing one.
- mutate_candidate(): mechanical tier (Groq first). Field/window/
  neutralization-style mechanical variations on a direction already picked.
  High volume, low reasoning per call.

Both functions expect the LLM to return a strict, fenced-free JSON array so
the caller doesn't need to run regex over free text. Parsing failures are
treated as "no candidates this round" rather than crashing the generation
loop — a single bad LLM response should never take down the worker.
"""
from __future__ import annotations

import json
from typing import Optional

from pipeline.llm.adapter import LLMAdapter, QuotaExhausted

REASONING_PROMPT_TEMPLATE = """You are an elite quantitative researcher designing WorldQuant BRAIN alpha expressions (Fast Expression syntax, USA Equities).

### VALID WORLDQUANT BRAIN DATA FIELDS:
- Price / Volume: `open`, `high`, `low`, `close`, `volume`, `vwap`, `returns`, `cap`, `adv20`, `sharesout`
- DO NOT invent variables like pe_ratio, market_cap, earnings_window, or custom flags.

### VALID OPERATORS (from BRAIN Operator Library):
- Cross-Sectional: `rank(x)`, `group_rank(x, group)`, `group_neutralize(x, group)`, `group_zscore(x, group)`, `group_mean(x, 1, group)`, `quantile(x, driver='gaussian')` (groups: `sector`, `industry`, `subindustry`)
- Time-Series: `ts_rank(x, d)`, `ts_zscore(x, d)`, `ts_decay_linear(x, d)`, `ts_delta(x, d)`, `ts_delay(x, d)`, `ts_mean(x, d)`, `ts_std_dev(x, d)`, `ts_max(x, d)`, `ts_min(x, d)`, `ts_corr(x, y, d)`
- Transform / Gating: `trade_when(condition, alpha, -1)` (e.g. `trade_when(volume > adv20, alpha, -1)`), `signed_power(x, p)`, `abs(x)`, `min(x, y)`, `max(x, y)`, `log(x)`

### HIGH-ALPHA MULTI-FACTOR ARCHETYPES:
1. Sector-Relative Mean Reversion: `group_neutralize(rank(-(ts_delta(close, 2) - group_mean(ts_delta(close, 2), 1, sector))), sector)`
2. Event-Gated Volume Surge Reversal: `trade_when(volume > adv20, group_neutralize(rank(-ts_delta(close, 2)), sector), -1)`
3. Risk-Adjusted Momentum: `group_neutralize(rank(ts_decay_linear(returns, 20) / (ts_std_dev(returns, 20) + 0.0001)), sector)`
4. Volatility-Conditioned Reversal: `trade_when(ts_rank(ts_std_dev(returns, 60), 126) > 0.50, group_neutralize(rank(-ts_delta(close, 3)), subindustry), -1)`
5. Price-Volume Divergence: `group_neutralize(rank(ts_delta(close, 10)) * rank(-ts_delta(volume, 10)), subindustry)`
6. VWAP Decay Trend with Volatility Dampening: `group_neutralize(rank(ts_decay_linear((close - vwap) / close, 10)) / (ts_std_dev(returns, 20) + 0.001), sector)`

### CONSTRAINTS:
- Outer expression MUST be cross-sectionally normalized with `rank(...)` or `group_neutralize(...)` or `trade_when(..., group_neutralize(...), -1)`.
- Avoid repeating recently proposed expressions.

Existing pool summary:
{pool_summary}

Recent failures:
{failure_log}

Avoid these recently proposed expressions:
{avoid_expressions}

Propose {n} NEW, distinct, multi-factor BRAIN expressions across varied horizons (Short-term 2-5d, Medium-term 10-60d, Long-term 126-252d).

Respond with ONLY a JSON array, no markdown fences, no preamble, in this exact shape:
[{{"expression": "...", "category": "...", "hypothesis": "one sentence causal economic reason"}}]
"""

MECHANICAL_PROMPT_TEMPLATE = """You are a quantitative researcher generating parameter/operator variations of a WorldQuant BRAIN alpha expression.

Base expression:
{base_expression}

Generate {n} variations by:
- Swapping lookback windows (e.g. 2 -> 5, 20 -> 60)
- Swapping neutralization targets (`sector`, `industry`, `subindustry`)
- Testing decay smoothing (`ts_decay_linear`) or event gating (`trade_when(volume > adv20, ..., -1)`)
- Swapping price reference (`close` -> `vwap` or `returns`)

Respond with ONLY a JSON array, no markdown fences, no preamble:
[{{"expression": "...", "category": "{category}"}}]
"""


def _safe_json_array(text: str) -> list:
    if text is None:
        return []
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict) and "expression" in item]


# Update 10 Item 3: _PROVIDER_TO_TIER (a hardcoded {"gemini": "llm_gemini",
# "groq": "llm_groq"} map) removed entirely. It silently went blind to any
# provider added after those two -- Cerebras/OpenRouter candidates fell
# through its `.get(provider, f"llm_{provider}")` default into tags
# ('llm_cerebras'/'llm_openrouter') that recent_llm_expressions()'s
# hardcoded IN-list never matched, making the Update 05 anti-duplication
# check blind to roughly two-thirds of current LLM-generated candidates
# while still silently running and returning rows.
#
# Every LLM-sourced candidate is now tagged with a single, fixed
# generation_tier value regardless of which provider actually answered --
# the provider itself is recorded separately (see `provider` below and the
# `provider` column added to `candidates` in schema.sql). This survives
# the next provider being added with zero changes required here or in
# recent_llm_expressions().
LLM_GENERATION_TIER = "llm"


def propose_new_ideas(
    adapter: LLMAdapter,
    pool_summary: str,
    failure_log: str,
    n: int = 5,
    avoid_expressions: Optional[list[str]] = None,
) -> list[dict]:
    """`avoid_expressions` (Update 05): recently-proposed LLM expressions to
    tell the model not to repeat. Without this the reasoning tier had no
    memory of its own prior output and nothing stopped it re-proposing (and
    re-billing tokens for) something it already gave us last tick -- belt
    and suspenders with the exact-match DB dedup in Worker._top_up_queue,
    since the LLM can still reword a near-duplicate the DB check won't
    catch, but at least the model is told explicitly not to."""
    avoid_block = "\n".join(f"- {e}" for e in (avoid_expressions or [])) or "(none yet)"
    prompt = REASONING_PROMPT_TEMPLATE.format(
        pool_summary=pool_summary, failure_log=failure_log, avoid_expressions=avoid_block, n=n
    )
    try:
        raw, provider = adapter.reasoning_call(prompt)
    except QuotaExhausted:
        return []
    items = _safe_json_array(raw)
    avoid_set = set(avoid_expressions or [])
    return [
        {
            "expression": item["expression"],
            "category": item.get("category", "llm_proposed"),
            "generation_tier": LLM_GENERATION_TIER,
            "provider": provider,
        }
        for item in items
        if item["expression"] not in avoid_set  # exact-match belt-and-suspenders
    ]


def mutate_candidate(
    adapter: LLMAdapter, base_expression: str, category: str, n: int = 5
) -> list[dict]:
    prompt = MECHANICAL_PROMPT_TEMPLATE.format(base_expression=base_expression, n=n, category=category)
    try:
        raw, provider = adapter.mechanical_call(prompt)
    except QuotaExhausted:
        return []
    items = _safe_json_array(raw)
    return [
        {
            "expression": item["expression"],
            "category": item.get("category", category),
            "generation_tier": LLM_GENERATION_TIER,
            "provider": provider,
        }
        for item in items
    ]
