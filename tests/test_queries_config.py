# tests/test_queries_config.py
# Unit tests for ConfigQueries.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_value(mock_db):
    mock_db.execute.return_value = {"value": "hello"}

    result = await mock_db.config.get("my_key")

    assert result == "hello"


@pytest.mark.asyncio
async def test_get_returns_default_when_missing(mock_db):
    mock_db.execute.return_value = None

    result = await mock_db.config.get("missing_key", default="fallback")

    assert result == "fallback"


@pytest.mark.asyncio
async def test_get_returns_none_default_when_not_set(mock_db):
    mock_db.execute.return_value = None

    result = await mock_db.config.get("missing_key")

    assert result is None


# ---------------------------------------------------------------------------
# set()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_calls_upsert(mock_db):
    mock_db.execute.return_value = None

    await mock_db.config.set("my_key", "new_value")

    mock_db.execute.assert_called_once()
    sql, params = mock_db.execute.call_args[0]
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert params == ("my_key", "new_value")


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_calls_execute(mock_db):
    mock_db.execute.return_value = None

    await mock_db.config.delete("my_key")

    mock_db.execute.assert_called_once()
    sql, params = mock_db.execute.call_args[0]
    assert "DELETE" in sql
    assert params == ("my_key",)


# ---------------------------------------------------------------------------
# get_int()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_int_converts_string_to_int(mock_db):
    mock_db.execute.return_value = {"value": "42"}

    result = await mock_db.config.get_int("counter")

    assert result == 42


@pytest.mark.asyncio
async def test_get_int_returns_default_when_missing(mock_db):
    mock_db.execute.return_value = None

    result = await mock_db.config.get_int("counter", default=99)

    assert result == 99


@pytest.mark.asyncio
async def test_get_int_default_zero(mock_db):
    mock_db.execute.return_value = None

    result = await mock_db.config.get_int("counter")

    assert result == 0


# ---------------------------------------------------------------------------
# increment()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_increment_returns_new_value(mock_db):
    cur = _mock_increment_cursor(mock_db, value=6)

    result = await mock_db.config.increment("counter")

    assert result == 6
    assert cur.execute.await_count == 2
    sql, params = cur.execute.await_args_list[0].args
    assert "LAST_INSERT_ID" in sql
    assert params == ("counter", 1, 1)


@pytest.mark.asyncio
async def test_increment_by_custom_amount(mock_db):
    cur = _mock_increment_cursor(mock_db, value=10)

    result = await mock_db.config.increment("counter", by=5)

    assert result == 10
    insert_args = cur.execute.await_args_list[0].args
    assert insert_args[1] == ("counter", 5, 5)


@pytest.mark.asyncio
async def test_increment_default_step_is_one(mock_db):
    cur = _mock_increment_cursor(mock_db, value=1)

    await mock_db.config.increment("counter")

    insert_args = cur.execute.await_args_list[0].args
    assert insert_args[1] == ("counter", 1, 1)


def _mock_increment_cursor(mock_db, value: int):
    conn = MagicMock()
    cur = AsyncMock()
    mock_db.pool.acquire.return_value.__aenter__.return_value = conn
    conn.cursor.return_value.__aenter__.return_value = cur
    cur.fetchone.return_value = (value,)
    return cur
