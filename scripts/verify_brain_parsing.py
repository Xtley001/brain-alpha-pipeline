"""
Update 02 P0.1 diagnostic: confirm `_parse_sim_response` / `_parse_pnl_response`
in `pipeline/brain/client.py` actually extract the right fields from BRAIN's
*real* response shape, instead of trusting the soft-fallback key lookups
that would otherwise silently return 0.0 / {} on a schema mismatch.

This is a throwaway script, not a test and not part of the pipeline import
graph -- it makes real network calls against your real BRAIN account and
prints raw vs. parsed side by side for you to eyeball. Run it once (and
again any time `wqb` is upgraded or BRAIN changes its response shape --
see the unpinned `wqb>=0.2.5` note in requirements.txt).

## How to run

1. Make sure BRAIN_USERNAME / BRAIN_PASSWORD are set (same as the
   pipeline itself uses), e.g.:

       export BRAIN_USERNAME=your_username
       export BRAIN_PASSWORD=your_password

2. Optionally set BRAIN_VERIFY_EXPRESSION to a known-quantity expression
   (something you already know the approximate Sharpe/Fitness for -- one
   obviously bad, one mediocre, one you know clears BRAIN's bar is the
   full P0.1 acceptance bar; run this script three times with different
   expressions to cover all three). Defaults to a simple 1-day reversal.

3. Optionally set BRAIN_VERIFY_ALPHA_ID to an existing alpha id you
   already know the PnL for, to also check `_parse_pnl_response`. If
   unset, the PnL check is skipped and only simulate-response parsing is
   verified.

4. Run:

       PYTHONPATH=. python scripts/verify_brain_parsing.py

## What to look at

For the simulation check, compare the "RAW JSON" block against the
"PARSED SimResult" block below it. Confirm sharpe/fitness/turnover/alpha_id
in the parsed result match what BRAIN's own dashboard shows for that same
simulation. If they don't match, fix the key lookups in
`_parse_sim_response` (pipeline/brain/client.py) -- that's a one-place fix,
not a redesign, per Update 02 P0.1's own framing.

Same idea for the PnL check: compare the "RAW JSON" records against the
"PARSED daily returns" dict. BRAIN's PnL recordset is *cumulative* PnL per
date; `_parse_pnl_response` diffs it into daily returns, so the printed
values should be small day-over-day deltas, not the raw cumulative numbers.

## Acceptance (Update 02 P0.1)

The fields `_parse_sim_response` returns for a real simulation match
BRAIN's dashboard numbers for that same simulation, exactly, for at least 3
test expressions across a range of quality (one obviously bad, one
mediocre, one you already know clears BRAIN's bar). Do not trust any
number `pipeline/brain/client.py` produces in production until this has
been confirmed once, by a human, against a real account -- see the warning
comment at the top of that file.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_EXPRESSION = "group_neutralize(rank(-ts_delta(close, 2)), sector)"


async def main() -> None:
    from pipeline.brain.client import (
        BrainClient,
        _parse_pnl_response,
        _parse_sim_response,
        settings_to_simulation_data,
    )
    from pipeline.sweep.settings_sweep import STAGE0_SETTINGS

    username = os.environ.get("BRAIN_USERNAME")
    password = os.environ.get("BRAIN_PASSWORD")
    if not username or not password:
        print(
            "BRAIN_USERNAME / BRAIN_PASSWORD are not set -- this script needs real "
            "credentials to make real network calls. See this file's own docstring "
            "for setup steps. Exiting without making any network calls."
        )
        return

    expression = os.environ.get("BRAIN_VERIFY_EXPRESSION", DEFAULT_EXPRESSION)
    alpha_id_for_pnl = os.environ.get("BRAIN_VERIFY_ALPHA_ID")

    client = BrainClient(username, password)
    print(f"Authenticating as {username}...")
    client.authenticate()
    print("Authenticated.\n")

    print(f"Running one real simulation for: {expression}")
    print(f"Settings: {STAGE0_SETTINGS}\n")

    session = client._get_session()
    target = settings_to_simulation_data(expression, STAGE0_SETTINGS)
    resp = await session.simulate(target)
    if resp is None:
        print("Simulation returned no response at all -- something is wrong before "
              "parsing even comes into play.")
        return

    raw = resp.json()
    print("=== RAW JSON (simulation response) ===")
    print(json.dumps(raw, indent=2, default=str))

    parsed = _parse_sim_response(resp)
    print("\n=== PARSED SimResult (via _parse_sim_response) ===")
    print(parsed)
    print(
        "\nCompare sharpe/fitness/turnover/alpha_id above against BRAIN's dashboard "
        "for this same simulation. If they don't match, fix the key lookups in "
        "_parse_sim_response (pipeline/brain/client.py)."
    )

    if alpha_id_for_pnl:
        print(f"\n\nFetching PnL recordset for alpha_id={alpha_id_for_pnl}...")
        pnl_resp = await session.get(f"alphas/{alpha_id_for_pnl}/recordsets/pnl")
        if pnl_resp is None:
            print("PnL fetch returned no response.")
            return
        raw_pnl = pnl_resp.json()
        print("=== RAW JSON (PnL recordset) ===")
        print(json.dumps(raw_pnl, indent=2, default=str))

        daily = _parse_pnl_response(pnl_resp)
        print("\n=== PARSED daily returns (via _parse_pnl_response) ===")
        print(json.dumps(daily, indent=2))
        print(
            "\nThese should be small day-over-day deltas of the raw cumulative PnL "
            "above, not the raw cumulative numbers themselves."
        )
    else:
        print(
            "\nBRAIN_VERIFY_ALPHA_ID not set -- skipping the PnL/_parse_pnl_response "
            "check. Set it to an alpha id you already know the PnL for to also "
            "verify that half of P0.1."
        )


if __name__ == "__main__":
    asyncio.run(main())
