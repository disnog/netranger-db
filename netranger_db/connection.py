# connection.py
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

"""Database connection management."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import aiomysql


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str = "localhost"
    port: int = 3306
    user: str = "netranger"
    password: str = ""
    database: str = "netranger"
    pool_size: int = 5
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load config from environment variables."""
        return cls(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "netranger"),
            password=os.environ.get("DB_PASS", ""),
            database=os.environ.get("DB_NAME", "netranger"),
            pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        )


class Database:
    """
    Async database connection manager.
    
    Usage:
        db = Database.from_env()
        await db.connect()
        # ... use db.users, db.guilds, db.config
        await db.close()
        
        # Or as context manager:
        async with Database.from_env() as db:
            user = await db.users.get(123)
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._pool: Optional[aiomysql.Pool] = None
        
        # Query interfaces (initialized after connect)
        from .queries.users import UserQueries
        from .queries.guilds import GuildQueries
        from .queries.config import ConfigQueries
        
        self.users = UserQueries(self)
        self.guilds = GuildQueries(self)
        self.config_store = ConfigQueries(self)
    
    @classmethod
    def from_env(cls) -> "Database":
        """Create Database instance from environment variables."""
        return cls(DatabaseConfig.from_env())
    
    async def connect(self) -> None:
        """Establish connection pool."""
        if self._pool is not None:
            return
        
        self._pool = await aiomysql.create_pool(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            db=self.config.database,
            maxsize=self.config.pool_size,
            autocommit=True,
            charset="utf8mb4",
        )
    
    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
    
    async def __aenter__(self) -> "Database":
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    @property
    def pool(self) -> aiomysql.Pool:
        """Get connection pool, raising if not connected."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call await db.connect() first.")
        return self._pool
    
    async def execute(
        self, 
        query: str, 
        params: tuple = (), 
        fetch: bool = False,
        fetchone: bool = False,
    ) -> Any:
        """
        Execute a query.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: If True, return all rows
            fetchone: If True, return single row
            
        Returns:
            Query results if fetch/fetchone, else lastrowid
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                
                if fetch:
                    return await cur.fetchall()
                elif fetchone:
                    return await cur.fetchone()
                else:
                    return cur.lastrowid
    
    async def executemany(self, query: str, params_list: list[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, params_list)
                return cur.rowcount
