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

from contextlib import contextmanager
try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None

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

CREATE TABLE IF NOT EXISTS options_rejected_alphas (
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
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS options_correlated_alphas (
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
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cluster_session_cache (
    key VARCHAR(64) PRIMARY KEY,
    token TEXT NOT NULL,
    cookies JSONB,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cluster_run_lock (
    worker_id VARCHAR(64) PRIMARY KEY,
    org_name VARCHAR(64) NOT NULL,
    archetype VARCHAR(128),
    heartbeat TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_options_alphas_alpha_id ON options_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_alphas_status_created ON options_alphas(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_options_alphas_archetype ON options_alphas(archetype);
CREATE INDEX IF NOT EXISTS idx_options_evaluations_expr ON options_evaluations(expression);
CREATE INDEX IF NOT EXISTS idx_options_eval_created_status ON options_evaluations(created_at DESC, status);
CREATE INDEX IF NOT EXISTS idx_options_learning_reward ON options_learning_memory(reward DESC);
CREATE INDEX IF NOT EXISTS idx_options_learning_archetype ON options_learning_memory(archetype);
CREATE INDEX IF NOT EXISTS idx_options_rejected_alpha_id ON options_rejected_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_rejected_reason ON options_rejected_alphas(rejection_reason);
CREATE INDEX IF NOT EXISTS idx_options_rejected_created ON options_rejected_alphas(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_options_correlated_alpha_id ON options_correlated_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_correlated_created ON options_correlated_alphas(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_session_expires ON cluster_session_cache(expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_cluster_run_heartbeat ON cluster_run_lock(heartbeat DESC);
"""


class OptionsDatabase:
    def __init__(self, database_url: Optional[str]):
        self.database_url = database_url
        self._pool: Optional[ConnectionPool] = None
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            if ConnectionPool is not None:
                try:
                    self._pool = ConnectionPool(
                        conninfo=url,
                        min_size=1,
                        max_size=10,
                        open=True,
                        timeout=15.0,
                    )
                    log.info("PostgreSQL connection pool initialized (min=1, max=10).")
                except Exception as pool_err:
                    log.warning("Connection pool initialization failed, falling back to direct connection: %s", pool_err)
                    self._pool = None
            self._init_schema()

    @contextmanager
    def _get_connection(self):
        if not self.database_url:
            yield None
            return

        if self._pool is not None:
            with self._pool.connection() as conn:
                yield conn
        else:
            import psycopg
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            conn = psycopg.connect(url)
            try:
                yield conn
            finally:
                conn.close()

    def close(self):
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception:
                pass

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

    def get_unsubmitted_pool_alphas(self) -> List[Dict[str, Any]]:
        """Returns alphas in options_alphas that have not yet been submitted, ordered by Composite Quality Score (CQS)."""
        if not self.database_url:
            return []
        sql = """
            SELECT alpha_id, expression, archetype, hypothesis, sharpe, fitness, turnover, returns, drawdown, margin,
                   (1.0 * COALESCE(sharpe, 0) + 1.2 * COALESCE(fitness, 0) + 200 * COALESCE(margin, 0) - 0.5 * COALESCE(turnover, 0)) AS cqs
            FROM options_alphas
            WHERE status = 'QUALIFIED' AND alpha_id IS NOT NULL
            ORDER BY (1.0 * COALESCE(sharpe, 0) + 1.2 * COALESCE(fitness, 0) + 200 * COALESCE(margin, 0) - 0.5 * COALESCE(turnover, 0)) DESC, sharpe DESC;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cols = [desc[0] for desc in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as e:
            log.warning("Failed to load unsubmitted pool alphas: %s", e)
            return []

    def mark_alpha_submitted(self, alpha_id: str):
        """Marks an alpha as SUBMITTED in options_alphas."""
        if not self.database_url:
            return
        sql = "UPDATE options_alphas SET status = 'SUBMITTED' WHERE alpha_id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (alpha_id,))
                conn.commit()
            log.info("Marked alpha %s as SUBMITTED in database.", alpha_id)
        except Exception as e:
            log.warning("Failed to mark alpha %s as SUBMITTED: %s", alpha_id, e)

    def mark_alpha_correlated(
        self,
        alpha_id: str,
        reason: str = "",
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        """Archives alpha into options_correlated_alphas and frees it from options_alphas."""
        if not self.database_url:
            return
        self.archive_correlated_alpha(alpha_id, f"CORRELATED: {reason}", cand_data, max_corr)

    def archive_correlated_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        """
        Archives a correlated alpha into options_correlated_alphas with correlation metrics,
        and deletes it from options_alphas to completely free up the qualified table.
        """
        if not self.database_url:
            return

        cand = cand_data or {}
        expr = cand.get("expression") or ""
        arch = cand.get("archetype") or ""
        hyp = cand.get("hypothesis") or ""
        src = cand.get("source") or ""
        sharpe = cand.get("sharpe")
        fitness = cand.get("fitness")
        turnover = cand.get("turnover")
        returns = cand.get("returns")
        drawdown = cand.get("drawdown")
        margin = cand.get("margin")
        corr_val = max_corr if max_corr is not None else cand.get("max_correlation")

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Attempt to copy from options_alphas if record exists
                    cur.execute(
                        """
                        INSERT INTO options_correlated_alphas (
                            alpha_id, expression, archetype, hypothesis, source,
                            sharpe, fitness, turnover, returns, drawdown, margin,
                            max_correlation, rejection_reason
                        )
                        SELECT alpha_id, expression, archetype, hypothesis, source,
                               sharpe, fitness, turnover, returns, drawdown, margin,
                               COALESCE(%s, max_correlation), %s
                        FROM options_alphas
                        WHERE alpha_id = %s
                        RETURNING id;
                        """,
                        (corr_val, reason, alpha_id),
                    )
                    row = cur.fetchone()

                    # 2. If not in options_alphas, insert directly
                    if not row and expr:
                        cur.execute(
                            """
                            INSERT INTO options_correlated_alphas (
                                alpha_id, expression, archetype, hypothesis, source,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                max_correlation, rejection_reason
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """,
                            (
                                alpha_id, expr, arch, hyp, src,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                corr_val, reason,
                            ),
                        )

                    # 3. Delete from options_alphas to free up the qualified table
                    cur.execute(
                        "DELETE FROM options_alphas WHERE alpha_id = %s;",
                        (alpha_id,),
                    )
                conn.commit()
            log.info("Archived correlated alpha %s to options_correlated_alphas and freed from options_alphas.", alpha_id)
        except Exception as e:
            log.warning("Failed to archive correlated alpha %s: %s", alpha_id, e)

    def archive_rejected_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Archives a rejected alpha into options_rejected_alphas with exact failure diagnostic,
        and deletes it from options_alphas to completely free up the qualified table.
        """
        if not self.database_url:
            return

        cand = cand_data or {}
        expr = cand.get("expression") or ""
        arch = cand.get("archetype") or ""
        hyp = cand.get("hypothesis") or ""
        src = cand.get("source") or ""
        sharpe = cand.get("sharpe")
        fitness = cand.get("fitness")
        turnover = cand.get("turnover")
        returns = cand.get("returns")
        drawdown = cand.get("drawdown")
        margin = cand.get("margin")

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Attempt to copy from options_alphas if record exists
                    cur.execute(
                        """
                        INSERT INTO options_rejected_alphas (
                            alpha_id, expression, archetype, hypothesis, source,
                            sharpe, fitness, turnover, returns, drawdown, margin,
                            rejection_reason
                        )
                        SELECT alpha_id, expression, archetype, hypothesis, source,
                               sharpe, fitness, turnover, returns, drawdown, margin,
                               %s
                        FROM options_alphas
                        WHERE alpha_id = %s
                        RETURNING id;
                        """,
                        (reason, alpha_id),
                    )
                    row = cur.fetchone()

                    # 2. If alpha was not in options_alphas but cand_data has expression, insert directly
                    if not row and expr:
                        cur.execute(
                            """
                            INSERT INTO options_rejected_alphas (
                                alpha_id, expression, archetype, hypothesis, source,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                rejection_reason
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """,
                            (
                                alpha_id, expr, arch, hyp, src,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                reason,
                            ),
                        )

                    # 3. Delete from options_alphas to free up the qualified table
                    cur.execute(
                        "DELETE FROM options_alphas WHERE alpha_id = %s;",
                        (alpha_id,),
                    )
                conn.commit()
            log.info("Archived rejected alpha %s to options_rejected_alphas and freed from options_alphas.", alpha_id)
        except Exception as e:
            log.warning("Failed to archive rejected alpha %s: %s", alpha_id, e)

    def get_recently_submitted_archetypes(self, limit: int = 3) -> List[str]:
        """Returns archetypes of the most recently submitted alphas to promote portfolio diversity."""
        if not self.database_url:
            return []
        sql = """
            SELECT archetype FROM options_alphas
            WHERE status = 'SUBMITTED' AND archetype IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (limit,))
                    return [row[0] for row in cur.fetchall() if row[0]]
        except Exception as e:
            log.warning("Failed to load recently submitted archetypes: %s", e)
            return []

    def get_today_saturated_archetypes(self, max_per_day: int = 1) -> List[str]:
        """
        Dynamic Archetype Quota Enforcer (Pillar 1):
        Returns archetypes that have already produced >= max_per_day qualified or submitted alphas today.
        Used to dynamically drop probability weight to 0.02 and steer workers to unfilled channels.
        """
        if not self.database_url:
            return []
        sql = """
            SELECT archetype, COUNT(*) as cnt
            FROM options_alphas
            WHERE status IN ('QUALIFIED', 'SUBMITTED')
              AND archetype IS NOT NULL
              AND created_at >= CURRENT_DATE
            GROUP BY archetype
            HAVING COUNT(*) >= %s;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (max_per_day,))
                    return [row[0] for row in cur.fetchall() if row[0]]
        except Exception as e:
            log.warning("Failed to load today saturated archetypes: %s", e)
            return []

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

        # Option D: Institutional Anti-Correlation Penalty in Reinforcement Learning
        corr_penalty = 0.0
        max_c = getattr(metrics, "max_correlation", None)
        if max_c is not None and float(max_c) > 0.60:
            corr_penalty += 12.0 * (float(max_c) - 0.50)
        if status == "CORRELATED":
            corr_penalty += 8.0
        elif status == "REJECTED":
            corr_penalty += 15.0

        adjusted_reward = reward - corr_penalty

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
                            adjusted_reward,
                            optimization_steps,
                            parent_expression,
                            mutation_type,
                            status,
                            metrics.alpha_id,
                        ),
                    )
                conn.commit()
            log.info("Recorded learning memory for %s (Reward=%.2f, Sharpe=%.2f, Status=%s)", candidate.expression[:35], adjusted_reward, metrics.sharpe, status)
        except Exception as e:
            log.warning("Failed to record learning memory: %s", e)

    def load_top_performing_exemplars(
        self,
        limit: int = 5,
        min_sharpe: float = 1.0,
        exclude_archetypes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Loads top performing alpha formulas from learning memory or evaluations, excluding saturated or rejected branches."""
        if not self.database_url:
            return []

        # Exclude archetypes that are already saturated in submitted alphas to promote diversity
        arch_filter = ""
        params_mem: list = [min_sharpe]
        if exclude_archetypes:
            arch_filter = " AND archetype != ALL(%s)"
            params_mem.append(list(exclude_archetypes))
        params_mem.append(limit)

        sql = f"""
            SELECT expression, archetype, hypothesis, sharpe, fitness, turnover, returns, reward
            FROM options_learning_memory
            WHERE sharpe >= %s AND reward > 0.5 AND status NOT IN ('REJECTED', 'CORRELATED'){arch_filter}
            ORDER BY reward DESC, sharpe DESC
            LIMIT %s;
        """
        results: List[Dict[str, Any]] = []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, tuple(params_mem))
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
                    eval_params: list = [min_sharpe]
                    eval_arch_filter = ""
                    if exclude_archetypes:
                        eval_arch_filter = " AND archetype != ALL(%s)"
                        eval_params.append(list(exclude_archetypes))
                    eval_params.append(limit)

                    eval_sql = f"""
                        SELECT expression, archetype, hypothesis, sharpe, fitness, turnover, returns, reward
                        FROM (
                            SELECT DISTINCT ON (expression)
                                expression, archetype, 'Historical evaluation' as hypothesis, sharpe, fitness, turnover, returns,
                                (sharpe + 1.5 * LEAST(fitness, 2.0)) as reward
                            FROM options_evaluations
                            WHERE sharpe >= %s AND (status = 'PASS' OR status = 'QUALIFIED'){eval_arch_filter}
                            ORDER BY expression, sharpe DESC
                        ) sub
                        ORDER BY sharpe DESC, fitness DESC
                        LIMIT %s;
                    """
                    cur.execute(eval_sql, tuple(eval_params))
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
                COUNT(*) FILTER (WHERE status = 'PASS' OR LEFT(stage, 5) = 'DIAG_' OR status = 'QUALIFIED') as all_time_pass,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_evaluated,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE AND (status = 'PASS' OR LEFT(stage, 5) = 'DIAG_')) as today_stage0_pass
            FROM options_evaluations;
        """
        sql_alphas = """
            SELECT
                COUNT(*) as all_time_pool,
                COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_pool
            FROM options_alphas;
        """
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

                    cur.execute(sql_alphas)
                    row_a = cur.fetchone()
                    if row_a:
                        stats["all_time_pool_alphas"] = int(row_a[0] or 0)
                        stats["today_qualified"] = int(row_a[1] or 0)
            return stats
        except Exception as e:
            log.warning("Failed to load options stats: %s", e)
            return stats

    def get_stage0_passed_candidates(self, limit: int = 100) -> List[OptionCandidate]:
        """Loads distinct candidates that passed Stage 0 screening for re-optimization, ordered by highest Sharpe & Fitness."""
        if not self.database_url:
            return []
        sql = """
            SELECT expression, archetype, source, sharpe, fitness, turnover
            FROM (
                SELECT DISTINCT ON (expression)
                    expression, archetype, COALESCE(source, 'stage0_pass') as source,
                    sharpe, fitness, turnover
                FROM options_evaluations
                WHERE ((stage = 'STAGE0' AND status = 'PASS') OR (sharpe >= 0.35 AND fitness >= 0.20))
                  AND expression NOT IN (SELECT expression FROM options_alphas WHERE expression IS NOT NULL)
                  AND expression NOT IN (
                      SELECT expression FROM options_evaluations
                      WHERE expression IS NOT NULL
                        AND (stage = 'RETRY_COMPLETED' OR LEFT(stage, 5) = 'DIAG_' OR status IN ('OPTIMIZED', 'EXHAUSTED', 'RETRY_COMPLETED'))
                  )
                ORDER BY expression, sharpe DESC
            ) sub
            ORDER BY sharpe DESC, fitness DESC
            LIMIT %s;
        """
        candidates: List[OptionCandidate] = []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (limit,))
                    for row in cur.fetchall():
                        expr, arch, src, sh, fit, to = row
                        candidates.append(OptionCandidate(
                            expression=expr,
                            archetype_name=arch or "options_alpha",
                            hypothesis=f"Stage 0 passer (Sharpe={float(sh or 0):.2f}, Fit={float(fit or 0):.2f})",
                            generation_source=src or "stage0_pass",
                        ))
            return candidates
        except Exception as e:
            log.warning("Failed to load stage0 passed candidates: %s", e)
    def get_cached_session(self, key: str = "brain_session") -> Optional[Dict[str, Any]]:
        """Retrieves valid cached session cookies/tokens from PostgreSQL cluster cache."""
        if not self.database_url:
            return None
        sql = """
            SELECT token, cookies, expires_at FROM cluster_session_cache
            WHERE key = %s AND expires_at > CURRENT_TIMESTAMP;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (key,))
                    row = cur.fetchone()
                    if row:
                        import json
                        cookies = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
                        return {"token": row[0], "cookies": cookies, "expires_at": row[2]}
            return None
        except Exception as e:
            log.warning("Failed to read session cache: %s", e)
            return None

    def save_cached_session(
        self,
        token: str,
        cookies: Dict[str, str],
        expires_in_seconds: int = 7200,
        key: str = "brain_session",
    ):
        """Saves BRAIN session cookies to PostgreSQL cluster cache with TTL (default 2 hours)."""
        if not self.database_url:
            return
        import json
        sql = """
            INSERT INTO cluster_session_cache (key, token, cookies, expires_at, updated_at)
            VALUES (%s, %s, %s::jsonb, CURRENT_TIMESTAMP + (%s || ' seconds')::interval, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                token = EXCLUDED.token,
                cookies = EXCLUDED.cookies,
                expires_at = EXCLUDED.expires_at,
                updated_at = CURRENT_TIMESTAMP;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (key, token, json.dumps(cookies), expires_in_seconds))
                conn.commit()
            log.info("Saved BRAIN session to PostgreSQL cluster cache (TTL=%ds).", expires_in_seconds)
        except Exception as e:
            log.warning("Failed to save session cache: %s", e)

    def acquire_cluster_lock(
        self,
        org_name: str,
        worker_id: str,
        archetype: str = "",
        timeout_seconds: int = 900,
    ) -> bool:
        """
        Acquires a cluster-wide run lock to prevent simultaneous worker overlap on BRAIN,
        ensuring total simulations across all 5 orgs never exceed 3.
        """
        if not self.database_url:
            return True
        cleanup_sql = "DELETE FROM cluster_run_lock WHERE heartbeat < CURRENT_TIMESTAMP - INTERVAL '15 minutes';"
        insert_sql = """
            INSERT INTO cluster_run_lock (worker_id, org_name, archetype, heartbeat, started_at)
            SELECT %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM cluster_run_lock
                WHERE heartbeat >= CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                  AND worker_id != %s
            )
            ON CONFLICT (worker_id) DO UPDATE SET heartbeat = CURRENT_TIMESTAMP
            RETURNING worker_id;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(cleanup_sql)
                    cur.execute(insert_sql, (worker_id, org_name, archetype, worker_id))
                    res = cur.fetchone()
                conn.commit()
                acquired = res is not None
                if acquired:
                    log.info("Acquired cluster run lock for %s (%s).", org_name, worker_id)
                else:
                    log.warning("Cluster run lock busy. Another worker is currently simulating on BRAIN.")
                return acquired
        except Exception as e:
            log.warning("Failed to acquire cluster run lock: %s", e)
            return True

    def release_cluster_lock(self, worker_id: str):
        """Releases the cluster run lock."""
        if not self.database_url:
            return
        sql = "DELETE FROM cluster_run_lock WHERE worker_id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (worker_id,))
                conn.commit()
            log.info("Released cluster run lock for %s.", worker_id)
        except Exception as e:
            log.warning("Failed to release cluster run lock: %s", e)

    def penalize_learning_memory(self, target: str, penalty: float = -10.0, reason: str = ""):
        """Slashes reward of an expression in learning memory when rejected for correlation."""
        if not self.database_url or not target:
            return
        sql = """
            UPDATE options_learning_memory
            SET reward = LEAST(reward, %s),
                status = 'REJECTED'
            WHERE expression = %s 
               OR expression IN (SELECT expression FROM options_alphas WHERE alpha_id = %s);
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (penalty, target, target))
                conn.commit()
            log.info("Penalized learning memory for %s (Reward capped at %.2f, reason=%s).", target[:35], penalty, reason)
        except Exception as e:
            log.warning("Failed to penalize learning memory: %s", e)


def map_archetype_to_core(archetype_name: str) -> str:
    """Maps arbitrary human-readable archetype titles to canonical core category keys."""
    if not archetype_name:
        return "breakeven"
    name = archetype_name.lower()
    if "hybrid" in name or "confluence" in name or "divergence" in name:
        return "hybrid_confluence"
    elif "breakeven" in name:
        return "breakeven"
    elif "skew" in name or "smirk" in name:
        return "skew"
    elif "term_structure" in name or "term structure" in name or "vrp" in name or "variance" in name or "parkinson" in name:
        return "term_structure"
    elif "forward" in name or "basis" in name:
        return "forward_basis"
    elif "pcr" in name or "put-call" in name or "put_call" in name or "flow" in name:
        return "pcr_flow"
    elif "analyst" in name or "revision" in name or "dispersion" in name or "pead" in name or "target_price" in name or "price target" in name or "sales" in name:
        return "analyst_revisions"
    elif "short" in name or "borrow" in name or "days_to_cover" in name:
        return "short_interest"
    return name




