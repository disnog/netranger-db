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

from .config import increment_with_cursor

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

    async def set_permanent_roles(
        self,
        user_id: int,
        role_significances: list[str],
    ) -> None:
        """Replace all permanent roles for a user."""
        unique_roles = list(dict.fromkeys(role_significances))
        async with self._db.pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM user_permanent_roles WHERE user_id = %s",
                        (user_id,),
                    )
                    if unique_roles:
                        await cur.executemany(
                            """
                            INSERT INTO user_permanent_roles
                                (user_id, role_significance)
                            VALUES (%s, %s)
                            """,
                            [(user_id, role) for role in unique_roles],
                        )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    
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
        Assign the next member number to a user who doesn't have one.

        Returns the user's member number: the existing one if already
        assigned, otherwise the newly assigned one. Raises LookupError if
        the user isn't in the users table, so no number is reserved for a
        row that can't hold it.

        The user row is locked for the whole operation, so concurrent calls
        for the same user wait for each other and reserve only one number.
        """
        async with self._db.pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT member_number FROM users WHERE id = %s FOR UPDATE",
                        (user_id,),
                    )
                    row = await cur.fetchone()
                    if row is None:
                        raise LookupError(f"User {user_id} not found")
                    if row[0] is not None:
                        await conn.commit()
                        return int(row[0])

                    member_number = await increment_with_cursor(
                        cur, "last_member_number"
                    )

                    await cur.execute(
                        "UPDATE users SET member_number = %s WHERE id = %s",
                        (member_number, user_id),
                    )
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise
        return member_number

    async def assign_missing_member_numbers(
        self,
        with_role: str = "Member",
        batch_size: int = 100,
    ) -> list[tuple[int, int]]:
        """
        Number every user with ``with_role`` who has no member number yet.

        Users are numbered in first_joined_at order, as the legacy bot did.
        Users without a first_joined_at are skipped. Returns a list of
        (user_id, member_number) pairs in assignment order.
        """
        assigned: list[tuple[int, int]] = []
        seen: set[int] = set()
        while True:
            batch = await self.get_users_without_member_number(
                with_role=with_role,
                limit=batch_size,
            )
            pending = [u for u in batch if u.id not in seen]
            if not pending:
                return assigned
            for user in pending:
                seen.add(user.id)
                number = await self.assign_member_number(user.id)
                assigned.append((user.id, number))

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
            ORDER BY u.first_joined_at, u.id
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
