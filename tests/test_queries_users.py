# tests/test_queries_users.py
# Unit tests for UserQueries.

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from netranger_db.queries.users import User

# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_user_with_roles(mock_db, sample_user_row, sample_role_rows):
    mock_db.execute.side_effect = [sample_user_row, sample_role_rows]

    user = await mock_db.users.get(123456789)

    assert isinstance(user, User)
    assert user.id == 123456789
    assert user.name == "testuser"
    assert user.discriminator == "1234"
    assert user.member_number == 42
    assert user.permanent_roles == ["Member"]


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_user(mock_db):
    mock_db.execute.return_value = None

    user = await mock_db.users.get(999)

    assert user is None


@pytest.mark.asyncio
async def test_get_user_no_roles(mock_db, sample_user_row):
    mock_db.execute.side_effect = [sample_user_row, []]

    user = await mock_db.users.get(123456789)

    assert user.permanent_roles == []


# ---------------------------------------------------------------------------
# upsert()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_calls_execute_with_correct_params(mock_db):
    mock_db.execute.return_value = None
    joined = datetime(2023, 1, 1)

    await mock_db.users.upsert(123456789, "testuser", "1234", "Nick", joined)

    mock_db.execute.assert_called_once()
    args = mock_db.execute.call_args
    assert 123456789 in args[0][1]
    assert "testuser" in args[0][1]


@pytest.mark.asyncio
async def test_upsert_without_optional_fields(mock_db):
    mock_db.execute.return_value = None

    await mock_db.users.upsert(1, "minimal")

    mock_db.execute.assert_called_once()


# ---------------------------------------------------------------------------
# add_permanent_role() / remove_permanent_role() / has_permanent_role()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_permanent_role(mock_db):
    mock_db.execute.return_value = None

    await mock_db.users.add_permanent_role(123456789, "Member")

    mock_db.execute.assert_called_once()
    sql, params = mock_db.execute.call_args[0]
    assert "INSERT IGNORE" in sql
    assert params == (123456789, "Member")


@pytest.mark.asyncio
async def test_remove_permanent_role(mock_db):
    mock_db.execute.return_value = None

    await mock_db.users.remove_permanent_role(123456789, "Member")

    mock_db.execute.assert_called_once()
    sql, params = mock_db.execute.call_args[0]
    assert "DELETE" in sql
    assert params == (123456789, "Member")


@pytest.mark.asyncio
async def test_set_permanent_roles_replaces_roles_transactionally(mock_db):
    conn, cur = _mock_transaction_cursor(mock_db)

    await mock_db.users.set_permanent_roles(
        123456789,
        ["Member", "recruiter", "Member"],
    )

    conn.begin.assert_awaited_once()
    conn.commit.assert_awaited_once()
    conn.rollback.assert_not_awaited()
    cur.execute.assert_awaited_once()
    cur.executemany.assert_awaited_once()
    _, params = cur.executemany.await_args.args
    assert params == [(123456789, "Member"), (123456789, "recruiter")]


@pytest.mark.asyncio
async def test_set_permanent_roles_rolls_back_on_failure(mock_db):
    conn, cur = _mock_transaction_cursor(mock_db)
    cur.executemany.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await mock_db.users.set_permanent_roles(123456789, ["Member"])

    conn.rollback.assert_awaited_once()
    conn.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_has_permanent_role_true(mock_db):
    mock_db.execute.return_value = {"1": 1}

    result = await mock_db.users.has_permanent_role(123456789, "Member")

    assert result is True


@pytest.mark.asyncio
async def test_has_permanent_role_false(mock_db):
    mock_db.execute.return_value = None

    result = await mock_db.users.has_permanent_role(123456789, "Member")

    assert result is False


# ---------------------------------------------------------------------------
# get_permanent_roles()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_permanent_roles(mock_db):
    mock_db.execute.return_value = [
        {"role_significance": "Member"},
        {"role_significance": "recruiter"},
    ]

    roles = await mock_db.users.get_permanent_roles(123456789)

    assert roles == ["Member", "recruiter"]


@pytest.mark.asyncio
async def test_get_permanent_roles_empty(mock_db):
    mock_db.execute.return_value = []

    roles = await mock_db.users.get_permanent_roles(123456789)

    assert roles == []


# ---------------------------------------------------------------------------
# count_by_role()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_count_by_role(mock_db):
    mock_db.execute.return_value = {"cnt": 17}

    count = await mock_db.users.count_by_role("Member")

    assert count == 17


@pytest.mark.asyncio
async def test_count_by_role_zero(mock_db):
    mock_db.execute.return_value = {"cnt": 0}

    count = await mock_db.users.count_by_role("nonexistent")

    assert count == 0


# ---------------------------------------------------------------------------
# list_members()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_members_returns_users(mock_db, sample_user_row):
    # First call: row list; subsequent calls: roles for each user
    mock_db.execute.side_effect = [
        [sample_user_row],
        [{"role_significance": "Member"}],
    ]

    members = await mock_db.users.list_members()

    assert len(members) == 1
    assert members[0].name == "testuser"
    assert members[0].permanent_roles == ["Member"]


@pytest.mark.asyncio
async def test_list_members_empty(mock_db):
    mock_db.execute.return_value = []

    members = await mock_db.users.list_members()

    assert members == []


@pytest.mark.asyncio
async def test_list_members_with_role_filter(mock_db, sample_user_row):
    mock_db.execute.side_effect = [
        [sample_user_row],
        [{"role_significance": "Member"}],
    ]

    members = await mock_db.users.list_members(with_role="Member")

    assert len(members) == 1
    # The SQL should include a JOIN on user_permanent_roles
    sql = mock_db.execute.call_args_list[0][0][0]
    assert "JOIN" in sql


# ---------------------------------------------------------------------------
# assign_member_number()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assign_member_number(mock_db):
    # Calls:
    #   1) get_member_number() pre-check -> no value
    #   2) config.increment() -> reserved member number
    #   3) UPDATE users.member_number
    #   4) get_member_number() post-check -> assigned value
    mock_db.execute.side_effect = [
        None,
        None,
        {"member_number": 5},
    ]
    mock_db.config.increment = AsyncMock(return_value=5)

    number = await mock_db.users.assign_member_number(123456789)

    assert number == 5
    mock_db.config.increment.assert_awaited_once_with("last_member_number")
    assert mock_db.execute.call_count == 3


@pytest.mark.asyncio
async def test_assign_member_number_returns_existing_without_increment(mock_db):
    mock_db.execute.return_value = {"member_number": 12}

    number = await mock_db.users.assign_member_number(123456789)

    assert number == 12
    mock_db.execute.assert_called_once()


# ---------------------------------------------------------------------------
# User dataclass properties
# ---------------------------------------------------------------------------

def test_user_dataclass_defaults():
    user = User(id=1, name="foo")
    assert user.permanent_roles == []
    assert user.member_number is None
    assert user.discriminator is None


def test_user_permanent_roles_not_shared():
    """Each User instance must have its own list (not a shared default)."""
    u1 = User(id=1, name="a")
    u2 = User(id=2, name="b")
    u1.permanent_roles.append("Member")
    assert u2.permanent_roles == []


def _mock_transaction_cursor(mock_db):
    conn = MagicMock()
    conn.begin = AsyncMock()
    conn.commit = AsyncMock()
    conn.rollback = AsyncMock()
    cur = AsyncMock()
    mock_db.pool.acquire.return_value.__aenter__.return_value = conn
    conn.cursor.return_value.__aenter__.return_value = cur
    return conn, cur
