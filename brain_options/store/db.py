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

CREATE TABLE IF NOT EXISTS options_learning_memory (
    id SERIAL PRIMARY KEY,
    expression TEXT NOT NULL UNIQUE,
    archetype VARCHAR(128),
    hypothesis TEXT,
    source VARCHAR(32),
    sharpe NUMERIC(8, 4),
    fitness NUMERIC(8, 4),
    turnover NUMERIC(8, 4),
    returns NUMERIC(8, 4),
    drawdown NUMERIC(8, 4),
    reward NUMERIC(10, 4),
    optimization_steps INTEGER DEFAULT 0,
    parent_expression TEXT,
    mutation_type VARCHAR(64),
    status VARCHAR(32),
    alpha_id VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_options_alphas_alpha_id ON options_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_evaluations_expr ON options_evaluations(expression);
CREATE INDEX IF NOT EXISTS idx_options_learning_reward ON options_learning_memory(reward DESC);
CREATE INDEX IF NOT EXISTS idx_options_learning_archetype ON options_learning_memory(archetype);
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
        if not self.database_url:
            return
        sql = """
            INSERT INTO options_learning_memory 
            (expression, archetype, hypothesis, source, sharpe, fitness, turnover, returns, drawdown,
             reward, optimization_steps, parent_expression, mutation_type, status, alpha_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (expression) DO UPDATE SET
                sharpe = EXCLUDED.sharpe,
                fitness = EXCLUDED.fitness,
                turnover = EXCLUDED.turnover,
                returns = EXCLUDED.returns,
                drawdown = EXCLUDED.drawdown,
                reward = EXCLUDED.reward,
                optimization_steps = EXCLUDED.optimization_steps,
                status = EXCLUDED.status,
                alpha_id = EXCLUDED.alpha_id;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql,
                        (
                            candidate.expression,
                            candidate.archetype_name,
                            candidate.hypothesis,
                            candidate.generation_source,
                            metrics.sharpe,
                            metrics.fitness,
                            metrics.turnover,
                            metrics.annualized_return,
                            metrics.max_drawdown,
                            reward,
                            optimization_steps,
                            parent_expression,
                            mutation_type,
                            status,
                            metrics.alpha_id,
                        ),
                    )
                conn.commit()
            log.info("Recorded learning memory for %s (Reward=%.2f, Sharpe=%.2f)", candidate.expression[:35], reward, metrics.sharpe)
        except Exception as e:
            log.warning("Failed to record learning memory: %s", e)

    def load_top_performing_exemplars(self, limit: int = 5, min_sharpe: float = 1.0) -> List[Dict[str, Any]]:
        """Loads top performing alpha formulas from learning memory or evaluations."""
        if not self.database_url:
            return []
        # First check options_learning_memory
        sql = """
            SELECT expression, archetype, hypothesis, sharpe, fitness, turnover, returns, reward
            FROM options_learning_memory
            WHERE sharpe >= %s
            ORDER BY reward DESC, sharpe DESC
            LIMIT %s;
        """
        results: List[Dict[str, Any]] = []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (min_sharpe, limit))
                    rows = cur.fetchall()
                    for r in rows:
                        results.append({
                            "expression": r[0],
                            "archetype": r[1],
                            "hypothesis": r[2],
                            "sharpe": float(r[3]) if r[3] is not None else 0.0,
                            "fitness": float(r[4]) if r[4] is not None else 0.0,
                            "turnover": float(r[5]) if r[5] is not None else 0.0,
                            "returns": float(r[6]) if r[6] is not None else 0.0,
                            "reward": float(r[7]) if r[7] is not None else 0.0,
                        })
                    if results:
                        return results

                    # If learning memory is fresh/empty, bootstrap from options_evaluations
                    eval_sql = """
                        SELECT expression, archetype, 'Historical evaluation' as hypothesis, sharpe, fitness, turnover, returns,
                               (sharpe + 1.5 * LEAST(fitness, 2.0)) as reward
                        FROM options_evaluations
                        WHERE sharpe >= %s AND status = 'PASS' OR sharpe >= 1.0
                        ORDER BY sharpe DESC
                        LIMIT %s;
                    """
                    cur.execute(eval_sql, (min_sharpe, limit))
                    rows = cur.fetchall()
                    for r in rows:
                        results.append({
                            "expression": r[0],
                            "archetype": r[1],
                            "hypothesis": r[2],
                            "sharpe": float(r[3]) if r[3] is not None else 0.0,
                            "fitness": float(r[4]) if r[4] is not None else 0.0,
                            "turnover": float(r[5]) if r[5] is not None else 0.0,
                            "returns": float(r[6]) if r[6] is not None else 0.0,
                            "reward": float(r[7]) if r[7] is not None else 0.0,
                        })
            return results
        except Exception as e:
            log.warning("Failed to load top performing exemplars: %s", e)
            return []

    def load_archetype_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Loads win rates and average metrics per archetype for Multi-Armed Bandit weighting."""
        if not self.database_url:
            return {}
        sql = """
            SELECT archetype,
                   COUNT(*) as total_sims,
                   COUNT(*) FILTER (WHERE status = 'PASS' OR sharpe >= 0.70) as passed_sims,
                   AVG(sharpe) as avg_sharpe,
                   AVG(fitness) as avg_fitness,
                   MAX(sharpe) as max_sharpe
            FROM options_evaluations
            WHERE archetype IS NOT NULL
            GROUP BY archetype;
        """
        summary: Dict[str, Dict[str, float]] = {}
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    for row in cur.fetchall():
                        arch, total, passed, avg_s, avg_f, max_s = row
                        summary[arch] = {
                            "total": int(total),
                            "passed": int(passed),
                            "pass_rate": float(passed) / max(1, int(total)),
                            "avg_sharpe": float(avg_s) if avg_s is not None else 0.0,
                            "avg_fitness": float(avg_f) if avg_f is not None else 0.0,
                            "max_sharpe": float(max_s) if max_s is not None else 0.0,
                        }
            return summary
        except Exception as e:
            log.warning("Failed to load archetype performance summary: %s", e)
            return {}

    def get_options_stats(self) -> Dict[str, Any]:
        """Loads daily and all-time options alpha statistics."""
        if not self.database_url:
            return {}
        stats: Dict[str, Any] = {
            "all_time_evaluated": 0,
            "all_time_stage0_pass": 0,
            "all_time_pool_alphas": 0,
            "today_evaluated": 0,
            "today_stage0_pass": 0,
            "today_qualified": 0,
        }
        sql_eval = """
            SELECT
                COUNT(*) as all_time_evaluated,
                COUNT(*) FILTER (WHERE status = 'PASS' OR stage LIKE 'DIAG_%' OR status = 'QUALIFIED') as all_time_pass,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_evaluated,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE AND (status = 'PASS' OR stage LIKE 'DIAG_%')) as today_stage0_pass,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE AND status = 'QUALIFIED') as today_qualified
            FROM options_evaluations;
        """
        sql_alphas = "SELECT COUNT(*) FROM options_alphas;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_eval)
                    row = cur.fetchone()
                    if row:
                        stats["all_time_evaluated"] = int(row[0] or 0)
                        stats["all_time_stage0_pass"] = int(row[1] or 0)
                        stats["today_evaluated"] = int(row[2] or 0)
                        stats["today_stage0_pass"] = int(row[3] or 0)
                        stats["today_qualified"] = int(row[4] or 0)

                    cur.execute(sql_alphas)
                    row_a = cur.fetchone()
                    if row_a:
                        stats["all_time_pool_alphas"] = int(row_a[0] or 0)
            return stats
        except Exception as e:
            log.warning("Failed to load options stats: %s", e)
            return stats


