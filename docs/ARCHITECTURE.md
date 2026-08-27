# Architecture

## Pipeline stages

```
reclaim orphaned candidates
  -> top up queue: template tier -> LLM reasoning tier -> LLM mechanical tier
  -> for each candidate:
       Stage 0 screen -> staged settings sweep (Stages 1-4) -> local filter
       -> correlation check vs. pool -> review_store -> Telegram alert
  -> heartbeat + run_history row
```

**Generation tiers**, each only firing if the previous one didn't fill the
queue:
- **Template** (`pipeline/generator/template_generator.py`) — pure string
  substitution over ~53 seed expressions, no LLM call.
- **LLM reasoning** (`propose_new_ideas`) — genuinely new economic ideas.
- **LLM mechanical** (`mutate_candidate`) — cheap, high-volume variations on
  whatever the reasoning tier just proposed.

`candidates.generation_tier` records which tier *and* which LLM provider
actually produced a candidate (e.g. `llm_groq`), based on whichever
provider in the fallback chain actually answered — not just whichever was
tried first.

## The staged settings sweep

`pipeline/sweep/settings_sweep.py` runs 41 simulations per candidate that
clears Stage 0, not a full cartesian grid (~1,200 sims):

| Stage | What | Sims | Concurrency |
|---|---|---|---|
| 0 | Quick screen at default settings | 1 | — |
| 1 | Neutralization (6) × Decay (5) grid | 30 | concurrent, bounded by shared sim semaphore |
| 2 | Truncation refinement around Stage 1's winner | 4 | concurrent |
| 3 | Delay / Pasteurization / Nan Handling, both values each | 6 | sequential — each field depends on the previous field's winner |
| 4 | Robustness check, computed from the 41 stored rows | 0 | — |

Stages 1–2 run concurrently via `asyncio.gather` bounded by a semaphore,
rather than one simulation at a time — a fully-serial sweep can take
7–14 minutes per candidate, which alone can exceed a tick's
`RUN_TIME_BUDGET_SECONDS`.

**Per-combo fault isolation.** A settings combo that fails to simulate is
recorded as a `SweepRun` with `.error` set, rather than losing every other
combo in that batch. If every combo in a stage fails, the sweep reports
`aborted_stage` (an operational failure) rather than a quality verdict.

## Concurrency and correlation

- **One shared semaphore.** `Worker` creates a single
  `asyncio.Semaphore(BRAIN_MAX_CONCURRENT_SIMS)` and passes it into every
  in-flight candidate's sweep, so the limit is a real global ceiling on
  concurrent BRAIN calls, not a per-candidate bound.
- **Correlation gate fed by the pipeline's own output.**
  `Worker._process_candidate` fetches the winning settings' actual daily
  returns from BRAIN, checks `compute_max_correlation` against
  `pool_returns`, then upserts the candidate's own returns back into the
  pool once it passes — so later candidates see it too.
- **Attempt-capped retries.** A candidate whose sweep aborts, or that
  raises anywhere in `_process_candidate`, gets up to
  `MAX_CANDIDATE_ATTEMPTS` (3, a fixed constant) retries before
  permanently flipping to `rejected_error` with one Telegram alert.

## Observability

Every tick sends a Telegram heartbeat and writes a `run_history` row —
pass, fail, or "nothing happened." Each report includes BRAIN auth
status, DB reachability, per-key LLM provider health, queue depth, and
candidates processed broken down by exit status
(`passed` / `rejected_stage0` / `rejected_filter` / `rejected_correlation`
/ `rejected_error`).

```sql
SELECT * FROM run_history ORDER BY started_at DESC LIMIT 20;
```

A BRAIN auth failure at startup happens before any `Worker` exists, so
`main()` catches `BrainAuthError` specifically and sends a best-effort
alert built directly from env vars before exiting non-zero.

## BRAIN response parsing — verify before trusting live numbers

`_parse_sim_response` / `_parse_pnl_response` in `pipeline/brain/client.py`
use soft key-lookup fallbacks that do not raise on a schema mismatch — a
genuinely strong candidate could silently score `sharpe=0.0` if BRAIN's
real response shape doesn't match what's assumed. A missing key now logs
a loud warning the first time it's observed (`_warn_missing_key_once`),
but that's a safety net, not a substitute for running
`scripts/verify_brain_parsing.py` against a live account (see `SETUP.md`
step 7).

## Deliberate schema deviation

`pool_returns` uses a composite `(alpha_id, return_date)` primary key
rather than a single-column `alpha_id` key, since a single-column key
would make it impossible to store more than one date per alpha — which
breaks the correlation check the table exists to support. See the comment
in `pipeline/db/schema.sql`.

## Ambiguities resolved during the build

1. **Stage 3 field values**: Delay has only 2 possible values (0, 1), so
   each field is simulated at both values, not just "the one value that
   differs from current" — that reading is what produces the spec's
   stated 6 sims. See the comment in `settings_sweep.py`.
2. **Stage 4 fragile threshold**: implemented as fragile if the count of
   distinct settings combos clearing the local filter bar is `<= 1`. See
   the comment in `settings_sweep.py`.
3. **Shared vs. per-sweep semaphore**: `run_staged_sweep` takes an
   optional `semaphore` parameter that `Worker` populates with one shared
   instance; standalone/test callers that don't pass one get a private
   per-call semaphore built from the int, unchanged.
