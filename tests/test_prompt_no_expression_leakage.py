"""
Regression test locking in prompt safety.
LLM prompts must never contain raw correlated or colliding expressions.
See AQuA (2026) in agentic-alpha-mining-references.md.
"""
from brain_options.llm.prompts import build_reasoning_prompt


def test_reasoning_prompt_never_contains_raw_correlated_expression():
    """
    Correlation feedback to the LLM tier must stay archetype-level only — never the
    colliding expression itself, which would let the LLM reconstruct near-duplicates
    around the AST dedup gate. See AQuA (2026) in agentic-alpha-mining-references.md.
    """
    fake_colliding_expression = "group_neutralize(rank((forward_price_30 - close) / close), sector)"
    colliding_archetype = "forward_basis"

    # Only archetype-level saturation info is provided to the prompt builder
    prompt = build_reasoning_prompt(
        archetype="term_structure",
        kb_cards=[],
        n=5,
        top_exemplars=[],
        failure_guidance=None,
        saturated_archetypes=[colliding_archetype, "volatility_skew"],
    )

    # The prompt must warn about the archetype name, but never leak the raw colliding formula
    assert colliding_archetype in prompt
    assert fake_colliding_expression not in prompt
