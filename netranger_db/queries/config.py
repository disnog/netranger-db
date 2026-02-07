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
