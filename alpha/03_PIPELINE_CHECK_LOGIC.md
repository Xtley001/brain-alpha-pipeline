# Pipeline Check Logic — Stage-by-Stage Decision Flow

**Purpose:** Docs 1 and 2 are reference material. This doc is the
**implementation spec** — it turns the theory (Doc 1) and BRAIN mechanics
(Doc 2) into an explicit decision tree per pipeline stage, so an agent (or
a human) can look at any candidate's state and know exactly what happens to
it next. Read alongside `README.md`'s stage list:

```
reclaim orphaned candidates
  -> top up queue (template / LLM reasoning / LLM mechanical)
  -> for each candidate: Stage 0 screen -> settings sweep -> local filter
     -> correlation check -> Telegram alert
  -> heartbeat + run_history row
```

---

## 0. Candidate Object — Minimum Fields to Track

Every candidate flowing through the pipeline should carry, at minimum:

- `expression` (the fastexpr string)
- `hypothesis` (one-sentence causal statement, written **before** any
  simulation — Doc 1 §6.3 storytelling guard)
- `origin` (`template` / `llm_reasoning` / `llm_mechanical`, plus the
  specific template/prompt id — needed for §9 batch statistics)
- `settings` (region, universe, delay, decay, neutralization, truncation)
- `stage` (`generated` → `stage0` → `sweep` → `local_filter` →
  `correlation_check` → `alerted` / `rejected` / `stale`)
- `checks` (raw `is.checks` array as returned by the simulator, kept
  verbatim — never hardcode thresholds into the candidate record, always
  re-read them from the check response per Doc 2's calibration warning)
- `reject_reason` (structured, one of the categories in §8, not free text)

---

## 1. Pre-Generation Gate (before a candidate is even created)

Applies inside the generator, not as a separate pipeline stage — but cheap
enough that it should never be skipped:

1. **Hypothesis check** — does the idea reduce to one causal sentence
   (Doc 1 §1)? If the generator (especially `llm_mechanical`) can't produce
   one, either force it to, or route the candidate to extra scrutiny rather
   than dropping straight into Stage 0.
2. **TAP-axis tagging** — record which axis (Idea/Dataset, Region/Universe,
   Performance-Parameter — Doc 1 §2) this candidate is exploring relative
   to its sibling batch. Used later for queue top-up diversity logic
   (§9).
3. **Unit/domain sanity** (Doc 1 §3.2):
   - Reject expressions combining incompatible raw units without a ratio.
   - Reject unbounded-denominator divisions (raw P/E-style) unless the
     denominator is provably bounded away from zero.
   - Reject domain violations (`log` on a signed quantity, etc.).
4. **Data-category cap** — count distinct data categories referenced; flag
   (don't necessarily reject) candidates exceeding a configured cap, since
   category-mixing raises overfitting risk (Doc 1 §3.2).

Candidates failing 3 should never reach Stage 0 — they're free to catch
locally and waste no simulation budget.

---

## 2. Stage 0 Screen

**Goal:** cheap, fast elimination of clearly-broken or clearly-unpromising
candidates before spending sweep budget on them. Run at a single default
settings configuration (not yet the full sweep grid).

**Hard gates (reject, no sweep):**
- Simulation errors / NaN-heavy output.
- Turnover floor failure (Doc 2 §3) — near-degenerate signal.
- Any `is.checks` entry categorized as a **data/expression validity**
  failure (as opposed to a **performance** failure) — these don't improve
  with parameter tuning.

**Soft gates (pass to sweep, but tag for extra scrutiny):**
- Sharpe below cutoff **but** Fitness/turnover shape suggests the sweep
  might recover it (e.g., Sharpe close to cutoff and turnover clearly
  above the Fitness sweet spot — Doc 2 §1–§3).
- Sector/PnL concentration high (Doc 1 §5.2) — not an auto-reject, but
  should propagate a flag through to the local filter.

**Pass criteria to advance to sweep:**
- No hard-gate failure.
- Sharpe at or above cutoff, **or** flagged soft-gate case above.
- Quintile/decile spread roughly monotonic (Doc 1 §5.2) — compute this at
  Stage 0 since it's cheap and highly diagnostic of "tail-only" fragility.

---

## 3. Settings Sweep

**Goal:** find the parameter configuration (within a bounded grid) that
maximizes Fitness while keeping every hard-required check passing — not
maximize Sharpe in isolation.

**Grid dimensions (Doc 1 §15, Doc 2 §6):**
- `decay`: sweep upward from the Stage-0 default when turnover is the
  binding constraint (Doc 2 §1, §8 cheat sheet) — this is the
  **first lever**, always try before anything else.
- `trade_when` / event-gating: second lever if decay alone can't bring
  turnover under the ceiling without collapsing Sharpe.
- `truncation`: sweep if the weight-distribution check is borderline.
- `neutralization`: sweep on/off and across granularity
  (market/sector/industry/subindustry) — cheap, often decisive.
- `universe size`: sweep TOP200…TOP3000-equivalent bands; track
  **sub-universe Sharpe** (Doc 2 §4) at each, not just full-universe Sharpe.
- `delay`: only sweep 0 vs. 1 if the underlying data's arrival-timestamp
  discipline is actually verified for delay-0 (Doc 1 §6.1) — never sweep
  into delay-0 blind.

**Objective function for picking the sweep "winner":**
Rank surviving configurations by **Fitness** first (it already encodes the
Sharpe/turnover trade-off — Doc 2 §1), then break ties by lower
correlation-risk proxies (fewer well-known-factor loadings, more novel
data category — Doc 1 §11) and by turnover **comfortably** inside the
band rather than just barely inside it (headroom against future data
regime drift).

**Stop condition:** if no configuration in the grid clears the hard gates,
reject with reason `sweep_exhausted` (§8) rather than looping indefinitely
— this is a signal the *idea*, not the *settings*, is the problem, and
should feed back into generator diversity tracking (§9) rather than
triggering more sweep budget.

---

## 4. Local Filter

**Goal:** the qualitative/robustness pass that raw metrics can't fully
capture — this is where Doc 1's "quality is qualitative too" (§5.2) and
"robustness techniques" (§8) get applied as explicit checks, not vibes.

Checklist (all should produce a structured pass/fail/flag, not prose):

1. **Parameter sensitivity** — perturb the winning sweep configuration's
   key parameters (decay ±20%, lookback ±20%) and confirm Fitness/Sharpe
   don't collapse. A cliff-edge result is a red flag even if the winning
   point itself passes every check.
2. **Bootstrapped drawdown** (Doc 1 §8) — resample PnL blocks per the
   candidate's autocorrelation structure; confirm the 90th-percentile
   synthetic drawdown isn't dramatically worse than the realized backtest
   drawdown. Large gaps here mean the realized drawdown was masked, not
   controlled.
3. **Factor-neutralization check** (Doc 1 §11) — regress the candidate's
   returns against standard style factors (market/size/value/momentum, if
   available in your factor dataset). Flag (don't auto-reject) candidates
   whose performance largely disappears after neutralization — these are
   likely repackaged risk-factor exposure, not new alpha, and should be
   deprioritized relative to candidates that survive neutralization.
4. **Sector/PnL and quintile checks**, re-verified at the *winning* sweep
   configuration (Stage 0 ran them at defaults; settings may have shifted
   the distribution).
5. **Sub-universe consistency** (Doc 2 §4) — confirm the winning
   configuration's sub-universe Sharpe is comfortably above its
   (size-scaled) cutoff, not just barely passing.

**Pass criteria to advance to correlation check:** all of the above are
pass or acceptable-flag (no hard reject), and the candidate's structured
hypothesis (from §0/§1) still plausibly explains *why* the winning
configuration's numbers look the way they do — if the settings sweep
produced a configuration that no longer matches the original hypothesis
(e.g., decay so high the "short-term reversion" story stopped being true),
that's itself a flag worth surfacing to the human later.

---

## 5. Correlation Check

**Two-phase, per Doc 2 §5:**

### Phase A — local/pre-check (cheap, synchronous)
- Compute daily-PnL-**delta** correlation (never cumulative PnL curves —
  Doc 2 §5) against your locally tracked pool of active/recently-alerted
  alphas, using the intersection of active date ranges for each pair.
- Compute **T-corr** (sum of correlations vs. the whole tracked pool) and
  **max correlation**, not just max alone (Doc 1 §5.1).
- Apply Doc 1's correlation bands as a *pre-filter*, not a hard reject:
  `<0.3` clean pass · `0.3–0.5` pass · `0.5–0.7` requires the candidate to
  be meaningfully better than its most-correlated pool neighbor on Fitness
  or Sharpe · `>0.7` reject locally unless there's a specific, documented
  reason to still send it to the server check.
- If a `>0.5` correlation exists, explicitly compute the **Sharpe delta**
  against that specific neighbor and require it to clear a minimum
  improvement bar (Doc 2 §5's "~10% Sharpe improvement" convention as a
  starting default) before allowing it through to Phase B.

### Phase B — server/authoritative check (async)
- Submit only Phase-A survivors to BRAIN's actual self-correlation check
  to avoid burning server-check throughput on hopeless candidates.
- Candidate enters `PENDING` state; the worker loop must **poll and
  reconcile** this on a later tick rather than blocking the alert on it
  synchronously (Doc 2 §5) — this matters for the orphan-reclaim logic in
  §7 below.
- On resolve: `PASS` → advance to alert; `FAIL` → apply the same
  Sharpe-delta-vs-neighbor logic as Phase A before finalizing rejection,
  since BRAIN's own self-correlation semantics allow a
  correlated-but-better candidate through.

---

## 6. Telegram Alert

**What the alert message should contain** (so the human reviewer isn't
re-deriving context from raw JSON):

- Expression + one-sentence hypothesis (from §0/§1).
- Winning settings configuration from the sweep (§3).
- The full `is.checks` PASS/FAIL/PENDING table, verbatim, formatted like
  your example in Doc 2 §2 — don't summarize away individual check lines,
  the human needs to see exactly what passed and by how much headroom.
- Correlation summary: max correlation, T-corr, and (if triggered) the
  Sharpe-delta-vs-neighbor comparison from §5.
- Any flags carried forward from the local filter (§4) — factor-loading
  concern, cliff-edge sensitivity, sector concentration — even though none
  of these blocked the candidate from reaching this stage. The human's
  judgment call (Doc 1 §10 "just get out" cases, §14 portfolio fit) is
  exactly where these soft flags are supposed to matter.
- Origin metadata (`template`/`llm_reasoning`/`llm_mechanical` + specific
  id) — useful for the human to calibrate trust and for post-hoc batch
  statistics (§9).

**No auto-submit, ever** (per README's non-negotiable). The alert is a
terminal, human-facing state — the pipeline's job ends at "alerted."

---

## 7. Orphan Reclaim

Candidates can get stuck mid-flow (worker crash mid-sweep, a PENDING
self-correlation check that never resolves due to an API issue, etc.).
Reclaim logic per stage:

- **Stuck in `sweep`**: safe to re-run from the last completed grid point;
  sweep is idempotent by construction (each grid point is independently
  computed).
- **Stuck in `local_filter`**: safe to re-run in full; all checks in §4 are
  deterministic given the winning sweep configuration.
- **Stuck in `correlation_check` Phase B (`PENDING`)**: **do not** re-submit
  to the server check blindly — first poll for an existing result (BRAIN
  may have already computed it), and only re-submit if genuinely absent,
  to avoid wasting server-check quota on duplicate requests.
- **Stale threshold**: candidates sitting in any non-terminal stage past a
  configured age should be force-transitioned to `stale` and excluded from
  future orphan-reclaim sweeps, rather than retried forever — surface stale
  counts in the heartbeat/run_history row (per README) as a pipeline-health
  signal.

---

## 8. Structured Rejection Reasons

Use a closed enum, not free text, so batch statistics (§9) are queryable:

| Reason code | Stage | Meaning |
|---|---|---|
| `expr_invalid` | pre-gen / stage0 | Domain/unit violation or simulator error |
| `turnover_floor` | stage0 | Degenerate/near-constant signal |
| `sharpe_below_cutoff` | stage0 | Failed even the cheap default-settings pass |
| `sweep_exhausted` | sweep | No grid point cleared all hard gates |
| `fitness_below_cutoff` | sweep | Best grid point still Fitness-FAIL after turnover levers tried |
| `subuniverse_fragile` | local_filter | Sub-universe Sharpe fails or is barely passing |
| `sensitivity_cliff` | local_filter | Small parameter perturbation collapses performance |
| `factor_redundant` | local_filter | Performance mostly explained by known style factors |
| `correlation_local` | correlation_check (A) | Fails local correlation bands, no sufficient Sharpe delta |
| `correlation_server` | correlation_check (B) | Fails BRAIN's authoritative self-correlation check |
| `stale` | any | Aged out without resolving |

---

## 9. Feeding Back Into Generation (Queue Top-Up)

This is where Doc 1 §9 (batch/yield discipline) becomes operational:

- **Track pass rate per `origin` id** (specific template / specific
  prompt), not just globally. A specific template with a collapsing pass
  rate over time is a decaying-idea-space signal (Doc 1 §14) — deprioritize
  it in favor of fresh TAP-axis combinations (Doc 1 §2) before regenerating
  more of the same.
- **Run an occasional yield-test control** (Doc 1 §9): periodically push a
  deliberately weak/noise-like candidate through the *full* pipeline and
  confirm it gets rejected at the expected stage. If a noise control starts
  passing Stage 0 / sweep, that's a pipeline-health bug, not an alpha-
  quality event — alert on this distinctly from normal candidate alerts.
- **Diversity-forced top-up**: when regenerating, explicitly vary the TAP
  axis that's been least-recently explored across the last N accepted/
  alerted candidates, rather than letting the generator drift toward
  whatever idea family it produced most recently (Doc 1 §2, §12 idea-family
  menu as the source list to draw the next axis value from).

---

**Doc map:** `FINDING_ALPHAS_GUIDE.md` (theory) → `02_BRAIN_MECHANICS.md`
(platform semantics) → `03_PIPELINE_CHECK_LOGIC.md` (this doc — wiring).
