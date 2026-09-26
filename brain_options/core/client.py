"""
Clean BRAIN client for brain_options: authenticates, simulates single Fast Expression,
polls results, extracts quantitative metrics, and pulls PnL series for correlation checking.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
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
                "neutralization": self.neutralization.upper() if self.neutralization else "SUBINDUSTRY",
                "truncation": self.truncation,
                "pasteurization": "ON" if self.pasteurization else "OFF",
                "unitHandling": self.unit_handling,
                "nanHandling": "ON" if self.nan_handling else "OFF",
                "language": self.language,
                "visualization": False,
            },
            "regular": expression,
        }


ACCEPTED_SIM_STATUSES = {"COMPLETE", "WARNING", "PASS", "SUCCESS"}


@dataclass(frozen=True)
class SimMetrics:
    alpha_id: Optional[str] = None
    sharpe: float = 0.0
    fitness: float = 0.0
    turnover: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    margin: float = 0.0
    status: str = "ERROR"
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        if self.status.upper() in ACCEPTED_SIM_STATUSES:
            return True
        # Fallback for providers that omit/mislabel status but returned real metrics
        return self.sharpe != 0.0 or self.fitness != 0.0


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
    """Async/sync facade over wqb.WQBSession for WorldQuant BRAIN operations with PostgreSQL session caching."""

    def __init__(self, username: str, password: str, max_concurrent_sims: int = 3, db: Optional[Any] = None):
        self.username = username
        self.password = password
        self.max_concurrent_sims = max_concurrent_sims
        self.db = db
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

        # Check PostgreSQL cluster session cache to avoid 429 login rate-limits
        if self.db is not None:
            try:
                cached = self.db.get_cached_session(key=f"brain_session_{self.username}")
                if cached and cached.get("cookies"):
                    for k, v in cached["cookies"].items():
                        session.cookies.set(k, v)
                    test_resp = session.get("https://api.worldquantbrain.com/users/self")
                    if test_resp.status_code == 200:
                        log.info("Successfully resumed BRAIN session from PostgreSQL cluster cache for %s (Zero 429 risk).", self.username)
                        return
            except Exception as cache_err:
                log.warning("Cached session validation skipped: %s", cache_err)

        resp = session.post_authentication()
        if resp is None or getattr(resp, "status_code", 500) >= 400:
            err_msg = f"WorldQuant BRAIN authentication failed for {self.username}: {resp}"
            log.error(err_msg)
            try:
                from brain_options.core.notifier import send_telegram_emergency_alert
                send_telegram_emergency_alert(
                    error_summary=err_msg,
                    context="BRAIN Auth Failure",
                    db=self.db,
                    cooldown_minutes=60,
                )
            except Exception:
                pass
            raise RuntimeError(err_msg)
        log.info("Successfully authenticated with WorldQuant BRAIN as %s", self.username)

        # Save session cookies to PostgreSQL cluster cache (TTL 2 hours)
        if self.db is not None:
            try:
                cookies_dict = session.cookies.get_dict()
                token = getattr(session, "token", "") or "cookie_session"
                self.db.save_cached_session(token=token, cookies=cookies_dict, expires_in_seconds=7200, key=f"brain_session_{self.username}")
            except Exception as save_err:
                log.warning("Failed to cache session cookies: %s", save_err)

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

                # Check for session token expiry (401)
                if resp is not None and getattr(resp, "status_code", 200) == 401:
                    log.error("BRAIN session token expired during batch for %s!", self.username)
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"BRAIN session token expired mid-batch for {self.username}. Needs re-auth.",
                            context="BRAIN Session Expired",
                            db=self.db,
                            cooldown_minutes=30,
                        )
                    except Exception:
                        pass

                # Check for non-200 simulation submit API error
                if resp is not None and getattr(resp, "status_code", 200) >= 400:
                    status_code = getattr(resp, "status_code", "unknown")
                    log.error("Simulation submit returned non-200 (%s) for %s: %s", status_code, expression[:50], getattr(resp, 'text', '')[:100])
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"Simulation submit returned HTTP {status_code} for {expression[:40]}: {getattr(resp, 'text', '')[:100]}",
                            context="BRAIN Sim API Error",
                            db=self.db,
                            cooldown_minutes=60,
                        )
                    except Exception:
                        pass

                if resp is None:
                    log.error("Simulation returned None (timeout/failure across all attempts) for expression: %s", expression)
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"Simulation result fetch returned null after all retries for: {expression[:50]}",
                            context="BRAIN Sim Result Null",
                            db=self.db,
                            cooldown_minutes=60,
                        )
                    except Exception:
                        pass
                    return SimMetrics(None, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "ERROR", {})

                metrics = parse_brain_sim_response(resp)

                # If metrics were not in simulation response directly, fetch from /alphas/<alpha_id>
                if (metrics.sharpe == 0.0 and metrics.fitness == 0.0) and metrics.alpha_id:
                    alpha_url = f"https://api.worldquantbrain.com/alphas/{metrics.alpha_id}"
                    try:
                        alpha_resp = await asyncio.wait_for(session.retry("GET", alpha_url, max_tries=15), timeout=45.0)
                        if alpha_resp is not None and alpha_resp.status_code < 400:
                            metrics = parse_brain_sim_response(alpha_resp)
                        elif alpha_resp is not None and alpha_resp.status_code >= 400:
                            log.error("Simulation detail fetch returned HTTP %s for %s", alpha_resp.status_code, metrics.alpha_id)
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
        
        data = {}
        if hasattr(resp, "text") and resp.text and resp.text.strip():
            try:
                data = resp.json()
            except Exception:
                data = {}

        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "data": data,
            "message": resp.text[:200] if hasattr(resp, "text") else "",
        }

    async def update_alpha_metadata(
        self,
        alpha_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update alpha name, economic description, tags, and category via PATCH /alphas/<id>."""
        session = self._get_session()
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
        payload: dict[str, Any] = {}
        if name:
            payload["name"] = name
        if category:
            payload["category"] = category
        if tags is not None:
            payload["tags"] = tags
        if description:
            payload["regular"] = {"description": description}

        if not payload:
            return {"ok": True, "status_code": 200}

        resp = await session.retry("PATCH", url, json=payload, max_tries=3)
        if resp is None:
            return {"ok": False, "status_code": 500, "message": "No response"}

        data = {}
        if hasattr(resp, "text") and resp.text and resp.text.strip():
            try:
                data = resp.json()
            except Exception:
                data = {}

        return {
            "ok": resp.status_code < 400,
            "status_code": resp.status_code,
            "data": data,
            "message": resp.text[:200] if hasattr(resp, "text") else "",
        }

