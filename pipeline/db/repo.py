"""
Data access layer over Neon Postgres, matching pipeline/db/schema.sql
exactly. Business logic (sweep, filter, correlation, generator) never
writes raw SQL directly -- it calls methods here.

`psycopg` / `psycopg_pool` are imported lazily so importing this module
(and running the rest of the test suite) never requires a real database
connection or those packages installed.

Connections are checked out of a `psycopg_pool.ConnectionPool` (opened once,
lazily, on first use) rather than opened fresh per call -- see the code
review's §3.1: at low candidate throughput a fresh `psycopg.connect(...)`
per method call is harmless, but it becomes a real bottleneck (connection
setup latency, and eventually Neon's connection-limit) the moment
`BRAIN_MAX_CONCURRENT_SIMS` or `QUEUE_TARGET_DEPTH` is raised.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class Repo:
    def __init__(self, database_url: str, pool_min_size: int = 1, pool_max_size: int = 10):
        self.database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._pool = None  # lazily created ConnectionPool; see _get_pool()

    def _get_pool(self):
        if self._pool is None:
            from psycopg_pool import ConnectionPool  # lazy import

            # open=True eagerly establishes the min-size connections instead
            # of deferring to first checkout, so a bad DATABASE_URL fails
            # fast at startup rather than on the first query.
            self._pool = ConnectionPool(
                self.database_url,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                open=True,
            )
        return self._pool

    def close(self) -> None:
        """Close the pool. Call on graceful shutdown; safe to call even if
        the pool was never opened."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    @contextmanager
    def _conn(self):
        pool = self._get_pool()
        with pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def migrate(self) -> None:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            ddl = f.read()
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)

    # --- candidates ---

    def insert_candidate(self, expression: str, category: Optional[str], generation_tier: str) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO candidates (expression, category, generation_tier) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (expression, category, generation_tier),
                )
                return cur.fetchone()[0]

    def queue_depth(self) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM candidates WHERE status = 'pending'")
                return cur.fetchone()[0]

    def claim_next_pending(self) -> Optional[dict]:
        """Atomically claim the oldest pending candidate by flipping it to
        'running', so two worker instances (or a restart mid-run) can't both
        grab the same row. Returns None if the queue is empty."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET status = 'running', claimed_at = now() "
                    "WHERE id = ("
                    "  SELECT id FROM candidates WHERE status = 'pending' "
                    "  ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                    ") RETURNING id, expression, category, generation_tier"
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return {"id": row[0], "expression": row[1], "category": row[2], "generation_tier": row[3]}

    def set_candidate_status(self, candidate_id: int, status: str, stage0_fitness=None, stage0_sharpe=None) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET status = %s, "
                    "stage0_fitness = COALESCE(%s, stage0_fitness), "
                    "stage0_sharpe = COALESCE(%s, stage0_sharpe) "
                    "WHERE id = %s",
                    (status, stage0_fitness, stage0_sharpe, candidate_id),
                )

    def reclaim_orphaned_running(self, older_than_minutes: int = 30) -> int:
        """On worker startup: any candidate stuck in 'running' from a crash/
        restart gets put back to 'pending' rather than orphaned forever
        (see the audit checklist).

        Keyed off `claimed_at` (set the moment a candidate flips to
        'running' in `claim_next_pending`), not `created_at` (set once at
        insertion). Keying off `created_at` would incorrectly reclaim
        genuinely in-progress candidates that simply sat 'pending' in a
        deep queue for a while before being claimed -- see the code
        review's §1.3."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET status = 'pending' "
                    "WHERE status = 'running' "
                    "AND claimed_at < now() - (%s || ' minutes')::interval",
                    (str(older_than_minutes),),
                )
                return cur.rowcount

    # --- sweep_runs ---

    def insert_sweep_run(self, candidate_id: int, stage: str, settings, result) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sweep_runs (candidate_id, stage, delay, universe, "
                    "neutralization, decay, truncation, pasteurization, nan_handling, "
                    "sharpe, fitness, turnover, returns_ann, drawdown) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (
                        candidate_id, stage, settings.delay, settings.universe,
                        settings.neutralization, settings.decay, settings.truncation,
                        settings.pasteurization, settings.nan_handling,
                        result.sharpe, result.fitness, result.turnover,
                        result.returns_ann, result.drawdown,
                    ),
                )
                return cur.fetchone()[0]

    def insert_sweep_run_error(self, candidate_id: int, stage: str, settings, error_text: str) -> int:
        """Records an *attempted* combo that failed to simulate -- error_text
        set, every metric column left NULL (Update 04 fault isolation; see
        SweepRun.ok in pipeline/sweep/settings_sweep.py). This is what keeps
        one bad combo from silently vanishing from the data the way an
        unhandled exception would have."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sweep_runs (candidate_id, stage, delay, universe, "
                    "neutralization, decay, truncation, pasteurization, nan_handling, error_text) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (
                        candidate_id, stage, settings.delay, settings.universe,
                        settings.neutralization, settings.decay, settings.truncation,
                        settings.pasteurization, settings.nan_handling, error_text,
                    ),
                )
                return cur.fetchone()[0]

    def record_candidate_error(self, candidate_id: int, error_text: str, max_attempts: int) -> tuple[str, int]:
        """Atomically increments `attempts` and flips `status` to
        'rejected_error' once `max_attempts` is reached, else back to
        'pending' so the next tick can retry it. Returns (new_status,
        attempts) so the caller (Worker._record_candidate_error) knows
        whether this was the final, alert-worthy failure or just a
        transient hiccup worth retrying quietly (Update 04)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE candidates SET attempts = attempts + 1, last_error = %s, "
                    "status = CASE WHEN attempts + 1 >= %s THEN 'rejected_error' ELSE 'pending' END "
                    "WHERE id = %s RETURNING status, attempts",
                    (error_text, max_attempts, candidate_id),
                )
                status, attempts = cur.fetchone()
                return status, attempts

    def count_sweep_runs(self, candidate_id: int, stage: str) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM sweep_runs WHERE candidate_id = %s AND stage = %s",
                    (candidate_id, stage),
                )
                return cur.fetchone()[0]

    # --- review_store ---

    def insert_review_store(self, row: dict) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO review_store (candidate_id, expression, delay, universe, "
                    "neutralization, decay, truncation, pasteurization, nan_handling, "
                    "sharpe, fitness, turnover, max_correlation, robust_count, sweep_total, "
                    "fragile) VALUES (%(candidate_id)s, %(expression)s, %(delay)s, %(universe)s, "
                    "%(neutralization)s, %(decay)s, %(truncation)s, %(pasteurization)s, "
                    "%(nan_handling)s, %(sharpe)s, %(fitness)s, %(turnover)s, "
                    "%(max_correlation)s, %(robust_count)s, %(sweep_total)s, %(fragile)s) "
                    "RETURNING id",
                    row,
                )
                return cur.fetchone()[0]

    def mark_telegram_sent(self, review_store_id: int) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE review_store SET telegram_sent_at = now() WHERE id = %s",
                    (review_store_id,),
                )

    def ranked_review_store(self, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT expression, sharpe, fitness, turnover, max_correlation, "
                    "universe, delay, neutralization, decay, truncation, pasteurization, "
                    "nan_handling, robust_count, sweep_total, fragile, submitted "
                    "FROM review_store WHERE submitted = false "
                    "ORDER BY fitness DESC, max_correlation ASC LIMIT %s",
                    (limit,),
                )
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    # --- pool_returns ---

    def get_pool_returns(self) -> dict:
        """Returns {alpha_id: {date_str: daily_return}} for correlation
        checks."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT alpha_id, return_date, daily_return FROM pool_returns")
                out: dict = {}
                for alpha_id, return_date, daily_return in cur.fetchall():
                    out.setdefault(alpha_id, {})[str(return_date)] = float(daily_return)
                return out

    def upsert_pool_returns(self, alpha_id: str, series: dict) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                for date_str, ret in series.items():
                    cur.execute(
                        "INSERT INTO pool_returns (alpha_id, return_date, daily_return) "
                        "VALUES (%s, %s, %s) "
                        "ON CONFLICT (alpha_id, return_date) DO UPDATE SET daily_return = EXCLUDED.daily_return",
                        (alpha_id, date_str, ret),
                    )
        self.set_meta("pool_returns_last_refreshed", datetime.now(timezone.utc).isoformat())

    # --- llm_usage ---

    def log_llm_usage(self, provider: str, key_label: str, tier: str, succeeded: bool, error_text: Optional[str]) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO llm_usage (provider, key_label, tier, succeeded, error_text) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (provider, key_label, tier, succeeded, error_text),
                )

    def recent_llm_key_health(self, max_age_minutes: int = 120) -> list[dict]:
        """Most-recent success/failure per (provider, key_label) -- what the
        heartbeat (Update 01 P1.1) surfaces so 'is the LLM tier even
        working' stops being invisible in llm_usage forever. DISTINCT ON
        picks each key's single latest row, ordered by recency.

        Update 05: also flags `stale` (no attempt within `max_age_minutes`)
        and includes a rolling `succeeded_last_10`/`attempted_last_10` so a
        key isn't judged by a single call. Without this, a key's ❌ from
        the very first cold-start tick would render identically to a
        genuinely-failing-right-now key forever, because nothing ever
        overwrites a stale row once the LLM tiers stop being called (see
        run_worker.py's template_tier_max_share fix for the other half of
        that bug)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT ON (provider, key_label) "
                    "provider, key_label, tier, called_at, succeeded, error_text, "
                    "(now() - called_at) > (%s || ' minutes')::interval AS stale "
                    "FROM llm_usage ORDER BY provider, key_label, called_at DESC",
                    (max_age_minutes,),
                )
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                for row in rows:
                    cur.execute(
                        "SELECT succeeded FROM llm_usage WHERE provider = %s AND key_label = %s "
                        "ORDER BY called_at DESC LIMIT 10",
                        (row["provider"], row["key_label"]),
                    )
                    recent = [r[0] for r in cur.fetchall()]
                    row["attempted_last_10"] = len(recent)
                    row["succeeded_last_10"] = sum(1 for s in recent if s)
                return rows

    # --- feedback engine (Update 05) ---
    #
    # Everything below reads data that already exists in `candidates` /
    # `review_store` -- no schema migration needed. This is what closes the
    # loop the pipeline never had: which categories/tiers actually clear the
    # bar, what's been tried and failed recently, and what the LLM has
    # already proposed (so it isn't re-proposing, and re-billing tokens for,
    # the same idea tick after tick).

    def category_performance(self, min_attempts: int = 1) -> list[dict]:
        """Attempts/passes/avg stage0 metrics per (category, generation_tier),
        straight off `candidates`. Feeds template-tier selection weighting
        and the real `_pool_summary()` prompt context."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT category, generation_tier, "
                    "COUNT(*) FILTER (WHERE status = ANY(%s)) AS attempts, "
                    "COUNT(*) FILTER (WHERE status = 'passed') AS passed, "
                    "AVG(stage0_fitness) FILTER (WHERE stage0_fitness IS NOT NULL) AS avg_stage0_fitness, "
                    "AVG(stage0_sharpe) FILTER (WHERE stage0_sharpe IS NOT NULL) AS avg_stage0_sharpe "
                    "FROM candidates GROUP BY category, generation_tier "
                    "HAVING COUNT(*) FILTER (WHERE status = ANY(%s)) >= %s "
                    "ORDER BY passed DESC, attempts DESC",
                    (
                        ["passed", "rejected_stage0", "rejected_filter", "rejected_correlation", "rejected_error"],
                        ["passed", "rejected_stage0", "rejected_filter", "rejected_correlation", "rejected_error"],
                        min_attempts,
                    ),
                )
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def category_quality(self) -> list[dict]:
        """Post-sweep quality (real fitness/sharpe/correlation from
        review_store, not just the stage0 gate) per (category,
        generation_tier) -- the signal that actually matters once a
        candidate has cleared stage0."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT c.category, c.generation_tier, COUNT(rs.id) AS reviewed, "
                    "AVG(rs.fitness) AS avg_fitness, AVG(rs.sharpe) AS avg_sharpe, "
                    "AVG(rs.max_correlation) AS avg_max_correlation, "
                    "AVG(CASE WHEN rs.fragile THEN 1.0 ELSE 0.0 END) AS fragile_rate "
                    "FROM candidates c JOIN review_store rs ON rs.candidate_id = c.id "
                    "GROUP BY c.category, c.generation_tier ORDER BY avg_fitness DESC"
                )
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def recent_rejections(self, limit: int = 10) -> list[dict]:
        """Most recent terminal rejections, for the LLM's `failure_log`
        prompt context (previously a hardcoded stub -- see
        Worker._recent_failure_log)."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT expression, category, status, stage0_sharpe, stage0_fitness, last_error "
                    "FROM candidates WHERE status IN "
                    "('rejected_stage0','rejected_filter','rejected_correlation','rejected_error') "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    def recent_llm_expressions(self, limit: int = 50) -> list[str]:
        """Expressions the LLM tiers have already proposed recently, so
        propose_new_ideas() can be told 'don't repeat these' instead of
        silently re-spending tokens (and a sweep slot) on an idea it already
        gave us. Update 05 -- there was no dedup signal of any kind before
        this; the reasoning prompt never saw its own prior output."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT expression FROM candidates "
                    "WHERE generation_tier IN ('llm_gemini','llm_groq') "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                return [r[0] for r in cur.fetchall()]

    def expression_exists(self, expression: str) -> bool:
        """Exact-match dedup check before inserting a candidate. Cheap
        insurance against the LLM (or a template cycle) re-submitting an
        expression already sitting in the queue/pool -- wasted tokens on
        the LLM side, wasted a BRAIN simulation slot on the template side."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM candidates WHERE expression = %s LIMIT 1", (expression,))
                return cur.fetchone() is not None

    def top_alphas(self, limit: int = 10) -> list[dict]:
        """Ranked leaderboard for a `/top` Telegram surface -- everything
        needed already lives in review_store, this was just never queried."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT rs.expression, c.category, c.generation_tier, rs.fitness, rs.sharpe, "
                    "rs.turnover, rs.max_correlation, rs.robust_count, rs.sweep_total, rs.created_at "
                    "FROM review_store rs JOIN candidates c ON c.id = rs.candidate_id "
                    "ORDER BY rs.fitness DESC LIMIT %s",
                    (limit,),
                )
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]

    # --- run_history ---

    def insert_run_history(self, row: dict) -> int:
        """One row per Worker.run_once() invocation -- see schema.sql's
        run_history table comment (Update 01 P1.1 / Update 02 P1.2). Written
        unconditionally, same as the heartbeat Telegram message, from the
        same RunSummary data so the two can never drift apart."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO run_history (reclaimed, queue_depth_before, "
                    "candidates_generated, candidates_processed, rejected_stage0, "
                    "rejected_filter, rejected_correlation, rejected_error, passed, "
                    "stopped_reason, brain_auth_ok, errors) "
                    "VALUES (%(reclaimed)s, %(queue_depth_before)s, %(candidates_generated)s, "
                    "%(candidates_processed)s, %(rejected_stage0)s, %(rejected_filter)s, "
                    "%(rejected_correlation)s, %(rejected_error)s, %(passed)s, "
                    "%(stopped_reason)s, %(brain_auth_ok)s, %(errors)s) RETURNING id",
                    row,
                )
                return cur.fetchone()[0]

    # --- pipeline_meta ---

    def set_meta(self, key: str, value: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO pipeline_meta (key, value, updated_at) VALUES (%s, %s, now()) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                    (key, value),
                )

    def get_meta(self, key: str) -> Optional[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM pipeline_meta WHERE key = %s", (key,))
                row = cur.fetchone()
                return row[0] if row else None
