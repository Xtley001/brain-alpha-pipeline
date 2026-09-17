"""
Smart 24-Hour Drip Submitter for WorldQuant BRAIN.
Enforces the 24-hour New York (EDT/EST) calendar day submission cadence
to maximize Stage 1 -> Stage 2 -> Stage 3 progression credit,
and validates pre-submission checklist gates (including sub-universe Sharpe)
via the BRAIN API before submitting.
"""
from __future__ import annotations

import datetime
import json
import logging
import zoneinfo
from typing import Any, Dict, List, Optional, Tuple

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.notifier import send_telegram_drip_alert
from brain_options.store.store import OptionsStore

log = logging.getLogger("brain_options.drip")

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


class DripSubmitter:
    def __init__(self, client: BrainClient, store: OptionsStore, config: OptionsConfig):
        self.client = client
        self.store = store
        self.config = config

    async def get_today_submissions_ny(self) -> List[dict]:
        """Queries the BRAIN platform for all submissions made today in New York calendar time."""
        sess = self.client._get_session()
        url = "https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=10&order=-dateSubmitted"
        now_ny = datetime.datetime.now(NY_TZ)
        today_ny = now_ny.date()
        today_subs: List[dict] = []
        try:
            resp = await sess.retry("GET", url, max_tries=3)
            if resp and resp.status_code == 200:
                data = resp.json()
                for a in data.get("results") or []:
                    date_str = a.get("dateSubmitted")
                    if date_str:
                        dt = datetime.datetime.fromisoformat(date_str).astimezone(NY_TZ)
                        if dt.date() == today_ny:
                            today_subs.append({
                                "id": a.get("id"),
                                "datetime_ny": dt,
                                "dateSubmitted": date_str,
                            })
        except Exception as e:
            log.warning("Could not fetch today's submissions from BRAIN: %s", e)
        return today_subs

    async def get_latest_submission_date_ny(self) -> Optional[datetime.date]:
        """Queries the BRAIN platform for the user's most recent active submission date in New York time."""
        subs = await self.get_today_submissions_ny()
        if subs:
            return subs[0]["datetime_ny"].date()
        sess = self.client._get_session()
        url = "https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=1&order=-dateSubmitted"
        try:
            resp = await sess.retry("GET", url, max_tries=3)
            if resp and resp.status_code == 200:
                data = resp.json()
                results = data.get("results") or []
                if results:
                    date_str = results[0].get("dateSubmitted")
                    if date_str:
                        dt = datetime.datetime.fromisoformat(date_str)
                        return dt.astimezone(NY_TZ).date()
        except Exception as e:
            log.warning("Could not fetch latest submission date from BRAIN: %s", e)
        return None

    async def verify_alpha_checks(self, alpha_id: str) -> Tuple[bool, list[str], dict[str, Any]]:
        """
        Verifies all platform checklist items (LOW_SHARPE, LOW_FITNESS, LOW_TURNOVER,
        HIGH_TURNOVER, CONCENTRATED_WEIGHT, LOW_SUB_UNIVERSE_SHARPE) and confirms
        self-correlation against active submissions is < 0.70.
        Returns (is_eligible, failed_checks, alpha_data).
        """
        sess = self.client._get_session()
        url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
        try:
            resp = await sess.retry("GET", url, max_tries=3)
            if resp and resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status != "UNSUBMITTED":
                    return False, [f"Status is {status}, not UNSUBMITTED"], data

                is_block = data.get("is") or {}
                checks = is_block.get("checks") or []
                failed = [
                    chk.get("name") for chk in checks
                    if chk.get("result") == "FAIL"
                ]

                # Pre-submission self-correlation verification (< 0.70 limit)
                corr_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self"
                try:
                    c_resp = await sess.retry("GET", corr_url, max_tries=2)
                    if c_resp and c_resp.status_code == 200 and c_resp.text.strip():
                        c_data = json.loads(c_resp.text)
                        for r in c_data.get("records") or []:
                            if len(r) > 5 and isinstance(r[5], (int, float)) and r[5] >= 0.70:
                                failed.append(f"HIGH_SELF_CORRELATION ({r[5]:.2f} >= 0.70 vs {r[0]})")
                                break
                except Exception as e:
                    log.debug("Self correlation check skipped for %s: %s", alpha_id, e)

                return len(failed) == 0, failed, data
        except Exception as e:
            log.warning("Failed to verify checks for alpha %s: %s", alpha_id, e)
        return False, ["API_FETCH_ERROR"], {}

    async def check_and_drip(self) -> Tuple[bool, Optional[str], str]:
        """
        Evaluates the daily submission cadence (up to 2 alphas per New York day,
        spaced by minimum interval hours to maintain optimal pacing).
        If a slot is free, selects the best fully verified alpha from the queue,
        submits it, updates records, and notifies Telegram.
        Returns (submitted: bool, alpha_id: Optional[str], reason: str).
        """
        now_ny = datetime.datetime.now(NY_TZ)
        today_ny = now_ny.date()
        max_daily = getattr(self.config, "drip_max_daily", 2)
        min_interval_hours = getattr(self.config, "drip_min_interval_hours", 4.0)

        today_subs = await self.get_today_submissions_ny()
        if len(today_subs) >= max_daily:
            msg = f"Daily submission quota ({len(today_subs)}/{max_daily}) already reached for {today_ny} EDT. Next window opens tomorrow at 00:00 EDT."
            log.info("[DRIP QUEUE] %s", msg)
            return False, None, msg

        if today_subs:
            latest_dt = max(s["datetime_ny"] for s in today_subs)
            hours_since = (now_ny - latest_dt).total_seconds() / 3600.0
            if hours_since < min_interval_hours:
                rem_hours = min_interval_hours - hours_since
                msg = f"Pacing limit: {len(today_subs)}/{max_daily} submitted today (latest: {today_subs[0]['id']}). Next slot opens in {rem_hours:.1f} hours ({rem_hours * 60:.0f} mins)."
                log.info("[DRIP QUEUE] %s", msg)
                return False, None, msg

        # Today's submission slot is open! Load candidate queue
        unsubmitted = self.store.get_unsubmitted_pool_alphas()
        if not unsubmitted:
            msg = f"Drip slot available for {today_ny} EDT, but no unsubmitted alphas found in pool."
            log.info("[DRIP QUEUE] %s", msg)
            return False, None, msg

        # Diversity optimization: prioritize candidates from archetypes distinct from recently submitted ones
        recent_archs: List[str] = []
        if hasattr(self.store, "get_recently_submitted_archetypes"):
            try:
                res = self.store.get_recently_submitted_archetypes(limit=2)
                if isinstance(res, list):
                    recent_archs = res
            except Exception:
                recent_archs = []

        if recent_archs:
            def _diversity_key(c):
                arch = c.get("archetype") or ""
                is_repeat = 1 if arch in recent_archs else 0
                return (is_repeat, -float(c.get("sharpe") or 0.0))
            unsubmitted.sort(key=_diversity_key)

        log.info("[DRIP QUEUE] Submission window OPEN for %s EDT. Evaluating %d queue candidates (Diversity prioritized vs %s)...",
                 today_ny, len(unsubmitted), recent_archs)

        for cand in unsubmitted:
            alpha_id = cand.get("alpha_id")
            if not alpha_id:
                continue

            is_eligible, failed_checks, alpha_data = await self.verify_alpha_checks(alpha_id)
            if not is_eligible:
                log.warning("[DRIP QUEUE] Skipping %s: failed checks %s", alpha_id, failed_checks)
                continue

            # Candidate is 100% verified! Submit exactly this one
            log.info("[DRIP QUEUE] Submitting verified alpha %s for %s EDT...", alpha_id, today_ny)
            res = await self.client.submit_alpha(alpha_id)
            if res.get("ok"):
                log.info("[DRIP QUEUE] Successfully submitted %s! Claimed progression for %s EDT.", alpha_id, today_ny)
                self.store.mark_alpha_submitted(alpha_id)

                # Format metrics for alert
                is_metrics = alpha_data.get("is") or {}
                metrics_dict = {
                    "sharpe": is_metrics.get("sharpe", cand.get("sharpe", 0.0)),
                    "fitness": is_metrics.get("fitness", cand.get("fitness", 0.0)),
                    "turnover": is_metrics.get("turnover", cand.get("turnover", 0.0)),
                    "returns": is_metrics.get("returns", cand.get("returns", 0.0)),
                    "margin": is_metrics.get("margin", cand.get("margin", 0.0)),
                }
                send_telegram_drip_alert(alpha_id, today_ny.isoformat(), metrics_dict, self.config)
                return True, alpha_id, f"Submitted {alpha_id} for {today_ny} EDT"
            else:
                log.warning("[DRIP QUEUE] Submission request for %s returned non-OK: %s", alpha_id, res.get("message"))

        return False, None, "No candidate cleared all pre-submission checklist gates."
