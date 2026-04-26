# DisNOG V2 Project: netranger-db

## GitHub Project Fields

| Field | Value |
| --- | --- |
| Project | DisNOG V2 |
| Repository | disnog/netranger-db |
| Branch | v2dev |
| Track | Data foundation |
| Status | Ready for integration verification |
| Priority | P0 |
| Depends on | MariaDB service availability |
| Enables | disnog/netranger-bot, disnog/netranger-web |

## Item Summary

Migrate the shared Network Ranger data layer from the legacy MongoDB helper module to a packaged MariaDB library with migrations, typed query interfaces, export/import tooling, CI, and unit tests.

## Feature Differences From main

| Area | main | v2dev | Documentation |
| --- | --- | --- | --- |
| Database engine | MongoDB/PyMongo helpers in a flat `__init__.py` | MariaDB/MySQL via `aiomysql` and `PyMySQL` | `README.md`, `MIGRATEDB.md` |
| Schema management | Implicit MongoDB collections | Numbered SQL migrations with `_migrations` tracking | `README.md`, `MIGRATEDB.md` |
| Data model | Nested users/guild documents | Normalized `users`, roles, guilds, channels, config tables | `README.md`, `MIGRATEDB.md` |
| Data migration | None | `scripts/export_mongo.py` and `scripts/import_to_mariadb.py` | `MIGRATEDB.md` |
| Packaging | Importable legacy module only | `pyproject.toml`, package metadata, console script | `README.md` |
| Tests/CI | None in main | Unit tests and GitHub Actions | `README.md`, `.github/workflows/ci.yml` |

## Migration Path

1. Provision MariaDB 10.6+ or MySQL 8.0+.
2. Install `netranger-db` from `v2dev`.
3. Configure `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, and `DB_NAME`.
4. Run `nrdb-migrate migrate`.
5. Export MongoDB with `scripts/export_mongo.py`.
6. Import the export with `scripts/import_to_mariadb.py`.
7. Verify row counts, role mappings, and `last_member_number >= MAX(users.member_number)`.
8. Deploy `netranger-web` and `netranger-bot` `v2dev` against the migrated database.
9. Keep MongoDB read-only and available until web and bot smoke tests pass.

## Acceptance Criteria

- All SQL migrations apply on an empty database.
- MongoDB export/import is repeatable and does not create duplicate users, roles, guilds, channels, or config rows.
- Existing member numbers are preserved.
- `last_member_number` is reconciled to the imported maximum.
- Concurrent member-number assignment reserves distinct values.
- `pytest` and `ruff check .` pass.

## Audit Notes

- Fixed during audit: member-number assignment now reserves the incremented config value on the same MariaDB connection.
- Fixed during audit: added `set_permanent_roles()` so consumers can replace current member role state safely during sync.
