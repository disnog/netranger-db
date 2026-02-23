# tests/test_migrations_runner.py
# Unit tests for migration runner transactional behavior.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from netranger_db.migrations.runner import MigrationRunner


def _build_runner():
    db = MagicMock()
    conn = MagicMock()
    conn.begin = AsyncMock()
    conn.commit = AsyncMock()
    conn.rollback = AsyncMock()
    cur = AsyncMock()

    db.pool.acquire.return_value.__aenter__.return_value = conn
    conn.cursor.return_value.__aenter__.return_value = cur

    return MigrationRunner(db), conn, cur


@pytest.mark.asyncio
async def test_apply_migration_commits_on_success(tmp_path):
    runner, conn, cur = _build_runner()
    sql_file = tmp_path / "001_initial.sql"
    sql_file.write_text(
        "CREATE TABLE a (id INT); CREATE TABLE b (id INT);",
        encoding="utf-8",
    )

    await runner.apply_migration(1, "initial", sql_file)

    conn.begin.assert_awaited_once()
    conn.commit.assert_awaited_once()
    conn.rollback.assert_not_awaited()

    executed_sql = [call.args[0] for call in cur.execute.await_args_list]
    assert "CREATE TABLE a (id INT)" in executed_sql
    assert "CREATE TABLE b (id INT)" in executed_sql
    assert any("INSERT INTO _migrations" in stmt for stmt in executed_sql)


@pytest.mark.asyncio
async def test_apply_migration_rolls_back_on_failure(tmp_path):
    runner, conn, cur = _build_runner()
    sql_file = tmp_path / "002_broken.sql"
    sql_file.write_text(
        "CREATE TABLE a (id INT); CREATE TABLE broken (id INT);",
        encoding="utf-8",
    )

    async def _execute_side_effect(statement, *_args, **_kwargs):
        if "CREATE TABLE broken" in statement:
            raise RuntimeError("boom")
        return None

    cur.execute.side_effect = _execute_side_effect

    with pytest.raises(RuntimeError, match="boom"):
        await runner.apply_migration(2, "broken", sql_file)

    conn.begin.assert_awaited_once()
    conn.rollback.assert_awaited_once()
    conn.commit.assert_not_awaited()

    executed_sql = [call.args[0] for call in cur.execute.await_args_list]
    assert not any("INSERT INTO _migrations" in stmt for stmt in executed_sql)
