"""Query modules for each domain."""

from .users import UserQueries
from .guilds import GuildQueries
from .config import ConfigQueries

__all__ = ["UserQueries", "GuildQueries", "ConfigQueries"]
