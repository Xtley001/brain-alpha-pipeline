# Options Alpha Knowledge Base — Master (Books 1–4)

**Status:** Books 2, 3, 4 fully processed. Book 1 (*Volatility Trading*, Sinclair) now has two extraction passes merged — Part 1/10 (Ch. 1–7, first pass) plus a second consolidated pass over Ch. 1–7 that surfaced additional cards the first pass missed. **Note:** a later extraction pasted into this thread was labeled "Book 2" by the person doing the extraction, but its own source line confirms it's the same Sinclair book, not a new source — merged here rather than filed separately. Book 1 still hasn't had a dedicated pass over any skew/forward-basis/pcr-flow material it may contain beyond what's captured below. Book 5 not started.

**Sources:**
- **Book 1** — *Volatility Trading*, Euan Sinclair (Part 1/10 only)
- **Book 2** — Equity derivatives / volatility trading handbook (Ch. 1–7 + Appendix)
- **Book 3** — *The Volatility Smile*, Derman & Miller (Ch. 1–24)
- **Book 4** — *Option Volatility and Pricing*, Natenberg (full text, single pass)

Intended use: reference input for `brain_options/llm/prompts.py` — feed relevant sections to the reasoning/mechanical tiers when generating or mutating candidates for a given archetype.

---

## 1. FORWARD-BASIS

### Forward ≠ stock: dividend/borrow risk in delta hedging
**Idea:** Long call − short put = a forward, not stock — a forward excludes soon-to-go-ex dividends. Hedging with the wrong instrument (stock vs. matched forward) silently leaks dividend/borrow risk equal to the option's delta.
**Heuristic:** Confirm hedge-instrument match before trusting a hedged-P&L signal; a drift between theory and hedged P&L in dividend-paying names is often unmodeled dividend leakage, not alpha.
**Pitfall:** Borrow cost is often priced asymmetrically by market makers (only into the delta-positive leg), creating a convention-driven bid-offer gap that looks like mispricing but isn't.
**Source:** Book 2, Ch. 2.1.

### Zero-delta straddle strike sits above spot
**Idea:** An ATM straddle is not zero-delta; the true zero-delta strike is `strike(%) = e^((r+σ²/2)T)`.
**Heuristic:** For a pure-vol-view straddle, solve for the zero-delta strike rather than defaulting to ATM, or you introduce unwanted directional exposure.
**Expression sketch:** `zero_delta_strike_pct = exp((r + 0.5*sigma^2)*T)`
**Pitfall:** Negligible for short-dated/low-vol names; matters mainly for longer-dated or high-vol underlyings.
**Source:** Book 2, Ch. 2.1.

### Forward price is the true fair-value anchor, not spot
**Idea:** Options price off the forward (spot adjusted for carry/dividends), not spot itself.
**Heuristic:** Back-solve implied forward via put-call parity `C − P = (F − X)/(1+rt)`; a material gap between implied and carry-model forward flags a rate/dividend surprise — or a stale-quote problem, which must be ruled out first.
**Expression sketch:** `feature = (implied_forward - carry_model_forward) / spot`, cross-sectionally ranked.
**Pitfall:** Stale/wide-quote strikes produce spurious "dividend surprises" — require tight, contemporaneous near-the-money quotes.
**Source:** Book 4 (Natenberg), Ch. 2, Ch. 15.

### At-the-forward ≠ at-the-money
**Idea:** The true 50-delta strike is at-the-forward, not spot-ATM, when carry/dividends are nonzero — the gap widens for long-dated, high-rate, low-dividend names.
**Heuristic:** Anchor "ATM implied vol" benchmarks to at-the-forward strike, not spot-ATM, for long-dated tenors or high-rate regimes; using spot-ATM biases the benchmark in the direction carry pushes the forward.
**Pitfall:** Negligible in short-dated, low-rate, liquid index options — not worth the added complexity there.
**Source:** Book 4, Ch. 5, 9, 18.

### Basis sign flips with convenience yield / dividend-vs-carry mismatch
**Idea:** Basis (cash − forward) is usually negative for financials (carry dominates) but flips positive when a benefit-of-holding-now (convenience yield, high dividend yield vs. rates) exceeds financing cost.
**Heuristic:** Track implied-basis sign/magnitude over time; a sign flip from historical norm can front-run a shift in dividend/convenience-yield expectations.
**Pitfall:** Very-short-dated basis is dominated by settlement-convention noise (AM/PM expiry, dividend record dates) — filter contracts inside the pre-ex-div blackout window.
**Source:** Book 4, Ch. 2.

### Implied dividend/rate can front-run consensus estimates
**Idea:** Given 3 of {forward, spot, rate, dividend}, solve for the 4th — a liquid, contemporaneous option chain's implied dividend is the market's real-time forecast, which can lead sell-side consensus.
**Heuristic:** Compute implied dividend from ATM call/put; a persistent, liquidity-adjusted gap vs. consensus ahead of an announcement is a candidate dividend-surprise signal.
**Expression sketch:** `implied_div = S×(1+r×t) − F` (F solved from C−P); feature = `(implied_div − consensus_div)/S`.
**Pitfall:** Only reliable with liquid, near-the-money call and put; thin single-name markets make this noisy — down-weight or exclude.
**Source:** Book 4, Ch. 2.

---

## 2. PCR-FLOW

### Structured-product flow direction predictably lifts/weighs on implied correlation
**Idea:** Structured-product client flow systematically buys "cheap" long-correlation structures (worst-of calls, best-of puts) and sells "expensive" short-correlation structures (worst-of puts, best-of calls) — a persistent, structurally embedded net buying pressure on implied correlation, not a random walk.
**Heuristic:** Track visible/estimable worst-of/best-of flow mix as a directional bias input on correlation-level trades; heavy worst-of-put selling (e.g., autocallable issuance) leads further correlation richening rather than just coinciding with it.
**Pitfall:** Best-of calls are rare in practice — real flow is asymmetric across the four structure types; don't assume equal two-way flow when calibrating magnitude.
**Note:** This is the flow-mechanism explanation behind several `skew`/`term-structure` correlation cards below (index skew, correlation-swap spreads) — treat as the flow-driver companion, not an independent tradeable signal on its own.
**Source:** Book 2, Ch. 5.2, 6.3.

> **Gap flagged explicitly by two sources:** Books 1, 3, and 4 all noted they contain essentially no put-call-ratio / open-interest / positioning-flow content — this archetype is thin across the corpus so far and is the one most worth targeting with a dedicated flow/positioning-focused book next.

---

## 3. SKEW

### Skew shape reflects who structurally hedges, not pure probability
**Idea:** Equity/index markets show "investment skew" (downside puts bid — long-only protective buying + covered-call selling). Commodities often show "demand skew" (upside calls bid — end-user spike hedging > producer decline hedging). FX tends toward balanced/symmetric skew (natural two-sided hedgers).
**Heuristic:** Classify each underlying's skew regime (investment/demand/balanced) from its economic hedging base; measure current skew steepness against *that regime's own history*, not a universal prior.
**Expression sketch:** `skew_regime_z = (25d_put_iv − 25d_call_iv)` normalized by the instrument's own trailing distribution, not a pooled cross-asset one.
**Pitfall:** Classification can drift over time (e.g., a commodity becoming financialized/ETF-driven) — re-estimate periodically, don't hardcode.
**Source:** Book 4, Ch. 24.

### Skewness (tilt) and kurtosis (curvature) are two distinct, separately tradeable factors
**Idea:** Skew decomposes into tilt (are low/high strikes relatively richer) and curvature (are *both* wings rich vs. ATM — fat perceived tails). These respond to different beliefs and shouldn't be collapsed into one scalar.
**Heuristic:** Fit skew per expiry to `a + bx + cx²` in log-moneyness; track `b` (tilt) and `c` (curvature) as separate series. A move in `b` alone = directional-tail repricing; a move in `c` alone = symmetric crash-and-melt-up repricing.
**Expression sketch:** `skew_tilt = b_t − b_hist_mean`; `skew_curve = c_t − c_hist_mean`.
**Pitfall:** With few strikes/wide spreads, the `c` (curvature) term is unstable — it leans hardest on illiquid far-wing strikes; require a minimum strike count/liquidity.
**Note:** Recommend splitting your existing single skew-steepness signal into an explicit tilt/curvature pair.
**Source:** Book 4, Ch. 24.

### Market-implied probability distribution from butterfly prices
**Idea:** A dense strip of butterfly prices directly reconstructs the market-implied density at expiry — no lognormal assumption needed. Comparing this to a matched-moments lognormal shows exactly where/how the market disagrees (fat left tail, thin right tail, etc.).
**Heuristic:** Reconstruct implied density periodically, diff vs. matched-moments lognormal; asymmetries that *don't* match the instrument's typical regime shape (see card above) are the more interesting, name-specific signal.
**Expression sketch:** `density_i ≈ butterfly_price(X_i-Δ, X_i, X_i+Δ) / Δ²` (normalized), compared bucket-by-bucket to lognormal reference.
**Pitfall:** Needs a genuinely dense, two-sided strike ladder — sparse grids blur real detail into noise.
**Note:** Likely the single most information-dense technique in the skew cluster; consider as a candidate core method rather than a peripheral card.
**Source:** Book 4, Ch. 24.

### Skew "floats" with the underlying — always re-express in moneyness space
**Idea:** The skew curve tends to shift with spot in log-moneyness/SD-from-spot space rather than staying pinned to absolute strikes. A fixed strike's IV changes as spot moves even with zero real change in skew view — purely because moneyness changed.
**Heuristic:** Always re-express strikes in SD-from-forward or log-moneyness before comparing skew snapshots across time; raw fixed-strike IV charts conflate spot movement with genuine skew-shape change.
**Pitfall:** This is a very common, very consequential analysis error — a naive fixed-strike chart can look like "skew is steepening" purely because spot fell toward a fixed low strike.
**Source:** Book 4, Ch. 24.

### Skew steepness partly reflects vol's own correlation with direction
**Idea:** Equity indices tend to get more volatile as they fall — a put moving further OTM as the market falls gets a vol tailwind, inflating its "fair" IV beyond what a symmetric-vol model predicts.
**Heuristic:** Estimate the instrument's historical vol-change/return correlation; strong negative correlation "deserves" more structural put-skew than pure hedging-flow explains alone — helps separate flow-driven (mean-reverting) richness from structurally-justified richness.
**Pitfall:** Conflating the two sources leads to systematically fading skew that's actually fairly priced.
**Source:** Book 4, Ch. 9, 24.

### Variance swaps are structurally long skew (1/K² weighting)
**Idea:** A variance swap replicates via a static log-contract portfolio weighted 1/K² — this over-weights low-strike (OTM put) vs. high-strike options, making the product inherently long downside skew/curvature.
**Heuristic:** A widening variance-swap-vs-ATM spread with flat realized skew signals skew richening specifically, not a pure vol-level move.
**Expression sketch:** `var_swap_minus_atm = variance_swap_level - atm_iv` as a skew-richness proxy.
**Pitfall:** Post-2008 removal of an implicit low-strike-IV cap lifted this spread from ~2pts to ~7pts (settling ~3-4pts) purely from a *convention* shift, not real skew-risk change — regime-break risk across the 2008 boundary.
**Source:** Book 2, Ch. 2.2–2.3.

### Options on variance/vol futures have inverted (positive) skew
**Idea:** Vol is calm when low but can spike sharply when already high — so options on VIX/vStoxx futures show *positive* skew (high strikes richer), opposite of equities.
**Heuristic:** Never apply equity-style skew assumptions to vol-future options chains; when mispriced, favor structures long the right tail (e.g., call spreads on vol).
**Pitfall:** Term structure on these options is sharply inverted (near-dated vol-of-vol >> far-dated) — skew and term structure interact strongly here and shouldn't be evaluated independently.
**Source:** Book 2, Ch. 2.4, 4.5.

### Index skew is structurally higher than average single-stock skew (implied-correlation channel)
**Idea:** Index variance = weighted single-stock variances + a correlation term. Implied correlation trends toward ~100% at crisis-like low strikes regardless of index diversity, lifting index skew above the average constituent skew even with flat single-stock surfaces.
**Heuristic:** Decompose observed index skew into (a) average single-stock skew and (b) the implied-correlation-skew component before calling index skew "rich" — a stable gap isn't itself mispricing; a widening beyond its historical band is.
**Expression sketch:** `index_skew_minus_avg_ss_skew`, tested for reversion to its historical band.
**Pitfall:** Structured-product flow (worst-of/best-of, autocallables) also structurally lifts implied correlation — a rich reading can reflect persistent hedging demand, not a temporary dislocation. Don't assume automatic mean reversion.
**Source:** Book 2, Ch. 6.3, 7.1.

### Skew × √T is roughly constant across maturities ("the √T rule") — high-confidence, corroborated 2×
**Idea:** Near-dated skew is structurally steeper than far-dated because near-dated ATM vol is itself more volatile (realized-vol mean reversion over ~8 months). No-arbitrage on put spreads mathematically requires skew to decay ~√time.
**Heuristic:** Normalize skew across expiries by `× √T` before comparing rich/cheap across the curve; a maturity whose normalized skew stands out from its own history or from neighbors is the better trade candidate than a raw-level comparison.
**Expression sketch:** `norm_skew = skew_90_100 * sqrt(T_years)`; flag deviation from trailing average or neighboring maturities.
**Pitfall:** The √T relationship can break in panicked/crisis markets when skew and term structure decouple. Very long-dated (~5yr+) skew needs a *decay-by-time*, not √time, bound (ratio put spreads enforce the stricter condition).
**🔁 Corroborated independently in Book 3** (Ch. 9, 14–15) via the Derman "rule of two" derivation — high-confidence relationship, same math from a different angle.
**Source:** Book 2, Ch. 7.1–7.2, Appendix A.6; Book 3, Ch. 9, 14–15.

### No-arbitrage ceiling on skew steepness — high-confidence, corroborated 2×
**Idea:** Put spreads (and, more strictly, ratio put spreads) can never have negative value — this places a hard mathematical ceiling on how steep negative skew can get for a given maturity, decaying by √time (or by time, for ~5yr+ maturities under the stricter ratio-spread argument).
**Heuristic:** Compute the theoretical bound from the standard-normal-density formula; a skew close to (not just historically elevated relative to) this hard bound is qualitatively different information than a multi-year-high skew still far from the limit.
**Expression sketch:** compute the upper/lower bound curve for `∂Σ/∂ln(K)` via the N'(d1)-based inequality; track `observed_skew_slope / theoretical_bound`.
**Pitfall:** In practice, participants arbitrage away richness well before the true bound — "distance from bound" alone, without also checking the security's own historical range, risks missing genuinely actionable richness that occurs well inside the bound.
**🔁 Corroborated independently in Book 2** (Ch. 7.2, Appendix A.6) via the standard put-spread positive-cost argument — same underlying constraint derived twice.
**Source:** Book 3, Ch. 9; Book 2, Ch. 7.2, Appendix A.6.

### Fixed-strike skew is a fine proxy for delta skew — do NOT divide by vol to "normalize"
**Idea:** Delta-based skew (e.g., `[25∆put−25∆call]/50∆`) is the theoretically clean measure (widens with vol *and* normalizes by it) but is ~93% R² correlated with simple fixed-strike skew (e.g., 90-100%). Dividing fixed-strike skew by ATM IV to "normalize" double-counts the effect.
**Heuristic:** Use raw fixed-strike skew directly, cross-sectionally, as a practical substitute for delta skew — skip the extra vol-normalization step.
**Expression sketch:** `skew_90_100 = iv(strike=0.9) - iv(strike=1.0)`, used as-is.
**Pitfall:** CBOE SKEW (3rd-central-moment-based) is a different, strike-independent construction — comparing it directly to a strike-based metric without adjustment looks inconsistent even when nothing is actually mispriced.
**Note:** This is a correctness check that should gate every other skew signal in the pipeline.
**Source:** Book 2, Ch. 7.4.

### Long skew only has positive expected value under "jumpy volatility" regimes
**Idea:** Long skew (long OTM put, short OTM call) pays daily carry ("skew theta") but earns from surface re-marks when spot and IV move negatively-correlated. Under 4 idealized regimes — sticky delta, sticky strike, sticky local vol, jumpy vol — long skew loses in the first two, breaks exactly even in the third, and is profitable only in the fourth.
**Heuristic:** Classify the current regime (trending/calm → sticky delta; normal → sticky strike; orderly risk-off → sticky local vol; panic/crash → jumpy vol) before entering — only jumpy-vol offers positive EV for long skew; the other three need strong standalone conviction of elevated realized skew ahead.
**Expression sketch:** `realized_skew_ratio = surface_move / skew`; persistently >1 windows identify jumpy-vol regimes retrospectively, usable to condition entry rules going forward.
**Pitfall:** Skew is on average priced with a jumpy-vol premium baked in (hedging demand keeps it "usually overpriced" from the long side) — long skew is a structural net loser most of the time; calm-period backtests will understate the true rare/large payoff and overstate typical cost.
**Note:** Central, non-redundant framework tying together several skew cards above into one trading-decision layer.
**Source:** Book 2, Ch. 7.5.

### Vanna/volga mechanically explain stochastic-vol-induced smile shape
**Idea:** Volga (∂²C/∂σ²) is generally positive away from ATM and creates a symmetric, U-shaped smile from pure vol-of-vol (even at zero spot/vol correlation). Vanna (∂²C/∂S∂σ) is positive for OTM calls, negative for ITM calls, and — multiplied by a typically-negative equity spot/vol correlation — tilts the symmetric smile into the familiar downward skew.
**Heuristic:** To separate "pure convexity" (volga) from "correlation tilt" (vanna×correlation), estimate the curvature (quadratic) and slope (linear) terms of the smile in log-moneyness separately; the curvature-to-slope ratio, cross-checked against an independent realized spot/vol correlation estimate, tests whether the observed shape is internally consistent with stochastic vol alone or needs another mechanism (jumps, flow).
**Expression sketch:** fit `IV(K) ≈ a + b*ln(K/S) + c*ln(K/S)²`; `c` should scale with vol-of-vol², `b` with `rho*vol_of_vol` — check the fitted `b/c` ratio against realized correlation.
**Pitfall:** Stochastic-vol-only models struggle to reproduce steep short-dated equity-index skew without unrealistic vol-of-vol/correlation — a poor short-end fit is itself diagnostic that jump risk is contributing, not that the framework is wrong.
**🔁 Reinforces the vega/vanna/volga moment-decomposition card in the OTHER section below (Book 2)** — recommend merging into one unified reference at final consolidation.
**Source:** Book 3, Ch. 19–20.

### Individual-strike skew slope is bounded by vega and cost-of-gamma (data-quality gate)
**Idea:** No-arbitrage price-monotonicity constraints (`∂C/∂K ≤ 0`, `∂²C/∂K² ≥ 0`) translate via the Greeks into a bound on how fast IV can change per unit strike change — near-ATM, low-vol, short-dated, the rule of thumb is ~1.25 vol-points per 1% strike move, scaled by `1/√τ`.
**Heuristic:** Use as an automated data-quality/arb-detection gate — verify adjacent-strike IV deltas don't exceed `1.25/√τ * (dK/K)`; a violation flags a stale/bad quote or a rare genuine arb.
**Expression sketch:** `max_skew_per_pct_strike ≈ 1.25 / sqrt(T)`.
**Pitfall:** Only valid near-ATM/low-vol/short-dated (small `d1,d2`); breaks down for far OTM/ITM, long-dated, or high-vol names — use the exact N(d)-based bound there instead.
**Source:** Book 3, Ch. 9.

### Corrado-Su expansion for implied skewness/kurtosis
**Idea:** Extending BSM with a Gram-Charlier expansion (`C = C_BSM + µ₃Q₃ + (µ₄−3)Q₄`) collapses an entire skew curve into 3 comparable parameters (vol, skew, kurtosis) per expiry.
**Heuristic:** Build implied-skewness/kurtosis time series per underlying/expiry (like an IV cone) and compare to realized return skew/kurtosis over the same horizon — a large implied-vs-realized skew gap is a candidate signal, VRP-style.
**Expression sketch:** fit `(sigma, mu3, mu4)` by minimizing `Σ(market_price − C_BSM − mu3*Q3 − (mu4−3)*Q4)²` across strikes.
**Pitfall:** Skew and kurtosis effects are intertwined in this model — a shift in one can look like a shift in the other; also can produce nonsensical negative option prices outside a bounded region.
**Note:** A second extraction pass over this same book adds a stricter arbitrage-free boundary constraint (Barton-Dennis / Jondeau-Rockinger) needed for the joint (μ3, μ4) fit, and confirms the parameters aren't cleanly separable in their effect on smile shape — don't naively equate fitted μ3/μ4 to a simple polynomial's tilt/curvature terms.
**Source:** Book 1 (Sinclair), Ch. 3, eq. 3.10–3.16.

### Delta-parameterized, ATM-normalized smile is far more stable across expirations than a strike-parameterized one
**Idea:** Taking each expiry's IV curve, parameterizing by delta (not raw strike), and dividing by that expiry's own ATM IV produces normalized curves that look nearly identical across very different tenors for the same underlying — far more so than raw strike-vol curves.
**Heuristic:** Use this delta/ATM-normalized representation as the baseline "typical shape" for cross-expiry or cross-time skew comparison; deviation from this stable baseline (not a raw-strike comparison, confounded by moneyness drift) is the more trustworthy skew-anomaly signal.
**Expression sketch:** `normalized_skew(delta, expiry) = IV(delta, expiry) / ATM_IV(expiry)`; flag expiries deviating from the name's own trailing-average normalized curve at matched delta buckets.
**Pitfall:** No known theoretical reason this normalization is so stable — may be a market-maker smile-propagation convention (microstructure habit) rather than a fundamental distributional truth. Rule out mechanical/liquidity explanations before reading deviations as pure "probability distribution changed" signals.
**Note:** Same underlying principle as the "skew floats with the underlying, re-express in moneyness space" card above, with a specific delta+ATM-normalization recipe and empirical cross-expiry stability evidence.
**Source:** Book 1, Ch. 3.

### Index skew steepness has an implied-correlation channel distinct from hedging-flow explanations — corroborates the Book 2 index-skew card
**Idea:** Index variance = weighted component variances + a correlation cross-term. Index-level skew can rise purely because the market expects correlation to rise as the index falls, even with every component surface flat — a mechanical source separate from hedging flow.
**Heuristic:** When comparing an index's skew to its correlation-weighted component skew, a persistent gap is partly implied-correlation-channel, not pure hedging flow — relevant for dispersion trades (index vol/skew vs. basket vol/skew), which should model this channel directly.
**Pitfall:** Don't attribute 100% of an index-vs-component skew gap to hedging flow without checking the correlation-channel contribution — conflating the two mis-specifies dispersion trades.
**🔁 Same mechanism as "Index skew is structurally higher than single-stock skew (implied correlation channel)" in this section (Book 2)** — independent corroboration from a second source; high confidence.
**Source:** Book 1, Ch. 3.

---

## 4. TERM-STRUCTURE

### The √T "rule of two" — local vol slope is ~2× the implied vol slope — corroborated 2×
**Idea:** In a local-vol model with a linear local-vol slope in underlying price, resulting BSM implied vol (~average local vol between spot and strike) has strike-slope exactly half as steep — so `∂Σ/∂S ≈ ∂Σ/∂K` for ATM options. At very short expirations this becomes a harmonic (not arithmetic) mean.
**Heuristic:** Apply a factor-of-2 adjustment (not 1:1) when inferring near-term local-vol dynamics from an observed implied skew, or vice versa.
**Expression sketch:** `local_vol_slope ≈ 2 * implied_vol_skew_slope` (log-strike space).
**Pitfall:** Only a valid leading-order approximation for small/slow-varying skew; breaks down for steep short-dated skews and can even produce prices with no equivalent BSM IV at all in extreme cases.
**🔁 Directly corroborates the √T skew-normalization concept in Book 2** (Ch. 7.1–7.2) — high-confidence, merge at consolidation.
**Source:** Book 3, Ch. 14–15.

### Local-vol vs. stochastic-vol models give opposite-signed hedge-ratio corrections for the same skew
**Idea:** For negatively-skewed vanillas: local-vol models give hedge ratios *smaller* than BSM delta (local vol falls as spot rises); stochastic-vol models with negative spot/vol correlation give hedge ratios *larger* than BSM delta.
**Heuristic:** Be explicit about which model family generated a "smile-consistent" hedge ratio before using it — mixing frameworks moves the hedge in the wrong direction.
**Expression sketch:** `hedge_local ≈ delta_BSM − vega_BSM * skew_slope`; `hedge_stochastic ≈ delta_BSM + rho*vega_BSM*vol_of_vol/(sigma*S)`; compare both against realized hedged-P&L variance to see which fits current regime.
**Pitfall:** Empirically (Crepey 2004), local-vol hedging performs better in typical equity-index regimes (crash-down/grind-up) — a regime-dependent finding, not universal proof either model always wins.
**Source:** Book 3, Ch. 16–17, 22.

### "Sticky" heuristics predict opposite skew dynamics — empirically C≈1.5 for S&P 500, between sticky-strike and sticky-local-vol
**Idea:** Sticky strike (C=1, ATM vol falls as spot rises), sticky delta/moneyness (C=0, ATM vol roughly constant), sticky local vol (C=2, ATM vol rises sharply as spot falls). Kamal & Gatheral found `C = (∂Σ_ATM/∂S)/(∂Σ/∂K) ≈ 1.5` for S&P 500 — between strike and local-vol, rejecting pure sticky-moneyness.
**Heuristic:** Use `C≈1.5` as a starting blend when forecasting ATM-vol change given a skew slope and expected spot move, rather than any single pure heuristic.
**Expression sketch:** `predicted_ATM_vol_change ≈ -1.5 * skew_slope_dK * spot_change`.
**Pitfall:** C≈1.5 is specific to the S&P 500 study/equity-index dynamics broadly — other asset classes (FX, single stocks, rates) need separate calibration, don't reuse 1.5 by default.
**Source:** Book 3, Ch. 18.

### Jumps and mean-reverting stochastic vol both flatten skew at long tenors — via different mechanisms
**Idea:** Jump risk's contribution to the return-distribution shape is roughly constant per event while diffusive variance grows with T, so jump-driven skew is steep short-dated and flattens as tenor grows. Mean-reverting stochastic vol flattens long-tenor skew too, but because vol paths converge to a common long-run mean, killing the variance-of-path-vol that drives curvature.
**Heuristic:** Distinguishing the two requires shape, not just term structure — jump-driven skews are more linear/monotonic short-dated; correlated-mean-reverting-stochvol skews retain more curvature as tenor flattens.
**Expression sketch:** compare curvature (2nd deriv) vs. slope (1st deriv) decay across tenors — jump models predict slope-dominated short-tenor skew; stochvol models retain balanced curvature/slope.
**Pitfall:** Reproducing realistically steep short-dated index skew via pure stochastic vol (no jumps) typically needs implausible vol-of-vol or mean-reversion speed — extreme fitted parameters is itself a signal jumps are the more parsimonious driver.
**Source:** Book 3, Ch. 22–24.

### Variance swaps replicate via a static log-contract (1/K²) portfolio, model-independent
**Idea:** A 1/K²-weighted put/call portfolio has variance-sensitivity independent of stock price; this replication holds under stochastic (not just constant) vol, as long as the underlying diffuses continuously without jumps.
**Heuristic:** Reconstruct the theoretical fair variance strike from the actual listed chain via piecewise-linear log-contract weights (Appendix C) rather than trusting a single ATM-vol approximation, when checking a quoted variance swap's fairness.
**Expression sketch:** `variance_fair_strike = (2/T) * Σ(w_i * O_i)`, `w_i` = piecewise-linear slope-difference weights.
**Pitfall:** Finite-strike replication is biased high when strikes are widely spaced, biased low if the range doesn't extend far into the tails; jumps additionally break replication (it only captures the (dS/S)² term, not higher-order jump terms).
**Source:** Book 3, Ch. 4, Appendix C.

### Volatility swaps are cheaper than variance swaps of equal vega — the gap is a pure vol-of-vol premium
**Idea:** Variance-swap payout is convex (∝σ²), vol-swap payout is linear (∝σ) — variance must always be worth ≥ vol swap of equal vega; the gap comes entirely from vol-of-vol (zero in a zero-vol-of-vol world).
**Heuristic:** The spread between quoted variance and vol-swap (or ATM IV as proxy) levels is a direct read on priced vol-of-vol; a widening spread with unchanged realized vol-of-vol history signals variance richening (or vice versa), independent of outright vol level.
**Expression sketch:** `vol_of_vol_premium = sqrt(variance_swap_strike) - vol_swap_strike`.
**Pitfall:** Assumes zero spot/vol correlation for the cleanest form; nonzero correlation complicates a naive comparison via a "fake" stock-price-shift term.
**Source:** Book 3, Ch. 4.

### Discrete-hedging noise shrinks ~1/√N — but only if hedging at the *correct* (realized) vol
**Idea:** Discrete delta-hedging using the correct realized vol has P&L noise std-dev scaling 1/√N (N = rehedges); quadrupling frequency halves noise. If hedge vol ≠ realized vol, this benefit largely disappears — a new noise term proportional to `(Δ_hedge − Δ_realized)·dS` doesn't vanish with finer steps.
**Heuristic:** Before crediting a P&L-variance reduction to "better/more frequent hedging" in a backtest, verify the hedge ratio actually tracked realized vol — a stale-implied-vol/regime-shift mismatch means more frequent rehedging won't meaningfully shrink noise.
**Expression sketch:** `hedging_error_stdev ≈ sigma/sqrt(N) * vega` as the theoretical floor for a correctly-vol-hedged strategy.
**Pitfall:** This is an idealized (known-future-vol) result; real hedging always has both this timing noise AND vol-forecast-error noise on top — conflating the two sources misattributes the actual cause of P&L variance.
**🔁 This is the rigorous, closed-form version of the discrete-hedging path-dependence theme seen across Books 1, 2, and 4** — treat as the anchor derivation.
**Source:** Book 3, Ch. 6.

### Transaction costs shift effective volatility (Leland's formula) — long options cheapen, short options richen
**Idea:** Proportional rehedging costs adjust the effective BSM vol used for pricing: long (positive-gamma) positions should be valued at `σ̂ = σ − k√(2/(π·dt))`; short positions at `σ + k√(2/(π·dt))` — the adjustment grows with rehedging frequency (finer dt).
**Heuristic:** Adjust the "fair" theoretical vol benchmark by the Leland cost term (position side, spread, expected rehedge frequency) before comparing to a market-quoted IV, or a genuinely fair cost-inclusive quote looks artificially rich/cheap.
**Expression sketch:** `sigma_effective = sigma -+ k * sqrt(2/(pi*dt))` (minus long, plus short).
**Pitfall:** As `dt→0` the adjustment diverges — continuous hedging with any nonzero cost is infinitely expensive; only useful for moderate, realistic rehedging frequencies.
**Source:** Book 3, Ch. 7.

### Expected profit from an implied/realized vol mismatch (vega form)
**Idea:** Expected profit of a delta-hedged option scales `½S²Γ(σ²−σ²implied)`, equivalently `vega·(σ−σimplied)`, linking gamma and vega exposure via `vega = σTS²Γ`.
**Heuristic:** Size expected VRP edge as `vega * (forecast_vol - implied_vol)`, not the raw vol spread — this scales edge by moneyness/time-dependent position exposure.
**Expression sketch:** `edge = vega * (rv_forecast - iv_implied)`
**Pitfall:** Highly path-dependent — realizing the "average" edge requires the underlying to stay in the region where gamma is meaningful.
**Source:** Book 1, Ch. 1.

### Sampling error gate for realized-vol-based signals
**Idea:** `Var(s) ≈ σ²/2N` — short-window RV estimates carry large sampling error (95% CI ~±25% at N=30).
**Heuristic:** Before treating an implied-vs-realized spread as real, check it exceeds the sampling-error confidence band; discount/skip signals within ~1 sampling-error band.
**Expression sketch:** `ci = rv * sqrt(1/(2*N))`; require `abs(iv - rv) > k*ci`.
**Pitfall:** More data reduces sampling error but stales the estimate vs. current regime — bias/variance tradeoff, no free lunch from a longer window.
**Source:** Book 1, Ch. 2, eq. 2.10.

### Alternative realized-vol estimators (Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang)
**Idea:** Range/OHLC-based estimators use more intraday info and converge faster than close-to-close, but each has known biases (Parkinson underestimates due to discrete sampling; Garman-Klass more efficient but more biased low; Rogers-Satchell robust to drift, not jumps; Yang-Zhang handles drift + opening jumps, degrades under heavy jumps).
**Heuristic:** Compute several simultaneously — a wide Parkinson-vs-close-to-close spread signals intraday range driving RV more than closing moves.
**Expression sketch:** `parkinson = sqrt(ts_mean(log(high/low)^2, N) / (4*N*log(2)))`
**Pitfall:** Under real (non-GBM) conditions, Garman-Klass/Yang-Zhang can bias slightly *high* — reversing the textbook simulation-based bias direction. Real-data correlation across estimators is ~0.94–0.99 (vs. lower on simulated data) — combining several buys less diversification than naive efficiency comparisons suggest.
**Source:** Book 1, Ch. 2, eq. 2.14–2.17.

### EWMA and GARCH(1,1) volatility forecasting
**Idea:** EWMA has no mean reversion, over-weighting a single shock as long as it's in the lambda-window. GARCH(1,1) reverts toward long-run variance `V=ω/(1−α−β)`; horizon-τ forecasts converge geometrically: `E[σ²t+τ]=V+(α+β)^τ(σ²t−V)`.
**Heuristic:** Prefer GARCH over EWMA when recent RV includes an identifiable one-off shock; better still, explicitly exclude a known discrete event (earnings) from the estimation window rather than relying on either model's implicit decay.
**Expression sketch:** `garch_forecast_tau = V + (alpha+beta)^tau * (sigma2_t - V)`
**Pitfall:** GARCH MLE parameters show little persistence on re-estimation — weak evidence of genuine model fit vs. curve-fitting; the likelihood surface is often flat, unstable across resampling.
**Source:** Book 1, Ch. 2, eq. 2.20–2.28.

### Optimal mean-reversion entry threshold ≈ 0.75σ
**Idea:** For a normal, independent-deviation mean-reverting process, expected profit from entering at deviation S is `2TS[1−N(S)]`; the maximizing entry is `Smax≈0.75σ` — closer to the mean than intuition suggests, since entering too far out sacrifices trade frequency.
**Heuristic:** Backtest-calibrate entry thresholds near 0.75σ from the rolling mean, rather than defaulting to conservative 2σ bands, for mean-reversion entry rules (e.g., on an IV/RV spread).
**Expression sketch:** `entry_threshold = 0.75 * rolling_std`
**Pitfall:** Real processes are fat-tailed/skewed — P&L degrades faster below-optimal than above; err slightly wider than 0.75σ rather than tighter.
**Source:** Book 1, Ch. 6, eq. 6.29–6.30.

### IV is structurally biased above RV — partly rational risk premium, partly true mispricing
**Idea:** Short vol is implicitly long equity risk (negative vol-equity correlation), so part of the average IV>RV premium is compensation for equity risk, not mispricing. Structural demand imbalances (protection buying, dealer margin, structured-product index demand) add a further, persistent overpricing on top.
**Heuristic:** Decompose the IV−RV spread into an equity-risk-premium component (roughly `vol-equity-correlation × equity risk premium`) and a residual; only the residual is a genuine selling-vol edge.
**Expression sketch:** `residual_vrp = (iv - rv) - beta_vol_to_equity * equity_risk_premium_proxy`
**Pitfall:** Far-dated implieds are more overpriced in absolute vol points, but near-dated variance-swap-equivalents can be sold more per unit time — richness alone doesn't tell you which tenor to sell.
**🔁 Reinforces the Book 4 "IV as lagging/biased predictor of RV" card and Book 1's own vega-form VRP card** — same phenomenon, three angles. High-confidence, prioritize for merging.
**Source:** Book 2, Ch. 3.1.

### Long volatility is a structurally poor equity hedge
**Idea:** Long variance swaps have only ~50-70% R² correlation to equity returns (peaking near 9-12mo tenor), and since vol is on average overpriced, a long-vol hedge costs more than simply trimming equity exposure for equal risk reduction.
**Heuristic:** Benchmark a vol-overlay hedge's risk-adjusted cost against simply reducing equity exposure/shorting futures at the same target risk; favor the futures/equity-reduction hedge if the vol hedge underperforms over positive-equity periods.
**Pitfall:** Constant-maturity vol-future ETN/ETF products are especially poor hedges — continuous roll from cheap near-dated to expensive far-dated futures generates negative roll-down that can outpace protective value even during genuine selloffs.
**Source:** Book 2, Ch. 3.2.

### Structural (non-mean-reverting) flow lifts long-dated term structure
**Idea:** Variable-annuity providers hedge long-dated downside guarantees by rolling shorter-dated (3-5yr) protection since sufficiently liquid longer options don't exist — creating a constant structural bid for long-dated downside strikes, lifting far-dated term structure/skew independent of near-term market view. Regulatory shifts (Dodd-Frank, Volcker) that shrink prop-desk counterparties for this flow have caused abrupt far-end spikes historically.
**Heuristic:** Treat persistently elevated far-dated (3yr+) term structure/skew (esp. S&P500) as partly structural flow, not pure market view — discount its mean-reversion tendency vs. near-dated richness.
**Pitfall:** Index-specific effect (S&P500 most affected); can decouple sharply from single-stock or other-index term structure during regulatory shift windows.
**Source:** Book 2, Ch. 3.3.

### The "vanna/volga vicious circle" — structured-product-driven IV overshoot/undershoot
**Idea:** Structured-product sellers are short skew and short volga; a decline moves their short put more ATM (raising short vega via vanna), and rising vol itself increases that short-vega further (via volga), forcing repeated short-covering (buying IV) — a self-reinforcing overshoot in declines, mirror undershoot in recoveries. Strongest for far-dated implieds and low-to-medium vol regimes (~20% or less).
**Heuristic:** During rapid declines (or sharp post-crisis recoveries), expect near-term IV to overshoot (undershoot) what pure RV-repricing justifies — a fade candidate once the acute short-covering flow subsides, not a regime shift.
**Expression sketch:** monitor vanna/volga-implied dealer exposure proxies (skew steepness × recent spot move) as a leading indicator for overshoot risk during fast moves.
**Pitfall:** Assumes dealers maintain a persistently short-skew/short-volga book; if books were rebuilt more conservatively post-crisis, amplification may be muted — don't assume constant magnitude across cycles.
**Source:** Book 2, Ch. 3.4.

### Discrete hedging with unknown (implied-proxy) volatility can turn a "cheap" option into a loser
**Idea:** Under continuous hedging with known or unknown vol, buying below eventual realized vol can never lose. Once hedging is discrete AND vol is estimated (via implied), both noise sources can combine to produce a loss even on a genuinely cheap (in hindsight) option — e.g., a 2008 SX5E straddle bought 20 vol points cheap still lost because most realized vol arrived late (post-Lehman) when the position's stale-IV-derived delta was badly mismatched.
**Heuristic:** In any hedged-P&L backtest of a long-vol strategy, compute the hedge delta from an updated/expected vol forecast, not static implied vol — using implied vol for delta systematically underhedges long-vol positions exactly when it matters most.
**Pitfall:** Hedging-error variance is independent of average trade profitability (pure noise on top of edge) and shrinks roughly by half for a 4x hedge-frequency increase — but never fully vanishes (weekend/overnight gaps).
**🔁 Directly reinforced by Book 3's √N/correct-vol card above** — same phenomenon, corroborated.
**Source:** Book 2, Ch. 3.5.

### Published vol indices read below "true" variance-swap value (methodology artifact)
**Idea:** VIX-style indices read 0.2-0.8 vol points below the true OTC variance-swap level due to tail-chopping (dominant effect, chopping low-strike puts matters ~6x more than high-strike calls), discrete strike sampling, and linear (not √time) interpolation between expiries.
**Heuristic:** Expect a small structural discount when comparing a published index to an OTC variance-swap or model-implied "true" level — a gap within ~0.2-0.8pts isn't itself an arb signal; only outside that range warrants investigation.
**Pitfall:** The discount size varies by provider methodology (deliberately, to avoid infringing others' proprietary calc conventions) — recalibrate per index/provider, not a universal constant.
**Source:** Book 2, Ch. 4.2.

### VIX/vStoxx futures are underpriced vol-of-vol relative to fair value
**Idea:** A vol-index future is linear in vol, sitting between a forward vol swap and √(forward variance swap) — structurally short vol-of-vol. Model-implied fair level should sit ~2pts below forward variance and ~1-2pts above ATMf IV; historically traded only ~1pt below variance and 5-6pts above ATMf — implying underpriced vol-of-vol.
**Heuristic:** Compute the model-implied fair future level (roughly midpoint of forward vol and forward variance) vs. traded price; a persistent gap above the theoretical range supports short-future/long-forward-variance relative value.
**Expression sketch:** `fair_vol_future ≈ 0.5*(fwd_vol_swap + sqrt(fwd_variance_swap))`
**Pitfall:** VIX-linked ETN/ETFs are now ~2/3 the vega size of the underlying futures market — the "mispricing" may partly reflect genuine persistent structured demand, not pure arb; can persist or widen rather than close.
**Source:** Book 2, Ch. 4.3.

### Constant-maturity vol ETN/ETF flow distorts the futures curve at specific points
**Idea:** Open-ended vol-future ETNs continuously sell near-dated, buy far-dated futures to hold a fixed average maturity — a flow large relative to the futures market that structurally depresses the front-month and (for medium-dated 4-7mo products) the fourth-month specifically.
**Heuristic:** For long vol-future exposure, prefer initiating at the front-month or fourth-month specifically (most likely cheapened by rebalancing flow); conversely short the relevant ETN itself to be short this imbalance directly.
**Pitfall:** Market-specific and size-dependent — significant for VIX products historically (vStoxx too small to matter), but relative product sizes shift over time and must be re-checked, not assumed static.
**Source:** Book 2, Ch. 4.4.

### Three distinct correlation "prices" — realized < correlation-swap < dispersion-implied
**Idea:** Realized correlation < correlation-swap traded level (~5pts above, structured-product demand) < dispersion-implied correlation (~10pts further above swaps, compensating dispersion's short-vol-of-vol/volga risk). The gap widens in relative terms at low absolute correlation (empirically more volatile/mean-reverting there).
**Heuristic:** Always identify which of the three "prices" is being compared to which — mixing them (comparing dispersion-implied directly to realized without the ~15pt structural premium) makes a fairly-priced trade look artificially attractive.
**Expression sketch:** `implied_corr_dispersion ≈ realized_corr + 5 (swap premium) + 10 (volga premium)` as a rough baseline.
**Pitfall:** At low realized correlation (~30), the implied premium can jump much further (to ~50+) — a naive constant-point-spread breaks down at correlation extremes.
**Source:** Book 2, Ch. 6.3.

### Dispersion-trade weighting scheme determines what risk is actually being expressed
**Idea:** Theta-weighted dispersion isolates pure correlation exposure (breaks even if realized=implied correlation, but very short gamma); vega-weighted adds a long single-stock-vol hedge (breaks even on equal absolute vol moves); only theta-weighting isolates correlation as the sole driver, and that payout is short vol-of-vol (gains damped, losses amplified by correlation-vol co-movement).
**Heuristic:** Confirm the weighting scheme before evaluating a dispersion trade — theta-weighted vs. implied-realized correlation; vega-weighted vs. single-stock-vs-index vol spread — since they give economically different optimal-entry signals.
**Expression sketch:** `theta_weighted_pnl ≈ 0.5 * avg_weighted_variance * (implied_corr - realized_corr)`
**Pitfall:** Clean variance-swap dispersion is now largely untradeable (single-stock variance liquidity dried up post-credit-crunch) — straddle/vol-swap/gamma-swap dispersion each carry different hedging frictions not captured by the theoretical formula.
**Source:** Book 2, Ch. 6.3.

### Volatility term structure is mean-reverting and "conic" — short tenors noisier
**Idea:** RV measured over longer windows converges toward a long-run average; short windows show much wider dispersion. Short-dated IV is inherently harder to forecast than long-dated, even though short-dated options are less vega-sensitive to the error.
**Heuristic:** Build a rolling min/max/average RV cone per underlying by lookback length; flag current short-dated IV outside the historical cone as a mean-reversion candidate.
**Expression sketch:** `z_score = (current_IV_Nweek − hist_mean_Nweek_realized) / hist_std_Nweek_realized`, per tenor bucket.
**Pitfall:** Regime changes (e.g., post-2008 structural resets) move the mean the series reverts to — rebuild the cone periodically, don't use a fixed pre-regime-change window.
**Source:** Book 4, Ch. 20.

### Front-month IV frequently disconnects from the rest of the curve
**Idea:** The nearest expiry often trades inconsistent with a smooth term-structure fit — reacting to near-term catalysts (earnings, data, pin risk) that longer tenors don't.
**Heuristic:** Exclude the front month when fitting a term-structure model; treat the residual between front-month IV and the extrapolated curve as its own event-risk feature, not noise to smooth away.
**Pitfall:** Force-fitting the front month into the same curve corrupts the mean-reversion parameter estimate for the whole curve.
**Source:** Book 4, Ch. 20.

### Seasonal vol humps persist independent of general term-structure shape
**Idea:** Some commodities (e.g., natural gas October, hurricane season) carry structurally elevated IV in a specific contract month every year regardless of the rest of the curve.
**Heuristic:** For seasonal underlyings, decompose the term-structure signal into (a) generic mean-reversion and (b) a month-of-year seasonal adjustment from multi-year average IV-by-month; only flag mispricing after removing the seasonal component.
**Pitfall:** Treating a seasonally-elevated month as "overpriced to sell" without adjusting is a classic false signal — the level may be exactly fair.
**Source:** Book 4, Ch. 20.

### Calendar-spread implied vol isolates single-expiry mispricing
**Idea:** Solving for the single vol that reprices a calendar spread (not each leg standalone) magnifies whether one specific expiry is out of line with the smooth curve, even when each leg's individual IV looks unremarkable.
**Heuristic:** For each adjacent expiry pair, compute the calendar-implied vol vs. a best-fit curve; systematic deviation at one tenor (vs. smooth deviation across all spreads) flags a specific mispriced expiry.
**Expression sketch:** for vega V1,V2 and prices O1,O2: `spread_impliedvol ≈ (O2−O1)/(V2−V1)`, compared to smoothed curve fit.
**Pitfall:** Needs reasonably liquid prices on both legs — stale back-month settlements generate false "mispricings" that aren't tradeable.
**Source:** Book 4, Ch. 20.

### Forward volatility is a cleaner term-structure decomposition than raw curve comparison
**Idea:** Since variance scales linearly with time, you can solve for implied *forward* vol between two expiries (analogous to forward rates) — cleaner than comparing raw spot-IV levels because it isolates the market's expectation for that specific future window.
**Heuristic:** Compute forward vol pairwise across the curve; a "notch" of temporarily high/low forward vol (e.g., around a known event) is a calendar-spread/event-vol trade candidate, and more robust to interpolation artifacts.
**Expression sketch:** `σ_forward² = [σ2²·t2 − σ1²·t1] / (t2 − t1)`
**Pitfall:** Amplifies noise from short/illiquid legs — a small near-leg pricing error can produce a large spurious forward-vol spike, especially as `t2−t1` shrinks.
**Source:** Book 4, Ch. 20.

### IV is a lagging, imperfectly-biased predictor of subsequent RV
**Idea:** Empirically (S&P 500), rolling IV tends to *follow* RV rather than lead it, and on average overstates subsequent RV (risk-premium effect) — though the gap can invert sharply around vol-shock events.
**Heuristic:** Don't treat current IV as an unbiased RV forecast — build a bias-corrected forecast (weighted blend of historical RV at matched-maturity windows, recency+mean-reversion weighted) and compare *that*, not raw IV, when sizing long/short-vol decisions.
**Pitfall:** The average overpricing dynamic reverses sharply around genuine tail events (2008) — a systematic "always sell rich-looking IV" strategy is short a fat left tail; historical edge has been small, blowups large.
**Note:** Flag as a candidate `other`/standalone VRP archetype if the pipeline doesn't already separate this from pure term-structure curve-shape trades.
**Source:** Book 4, Ch. 20.

### Volatility cones need an overlapping-data bias correction (Hodges-Tompkins)
**Idea:** Building a vol cone from overlapping sub-periods (the standard practical choice) introduces artificial autocorrelation into the variance estimate, biasing the cone's apparent width unless corrected.
**Heuristic:** Multiply measured variance by the Hodges-Tompkins factor before building cone percentiles or comparing current IV to the cone.
**Expression sketch:** `adjusted_var = raw_overlapping_var × [1/(1 − h/n + (h²−1)/(3n²))]`, `h`=sub-window length, `n`=number of overlapping sub-series.
**Pitfall:** The correction grows as sub-window length approaches total sample length — cones built from long lookbacks on short total history need the largest (least reliable) correction; below some sample-size threshold, don't trust that part of the cone even after correcting.
**Note:** Direct implementation detail for the "conic" term-structure cone card above — apply this correction whenever building one.
**Source:** Book 1, Ch. 2 (Hodges & Tompkins).

### GARCH-style forecasts can't produce humped term structures — a humped market curve is itself informative
**Idea:** GARCH(1,1) decays exponentially toward a long-run mean, so its term-structure forecast is necessarily monotonic. Real option markets frequently price humped curves (e.g., 2-month IV above both 1-month and 3-month) — GARCH structurally can't explain this; the hump is coming from something GARCH doesn't model (typically a scheduled event inside one tenor).
**Heuristic:** When implied term structure is humped but a GARCH-style forecast is monotonic, don't fit a fancier time-series model to reconcile them — treat the hump as a discrete event-driven deviation (see the event-jump extraction card below) rather than a forecast-model failure.
**Pitfall:** Don't conclude "market disagrees with GARCH, so vol is overpriced at the humped tenor" — humped curves usually correctly price a dated catalyst a smooth statistical model can't represent.
**Source:** Book 1, Ch. 2.

### Level dominates the implied-vol surface — prioritize term-structure/level signals over skew/curvature
**Idea:** PCA of surface changes shows a parallel level shift explains ~65-80% of total variation; tilt (skew) ~5-15%; curvature (kurtosis) ~5%. Level is the dominant risk factor by a wide margin.
**Heuristic:** Weight research/modeling effort toward term-structure/level signals first — they carry most of the exploitable variance. Don't let a sophisticated skew model crowd out getting the level call right.
**Expression sketch:** fit a level/tilt/curvature factor model via PCA per underlying; large deviations from the ~70/10/5 pattern (e.g., unusually large curvature share) flag that name as having atypical surface dynamics worth handling separately.
**Pitfall:** Estimated on index datasets (S&P 500, Nikkei) — don't assume the exact split transfers to single names, especially event-driven or thin ones, where idiosyncratic skew/term-structure moves can dominate the generic level factor.
**Note:** Directly informs how much of the pipeline's resourcing should go to term-structure vs. skew archetypes.
**Source:** Book 1, Ch. 3 (Alexander 2001b PCA results).

### Event-jump size, back-solved from front-vs-back-month IV via forward vol — alternate formula, corroborates the breakeven-section event-jump card
**Idea:** When a scheduled event sits inside the front expiry but not the back, the gap between front-month IV and the implied forward vol between the two expiries isolates the event's contribution, convertible to an expected absolute move.
**Heuristic:** (1) `σ12 = sqrt[(σ2²T2 − σ1²T1)/(T2−T1)]`; (2) `σE = σ1·sqrt(T1)·sqrt(1 − (σ12/σ1)²)`; (3) `E[|R|] = sqrt(2/π)·σE`. Compare to an independent move estimate (e.g., historical move size around similar past events) — a large gap is the tradeable signal in either direction.
**Expression sketch:** `implied_jump = sqrt(2/π) × sqrt(T1) × sqrt(σ1² − σ12²)`; feature = `implied_jump − historical_event_move_estimate`, normalized by historical dispersion.
**Pitfall:** Only clean if the event really is the dominant reason front-month IV exceeds the forward — illiquid specific strikes, a second smaller catalyst in the same window, or stale quotes contaminate it. If front-month IV is *below* the back month's, the model breaks and shouldn't be forced through.
**🔁 Same underlying signal as the "implied earnings/event jump" card in the BREAKEVEN section (Book 2, Book 3 backing)** — different derivation path, same output; treat as corroboration, not a separate signal.
**Source:** Book 1, Ch. 3.

### Range-vs-close-to-close estimator disagreement flags *where* volatility is coming from
**Idea:** When a range-based estimator (Parkinson, Garman-Klass, etc.) runs well above the close-to-close estimate for the same name/period, realized variability is concentrated intraday rather than in day-over-day closes — relevant for choosing hedge frequency, or flagging names (e.g., ADRs missing their primary market's news flow) with a structurally elevated intraday/close ratio.
**Heuristic:** Track the range-estimator/close-to-close ratio as its own diagnostic series per name; a ratio well outside that name's own historical norm signals a change in where information is being incorporated — relevant context before trusting close-based term-structure or skew signals for that name.
**Pitfall:** Range-based estimators are systematically biased low under discrete sampling (worse for Garman-Klass than Parkinson) — correct for the known bias before comparing across names with very different liquidity/trade-count profiles, since the bias itself depends on sample size.
**Source:** Book 1, Ch. 2.

---

## 5. BREAKEVEN

### Position-level breakeven vol = input vol + edge/vega
**Idea:** For any position with theoretical edge and vega, the vol level at which it stops being profitable ≈ `input_vol + (theoretical_edge / vega)` — generalizes "implied vol" from a single option to a whole structure.
**Heuristic:** Compute breakeven vol for any candidate multi-leg structure; express margin-for-error as `breakeven_vol − vol_forecast`, and rank/size candidates by this margin rather than raw edge alone.
**Expression sketch:** `breakeven_vol = input_vol + total_theoretical_edge / total_vega`; `margin_for_error = breakeven_vol − vol_forecast`.
**Pitfall:** First-order linear approximation — breaks down for large vol moves since vega itself changes with vol (volga). Local/first-order risk gauge only.
**Note:** Probably the single most directly BRAIN-expressible idea in this whole knowledge base — high implementation priority.
**Source:** Book 4, Ch. 7, 21.

### Volga determines symmetric vs. asymmetric breakeven risk
**Idea:** Structures with identical starting vega can have very different large-vol-move P&L profiles depending on their volga. Straddles: roughly flat vega (low volga). Ratio spreads/skewed structures: strong positive or negative volga — losses/gains accelerate or decelerate disproportionately even with similar near-term breakeven math.
**Heuristic:** For two candidates with similar linear-approx breakeven vol, differentiate by volga — positive volga gives better tail protection (losses decelerate, gains accelerate) in a large vol spike, preferable under genuine large-move uncertainty.
**Expression sketch:** `volga_position = Σ(vega_i × d²V_i/dσ²)` — rank by `(breakeven_vol, volga)` pair, not breakeven alone.
**Pitfall:** Structures with attractive volga by construction (long butterflies) typically embed limited base-case profit — "good volga" trades off against smaller edge, not a free lunch.
**Source:** Book 4, Ch. 13.

### Gamma/theta efficiency ratio — fast same-expiry comparison proxy
**Idea:** For same-expiry structures (no vega/term-structure differentiation), `gamma/theta` is a quick order-of-magnitude ranking of "move protection bought per unit of time decay."
**Heuristic:** Pre-screen candidate same-expiry structures by `|gamma/theta|` before running full simulation — prefer smaller absolute ratio for negative-gamma/positive-theta structures, larger for positive-gamma/negative-theta.
**Pitfall:** Only valid within the same expiry — says nothing about vega/skew risk, must be paired with those before a real decision.
**Source:** Book 4, Ch. 13.

### Early-exercise breakeven threshold — data-hygiene tool, not an alpha signal
**Idea:** An American call is a genuine early-exercise candidate only when expected dividend value exceeds remaining vol value (proxied by the OTM put) plus interest earnable on strike — and only the day before ex-div. Puts have an analogous, date-independent threshold with a computable pre-dividend blackout window.
**Heuristic:** Compute this threshold per deep-ITM American option around known ex-div dates; large market-vs-theoretical deviations flag either a dividend-arb opportunity or a stale/thin quote to filter from downstream vol-signal construction.
**Expression sketch:** `blackout_days = dividend / (strike × daily_rate)`; flag names/strikes inside the window from any put-based signal construction.
**Pitfall:** Narrow scope — only relevant for American, dividend-paying, deep-ITM, near-ex-div options; irrelevant noise for European index options or non-dividend names.
**Source:** Book 4, Ch. 16.

### Implied event/earnings jump size, back-solved from front-vs-second-month IV — corroborated 2×
**Idea:** Total implied variance for an expiry spanning a known event = diffusive variance + event-jump variance. Using a non-event (second) expiry's IV as the diffusive-vol proxy, solve algebraically for jump-specific vol and thus the market-implied expected absolute move.
**Heuristic:** `σ_jump² = σ_(expiry after event)²×T − σ_diffusive²×T`; convert to expected move via `E[|R|]=√(2/π)×σ_jump`. Compare to an independent move estimate to decide buy-vol-ahead (if underpriced) or sell-into-event (if overpriced).
**Expression sketch:** `implied_jump_move = sqrt(2/pi) * sqrt(iv_after_event^2*T_after - iv_diffusive^2*T_after)`
**Pitfall:** For index-level estimates, must first strip the macro/index-level upward-sloping term-structure component before attributing the residual to the event, or the jump estimate inflates.
**🔁 Given a rigorous theoretical backing by Book 3's Merton mixing-formula card below** — high-confidence, recommend attaching that derivation as the formal justification for this heuristic.
**Source:** Book 2, Ch. 6.4; Book 3, Ch. 23–24 (theoretical backing).

### Barrier/knock-out option pricing shortcuts (KO+KI=vanilla identity)
**Idea:** Knock-out put + knock-in put of identical strike/barrier = vanilla put exactly. So "cheap-looking" knock-outs imply correspondingly "expensive-looking" knock-ins (roughly vanilla-priced); a knock-out's fair price sanity-checks as ~15-25% of the corresponding vanilla put spread for barriers 10-30% below strike.
**Heuristic:** Use the KO+KI identity and the put-spread-fraction rule as a quick consistency check before accepting a quoted barrier price; a price well outside the ~15-25% band warrants closer scrutiny.
**Expression sketch:** `KO_put_price ≈ 0.15-0.25 * put_spread_price(strike, barrier)`
**Pitfall:** Discrete (close-only) barriers price differently from continuous (intraday) barriers — discrete knock-outs cost more, knock-ins less, especially in high-vol regimes; calibrate the rule separately per convention.
**Source:** Book 2, Ch. 5.1.

### Put spreads/ratio put spreads must have positive cost — bounds how negative skew can get
**Idea:** A standard put spread payoff can never be negative, so its price can never be negative — a no-arb condition that mathematically caps skew steepness, decaying ~√time, tightening to decay-by-time for very long-dated (~5yr+) maturities under the stricter ratio-spread version.
**Heuristic:** When a quoted/modeled skew approaches its theoretical no-arb bound, treat it as a hard ceiling rather than assuming continued richening; in practice richness is arbitraged away well before the literal bound, so *approach toward* (not just breach of) the bound is itself informative.
**Expression sketch:** compute the theoretical bound (d1-based formula); track `observed_skew / theoretical_bound` as a "room to run" gauge.
**Pitfall:** A hard arbitrage constraint, not a typical trading range — skew is priced well inside it most of the time; using distance-from-bound alone (without comparing to the security's own historical range) misses genuinely rich-but-not-extreme skew.
**🔁 Same underlying constraint as the SKEW-section "no-arbitrage ceiling" card (Book 3) — corroborated derivation, different angle.**
**Source:** Book 2, Ch. 7.2, Appendix A.6.

### Discrete delta hedging with a smile requires a chain-rule correction to delta
**Idea:** When IV varies systematically with both strike and spot, the true hedge ratio is `Δ_BSM + (∂C/∂Σ)(∂Σ/∂S)`, not naive BSM delta. Using the uncorrected delta introduces a hedging-error P&L drag on the order of vega × local skew sensitivity — which can dominate the theoretical gamma-scalping profit the position is nominally capturing.
**Heuristic:** For any hedged-carry strategy in a name with measurable persistent skew, size the delta hedge with the corrected Δ, not raw BSM delta — the correction can be near half the naive delta itself in liquid index options, dwarfing typical single-day gamma P&L.
**Expression sketch:** `delta_corrected = N(d1) + vega * dSigma_dS`, with `dSigma_dS` from the fitted local skew slope.
**Pitfall:** Sign/magnitude of the correction differs (can flip) depending on whether local-vol or stochastic-vol better describes the underlying dynamics (see TERM-STRUCTURE section) — applying the wrong sign actively worsens the hedge. Never apply without first establishing the regime.
**Source:** Book 3, Ch. 10, 16.

### Barrier options can be statically replicated with a small vanilla-option basket
**Idea:** Rather than continuous dynamic hedging (expensive/error-prone near a barrier where gamma explodes), a knock-out's payoff can be approximated with a static vanilla basket chosen so portfolio value is zero on the barrier at several discrete time points, plus matching terminal payoff. More matched time-points = better approximation, with errors concentrated near expiry/close-to-barrier.
**Heuristic:** For OTC barriers without a liquid dynamic-hedging capability, construct a static replicating basket (calls above an above-spot barrier, puts below a below-spot barrier, at the barrier strike and several maturities back from expiry) rather than a pure Greek-based dynamic hedge — often more robust and lower-cost near the knockout level.
**Pitfall:** "Weak" replication — only holds within the assumed pricing model; if true smile dynamics differ from the assumption used to pick strikes/expiries, replication drifts and needs rebalancing exactly when the barrier is approached — the worst time for execution risk.
**🔁 Extends the Book 2 KO+KI barrier-identity card into a full constructive hedging methodology** — complementary, not redundant.
**Source:** Book 3, Ch. 12.

### Merton jump-diffusion mixing formula — rigorous backing for implied-jump signals
**Idea:** Under compensated-drift jump-diffusion, a European option's price is exactly a Poisson-weighted sum of ordinary BSM prices at shifted forward rates and volatilities, one term per assumed jump count `n` — letting a trader see exactly how much of jump-diffusion value comes from the 0-jump, 1-jump, 2-jump, etc. scenarios and where to safely truncate.
**Heuristic:** For a short-dated OTM option a pure-diffusion BSM badly mispriced, decompose fair value into the first 4-6 Poisson-weighted terms rather than assuming one "jump-adjusted" vol number — a small number of high-value moderate-probability jump scenarios often dominates total premium in a way one blended vol can't capture.
**Expression sketch:** `C_JD = Σ_{n=0}^{N} [(lambda_eff*T)^n / n!] * exp(-lambda_eff*T) * C_BSM(S, K, T, sigma_n, r_n)`, truncate once term weight <~0.1%.
**Pitfall:** Assumes jump risk is diversifiable/idiosyncratic to justify risk-neutral valuation — weak for market-wide crash jumps (the type most relevant to index skew), so treat the result as a lower-bound reference price; real crash-protection prices likely trade above it (jump-risk premium the model doesn't capture).
**Note:** This is the formal derivation backing the more heuristic implied-jump-from-IV-spread cards in Book 2 (and Book 1, which now also has its own independent derivation — see the term-structure section above).
**Source:** Book 3, Ch. 23–24.

### Hedged-option P&L variance scales with 1/√N of hedge frequency — precise formula, corroborates the Book 3 √N card
**Idea:** Even with a perfectly correct vol forecast, discretely-hedged P&L is a distribution, not a certain outcome — its std dev scales roughly as `vega × σ × sqrt(π/4) / sqrt(N)`, N = number of rehedges. The same "correct" call can realize a wide range of outcomes purely from hedge-timing noise, separate from forecast error.
**Heuristic:** Don't rank/size candidate trades by expected edge alone — estimate this realization-noise std dev from the structure's expected hedge frequency and tenor, and use edge-relative-to-noise for ranking. Short-dated, infrequently-rehedged, or large-vega structures show much wider realization variance around the same expected edge than long-dated, frequently-rehedged, small-vega ones.
**Expression sketch:** `realization_std ≈ vega × σ × sqrt(π/4) / sqrt(N_expected_hedges)`; `risk_adjusted_edge = expected_edge / realization_std`.
**Pitfall:** Assumes continuous (diffusive) behavior between hedges — real gap/jump risk adds a non-diminishing-with-N variance source this formula doesn't capture. Treat as a lower bound on realization noise, not the whole picture.
**🔁 The precise, formula-based version of the Book 3 discrete-hedging-noise card in the TERM-STRUCTURE section** — use this exact formula if the pipeline needs a number rather than a directional caveat.
**Source:** Book 1, Ch. 5 (Kamal & Derman 1999).

### Hedging at implied vs. realized vol changes P&L *shape*, not expected value — know which convention you're implicitly using
**Idea:** Hedging at realized (forecast) vol gives a genuinely stochastic daily P&L (can swing meaningfully day to day even when "properly hedged," since the market marks the option at a different implied vol). Hedging at the transacted implied vol gives a deterministic-form, smoother daily P&L — but the *terminal* P&L becomes more path-dependent, since how much edge you actually capture depends on remaining gamma exposure as the underlying drifts from the strike.
**Heuristic:** Decide explicitly which hedging convention is in use before entering a vol trade, and set expectations accordingly — hedging-at-implied gives smooth, explainable daily marks but a more binary/path-dependent final outcome; hedging-at-forecast gives a noisier path but a cleaner unbiased edge estimate as it's realized. Don't judge a trade's success by daily P&L smoothness under the implied-vol convention — that smoothness is by construction.
**Pitfall:** A trader hedging at implied vol seeing smooth small daily gains can mistake this for confirmation the trade is working, when the real edge realization is still fully path-dependent on where the underlying ends up relative to strike at expiry.
**Source:** Book 1, Ch. 5.

### Apparent IV richness may just be correctly-priced hedging/transaction cost, not genuine mispricing — a false-positive control for the whole breakeven family
**Idea:** Leland's transaction-cost-adjusted vol shows the "fair" IV for a discretely-hedged position is systematically higher than the frictionless fair vol, by an amount depending on bid/ask spread, rehedge frequency, and gamma. A short-dated, illiquid, low-vol name can show "rich-looking" IV that's entirely explained by hedge-maintenance cost, with zero genuine mispricing.
**Heuristic:** Before treating elevated IV as a short-vol signal (especially illiquid or low-vol names), net out an estimated transaction-cost-implied premium and compare the *residual* IV to the forecast, not raw IV to raw forecast — most important for wide-relative-spread names or where dynamic hedging is expected to be frequent.
**Expression sketch:** `cost_adjusted_iv_premium ≈ bid_ask_spread_proportional × sqrt(8/(π × rehedge_interval))`; "true" mispricing signal = `(implied_vol − cost_adjusted_iv_premium) − forecast_vol`, not `implied_vol − forecast_vol`.
**Pitfall:** Cost and genuine volatility both make hedging "harder" but are economically different — vol is a two-sided, tradeable risk/reward factor; transaction cost is a pure cost with no offsetting reward. Determine which is driving apparent choppiness before adjusting a signal threshold.
**🔁 A quantified, breakeven-specific application of the Book 3 Leland's-formula card in TERM-STRUCTURE** — same formula, applied here as a signal false-positive filter rather than a pricing adjustment.
**Source:** Book 1, Ch. 4 (Leland; Whalley-Wilmott).

### Gamma value realizes disproportionately near-the-money and near expiry — prefer strangle/strip structures for a broad realized-vol view
**Idea:** Long-gamma profit concentrates where/when gamma is largest — near the money, close to expiry. An ATM straddle that drifts away from the strike "uses up" most of its edge-capturing ability early, even if the total realized-vol forecast over the option's whole life is correct.
**Heuristic:** For trade ideas expressing "realized vol will be higher/lower than implied across a wide price range" (vs. a precise pinning view), prefer strangle/strip structures spanning a wider strike range over a single ATM straddle — reduces the risk that gamma (and thus edge-capturing ability) concentrates in a narrow zone the underlying may not stay near.
**Pitfall:** A structural point about capturing edge, not a claim OTM strikes are generally better risk-adjusted — strangles/strips carry their own decay/vega profile; don't read this as "always prefer wings over ATM."
**Note:** Directly tied to why different strikes trade at different IVs (path-dependence of gamma capture) — cross-relevant to the skew archetype too.
**Source:** Book 1, Ch. 5.

---

## 6. OTHER — cross-cutting tools, sizing, and candidate new archetypes

> Not standalone signal-generation archetypes on their own — this section sits *underneath* the 5 core archetypes above: QA gates, sizing/bankroll layers, and genuinely new archetype candidates worth a "6th tag" if you decide to add one.

### BSM as replicating-portfolio P&L decomposition
**Idea:** A delta-hedged option's P&L per period splits into gamma (convexity, positive), theta (time decay, negative), and financing — setting the sum to zero (no arb) yields the BSM PDE.
**Use:** Decompose realized hedged P&L into gamma-scalping vs. theta components to check whether a vol-trade thesis (not directional) is actually working.
**Pitfall:** Breaks down under jumps or discrete hedging — assumes continuous smooth paths.
**Source:** Book 1, Ch. 1.

### Quick vol-from-average-move conversion (QA sanity check)
**Idea:** `E[|R|]=√(2/π)·σ`, so annualized vol ≈ 20× average daily absolute return.
**Use:** `annualized_vol ≈ 19.896 * mean(abs(daily_return))` as a rapid cross-check; flag disagreement with a slower estimator as a methodology/data error signal.
**Pitfall:** Breaks down when returns are far from normal (fat tails).
**Source:** Book 1, Ch. 2.

### Bias correction for realized-vol estimators (Jensen's inequality)
**Idea:** `√(sample variance)` is biased-low; correction factor `b(N)=√(2/N)·Γ(N/2)/Γ((N−1)/2)` must divide the raw estimate, more severe at small N (`b(5)≈0.84` vs. `b(200)≈0.996`).
**Use:** `rv_debiased = rv_raw / b(N)` before comparing short-window RV to implied vol or longer-window estimates.
**Pitfall:** Ignoring this creates a systematic downward bias in short-window RV that can masquerade as a real term-structure/VRP signal. **Apply this correction pipeline-wide wherever short-window RV feeds a signal.**
**Source:** Book 1, Ch. 2, eq. 2.4–2.9.

### Kelly criterion for position sizing — candidate distinct archetype (sizing layer)
**Idea:** Optimal log-wealth-growth bet fraction `f=(pw−ql)/(wl)` generalizes to `f=r/σ²` for small-edge trades. Overbetting Kelly lowers growth rate *and* raises volatility; fractional Kelly trades growth for smaller drawdowns.
**Use:** `size = k_fraction * expected_edge / variance_of_payoff` as a sizing multiplier, default 0.3–0.5x Kelly. P(halve before double) is 1/3 at full Kelly, ~0.06% at 0.2x.
**Pitfall:** Full Kelly is extremely volatile even with genuinely correct edge; overestimating win probability near full-Kelly is a classic disaster mode — err toward underestimating edge.
**Source:** Book 1, Ch. 6, eq. 6.5, 6.14–6.16.

### Kelly sizing for a mean-reverting (OU) process
**Idea:** For a normalized OU spread, log-utility-optimal size is `−W·σ/2`, independent of reversion speed. Optimal scale-in peaks at `σ=√2` deviation, beyond which further scaling is dominated by wealth depletion.
**Use:** Size mean-reversion vol trades proportional to SD-distance from the mean up to ~√2 SDs, then taper.
**Pitfall:** Assumes normal innovations; under fat tails, entering more aggressively but exiting faster tends to work better. Can't distinguish temporary deviation from a permanent mean shift — scaling into a broken regime is the main failure mode.
**Note:** A second extraction pass over this book re-confirms this result and adds one detail: under a fat-tailed (logistic) alternative distribution, performance degrades relative to the idealized normal case, and the "keep scaling to √2 std devs" rule gets considerably riskier, since a genuine regime change looks identical to an attractive entry point in the model. Also explicitly connected to "when in trouble, double" market-maker folklore.
**Source:** Book 1, Ch. 6, eq. 6.27–6.28.

### Risk-adjusted performance ratios and their sampling error
**Idea:** Sharpe penalizes up/down vol equally with large sampling error (`Var(Sharpe)≈(1/T)(1+SR²/2)` — same order of magnitude as the ratio itself). Sortino uses downside only. Calmar uses max drawdown (Calmar≈1 is "good" — expect a drawdown ~= your target return). Omega uses the full distribution above/below a threshold.
**Use:** Flag `measured_sharpe < 2*sharpe_sd` as statistically indistinguishable from zero rather than ranking candidates by raw in-sample Sharpe; prefer Calmar/Omega for asymmetric short-vol-style payoffs.
**Expression sketch:** `sharpe_sd = sqrt((1 + sharpe^2/2) / T)`
**Pitfall:** All are historical-window statistics, blind to unrealized tail risk (the "peso problem") — a strategy can show high Sharpe purely because a large loss hasn't happened in-sample yet. Classic short-vol trap.
**Note:** Worth adding as an explicit local-filter stage on top of existing Sharpe/Fitness thresholds — catches "passed by noise" candidates.
**🔁 Reinforced independently by Book 3's leverage-invariant-Sharpe/CAPM card below** — same evaluation-methodology theme.
**Source:** Book 1, Ch. 7, eq. 7.1–7.6.

### Simple pricing/vol rules of thumb (automated sanity-check gates)
**Idea:** (1) annualized vol ≈ 16× average daily % move (√252≈16); (2) ATM premium (%) ≈ `0.4 × IV × √T`; (3) delta-hedged P&L scales with the *square* of the move, not linearly; (4) hedging carry depends on the *linear* difference between realized and implied vol, not the difference of their squares (dollar gamma ∝ 1/σ cancels the extra σ).
**Use:** Flag computed ATM premiums or P&L-attribution models that violate these relationships as likely implementation bugs, not real findings.
**Expression sketch:** `atm_premium_check = 0.4 * iv * sqrt(T)`; `carry_pnl ≈ dollar_gamma_const * (realized_vol - implied_vol)`.
**Pitfall:** Zero-rate, zero-dividend, flat-vol approximations — degrade for long-dated, high-rate, or heavily skewed surfaces; order-of-magnitude checks only.
**Note:** The "profit ∝ move²" and "carry = realized−implied, not variance difference" points sharpen the vega-form VRP card above.
**Source:** Book 2, Ch. 2.1.

### Gamma scalping cost asymmetry: passive when long gamma, forced spread-crossing when short
**Idea:** Long gamma naturally wants to buy on dips/sell on rallies — resting limit orders can monetize gamma *and* earn the spread. Short gamma requires the opposite, mechanically forcing spread-crossing on every rehedge — a real, often-underappreciated cost, especially in wide-spread names.
**Use:** Explicitly add an estimated spread-crossing cost per rehedge (∝ trade frequency × average bid-offer width) when estimating realistic short-gamma strategy costs — this cost is asymmetric between long/short-gamma programs and easy to omit from naive backtests.
**Expression sketch:** `short_gamma_hedge_cost ≈ num_rehedges * avg_bid_offer_width * avg_hedge_size`
**Pitfall:** Long-gamma's passive-execution advantage requires genuine two-sided liquidity and time to work orders — during fast/gappy moves (when gamma matters most), passive execution may not be achievable, eroding the advantage exactly when needed.
**Source:** Book 2, Ch. 2.1.

### Delta-hedged programs can mechanically "pin" illiquid underlyings near a strike into expiry — candidate distinct archetype
**Idea:** A large enough long-gamma position (e.g., a sizable convertible) forces hedging that sells into rallies above and buys into declines below the strike — precisely at the strike — pinning the stock's price near it, with a potential catch-up "snap back" once the position expires and pinning pressure disappears.
**Use:** For illiquid single names with known large convertible/option open interest near expiry, expect suppressed realized vol and price stickiness near that strike into expiry, followed by a potential post-expiry catch-up move — a name-specific RV-forecasting signal generic GARCH/historical-vol models miss.
**Pitfall:** Requires hedging flow large relative to trading volume and a relatively calm market; a strong independent catalyst can overwhelm it entirely; liquid indices essentially never pin this way.
**Source:** Book 2, Ch. 2.1.

### Vega, vanna, volga map onto the 2nd, 3rd, and 4th statistical moments — foundational measurement framework
**Idea:** Vol-surface shape decomposes via moments: variance (2nd, vega/ATM), skew (3rd, vanna/risk-reversal, decays √time), kurtosis (4th, volga/butterfly, decays by time, most important near-dated only). Gamma theta pays for the vega/variance bet; skew theta specifically pays for the skew bet and can be compared against "power vanna" (vanna×√time) to find mispriced skew.
**Use:** To isolate skew richness/cheapness from general vol-level richness, compare skew-theta cost to √time-weighted vanna exposure rather than raw cross-strike IV comparison.
**Expression sketch:** `power_vanna = vanna * sqrt(T)`; compare against skew_theta-per-unit-vanna across strikes/maturities.
**Pitfall:** Vanna/volga peak around 10-15 delta options specifically — applying this framework to near-ATM options (where they're small) produces noisy, low-signal results.
**🔁 Reinforced and extended by Book 3's stochastic-vol-specific vanna/volga smile card** (SKEW section) — recommend merging into one unified "moment decomposition" reference card at final consolidation.
**Source:** Book 2, Ch. 7.4, Appendix A.8.

### Capital structure arbitrage: credit spreads and equity skew, linked via jump-to-default risk — genuinely new archetype candidate
**Idea:** A jump-diffusion framework splits equity vol into a diffusive component and a jump-to-bankruptcy component sized by credit spread; because bankruptcy-jump risk disproportionately impacts low-strike (put) time value, a rising credit spread mechanically produces "credit-induced skew" even with unchanged diffusive vol. The Merton model separately shows equity IV ≈ enterprise vol × leverage — skew also arises simply from leverage rising as price falls.
**Use:** For single names with actively traded CDS, monitor CDS spread changes as a leading/coincident input for expected equity skew direction — a widening CDS spread with unchanged equity skew signals equity skew may be underpricing jump-to-default risk (and vice versa).
**Expression sketch:** derive a "no-default implied vol" by stripping the CDS-implied jump-to-default value out of put prices, compare this flattened surface's skew to raw equity skew — the gap approximates credit-implied skew.
**Pitfall:** Strongest for BBB/BB names specifically — investment-grade spreads are driven more by rate/supply factors, single-B-or-below by idiosyncratic default speculation. Single-name equity-CDS correlation is only 5-15% (vs. ~90% at portfolio level) — this is a portfolio-level, not single-name-reliable, signal, and sudden leverage-changing events can decouple the relationship abruptly.
**Note:** Not currently covered by any of the 5 core archetypes — links an external market (credit/CDS) to equity skew via a specific, testable mechanism. Strong candidate for a 6th archetype if you have or can get CDS data alongside options data.
**Source:** Book 2, Ch. 7.1, Appendix A.12.

### Models are relative-valuation interpolation tools, not forecasts — foundational epistemic gate
**Idea:** BSM and similar models are best understood as telling you how to extrapolate from a known, liquid price to a related, less-liquid one *today* — not how prices will evolve, the way physics predicts a trajectory. An "implied" parameter (implied vol, local vol, implied correlation) is a distilled summary of current relative prices absorbing all the frictions an idealized model ignores, not a forecast.
**Use:** When a backtested "mispricing" signal persistently fails to resolve, ask whether the "fair value" benchmark is itself a legitimate replication-based interpolation from currently-liquid prices, or an unhedgeable theoretical construct — a signal built on an unreplicable value isn't really edge, just a modeling artifact.
**Pitfall:** Can be used to dismiss genuinely valid signals too aggressively if taken as "nothing is real unless perfectly replicable" — the practical middle ground is *approximate* replication with bounded, quantifiable error, still meaningfully more robust than an unreplicable economic model.
**Note:** Foundational gating principle for the entire OTHER category and arguably for the whole pipeline's "is this a real signal" question — not itself a signal.
**Source:** Book 3, Ch. 1–2.

### Sharpe ratio is leverage-invariant — a sanity gate against "leverage masquerading as edge"
**Idea:** Diluting/levering a position with the riskless asset doesn't change its Sharpe ratio. Extending the law-of-one-price logic across uncorrelated assets, then to a common-market-factor world, recovers a CAPM-style result: excess return = beta × market excess return, with diversifiable idiosyncratic risk earning zero premium.
**Use:** When a strategy shows an unusually high Sharpe, check whether it's simply levered up (Sharpe should be unchanged by pure leverage at the riskless rate) versus a structural risk/return change — a "higher Sharpe from leverage" claim is a definitional red flag.
**Expression sketch:** `if sharpe_change > threshold and leverage_change != 0 and financing_rate == riskless: flag_for_review`
**Pitfall:** Assumes free borrowing/lending at a single riskless rate and mean-variance-only preferences — real financing spreads, skew/kurtosis preferences, liquidity, and tax effects can cause genuine (not illusory) Sharpe changes from leverage. Useful null hypothesis, not an absolute rule.
**Source:** Book 3, Ch. 2.

### Compensated-drift calibration integrity for jump-diffusion models
**Idea:** Adding a jump term shifts a stock's expected growth away from pure-diffusion drift; risk-neutral pricing requires the diffusion drift be compensated (`μ' = r − σ²/2 − λ(e^J−1)`, or its normal-jump-size generalization) to preserve expected riskless growth.
**Use:** Before fitting jump-diffusion parameters (λ, jump size) to market option prices, verify the diffusion drift has been correctly compensated — an uncompensated/miscompensated drift silently biases fitted jump parameters even if resulting option prices happen to match the market (the same market price can come from multiple (λ,J) combos if compensation isn't applied consistently).
**Expression sketch:** `mu_compensated = r - sigma^2/2 - lambda*(exp(mu_J + 0.5*sigma_J^2) - 1)`
**Pitfall:** Assumes jump risk is diversifiable enough to justify risk-neutral valuation at all — weak for market-wide crash jumps specifically; even a correctly-compensated model may still misprice systemic jump risk carrying a genuine real-market risk premium.
**Source:** Book 3, Ch. 23–24.

### Path-dependency / vol-timing — candidate distinct archetype
**Idea:** Two price paths with identical total realized vol can produce very different dynamic-hedged P&L, since gamma/theta peaks for ATM options near expiry. Vol concentrated late in life with the underlying near-strike → long-gamma captures far more value than a constant-vol model predicts; vol concentrated early with the underlying drifting away → captures far less. One number ("volatility") hides this.
**Use:** For dynamically-hedged (not held-to-expiry) strategies, don't rely solely on a total-period vol forecast — model sensitivity to *timing* of realized vol (front- vs. back-loaded historical vol clustering for that instrument).
**Pitfall:** Largest for near-the-money options close to expiry; largely irrelevant for far-OTM/ITM or unhedged-to-expiry options — scope narrowly.
**Note:** Flag as a real `other`-archetype candidate specifically if/when the pipeline adds dynamically-hedged strategies rather than static candidates.
**Source:** Book 4, Ch. 23.

### Gap/jump risk mispricing — candidate distinct archetype
**Idea:** Continuous-diffusion models assume no gaps, but real markets gap on news/weekends/illiquidity. The impact is disproportionately larger for near-ATM, near-expiry, low-assumed-vol options (highest gamma, no chance to rehedge through the gap) — a systematic, structural case for such options being underpriced, and a plausible explanation for IV's general tendency to run above subsequent RV.
**Use:** Flag short-dated, near-the-money, low-current-IV legs as maximally exposed to (and, if short, most likely to be systematically underpriced relative to) jump risk — the same condition that makes cheap short-dated ATM straddles attractive in quiet markets.
**Pitfall:** Slow-moving structural bias (small edge, fat-tailed rare payoff), not a reliable per-trade signal — most individual instances lose by design; don't backtest on a short sample, it will look like a loser most of the time.
**Source:** Book 4, Ch. 23.

### Direct volatility instruments (VIX, variance swaps) decouple vol-trading from options-hedging mechanics — candidate distinct archetype
**Idea:** Variance swaps settle on realized variance directly; VIX-family instruments settle on a model-free implied-vol strip. These enable a vol view without an options-hedging engine — but VIX futures show strong contango/roll effects and do NOT move point-for-point with spot VIX, and VIX itself behaves more like a fear/hedging-demand gauge than a calibrated RV forecast (negligible correlation between VIX level/changes and subsequent RV changes, per the source's own 10-year study).
**Use:** If incorporating VIX-family products directly, model the futures/spot basis and roll-yield as a first-class feature — don't assume futures returns ≈ spot-VIX returns.
**Expression sketch:** `vix_futures_roll_yield = (futures_price(t) − futures_price(t-1)) / spot_move(t)`, tracked by days-to-expiry bucket.
**Pitfall:** Do not treat "VIX rose" as "RV about to rise" — near-zero empirical correlation between the two; VIX correlates strongly with *index returns* (negative), not with future RV.
**Note:** Overlaps but is distinct from the Book 2 TERM-STRUCTURE cards on VIX futures pricing — this one is about the level/interpretation of VIX itself, those are about the futures curve's relative-value mechanics.
**Source:** Book 4, Ch. 25.

---

## Cross-book high-confidence themes (corroborated independently by 2+ sources)

These are the strongest candidates to implement first — independent derivation across separate books is the best available evidence of genuine, non-spurious relationships:

1. **√T skew-normalization / "rule of two"** (Books 2 & 3) — skew decays ~√time across the curve; local-vol slope is ~2× implied-vol slope.
2. **No-arbitrage ceiling on skew steepness** (Books 2 & 3) — put-spread positive-cost argument, same constraint derived two ways.
3. **Discrete-hedging path-dependence / noise from vol mismatch** (Books 1, 2, & 3) — hedging at the wrong (implied vs. realized) vol reintroduces noise that finer rehedging can't fix.
4. **Vega/vanna/volga moment decomposition** (Books 2 & 3) — the general measurement framework and its stochastic-vol-specific derivation should be merged into one reference.
5. **Implied vol structurally biased above realized** (Books 1, 2, & 4) — partly rational risk premium, partly persistent structural overpricing; three independent framings of the same core VRP phenomenon.
6. **Merton jump-diffusion mixing formula as backing for implied-jump-from-IV-spread heuristics** (Books 2 & 3) — the rigorous derivation should be attached to the more practical Book 2 heuristic.
7. **Sharpe ratio sampling-error/leverage-invariance caution** (Books 1 & 3) — two independent angles on the same "don't trust raw Sharpe rankings" gate; worth implementing as an explicit filter stage.
8. **Event-implied jump size from front-vs-back-month IV** (Books 1, 2, & 3) — now derived independently three times (two different formula paths in Books 1 and 2, plus Book 3's Merton mixing-formula backing) — probably the single highest-confidence, most directly implementable signal in this whole knowledge base.
9. **Index skew's implied-correlation channel** (Books 1 & 2) — index skew rising purely from expected correlation increase, independent of every component surface being flat — corroborated twice, worth a dedicated dispersion-trade feature.
10. **Transaction-cost-implied vol richness (Leland's formula)** (Books 1 & 3) — same formula surfaced twice, once as a pricing adjustment (Book 3) and once as an explicit false-positive filter for breakeven signals (Book 1) — implement as a standard pre-signal filter, not just a pricing footnote.

## Candidate archetypes beyond the current 5

Worth a real "6th tag" (or dedicated pipeline module) if you want to pursue them:

- **Position sizing / bankroll management** (Kelly and OU-Kelly cards, Book 1) — currently absorbed into `other`, but distinct enough from signal generation to warrant its own module.
- **Path-dependency / vol-timing** (Book 4) — only relevant if/when the pipeline moves to dynamically-hedged rather than static candidates.
- **Gap/jump risk mispricing** (Book 4) — structural, slow-edge, fat-tailed-payoff strategy family.
- **Direct volatility instruments** (Book 4, overlapping Book 2's VIX cards) — VIX/variance-swap-specific relative value, distinct from options-derived signals.
- **Capital structure arbitrage / credit-equity skew link** (Book 2) — needs CDS data; genuinely new external-data archetype.

## Open flags

- No `pcr-flow` coverage from any of the three books that touch it (Book 1, Book 3, Book 4 — the equity-derivatives handbook, "Book 2" in this file, remains the only source with a real flow-related card, and even that one is more "flow explains skew" than a standalone tradeable signal). This archetype is the thinnest in the corpus by far — prioritize a flow/positioning-focused source next if you continue past Book 4.
- Book 1 (Sinclair) has now had two extraction passes over Ch. 1–7 merged, but still has no `forward-basis` cards — check whether the book covers forward pricing/basis mechanics elsewhere, or accept that this archetype's coverage will keep coming from Books 2 and 4.
- **Labeling caution for future extraction sessions:** the same source book got extracted twice under two different "Book N" labels in two different chat threads before landing here. When starting a new extraction thread, paste the book's title into the very first message so future consolidation passes can catch this automatically instead of relying on a manual re-read.
