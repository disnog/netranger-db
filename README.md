# netranger-db

Database library for Network Ranger (bot and web). Provides async MariaDB/MySQL access with a simple migration system.

## Installation

```bash
pip install git+https://github.com/disnog/netranger-db.git@v2dev
```

## Configuration

Set environment variables (or copy `.env.example` to `.env`):

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=netranger
export DB_PASS=secret
export DB_NAME=netranger
```

## Usage

### Async (discord.py / asyncio)

```python
from netranger_db import Database

# Using context manager (recommended)
async with Database.from_env() as db:
    user = await db.users.get(123456789)
    if user:
        print(f"Member #{user.member_number}: {user.name}")

# Manual connection management
db = Database.from_env()
await db.connect()
try:
    await db.users.upsert(123456789, "username", nick="Nickname")
    await db.users.add_permanent_role(123456789, "Member")
finally:
    await db.close()
```

### Available Query Interfaces

```python
# Users
user = await db.users.get(user_id)
await db.users.upsert(user_id, name, discriminator, nick, first_joined_at)
await db.users.add_permanent_role(user_id, "Member")
await db.users.remove_permanent_role(user_id, "Member")
roles = await db.users.get_permanent_roles(user_id)
has_role = await db.users.has_permanent_role(user_id, "Member")
member_num = await db.users.assign_member_number(user_id)
members = await db.users.list_members(with_role="Member")
count = await db.users.count_by_role("Member")

# Guilds
guild = await db.guilds.get(guild_id)
await db.guilds.upsert(guild_id, name)
role = await db.guilds.get_role_by_significance(guild_id, "Member")
roles = await db.guilds.get_significant_roles(guild_id)
channel = await db.guilds.get_channel_by_significance(guild_id, "greeting")

# Config (key-value store)
value = await db.config.get("some_key")
await db.config.set("some_key", "some_value")
count = await db.config.increment("counter")
```

## Migrations

Run pending migrations:

```bash
nrdb-migrate migrate
```

Check migration status:

```bash
nrdb-migrate status
```

### Creating New Migrations

Add numbered SQL files to `netranger_db/migrations/versions/`:

```
002_add_email_verification.sql
003_add_audit_log.sql
```

## Migration from MongoDB

See `MIGRATEDB.md` for full migration instructions and `scripts/` for helper scripts.

## Schema

See `netranger_db/migrations/versions/001_initial.sql` for the complete schema.

### Tables

- `users` — Discord users with member numbers and join dates
- `user_permanent_roles` — Roles that persist across leave/rejoin
- `guilds` — Discord servers
- `guild_known_roles` — Roles with special significance
- `role_significances` — Many-to-many role significance mappings
- `guild_known_channels` — Channels with special purposes
- `config` — Key-value configuration store

## Development

### Setup

```bash
git clone https://github.com/disnog/netranger-db.git
cd netranger-db
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env   # edit with real values
```

### Running Tests

Tests use `pytest-asyncio` and mock the database layer — **no running MariaDB instance is required** for the unit tests.

```bash
# Run all tests
pytest -v

# Run with coverage report
pytest -v --cov=netranger_db --cov-report=term-missing

# Run a specific test file
pytest tests/test_queries_users.py -v
```

### Linting

```bash
ruff check .
ruff check . --fix   # auto-fix safe issues
```

## License

AGPL-3.0-or-later
