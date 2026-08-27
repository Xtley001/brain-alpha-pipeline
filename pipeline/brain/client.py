"""
Thin wrapper around the `wqb` BRAIN client: auth, single simulate, poll for
a result, and convert the response into the `SimResult` shape the sweep
module expects.

Hard rule, per the project's build prompt and audit checklist:
this module (and this codebase) never calls a BRAIN submit/create endpoint.
Submission is manual, always. There is intentionally no `submit(...)`
method anywhere below, and none should ever be added.

`wqb` is imported lazily so importing this module doesn't require network
access or the package installed just to run the rest of the test suite.

STILL UNVERIFIED AGAINST A REAL ACCOUNT as of Update 10 Item 8 -- READ
BEFORE TRUSTING LIVE RESULTS FROM THIS MODULE:

`_parse_sim_response`/`_parse_pnl_response` below pull metrics out of
BRAIN's JSON with soft fallbacks (`.get(..., 0.0)`, tolerating a couple of
plausible key names). If BRAIN's real response doesn't nest stats under
`"is"`, or uses different key names than assumed, these functions do NOT
raise -- they quietly return 0.0 / an empty series, and a genuinely strong
candidate would then fail the local filter silently, looking exactly like a
bad idea (see Update 02 P0.1 for the full failure mode).

Update 10 Item 8 status (read this honestly, not as boilerplate):

  - `scripts/verify_brain_parsing.py` was re-read in full and confirmed to
    already make a REAL network call against a live, authenticated BRAIN
    account (via `BrainClient.authenticate()` + `session.simulate(...)`) --
    it does NOT run against a fixture/mocked response. No fix was needed
    to that script for this sub-requirement.
  - It was NOT actually run against a live account during this update --
    no BRAIN_USERNAME/BRAIN_PASSWORD credentials, and no network route to
    BRAIN's API, were available in the environment this update was done
    in. This is stated plainly, not hedged: nobody has confirmed
    `_parse_sim_response`/`_parse_pnl_response` against real BRAIN JSON,
    still, as of this update.
  - What WAS done: the silent `.get(key, 0.0)` fallback behavior below now
    logs a loud (ERROR-level, impossible-to-miss-in-normal-log-output)
    warning the first time each specific key is ever observed missing from
    a real response, via `_warn_missing_key_once` -- so a schema mismatch
    in production stops being silently indistinguishable from a real,
    correct rejection and instead leaves a loud trace in the logs the very
    first time it happens. This does not replace running the verification
    script -- it's a safety net for if that verification is skipped or
    happens after this ships anyway.
  - `scripts/verify_brain_parsing.py` remains a manual step, not wired into
    CI (a CI job would need real BRAIN credentials as a repo secret and
    would burn real simulation quota on every push, which is a cost/quota
    tradeoff a human should decide, not something to silently wire in) --
    but SETUP.md's deploy section now states, in bold, explicit terms,
    that running it is a mandatory pre-trust step, not an optional
    diagnostic.

Every Sharpe/Fitness/turnover/correlation figure this pipeline has ever
produced remains unverified against live BRAIN output until a human runs
`scripts/verify_brain_parsing.py` against a real account and confirms the
parsed values match BRAIN's own dashboard. Treat all historical DB rows
accordingly until that happens.

Before trusting any number this module produces:

    1. Run `python scripts/verify_brain_parsing.py` against a real,
       authenticated BrainClient (see that script's own docstring for
       exact steps) and confirm the printed raw JSON matches what
       `_parse_sim_response`/`_parse_pnl_response` extract from it.
    2. Fix the key lookups in the two functions below if they don't match.

Do not treat sharpe/fitness/turnover/alpha_id/daily-return values from this
module as ground truth until that check has been run once, by a human,
against a real account.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pipeline.sweep.settings_sweep import Settings, SimResult

log = logging.getLogger("brain_client")

# Update 10 Item 8: which (context, key) pairs have already logged a
# missing-key warning -- deduped so a sustained schema mismatch doesn't
# spam the log once per simulation (which could be dozens per tick) while
# still guaranteeing the very first occurrence is loud and visible.
_warned_missing_keys: set[tuple[str, str]] = set()


def _warn_missing_key_once(context: str, key: str, data: Any) -> None:
    """Logs an ERROR-level (not silently-swallowed) warning the first time
    `key` is observed missing from a real BRAIN response in `context`
    ('sim_response' | 'pnl_response'). Update 10 Item 8: replaces pure
    silent `.get(key, 0.0)` fallbacks -- the fallback value is still used
    (a hard `raise` here would take the whole candidate down on every
    schema drift, which is worse than a possibly-wrong-but-visible 0.0 for
    an optional field), but a missing key can no longer be silently
    indistinguishable from a real, correctly-computed 0.0/rejection."""
    dedup_key = (context, key)
    if dedup_key in _warned_missing_keys:
        return
    _warned_missing_keys.add(dedup_key)
    log.error(
        "BRAIN response parsing: expected key %r missing from %s -- falling back "
        "to a default value, but this means the parsed metrics for this response "
        "may not reflect BRAIN's real output. This has NOT been verified against "
        "a live account (see this module's docstring / Update 10 Item 8) -- run "
        "scripts/verify_brain_parsing.py against a real account before trusting "
        "any number this module produces. Raw response keys seen: %s",
        key, context, sorted(data.keys()) if isinstance(data, dict) else type(data),
    )


# BRAIN's Simulation-1-block field names, in the exact order the UI shows
# them (also used for the "copy-paste ready" settings block in Telegram
# alerts and the review store).
SIMULATION_FIELD_ORDER = [
    "instrumentType",
    "region",
    "universe",
    "delay",
    "decay",
    "neutralization",
    "truncation",
    "pasteurization",
    "unitHandling",
    "nanHandling",
    "language",
    "visualization",
]


def settings_to_simulation_data(expression: str, settings: Settings) -> dict:
    """Build the JSON body BRAIN's /simulations endpoint expects for a
    single "Fast Expression" alpha, from our internal Settings dataclass."""
    return {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": settings.universe,
            "delay": settings.delay,
            "decay": settings.decay,
            "neutralization": settings.neutralization,
            "truncation": settings.truncation,
            "pasteurization": "ON" if settings.pasteurization else "OFF",
            "unitHandling": "VERIFY",
            "nanHandling": "ON" if settings.nan_handling else "OFF",
            "language": "FASTEXPR",
            "visualization": False,
        },
        "regular": expression,
    }


@dataclass
class BrainAuthError(Exception):
    message: str


class BrainClient:
    """Sync facade over wqb's async WQBSession, scoped to exactly what this
    pipeline needs: authenticate, run one simulation, read back metrics.
    Nothing here can call a submit/create-alpha endpoint."""

    def __init__(self, username: str, password: str, max_concurrent_sims: int = 3):
        self.username = username
        self.password = password
        self.max_concurrent_sims = max_concurrent_sims
        self._session = None

    def _get_session(self):
        if self._session is None:
            import wqb  # lazy import

            self._session = wqb.WQBSession((self.username, self.password))
        return self._session

    def authenticate(self) -> None:
        session = self._get_session()
        resp = session.post_authentication()
        if resp is None or resp.status_code >= 400:
            raise BrainAuthError(f"BRAIN authentication failed: {resp}")

    async def simulate_one(self, expression: str, settings: Settings) -> SimResult:
        """Run exactly one simulation and return its metrics. Polling is
        handled inside wqb.WQBSession.simulate(...)."""
        session = self._get_session()
        target = settings_to_simulation_data(expression, settings)
        resp = await session.simulate(target)
        if resp is None:
            raise RuntimeError(f"Simulation failed to return a result for: {expression} / {settings}")
        return _parse_sim_response(resp)

    async def get_alpha_pnl(self, alpha_id: str) -> dict[str, float]:
        """Fetch a simulated alpha's daily-return series from BRAIN's
        alpha-PnL endpoint, as {date_str: daily_return} -- the shape
        `pipeline/filter/correlation_check.py` expects.

        This is a separate *read* endpoint from `simulate()`; it does not
        submit or create anything, and calling it has no bearing on the
        "no submit/create-alpha call" rule documented at the top of this
        file. Wires up the previously-stubbed correlation gate (code
        review §2.1): before this existed, `Worker._process_candidate`
        passed an empty dict here, so every candidate passed the
        correlation gate by construction, regardless of actual overlap
        with the pool.

        BRAIN's PnL recordset returns *cumulative* PnL per date, not daily
        returns, so this converts via day-over-day diff of cumulative PnL
        (a reasonable proxy for daily return here, since correlation is
        scale-invariant -- Pearson correlation of consecutive differences
        of two series is what actually matters for this gate, not units).
        """
        session = self._get_session()
        resp = await session.get(f"alphas/{alpha_id}/recordsets/pnl")
        if resp is None:
            raise RuntimeError(f"Failed to fetch PnL recordset for alpha {alpha_id}")
        return _parse_pnl_response(resp)


def _parse_sim_response(resp: Any) -> SimResult:
    """Convert a wqb simulation-result Response into our SimResult. BRAIN's
    response shape (as of the wqb client this wraps) nests performance
    metrics under `is` (in-sample) — adjust the key lookups here first if
    BRAIN changes its response schema; that's a one-place fix.

    Update 10 Item 8: sharpe/fitness/turnover and alpha_id are the fields
    every downstream decision (local filter thresholds, correlation gate,
    review_store) actually depends on -- a missing one of these now logs a
    loud warning (once per key, see `_warn_missing_key_once`) instead of
    silently defaulting. `returns`/`drawdown` stay silent on absence since
    they're just informational (Update 03) and are genuinely optional even
    in a correctly-shaped response for stages BRAIN doesn't always return
    them for."""
    data = resp.json()
    is_stats = data.get("is", data)  # tolerate either nested-under-`is` or flat
    for critical_key in ("sharpe", "fitness", "turnover"):
        if critical_key not in is_stats:
            _warn_missing_key_once("sim_response", critical_key, is_stats)
    if "id" not in data and "alphaId" not in data:
        _warn_missing_key_once("sim_response", "id/alphaId", data)
    return SimResult(
        sharpe=float(is_stats.get("sharpe", 0.0)),
        fitness=float(is_stats.get("fitness", 0.0)),
        turnover=float(is_stats.get("turnover", 0.0)),
        returns_ann=float(is_stats["returns"]) if is_stats.get("returns") is not None else None,
        drawdown=float(is_stats["drawdown"]) if is_stats.get("drawdown") is not None else None,
        # `alpha_id` sits alongside `is`/settings in the simulation-result
        # payload -- tolerate a couple of plausible key names since this is
        # the one field BRAIN's docs are least consistent about across
        # endpoints.
        alpha_id=data.get("id") or data.get("alphaId"),
    )


def _parse_pnl_response(resp: Any) -> dict[str, float]:
    """Convert a wqb PnL-recordset Response into {date_str: daily_return},
    diffing BRAIN's cumulative-PnL records day-over-day. Adjust the key
    lookups here first if BRAIN changes this endpoint's response schema —
    same one-place-fix intent as `_parse_sim_response` above.

    Update 10 Item 8: if BRAIN's real response nests records/fields under
    different keys than assumed, every record gets silently skipped (the
    `date is None or pnl is None` guard) and this returns {} -- which,
    fed into compute_max_correlation, reports max_correlation=0.0 and
    passes the gate by construction, exactly the failure mode Update 02
    P0.1 already flagged for the empty-dict case. A response that yields
    zero usable records now logs a loud warning once."""
    data = resp.json()
    records = data.get("records", data.get("pnl", []))
    schema = data.get("schema", {}).get("properties", [])
    field_names = [p.get("name") for p in schema] if schema else ["date", "pnl"]

    dates: list[str] = []
    cumulative: list[float] = []
    skipped = 0
    for record in records:
        if isinstance(record, dict):
            row = record
        else:
            row = dict(zip(field_names, record))
        date = row.get("date")
        pnl = row.get("pnl")
        if date is None or pnl is None:
            skipped += 1
            continue
        dates.append(str(date))
        cumulative.append(float(pnl))

    if records and skipped == len(records):
        _warn_missing_key_once("pnl_response", "date/pnl", data)

    daily_returns: dict[str, float] = {}
    for i in range(1, len(cumulative)):
        daily_returns[dates[i]] = cumulative[i] - cumulative[i - 1]
    return daily_returns
