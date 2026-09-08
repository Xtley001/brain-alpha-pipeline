# BRAIN FastExpr Operator & Field Reference

**Purpose:** Doc 3 tells the pipeline what to *do* with a candidate. This
doc is the **vocabulary** — the operator/keyword library that "Fast
Expression" (BRAIN's alpha language) is built from, plus the data-field
naming conventions. This is what a generator (template engine or LLM)
actually draws from to construct an `expression` string.

> ⚠️ **This is not the authoritative source — here's where that lives.**
> BRAIN gates operators behind account tiers (base/Consultant → Expert →
> Master → Grandmaster unlock progressively more operators), and the
> canonical, complete, versioned list only exists **inside your own
> authenticated session**:
> - **In-platform:** the Simulate page's **Operators** tab (full
>   descriptions, signatures, examples) and the **Data Explorer** /
>   dataset browser for fields (per region/universe/delay, with coverage
>   %).
> - **Via API:** BRAIN exposes `/operators` and `/data-fields`-style
>   endpoints once authenticated — this is the one your pipeline should
>   actually depend on at runtime, not this file. Community tools like
>   `wq-alphagen` (PyPI) are built exactly around this: you export your
>   own `data_fields.csv` + `wq_operators.json` from your live session and
>   feed those into the generator, rather than hardcoding a static list.
>
> **Recommendation:** treat this MD as a **human-readable bootstrap
> reference** (so an agent/human has vocabulary to reason with offline),
> and build a small pipeline step — call it `catalog_sync` — that pulls
> the live operator + field list from your authenticated session
> periodically and caches it as the actual source of truth the generator
> reads from. That cache should also record which tier gates each
> operator, so the generator never proposes an expression using an
> operator your account can't actually run.

Everything below is compiled from public documentation, competition
writeups, and example alphas circulated by BRAIN/IQC participants — it's
representative and covers the operators you'll use 95% of the time, but
treat any specific signature (arg order, defaults) as **provisional**;
confirm against the in-platform Operators tab before relying on it.

---

## 1. How to Think About the Language

Fast Expression operates on **matrices**: rows = trading days, columns =
instruments (in the declared universe). Every operator falls into one of a
few shapes:

- **Elementwise / arithmetic** — operates on each (day, instrument) cell
  independently, no lookback or cross-section needed.
- **Time-series (`ts_*`)** — for a fixed instrument, looks back `d` days
  and returns one value per day (rolling window). This is where turnover
  and lookback-window sizing decisions live.
- **Cross-sectional** — for a fixed day, operates across all instruments
  in the universe (ranking, scaling, z-scoring "today, across everyone").
- **Group** — cross-sectional, but computed **within** a group label
  (sector/industry/subindustry/etc.) rather than across the whole
  universe — this is how neutralization gets expressed inline (as in your
  earlier example: `group_mean(ts_delta(close,1), 1, sector)`).
- **Vector (`vec_*`)** — for fields that carry *multiple* values per
  (day, instrument) — e.g., a "buzz vector" summarizing many news
  mentions in one field — collapse that multi-value field into a single
  scalar per (day, instrument) before it can be used like a normal field.
- **Transformational / control-flow** — turnover shaping, conditional
  trading, risk-factor orthogonalization. This is the category most
  directly relevant to Doc 2/3's Fitness-and-turnover fixes.

---

## 2. Arithmetic Operators

Elementwise math — the building blocks everything else composes on top of.

| Operator | Signature | Notes |
|---|---|---|
| `abs(x)` | | Absolute value |
| `add(x, y, ..., filter=false)` / `x + y` | 2+ inputs | `filter=true` treats NaN inputs as 0 before summing |
| `subtract(x, y, filter=false)` / `x - y` | | |
| `multiply(x, y, ..., filter=false)` / `x * y` | 2+ inputs | `filter=true` treats NaN inputs as 1 before multiplying |
| `divide(x, y)` / `x / y` | | **No automatic zero-guard** — see Doc 1 §3.2's unbounded-denominator warning |
| `inverse(x)` | | `1 / x` |
| `log(x)` | | Natural log — domain requires `x > 0` |
| `sqrt(x)` | | Domain requires `x >= 0` |
| `power(x, y)` / `x ^ y` | | |
| `sign(x)` | | −1 / 0 / 1 |
| `signed_power(x, y)` | | `sign(x) * abs(x)^y` — power that preserves sign, common for compressing outliers without flipping direction |
| `max(x, y, ...)` / `min(x, y, ...)` | 2+ inputs | Elementwise, not time-series |
| `round(x)`, `ceiling(x)`, `floor(x)` | | |
| `exp(x)` | | |
| `nan_out(x, lower, upper)` | | Forces values outside `[lower, upper]` to NaN — useful pre-filter before ranking |
| `purify(x)` | | Cleans a field to a usable numeric state (implementation detail varies by field type) |

## 3. Logical / Conditional Operators

| Operator | Signature | Notes |
|---|---|---|
| `and(x, y)`, `or(x, y)`, `not(x)` | | Boolean-style, operate on 0/1-valued matrices |
| `equal(x, y)`, `not_equal(x, y)` | | |
| `greater(x, y)`, `less(x, y)` (also `>`, `<`, `>=`, `<=`) | | |
| `if_else(condition, if_true, if_false)` / `condition ? if_true : if_false` | | Either branch can be a scalar or a full sub-expression |
| `is_nan(x)`, `is_finite(x)` | | |

**Doc 1 §6.2 caution applies directly here:** stacking too many strict
logical conditions shrinks the number of instruments actually receiving
non-zero signal on any given day, which increases overfitting risk even
though the expression "looks" more sophisticated. Prefer `trade_when`
(§6) with a small number of well-justified conditions over deeply nested
`if_else` chains.

## 4. Time-Series Operators (`ts_*`)

Rolling-window operators — the single largest category, and the primary
lever for turnover/decay tuning (Doc 2 §6).

| Operator | Signature | Notes |
|---|---|---|
| `ts_delay(x, d)` / `delay(x, d)` | | Value from `d` days ago |
| `ts_delta(x, d)` / `delta(x, d)` | | `x - delay(x, d)` — the standard "change over d days" |
| `ts_rank(x, d)` | | Current value's percentile rank within its own trailing `d`-day history (0–1) |
| `ts_mean(x, d)`, `ts_sum(x, d)`, `ts_product(x, d)` | | Rolling aggregates |
| `ts_std_dev(x, d)` | | Rolling standard deviation |
| `ts_zscore(x, d)` | | `(x - ts_mean(x,d)) / ts_std_dev(x,d)` — self-relative z-score, distinct from cross-sectional `zscore` (§5) |
| `ts_min(x, d)`, `ts_max(x, d)` | | Rolling min/max |
| `ts_argmax(x, d)`, `ts_argmin(x, d)` | | Index (0 = oldest day in window) of the extreme value — a large value means the extreme was recent |
| `ts_backfill(x, d)` | | Fills NaN with the most recent valid value within `d` days — common for sparse/event-driven fields (news, buzz) |
| `ts_decay_linear(x, d)` / `decay_linear(x, d)` | | Linearly weighted rolling average, most recent day weighted highest — **the primary turnover-reduction lever** (Doc 2 §6) |
| `ts_decay_exp_window(x, d, factor=...)` | | Exponentially weighted decay, `factor` controls how fast old values fade |
| `ts_count_nans(x, d)` | | Diagnostic — data-quality/coverage check, useful in Stage 0 sanity gating |
| `ts_step(x)` | | Days-since-last-change style counter |
| `ts_returns(x, d)` | | `d`-day return of `x` |
| `correlation(x, y, d)` / `ts_corr(x, y, d)` | | Rolling Pearson correlation between two series — heavily used in price/volume divergence signals |
| `covariance(x, y, d)` / `ts_covariance(x, y, d)` | | Rolling covariance (unnormalized correlation) |
| `ts_regression(y, x, d, ...)` | | Rolling regression of `y` on `x` — used to build residual/predicted-value signals |

**Pipeline tie-in:** every `ts_*` operator's `d` argument is a first-class
sweep dimension (Doc 3 §3) — treat lookback windows as tunable, not fixed,
and always sanity-check `d` against the underlying data's actual cadence
(Doc 1 §4 — don't use `d=3` on quarterly fundamentals).

## 5. Cross-Sectional Operators

Operate across all instruments, for a fixed day — this is where
"positions relative to the rest of the universe today" gets built.

| Operator | Signature | Notes |
|---|---|---|
| `rank(x)` | | Percentile rank across the universe, 0–1. The single most common wrapper — most raw signals get `rank()`-ed before becoming the final alpha (Doc 1 §8 ordering methods) |
| `zscore(x)` | | Cross-sectional z-score: `(x - mean(x)) / std(x)` across the universe on that day |
| `quantile(x, driver='gaussian', sigma=1.0)` | | Rank the raw vector, then remap through a target distribution (gaussian/cauchy/uniform) — useful when you want rank-like robustness but a specific output distribution shape |
| `scale(x, scale=1, longscale=..., shortscale=...)` | | Rescales so the alpha's gross exposure matches book size; `longscale`/`shortscale` let you set long and short exposure independently |
| `winsorize(x, std=4)` | | Caps outliers at `std` standard deviations — direct implementation of Doc 1 §8's limiting-methods robustness technique |
| `normalize(x, useStd=false, limit=0.0)` | | Subtract cross-sectional mean (and optionally divide by std); `limit` can cap extreme post-normalization values |

## 6. Group Operators

Same idea as cross-sectional operators, but computed **within** a group
label (sector, industry, subindustry, exchange, custom groupings) instead
of across the whole universe. This is BRAIN's inline mechanism for
neutralization (Doc 1 §8, Doc 2 §6).

| Operator | Signature | Notes |
|---|---|---|
| `group_mean(x, weight, group)` | | Group average, optionally weighted |
| `group_sum(x, group)`, `group_median(x, group)` | | |
| `group_rank(x, group)` | | Rank within group only, not universe-wide |
| `group_zscore(x, group)` | | Z-score within group |
| `group_neutralize(x, group)` | | Demean `x` within each group — the standard inline neutralization call |
| `group_vector_neut(x, factor, group)` | | Orthogonalize `x` against `factor` **within each group** — combines vector-neutralization (§7) with group scoping in one call |
| `densify(group_field)` | | Collapses a sparse/high-cardinality group field (e.g., a composite of industry × exchange) into a smaller number of contiguous buckets — reduces the computational/statistical cost of grouping on it |
| `IndNeutralize(x, IndClass.sector / .industry / .subindustry)` | | Older/alternate syntax seen in community examples for the same neutralization concept as `group_neutralize` — confirm current preferred form in your platform's Operators tab, syntax has evolved across BRAIN versions |

**Group field note:** `sector`, `industry`, `subindustry`, `exchange`
(and similar) are themselves special **grouping-type data fields** — not
numeric values to compute on directly, but labels that group operators
consume as their `group` argument.

## 7. Vector Operators (`vec_*`)

For fields that pack multiple sub-values into one (day, instrument) cell
(e.g., a "buzz vector" aggregating many news/sentiment mentions) —
collapse to a scalar before the field can be used like any other field.

| Operator | Signature | Notes |
|---|---|---|
| `vec_avg(x)` | | Mean of the vector's elements |
| `vec_sum(x)` | | Sum of the vector's elements |
| `vec_max(x)`, `vec_min(x)` | | Extremes within the vector |

Typically chained with `ts_backfill` immediately after, since
vector-sourced fields (news/sentiment/buzz datasets) are often sparse —
e.g. `ts_backfill(vec_sum(some_buzz_vector), 20)`.

## 8. Transformational / Turnover-Control / Risk Operators

The category most directly tied to fixing Doc 2's Fitness/turnover
failures and Doc 1's risk-neutralization (§10–§11).

| Operator | Signature | Notes |
|---|---|---|
| `trade_when(condition, alpha, exit_condition)` | | Only updates the position when `condition` is true; holds the prior position otherwise; `exit_condition` (often `-1`, meaning "never force exit" / or a specific exit rule) controls when to flatten. **This is the primary event-gating lever** for cutting turnover without smoothing the signal itself (contrast with `ts_decay_linear`, which smooths instead of gating) |
| `hump(x, hump=threshold)` | | Only changes the alpha value if the change exceeds `threshold`; otherwise holds the previous value — direct implementation of Doc 1 §7's "humped delta" turnover-reduction technique |
| `vector_neut(a, b)` | | Returns the component of `a` orthogonal to `b` — i.e., strips out `b`-correlated exposure from `a`. Used for factor-neutralizing an alpha against a specific risk vector (e.g., `vector_neut(a, ts_mean(returns, 250))` to strip out a long-run-return/beta-like exposure) |
| `densify(x)` | | (also listed under Group, §6) general-purpose bucket-compression, not exclusively for group fields |

---

## 9. Data Fields — Naming Conventions (not exhaustive)

Fields are dataset-scoped and vary by region/universe/delay coverage —
always check actual coverage % in the Data Explorer before assuming a
field is usable for a given universe. Rough conventions seen across
examples:

### Core price-volume (near-universal coverage)
`close`, `open`, `high`, `low`, `volume`, `vwap` (volume-weighted average
price), `returns` (daily return), `cap` (market cap), `adv20` / `adv60` /
`adv180` (average daily $ volume over N days — used constantly as a
liquidity/event-trigger reference, e.g. `volume > adv20`).

### Grouping / classification fields
`sector`, `industry`, `subindustry`, `exchange`, `country` — consumed by
group operators (§6), not used arithmetically.

### Dataset-prefixed fields (fundamental / alternative data)
Fields from specific BRAIN datasets carry a dataset-id prefix, e.g.:
- `fnd6_*` — a fundamentals dataset (balance sheet / income statement
  derived ratios).
- `mdl*` — a modeled/derived-metrics dataset.
- `scl12_*` — a sentiment/social "buzz" dataset (often vector-typed,
  paired with `vec_*` + `ts_backfill`).
- `nws*` — news-derived fields.

**These prefixes are dataset IDs, not a fixed BRAIN-wide naming
standard** — the actual catalog of dataset IDs available to your account
is exactly what the `catalog_sync` step (§0 warning above) should be
pulling live, since dataset access varies by account tier and by
region/delay/universe combination.

---

## 10. Composition Patterns Worth Templating

These recur constantly across example alphas and are good starting
**templates** for the `template` generation path (Doc 3 §9):

- **Cross-sectional signal, industry-neutral:**
  `group_neutralize(rank(<raw signal>), sector)` or the inline-demean form
  from your own example: `rank(-(<raw signal> - group_mean(<raw signal>,
  1, sector)))`.
- **Event-gated trend/reversion:**
  `event = volume > adv20; alpha = <signal>; trade_when(event, alpha, -1)`
  — only trade on above-average-volume days.
- **Volatility-regime-conditioned reversion:**
  `when = ts_rank(ts_std_dev(returns, 60), 126) > 0.55; trade_when(when,
  <reversion signal>, -1)` — only trade the reversion idea when recent
  volatility is itself elevated relative to its own history.
- **Risk-neutralized momentum-style signal:**
  `vector_neut(<raw signal>, ts_mean(returns, 250))` then
  `ts_decay_exp_window(..., d, factor=...)` then
  `group_neutralize(..., densify((industry+1)*10 + exchange))` — layered
  neutralization + decay + fine-grained custom grouping, all in one
  expression.
- **Turnover-controlled fundamental ratio:**
  `hump(group_neutralize(quantile(<fundamental ratio>), sector),
  hump=<threshold>)` — quantile-transform, sector-neutralize, then
  turnover-gate with `hump`.
- **Geometric-mean-based composite:**
  `power(ts_product(returns + 1, d), 1/d)` — geometric mean of returns
  over `d` days; noted in community sources as numerically preferable to
  arithmetic mean for compounding-return-style aggregation, and can be
  stabilized further via `exp((1/d) * sum(log(x)))` if `x` risks
  near-zero/negative values.

---

## 11. Operator-Tier Awareness for the Generator

Community documentation explicitly notes operators unlock progressively
by account level (base → Expert → Master → Grandmaster-tier operators
being more advanced/exotic). Practical implications:

- The `catalog_sync` step (§0) should tag each operator with its
  required tier, sourced from your live session's actual Operators tab
  (which only *shows* operators your account can use, but doesn't always
  make the tier boundary explicit in the UI — check API response
  metadata if available).
- Template and LLM-mechanical generation paths should **only draw from
  operators confirmed available to the live account**, not from this
  static reference — this file may include operators your specific
  account tier doesn't have access to yet.
- If a generated candidate simulation fails with an operator/permission
  error rather than a data/logic error, route it to a distinct rejection
  reason (extend Doc 3 §8's enum with `operator_unavailable`) so it's not
  confused with an actual idea-quality failure.

---

**Doc map:** `FINDING_ALPHAS_GUIDE.md` (theory) → `02_BRAIN_MECHANICS.md`
(scoring/checks) → `03_PIPELINE_CHECK_LOGIC.md` (stage wiring) →
`04_BRAIN_OPERATORS.md` (this doc — the expression vocabulary the
generator and sweep stage actually manipulate).
