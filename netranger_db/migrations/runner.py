# runner.py
# Copyright (C) 2020-2026 DisNOG.org
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Simple SQL migration runner."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import Database


class MigrationRunner:
    """
    Simple SQL migration runner.
    
    Migrations are numbered SQL files in the versions/ directory:
        001_initial.sql
        002_add_indexes.sql
        etc.
    
    Applied migrations are tracked in a _migrations table.
    """
    
    def __init__(self, db: "Database"):
        self._db = db
        self._versions_dir = Path(__file__).parent / "versions"
    
    async def ensure_migrations_table(self) -> None:
        """Create the migrations tracking table if it doesn't exist."""
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                version INT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    
    async def get_applied_versions(self) -> set[int]:
        """Get set of already-applied migration versions."""
        await self.ensure_migrations_table()
        rows = await self._db.execute(
            "SELECT version FROM _migrations",
            fetch=True,
        )
        return {r["version"] for r in rows}
    
    def get_available_migrations(self) -> list[tuple[int, str, Path]]:
        """
        Get list of available migrations.
        Returns list of (version, name, path) tuples, sorted by version.
        """
        migrations = []
        
        if not self._versions_dir.exists():
            return migrations
        
        for file in self._versions_dir.glob("*.sql"):
            match = re.match(r"^(\d+)_(.+)\.sql$", file.name)
            if match:
                version = int(match.group(1))
                name = match.group(2)
                migrations.append((version, name, file))
        
        return sorted(migrations, key=lambda x: x[0])
    
    async def apply_migration(self, version: int, name: str, path: Path) -> None:
        """Apply a single migration."""
        print(f"Applying migration {version:03d}_{name}...")
        
        sql = path.read_text()
        
        # Split on semicolons but handle edge cases
        # This is naive but works for most migrations
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        
        async with self._db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for statement in statements:
                    if statement:
                        await cur.execute(statement)
                
                # Record the migration
                await cur.execute(
                    "INSERT INTO _migrations (version, name) VALUES (%s, %s)",
                    (version, name),
                )
        
        print(f"  Applied {version:03d}_{name}")
    
    async def migrate(self) -> int:
        """
        Apply all pending migrations.
        Returns the number of migrations applied.
        """
        applied = await self.get_applied_versions()
        available = self.get_available_migrations()
        
        count = 0
        for version, name, path in available:
            if version not in applied:
                await self.apply_migration(version, name, path)
                count += 1
        
        if count == 0:
            print("No pending migrations.")
        else:
            print(f"Applied {count} migration(s).")
        
        return count
    
    async def status(self) -> None:
        """Print migration status."""
        applied = await self.get_applied_versions()
        available = self.get_available_migrations()
        
        print("Migration Status:")
        print("-" * 40)
        
        for version, name, path in available:
            status = "✓" if version in applied else "pending"
            print(f"  {version:03d}_{name}: {status}")
        
        if not available:
            print("  No migrations found.")
