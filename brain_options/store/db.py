"""
PostgreSQL database adapter for brain_options.
Manages dedicated tables:
- `options_alphas`: qualified and accepted options alphas.
- `options_evaluations`: tracking for every candidate screened or optimized.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from brain_options.core.client import SimMetrics, SimSettings
from brain_options.specialist.templates import OptionCandidate

log = logging.getLogger("brain_options.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS options_alphas (
    id SERIAL PRIMARY KEY,
    alpha_id VARCHAR(64),
    expression TEXT NOT NULL,
    archetype VARCHAR(128),
    hypothesis TEXT,
    source VARCHAR(32),
    sharpe NUMERIC(8, 4),
    fitness NUMERIC(8, 4),
    turnover NUMERIC(8, 4),
    returns NUMERIC(8, 4),
    drawdown NUMERIC(8, 4),
    margin NUMERIC(10, 6),
    max_correlation NUMERIC(8, 4),
    universe VARCHAR(32),
    neutralization VARCHAR(32),
    delay INTEGER,
    decay INTEGER,
    truncation NUMERIC(6, 4),
    pasteurization VARCHAR(8),
    nan_handling VARCHAR(8),
    status VARCHAR(32) DEFAULT 'QUALIFIED',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS options_evaluations (
    id SERIAL PRIMARY KEY,
    expression TEXT NOT NULL,
    archetype VARCHAR(128),
    source VARCHAR(32),
    stage VARCHAR(32),
    status VARCHAR(32),
    sharpe NUMERIC(8, 4),
    fitness NUMERIC(8, 4),
    turnover NUMERIC(8, 4),
    returns NUMERIC(8, 4),
    drawdown NUMERIC(8, 4),
    alpha_id VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_options_alphas_alpha_id ON options_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_evaluations_expr ON options_evaluations(expression);
"""


class OptionsDatabase:
    def __init__(self, database_url: Optional[str]):
        self.database_url = database_url
        if self.database_url:
            self._init_schema()

    def _get_connection(self):
        if not self.database_url:
            return None
        import psycopg
        return psycopg.connect(self.database_url)

    def _init_schema(self):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(SCHEMA_SQL)
                conn.commit()
            log.info("Options database schema initialized successfully.")
        except Exception as e:
            log.warning("Database schema initialization warning: %s", e)

    def record_candidate(
        self, candidate: OptionCandidate, stage: str, status: str, metrics: SimMetrics
    ):
        if not self.database_url:
            return
        sql = """
            INSERT INTO options_evaluations 
            (expression, archetype, source, stage, status, sharpe, fitness, turnover, returns, drawdown, alpha_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            candidate.expression,
                            candidate.archetype_name,
                            candidate.generation_source,
                            stage,
                            status,
                            metrics.sharpe,
                            metrics.fitness,
                            metrics.turnover,
                            metrics.annualized_return,
                            metrics.max_drawdown,
                            metrics.alpha_id,
                        ),
                    )
                conn.commit()
        except Exception as e:
            log.warning("Failed to record candidate in database: %s", e)

    def save_passed_alpha(
        self,
        candidate: OptionCandidate,
        settings: SimSettings,
        metrics: SimMetrics,
        max_corr: float,
    ):
        if not self.database_url:
            return
        sql = """
            INSERT INTO options_alphas
            (alpha_id, expression, archetype, hypothesis, source, sharpe, fitness, turnover, returns,
             drawdown, margin, max_correlation, universe, neutralization, delay, decay, truncation,
             pasteurization, nan_handling, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'QUALIFIED');
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            metrics.alpha_id,
                            candidate.expression,
                            candidate.archetype_name,
                            candidate.hypothesis,
                            candidate.generation_source,
                            metrics.sharpe,
                            metrics.fitness,
                            metrics.turnover,
                            metrics.annualized_return,
                            metrics.max_drawdown,
                            metrics.margin,
                            max_corr,
                            settings.universe,
                            settings.neutralization,
                            settings.delay,
                            settings.decay,
                            settings.truncation,
                            "ON" if settings.pasteurization else "OFF",
                            "ON" if settings.nan_handling else "OFF",
                        ),
                    )
                conn.commit()
            log.info("Saved passed alpha %s to database table options_alphas.", metrics.alpha_id or candidate.expression[:30])
        except Exception as e:
            log.warning("Failed to save passed alpha in database: %s", e)

    def load_evaluated_expressions(self) -> Set[str]:
        if not self.database_url:
            return set()
        sql = "SELECT DISTINCT expression FROM options_evaluations;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return {row[0].strip() for row in cur.fetchall() if row[0]}
        except Exception as e:
            log.warning("Failed to load evaluated expressions from database: %s", e)
            return set()
