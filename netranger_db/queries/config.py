# config.py
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

"""Configuration key-value store queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..connection import Database


class ConfigQueries:
    """Config key-value store interface."""
    
    def __init__(self, db: "Database"):
        self._db = db
    
    async def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a config value by name."""
        row = await self._db.execute(
            "SELECT value FROM config WHERE name = %s",
            (name,),
            fetchone=True,
        )
        return row["value"] if row else default
    
    async def set(self, name: str, value: str) -> None:
        """Set a config value."""
        await self._db.execute(
            """
            INSERT INTO config (name, value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE value = VALUES(value)
            """,
            (name, value),
        )
    
    async def delete(self, name: str) -> None:
        """Delete a config value."""
        await self._db.execute(
            "DELETE FROM config WHERE name = %s",
            (name,),
        )
    
    async def get_int(self, name: str, default: int = 0) -> int:
        """Get a config value as integer."""
        value = await self.get(name)
        return int(value) if value is not None else default
    
    async def increment(self, name: str, by: int = 1) -> int:
        """Increment a numeric config value and return the new value."""
        await self._db.execute(
            """
            INSERT INTO config (name, value) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE value = value + %s
            """,
            (name, str(by), by),
        )
        return await self.get_int(name)
