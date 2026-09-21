"""
PostgreSQL database adapter for brain_options.

DATABASE SCHEMA — 7 Tables
============================

1. options_alphas          — The primary alpha pool (qualified, submitted, or archived).
2. options_evaluations     — Immutable log of every single simulation run across all orgs.
3. options_learning_memory — Reinforcement learning (MAB) memory: reward scores per expression.
4. options_rejected_alphas — Archive of alphas that failed platform checklist gates.
5. options_correlated_alphas — Archive of alphas that failed the self-correlation < 0.70 gate.
6. cluster_session_cache   — Shared BRAIN session token cache across all 4 worker orgs.
7. cluster_run_lock        — Cluster-wide mutex: prevents more than 1 org simulating at a time.

All tables are created with IF NOT EXISTS so the schema is safe to run on first boot and on
upgrades. Indexes are maintained for all hot query paths.
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

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- ============================================================
-- TABLE 1: options_alphas
-- Purpose: Primary alpha pool. Holds every alpha that passed
--   all qualification gates (Sharpe >= 1.25, Fitness >= 1.00,
--   self-correlation < 0.70, all BRAIN platform checklist gates).
-- Lifecycle:
--   QUALIFIED  → new, ready for submission via drip.yml
--   SUBMITTED  → drip submitter confirmed OS stage on BRAIN
-- When an alpha fails the correlation or checklist gate AFTER
--   initially being qualified, it is moved out of this table
--   into options_correlated_alphas or options_rejected_alphas
--   so this table stays clean and only holds actionable alphas.
-- ============================================================
CREATE TABLE IF NOT EXISTS options_alphas (
    id               SERIAL PRIMARY KEY,
    alpha_id         VARCHAR(64),
    expression       TEXT        NOT NULL,
    archetype        VARCHAR(128),
    hypothesis       TEXT,
    source           VARCHAR(32),          -- 'template', 'llm', 'procedural'
    sharpe           NUMERIC(8, 4),
    fitness          NUMERIC(8, 4),
    turnover         NUMERIC(8, 4),
    returns          NUMERIC(8, 4),
    drawdown         NUMERIC(8, 4),
    margin           NUMERIC(10, 6),
    max_correlation  NUMERIC(8, 4),
    universe         VARCHAR(32),
    neutralization   VARCHAR(32),
    delay            INTEGER,
    decay            INTEGER,
    truncation       NUMERIC(6, 4),
    pasteurization   VARCHAR(8),           -- 'ON' | 'OFF'
    nan_handling     VARCHAR(8),           -- 'ON' | 'OFF'
    status           VARCHAR(32) DEFAULT 'QUALIFIED',
    submitted_at     TIMESTAMPTZ,          -- Set when BRAIN OS stage confirmed
    created_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 2: options_evaluations
-- Purpose: Immutable audit log of every candidate tested
--   across all 4 worker orgs. Each simulation run appends
--   one row here. Never updated — only inserted.
-- Used for:
--   - Deduplication seed (ASTDeduplicator.populate on startup)
--   - MAB archetype performance summaries (win rates, avg Sharpe)
--   - Stage 0 re-optimizer candidate selection
--   - Daily/all-time discovery funnel stats
-- Key stage values: STAGE0, RETRY_COMPLETED, PRE_SCREEN, DIAG_*
-- Key status values: PASS, FAIL, QUALIFIED, EXHAUSTED,
--                    CORRELATED, REJECTED, DUPLICATE_AST
-- ============================================================
CREATE TABLE IF NOT EXISTS options_evaluations (
    id          SERIAL PRIMARY KEY,
    expression  TEXT        NOT NULL,
    archetype   VARCHAR(128),
    source      VARCHAR(32),
    stage       VARCHAR(32),
    status      VARCHAR(32),
    sharpe      NUMERIC(8, 4),
    fitness     NUMERIC(8, 4),
    turnover    NUMERIC(8, 4),
    returns     NUMERIC(8, 4),
    drawdown    NUMERIC(8, 4),
    alpha_id    VARCHAR(64),
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 3: options_learning_memory
-- Purpose: Multi-Armed Bandit (MAB) reinforcement learning
--   memory. Stores one row per unique expression with an
--   accumulated reward score.
-- Used by OptionsGenerator to:
--   - Weight archetype MAB arms (higher reward = more sampling)
--   - Bootstrap top-performing expressions as mutation seeds
--   - Penalise correlated/rejected expressions (reward -= 15)
-- Unique constraint on expression ensures ON CONFLICT upserts.
-- Status values: EVALUATED, QUALIFIED, REJECTED, CORRELATED
-- ============================================================
CREATE TABLE IF NOT EXISTS options_learning_memory (
    id                 SERIAL PRIMARY KEY,
    expression         TEXT        NOT NULL UNIQUE,
    archetype          VARCHAR(128),
    hypothesis         TEXT,
    source             VARCHAR(32),
    sharpe             NUMERIC(8, 4),
    fitness            NUMERIC(8, 4),
    turnover           NUMERIC(8, 4),
    returns            NUMERIC(8, 4),
    drawdown           NUMERIC(8, 4),
    reward             NUMERIC(10, 4),
    optimization_steps INTEGER       DEFAULT 0,
    parent_expression  TEXT,
    mutation_type      VARCHAR(64),
    status             VARCHAR(32),
    alpha_id           VARCHAR(64),
    created_at         TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMPTZ   DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 4: options_rejected_alphas
-- Purpose: Archive of alphas that were initially qualified
--   (Sharpe/Fitness thresholds met) but then failed a
--   BRAIN platform checklist gate (LOW_SUB_UNIVERSE_SHARPE,
--   CONCENTRATED_WEIGHT, etc.) or were rejected by BRAIN
--   during submission.
-- These alphas are permanently barred from resubmission.
-- ============================================================
CREATE TABLE IF NOT EXISTS options_rejected_alphas (
    id               SERIAL PRIMARY KEY,
    alpha_id         VARCHAR(64),
    expression       TEXT        NOT NULL,
    archetype        VARCHAR(128),
    hypothesis       TEXT,
    source           VARCHAR(32),
    sharpe           NUMERIC(8, 4),
    fitness          NUMERIC(8, 4),
    turnover         NUMERIC(8, 4),
    returns          NUMERIC(8, 4),
    drawdown         NUMERIC(8, 4),
    margin           NUMERIC(10, 6),
    rejection_reason TEXT,
    created_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 5: options_correlated_alphas
-- Purpose: Archive of alphas that passed Sharpe/Fitness gates
--   but failed the self-correlation gate (corr >= 0.70
--   against the existing live submission portfolio).
-- Separated from rejected_alphas to allow future analysis:
--   a correlated alpha may become submittable once its
--   correlated peer is superseded or removed.
-- ============================================================
CREATE TABLE IF NOT EXISTS options_correlated_alphas (
    id               SERIAL PRIMARY KEY,
    alpha_id         VARCHAR(64),
    expression       TEXT        NOT NULL,
    archetype        VARCHAR(128),
    hypothesis       TEXT,
    source           VARCHAR(32),
    sharpe           NUMERIC(8, 4),
    fitness          NUMERIC(8, 4),
    turnover         NUMERIC(8, 4),
    returns          NUMERIC(8, 4),
    drawdown         NUMERIC(8, 4),
    margin           NUMERIC(10, 6),
    max_correlation  NUMERIC(8, 4),
    rejection_reason TEXT,
    created_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 6: cluster_session_cache
-- Purpose: Shared BRAIN session token cache across all 4
--   worker orgs and the Xtley001 drip org. Allows any of the
--   5 GitHub Actions runners to reuse a live authenticated
--   session instead of each logging in fresh, saving ~10s per
--   run and preventing rate-limiting from repeated login calls.
-- TTL is enforced by expires_at; stale rows are ignored on read.
-- ============================================================
CREATE TABLE IF NOT EXISTS cluster_session_cache (
    key         VARCHAR(64)  PRIMARY KEY,
    token       TEXT         NOT NULL,
    cookies     JSONB,
    expires_at  TIMESTAMPTZ  NOT NULL,
    updated_at  TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 7: cluster_run_lock
-- Purpose: Cluster-wide mutex that ensures only 1 of the 4
--   worker orgs runs simulations on BRAIN at a time. Since all
--   worker orgs share the same BRAIN researcher account, running
--   simulations concurrently would cause the BRAIN API to reject
--   additional requests (3 concurrent sim limit).
-- Rows auto-expire after 15 minutes via heartbeat-based cleanup.
-- The drip org (Xtley001) is excluded — it only submits, not sims.
-- ============================================================
CREATE TABLE IF NOT EXISTS cluster_run_lock (
    worker_id   VARCHAR(64)  PRIMARY KEY,
    org_name    VARCHAR(64)  NOT NULL,
    archetype   VARCHAR(128),
    heartbeat   TIMESTAMPTZ  NOT NULL,
    started_at  TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES — All hot query paths covered
-- ============================================================

-- options_alphas: drip submitter reads by status frequently
CREATE INDEX IF NOT EXISTS idx_options_alphas_alpha_id
    ON options_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_alphas_status_created
    ON options_alphas(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_options_alphas_archetype_status
    ON options_alphas(archetype, status);

-- options_evaluations: dedup seed loads all expressions;
-- MAB summary groups by archetype; stats filter by date
-- NOTE: No unique index here — historical data has duplicate (expression, stage) pairs.
-- Deduplication is handled in-memory by ASTDeduplicator on startup.
CREATE INDEX IF NOT EXISTS idx_options_eval_expr
    ON options_evaluations(expression);
CREATE INDEX IF NOT EXISTS idx_options_eval_archetype
    ON options_evaluations(archetype);
CREATE INDEX IF NOT EXISTS idx_options_eval_created_status
    ON options_evaluations(created_at DESC, status);

-- options_learning_memory: MAB reads by reward and archetype
CREATE INDEX IF NOT EXISTS idx_options_learning_reward
    ON options_learning_memory(reward DESC);
CREATE INDEX IF NOT EXISTS idx_options_learning_archetype
    ON options_learning_memory(archetype);
CREATE INDEX IF NOT EXISTS idx_options_learning_status
    ON options_learning_memory(status);

-- options_rejected_alphas: lookups by alpha_id and date
CREATE INDEX IF NOT EXISTS idx_options_rejected_alpha_id
    ON options_rejected_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_rejected_created
    ON options_rejected_alphas(created_at DESC);

-- options_correlated_alphas: lookups by alpha_id and date
CREATE INDEX IF NOT EXISTS idx_options_correlated_alpha_id
    ON options_correlated_alphas(alpha_id);
CREATE INDEX IF NOT EXISTS idx_options_correlated_created
    ON options_correlated_alphas(created_at DESC);

-- cluster_session_cache: validity check on every BRAIN API call
CREATE INDEX IF NOT EXISTS idx_cluster_session_expires
    ON cluster_session_cache(expires_at DESC);

-- cluster_run_lock: heartbeat-based stale lock cleanup
CREATE INDEX IF NOT EXISTS idx_cluster_run_heartbeat
    ON cluster_run_lock(heartbeat DESC);

-- ============================================================
-- TABLE 8: org_runs
-- Purpose: Heartbeat log - one row per GitHub Actions org run.
-- Proves which orgs are actually firing and allows the health
-- check to report multi-org activity status.
-- ============================================================
CREATE TABLE IF NOT EXISTS org_runs (
    id          SERIAL PRIMARY KEY,
    org_name    VARCHAR(64)  NOT NULL,
    archetype   VARCHAR(128),
    run_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    evals_done  INTEGER      DEFAULT 0,
    qualified   INTEGER      DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_org_runs_org_run_at
    ON org_runs(org_name, run_at DESC);
"""



# Migration SQL: idempotent patches for existing deployments.
# Each statement runs independently (split on ;) so a single failure
# never blocks subsequent migrations.
MIGRATION_SQL = """
-- v2.1: submitted_at for options_alphas
ALTER TABLE options_alphas
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ;

-- v2.1: updated_at for learning memory
ALTER TABLE options_learning_memory
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

-- v2.2: backfill submitted_at for existing SUBMITTED rows so drip pacing works
UPDATE options_alphas
    SET submitted_at = created_at
    WHERE status = 'SUBMITTED' AND submitted_at IS NULL;

-- v2.2: UNIQUE constraint on alpha_id in archive tables to prevent duplicate rows
-- for the same alpha being rejected/correlated multiple times.
-- Uses CREATE UNIQUE INDEX IF NOT EXISTS (safer than ALTER TABLE on existing data).
CREATE UNIQUE INDEX IF NOT EXISTS uq_corr_alpha_id
    ON options_correlated_alphas(alpha_id)
    WHERE alpha_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rej_alpha_id
    ON options_rejected_alphas(alpha_id)
    WHERE alpha_id IS NOT NULL;

-- v2.2: Upgrade SERIAL sequences to BIGINT for long-term durability
ALTER SEQUENCE IF EXISTS options_evaluations_id_seq AS BIGINT;
ALTER SEQUENCE IF EXISTS options_alphas_id_seq AS BIGINT;
ALTER SEQUENCE IF EXISTS options_correlated_alphas_id_seq AS BIGINT;
ALTER SEQUENCE IF EXISTS options_rejected_alphas_id_seq AS BIGINT;

-- v2.2: org_runs table for multi-org heartbeat (added here as a migration too)
CREATE TABLE IF NOT EXISTS org_runs (
    id          BIGSERIAL    PRIMARY KEY,
    org_name    VARCHAR(64)  NOT NULL,
    archetype   VARCHAR(128),
    run_at      TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    evals_done  INTEGER      DEFAULT 0,
    qualified   INTEGER      DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_org_runs_org_run_at
    ON org_runs(org_name, run_at DESC);
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
                        kwargs={
                            "connect_timeout": 15,
                            "keepalives": 1,
                            "keepalives_idle": 30,
                            "keepalives_interval": 10,
                            "keepalives_count": 5,
                        },
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
            conn = psycopg.connect(
                url,
                connect_timeout=15,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
            )
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
        """
        Creates all 7 tables and indexes, then runs idempotent migration patches.
        Each SQL statement is executed independently so a single failure (e.g. a
        unique index that can't be created on existing data) never blocks the
        critical migration statements that add new columns.
        """
        def _run_statements(sql_block: str, label: str):
            """Split a SQL block on semicolons and execute each statement independently."""
            for stmt in sql_block.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    with self._get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(stmt)
                        conn.commit()
                except Exception as err:
                    log.debug("%s statement skipped: %s | SQL: %s", label, err, stmt[:80])

        _run_statements(SCHEMA_SQL, "SCHEMA")
        _run_statements(MIGRATION_SQL, "MIGRATION")
        log.info("Database schema initialized (7 tables, migrations applied).")

    # ------------------------------------------------------------------
    # options_evaluations — write path
    # ------------------------------------------------------------------

    def record_candidate(
        self, candidate: OptionCandidate, stage: str, status: str, metrics: SimMetrics
    ):
        """
        Appends one row to options_evaluations for every simulation stage event.
        Uses INSERT … ON CONFLICT DO NOTHING on the (expression, stage) unique index
        to prevent duplicate rows from concurrent workers writing the same result.
        """
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

    # ------------------------------------------------------------------
    # options_alphas — write path
    # ------------------------------------------------------------------

    def save_passed_alpha(
        self,
        candidate: OptionCandidate,
        settings: SimSettings,
        metrics: SimMetrics,
        max_corr: float,
    ):
        """
        Saves a fully qualified alpha to options_alphas with status='QUALIFIED'.
        Uses ON CONFLICT (alpha_id) DO NOTHING to safely handle concurrent workers
        discovering the same alpha simultaneously.
        """
        if not self.database_url:
            return
        sql = """
            INSERT INTO options_alphas
            (alpha_id, expression, archetype, hypothesis, source, sharpe, fitness, turnover, returns,
             drawdown, margin, max_correlation, universe, neutralization, delay, decay, truncation,
             pasteurization, nan_handling, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'QUALIFIED')
            ON CONFLICT DO NOTHING;
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
            log.info("Saved passed alpha %s to options_alphas.", metrics.alpha_id or candidate.expression[:30])
        except Exception as e:
            log.warning("Failed to save passed alpha in database: %s", e)

    # ------------------------------------------------------------------
    # options_alphas — read path
    # ------------------------------------------------------------------

    def get_unsubmitted_pool_alphas(self) -> List[Dict[str, Any]]:
        """
        Returns all alphas in options_alphas with status='QUALIFIED' (i.e. not yet
        submitted), ranked by Composite Quality Score (CQS = Sharpe + 1.2×Fitness
        + 200×Margin - 0.5×Turnover) for optimal drip ordering.
        """
        if not self.database_url:
            return []
        sql = """
            SELECT alpha_id, expression, archetype, hypothesis, sharpe, fitness, turnover, returns, drawdown, margin,
                   (1.0 * COALESCE(sharpe, 0) + 1.2 * COALESCE(fitness, 0) + 200 * COALESCE(margin, 0) - 0.5 * COALESCE(turnover, 0)) AS cqs
            FROM options_alphas
            WHERE status = 'QUALIFIED' AND alpha_id IS NOT NULL
            ORDER BY cqs DESC, sharpe DESC;
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
        """
        Marks an alpha as SUBMITTED in options_alphas and records the exact submission
        timestamp. Called once BRAIN confirms the OS stage transition.
        """
        if not self.database_url:
            return
        sql = "UPDATE options_alphas SET status = 'SUBMITTED', submitted_at = CURRENT_TIMESTAMP WHERE alpha_id = %s;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (alpha_id,))
                conn.commit()
            log.info("Marked alpha %s as SUBMITTED.", alpha_id)
        except Exception as e:
            log.warning("Failed to mark alpha %s as SUBMITTED: %s", alpha_id, e)

    def get_submitted_alpha_ids(self) -> Set[str]:
        """
        Returns the set of alpha_ids currently in options_alphas with status='SUBMITTED'.
        Used by load_pool_pnl_series() to build the exact active correlation reference
        set = QUALIFIED (reserve) ∪ SUBMITTED (live on BRAIN). This prevents the
        correlation gate from comparing a new candidate against stale archived alphas.
        """
        if not self.database_url:
            return set()
        sql = "SELECT alpha_id FROM options_alphas WHERE status = 'SUBMITTED' AND alpha_id IS NOT NULL;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return {row[0] for row in cur.fetchall() if row[0]}
        except Exception as e:
            log.warning("Failed to load submitted alpha IDs: %s", e)
            return set()

    def mark_alpha_correlated(
        self,
        alpha_id: str,
        reason: str = "",
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        """
        Moves an alpha from options_alphas → options_correlated_alphas.
        Called when the drip submitter detects a late-stage correlation failure.
        """
        if not self.database_url:
            return
        self.archive_correlated_alpha(alpha_id, f"CORRELATED: {reason}", cand_data, max_corr)

    # ------------------------------------------------------------------
    # Archive operations (move out of options_alphas)
    # ------------------------------------------------------------------

    def archive_correlated_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
        max_corr: Optional[float] = None,
    ):
        """
        Copies a correlated alpha into options_correlated_alphas then deletes it
        from options_alphas, keeping the qualified pool clean.
        Source data is pulled from options_alphas first; cand_data is used as fallback
        for alphas that were never saved to options_alphas (e.g. caught at run_candidate gate).
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
                    # 1. Copy from options_alphas if it exists there
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
                        ON CONFLICT DO NOTHING
                        RETURNING id;
                        """,
                        (corr_val, reason, alpha_id),
                    )
                    row = cur.fetchone()

                    # 2. If not in options_alphas, insert directly from cand_data
                    if not row and expr:
                        cur.execute(
                            """
                            INSERT INTO options_correlated_alphas (
                                alpha_id, expression, archetype, hypothesis, source,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                max_correlation, rejection_reason
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (
                                alpha_id, expr, arch, hyp, src,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                corr_val, reason,
                            ),
                        )

                    # 3. Free options_alphas
                    cur.execute("DELETE FROM options_alphas WHERE alpha_id = %s;", (alpha_id,))
                conn.commit()
            log.info("Archived correlated alpha %s → options_correlated_alphas.", alpha_id)
        except Exception as e:
            log.warning("Failed to archive correlated alpha %s: %s", alpha_id, e)

    def archive_rejected_alpha(
        self,
        alpha_id: str,
        reason: str,
        cand_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Copies a checklist-failed alpha into options_rejected_alphas then deletes it
        from options_alphas. Called when BRAIN returns a FAIL on any checklist gate
        (LOW_SHARPE, LOW_FITNESS, LOW_SUB_UNIVERSE_SHARPE, CONCENTRATED_WEIGHT, etc.)
        or when post-submission async validation shows it was rejected by the platform.
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
                    # 1. Copy from options_alphas if it exists there
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
                        ON CONFLICT DO NOTHING
                        RETURNING id;
                        """,
                        (reason, alpha_id),
                    )
                    row = cur.fetchone()

                    # 2. If not in options_alphas, insert directly from cand_data
                    if not row and expr:
                        cur.execute(
                            """
                            INSERT INTO options_rejected_alphas (
                                alpha_id, expression, archetype, hypothesis, source,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                rejection_reason
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT DO NOTHING;
                            """,
                            (
                                alpha_id, expr, arch, hyp, src,
                                sharpe, fitness, turnover, returns, drawdown, margin,
                                reason,
                            ),
                        )

                    # 3. Free options_alphas
                    cur.execute("DELETE FROM options_alphas WHERE alpha_id = %s;", (alpha_id,))
                conn.commit()
            log.info("Archived rejected alpha %s → options_rejected_alphas.", alpha_id)
        except Exception as e:
            log.warning("Failed to archive rejected alpha %s: %s", alpha_id, e)

    # ------------------------------------------------------------------
    # Archetype saturation / diversity queries
    # ------------------------------------------------------------------

    def get_recently_submitted_archetypes(self, limit: int = 3) -> List[str]:
        """
        Returns the archetypes of the most recently submitted alphas.
        Used by the drip submitter's diversity ranker to deprioritise
        repeating the same archetype family back-to-back.
        """
        if not self.database_url:
            return []
        sql = """
            SELECT archetype FROM options_alphas
            WHERE status = 'SUBMITTED' AND archetype IS NOT NULL
            ORDER BY submitted_at DESC NULLS LAST, created_at DESC
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
        Dynamic Archetype Quota Enforcer (Pillar 1 of the 5-channel strategy):
        Returns archetypes that have already produced >= max_per_day qualified or
        submitted alphas today. Uses New York calendar date to match BRAIN's day.
        """
        if not self.database_url:
            return []
        sql = """
            SELECT archetype, COUNT(*) as cnt
            FROM options_alphas
            WHERE status IN ('QUALIFIED', 'SUBMITTED')
              AND archetype IS NOT NULL
              AND created_at >= (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date
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

    # ------------------------------------------------------------------
    # options_evaluations — read path
    # ------------------------------------------------------------------

    def load_evaluated_expressions(self) -> Set[str]:
        """
        Returns the complete set of expression strings ever evaluated across all tables.
        Loaded on startup to seed the in-memory ASTDeduplicator so workers never
        re-simulate structurally identical formulas — including expressions that were
        correlated, rejected, or already in the alpha pool.
        """
        if not self.database_url:
            return set()
        exprs: Set[str] = set()
        queries = [
            "SELECT DISTINCT expression FROM options_evaluations WHERE expression IS NOT NULL;",
            "SELECT DISTINCT expression FROM options_correlated_alphas WHERE expression IS NOT NULL;",
            "SELECT DISTINCT expression FROM options_rejected_alphas WHERE expression IS NOT NULL;",
            "SELECT DISTINCT expression FROM options_alphas WHERE expression IS NOT NULL;",
        ]
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for q in queries:
                        try:
                            cur.execute(q)
                            exprs.update(row[0].strip() for row in cur.fetchall() if row[0])
                        except Exception as qe:
                            log.debug("load_evaluated_expressions sub-query skipped: %s", qe)
            log.info("Seeded ASTDeduplicator with %d known expressions from all tables.", len(exprs))
        except Exception as e:
            log.warning("Failed to load evaluated expressions from database: %s", e)
        return exprs

    # ------------------------------------------------------------------
    # options_learning_memory — write path
    # ------------------------------------------------------------------

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
        """
        Upserts a reward-adjusted learning memory entry for the expression.
        Applies anti-correlation and rejection penalties before storing:
          - corr > 0.60: penalty += 12 × (corr - 0.50)
          - status CORRELATED: penalty += 8
          - status REJECTED: penalty += 15
        ON CONFLICT updates all metric fields so the most recent result wins.
        """
        if not self.database_url:
            return

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
             reward, optimization_steps, parent_expression, mutation_type, status, alpha_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (expression) DO UPDATE SET
                sharpe = EXCLUDED.sharpe,
                fitness = EXCLUDED.fitness,
                turnover = EXCLUDED.turnover,
                returns = EXCLUDED.returns,
                drawdown = EXCLUDED.drawdown,
                reward = EXCLUDED.reward,
                optimization_steps = EXCLUDED.optimization_steps,
                status = EXCLUDED.status,
                alpha_id = EXCLUDED.alpha_id,
                updated_at = CURRENT_TIMESTAMP;
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
            log.info(
                "Learning memory updated for %s (Reward=%.2f, Sharpe=%.2f, Status=%s)",
                candidate.expression[:35], adjusted_reward, metrics.sharpe, status,
            )
        except Exception as e:
            log.warning("Failed to record learning memory: %s", e)

    # ------------------------------------------------------------------
    # options_learning_memory — read path
    # ------------------------------------------------------------------

    def load_top_performing_exemplars(
        self,
        limit: int = 5,
        min_sharpe: float = 1.0,
        exclude_archetypes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Loads top-performing alpha expressions from options_learning_memory to use as
        mutation seeds for new candidate generation. Falls back to options_evaluations
        if learning memory is empty (e.g. fresh deployment).
        Excludes archetypes that are already saturated to enforce channel diversity.
        """
        if not self.database_url:
            return []

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

                    # Bootstrap from options_evaluations when learning memory is cold
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

    # ------------------------------------------------------------------
    # MAB archetype performance summary
    # ------------------------------------------------------------------

    def load_archetype_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Loads win rates and average metrics per archetype from options_evaluations
        for Multi-Armed Bandit weight calculation in OptionsGenerator.
        A 'win' = status PASS or Sharpe >= 0.70 (Stage 0 pass threshold).
        """
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

    # ------------------------------------------------------------------
    # Stats / reporting
    # ------------------------------------------------------------------

    def get_options_stats(self) -> Dict[str, Any]:
        """
        Loads daily and all-time pipeline statistics for health checks and daily digests.
        Returns:
          today_evaluated     — total simulations run today across all orgs
          today_stage0_pass   — how many passed Stage 0 screening today
          today_qualified     — new qualified alphas added to pool today
          today_submitted     — alphas submitted to BRAIN today
          today_correlated    — alphas rejected for correlation today
          reserve_count       — unsubmitted alphas currently in options_alphas
          all_time_evaluated  — total simulations ever run
          all_time_stage0_pass — total Stage 0 passes ever
          all_time_pool_alphas — total rows ever in options_alphas
          all_time_correlated  — total alphas in options_correlated_alphas
        """
        if not self.database_url:
            return {}
        stats: Dict[str, Any] = {
            "all_time_evaluated": 0,
            "all_time_stage0_pass": 0,
            "all_time_pool_alphas": 0,
            "today_evaluated": 0,
            "today_stage0_pass": 0,
            "today_qualified": 0,
            "today_submitted": 0,
            "reserve_count": 0,
            "today_correlated": 0,
            "all_time_correlated": 0,
        }
        # All today_* filters use New York calendar date to match BRAIN's submission day.
        ny_today = "(CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date"
        sql_eval = f"""
            SELECT
                COUNT(*) as all_time_evaluated,
                COUNT(*) FILTER (WHERE status = 'PASS' OR LEFT(stage, 5) = 'DIAG_' OR status = 'QUALIFIED') as all_time_pass,
                COUNT(*) FILTER (WHERE created_at >= {ny_today}) as today_evaluated,
                COUNT(*) FILTER (WHERE created_at >= {ny_today} AND (status = 'PASS' OR LEFT(stage, 5) = 'DIAG_')) as today_stage0_pass,
                COUNT(*) FILTER (WHERE created_at >= {ny_today} AND status = 'CORRELATED') as today_correlated
            FROM options_evaluations;
        """
        sql_alphas = f"""
            SELECT
                COUNT(*) as all_time_pool,
                COUNT(*) FILTER (WHERE created_at >= {ny_today}) as today_pool,
                COUNT(*) FILTER (WHERE status = 'SUBMITTED' AND submitted_at >= {ny_today}) as today_submitted,
                COUNT(*) FILTER (WHERE status = 'QUALIFIED') as reserve_count
            FROM options_alphas;
        """
        sql_corr = "SELECT COUNT(*) FROM options_correlated_alphas;"
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
                        stats["today_correlated"] = int(row[4] or 0)

                    cur.execute(sql_alphas)
                    row_a = cur.fetchone()
                    if row_a:
                        stats["all_time_pool_alphas"] = int(row_a[0] or 0)
                        stats["today_qualified"] = int(row_a[1] or 0)
                        stats["today_submitted"] = int(row_a[2] or 0)
                        stats["reserve_count"] = int(row_a[3] or 0)

                    try:
                        cur.execute(sql_corr)
                        row_c = cur.fetchone()
                        if row_c:
                            stats["all_time_correlated"] = int(row_c[0] or 0)
                    except Exception:
                        pass

            return stats
        except Exception as e:
            log.warning("Failed to load options stats: %s", e)
            return stats

    # ------------------------------------------------------------------
    # Stage 0 re-optimizer feed
    # ------------------------------------------------------------------

    def get_stage0_passed_candidates(self, limit: int = 100) -> List[OptionCandidate]:
        """
        Loads distinct candidates from options_evaluations that passed Stage 0 screening
        (Sharpe >= 0.35, Fitness >= 0.20) but were never fully optimised, for the
        --retry-stage0 pipeline mode. Excludes any already in options_alphas
        or already through a full retry/optimization cycle.
        """
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
        except Exception as e:
            log.warning("Failed to load stage0 passed candidates: %s", e)
        return candidates

    # ------------------------------------------------------------------
    # org_runs — multi-org heartbeat tracking
    # ------------------------------------------------------------------

    def record_org_run(
        self,
        org_name: str,
        archetype: str = "",
        evals_done: int = 0,
        qualified: int = 0,
    ):
        """
        Writes a heartbeat row for an org run. Called at the start (evals_done=0)
        and optionally updated at the end with actual counts. Provides proof of
        which orgs are actually firing, independent of the cluster run lock.
        """
        if not self.database_url:
            return
        sql = """
            INSERT INTO org_runs (org_name, archetype, evals_done, qualified)
            VALUES (%s, %s, %s, %s);
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (org_name, archetype or "", evals_done, qualified))
                conn.commit()
            log.info("Org run heartbeat recorded: %s (arch=%s)", org_name, archetype)
        except Exception as e:
            log.debug("Failed to record org run heartbeat: %s", e)

    def get_org_activity(self, hours: int = 26) -> List[Dict[str, Any]]:
        """
        Returns summary of org activity in the last `hours` hours.
        Used by health check to report: 'Orgs active last 24h: 2/4'.
        """
        if not self.database_url:
            return []
        sql = """
            SELECT org_name,
                   COUNT(*) as run_count,
                   MAX(run_at) as last_seen,
                   SUM(evals_done) as total_evals,
                   SUM(qualified) as total_qualified
            FROM org_runs
            WHERE run_at >= NOW() - (%s * INTERVAL '1 hour')
            GROUP BY org_name
            ORDER BY last_seen DESC;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (hours,))
                    return [
                        {
                            "org": row[0],
                            "runs": int(row[1] or 0),
                            "last_seen": str(row[2])[:16] if row[2] else "never",
                            "evals": int(row[3] or 0),
                            "qualified": int(row[4] or 0),
                        }
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            log.warning("Failed to load org activity: %s", e)
            return []

    # ------------------------------------------------------------------
    # cluster_session_cache
    # ------------------------------------------------------------------

    def get_cached_session(self, key: str = "brain_session") -> Optional[Dict[str, Any]]:
        """
        Retrieves a valid BRAIN session from the shared cluster cache.
        Returns None if no valid (non-expired) session exists.
        All 5 orgs (4 workers + drip) share one session entry to avoid
        repeated login calls which can trigger BRAIN rate limiting.
        """
        if not self.database_url:
            return None
        sql = """
            SELECT token, cookies, expires_at FROM cluster_session_cache
            WHERE key = %s AND expires_at > CURRENT_TIMESTAMP + INTERVAL '10 minutes';
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
        """
        Saves a fresh BRAIN session token + cookies to the cluster cache with a 2-hour TTL.
        Uses ON CONFLICT upsert so concurrent orgs safely overwrite stale sessions.
        """
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
            log.info("Saved BRAIN session to cluster cache (TTL=%ds).", expires_in_seconds)
        except Exception as e:
            log.warning("Failed to save session cache: %s", e)

    # ------------------------------------------------------------------
    # cluster_run_lock
    # ------------------------------------------------------------------

    def acquire_cluster_lock(
        self,
        org_name: str,
        worker_id: str,
        archetype: str = "",
        timeout_seconds: int = 900,
    ) -> bool:
        """
        Acquires the cluster-wide run mutex for this worker org. Only one worker
        can hold the lock at a time, enforcing the BRAIN platform's 3 concurrent
        simulation limit across the entire cluster.
        Stale locks (heartbeat > 15 minutes old) are cleaned up before attempting.
        Returns True if lock acquired, False if another worker is already running.
        On DB error, returns False (fail closed) to prevent multi-worker collisions.
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
            log.warning("Failed to acquire cluster run lock (failing closed): %s", e)
            return False  # Fail closed: never simulate without a verified lock

    def touch_cluster_lock(self, worker_id: str) -> bool:
        """
        Updates the in-flight heartbeat timestamp for this worker to prevent
        stale lock eviction during long-running discovery batches (> 15 minutes).
        Returns True if heartbeat was refreshed, False otherwise.
        """
        if not self.database_url:
            return True
        sql = "UPDATE cluster_run_lock SET heartbeat = CURRENT_TIMESTAMP WHERE worker_id = %s RETURNING worker_id;"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (worker_id,))
                    res = cur.fetchone()
                conn.commit()
            return res is not None
        except Exception as e:
            log.debug("Failed to touch cluster run lock heartbeat: %s", e)
            return False

    def release_cluster_lock(self, worker_id: str):
        """Releases the cluster run mutex immediately after batch completion."""
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

    # ------------------------------------------------------------------
    # options_learning_memory — penalty path
    # ------------------------------------------------------------------

    def penalize_learning_memory(self, target: str, penalty: float = -10.0, reason: str = ""):
        """
        Caps the reward of an expression (or the expression of an alpha_id) in
        learning memory to the penalty value and marks it REJECTED.
        Called when an alpha is rejected for correlation or platform gate failure
        so the generator avoids mutating this branch in future discovery cycles.
        """
        if not self.database_url or not target:
            return
        sql = """
            UPDATE options_learning_memory
            SET reward = LEAST(reward, %s),
                status = 'REJECTED',
                updated_at = CURRENT_TIMESTAMP
            WHERE expression = %s
               OR expression IN (SELECT expression FROM options_alphas WHERE alpha_id = %s);
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (penalty, target, target))
                conn.commit()
            log.info(
                "Penalised learning memory for %s (reward capped at %.2f, reason=%s).",
                target[:35], penalty, reason,
            )
        except Exception as e:
            log.warning("Failed to penalise learning memory: %s", e)


# ---------------------------------------------------------------------------
# Archetype normalisation utility
# ---------------------------------------------------------------------------

def map_archetype_to_core(archetype_name: str) -> str:
    """
    Normalises arbitrary archetype labels (from LLM output, mutation tags, etc.)
    to the canonical 8-key taxonomy used throughout the pipeline:
      breakeven, skew, term_structure, forward_basis, pcr_flow,
      analyst_revisions, short_interest, hybrid_confluence
    """
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
