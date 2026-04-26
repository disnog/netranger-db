# Database Migration Guide: MongoDB → MariaDB

This guide covers migrating from the legacy MongoDB setup to the new MariaDB schema.

## Prerequisites

- Python 3.10+
- MariaDB 10.6+ or MySQL 8.0+
- Access to your existing MongoDB instance
- `pymongo` installed for export script

## Step 1: Set Up MariaDB

```bash
# Create database and user
mysql -u root -p << 'SQL'
CREATE DATABASE netranger CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'netranger'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON netranger.* TO 'netranger'@'localhost';
FLUSH PRIVILEGES;
SQL
```

## Step 2: Install netranger-db

```bash
pip install git+https://github.com/disnog/netranger-db.git@v2dev
```

## Step 3: Configure Environment

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=netranger
export DB_PASS=your_secure_password
export DB_NAME=netranger
```

## Step 4: Run Migrations

```bash
nrdb-migrate migrate
```

This creates all tables:
- `users` - Discord users with member info
- `user_permanent_roles` - Persistent role assignments
- `guilds` - Discord servers
- `guild_known_roles` - Roles with significance mappings
- `role_significances` - Role-to-significance mappings
- `guild_known_channels` - Channels with special purposes
- `config` - Key-value configuration store
- `_migrations` - Migration tracking

## Step 5: Export from MongoDB

```bash
# Set MongoDB connection
export MONGO_HOST=localhost
export MONGO_PORT=27017
export MONGO_USER=your_mongo_user
export MONGO_PASS=your_mongo_pass
export MONGO_DB=network_ranger

# Or use a URI
export MONGO_URI="mongodb://user:pass@host:27017/network_ranger?authSource=admin"

# Run export
cd /path/to/netranger-db
pip install pymongo  # if not installed
python scripts/export_mongo.py > data.json
```

This exports:
- All users with permanent roles and member numbers
- Guild configurations (known roles, channels)
- Config key-value pairs

## Step 6: Import to MariaDB

```bash
python scripts/import_to_mariadb.py < data.json
```

The importer reconciles `config.last_member_number` to at least the current
maximum value in `users.member_number` so future member-number assignment
continues safely.

The runtime member-number counter uses a connection-local MariaDB increment
when assigning new numbers, so concurrent joins reserve distinct values instead
of reading a global counter value that another worker may have advanced.

## Step 7: Verify Migration

```bash
# Check migration status
nrdb-migrate status

# Verify data (using mysql client)
mysql -u netranger -p netranger << 'SQL'
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as member_count FROM users WHERE member_number IS NOT NULL;
SELECT COUNT(*) as roles_count FROM user_permanent_roles;
SELECT value AS last_member_number FROM config WHERE name = 'last_member_number';
SELECT MAX(member_number) AS max_member_number FROM users;
SELECT * FROM config;
SQL
```

`last_member_number` should be greater than or equal to `max_member_number`.

## Step 8: Update Applications

Update environment variables for bot and web:

### Changed Variables

| Old (MongoDB) | New (MariaDB) | Notes |
|---------------|---------------|-------|
| `MONGO_HOST` | `DB_HOST` | |
| `MONGO_PORT` | `DB_PORT` | Default: 3306 |
| `MONGO_USER` | `DB_USER` | |
| `MONGO_PASS` | `DB_PASS` | |
| `MONGO_DB` | `DB_NAME` | |
| `MONGO_URI` | *(removed)* | Use individual vars |
| `MONGO_AUTHSOURCE` | *(removed)* | Not needed |

### New Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | 5 | Connection pool size |

## Rollback Plan

If issues occur, the MongoDB data remains untouched. Simply:
1. Point applications back to MongoDB env vars
2. Redeploy old application versions

## Schema Differences

### Users Collection → users + user_permanent_roles

**MongoDB:**
```json
{
  "_id": 123456789,
  "name": "username",
  "discriminator": "1234",
  "permanent_roles": ["Member", "!eggs"],
  "member_number": 42
}
```

**MariaDB:**
```sql
-- users table
SELECT * FROM users WHERE id = 123456789;
-- user_permanent_roles table  
SELECT * FROM user_permanent_roles WHERE user_id = 123456789;
```

### Guilds Collection → guilds + guild_known_roles + role_significances + guild_known_channels

The nested MongoDB structure is normalized into relational tables with proper foreign keys.

## Troubleshooting

### "Table already exists" during migration
```bash
# Check current state
nrdb-migrate status
# Migrations are idempotent - already applied ones are skipped
```

### Import fails with duplicate key
The import script uses `INSERT ... ON DUPLICATE KEY UPDATE`, so re-running is safe.

### Connection refused
Check MariaDB is running and accepting connections:
```bash
mysql -u netranger -p -h localhost netranger -e "SELECT 1"
```
