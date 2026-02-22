# __init__.py
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
netranger-db: Database library for Network Ranger

Install from git:
    pip install git+https://github.com/disnog/netranger-db.git

Usage:
    from netranger_db import Database
    
    # Async (for FastAPI / discord.py)
    db = Database.from_env()
    await db.connect()
    user = await db.users.get(user_id)
    await db.close()
    
    # Context manager
    async with Database.from_env() as db:
        user = await db.users.get(user_id)
"""

from .connection import Database
from .queries.config import ConfigQueries
from .queries.guilds import GuildQueries
from .queries.users import UserQueries

__version__ = "2.0.0"
__all__ = ["Database", "UserQueries", "GuildQueries", "ConfigQueries"]
