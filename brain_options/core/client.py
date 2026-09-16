"""
Clean BRAIN client for brain_options: authenticates, simulates single Fast Expression,
polls results, extracts quantitative metrics, and pulls PnL series for correlation checking.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger("brain_options.client")


@dataclass(frozen=True)
class SimSettings:
    region: str = "USA"
    universe: str = "TOP3000"
    delay: int = 1
    decay: int = 8
    neutralization: str = "SUBINDUSTRY"
    truncation: float = 0.05
    pasteurization: bool = True
    nan_handling: bool = False
    unit_handling: str = "VERIFY"
    language: str = "FASTEXPR"

    def to_simulation_payload(self, expression: str) -> dict[str, Any]:
        return {
            "type": "REGULAR",
            "settings": {
                "instrumentType": "EQUITY",
                "region": self.region,
                "universe": self.universe,
                "delay": self.delay,
                "decay": self.decay,
                "neutralization": self.neutralization,
                "truncation": self.truncation,
                "pasteurization": "ON" if self.pasteurization else "OFF",
                "unitHandling": self.unit_handling,
                "nanHandling": "ON" if self.nan_handling else "OFF",
                "language": self.language,
                "visualization": False,
            },
            "regular": expression,
        }


@dataclass(frozen=True)
class SimMetrics:
    alpha_id: Optional[str]
    sharpe: float
    fitness: float
    turnover: float
    annualized_return: float
    max_drawdown: float
    margin: float
    status: str
    raw_response: dict[str, Any]

    @property
    def is_valid(self) -> bool:
        return self.status.upper() in ("COMPLETE", "PASS", "SUCCESS") or (self.sharpe != 0.0 or self.fitness != 0.0)


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_brain_sim_response(resp: Any) -> SimMetrics:
    if resp is None:
        return SimMetrics(None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "FAILED", {})

    data = resp.json() if hasattr(resp, "json") else (resp if isinstance(resp, dict) else {})
    alpha_id = data.get("alpha") or data.get("id") or data.get("alphaId")
    status = data.get("status", "COMPLETE")

    # Metrics can be under data['is'], data['stats'], or directly at root
    stats = data.get("is") or data.get("stats") or data

    sharpe = _safe_float(stats.get("sharpe") or data.get("sharpe"))
    fitness = _safe_float(stats.get("fitness") or data.get("fitness"))
    turnover = _safe_float(stats.get("turnover") or data.get("turnover"))
    returns = _safe_float(stats.get("returns") or stats.get("pnl") or data.get("returns"))
    drawdown = _safe_float(stats.get("drawdown") or stats.get("maxDrawdown") or data.get("drawdown"))
    margin = _safe_float(stats.get("margin") or data.get("margin"))

    return SimMetrics(
        alpha_id=str(alpha_id) if alpha_id else None,
        sharpe=sharpe,
        fitness=fitness,
        turnover=turnover,
        annualized_return=returns,
        max_drawdown=drawdown,
        margin=margin,
        status=status,
        raw_response=data,
    )


class BrainClient:
    """Async/sync facade over wqb.WQBSession for WorldQuant BRAIN operations."""

    def __init__(self, username: str, password: str, max_concurrent_sims: int = 3):
        self.username = username
        self.password = password
        self.max_concurrent_sims = max_concurrent_sims
        self._session = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_sims: int = 0

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_sims)
        return self._semaphore

    @property
    def active_simulations(self) -> int:
        return self._active_sims

    def _get_session(self):
        if self._session is None:
            import wqb  # lazy import
            self._session = wqb.WQBSession((self.username, self.password))
        return self._session

    def authenticate(self) -> None:
        session = self._get_session()
        resp = session.post_authentication()
        if resp is None or getattr(resp, "status_code", 500) >= 400:
            raise RuntimeError(f"WorldQuant BRAIN authentication failed: {resp}")
        log.info("Successfully authenticated with WorldQuant BRAIN as %s", self.username)

    async def simulate_one(self, expression: str, settings: SimSettings) -> SimMetrics:
        async with self.semaphore:
            self._active_sims += 1
            log.info("Acquired simulation slot (%d/%d in-flight) for: %s", self._active_sims, self.max_concurrent_sims, expression[:50])
            try:
                session = self._get_session()
                payload = settings.to_simulation_payload(expression)

                resp = None
                for attempt in range(3):
                    try:
                        resp = await asyncio.wait_for(session.simulate(payload), timeout=180.0)
                        if resp is not None:
                            break
                    except asyncio.TimeoutError:
                        log.warning("Simulation attempt %d timed out after 180s for: %s", attempt + 1, expression[:40])
                    except Exception as e:
                        log.warning("Simulation attempt %d failed: %s", attempt + 1, e)
                    await asyncio.sleep(2.0 * (attempt + 1))

                if resp is None:
                    log.error("Simulation returned None for expression: %s", expression)
                    return SimMetrics(None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "ERROR", {})

                metrics = parse_brain_sim_response(resp)

                # If metrics were not in simulation response directly, fetch from /alphas/<alpha_id>
                if (metrics.sharpe == 0.0 and metrics.fitness == 0.0) and metrics.alpha_id:
                    alpha_url = f"https://api.worldquantbrain.com/alphas/{metrics.alpha_id}"
                    try:
                        alpha_resp = await asyncio.wait_for(session.retry("GET", alpha_url, max_tries=15), timeout=45.0)
                        if alpha_resp is not None and alpha_resp.status_code < 400:
                            metrics = parse_brain_sim_response(alpha_resp)
                    except Exception as e:
                        log.warning("Could not fetch alpha detail for %s: %s", metrics.alpha_id, e)

                return metrics
            finally:
                self._active_sims -= 1
                log.info("Released simulation slot (%d/%d in-flight) for: %s", self._active_sims, self.max_concurrent_sims, expression[:50])

    async def get_alpha_pnl(self, alpha_id: str) -> dict[str, float]:
        """Fetch daily returns for an alpha via /alphas/<id>/recordsets/pnl."""
        session = self._get_session()
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/recordsets/pnl"
        try:
            resp = await asyncio.wait_for(session.retry("GET", url, max_tries=15), timeout=45.0)
        except Exception as e:
            log.warning("Failed to fetch PnL recordset for alpha %s: %s", alpha_id, e)
            return {}
        if resp is None or resp.status_code >= 400:
            return {}

        data = resp.json() if hasattr(resp, "json") else {}
        records = data.get("records") or []
        if not records:
            return {}

        # Convert cumulative PnL to daily return diff
        daily_returns: dict[str, float] = {}
        prev_pnl: Optional[float] = None
        for row in records:
            if isinstance(row, list) and len(row) >= 2:
                dt_str, pnl_val = str(row[0]), _safe_float(row[1])
                if prev_pnl is not None:
                    daily_returns[dt_str] = pnl_val - prev_pnl
                prev_pnl = pnl_val

        return daily_returns

    async def submit_alpha(self, alpha_id: str) -> dict[str, Any]:
        """Submit a qualified alpha to the BRAIN platform."""
        session = self._get_session()
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/submit"
        resp = await session.retry("POST", url, max_tries=5)
        if resp is None:
            return {"ok": False, "status_code": 500, "message": "No response"}
        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "data": resp.json() if hasattr(resp, "json") else {},
            "message": resp.text[:200] if hasattr(resp, "text") else "",
        }
