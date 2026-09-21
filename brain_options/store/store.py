"""
Local store for passed options alphas and evaluated candidate history.
Maintains clean CSV and JSON records with full reproduction parameters.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
import os
import threading
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from brain_options.core.client import SimMetrics, SimSettings
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.db import OptionsDatabase

load_dotenv()

log = logging.getLogger("brain_options.store")


_SENTINEL = object()


class OptionsStore:
    def __init__(self, data_dir: Optional[str] = None, database_url: Any = _SENTINEL):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.passed_csv = os.path.join(self.data_dir, "passed_options_alphas.csv")
        self.passed_json = os.path.join(self.data_dir, "passed_options_alphas.json")
        self.rejected_csv = os.path.join(self.data_dir, "rejected_options_alphas.csv")
        self.correlated_csv = os.path.join(self.data_dir, "correlated_options_alphas.csv")
        self.history_csv = os.path.join(self.data_dir, "evaluated_candidates.csv")
        self.pnl_cache_dir = os.path.join(self.data_dir, "pnl_series")
        os.makedirs(self.pnl_cache_dir, exist_ok=True)

        if database_url is _SENTINEL:
            database_url = os.getenv("DATABASE_URL")

        self.db = OptionsDatabase(database_url)
        self._write_lock = threading.Lock()

    def load_evaluated_expressions(self) -> set[str]:
        evaluated = set()
        if os.path.exists(self.history_csv):
            try:
                with open(self.history_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        expr = row.get("expression")
                        if expr:
                            evaluated.add(expr.strip())
            except Exception as e:
                log.warning("Could not load evaluated history from CSV: %s", e)
        # Also load from Postgres
        db_evaluated = self.db.load_evaluated_expressions()
        evaluated.update(db_evaluated)
        return evaluated

    def load_top_performing_exemplars(
        self,
        limit: int = 5,
        min_sharpe: float = 1.0,
        exclude_archetypes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self.db.load_top_performing_exemplars(
            limit=limit,
            min_sharpe=min_sharpe,
            exclude_archetypes=exclude_archetypes,
        )

    def load_archetype_performance_summary(self) -> Dict[str, Any]:
        return self.db.load_archetype_performance_summary()

    def record_evaluated_candidate(
        self, candidate: OptionCandidate, stage: str, status: str, metrics: SimMetrics
    ):
        file_exists = os.path.exists(self.history_csv)
        fieldnames = [
            "timestamp", "expression", "archetype", "source", "stage", "status",
            "sharpe", "fitness", "turnover", "returns", "drawdown", "alpha_id"
        ]
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expression": candidate.expression,
            "archetype": candidate.archetype_name,
            "source": candidate.generation_source,
            "stage": stage,
            "status": status,
            "sharpe": f"{metrics.sharpe:.4f}",
            "fitness": f"{metrics.fitness:.4f}",
            "turnover": f"{metrics.turnover:.4f}",
            "returns": f"{metrics.annualized_return:.4f}",
            "drawdown": f"{metrics.max_drawdown:.4f}",
            "alpha_id": metrics.alpha_id or "",
        }
        with self._write_lock:
            with open(self.history_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
        # Also sync to PostgreSQL table options_evaluations
        self.db.record_candidate(candidate, stage, status, metrics)

    def save_passed_alpha(
        self,
        candidate: OptionCandidate,
        settings: SimSettings,
        metrics: SimMetrics,
        max_corr: float,
        pnl_series: Dict[str, float],
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alpha_id": metrics.alpha_id or "",
            "expression": candidate.expression,
            "archetype": candidate.archetype_name,
            "hypothesis": candidate.hypothesis,
            "source": candidate.generation_source,
            "sharpe": metrics.sharpe,
            "fitness": metrics.fitness,
            "turnover": metrics.turnover,
            "returns": metrics.annualized_return,
            "drawdown": metrics.max_drawdown,
            "margin": metrics.margin,
            "max_correlation": max_corr,
            "universe": settings.universe,
            "neutralization": settings.neutralization,
            "delay": settings.delay,
            "decay": settings.decay,
            "truncation": settings.truncation,
            "pasteurization": "ON" if settings.pasteurization else "OFF",
            "nan_handling": "ON" if settings.nan_handling else "OFF",
        }

        with self._write_lock:
            # 1. Append to CSV
            file_exists = os.path.exists(self.passed_csv)
            fieldnames = list(record.keys())
            with open(self.passed_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)

            # 2. Append to JSON list
            existing_json: list[dict] = []
            if os.path.exists(self.passed_json):
                try:
                    with open(self.passed_json, "r", encoding="utf-8") as f:
                        existing_json = json.load(f)
                except Exception:
                    existing_json = []
            existing_json.append(record)
            with open(self.passed_json, "w", encoding="utf-8") as f:
                json.dump(existing_json, f, indent=2)

            # 3. Cache PnL series if available
            if pnl_series and metrics.alpha_id:
                pnl_path = os.path.join(self.pnl_cache_dir, f"{metrics.alpha_id}.json")
                with open(pnl_path, "w", encoding="utf-8") as f:
                    json.dump(pnl_series, f)

        # 4. Sync to PostgreSQL table options_alphas
        self.db.save_passed_alpha(candidate, settings, metrics, max_corr)

        log.info("Saved passed alpha %s to store.", metrics.alpha_id or candidate.expression[:40])

    def load_pool_pnl_series(self) -> List[Dict[str, float]]:
        """
        Loads daily return series ONLY for alphas currently in the live pool:
          - status = QUALIFIED  (unsubmitted reserve)
          - status = SUBMITTED  (already live on BRAIN)

        This ensures the correlation gate checks against the true live portfolio,
        not against alphas that were later archived as correlated or rejected.
        Without this filter, a new alpha could be rejected for correlating with
        a stale alpha that was already removed from the pool — wasting a slot.

        Resolution order:
        1. Fetch active alpha_ids from Neon DB (QUALIFIED + SUBMITTED).
        2. Load only the matching pnl_series/<alpha_id>.json files.
        3. If DB unavailable, fall back to passed_options_alphas.json filtering
           by status=SUBMITTED or status=QUALIFIED (or no status field = legacy).
        """
        series_list: list[dict[str, float]] = []
        if not os.path.exists(self.pnl_cache_dir):
            return series_list

        # --- 1. Get active alpha IDs from DB ---
        active_ids: set[str] = set()
        if self.db and self.db.database_url:
            try:
                # Pull QUALIFIED (reserve) + SUBMITTED from options_alphas
                pool_rows = self.db.get_unsubmitted_pool_alphas()  # returns QUALIFIED only
                for row in pool_rows:
                    aid = row.get("alpha_id")
                    if aid:
                        active_ids.add(aid)

                # Also pull SUBMITTED alpha_ids directly
                submitted_rows = self.db.get_submitted_alpha_ids()
                active_ids.update(submitted_rows)

                log.debug(
                    "Correlation pool: %d active alpha IDs loaded from DB (%d QUALIFIED, %d SUBMITTED).",
                    len(active_ids),
                    len(pool_rows),
                    len(submitted_rows),
                )
            except Exception as db_err:
                log.debug("DB unavailable for correlation pool load, using CSV fallback: %s", db_err)
                active_ids = set()

        # --- 2. Load PnL files for active IDs only ---
        if active_ids:
            for alpha_id in active_ids:
                path = os.path.join(self.pnl_cache_dir, f"{alpha_id}.json")
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                series_list.append(data)
                    except Exception as e:
                        log.warning("Could not read pnl file %s.json: %s", alpha_id, e)
            if series_list:
                return series_list

        # --- 3. CSV fallback: filter by status ---
        # Only include SUBMITTED or QUALIFIED (or legacy rows with no status)
        active_from_csv: set[str] = set()
        if os.path.exists(self.passed_json):
            try:
                with open(self.passed_json, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    st = rec.get("status", "QUALIFIED")
                    aid = rec.get("alpha_id", "")
                    if aid and st in ("SUBMITTED", "QUALIFIED", ""):
                        active_from_csv.add(aid)
            except Exception:
                pass

        if active_from_csv:
            for alpha_id in active_from_csv:
                path = os.path.join(self.pnl_cache_dir, f"{alpha_id}.json")
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                series_list.append(data)
                    except Exception as e:
                        log.warning("Could not read pnl file %s.json: %s", alpha_id, e)
            return series_list

        # Final fallback: load all files (cold start with no DB and no JSON)
        log.debug("Correlation pool: cold start fallback — loading all PnL files.")
        for fname in os.listdir(self.pnl_cache_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.pnl_cache_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            series_list.append(data)
                except Exception as e:
                    log.warning("Could not read pnl file %s: %s", fname, e)
        return series_list

    def record_learning_memory(
        self,
        candidate: OptionCandidate,
        metrics: SimMetrics,
        reward: float,
        optimization_steps: int = 0,
        parent_expression: Optional[str] = None,
        mutation_type: Optional[str] = None,
        status: str = "EVALUATED",
    ):
        self.db.record_learning_memory(
            candidate, metrics, reward, optimization_steps, parent_expression, mutation_type, status
        )

    def load_archetype_performance_summary(self) -> Dict[str, Dict[str, float]]:
        return self.db.load_archetype_performance_summary()

    def get_options_stats(self) -> Dict[str, Any]:
        return self.db.get_options_stats()

    def get_submitted_alpha_ids(self) -> set:
        """Returns set of alpha_ids with status=SUBMITTED in options_alphas."""
        return self.db.get_submitted_alpha_ids()

    def get_unsubmitted_pool_alphas(self) -> List[Dict[str, Any]]:
        """Returns qualified but not-yet-submitted alphas from Neon DB (source of truth)."""
        if self.db and self.db.database_url:
            return self.db.get_unsubmitted_pool_alphas()
        return []

    def get_recently_submitted_archetypes(self, limit: int = 3) -> List[str]:
        return self.db.get_recently_submitted_archetypes(limit=limit)

    def get_today_saturated_archetypes(self, max_per_day: int = 1) -> List[str]:
        return self.db.get_today_saturated_archetypes(max_per_day=max_per_day)

    def record_org_run(
        self,
        org_name: str,
        archetype: str = "",
        evals_done: int = 0,
        qualified: int = 0,
    ):
        """Write an org run heartbeat row to the org_runs table."""
        self.db.record_org_run(org_name, archetype=archetype, evals_done=evals_done, qualified=qualified)

    def get_org_activity(self, hours: int = 26) -> List[Dict[str, Any]]:
        """Return per-org activity summary from org_runs for the last N hours."""
        return self.db.get_org_activity(hours=hours)

    def claim_hourly_health_slot(self, min_interval_minutes: int = 55) -> bool:
        """Atomically claims hourly health lock if >= min_interval_minutes have elapsed."""
        if hasattr(self.db, "claim_hourly_health_slot"):
            return self.db.claim_hourly_health_slot(min_interval_minutes=min_interval_minutes)
        return True

    def acquire_telegram_send_lease(self, min_gap_seconds: float = 1.2, max_wait_seconds: float = 6.0) -> bool:
        """Cross-org pacing lock so concurrent workers don't collide on Telegram sends."""
        if hasattr(self.db, "acquire_telegram_send_lease"):
            return self.db.acquire_telegram_send_lease(min_gap_seconds=min_gap_seconds, max_wait_seconds=max_wait_seconds)
        return True


    def mark_alpha_submitted(self, alpha_id: str):
        self.db.mark_alpha_submitted(alpha_id)

    def mark_alpha_correlated(
        self,
        alpha_id: str,
        reason: str = "",
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        self.archive_correlated_alpha(alpha_id, f"CORRELATED: {reason}", cand_data, max_corr)

    def archive_correlated_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        """Archives correlated alpha in PostgreSQL options_correlated_alphas and local correlated_options_alphas.csv, and frees from options_alphas."""
        # 1. Archive in PostgreSQL dedicated table options_correlated_alphas
        self.db.archive_correlated_alpha(alpha_id, reason, cand_data, max_corr)

        # 2. Archive locally in correlated_options_alphas.csv
        cand = cand_data or {}
        corr_val = max_corr if max_corr is not None else cand.get("max_correlation")
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alpha_id": alpha_id,
            "expression": cand.get("expression") or "",
            "archetype": cand.get("archetype") or "",
            "hypothesis": cand.get("hypothesis") or "",
            "source": cand.get("source") or "",
            "sharpe": cand.get("sharpe") or "",
            "fitness": cand.get("fitness") or "",
            "turnover": cand.get("turnover") or "",
            "returns": cand.get("returns") or "",
            "drawdown": cand.get("drawdown") or "",
            "margin": cand.get("margin") or "",
            "max_correlation": corr_val or "",
            "rejection_reason": reason,
        }
        with self._write_lock:
            file_exists = os.path.exists(self.correlated_csv)
            with open(self.correlated_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)

            # Purge from passed_options_alphas.json and passed_options_alphas.csv
            self._purge_from_passed_store(alpha_id)

    def archive_rejected_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
    ):
        """Archives rejected alpha in both PostgreSQL and local storage, and frees from options_alphas."""
        # 1. Archive in PostgreSQL dedicated table options_rejected_alphas
        self.db.archive_rejected_alpha(alpha_id, reason, cand_data)

        # 2. Archive locally in rejected_options_alphas.csv
        cand = cand_data or {}
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alpha_id": alpha_id,
            "expression": cand.get("expression") or "",
            "archetype": cand.get("archetype") or "",
            "hypothesis": cand.get("hypothesis") or "",
            "source": cand.get("source") or "",
            "sharpe": cand.get("sharpe") or "",
            "fitness": cand.get("fitness") or "",
            "turnover": cand.get("turnover") or "",
            "returns": cand.get("returns") or "",
            "drawdown": cand.get("drawdown") or "",
            "margin": cand.get("margin") or "",
            "rejection_reason": reason,
        }
        with self._write_lock:
            file_exists = os.path.exists(self.rejected_csv)
            with open(self.rejected_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)

            # Purge from passed_options_alphas.json and passed_options_alphas.csv
            self._purge_from_passed_store(alpha_id)

    def _purge_from_passed_store(self, alpha_id: str):
        """Removes alpha from passed_options_alphas.json and passed_options_alphas.csv to keep qualified store clean."""
        if not alpha_id:
            return

        # Purge from passed_options_alphas.json
        if os.path.exists(self.passed_json):
            try:
                with open(self.passed_json, "r", encoding="utf-8") as f:
                    records = json.load(f)
                new_records = [r for r in records if r.get("alpha_id") != alpha_id]
                if len(new_records) != len(records):
                    with open(self.passed_json, "w", encoding="utf-8") as f:
                        json.dump(new_records, f, indent=2)
            except Exception as e:
                log.warning("Could not purge %s from passed_json: %s", alpha_id, e)

        # Purge from passed_options_alphas.csv
        if os.path.exists(self.passed_csv):
            try:
                with open(self.passed_csv, "r", encoding="utf-8") as f:
                    reader = list(csv.DictReader(f))
                new_rows = [r for r in reader if r.get("alpha_id") != alpha_id]
                if len(new_rows) != len(reader) and new_rows:
                    with open(self.passed_csv, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=list(new_rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(new_rows)
            except Exception as e:
                log.warning("Could not purge %s from passed_csv: %s", alpha_id, e)



    def get_salvageable_correlated_alphas(
        self, min_sharpe: float = 1.25, min_fitness: float = 1.00, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Returns high-performing correlated alphas eligible for orthogonalization."""
        if hasattr(self, "db") and self.db:
            return self.db.get_salvageable_correlated_alphas(min_sharpe=min_sharpe, min_fitness=min_fitness, limit=limit)
        return []

    def get_stage0_passed_candidates(self, limit: int = 100) -> List[OptionCandidate]:
        candidates = self.db.get_stage0_passed_candidates(limit=limit)
        if candidates:
            return candidates

        # Fallback to local CSV history if database is offline, fresh, or returned empty
        if not os.path.exists(self.history_csv):
            return []

        candidates_map: dict[str, OptionCandidate] = {}
        completed_exprs: set[str] = set()

        try:
            with open(self.history_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Find candidates that have already completed retry or qualified
            for row in rows:
                expr = (row.get("expression") or "").strip()
                stage = (row.get("stage") or "").strip()
                status = (row.get("status") or "").strip()
                if stage == "RETRY_COMPLETED" or stage.startswith("DIAG_") or status in ("QUALIFIED", "OPTIMIZED", "EXHAUSTED"):
                    completed_exprs.add(expr)

            # Check passed_alphas CSV
            if os.path.exists(self.passed_csv):
                with open(self.passed_csv, "r", encoding="utf-8") as pf:
                    preader = csv.DictReader(pf)
                    for prow in preader:
                        pexpr = (prow.get("expression") or "").strip()
                        if pexpr:
                            completed_exprs.add(pexpr)

            # Collect eligible Stage 0 candidates
            eligible: list[tuple[float, float, OptionCandidate]] = []
            for row in rows:
                expr = (row.get("expression") or "").strip()
                if not expr or expr in completed_exprs or expr in candidates_map:
                    continue

                stage = (row.get("stage") or "").strip()
                status = (row.get("status") or "").strip()
                try:
                    sh = float(row.get("sharpe") or 0.0)
                    fit = float(row.get("fitness") or 0.0)
                except ValueError:
                    sh, fit = 0.0, 0.0

                if (stage == "STAGE0" and status == "PASS") or (sh >= 0.35 and fit >= 0.20):
                    cand = OptionCandidate(
                        expression=expr,
                        archetype_name=row.get("archetype") or "options_alpha",
                        hypothesis=f"Stage 0 passer (Sharpe={sh:.2f}, Fit={fit:.2f})",
                        generation_source=row.get("source") or "stage0_pass",
                    )
                    candidates_map[expr] = cand
                    eligible.append((sh, fit, cand))

            eligible.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return [c for _, _, c in eligible[:limit]]
        except Exception as e:
            log.warning("Could not load stage0 candidates from local CSV fallback: %s", e)
            return []

