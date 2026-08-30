"""baseline schema

Revision ID: 93b626538c0e
Revises:
Create Date: 2026-08-26 07:05:54.326992

Update 10 Item 6: this is the single baseline migration reproducing the
exact schema pipeline/db/schema.sql produces (the pre-Alembic
CREATE-TABLE-IF-NOT-EXISTS-plus-bolted-on-ALTERs approach), verified by
diffing the "pg_dump --schema-only" output between a fresh DB migrated
via `alembic upgrade head` and a fresh DB migrated via the old
`Repo.migrate()` (schema.sql execution) -- see the Update 10 final report
for the actual diff command and output. `schema.sql` itself is left in
the repo unmodified as a historical/legacy artifact and reference, but
`Repo.migrate()` no longer executes it -- see that method's docstring.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93b626538c0e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema -- reproduces pipeline/db/schema.sql's end state
    exactly (final column set, including every column added via a later
    ALTER TABLE ... ADD COLUMN IF NOT EXISTS in that file), as one
    idempotent baseline revision."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id              BIGSERIAL PRIMARY KEY,
            expression      TEXT NOT NULL,
            category        TEXT,
            generation_tier TEXT,
            provider        TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            claimed_at      TIMESTAMPTZ,
            stage0_fitness  NUMERIC,
            stage0_sharpe   NUMERIC,
            status          TEXT NOT NULL DEFAULT 'pending',
            attempts        INTEGER NOT NULL DEFAULT 0,
            last_error      TEXT
        )
    """)
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS provider TEXT")
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS last_error TEXT")

    op.execute("""
        CREATE TABLE IF NOT EXISTS sweep_runs (
            id              BIGSERIAL PRIMARY KEY,
            candidate_id    BIGINT NOT NULL REFERENCES candidates(id),
            stage           TEXT NOT NULL,
            delay           SMALLINT,
            universe        TEXT,
            neutralization  TEXT,
            decay           SMALLINT,
            truncation      NUMERIC,
            pasteurization  BOOLEAN,
            nan_handling    BOOLEAN,
            sharpe          NUMERIC,
            fitness         NUMERIC,
            turnover        NUMERIC,
            returns_ann     NUMERIC,
            drawdown        NUMERIC,
            simulated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            error_text      TEXT
        )
    """)
    op.execute("ALTER TABLE sweep_runs ADD COLUMN IF NOT EXISTS error_text TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sweep_runs_candidate ON sweep_runs(candidate_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS review_store (
            id                   BIGSERIAL PRIMARY KEY,
            candidate_id         BIGINT NOT NULL REFERENCES candidates(id),
            expression           TEXT NOT NULL,
            region               TEXT NOT NULL DEFAULT 'USA',
            instrument_type      TEXT NOT NULL DEFAULT 'EQUITY',
            delay                SMALLINT NOT NULL,
            universe             TEXT NOT NULL,
            neutralization       TEXT NOT NULL,
            decay                SMALLINT NOT NULL,
            truncation           NUMERIC NOT NULL,
            pasteurization       BOOLEAN NOT NULL,
            nan_handling         BOOLEAN NOT NULL,
            sharpe               NUMERIC NOT NULL,
            fitness              NUMERIC NOT NULL,
            turnover             NUMERIC NOT NULL,
            max_correlation      NUMERIC NOT NULL,
            robust_count         SMALLINT NOT NULL,
            sweep_total          SMALLINT NOT NULL,
            fragile              BOOLEAN NOT NULL,
            telegram_sent_at     TIMESTAMPTZ,
            submitted            BOOLEAN NOT NULL DEFAULT false,
            submitted_at         TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_review_store_fitness ON review_store(fitness DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_review_store_correlation ON review_store(max_correlation ASC)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS pool_returns (
            alpha_id     TEXT NOT NULL,
            return_date  DATE NOT NULL,
            daily_return NUMERIC NOT NULL,
            PRIMARY KEY (alpha_id, return_date)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id           BIGSERIAL PRIMARY KEY,
            provider     TEXT NOT NULL,
            key_label    TEXT NOT NULL,
            tier         TEXT NOT NULL,
            called_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            succeeded    BOOLEAN NOT NULL,
            error_text   TEXT
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_meta (
            key          TEXT PRIMARY KEY,
            value        TEXT,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS run_history (
            id                    BIGSERIAL PRIMARY KEY,
            started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            reclaimed             INTEGER,
            queue_depth_before    INTEGER,
            candidates_generated  INTEGER,
            candidates_processed  INTEGER,
            rejected_stage0       INTEGER,
            rejected_filter       INTEGER,
            rejected_correlation  INTEGER,
            rejected_error        INTEGER,
            passed                INTEGER,
            stopped_reason        TEXT,
            brain_auth_ok         BOOLEAN,
            errors                TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_run_history_started_at ON run_history(started_at DESC)")


def downgrade() -> None:
    """Downgrade schema -- drops every table this baseline created, in
    FK-safe dependency order (tables referencing candidates.id first)."""
    op.execute("DROP TABLE IF EXISTS run_history")
    op.execute("DROP TABLE IF EXISTS pipeline_meta")
    op.execute("DROP TABLE IF EXISTS llm_usage")
    op.execute("DROP TABLE IF EXISTS pool_returns")
    op.execute("DROP TABLE IF EXISTS review_store")
    op.execute("DROP TABLE IF EXISTS sweep_runs")
    op.execute("DROP TABLE IF EXISTS candidates")
