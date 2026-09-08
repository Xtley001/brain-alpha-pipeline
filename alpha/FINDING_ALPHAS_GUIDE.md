# Finding Alphas — Distilled Engineering Reference

**Purpose:** This document translates *Finding Alphas: A Quantitative Approach
to Building Trading Strategies* (Tulchinsky et al., WorldQuant, 2nd ed.) into
an operational reference for the BRAIN Alpha Pipeline. It is organized so
each section maps onto a concrete decision the pipeline (or the LLM agents
generating/screening candidates) has to make: what makes an idea worth
testing, what metrics gate it forward, how to avoid fooling yourself, and
which idea families to draw from when the candidate queue runs dry.

Use this as the shared vocabulary between the README's pipeline stages
(`Stage 0 screen -> settings sweep -> local filter -> correlation check ->
alert`) and the underlying quant theory that justifies each gate.

---

## 1. What an Alpha Actually Is

An alpha is **not** "a good idea about the market" — it's a fully specified,
executable function: `input data -> alpha value vector -> position sizes`.
Concretely, for a universe of instruments on a given day, an alpha assigns a
signed weight to each instrument; positive weights are long, negative are
short, and the magnitude is a relative dollar allocation. That vector is
proportional to the money the strategy wants to hold in each name.

Two framings matter for pipeline design:

- **Alpha as hypothesis.** Every alpha expression should trace back to a
  falsifiable statement about *why* a data change should predict a price
  change (Table: `1/price` → "invest more when price is low";
  `correlation(price, delay(price,1))` → "trending stocks outperform"). If a
  generated candidate can't be restated as a one-sentence causal hypothesis,
  it's a data-mining artifact, not an alpha idea — flag it for extra
  scrutiny in the LLM-reasoning generation path.
- **Alpha as statistical arbitrage, not prophecy.** Single-stock,
  single-day predictions are not reliable; alphas only work "in aggregate,"
  across many instruments and many days. This is why per-candidate
  screening must always look at *distributional* properties (quintile
  spread, sector spread, drawdown shape) and not just headline IR.

### The five-step construction loop (mirrors the pipeline's tick loop)

1. Analyze the variables in a dataset.
2. Form a hypothesis about the price response to a change in that data.
3. Translate the hypothesis into a mathematical expression → positions.
4. Test the expression (Stage 0 screen → sweep → local filter).
5. If favorable, surface it (correlation check → Telegram alert to human).

---

## 2. The Three Axes of Alpha Design (TAP)

Every alpha (and every *batch* the generator produces) should be placed
deliberately along three axes, generalizing a single idea into a family
instead of one-off signals:

| Axis | Examples |
|---|---|
| **Ideas & Datasets** | reversion, momentum, seasonality, ML/learned signals, lead-lag; price-volume, fundamentals, analyst data, sentiment, social media, options |
| **Regions & Universes** | US / Europe / Asia / global; TOP200–TOP3000 liquidity bands, sector/industry subsets, single-instrument groups |
| **Performance Parameters** | high return, high Sharpe/IR, low cost (margin), low drawdown |

**Operational use:** when the candidate queue needs topping up, don't just
regenerate variations of the last idea. Freeze one axis and vary the other
two systematically (e.g., "momentum, fixed" → sweep across universes and
objective functions before moving to a new idea family). This is exactly
the discipline that prevents a portfolio of "diverse-looking" alphas that
are secretly all the same trade with different decay parameters.

---

## 3. Data Inputs

### 3.1 Data categories

- **Prices & volumes** — technical/regression models, highest turnover.
- **Fundamentals** — quarterly-cadence, low turnover, requires point-in-time
  handling (see §6.1).
- **Macro** — GDP, employment; market-wide, event-driven jumps.
- **Text** — filings, news, transcripts, social media; needs NLP/sentiment
  scoring before use.
- **Multimedia** — audio/video converted to text, niche but growing.
- **Risk/relationship data** — not directional signals themselves; used to
  *reduce noise* in other alphas (risk-factor neutralization, correlated
  instrument pairs).

### 3.2 Data selection heuristics for automated/LLM-driven idea generation

- **Prefer unitless, cross-sectionally comparable ratios** over raw levels.
  Raw earnings isn't comparable across firms; earnings/revenue is. Reject
  candidate expressions that mix incompatible units (e.g., `price + volume`)
  — this is a strong, cheap pre-Stage-0 filter.
- **Avoid ratios with a denominator that can approach zero** (e.g., raw P/E
  diverges near zero earnings; prefer E/P). Flag any generated expression
  with a raw division where the denominator isn't bounded away from zero.
- **Restrict input-category diversity per alpha.** Mixing many
  differently-cadenced data categories (quarterly fundamentals + tick price
  data + sporadic insider filings) in one expression increases overfitting
  risk disproportionately. Cap category count per candidate, especially for
  the mechanical/LLM-generated path.
- **New/lesser-known data > well-trodden data**, all else equal — crowding
  arbitrages away known signals faster. Weight novelty in idea scoring.
- **Data usability checklist before ever touching alpha logic:**
  - Is every data point **dual-timestamped** (occurrence time vs. arrival
    time)? If only occurrence time exists, assume look-ahead risk.
  - Will the data source **keep being produced** on a reliable schedule?
    (Discontinued feeds can't support live production even if backtests
    look great.)
  - Is there a **survivorship** angle — did a vendor cherry-pick this
    series from many failed attempts?

---

## 4. Alpha Design Decisions

- **Universe**: asset class, region, sector, or explicit instrument list.
  Usually driven by data coverage, but can be deliberately narrowed even
  when data is wider (e.g., restrict to sectors where the idea plausibly
  applies rather than letting noise dilute the signal).
- **Prediction frequency**: tick / intraday / daily (delay-0 snapshot,
  delay-1, MOO/MOC) / weekly / monthly. Frequency should match the natural
  cadence of the underlying data — forcing high-frequency predictions from
  quarterly fundamentals just produces turnover spikes with no informational
  content behind them.
- **Value is context-dependent**: an alpha's contribution to a *portfolio*
  is not identical to its standalone backtest, because of nonlinear
  crossing effects when many alphas combine (§8). Standalone metrics
  (§5) are still the right *gate*, but shouldn't be over-interpreted as the
  alpha's "true" worth.

---

## 5. Evaluation Metrics — the Screening Vocabulary

These are the numbers Stage 0 / sweep / local-filter should compute and
threshold on.

| Metric | Definition | Rule of thumb |
|---|---|---|
| **Information Ratio (IR)** | mean(daily return) / std(daily return) × √256 | ~1.0 annualized is a reasonable bar for a unique, lightly-fit alpha over 5 years; real alphas (some fitting, some correlation) often run a bit higher |
| **Margin** | PnL / $ traded | ~5 bps/day is generally acceptable; low margin = highly cost-sensitive, only useful if very uncorrelated |
| **Correlation (max, to pool)** | Pearson/temporal/PnL or position correlation vs. existing alphas | `<0.3` good · `0.3–0.5` acceptable · `0.5–0.7` borderline (must excel elsewhere) · `>0.7` reject unless dramatically better |
| **Turnover** | avg $ traded / book size | Must be evaluated against margin — high turnover kills low-margin alphas after cost |
| **Max drawdown** | peak-to-trough loss / (booksize/2) | Compare to annualized return; a sudden one-off drop vs. slow bleed says different things about robustness |
| **% profitable days** | fraction of positive-PnL days | Sanity metric, not a primary gate |
| **Quintile/decile spread** | avg return by alpha-value bucket | Want monotonic spread across all buckets, not just the tails carrying everything |
| **Sector/PnL concentration** | PnL share by GICS sector | Flag alphas where 1–2 sectors generate ~all the PnL — fragile to regime change in just that sector |

### 5.1 Correlation math (for the correlation-check stage)

- **Pearson PnL correlation** — standard; use 2–4 years of daily PnL
  vectors, not full history (compute cost + relevance).
- **Temporal-weighted correlation** — weight recent days more heavily
  (e.g., `w_t ∝ 1/(n-t+1)`) before computing Pearson; captures whether two
  alphas are *currently* converging even if historically decorrelated.
- **Position correlation** vs. **trading (delta-position) correlation** —
  position correlation over a rolling window (~20 days × universe size) can
  matter as much as PnL correlation, especially for alphas about to be
  combined into the same book.
- **Pool-level statistics**, not just max: track **T-corr** (sum of
  correlations vs. all pool members) and the full correlation **histogram**
  once the pool is large — max-correlation alone under-weights an alpha
  that's moderately correlated with *everything*.

### 5.2 What "quality" looks like qualitatively

- Simple idea, simple/elegant expression.
- Not sensitive to small parameter perturbations (test this explicitly —
  perturb decay/lookback windows ±20% and confirm IR doesn't collapse).
- Works across multiple universes and multiple regions.
- Story is explainable in one sentence, grounded in an economic mechanism
  — not merely "it back-tested well" (see World-Cup "3,964 formula" — a
  numerically perfect but mechanism-free pattern is not an alpha).

---

## 6. Bias Control — What Kills a Backtest's Credibility

Treat this section as a mandatory pre-flight checklist before any candidate
reaches Stage 0.

### 6.1 Look-ahead bias

- Every field needs **dual timestamps**: occurrence datetime vs. arrival
  datetime. Signals must key off *arrival*, not occurrence.
- Normalize timezones across data sources for strategies spanning regions.
- For ML components: hyperparameters must be tuned on backward-looking
  data only — never on the full sample including the test window.
- Point-in-time fundamentals (post-restatement data leaking backward) is a
  classic, easy-to-miss leak — verify the fundamentals provider delivers
  as-reported-at-the-time values, not restated historicals.

### 6.2 Data mining / overfitting

- Use **holdouts**: a time-series holdout (a withheld trailing window, or
  interleaved withheld periods) and/or an asset holdout (a withheld,
  statistically-representative subset of the universe). Validate on the
  holdout *after* the model is frozen.
- **Formulation bias** — don't cherry-pick which of several plausible
  formulations (3 vs 6 vs 12-month momentum window) performed best in
  sample; either commit to an a-priori choice or blend formulations with
  unbiased weights (equal-weight, risk-parity).
- **Batch-level, not candidate-level, validation** for automated search: if
  the generator produces N candidates from one search space, judge the
  *average* out-of-sample IR of the whole batch, not the best individual
  survivor. Selecting only the winners after seeing out-of-sample
  performance re-contaminates "out-of-sample" into "in-sample."
- **Longer backtests reduce false-positive risk but aren't free** — the
  number of random-noise strategy configurations needed to spuriously
  clear a given Sharpe bar rises steeply with window length (e.g., roughly
  hundreds of trials needed to spuriously clear IR≈1.0 over 250 days, but
  tens of millions to spuriously clear IR≈3.0 over the same window) — so
  raising the in-sample IR bar and lengthening the window are both valid,
  complementary levers against overfitting, not substitutes for holdouts.

### 6.3 Systematic behavioral biases to check for in generated ideas

- **Storytelling / theory-fitting** — a plausible-sounding narrative
  invented *after* seeing good backtest results. Guard: require the
  hypothesis be written down *before* the backtest is run (the pipeline's
  candidate spec should capture "idea" text prior to Stage 0 execution).
- **Confirmation bias** — over-weighting "the latest research" or
  buzzword-driven ideas without independent verification.
- **Familiarity bias** — defaulting to the same universe (S&P 500) or the
  same idea family (momentum/reversion) repeatedly because it's what's been
  explored before; use the TAP axes (§2) to force diversification.
- **Herding** — many quants converge on the same well-known factors via the
  same academic papers; correlation checks (§5.1) are the direct technical
  defense against this becoming a portfolio-level problem.
- **Narrow framing** — evaluating a candidate purely on its own merits
  without checking correlation to the existing pool; this is precisely why
  correlation-check is a *separate, mandatory* pipeline stage rather than
  a metric bundled into Stage 0.

---

## 7. Turnover, Decay, and Cost Control

- **Turnover** = avg $ traded per day / book size. Driven directly by how
  fast the *underlying data* changes — daily-price-driven signals are
  naturally high turnover; quarterly-fundamentals-driven signals are
  naturally low, but can show artificial turnover *spikes* around release
  dates if not smoothed.
- **Smoothing techniques** (apply during the sweep stage as parameterized
  variants of a candidate, not as one-off manual tweaks):
  - **Clamping/winsorizing** extreme input values (outlier control).
  - **Humped delta** — ignore changes below a threshold, hold prior value;
    trades become sparser but larger/more concentrated in time.
  - **Linear / exponential decay** — smooth the signal over a window;
    reduces turnover with a smoother trading profile than the hump method.
- **The crossing effect** matters at the *portfolio* level: an individual
  alpha's after-cost margin can look weak in isolation but still be
  valuable if its trades largely offset (cross) against other alphas in the
  combined book, avoiding the spread cost entirely. Don't reject a
  candidate purely on weak standalone after-cost margin if it's
  structurally likely to cross well (e.g., contrarian to the existing
  pool's net flow) — flag these for human judgment rather than auto-reject.
- **Universe liquidity interacts with turnover cost non-linearly** — the
  same turnover number is far more expensive on a wide, less-liquid
  universe than a narrow, liquid one. Sweep across universe size
  (TOP500/TOP1000/TOP3000) as part of the settings sweep, and evaluate
  after-cost margin per universe rather than assuming a single universe
  choice generalizes.

---

## 8. Robustness Techniques (apply during sweep / local-filter)

Three families, useful as concrete transforms to try when sweeping a
candidate expression:

1. **Ordering methods** — rank-based transforms. Cross-sectional
   **ranking** (rescale to [0,1]) makes an alpha invariant to monotone
   transformations of the input and is far more stable under
   non-stationary/non-linear inputs than raw values. Prefer rank-based
   correlation (Spearman-style) over raw Pearson when inputs are heavy
   tailed.
2. **Normalization / distribution transforms** — Z-scoring (zero mean,
   unit variance) and the Fisher transform (for bounded variables like
   correlations) stabilize inputs that are roughly normal but
   outlier-contaminated.
3. **Limiting methods** — **trimming** (drop extreme tail observations) and
   **winsorizing** (cap extremes at a cutoff rather than dropping them).
   Winsorizing is generally preferred in production alphas because it
   preserves the instrument in the universe rather than removing it.

**Neutralization** (industry/sector/market/subindustry demeaning) should be
a standard sweep dimension — most raw ideas benefit substantially from at
least industry-neutralization, and comparing neutralized vs.
un-neutralized variants is a cheap, high-value sweep axis.

**Drawdown-specific robustness check — bootstrapping:**
1. Estimate the alpha's PnL autocorrelation structure.
2. Generate many (e.g., 1,000) synthetic multi-year PnL paths by
   resampling PnL blocks (sized to the autocorrelation period) with
   replacement.
3. Take the 90th-percentile max-drawdown across synthetic paths as the
   **bootstrapped drawdown** estimate.
If the *realized* backtest drawdown looks controlled but the
*bootstrapped* drawdown doesn't improve after a fix, the risk was masked,
not actually reduced — this is a good candidate for an automated
local-filter check on any parameter change that "fixes" a drawdown.

---

## 9. Automated / Batch Search — Directly Applicable to This Pipeline

This is the most directly relevant section to the pipeline's
template/LLM-reasoning/LLM-mechanical generation paths.

- **Judge batches, not individual candidates**, when candidates come from
  the same search space/prompt template. Track average in-sample and
  out-of-sample IR *across the whole batch* produced by a given
  template/prompt; if the batch average doesn't clear a bar, discard the
  whole batch rather than cherry-picking the few survivors (this avoids
  reintroducing selection bias — see §6.2).
- **Yield test**: periodically feed a deliberately noisy/nonsensical input
  set through the same generation+screening pipeline as a control. A
  healthy search space/prompt should produce a markedly higher yield of
  passing candidates than the noise control. If yields converge, the
  screening pipeline itself may be too permissive (an actionable pipeline
  health metric, not just an alpha-quality metric).
- **Narrow the search space before generating**, don't rely on
  post-hoc filtering alone:
  - Screen out expressions with dimensionally nonsensical combinations
    (units that can't be added/multiplied meaningfully).
  - Screen out functions applied outside their valid domain (e.g., `log`
    of a value that can go negative).
  - Match data cadence to intended prediction frequency (don't feed
    quarterly fundamentals into an intraday-frequency template).
- **Reuse intermediate variables** (e.g., a computed E/P ratio) across
  candidate generations rather than recomputing raw combinations each time
  — cheaper and mirrors how strong intermediate variables recur across many
  good alphas.
- **Depth vs. breadth** — prefer expanding the search space (more input
  data, more trial-function *types*) over increasing expression *depth*
  (nesting more operators on the same few inputs). Depth-first search
  produces noise that fits in-sample and fails out-of-sample much faster
  than breadth-first search.
- **Iterative/coarse-to-fine backtesting** — run a first pass on a short
  window / coarse parameter grid to cheaply prune candidates, then only
  extend the window / fine-tune parameters for survivors. Each successive
  round should also *extend* the backtest window (not just narrow the grid)
  so later rounds act as a quasi out-of-sample check on earlier rounds.

---

## 10. Risk and Drawdown Framework

- **Extrinsic risk** — exposure to known, external factors (industry,
  market beta, well-known style factors like value/momentum/size). This
  should generally be **neutralized or hedged**, not treated as alpha.
  Track factor loadings (regression against Fama-French / Barra-style
  factors) for any candidate before it's alerted — an idea that's secretly
  just re-deriving the momentum factor is not novel, even with a low
  correlation to the existing *alpha* pool, if it's highly loaded on a
  well-known *risk factor*.
- **Intrinsic risk** — what's left after neutralization; this is what
  actually should drive expected return. Measured via volatility, value at
  risk, expected tail loss, and drawdown. This should scale position
  sizing (book size should shrink when intrinsic risk measures spike, e.g.
  via VIX-style regime proxies) rather than being static.
- **Event risk** — a known-in-advance event (earnings, central bank
  meetings) that can temporarily dominate an alpha's normal drivers. Where
  predictable, candidates sensitive to such events should either reduce
  exposure ahead of the event or be explicitly flagged as event-driven
  (different evaluation standard — see §12.9).
- **"Just get out" cases** — some risks (extreme/unprecedented news,
  correlation-structure breaks, counterparty risk) aren't measurable ex
  ante. No metric threshold substitutes for a human review step here —
  this is part of why the pipeline routes to a human via Telegram rather
  than auto-submitting.

---

## 11. Alpha and Risk Factors — Don't Rediscover the Wheel

A large fraction of "new-looking" alphas are actually re-expressions of
well-documented risk factors (market, size, value, profitability,
investment [Fama-French 5-factor]; momentum, liquidity, accruals as
prominent factors outside that model). These factors:

- Have **compressed Sharpe ratios** precisely because they're well known
  and heavily arbitraged (e.g., published value-factor Sharpe roughly
  halved from the pre-1990 period to the post-1990 period on Kenneth
  French's long-run series).
- Can require **large long/short liquidity imbalances**, which is
  operationally undesirable even if the paper Sharpe looks fine.
- Are **crowded** — synchronized deleveraging by large holders in a
  popular factor was implicated in the August 2007 "quant crash."

**Pipeline implication:** run a factor-neutralization step on any
candidate whose top-line performance looks unusually good — if performance
survives neutralizing against momentum/size/value, it's much more likely
to be a genuine new alpha rather than a repackaged risk factor. This is a
good candidate for a dedicated "factor regression" sub-check inside Stage
0 or the local filter.

---

## 12. Idea Families — A Menu for the Generator

Use this as the taxonomy for the template library and for prompting the
LLM-reasoning generation path when the queue needs topping up with a
*specific, well-scoped* family rather than an open-ended "think of an
alpha" prompt.

### 12.1 Price-volume

- Momentum-reversion depends heavily on **time horizon**: reversion
  dominates intraday/daily; trend/momentum dominates over weeks-to-months;
  and *within a correlated group* (same industry), individually strong
  performers tend to revert relative to peers even when the single-name
  trend is still positive.
- **Integer/round-number effects** — human order-entry clusters around
  round numbers; price-level psychology (asymmetric loss aversion,
  disposition effect) is a legitimate, if soft, signal family.
- Price-volume signals gain power when **combined with event data**
  (e.g., volume shocks around earnings dates predict subsequent returns
  better than volume alone).

### 12.2 Fundamental / financial-statement

- Balance sheet: liquidity improvement, sales/assets improvement, no new
  equity issuance, declining leverage → historically positively correlated
  with forward returns (Piotroski-style).
- Income statement: positive net income, improving net income/assets,
  improving gross margin.
- Cash flow: operating cash flow > 0 and > net income (quality-of-earnings
  signal — accrual-heavy earnings are a *weaker* predictor of future
  earnings than cash-flow-heavy earnings).
- Growth-specific factors (for low book-to-market names): R&D/assets,
  capex/assets, ad spend/assets above industry median, alongside
  low earnings/cash-flow variance vs. industry median.
- Negative/short-side factors: earnings manipulation red flags, high
  sales-growth-vs-cash-flow divergence, recent equity issuance, recent
  M&A history, high financial leverage (ex-operating-liabilities).
- **Always express as rate-of-change / YoY**, not raw levels, to avoid
  seasonality contaminating quarter-over-quarter comparisons. Use
  point-in-time data (§6.1).

### 12.3 Momentum

- 3–12 month winners/losers tend to persist (classic cross-sectional
  momentum), but profitability has **compressed since 2008** and the
  factor is prone to sharp, sudden drawdowns during reversal regimes —
  size positions and stops accordingly, don't just trust the long-run
  average Sharpe.
- Momentum is **stronger** for: growth stocks vs. value, low
  analyst-coverage names, higher-volume names, and around
  quarter-ending months (institutional window dressing).
- Consider **industry/group momentum** and **lead-lag effects** within a
  correlated group as a distinct sub-family from single-name momentum.
- If a candidate loads heavily on price momentum *unintentionally*,
  neutralize it — see §11.

### 12.4 News & social media

- Score along four axes, not just polarity: **sentiment** (good/bad,
  normalized 0–100), **novelty** (new story vs. rehash — impact decays
  with lower novelty), **relevance** (how targeted the news is to a
  specific name), **category** (earnings vs. legal vs. macro — different
  categories have different reaction speeds/half-lives).
- **Expected vs. unexpected** matters more than raw sentiment — good news
  that's already priced in (below consensus) can still cause a decline.
- Large caps + expected news → tends to overshoot-then-reverse; small caps
  + unexpected news → tends to drift/continue. Design decay/holding period
  differently for each quadrant.
- Social media (esp. Twitter) is higher-volume, noisier, and more prone to
  fake signals than curated news — treat as a distinct, lower-trust data
  category requiring extra novelty/verification filtering.

### 12.5 Options-market-derived

- **Volatility skew** (IV of OTM puts vs. calls) — high skew predicts
  underperformance; reflects informed traders' negative-information demand
  for downside protection.
- **Volatility spread** (call IV − put IV beyond the early-exercise
  premium) — high spread predicts outperformance.
- **Option-to-stock volume ratio (O/S)** — high O/S predicts
  underperformance (informed traders lean on options when short-sale costs
  are high).
- **Open interest changes** (especially put open interest) — rising put OI
  relative to call OI predicts underperformance.

### 12.6 Analyst / institutional research

- Usable signal families: consensus buy/sell rating changes, price-target
  vs. current-price gaps, earnings-estimate revisions/growth, earnings
  surprises (actual vs. estimate), earnings-call sentiment/Q&A tone,
  coverage drops (especially on large caps — a proxy for "analyst wants to
  quietly go negative without a formal downgrade").
- Structural biases to account for when weighting these signals: analysts
  are net **positively biased** (buy >> sell ratings), prone to
  **herding** around consensus, and prone to **dropping coverage** rather
  than issuing sell ratings on names they're bearish on.

### 12.7 Event-driven

- Distinct sub-strategies: merger arbitrage (deal-spread capture, hedged
  by shorting the acquirer in stock deals), spin-off/split-off/carve-out
  drift (parent + spin-off both tend to outperform post-separation),
  distressed-asset reversion, index-rebalancing arbitrage (anticipate
  adds/deletes ahead of forced institutional flows — strongest in
  small/micro-cap indices like Russell 2000/Microcap, much weaker in
  large-cap indices), capital-structure arbitrage (equity vs. bonds/CDS of
  the same issuer).
- These are **naturally low-turnover, event-clustered** signals — don't
  force them into a continuous daily-signal shape; model them as
  discrete entry/exit triggers around known event dates.

### 12.8 ETFs and index products

- Distinct alpha sources vs. single stocks: **index-arbitrage** (futures
  fair value vs. actual), **rebalancing market impact** (strongest in
  small-cap/less-liquid indices like Russell 2000, weak-to-absent in
  broad/large-cap indices), **captive capital-raise mispricing** (e.g.,
  REITs raising equity around index-inclusion dates at abnormally thin
  discounts), **index-vs-nonindex valuation premia/discounts** (small caps:
  index members trade at a *premium*; large caps: index members trade at a
  *discount* — direction flips by cap segment, don't assume one sign).
- **Watch for near-duplicate instruments** (SPY/IVV/VOO all track the same
  index) — don't let a screen assign opposite signs to functionally
  identical ETFs; and watch for inverse/leveraged ETFs silently doubling
  up market-beta exposure inside a nominally "dollar-neutral" book.
- ETF universes are **much smaller and more liquidity-concentrated** than
  equities (a handful of names dominate total ETF volume) — overfitting
  risk is proportionally higher; be more conservative with in-sample
  metric bars for ETF-universe candidates.

### 12.9 Futures & forwards

- Futures/forwards naturally segment into **sector groups** driven by
  distinct trader populations (commodity producers/consumers, currency
  hedgers, rate desks) with much **weaker cross-sector correlation** than
  equities — don't backtest a futures alpha across an undifferentiated
  "all futures" universe; test within sector-consistent groups.
- Smaller per-group universes mean **lower expected Sharpe from breadth
  alone** (Sharpe scales with √breadth) — futures alphas need
  proportionally stronger per-instrument signal to compensate, and
  cross-validation via leave-one-out (does the effect hold with any single
  instrument removed?) is especially important given how few instruments
  populate some groups.
- Idea families specific to this asset class: **COT-report positioning**
  (follow speculative/"smart money" open-interest changes), **seasonality**
  (harvest/heating cycles — strongest in ags/energy, weak in rates/
  non-commodity FX), **risk-on/risk-off regime** (VIX level, yield-curve
  shape, sector/EM-vs-DM flows as regime indicators; correlations across
  asset classes rise sharply in risk-off regimes), and **carry /
  contango-backwardation** (long backwardated, short contangoed
  instruments; profits from both roll yield and convergence, but is
  vulnerable to sudden risk-off unwinds).

### 12.10 Intraday / market microstructure

- Bid-ask spread and order-book depth directly determine after-impact
  cost — any intraday-frequency candidate should be evaluated with
  execution-cost modeling from real order-book depth, not just a flat
  spread assumption.
- **Illiquidity premium**: wider-spread names carry a real expected-return
  premium to compensate liquidity providers; a rough rule of thumb from
  the literature is roughly a 0.2%-ish monthly excess-return effect per
  1% of spread — useful as a sanity-check magnitude, not a hard constant.
- **Probability of informed trading (PIN)** and related microstructure
  measures are usable both cross-sectionally (higher-PIN names show higher
  expected returns, reflecting adverse-selection compensation to
  liquidity providers) and as an early-warning **time-series** signal —
  spikes in informed-trading proxies have preceded major liquidity events
  historically (flash crashes, bubble peaks) — worth monitoring as a
  regime/risk overlay, not just a stock-selection signal.
- Robust, U/reverse-J-shaped **intraday patterns** exist in volume,
  spread, and volatility (thin/wide near the open and close vs. mid-day) —
  intraday alphas should be volume/spread-time-of-day-aware, not
  uniform-weighted across the trading day.

---

## 13. Machine Learning Notes

- Frame the problem type explicitly before picking a method: **regression**
  (continuous return forecast), **classification** (up/down, regime label),
  or **clustering** (grouping instruments/features with no labeled target).
- **Model family trade-offs** relevant to a fast-iterating pipeline:
  - *Statistical models* (logistic regression, naive Bayes, HMM) — cheap,
    interpretable, tolerant of missing data, but limited expressiveness;
    good default/baseline before reaching for anything heavier.
  - *SVM* — strong theory, robust, but training-cost-heavy and awkward to
    parallelize; a good candidate to skip inside a fast automated-sweep
    loop where iteration speed matters most.
  - *Neural nets* — powerful, opaque, favor problems with abundant data
    and compute; treat as a "later stage" tool for the highest-conviction,
    already-vetted ideas rather than the default generation path.
  - *Ensembles* (random forest, boosting) — combine weak signals well,
    scale/parallelize nicely; a natural fit for combining several
    already-existing weak alphas into a stronger composite rather than for
    single-signal generation.
- **Same overfitting rules apply, doubled**: any ML component still needs
  out-of-sample and holdout validation, and hyperparameters must be tuned
  only on backward-looking data (§6.1). ML doesn't get an exemption from
  the bias-control checklist — if anything it needs stricter enforcement
  because it has more free parameters to silently overfit with.

---

## 14. Cutting Losses — Portfolio-of-Alphas Discipline

This is the philosophy that should govern how the pipeline (and the human
reviewing Telegram alerts) treats the *pool* of live/candidate alphas over
time, not just individual candidate screening:

- **No alpha (or rule) works forever.** Every signal has a finite, unknown
  shelf life; expect decay and design for graceful retirement, not
  permanence.
- **Pre-commit an exit rule before deploying**, not after a drawdown starts
  — define in advance what drawdown magnitude / IR degradation / duration
  triggers a re-review, so the decision isn't made emotionally mid-drawdown.
- **Diversify and let performance arbitrate.** Run many uncorrelated ideas
  simultaneously; don't over-commit belief to any single "great idea" no
  matter how compelling the backtest story is — track record, not
  narrative conviction, should drive which alphas stay in the pool.
- **Signals of a strategy breaking** (worth encoding as pool-level
  monitoring, not just at initial screening): drawdown exceeding any
  previously observed historical drawdown, materially falling live Sharpe
  vs. backtest Sharpe, and a documented rule from the backtest failing to
  hold up in live behavior.

---

## 15. WebSim / BRAIN-Style Simulation Conventions

These conventions (from WorldQuant's own public simulator) map closely
onto BRAIN and are useful defaults for the sweep stage's parameter grid:

- **Region / Universe** — top-N liquidity band per region (e.g.,
  TOP200…TOP3000); always a first-class sweep dimension, not a fixed
  assumption baked into the candidate.
- **Delay** — Delay-0 (same-day snapshot before a cutoff) vs. Delay-1
  (prior-day data only). Delay-0 without a hard time cutoff risks
  look-ahead; default to Delay-1 unless the data's arrival-timestamp
  discipline is verified.
- **Decay** — linear-weighted blending of today's value with prior days';
  primary lever for trading off responsiveness against turnover cost.
- **Max stock weight** — position cap per instrument (typically ~5–10% of
  book); larger universes should generally get smaller caps, smaller
  universes can tolerate larger caps.
- **Neutralization** — market/industry/sector/subindustry demeaning;
  sweep with and without as a standard grid dimension (§8).
- **Lookback window** — how much history each daily computation can see;
  doesn't change alpha *values* but does gate what data can be used
  (longer lookback needed for low-frequency fundamentals) and affects
  simulation cost/speed.
- **Standard book size convention** for comparability across sweeps: hold
  book size fixed within a sweep batch so IR/margin/turnover are
  comparable across parameter variants of the *same* candidate.

---

## 16. Pipeline Stage ↔ Book-Concept Cross-Reference

Quick lookup from the README's stage names to the sections above:

| Pipeline stage | Primary concepts to apply |
|---|---|
| **Candidate generation** (template / LLM-reasoning / LLM-mechanical) | §2 TAP axes, §3.2 data heuristics, §9 batch/yield discipline, §12 idea-family menu |
| **Stage 0 screen** | §5 core metrics gate, §6.1–6.2 look-ahead/mining pre-checks, §3.2 unit/domain sanity checks |
| **Settings sweep** | §7 turnover/decay grid, §8 robustness transforms (rank/winsorize/neutralize), §15 WebSim-style parameter grid |
| **Local filter** | §5.2 qualitative quality checks, §8 bootstrapped-drawdown check, §11 factor-neutralization check |
| **Correlation check** | §5.1 correlation math (Pearson/temporal/position, T-corr, histogram) |
| **Telegram alert → human review** | §10 "just get out" judgment calls, §14 portfolio-of-alphas fit, event-driven/qualitative context the metrics can't capture |
| **Queue top-up trigger** | §9 batch/yield health as a pipeline-quality signal, §2 TAP-axis-forced diversification |

---

## 17. Quick-Reference Checklists

### Before a candidate is generated
- [ ] Idea stated as a one-sentence causal hypothesis
- [ ] TAP axis explicitly chosen/varied (not accidental repeat of prior idea family)
- [ ] Data category count kept low; units/dimensions consistent
- [ ] Denominators bounded away from zero

### Before a candidate passes Stage 0
- [ ] Dual-timestamped, point-in-time data confirmed (no look-ahead)
- [ ] IR, margin, turnover computed and thresholded
- [ ] Quintile spread checked (monotonic, not tail-only)
- [ ] Sector/PnL concentration checked

### Before a candidate passes the sweep
- [ ] Swept across universe size, delay, decay, neutralization
- [ ] Parameter sensitivity confirmed (no cliff-edge fragility)
- [ ] After-cost margin evaluated per universe (not just headline universe)

### Before a candidate passes correlation check
- [ ] Max correlation vs. pool computed (Pearson + temporal-weighted)
- [ ] T-corr / histogram reviewed if pool is large
- [ ] Factor-neutralization check run if performance looks unusually strong

### Before alerting a human
- [ ] Bootstrapped drawdown checked, not just realized drawdown
- [ ] Batch-level stats available if this came from an automated search batch
- [ ] Clear one-paragraph hypothesis + metrics summary ready for the Telegram message
