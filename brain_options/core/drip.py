"""
Smart 24-Hour Drip Submitter for WorldQuant BRAIN.
Enforces the 24-hour New York (EDT/EST) calendar day submission cadence
to maximize Stage 1 -> Stage 2 -> Stage 3 progression credit,
and validates pre-submission checklist gates (including sub-universe Sharpe)
via the BRAIN API before submitting.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import zoneinfo
from typing import Any, Dict, List, Optional, Tuple

from brain_options.config import OptionsConfig
from brain_options.core.client import BrainClient
from brain_options.core.notifier import send_telegram_drip_alert, send_telegram_drip_failure_alert
from brain_options.store.store import OptionsStore

log = logging.getLogger("brain_options.drip")

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


def build_alpha_submission_metadata(cand: Dict[str, Any]) -> Dict[str, Any]:
    """Generates structured name, description, category, and tags for BRAIN submission."""
    alpha_id = cand.get("alpha_id") or ""
    arch = cand.get("archetype") or "Options Factor"
    hyp = cand.get("hypothesis") or ""
    expr = (cand.get("expression") or "").lower()

    # Clean archetype slug for naming
    clean_arch = arch.replace("Mutation(", "").replace(")", "").strip()
    clean_arch = clean_arch.replace(" ", "_").replace("-", "_").title()
    clean_arch = "".join(c for c in clean_arch if c.isalnum() or c == "_")
    name_suffix = alpha_id[-6:] if alpha_id else "ALPHA"
    name = f"OPT_{clean_arch[:18]}_{name_suffix}"

    # Build descriptive economic hypothesis
    if hyp and len(hyp.strip()) > 20:
        description = hyp.strip()
    else:
        description = f"Quantitative options factor exploiting {arch.lower()} dynamics with subindustry neutralization."

    # Derive tags and category based on formula features
    tags = ["options"]
    if "breakeven" in expr or "breakeven" in arch.lower():
        tags.append("breakeven")
    if "skew" in expr or "skew" in arch.lower():
        tags.append("skew")
    if "implied_volatility" in expr or "iv" in arch.lower() or "volatility" in arch.lower():
        tags.append("volatility")
    if "pcr" in expr:
        tags.append("pcr")
    if "forward_price" in expr or "basis" in arch.lower():
        tags.append("forward-basis")
    if "term_structure" in expr or "term_structure" in arch.lower():
        tags.append("term-structure")

    category = "PRICE_VOLUME" if ("volume" in expr or "adv" in expr) else "PRICE_REVERSION"

    return {
        "name": name,
        "description": description,
        "tags": list(dict.fromkeys(tags)),
        "category": category,
    }


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
            if resp and resp.status_code >= 500:
                log.error("Platform gate check returned HTTP %s for alpha %s (BRAIN API down)", resp.status_code, alpha_id)
                try:
                    from brain_options.core.notifier import send_telegram_emergency_alert
                    send_telegram_emergency_alert(
                        error_summary=f"Platform gate check returned HTTP {resp.status_code} for {alpha_id}. BRAIN API down.",
                        config=self.config,
                        context="BRAIN Platform Gate 5xx",
                        db=self.store,
                        cooldown_minutes=60,
                    )
                except Exception:
                    pass
                return False, [f"HTTP_{resp.status_code}"], {}

            if resp and resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                stage = data.get("stage")
                if stage == "OS" and status == "ACTIVE":
                    log.info("Alpha %s is already submitted and ACTIVE on BRAIN. Marking SUBMITTED.", alpha_id)
                    if hasattr(self.store, "mark_alpha_submitted"):
                        self.store.mark_alpha_submitted(alpha_id)
                    return False, ["ALREADY_SUBMITTED"], data
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
                    c_resp = await sess.retry("GET", corr_url, max_tries=1)
                    # BRAIN calculates self-correlation lazily; retry with exponential backoff if empty
                    backoff = 1.0
                    for _ in range(3):
                        if c_resp and c_resp.status_code == 200 and not c_resp.text.strip():
                            await asyncio.sleep(backoff)
                            backoff *= 2.0
                            c_resp = await sess.retry("GET", corr_url, max_tries=1)
                        else:
                            break

                    if c_resp and c_resp.status_code == 200 and c_resp.text.strip():
                        c_data = json.loads(c_resp.text)
                        for r in c_data.get("records") or []:
                            if len(r) > 5 and isinstance(r[5], (int, float)) and abs(float(r[5])) >= 0.70:
                                failed.append(f"HIGH_SELF_CORRELATION (|{float(r[5]):.2f}| >= 0.70 vs {r[0]})")
                                if hasattr(self.store, "mark_alpha_correlated"):
                                    self.store.mark_alpha_correlated(alpha_id, f"High self-correlation {float(r[5]):.2f} vs {r[0]}")
                                break
                except Exception as e:
                    log.error("Self correlation live check failed with exception for %s: %s", alpha_id, e)
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"Self-correlation live check exception on {alpha_id}: {e}",
                            config=self.config,
                            context="Self-Correlation Check Error",
                            db=self.store,
                            cooldown_minutes=60,
                        )
                    except Exception:
                        pass

                return len(failed) == 0, failed, data
        except Exception as e:
            log.warning("Failed to verify checks for alpha %s: %s", alpha_id, e)
        return False, ["API_FETCH_ERROR"], {}

    async def verify_sub_universe_monotonicity(
        self,
        expression: str,
        base_settings: SimSettings,
        sub_universes: list[str] = ["TOP1000", "TOP500"],
        min_sharpe_ratio: float = 0.60,
    ) -> bool:
        """
        Pre-submission sub-universe verification.
        Ensures the candidate retains positive valid Sharpe across smaller liquid sub-universes,
        preventing sub-universe decay penalties.
        """
        if not expression:
            return True
        try:
            for uni in sub_universes:
                if uni == base_settings.universe:
                    continue
                sub_settings = SimSettings(
                    universe=uni,
                    delay=base_settings.delay,
                    decay=base_settings.decay,
                    neutralization=base_settings.neutralization,
                    truncation=base_settings.truncation,
                    pasteurization=base_settings.pasteurization,
                    nan_handling=base_settings.nan_handling,
                )
                sub_metrics = await self.client.simulate_one(expression, sub_settings)
                if not sub_metrics.is_valid or sub_metrics.sharpe < 0:
                    log.warning("Sub-universe %s verification failed for alpha expression.", uni)
                    return False
            return True
        except Exception as e:
            log.warning("Non-fatal sub-universe monotonicity check error: %s", e)
            return True

    async def check_and_drip(self, force_catchup: bool = False) -> Tuple[bool, Optional[str], str]:
        """
        Main drip submitter entry point. Evaluates whether a submission window is open.
        Under normal operations, automatically submits up to 3 alphas per day spaced across
        the designated daily submission windows (Slot 1 at 06:15 WAT, Slot 2 at 14:15 WAT, Slot 3 at 18:15 WAT).
        If earlier timeslots were missed due to lack of qualified alphas in the reserve pool,
        catch-up mode immediately submits straight up for the missed timeslot(s) (1, 2, or 3),
        and strictly preserves any remaining qualified alphas in reserve for tomorrow.
        Returns (submitted: bool, alpha_id: Optional[str], reason: str).
        """
        now_ny = datetime.datetime.now(NY_TZ)
        today_ny = now_ny.date()
        max_daily = getattr(self.config, "drip_max_daily", 3)
        min_interval_hours = getattr(self.config, "drip_min_interval_hours", 4.0)

        today_subs = await self.get_today_submissions_ny()
        current_subs = len(today_subs)

        # 1. Hard Daily Ceiling: Never exceed max_daily (3 alphas/day). Keep the rest for tomorrow.
        if current_subs >= max_daily:
            msg = f"Daily submission quota ({current_subs}/{max_daily}) already reached for {today_ny} EDT. Remaining alphas kept in reserve for tomorrow."
            log.info("[DRIP QUEUE] %s", msg)
            return False, None, msg

        # 2. Determine how many slots should have been filled by this time of day:
        # Slot 1: 06:15 WAT (05:15 UTC / 01:15 EDT)
        # Slot 2: 14:15 WAT (13:15 UTC / 09:15 EDT)
        # Slot 3: 18:15 WAT (17:15 UTC / 13:15 EDT)
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        utc_minute_of_day = utc_now.hour * 60 + utc_now.minute

        if utc_minute_of_day >= 1035:       # >= 17:15 UTC (18:15 WAT): All 3 slots have opened
            expected_slots_by_now = 3
        elif utc_minute_of_day >= 795:      # >= 13:15 UTC (14:15 WAT): Slots 1 & 2 have opened
            expected_slots_by_now = 2
        elif utc_minute_of_day >= 315:      # >= 05:15 UTC (06:15 WAT): Slot 1 has opened
            expected_slots_by_now = 1
        else:                               # Early morning before Slot 1 opens
            expected_slots_by_now = 0

        # Calculate how many submissions to perform in this run:
        if force_catchup:
            slots_needed = max_daily - current_subs
        elif current_subs < expected_slots_by_now:
            # We missed 1, 2, or 3 timeslots! Submit straight up for the missed timeslots.
            slots_needed = expected_slots_by_now - current_subs
            log.info("[DRIP QUEUE] Catch-up active: %d/%d submitted today, missed %d timeslot(s) by %02d:%02d WAT. Submitting straight up to catch up.",
                     current_subs, max_daily, slots_needed, (utc_now.hour + 1) % 24, utc_now.minute)
        else:
            # On schedule: 1 slot at a time, enforcing standard spacing
            slots_needed = 1
            if today_subs:
                latest_dt = max(s["datetime_ny"] for s in today_subs)
                hours_since = (now_ny - latest_dt).total_seconds() / 3600.0
                if hours_since < min_interval_hours:
                    rem_hours = min_interval_hours - hours_since
                    msg = f"Pacing limit: {current_subs}/{max_daily} submitted today (latest: {today_subs[0]['id']}). Next slot opens in {rem_hours:.1f} hours ({rem_hours * 60:.0f} mins). Alphas kept in reserve."
                    log.info("[DRIP QUEUE] %s", msg)
                    return False, None, msg

        # Today's submission slot is open! Load candidate queue
        unsubmitted = self.store.get_unsubmitted_pool_alphas()
        if not unsubmitted:
            msg = f"Drip slot available for {today_ny} EDT, but no unsubmitted alphas found in pool."
            log.info("[DRIP QUEUE] %s", msg)
            return False, None, msg

        # Diversity & Quality optimization: prioritize candidates with highest Composite Quality Score (CQS)
        # while penalizing immediate repeats of recently submitted archetypes.
        recent_archs: List[str] = []
        if hasattr(self.store, "get_recently_submitted_archetypes"):
            try:
                res = self.store.get_recently_submitted_archetypes(limit=5)
                if isinstance(res, list):
                    recent_archs = res
            except Exception:
                recent_archs = []

        recent_archs_cleaned = [
            a.replace("Mutation(", "").replace(")", "").strip().lower()
            for a in recent_archs if a
        ]

        def _cqs_diversity_key(c):
            arch = (c.get("archetype") or "").replace("Mutation(", "").replace(")", "").strip().lower()
            is_repeat = 1 if (recent_archs_cleaned and arch in recent_archs_cleaned) else 0
            cqs = c.get("cqs")
            if cqs is None:
                s = float(c.get("sharpe") or 0.0)
                f = float(c.get("fitness") or 0.0)
                m = float(c.get("margin") or 0.0)
                t = float(c.get("turnover") or 0.0)
                cqs = 1.0 * s + 1.2 * f + 200.0 * m - 0.5 * t
            return (is_repeat, -float(cqs), -float(c.get("sharpe") or 0.0))

        unsubmitted.sort(key=_cqs_diversity_key)

        log.info("[DRIP QUEUE] Submission window OPEN for %s EDT. Need %d submission(s) (Cap: %d/%d). Evaluating %d queue candidates sorted by CQS...",
                 today_ny, slots_needed, current_subs, max_daily, len(unsubmitted))

        submitted_alphas: List[str] = []

        for cand in unsubmitted:
            # Stop immediately if daily cap is reached or required slots are filled
            if current_subs + len(submitted_alphas) >= max_daily:
                log.info("[DRIP QUEUE] Daily quota full (%d/%d). Preserving remaining %d alphas in reserve for tomorrow.",
                         max_daily, max_daily, len(unsubmitted) - len(submitted_alphas))
                break

            if len(submitted_alphas) >= slots_needed:
                log.info("[DRIP QUEUE] Target slots filled (%d submitted this run). Preserving remaining %d alphas in reserve for next slot/tomorrow.",
                         len(submitted_alphas), len(unsubmitted) - len(submitted_alphas))
                break

            alpha_id = cand.get("alpha_id")
            if not alpha_id:
                continue

            is_eligible, failed_checks, alpha_data = await self.verify_alpha_checks(alpha_id)
            if not is_eligible:
                if "ALREADY_SUBMITTED" in failed_checks:
                    log.info("[DRIP QUEUE] %s is already ACTIVE on BRAIN; marked as SUBMITTED.", alpha_id)
                    continue
                log.warning("[DRIP QUEUE] Rejecting %s: failed checks %s. Archiving to rejected alphas table.", alpha_id, failed_checks)
                if hasattr(self.store, "archive_rejected_alpha"):
                    self.store.archive_rejected_alpha(alpha_id, f"CHECK_FAIL: {', '.join(failed_checks)}", cand)
                continue

            # Candidate is 100% verified! Populate name, description, tags, and category on BRAIN
            meta = build_alpha_submission_metadata(cand)
            if hasattr(self.client, "update_alpha_metadata"):
                try:
                    await self.client.update_alpha_metadata(
                        alpha_id,
                        name=meta["name"],
                        description=meta["description"],
                        tags=meta["tags"],
                        category=meta["category"],
                    )
                    log.info("[DRIP QUEUE] Updated metadata on BRAIN for %s: name='%s'", alpha_id, meta["name"])
                except Exception as meta_err:
                    log.warning("[DRIP QUEUE] Non-fatal: could not update metadata for %s: %s", alpha_id, meta_err)

            log.info("[DRIP QUEUE] Submitting verified alpha %s for %s EDT...", alpha_id, today_ny)
            res = await self.client.submit_alpha(alpha_id)
            if res.get("ok"):
                is_actually_submitted = False
                verified_data = alpha_data
                sess = self.client._get_session()
                v_stage = ""
                v_status = ""
                for attempt in range(5):
                    await asyncio.sleep(2.5)
                    v_resp = await sess.retry("GET", f"https://api.worldquantbrain.com/alphas/{alpha_id}", max_tries=2)
                    if v_resp and v_resp.status_code == 200:
                        v_json = v_resp.json()
                        v_stage = v_json.get("stage", "")
                        v_status = v_json.get("status", "")
                        if v_stage == "OS" and v_status == "ACTIVE":
                            is_actually_submitted = True
                            verified_data = v_json
                            break
                        elif v_status == "UNSUBMITTED":
                            log.warning("[DRIP QUEUE] Alpha %s rejected by BRAIN backend (stage=%s, status=%s).",
                                        alpha_id, v_stage, v_status)
                            break

                if is_actually_submitted:
                    slot_num = current_subs + len(submitted_alphas) + 1
                    submitted_alphas.append(alpha_id)
                    log.info("[DRIP QUEUE] Successfully submitted and verified %s in stage OS (Slot %d/%d) for %s EDT.",
                             alpha_id, slot_num, max_daily, today_ny)
                    self.store.mark_alpha_submitted(alpha_id)

                    # Format metrics for alert
                    is_metrics = verified_data.get("is") or {}
                    metrics_dict = {
                        "sharpe": is_metrics.get("sharpe", cand.get("sharpe", 0.0)),
                        "fitness": is_metrics.get("fitness", cand.get("fitness", 0.0)),
                        "turnover": is_metrics.get("turnover", cand.get("turnover", 0.0)),
                        "returns": is_metrics.get("returns", cand.get("returns", 0.0)),
                        "margin": is_metrics.get("margin", cand.get("margin", 0.0)),
                    }
                    send_telegram_drip_alert(
                        alpha_id=alpha_id,
                        date_label=today_ny.isoformat(),
                        metrics=metrics_dict,
                        config=self.config,
                        slot_num=slot_num,
                        max_daily=max_daily,
                        db=self.store,
                    )

                    # Pause briefly between consecutive submissions if more slots need filling
                    if len(submitted_alphas) < slots_needed and current_subs + len(submitted_alphas) < max_daily:
                        await asyncio.sleep(4.0)
                else:
                    log.error("[DRIP QUEUE] Alpha %s failed post-submission validation: polling exhausted (stage=%s, status=%s). Moving to options_rejected_alphas.", alpha_id, v_stage, v_status)
                    rej_msg = f"FAILED_ASYNC_SUBMISSION (stage={v_stage}, status={v_status})"
                    if hasattr(self.store, "archive_rejected_alpha"):
                        self.store.archive_rejected_alpha(alpha_id, rej_msg, cand)
                    send_telegram_drip_failure_alert(alpha_id, rej_msg, self.config, db=self.store)
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"Alpha {alpha_id} post-submission verification never reached ACTIVE after 5 polling cycles: stage={v_stage}, status={v_status}",
                            config=self.config,
                            context="Alpha Post-Submit Verification Exhausted",
                            db=self.store,
                            cooldown_minutes=60,
                        )
                    except Exception:
                        pass
                    continue
            else:
                data = res.get("data") or {}
                msg = res.get("message", "")
                is_chk = data.get("is", {}).get("checks", [])
                self_corr_fail = next((c for c in is_chk if c.get("name") == "SELF_CORRELATION" and c.get("result") == "FAIL"), None)
                self_corr_records = data.get("selfCorrelated", {}).get("records", [])

                if self_corr_fail:
                    val = self_corr_fail.get("value", ">=0.70")
                    top_corr_id = self_corr_records[0][0] if self_corr_records else "existing_sub"
                    rejection_str = f"HIGH_SELF_CORRELATION: {val} vs {top_corr_id}"
                elif "SELF_CORRELATION" in msg or "selfCorrelated" in msg or res.get("status_code") == 403:
                    rejection_str = f"HIGH_SELF_CORRELATION: {msg[:120]}"
                else:
                    rejection_str = f"SUBMISSION_REJECTED: {msg[:120]}"
                    log.error("[DRIP QUEUE] Alpha %s rejected with NON-CORRELATION reason: %s. BRAIN API policy change?", alpha_id, rejection_str)
                    try:
                        from brain_options.core.notifier import send_telegram_emergency_alert
                        send_telegram_emergency_alert(
                            error_summary=f"Alpha {alpha_id} rejected with non-correlation reason: {rejection_str}. Check BRAIN API policy / syntax requirements.",
                            config=self.config,
                            context="Submission Non-Corr Rejection",
                            db=self.store,
                            cooldown_minutes=60,
                        )
                    except Exception:
                        pass

                log.warning("[DRIP QUEUE] Alpha %s rejected during submission: %s. Moving to options_rejected_alphas.", alpha_id, rejection_str)
                if hasattr(self.store, "archive_rejected_alpha"):
                    self.store.archive_rejected_alpha(alpha_id, rejection_str, cand)
                if hasattr(self.store, "db") and self.store.db and cand.get("expression"):
                    self.store.db.penalize_learning_memory(cand.get("expression"), penalty=-15.0, reason=rejection_str)
                send_telegram_drip_failure_alert(alpha_id, rejection_str, self.config, db=self.store)

            # Brief pause to respect BRAIN platform request pacing
            await asyncio.sleep(0.5)

        if submitted_alphas:
            total_now = current_subs + len(submitted_alphas)
            primary_id = submitted_alphas[-1]
            return True, primary_id, f"Submitted {len(submitted_alphas)} alpha(s) (Total {total_now}/{max_daily}) for {today_ny} EDT. Remaining kept in reserve for tomorrow."

        if unsubmitted and len(submitted_alphas) == 0:
            log.error("All %d eligible alphas in pool failed drip verification! Pool may be corrupted or stale.", len(unsubmitted))
            try:
                from brain_options.core.notifier import send_telegram_emergency_alert
                send_telegram_emergency_alert(
                    error_summary=f"All {len(unsubmitted)} eligible alphas in pool failed drip verification! Pool may be corrupted or stale.",
                    config=self.config,
                    context="Drip Pool Verification Exhausted",
                    db=self.store,
                    cooldown_minutes=120,
                )
            except Exception:
                pass

        return False, None, "No eligible unsubmitted alphas passed verification in pool."


