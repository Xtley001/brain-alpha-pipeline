"""Formula templates for Synthetic Forward Basis strategies."""
from __future__ import annotations
from brain_options.specialist.templates import OptionCandidate

def generate_forward_basis_candidates() -> list[OptionCandidate]:
    candidates: list[OptionCandidate] = []
    groups = ["subindustry", "sector"]

    # 1. Forward Basis Spread across tenors
    for tenor in [10, 20, 30, 60, 90]:
        for grp in groups:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank((forward_price_{tenor} - close) / close), {grp})",
                    archetype_name="Forward Basis Spread",
                    hypothesis=f"Synthetic forward basis at {tenor}d tenor demeaned by {grp} predicts drift.",
                    generation_source="template",
                )
            )

    # 2. Forward Basis Velocity
    for tenor in [20, 30]:
        for window in [3, 5, 10]:
            for grp in groups:
                candidates.append(
                    OptionCandidate(
                        expression=f"group_neutralize(rank(ts_delta((forward_price_{tenor} - close) / close, {window})), {grp})",
                        archetype_name="Forward Basis Velocity",
                        hypothesis=f"Rate of change in {tenor}d forward basis over {window}d window identifies accumulation.",
                        generation_source="template",
                    )
                )

    # 3. Decayed Forward Basis Acceleration
    for tenor in [30, 60]:
        for grp in groups:
            candidates.append(
                OptionCandidate(
                    expression=f"group_neutralize(rank(ts_decay_linear(ts_delta((forward_price_{tenor} - close) / close, 5), 5)), {grp})",
                    archetype_name="Decayed Forward Basis Acceleration",
                    hypothesis="Smoothed acceleration in forward basis isolates sustained institutional position shifts.",
                    generation_source="template",
                )
            )

    return candidates
