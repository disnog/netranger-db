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
from .queries.users import UserQueries
from .queries.guilds import GuildQueries
from .queries.config import ConfigQueries

__version__ = "2.0.0"
__all__ = ["Database", "UserQueries", "GuildQueries", "ConfigQueries"]
