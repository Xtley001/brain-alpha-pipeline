"""
Tests for database migrations and Repo.migrate().
Verifies that all DDL statements in Alembic baseline schema are idempotent
(using IF NOT EXISTS) so that startup does not fail with psycopg.errors.DuplicateTable
when connecting to a pre-existing database.
"""
import importlib
from unittest.mock import MagicMock, patch

import pytest

from pipeline.db.repo import Repo

baseline_migration = importlib.import_module("pipeline.db.alembic.versions.93b626538c0e_baseline_schema")


def test_baseline_migration_is_idempotent():
    """Verify that all CREATE TABLE and CREATE INDEX statements executed in the
    baseline migration use IF NOT EXISTS, and all added columns use IF NOT EXISTS."""
    executed_statements = []

    with patch.object(baseline_migration.op, "execute", side_effect=lambda stmt: executed_statements.append(stmt)):
        baseline_migration.upgrade()

    assert len(executed_statements) > 0

    for stmt in executed_statements:
        clean = " ".join(stmt.strip().split())
        upper = clean.upper()

        if "CREATE TABLE" in upper:
            assert "CREATE TABLE IF NOT EXISTS" in upper, f"CREATE TABLE missing IF NOT EXISTS: {clean}"

        if "CREATE INDEX" in upper:
            assert "CREATE INDEX IF NOT EXISTS" in upper, f"CREATE INDEX missing IF NOT EXISTS: {clean}"

        if "ADD COLUMN" in upper:
            assert "ADD COLUMN IF NOT EXISTS" in upper, f"ADD COLUMN missing IF NOT EXISTS: {clean}"


def test_repo_migrate_runs_alembic_upgrade_head():
    """Verify Repo.migrate sets up alembic config and calls upgrade head."""
    repo = Repo("postgresql://user:pass@localhost:5432/testdb")

    with patch("alembic.command.upgrade") as mock_upgrade:
        repo.migrate()
        mock_upgrade.assert_called_once()
        alembic_cfg, target = mock_upgrade.call_args[0]
        assert target == "head"
        assert "postgresql+psycopg://" in alembic_cfg.get_main_option("sqlalchemy.url")
