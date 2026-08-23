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

REASONING_PROMPT_TEMPLATE = """You are proposing new WorldQuant BRAIN equities \
cross-sectional alpha expressions (Fast Expression syntax, USA equities).

Existing pool summary (categories and idea counts already covered):
{pool_summary}

Recent failures (expression -> why it failed the local filter or \
correlation check):
{failure_log}

Propose {n} NEW expressions that are economically distinct from what's \
already in the pool above -- not a field/window tweak on an existing one, \
a genuinely different mechanism (different data category, different \
horizon, or a different economic rationale entirely).

Respond with ONLY a JSON array, no markdown fences, no preamble, in this \
exact shape:
[{{"expression": "...", "category": "...", "rationale": "one sentence"}}]
"""

MECHANICAL_PROMPT_TEMPLATE = """Given this BRAIN alpha expression:
{base_expression}

Produce {n} mechanical variations by swapping fields, window lengths, or \
group-neutralization targets -- keep the same economic idea, just \
different parameters or a closely related field.

Respond with ONLY a JSON array, no markdown fences, no preamble, in this \
exact shape:
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


# Maps the provider name LLMAdapter.reasoning_call/mechanical_call actually
# used (not just whichever was tried first) to the generation_tier value
# stored on the candidate row. Update 03: this used to be hardcoded to
# "llm_gemini" on every propose_new_ideas() result regardless of whether
# Gemini was exhausted and Groq answered instead -- which silently corrupted
# the generated-by-tier breakdown the heartbeat (Update 01 P1.1) reports.
_PROVIDER_TO_TIER = {"gemini": "llm_gemini", "groq": "llm_groq"}


def propose_new_ideas(
    adapter: LLMAdapter, pool_summary: str, failure_log: str, n: int = 5
) -> list[dict]:
    prompt = REASONING_PROMPT_TEMPLATE.format(pool_summary=pool_summary, failure_log=failure_log, n=n)
    try:
        raw, provider = adapter.reasoning_call(prompt)
    except QuotaExhausted:
        return []
    generation_tier = _PROVIDER_TO_TIER.get(provider, f"llm_{provider}")
    items = _safe_json_array(raw)
    return [
        {
            "expression": item["expression"],
            "category": item.get("category", "llm_proposed"),
            "generation_tier": generation_tier,
        }
        for item in items
    ]


def mutate_candidate(
    adapter: LLMAdapter, base_expression: str, category: str, n: int = 5
) -> list[dict]:
    prompt = MECHANICAL_PROMPT_TEMPLATE.format(base_expression=base_expression, n=n, category=category)
    try:
        raw, provider = adapter.mechanical_call(prompt)
    except QuotaExhausted:
        return []
    generation_tier = _PROVIDER_TO_TIER.get(provider, f"llm_{provider}")
    items = _safe_json_array(raw)
    return [
        {
            "expression": item["expression"],
            "category": item.get("category", category),
            "generation_tier": generation_tier,
        }
        for item in items
    ]
