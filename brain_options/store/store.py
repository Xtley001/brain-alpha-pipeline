"""
Local store for passed options alphas and evaluated candidate history.
Maintains clean CSV and JSON records with full reproduction parameters.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
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
        self.history_csv = os.path.join(self.data_dir, "evaluated_candidates.csv")
        self.pnl_cache_dir = os.path.join(self.data_dir, "pnl_series")
        os.makedirs(self.pnl_cache_dir, exist_ok=True)

        self.db = OptionsDatabase(database_url)

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

