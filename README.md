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

`pipeline/run_worker.py`'s `run_once()` does one bounded pass and exits — deployed
as a scheduled GitHub Actions job (`.github/workflows/run.yml`),
invoked every 10 minutes:

1. Reclaim any candidate orphaned in `running` by a previous invocation that got cut
   off mid-simulation.
2. Top up the `candidates` queue: template tier (`pipeline/generator/template_generator.py`,
   pure string substitution over 50 seed ideas, no LLM) → LLM reasoning tier
   (`propose_new_ideas`, genuinely new economic ideas) → LLM mechanical tier
   (`mutate_candidate`, cheap high-volume variations on whatever the reasoning tier
   just proposed), each only firing if the previous tier didn't fill the queue.
3. Process a bounded batch of candidates through:

   ```
   Stage 0 screen -> staged settings sweep (Stages 1-4) -> local filter
   -> correlation check vs. pool -> review_store -> Telegram alert
   ```

4. Send a heartbeat report to Telegram and write one `run_history` row —
   unconditionally, every tick, pass or fail or silence.

### The staged settings sweep (`pipeline/sweep/settings_sweep.py`)

41 simulations per candidate that clears Stage 0, not a full cartesian grid
(~1,200 sims):

| Stage | What | Sims | Concurrency |
|---|---|---|---|
| 0 | Quick screen at default settings | 1 | — |
| 1 | Neutralization (6) x Decay (5) grid | 30 | **concurrent**, bounded by the shared sim semaphore |
| 2 | Truncation refinement around the Stage 1 winner | 4 | **concurrent** |
| 3 | Delay / Pasteurization / Nan Handling, both values each | 6 | sequential (each field depends on the previous field's winner) |
| 4 | Robustness check — computed from the 41 stored rows, **0 new sims** | 0 | — |

Stages 1 and 2 run their combos concurrently (`asyncio.gather`, bounded by a
semaphore) rather than one simulate() call at a time — the single biggest
throughput fix in this codebase's history: a fully-serial 41-sim sweep could take
7-14 minutes per candidate and alone blow past the whole tick's `RUN_TIME_BUDGET_SECONDS`.
Stage 3 stays sequential on purpose: each field's test genuinely depends on
whichever value the previous field settled on.

**Per-combo fault isolation.** A single settings combo that fails to simulate
(BRAIN error, timeout) is recorded as a `SweepRun` with `.error` set instead of
raising and losing every other combo in that batch with it. If literally every
combo in a stage fails, the whole sweep reports `aborted_stage` (an operational
failure) rather than being silently treated as a quality verdict.

## Concurrency, correlation, and fault handling — how they actually work now

- **Real BRAIN-call concurrency is a single shared semaphore.** `Worker` creates
  exactly one `asyncio.Semaphore(BRAIN_MAX_CONCURRENT_SIMS)` and passes that same
  instance into every in-flight candidate's `run_staged_sweep` call. This means
  `BRAIN_MAX_CONCURRENT_SIMS` is a real, global ceiling on concurrent BRAIN calls —
  regardless of how many candidates or sweep stages those calls come from — not a
  per-candidate bound that let each candidate's sweep run its own 41 sims serially
  inside it (the previous, much slower shape). `tests/test_settings_sweep.py` and
  `tests/test_run_worker.py` both assert peak concurrency never exceeds the
  configured limit, including across two sweeps sharing one semaphore instance.
- **Correlation gate against the real pool, fed by the pipeline's own output.**
  `Worker._process_candidate` fetches the winning settings' actual daily-return
  series from BRAIN (`BrainClient.get_alpha_pnl`) before running
  `compute_max_correlation` against `pool_returns` — and, once a candidate passes,
  immediately upserts its own return series back into `pool_returns` so the *next*
  candidate's correlation check can see it too. Previously nothing ever called
  `upsert_pool_returns`, so the pool was permanently empty and every candidate
  passed the correlation gate by construction, including near-duplicates of each
  other.
- **Attempt-capped retries for operational failures.** A candidate whose sweep
  aborts (every combo in some stage failed) or that raises anywhere else in
  `_process_candidate` (e.g. a PnL fetch failure) gets up to 3 retries
  (`MAX_CANDIDATE_ATTEMPTS`, tracked via `candidates.attempts`/`last_error`)
  before permanently flipping to `rejected_error` with exactly one Telegram
  alert — not silently retried forever, and not one alert per tick either.

## Observability: the heartbeat and `run_history`

Every `run_once()` invocation sends a Telegram heartbeat and writes a
`run_history` row — pass, fail, or "nothing happened this tick". Silence is no
longer a valid healthy state. Each report includes: BRAIN auth status, DB
reachability, Gemini/Groq per-key health (from `llm_usage`, previously never
surfaced anywhere), queue depth, candidates generated, and candidates processed
broken down by exit status (`passed` / `rejected_stage0` / `rejected_filter` /
`rejected_correlation` / `rejected_error`). `run_history` turns that into a
queryable trend: `SELECT * FROM run_history ORDER BY started_at DESC LIMIT 20`.

Two gaps needed their own fix, not just the heartbeat, because they're invisible
in exactly the channel meant to report invisibility:

- A BRAIN-auth failure at startup happens *before* any `Worker`/`TelegramNotifier`
  exists — `main()` now catches `BrainAuthError` specifically and sends a
  best-effort alert built directly from env vars before exiting non-zero.
- Enable GitHub's native Actions-failure email notifications as a fully
  independent backup channel (see `SETUP.md`) — the only thing that still
  reaches you if Telegram, the DB, and BRAIN are all down at once.

## Generation tiers, honestly labeled

`candidates.generation_tier` records which tier and which LLM provider actually
produced a candidate (`template` / `llm_gemini` / `llm_groq`). The reasoning tier
(`propose_new_ideas`) and mechanical tier (`mutate_candidate`, now actually wired
into `Worker._top_up_queue` — it existed, fully written and tested, with zero call
sites before this pass) both report back which provider *actually* answered
(Gemini, or the Groq fallback on quota exhaustion), rather than hardcoding
`llm_gemini` regardless of which one ran. That hardcoding bug would have silently
corrupted the heartbeat's generated-by-tier breakdown the moment Gemini's quota
was ever exhausted.

## BRAIN response parsing — verify before trusting live numbers

`pipeline/brain/client.py`'s `_parse_sim_response`/`_parse_pnl_response` pull
metrics out of BRAIN's JSON with soft fallbacks that do **not** raise on a schema
mismatch — a genuinely strong candidate could silently be scored `sharpe=0.0` and
rejected if BRAIN's real key names don't match what's assumed. This has **not**
been verified against a live BRAIN account in this environment (no credentials
available). Before trusting any number this pipeline produces:

```bash
export BRAIN_USERNAME=... BRAIN_PASSWORD=...
PYTHONPATH=. python scripts/verify_brain_parsing.py
```

See that script's own docstring for the full acceptance criteria (3 test
expressions across a range of quality) and the warning comment at the top of
`pipeline/brain/client.py`.

## One deliberate schema deviation (flagged, not silent)

`pool_returns` uses a composite `(alpha_id, return_date)` primary key rather than
a single-column `alpha_id` PK. A single-column PK would make it impossible to
store more than one date per alpha, which breaks the correlation check this
table exists to support. See the comment in `pipeline/db/schema.sql`.

## Ambiguities resolved during the build (flagged in code comments)

1. **Stage 3's "2 alternatives each"**: Delay only has 2 possible values total
   (0, 1), so this only makes sense as "simulate both values of each field",
   not "the one value that differs from current" — that's the reading that
   produces the spec's stated 6 sims. See the comment in `settings_sweep.py`.
2. **Stage 4 fragile threshold**: the spec describes "only the single best combo
   clears the bar" vs. "a healthy cluster" without a numeric cutoff. Implemented
   as: fragile if the count of **distinct** settings combos clearing the local
   filter bar is `<= 1`. See the comment in `settings_sweep.py`.
3. **Shared sim semaphore vs. per-sweep semaphore (Update 04)**: the sweep-rewrite
   spec's prose says the semaphore must be one instance shared across every
   in-flight candidate, but its own literal code sample had `run_staged_sweep`
   build a fresh semaphore from an int on every call — which, taken literally,
   would let N concurrently-processed candidates each get their own
   `BRAIN_MAX_CONCURRENT_SIMS`-sized semaphore (up to N× over the real limit).
   Resolved by adding an optional `semaphore` parameter that `Worker` populates
   with one shared instance; standalone/test callers that don't pass one still
   get a private per-call semaphore built from the int, unchanged. See the
   comment on `run_staged_sweep` in `settings_sweep.py`.

## Setup

See [`SETUP.md`](./SETUP.md) for environment configuration, installation,
database migration, and deployment steps.

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

All tests run against in-memory fakes — no live BRAIN, Postgres, Telegram, or LLM
credentials required or contacted. Covers: staged sweep correctness (stage counts,
winner-holding, fragile flagging, concurrent Stage 1/2 execution, per-combo fault
isolation, shared-semaphore bounding across sweeps), LLM key-rotation fallback
(rate-limit and hard-failure paths, total-exhaustion alerting, provider-reporting
for the generation_tier fix), correlation math (identical/independent/inverted
synthetic streams), local filter thresholds, Telegram message formatting
(candidate alerts, operational alerts, heartbeat reports), bounded simulation
concurrency, attempt-capped retry/permanent-failure handling, the pool
self-consistency fix, BRAIN response parsing (alpha-id extraction, PnL-to-daily-
returns conversion), and a full end-to-end mock run of generate -> screen -> sweep
-> filter -> correlate -> store -> alert.
