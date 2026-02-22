# users.py
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

"""User-related database queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..connection import Database


@dataclass
class User:
    """User data model."""
    id: int
    name: str
    discriminator: Optional[str] = None
    nick: Optional[str] = None
    first_joined_at: Optional[datetime] = None
    member_number: Optional[int] = None
    permanent_roles: list[str] = field(default_factory=list)


class UserQueries:
    """User query interface."""
    
    def __init__(self, db: "Database"):
        self._db = db
    
    async def get(self, user_id: int) -> Optional[User]:
        """Get a user by Discord ID."""
        row = await self._db.execute(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            fetchone=True,
        )
        if not row:
            return None
        
        # Fetch permanent roles
        roles = await self._db.execute(
            "SELECT role_significance FROM user_permanent_roles WHERE user_id = %s",
            (user_id,),
            fetch=True,
        )
        
        return User(
            id=row["id"],
            name=row["name"],
            discriminator=row.get("discriminator"),
            nick=row.get("nick"),
            first_joined_at=row.get("first_joined_at"),
            member_number=row.get("member_number"),
            permanent_roles=[r["role_significance"] for r in roles],
        )
    
    async def upsert(
        self,
        user_id: int,
        name: str,
        discriminator: Optional[str] = None,
        nick: Optional[str] = None,
        first_joined_at: Optional[datetime] = None,
    ) -> None:
        """Insert or update a user."""
        await self._db.execute(
            """
            INSERT INTO users (id, name, discriminator, nick, first_joined_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                discriminator = VALUES(discriminator),
                nick = VALUES(nick),
                first_joined_at = COALESCE(first_joined_at, VALUES(first_joined_at))
            """,
            (user_id, name, discriminator, nick, first_joined_at),
        )
    
    async def add_permanent_role(self, user_id: int, role_significance: str) -> None:
        """Add a permanent role to a user."""
        await self._db.execute(
            """
            INSERT IGNORE INTO user_permanent_roles (user_id, role_significance)
            VALUES (%s, %s)
            """,
            (user_id, role_significance),
        )
    
    async def remove_permanent_role(self, user_id: int, role_significance: str) -> None:
        """Remove a permanent role from a user."""
        await self._db.execute(
            "DELETE FROM user_permanent_roles "
            "WHERE user_id = %s AND role_significance = %s",
            (user_id, role_significance),
        )
    
    async def get_permanent_roles(self, user_id: int) -> list[str]:
        """Get all permanent roles for a user."""
        rows = await self._db.execute(
            "SELECT role_significance FROM user_permanent_roles WHERE user_id = %s",
            (user_id,),
            fetch=True,
        )
        return [r["role_significance"] for r in rows]
    
    async def has_permanent_role(self, user_id: int, role_significance: str) -> bool:
        """Check if user has a specific permanent role."""
        row = await self._db.execute(
            """
            SELECT 1 FROM user_permanent_roles 
            WHERE user_id = %s AND role_significance = %s
            """,
            (user_id, role_significance),
            fetchone=True,
        )
        return row is not None
    
    async def assign_member_number(self, user_id: int) -> int:
        """
        Assign next member number to a user.
        Returns the assigned number.
        """
        # Get and increment the counter atomically
        await self._db.execute(
            """
            INSERT INTO config (name, value) VALUES ('last_member_number', '1')
            ON DUPLICATE KEY UPDATE value = value + 1
            """,
        )
        
        row = await self._db.execute(
            "SELECT value FROM config WHERE name = 'last_member_number'",
            fetchone=True,
        )
        member_number = int(row["value"])
        
        # Assign to user
        await self._db.execute(
            "UPDATE users SET member_number = %s "
            "WHERE id = %s AND member_number IS NULL",
            (member_number, user_id),
        )
        
        return member_number
    
    async def get_member_number(self, user_id: int) -> Optional[int]:
        """Get a user's member number."""
        row = await self._db.execute(
            "SELECT member_number FROM users WHERE id = %s",
            (user_id,),
            fetchone=True,
        )
        return row["member_number"] if row else None
    
    async def list_members(self, with_role: Optional[str] = None) -> list[User]:
        """
        List users with member numbers.
        Optionally filter by permanent role.
        """
        if with_role:
            rows = await self._db.execute(
                """
                SELECT u.* FROM users u
                JOIN user_permanent_roles r ON u.id = r.user_id
                WHERE u.member_number IS NOT NULL AND r.role_significance = %s
                ORDER BY u.member_number
                """,
                (with_role,),
                fetch=True,
            )
        else:
            rows = await self._db.execute(
                """
                SELECT * FROM users 
                WHERE member_number IS NOT NULL
                ORDER BY member_number
                """,
                fetch=True,
            )
        
        users = []
        for row in rows:
            roles = await self.get_permanent_roles(row["id"])
            users.append(User(
                id=row["id"],
                name=row["name"],
                discriminator=row.get("discriminator"),
                nick=row.get("nick"),
                first_joined_at=row.get("first_joined_at"),
                member_number=row.get("member_number"),
                permanent_roles=roles,
            ))
        return users
    
    async def count_by_role(self, role_significance: str) -> int:
        """Count users with a specific permanent role."""
        row = await self._db.execute(
            """
            SELECT COUNT(*) as cnt FROM user_permanent_roles
            WHERE role_significance = %s
            """,
            (role_significance,),
            fetchone=True,
        )
        return row["cnt"]
    
    async def get_users_without_member_number(
        self, 
        with_role: str = "Member",
        limit: int = 100,
    ) -> list[User]:
        """Get users who need member numbers assigned."""
        rows = await self._db.execute(
            """
            SELECT u.* FROM users u
            JOIN user_permanent_roles r ON u.id = r.user_id
            WHERE u.member_number IS NULL 
              AND u.first_joined_at IS NOT NULL
              AND r.role_significance = %s
            ORDER BY u.first_joined_at
            LIMIT %s
            """,
            (with_role, limit),
            fetch=True,
        )
        
        return [
            User(
                id=row["id"],
                name=row["name"],
                discriminator=row.get("discriminator"),
                nick=row.get("nick"),
                first_joined_at=row.get("first_joined_at"),
                member_number=None,
                permanent_roles=[with_role],
            )
            for row in rows
        ]
