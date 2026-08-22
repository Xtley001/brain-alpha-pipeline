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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipeline.sweep.settings_sweep import Settings, SimResult

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
    BRAIN changes its response schema; that's a one-place fix."""
    data = resp.json()
    is_stats = data.get("is", data)  # tolerate either nested-under-`is` or flat
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
    same one-place-fix intent as `_parse_sim_response` above."""
    data = resp.json()
    records = data.get("records", data.get("pnl", []))
    schema = data.get("schema", {}).get("properties", [])
    field_names = [p.get("name") for p in schema] if schema else ["date", "pnl"]

    dates: list[str] = []
    cumulative: list[float] = []
    for record in records:
        if isinstance(record, dict):
            row = record
        else:
            row = dict(zip(field_names, record))
        date = row.get("date")
        pnl = row.get("pnl")
        if date is None or pnl is None:
            continue
        dates.append(str(date))
        cumulative.append(float(pnl))

    daily_returns: dict[str, float] = {}
    for i in range(1, len(cumulative)):
        daily_returns[dates[i]] = cumulative[i] - cumulative[i - 1]
    return daily_returns
