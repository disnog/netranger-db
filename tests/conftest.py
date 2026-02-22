# tests/conftest.py
# Shared fixtures for netranger-db tests.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from netranger_db.queries.config import ConfigQueries
from netranger_db.queries.guilds import GuildQueries
from netranger_db.queries.users import UserQueries


@pytest.fixture
def mock_db():
    """Mock Database with AsyncMock execute, wired to real query classes."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.users = UserQueries(db)
    db.guilds = GuildQueries(db)
    db.config = ConfigQueries(db)
    return db


@pytest.fixture
def sample_user_row():
    return {
        "id": 123456789,
        "name": "testuser",
        "discriminator": "1234",
        "nick": "Test User",
        "first_joined_at": None,
        "member_number": 42,
    }


@pytest.fixture
def sample_role_rows():
    return [
        {"role_significance": "Member"},
    ]


@pytest.fixture
def sample_guild_row():
    return {"id": "987654321", "name": "Test Guild"}


@pytest.fixture
def sample_known_role_rows():
    return [
        {"id": 1, "role_id": "111000111", "role_name": "Members", "color": 0x00FF00},
        {"id": 2, "role_id": "222000222", "role_name": "Periphery", "color": 0x0000FF},
    ]


@pytest.fixture
def sample_sig_rows_member():
    return [{"significance": "Member"}]


@pytest.fixture
def sample_sig_rows_periphery():
    return [{"significance": "periphery"}]


@pytest.fixture
def sample_channel_rows():
    return [
        {"id": 1, "channel_id": "999888777", "significance": "greeting"},
    ]
