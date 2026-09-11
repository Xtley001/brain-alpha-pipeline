# BRAIN Platform Mechanics — What Actually Gates a Submission

**Purpose:** Doc 1 (`FINDING_ALPHAS_GUIDE.md`) covers *alpha theory* — why an
idea might work. This doc covers *BRAIN-specific mechanics* — the literal
formulas and check semantics that decide whether a candidate is even
eligible for a human to submit. The book never discusses BRAIN; this is
sourced from BRAIN's own scoring conventions as documented across public
WorldQuant-competition writeups, third-party BRAIN tooling repos, and your
own pasted check output.

> ⚠️ **Calibration warning.** Numeric cutoffs below (Sharpe 1.25, Fitness
> 1.0, turnover bands, sub-universe thresholds) are drawn from community
> documentation and your own example — they are **not** pulled from an
> authenticated BRAIN session and **do vary** by region, universe, delay,
> neutralization, and by whether you're in "regular" alpha submission vs. a
> competition track (e.g., IQC). Treat every number here as a *default
> assumption to verify against your own account's live check output*, not
> a hardcoded constant. Your pipeline's Stage 0 / sweep logic should read
> cutoffs from the actual `is.checks` API response per simulation, not
> from a static table — this doc exists so the *shape* of the logic is
> right even when exact numbers drift.

---

## 1. The Core Score Triangle: Sharpe, Turnover, Fitness

BRAIN (and the WorldQuant International Quant Championship, which uses the
same underlying simulator) scores alphas on three interlocking numbers:

- **Sharpe** — annualized daily risk-adjusted return. Standard definition:
  `Sharpe = sqrt(252) * mean(daily_pnl_pct) / std(daily_pnl_pct)`. This is
  the platform's name for what Doc 1 calls "Information Ratio."
- **Turnover** — `Turnover = Dollar Trading Value / Booksize` per day,
  averaged over the sim window. This is a **cost/activity** metric, not a
  quality metric on its own — both too-high *and* too-low turnover can fail
  a check (see §3).
- **Fitness** — the composite metric BRAIN actually optimizes for
  submission-worthiness:

  ```
  Fitness = Sharpe * sqrt( |Returns| / max(Turnover, 0.125) )
  ```

  Read this formula operationally:
  - Fitness rewards **high Sharpe** and **high absolute returns**, same as
    you'd expect.
  - It **penalizes turnover above 0.125 (12.5%)** — the `max(turnover,
    0.125)` floor means turnover *below* 12.5% gives you no extra Fitness
    credit (there's a floor, not a continuously increasing bonus for going
    lower and lower), but turnover *above* 12.5% actively drags Fitness
    down as it grows, via the square-root-of-inverse-turnover term.
  - **Practical consequence for the sweep stage:** a large fraction of
    "Fitness FAIL" outcomes are not really a signal-quality problem — they
    are a turnover problem wearing a Fitness costume. Before junking a
    candidate on Fitness failure, always check whether decay/smoothing
    (Doc 1 §7) can pull turnover down toward the ~12.5–70% band without
    materially hurting Sharpe. This should be the **first automated lever**
    the sweep stage tries on any Fitness-FAIL / Sharpe-PASS candidate.

## 2. Reading Your Example, Check by Check

```
rank(-(ts_delta(close,1) - group_mean(ts_delta(close,1), 1, sector)))

5 PASS
Sharpe of 2.06 is above cutoff of 1.25.
Turnover of 84.46% is above cutoff of 1%.
Weight is well distributed over instruments.
Sub-universe Sharpe of 1.57 is above cutoff of 0.89.
Competition Challenge matches.

2 FAIL
Fitness of 0.92 is below cutoff of 1.
Turnover of 84.46% is above cutoff of 70%.

1 PENDING
Self-correlation check pending.
```

Expression logic: `ts_delta(close,1)` is the 1-day price change; subtracting
the sector's group-mean 1-day change de-means it against the sector
(**sector-relative reversion signal** — how much a stock moved *more or
less* than its sector today), then `rank(-...)` cross-sectionally ranks the
negative of that (short the sector-relative winners, long the sector-relative
losers → classic sector-neutral **short-term mean reversion**). This is a
textbook Doc-1-§3.1 reversion idea, expressed with a group-neutralization
baked directly into the formula rather than via the neutralization setting.

Check-by-check:

| Check | Result | What it actually measures | Diagnosis for this candidate |
|---|---|---|---|
| **Sharpe ≥ 1.25** | PASS (2.06) | Risk-adjusted return quality | Strong — this is a genuinely good signal on a risk-adjusted basis |
| **Turnover ≥ 1%** (floor) | PASS (84.46%) | Alpha isn't degenerate/near-static | Trivially passes — this floor mainly catches broken/constant expressions, not a real constraint here |
| **Weight distribution** | PASS | No single-instrument or tiny-subset domination | Book is spread across the universe, not concentrated in a few names |
| **Sub-universe Sharpe ≥ 0.89** | PASS (1.57) | Signal holds up on a harder/smaller sub-universe (see §4) | Signal isn't just an artifact of illiquid/small-cap noise |
| **Competition Challenge matches** | PASS | Meets whatever the specific challenge/track's extra rule set requires | Track-specific, not a general submission gate |
| **Fitness ≥ 1.0** | **FAIL (0.92)** | Composite Sharpe/return/turnover efficiency | Driven almost entirely by turnover, not by weak Sharpe — see below |
| **Turnover ≤ 70%** (ceiling) | **FAIL (84.46%)** | Cost-efficiency ceiling | The direct cause of the Fitness fail too |
| **Self-correlation** | PENDING | Similarity to existing pool (yours + BRAIN's) | Can't be evaluated until server-side batch check completes (§5) |

**Diagnosis:** this is a *good* signal (Sharpe 2.06, clean weight
distribution, robust sub-universe) that is failing purely on
**cost-efficiency**, not signal quality. The turnover (84.46%) is above both
the local Fitness-formula sweet spot (~12.5%) and the hard ceiling (70%).
This is precisely the "Fitness failures are often turnover problems in
disguise" pattern — the fix path is decay/smoothing sweeps (Doc 1 §7), not
throwing the idea away. A day-1 reversion signal is inherently high-turnover
by construction (it re-evaluates every day), so this candidate is an
excellent sweep-grid candidate: try `decay(2..8)` and/or wrap in
`trade_when(...)` to fire less often, and re-check whether Sharpe survives
while turnover drops under 70%.

## 3. Turnover Has *Two* Bounds, Not One

Your example shows both directions explicitly:

- **Floor (~1%):** catches degenerate alphas — near-constant weights,
  broken expressions, or signals so smoothed/decayed they've stopped
  reacting to data at all. A candidate failing the *floor* almost always
  indicates a bug (e.g., an operator returning a constant, or decay set so
  high the signal never updates) rather than a "too good" alpha — treat
  floor failures as a hard error in the local filter, not a tuning problem.
- **Ceiling (~70%, though this is one of the numbers most likely to shift
  by region/universe/challenge — verify per-account):** catches
  cost-inefficient alphas that would bleed most of their edge to
  transaction costs in live trading. Ceiling failures are the tuning
  problem — decay/smoothing/`trade_when` gating are the standard fixes
  (Doc 1 §7).

**Pipeline implication:** the sweep stage's decay/`trade_when` grid should
be framed explicitly as "search for the turnover sweet spot between the
floor and ceiling that preserves the most Sharpe," not as an undirected
parameter sweep. Track Fitness as the *objective* of that sub-search, since
it already encodes the Sharpe/turnover trade-off in one number.

## 4. Sub-Universe Sharpe

- BRAIN reruns the alpha on a **smaller/harder sub-universe** (e.g., a more
  liquid-restricted or specifically-defined subset of the declared
  universe) and requires a separate, generally lower, Sharpe cutoff there.
- The cutoff **scales with sub-universe size** — smaller sub-universes get
  a lower bar, larger ones a higher bar (mirrors the general
  Sharpe-scales-with-√breadth relationship from Doc 1 §12.9).
- **What it's defending against:** an alpha that only works because it
  leans on a handful of easy, well-known large-cap trending names within a
  big universe, and would fall apart if forced onto a tighter, less
  redundant subset. This is functionally a **robustness-to-universe-choice**
  check — directly related to Doc 1 §5.2's "works across multiple
  universes" quality criterion, just enforced automatically.
- **Pipeline implication:** when the sweep stage tests universe-size
  variants (Doc 1 §15), treat sub-universe Sharpe consistency as a first-class
  metric alongside full-universe Sharpe, not an afterthought only checked
  at final gate time.

## 5. Self-Correlation

- Measured on **daily PnL changes** (i.e., correlate the day-to-day PnL
  *deltas* of the candidate against existing alphas), **not** on cumulative
  PnL curves and **not** on raw alpha/position weights. Two alphas with
  similar-looking cumulative equity curves can have low actual
  correlation once you look at daily deltas — always correlate deltas
  (mirrors Doc 1 §5.1's Pearson-on-daily-PnL-vectors convention).
- Uses a rolling **~2-year window**; for two alphas with different live
  histories, correlation is computed over the **intersection** of their
  active date ranges ("inner correlation").
- Checked against your **own already-submitted/active alphas** *and*
  against the broader BRAIN alpha pool server-side — this is why it's a
  separate **server-side, asynchronous check** (shows as PENDING while
  the platform computes it against the full comparison set) rather than
  something your local simulator can fully resolve.
- **Important nuance:** high self-correlation is not always an automatic
  reject — an alpha correlated with an existing one can still be
  submittable if it improves Sharpe by a sufficient margin over what's
  already in the pool (commonly cited threshold: **~10% Sharpe
  improvement**) — i.e., correlated-but-meaningfully-better can still pass.
  This matters for how your correlation-check stage should be tuned: don't
  hard-reject purely on a correlation number without also comparing Sharpe
  delta against the nearest correlated neighbor.
- **Pipeline implication:** because this check is asynchronous
  (PENDING → resolves later), your local `correlation-check` stage
  (Doc 1 §16) should treat it as a **two-phase gate**:
  1. *Local/pre-check*: compute your own approximate daily-PnL-delta
     correlation against your tracked pool before ever hitting the server
     check, to cheaply filter obvious near-duplicates and avoid burning
     server-check quota/time on hopeless candidates.
  2. *Server/authoritative check*: only send genuinely promising survivors
     to the official concurrent/self-correlation check, and have the
     worker loop poll/reconcile PENDING → PASS/FAIL rather than treating
     PENDING as a terminal state that blocks the alert.

## 6. Decay, Truncation, and Their Downstream Effects

- **Decay** — how long a day's signal value persists before fading (0 =
  forgotten immediately next day; higher = slowly blended with prior
  values). Higher decay → lower turnover (fewer position changes day to
  day) → generally higher Fitness, *provided* the smoothed signal still
  predicts returns. This is the single highest-leverage lever for fixing a
  turnover/Fitness fail without touching the core expression.
- **Truncation** — caps the max weight any single instrument can receive
  (this is BRAIN's version of Doc 1 §8's "max stock weight" / winsorizing
  concept, applied at the position-weight level rather than the raw-input
  level). Directly defends against the "weight distribution" check (§2).
- **Neutralization** — market/sector/industry/subindustry demeaning, same
  concept as Doc 1 §8, configurable as a simulation setting *or*, as in
  your example, baked directly into the expression via `group_mean(...)`.
  Both approaches are valid; baking it into the expression is more
  auditable/portable across settings sweeps, since the neutralization
  logic travels with the alpha text itself.
- **Pasteurization / Unit Handling / NaN Handling** — data-hygiene settings
  (how missing/invalid values and mismatched units are treated pre-sim).
  These belong in Stage 0 as **hard sanity gates**, not sweep-tunable
  performance levers — a candidate shouldn't reach the performance sweep
  at all if it depends on fragile NaN/unit assumptions.

## 7. Competition / Scoring Context (useful background, lower priority)

If any part of the pipeline eventually targets competition tracks (e.g.,
IQC-style) rather than only regular BRAIN submission, note the scoring
asymmetries — they change what "good" means for a candidate depending on
the track:

- Smaller declared universe, lower self-correlation, higher fitness, and
  longer delay (Delay-1 over Delay-0) all tend to score **better**, all
  else equal, in at least some competition scoring schemes.
- Delay-0 contributions can be **down-weighted** (e.g., divided by 3) in
  some final scoring formulas relative to Delay-1 — don't assume Delay-0
  and Delay-1 candidates are scored on equal footing downstream even if
  their in-sample metrics look similar.
- Competition scoring is frequently staged: an in-sample-only stage first,
  then an out-of-sample stage — meaning a candidate optimized purely
  against in-sample Fitness can still fail later. This is the platform-level
  analog of Doc 1 §6.2's holdout discipline — don't let a pipeline that's
  only ever seen in-sample checks develop false confidence.
- Team/merged-PnL scoring modes exist in some competitions (aggregate PnL
  across a team's whole alpha set) — largely irrelevant to a
  single-account production pipeline, but relevant context if your
  Telegram-reviewing human is also playing in a team competition
  alongside running the production pipeline.

## 8. Practical Failure-Pattern Cheat Sheet

| Symptom | Likely cause | First lever to try |
|---|---|---|
| Sharpe PASS, Fitness FAIL | Turnover too high relative to Sharpe/returns | Increase decay; add `trade_when` gating; smooth the signal (Doc 1 §7) |
| Turnover FAIL (ceiling) | Signal re-evaluates too aggressively every day | Same as above — decay/gating, not a new idea |
| Turnover FAIL (floor) | Degenerate/near-constant expression, likely a bug | Treat as hard error, not tunable — inspect expression logic |
| Sub-universe Sharpe FAIL, full-universe Sharpe PASS | Signal concentrated in a narrow, easy slice of the universe | Doesn't generalize — deprioritize or dig into which names are carrying it (Doc 1 §5.2 quintile/sector-concentration check) |
| Weight-distribution FAIL | A few instruments dominate book weight | Add/tighten truncation; check for an unbounded ratio (Doc 1 §3.2 denominator warning) |
| Self-correlation FAIL post-resolve | Genuinely redundant vs. existing pool, or correlated-but-not-better | Compare Sharpe delta vs. nearest correlated neighbor before rejecting outright (§5) |
| Everything PASS except one PENDING | Normal async server-check latency | Poll/reconcile; don't block the alert queue indefinitely on this (§5) |

---

**See also:** `FINDING_ALPHAS_GUIDE.md` (Doc 1) for the underlying alpha
theory referenced throughout (§ numbers above refer to that doc), and
`03_PIPELINE_CHECK_LOGIC.md` (Doc 3) for how these checks slot into the
actual Stage 0 → sweep → local filter → correlation check → alert flow.
