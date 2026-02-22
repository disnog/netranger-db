# tests/test_queries_guilds.py
# Unit tests for GuildQueries.

from __future__ import annotations

import pytest

from netranger_db.queries.guilds import Guild, KnownChannel, KnownRole

# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_returns_guild_with_roles_and_channels(
    mock_db,
    sample_guild_row,
    sample_known_role_rows,
    sample_sig_rows_member,
    sample_sig_rows_periphery,
    sample_channel_rows,
):
    mock_db.execute.side_effect = [
        sample_guild_row,              # guilds SELECT
        sample_known_role_rows,        # guild_known_roles SELECT
        sample_sig_rows_member,        # role_significances for role 1
        sample_sig_rows_periphery,     # role_significances for role 2
        sample_channel_rows,           # guild_known_channels SELECT
    ]

    guild = await mock_db.guilds.get("987654321")

    assert isinstance(guild, Guild)
    assert guild.id == "987654321"
    assert len(guild.known_roles) == 2
    assert guild.known_roles[0].role_id == "111000111"
    assert guild.known_roles[0].significances == ["Member"]
    assert len(guild.known_channels) == 1
    assert guild.known_channels[0].channel_id == "999888777"
    assert guild.known_channels[0].significance == "greeting"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_guild(mock_db):
    mock_db.execute.return_value = None

    guild = await mock_db.guilds.get("000")

    assert guild is None


@pytest.mark.asyncio
async def test_get_guild_no_roles_or_channels(mock_db, sample_guild_row):
    mock_db.execute.side_effect = [
        sample_guild_row,
        [],   # no roles
        [],   # no channels
    ]

    guild = await mock_db.guilds.get("987654321")

    assert guild.known_roles == []
    assert guild.known_channels == []


# ---------------------------------------------------------------------------
# get_role_by_significance()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_role_by_significance_found(mock_db, sample_sig_rows_member):
    role_row = {
        "id": 1, "role_id": "111000111", "role_name": "Members", "color": 0x00FF00
    }
    mock_db.execute.side_effect = [role_row, sample_sig_rows_member]

    role = await mock_db.guilds.get_role_by_significance("987654321", "Member")

    assert isinstance(role, KnownRole)
    assert role.role_id == "111000111"
    assert "Member" in role.significances


@pytest.mark.asyncio
async def test_get_role_by_significance_not_found(mock_db):
    mock_db.execute.return_value = None

    role = await mock_db.guilds.get_role_by_significance("987654321", "nonexistent")

    assert role is None


# ---------------------------------------------------------------------------
# get_channel_by_significance()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_channel_by_significance_found(mock_db):
    mock_db.execute.return_value = {
        "id": 1,
        "channel_id": "999888777",
        "significance": "greeting",
    }

    channel = await mock_db.guilds.get_channel_by_significance("987654321", "greeting")

    assert isinstance(channel, KnownChannel)
    assert channel.channel_id == "999888777"
    assert channel.significance == "greeting"


@pytest.mark.asyncio
async def test_get_channel_by_significance_not_found(mock_db):
    mock_db.execute.return_value = None

    channel = await mock_db.guilds.get_channel_by_significance("987654321", "missing")

    assert channel is None


# ---------------------------------------------------------------------------
# upsert()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guild_upsert(mock_db):
    mock_db.execute.return_value = None

    await mock_db.guilds.upsert("987654321", "My Server")

    mock_db.execute.assert_called_once()
    sql, params = mock_db.execute.call_args[0]
    assert "INSERT INTO guilds" in sql
    assert "987654321" in params


# ---------------------------------------------------------------------------
# get_significant_roles()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_significant_roles_returns_only_roles_with_significance(
    mock_db,
    sample_known_role_rows,
    sample_sig_rows_member,
):
    # Role 1 has significance, role 2 does not
    mock_db.execute.side_effect = [
        sample_known_role_rows,
        sample_sig_rows_member,  # role 1 has significance
        [],                       # role 2 has no significances -> excluded
    ]

    roles = await mock_db.guilds.get_significant_roles("987654321")

    assert len(roles) == 1
    assert roles[0].role_id == "111000111"


# ---------------------------------------------------------------------------
# KnownRole / KnownChannel dataclass defaults
# ---------------------------------------------------------------------------

def test_known_role_defaults():
    role = KnownRole(id=1, role_id="abc")
    assert role.significances == []
    assert role.role_name is None
    assert role.color is None


def test_known_channel_fields():
    ch = KnownChannel(id=1, channel_id="xyz", significance="greeting")
    assert ch.channel_id == "xyz"
    assert ch.significance == "greeting"
