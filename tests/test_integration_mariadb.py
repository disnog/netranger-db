# tests/test_integration_mariadb.py
# Tests that run against a real MariaDB server.
#
# They create and drop their own scratch database, so they only run when
# NRDB_INTEGRATION=1 is set (CI sets it next to its MariaDB service). The
# connection comes from the usual DB_HOST/DB_PORT/DB_USER/DB_PASS variables,
# and that user needs CREATE and DROP DATABASE rights.

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta

import aiomysql
import pytest

from netranger_db import Database
from netranger_db.connection import DatabaseConfig
from netranger_db.migrations.runner import MigrationRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("NRDB_INTEGRATION") != "1",
    reason="set NRDB_INTEGRATION=1 to run against a real MariaDB",
)


async def _admin_execute(sql: str) -> None:
    cfg = DatabaseConfig.from_env()
    conn = await aiomysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        autocommit=True,
    )
    try:
        async with conn.cursor() as cur:
            await cur.execute(sql)
    finally:
        conn.close()


@pytest.fixture
async def db():
    name = f"nrdb_it_{uuid.uuid4().hex[:12]}"
    await _admin_execute(
        f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cfg = DatabaseConfig.from_env()
    cfg.database = name
    cfg.pool_size = 25
    database = Database(cfg)
    await database.connect()
    try:
        yield database
    finally:
        await database.close()
        await _admin_execute(f"DROP DATABASE {name}")


@pytest.fixture
async def migrated_db(db):
    await MigrationRunner(db).migrate()
    return db


async def _tables(db) -> set[str]:
    rows = await db.execute(
        "SELECT table_name AS t FROM information_schema.tables "
        "WHERE table_schema = DATABASE()",
        fetch=True,
    )
    return {r["t"] for r in rows}


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

async def test_migrations_apply_on_empty_database(db):
    runner = MigrationRunner(db)

    assert await runner.migrate() == len(runner.get_available_migrations())

    assert {
        "_migrations",
        "users",
        "user_permanent_roles",
        "guilds",
        "guild_known_roles",
        "role_significances",
        "guild_known_channels",
        "config",
    } <= await _tables(db)
    assert await runner.migrate() == 0


async def test_partly_applied_migration_can_be_rerun(db):
    """A migration that failed after some DDL ran must succeed on retry."""
    runner = MigrationRunner(db)
    version, name, path = runner.get_available_migrations()[0]
    statements = [s.strip() for s in path.read_text().split(";") if s.strip()]

    # Simulate a crash after the first two CREATE TABLEs: MariaDB has
    # committed them, and no _migrations row was written.
    await runner.ensure_migrations_table()
    for statement in statements[:2]:
        await db.execute(statement)
    assert version not in await runner.get_applied_versions()

    assert await runner.migrate() >= 1
    assert version in await runner.get_applied_versions()
    assert "config" in await _tables(db)


async def test_ensure_migrations_table_is_quiet_when_present(db, recwarn):
    runner = MigrationRunner(db)
    await runner.ensure_migrations_table()
    recwarn.clear()

    await runner.ensure_migrations_table()

    assert not [w for w in recwarn if "already exists" in str(w.message)]


# ---------------------------------------------------------------------------
# Member numbers
# ---------------------------------------------------------------------------

async def test_assign_member_number_unknown_user_reserves_nothing(migrated_db):
    with pytest.raises(LookupError):
        await migrated_db.users.assign_member_number(424242)

    assert await migrated_db.config.get("last_member_number") is None


async def test_concurrent_calls_for_one_user_reserve_one_number(migrated_db):
    await migrated_db.users.upsert(1001, "solo")

    results = await asyncio.gather(
        *(migrated_db.users.assign_member_number(1001) for _ in range(10))
    )

    assert set(results) == {1}
    assert await migrated_db.config.get_int("last_member_number") == 1
    assert await migrated_db.users.get_member_number(1001) == 1


async def test_concurrent_calls_for_many_users_get_distinct_numbers(migrated_db):
    ids = list(range(2000, 2050))
    for uid in ids:
        await migrated_db.users.upsert(uid, f"user{uid}")

    results = await asyncio.gather(
        *(migrated_db.users.assign_member_number(uid) for uid in ids)
    )

    assert sorted(results) == list(range(1, len(ids) + 1))
    assert await migrated_db.config.get_int("last_member_number") == len(ids)


async def test_assign_missing_member_numbers_uses_join_order(migrated_db):
    users = migrated_db.users
    base = datetime(2021, 1, 1)
    await migrated_db.config.set("last_member_number", "40")
    # Inserted out of join order on purpose.
    await users.upsert(3, "third", first_joined_at=base + timedelta(days=3))
    await users.upsert(1, "first", first_joined_at=base + timedelta(days=1))
    await users.upsert(2, "second", first_joined_at=base + timedelta(days=2))
    await users.upsert(4, "periphery", first_joined_at=base)
    await users.upsert(5, "no-join-date")
    for uid in (1, 2, 3, 5):
        await users.add_permanent_role(uid, "Member")
    await users.add_permanent_role(4, "periphery")

    assigned = await users.assign_missing_member_numbers(batch_size=2)

    assert assigned == [(1, 41), (2, 42), (3, 43)]
    assert await users.get_member_number(4) is None
    assert await users.get_member_number(5) is None
    assert await users.assign_missing_member_numbers() == []
