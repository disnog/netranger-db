#!/usr/bin/env python3

# import_to_mariadb.py
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

"""
Import data from MongoDB export to MariaDB.

Usage:
    DB_HOST=localhost DB_USER=netranger DB_PASS=secret DB_NAME=netranger \
        python import_to_mariadb.py < data.json

Prerequisites:
    - Run migrations first: nrdb-migrate migrate
    - Have the JSON export from export_mongo.py
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add parent to path for netranger_db import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from netranger_db import Database


def parse_timestamp(value):
    """Parse a timestamp that might be float (unix) or ISO string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        # Try ISO format
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            pass
    return None


async def import_users(db: Database, users: list) -> int:
    """Import users and their permanent roles."""
    count = 0
    
    for user in users:
        user_id = user.get("_id")
        if not user_id:
            continue
        
        # Handle user_id that might be string or int
        user_id = int(user_id)
        
        name = user.get("name", "Unknown")
        discriminator = user.get("discriminator")
        nick = user.get("nick")
        first_joined_at = parse_timestamp(user.get("first_joined_at"))
        member_number = user.get("member_number")
        permanent_roles = user.get("permanent_roles", [])
        
        # Insert user
        await db.execute(
            """
            INSERT INTO users
                (id, name, discriminator, nick, first_joined_at, member_number)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                discriminator = VALUES(discriminator),
                nick = VALUES(nick),
                first_joined_at = COALESCE(first_joined_at, VALUES(first_joined_at)),
                member_number = COALESCE(member_number, VALUES(member_number))
            """,
            (user_id, name, discriminator, nick, first_joined_at, member_number),
        )
        
        # Insert permanent roles
        for role in permanent_roles:
            if role:
                await db.execute(
                    """
                    INSERT IGNORE INTO user_permanent_roles (user_id, role_significance)
                    VALUES (%s, %s)
                    """,
                    (user_id, role),
                )
        
        count += 1
    
    return count


async def import_guilds(db: Database, guilds: list) -> int:
    """Import guilds, known roles, and known channels."""
    count = 0
    
    for guild in guilds:
        guild_id = str(guild.get("_id"))
        name = guild.get("name")
        known_roles = guild.get("known_roles", [])
        known_channels = guild.get("known_channels", [])
        
        # Insert guild
        await db.execute(
            """
            INSERT INTO guilds (id, name)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            (guild_id, name),
        )
        
        # Insert known roles
        for role in known_roles:
            role_id = str(role.get("id"))
            role_name = role.get("name")
            color = role.get("color")
            significances = role.get("significance", [])
            
            if isinstance(significances, str):
                significances = [significances]
            
            # Insert the role
            await db.execute(
                """
                INSERT INTO guild_known_roles (guild_id, role_id, role_name, color)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    role_name = VALUES(role_name),
                    color = VALUES(color)
                """,
                (guild_id, role_id, role_name, int(color) if color else None),
            )
            
            # Get the internal ID
            row = await db.execute(
                "SELECT id FROM guild_known_roles WHERE guild_id = %s AND role_id = %s",
                (guild_id, role_id),
                fetchone=True,
            )
            internal_id = row["id"]
            
            # Insert significances
            for sig in significances:
                if sig:
                    await db.execute(
                        """
                        INSERT IGNORE INTO role_significances (role_id, significance)
                        VALUES (%s, %s)
                        """,
                        (internal_id, sig),
                    )
        
        # Insert known channels
        for channel in known_channels:
            channel_id = str(channel.get("id"))
            significance = channel.get("significance")
            
            if significance:
                await db.execute(
                    """
                    INSERT INTO guild_known_channels
                        (guild_id, channel_id, significance)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE significance = VALUES(significance)
                    """,
                    (guild_id, channel_id, significance),
                )
        
        count += 1
    
    return count


async def import_config(db: Database, config: list) -> int:
    """Import config key-value pairs."""
    count = 0
    
    for entry in config:
        name = entry.get("name")
        value = entry.get("value")
        
        if name:
            await db.execute(
                """
                INSERT INTO config (name, value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE value = VALUES(value)
                """,
                (name, str(value) if value is not None else None),
            )
            count += 1
    
    return count


async def main():
    # Read JSON from stdin
    data = json.load(sys.stdin)
    
    print(f"Importing data exported at {data.get('exported_at', 'unknown')}")
    
    collections = data.get("collections", {})
    
    db = Database.from_env()
    await db.connect()
    
    try:
        # Import in order: guilds first (FK constraints), then users
        guilds = collections.get("guilds", [])
        guild_count = await import_guilds(db, guilds)
        print(f"Imported {guild_count} guilds")
        
        users = collections.get("users", [])
        user_count = await import_users(db, users)
        print(f"Imported {user_count} users")
        
        config = collections.get("config", [])
        config_count = await import_config(db, config)
        print(f"Imported {config_count} config entries")
        
        print("Import complete!")
        
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
