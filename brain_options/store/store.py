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
from brain_options.core.client import SimMetrics, SimSettings
from brain_options.specialist.templates import OptionCandidate
from brain_options.store.db import OptionsDatabase

log = logging.getLogger("brain_options.store")


class OptionsStore:
    def __init__(self, data_dir: Optional[str] = None, database_url: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.passed_csv = os.path.join(self.data_dir, "passed_options_alphas.csv")
        self.passed_json = os.path.join(self.data_dir, "passed_options_alphas.json")
        self.rejected_csv = os.path.join(self.data_dir, "rejected_options_alphas.csv")
        self.history_csv = os.path.join(self.data_dir, "evaluated_candidates.csv")
        self.pnl_cache_dir = os.path.join(self.data_dir, "pnl_series")
        os.makedirs(self.pnl_cache_dir, exist_ok=True)

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
        """Loads all cached daily return series of previously passed alphas."""
        series_list: list[dict[str, float]] = []
        if not os.path.exists(self.pnl_cache_dir):
            return series_list

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

    def load_top_performing_exemplars(self, limit: int = 5, min_sharpe: float = 1.0) -> List[Dict[str, Any]]:
        return self.db.load_top_performing_exemplars(limit=limit, min_sharpe=min_sharpe)

    def load_archetype_performance_summary(self) -> Dict[str, Dict[str, float]]:
        return self.db.load_archetype_performance_summary()

    def get_options_stats(self) -> Dict[str, Any]:
        return self.db.get_options_stats()

    def get_unsubmitted_pool_alphas(self) -> List[Dict[str, Any]]:
        return self.db.get_unsubmitted_pool_alphas()

    def get_recently_submitted_archetypes(self, limit: int = 3) -> List[str]:
        return self.db.get_recently_submitted_archetypes(limit=limit)

    def mark_alpha_submitted(self, alpha_id: str):
        self.db.mark_alpha_submitted(alpha_id)

    def mark_alpha_correlated(self, alpha_id: str, reason: str = ""):
        self.archive_rejected_alpha(alpha_id, f"CORRELATED: {reason}")

    def archive_rejected_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
    ):
        """Archives rejected/correlated alpha in both PostgreSQL and local storage."""
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

            # Update passed_options_alphas.json status if present
            if os.path.exists(self.passed_json):
                try:
                    with open(self.passed_json, "r", encoding="utf-8") as f:
                        records = json.load(f)
                    updated = False
                    for r in records:
                        if r.get("alpha_id") == alpha_id:
                            r["status"] = "REJECTED"
                            r["rejection_reason"] = reason
                            updated = True
                    if updated:
                        with open(self.passed_json, "w", encoding="utf-8") as f:
                            json.dump(records, f, indent=2)
                except Exception as e:
                    log.warning("Could not update status in passed_json: %s", e)



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

