# guilds.py
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

"""Guild-related database queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..connection import Database


@dataclass
class KnownRole:
    """A role with significance mappings."""
    id: int
    role_id: str
    role_name: Optional[str] = None
    color: Optional[int] = None
    significances: list[str] = field(default_factory=list)


@dataclass
class KnownChannel:
    """A channel with significance."""
    id: int
    channel_id: str
    significance: str


@dataclass
class Guild:
    """Guild data model."""
    id: str
    name: Optional[str] = None
    known_roles: list[KnownRole] = field(default_factory=list)
    known_channels: list[KnownChannel] = field(default_factory=list)


class GuildQueries:
    """Guild query interface."""
    
    def __init__(self, db: "Database"):
        self._db = db
    
    async def get(self, guild_id: str) -> Optional[Guild]:
        """Get a guild by ID with all known roles and channels."""
        row = await self._db.execute(
            "SELECT * FROM guilds WHERE id = %s",
            (guild_id,),
            fetchone=True,
        )
        if not row:
            return None
        
        guild = Guild(id=row["id"], name=row.get("name"))
        
        # Fetch known roles
        role_rows = await self._db.execute(
            "SELECT * FROM guild_known_roles WHERE guild_id = %s",
            (guild_id,),
            fetch=True,
        )
        
        for role_row in role_rows:
            sig_rows = await self._db.execute(
                "SELECT significance FROM role_significances WHERE role_id = %s",
                (role_row["id"],),
                fetch=True,
            )
            guild.known_roles.append(KnownRole(
                id=role_row["id"],
                role_id=role_row["role_id"],
                role_name=role_row.get("role_name"),
                color=role_row.get("color"),
                significances=[s["significance"] for s in sig_rows],
            ))
        
        # Fetch known channels
        channel_rows = await self._db.execute(
            "SELECT * FROM guild_known_channels WHERE guild_id = %s",
            (guild_id,),
            fetch=True,
        )
        guild.known_channels = [
            KnownChannel(
                id=row["id"],
                channel_id=row["channel_id"],
                significance=row["significance"],
            )
            for row in channel_rows
        ]
        
        return guild
    
    async def upsert(self, guild_id: str, name: Optional[str] = None) -> None:
        """Insert or update a guild."""
        await self._db.execute(
            """
            INSERT INTO guilds (id, name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            (guild_id, name),
        )
    
    async def get_role_by_significance(
        self, 
        guild_id: str, 
        significance: str,
    ) -> Optional[KnownRole]:
        """Get a role by its significance."""
        row = await self._db.execute(
            """
            SELECT r.* FROM guild_known_roles r
            JOIN role_significances s ON r.id = s.role_id
            WHERE r.guild_id = %s AND s.significance = %s
            LIMIT 1
            """,
            (guild_id, significance),
            fetchone=True,
        )
        if not row:
            return None
        
        sig_rows = await self._db.execute(
            "SELECT significance FROM role_significances WHERE role_id = %s",
            (row["id"],),
            fetch=True,
        )
        
        return KnownRole(
            id=row["id"],
            role_id=row["role_id"],
            role_name=row.get("role_name"),
            color=row.get("color"),
            significances=[s["significance"] for s in sig_rows],
        )
    
    async def get_significant_roles(self, guild_id: str) -> list[KnownRole]:
        """Get all roles with significances for a guild."""
        role_rows = await self._db.execute(
            "SELECT * FROM guild_known_roles WHERE guild_id = %s",
            (guild_id,),
            fetch=True,
        )
        
        roles = []
        for role_row in role_rows:
            sig_rows = await self._db.execute(
                "SELECT significance FROM role_significances WHERE role_id = %s",
                (role_row["id"],),
                fetch=True,
            )
            if sig_rows:  # Only include roles with significances
                roles.append(KnownRole(
                    id=role_row["id"],
                    role_id=role_row["role_id"],
                    role_name=role_row.get("role_name"),
                    color=role_row.get("color"),
                    significances=[s["significance"] for s in sig_rows],
                ))
        
        return roles
    
    async def get_channel_by_significance(
        self, 
        guild_id: str, 
        significance: str,
    ) -> Optional[KnownChannel]:
        """Get a channel by its significance."""
        row = await self._db.execute(
            """
            SELECT * FROM guild_known_channels
            WHERE guild_id = %s AND significance = %s
            LIMIT 1
            """,
            (guild_id, significance),
            fetchone=True,
        )
        if not row:
            return None
        
        return KnownChannel(
            id=row["id"],
            channel_id=row["channel_id"],
            significance=row["significance"],
        )
    
    async def add_known_role(
        self,
        guild_id: str,
        role_id: str,
        role_name: Optional[str] = None,
        color: Optional[int] = None,
        significances: list[str] = None,
    ) -> int:
        """Add a known role to a guild. Returns the role's internal ID."""
        row_id = await self._db.execute(
            """
            INSERT INTO guild_known_roles (guild_id, role_id, role_name, color)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                role_name = VALUES(role_name),
                color = VALUES(color)
            """,
            (guild_id, role_id, role_name, color),
        )
        
        # Get the ID (either new or existing)
        if row_id == 0:
            existing = await self._db.execute(
                "SELECT id FROM guild_known_roles WHERE guild_id = %s AND role_id = %s",
                (guild_id, role_id),
                fetchone=True,
            )
            row_id = existing["id"]
        
        # Add significances
        if significances:
            for sig in significances:
                await self._db.execute(
                    """
                    INSERT IGNORE INTO role_significances (role_id, significance)
                    VALUES (%s, %s)
                    """,
                    (row_id, sig),
                )
        
        return row_id
    
    async def add_known_channel(
        self,
        guild_id: str,
        channel_id: str,
        significance: str,
    ) -> int:
        """Add a known channel to a guild."""
        return await self._db.execute(
            """
            INSERT INTO guild_known_channels (guild_id, channel_id, significance)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE significance = VALUES(significance)
            """,
            (guild_id, channel_id, significance),
        )
