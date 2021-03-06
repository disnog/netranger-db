# nrweb - nrdb.py
# Copyright (C) 2020  Networking Discord
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

from datetime import datetime
from pymongo import ReturnDocument


def get_guild(db, guild_id):
    return db.guilds.find_one({"_id": guild_id})


def get_user(db, user_id):
    q = {"_id": int(user_id)}
    r = db.users.find_one(q)
    return r


def get_role_by_significance(db, guild_id, role_significance):
    q = {"_id": guild_id, "known_roles.significance": role_significance}
    r = db.guilds.find_one(q, {"known_roles.$": 1})
    return r["known_roles"][0]


def get_significant_roles(db, guild_id):
    """
    Returns a list of tuples of significant role IDs and their associated significances.
    Example return:
        [{'id': '111111111111111111', 'name': 'Members', 'significance': ['Member']},
         {'color': 15844367.0,
          'id': '333333333333333333',
          'name': '!eggs',
          'significance': ['eggs']},
         {'id': '444444444444444444',
          'name': 'periphery',
          'significance': ['periphery']},
         {'id': '555555555555555555',
          'name': 'Recruiter',
          'significance': ['recruiter']}]
    :param db:
    :param guild_id:
    :return list:
    """
    q = {"_id": str(guild_id)}
    r = db.guilds.find_one(q, {"known_roles": 1})
    return r["known_roles"]


def get_channel_by_significance(db, guild_id, channel_significance):
    q = {"_id": guild_id, "known_channels.significance": channel_significance}
    r = db.guilds.find_one(q, {"known_channels.$": 1})
    return r["known_channels"][0]


def upsert_member(db, user, role_significances):
    if "permanent_roles" not in user:
        user["permanent_roles"] = list()
    for role_significance in role_significances:
        if role_significance not in user["permanent_roles"]:
            user["permanent_roles"].append(role_significance)
    m = {
        "name": user["username"],
        "discriminator": user["discriminator"],
        "permanent_roles": user["permanent_roles"],
    }
    if not (user.get("first_joined_at")):
        m.update({"first_joined_at": datetime.utcnow().timestamp()})
    if not (user.get("member_number")):
        nextnumber = db.config.find_one_and_update(
            {"name": "last_member_number"},
            {"$inc": {"value": 1}},
            projection={"value": True, "_id": False},
            return_document=ReturnDocument.AFTER,
            upsert=True,
        )["value"]
        m.update({"member_number": nextnumber})
    db.users.update_one(
        {"_id": int(user["id"])},
        {"$setOnInsert": {"_id": int(user["id"])}, "$set": m},
        upsert=True,
    )
