# BRAIN Alpha Generation Pipeline

Autonomous pipeline that generates, screens, sweeps, filters, and correlation-checks
WorldQuant BRAIN equity alpha candidates, then hands anything that clears every bar
to a human via Telegram for **manual** review and submission.

## Non-negotiables

- **This codebase never calls a BRAIN submit/create-alpha endpoint.** There is no
  `submit(...)` method anywhere in `pipeline/brain/client.py` or elsewhere.
  Submission is manual, always — a human reads the Telegram alert, opens BRAIN,
  pastes the settings block, and submits it themselves.
- No hardcoded credentials or API keys anywhere. Everything comes from environment
  variables (`pipeline/config.py`), validated at startup — a missing required var
  raises `MissingConfigError` immediately rather than failing partway through a run.

## Architecture

One always-on process (`pipeline/run_worker.py`, deployed as a Render **Background
Worker**, not a Cron Job — see `render.yaml`) running two loops concurrently:

- **generation loop**: tops up the `candidates` queue from two tiers — a template
  generator (`pipeline/generator/template_generator.py`, pure string substitution
  over the 50 seed ideas, no LLM) and an LLM generator
  (`pipeline/generator/llm_generator.py`, used only to fill the gap the template
  tier can't).
- **simulation loop**: a semaphore bounded by `BRAIN_MAX_CONCURRENT_SIMS`, pulling
  the oldest pending candidate the instant a slot frees and running it through:

  ```
  Stage 0 screen -> staged settings sweep (Stages 1-4) -> local filter
  -> correlation check vs. pool -> review_store -> Telegram alert
  ```

### The staged settings sweep (`pipeline/sweep/settings_sweep.py`)

41 simulations per candidate that clears Stage 0, not a full cartesian grid
(~1,200 sims):

| Stage | What | Sims |
|---|---|---|
| 0 | Quick screen at default settings | 1 |
| 1 | Neutralization (6) x Decay (5) grid | 30 |
| 2 | Truncation refinement around the Stage 1 winner | 4 |
| 3 | Delay / Pasteurization / Nan Handling, both values each | 6 |
| 4 | Robustness check — computed from the 41 stored rows, **0 new sims** | 0 |

## Concurrency and correlation — how they actually work now

Two pieces here are easy to get subtly wrong, so they're called out explicitly:

- **Bounded simulation concurrency.** `simulation_loop` in `pipeline/run_worker.py`
  claims a candidate only when a `BRAIN_MAX_CONCURRENT_SIMS` slot is actually free,
  and holds the semaphore for the *entire* duration of that candidate's simulation
  work — not just around scheduling the task. `tests/test_run_worker.py` asserts
  peak concurrency never exceeds the configured limit.
- **Correlation gate against the real pool.** `Worker._process_candidate` fetches
  the winning settings' actual daily-return series from BRAIN
  (`BrainClient.get_alpha_pnl`, keyed off the `alpha_id` BRAIN assigns each
  simulation) before running `compute_max_correlation` against `pool_returns`. A
  candidate is rejected outright if that fetch can't happen, rather than silently
  passing the gate.

`_parse_pnl_response` in `pipeline/brain/client.py` is only tested against a
synthetic response shape so far — confirm it against a real BRAIN account
before trusting this gate live.

## One deliberate schema deviation (flagged, not silent)

`pool_returns` uses a composite `(alpha_id, return_date)` primary key rather than
a single-column `alpha_id` PK. A single-column PK would make it impossible to
store more than one date per alpha, which breaks the correlation check this
table exists to support. See the comment in `pipeline/db/schema.sql`.

## Two ambiguities resolved during the build (flagged in code comments)

1. **Stage 3's "2 alternatives each"**: Delay only has 2 possible values total
   (0, 1), so this only makes sense as "simulate both values of each field",
   not "the one value that differs from current" — that's the reading that
   produces the spec's stated 6 sims. See the comment in `settings_sweep.py`.
2. **Stage 4 fragile threshold**: the spec describes "only the single best combo
   clears the bar" vs. "a healthy cluster" without a numeric cutoff. Implemented
   as: fragile if the count of **distinct** settings combos clearing the local
   filter bar is `<= 1`. See the comment in `settings_sweep.py`.

## Setup

See [`SETUP.md`](./SETUP.md) for environment configuration, installation,
database migration, and deployment steps.

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

45 tests, all against in-memory fakes — no live BRAIN, Postgres, Telegram, or LLM
credentials required or contacted. Covers: staged sweep correctness (stage counts,
winner-holding, fragile flagging), LLM key-rotation fallback (rate-limit and
hard-failure paths, total-exhaustion alerting), correlation math (identical/
independent/inverted synthetic streams), local filter thresholds, Telegram message
formatting, bounded simulation concurrency, BRAIN response parsing (alpha-id
extraction, PnL-to-daily-returns conversion), and one full end-to-end mock run of
generate -> screen -> sweep -> filter -> correlate -> store -> alert.
