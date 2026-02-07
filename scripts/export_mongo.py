#!/usr/bin/env python3
"""
Export data from MongoDB for migration to MariaDB.

Usage:
    MONGO_URI="mongodb://user:pass@host:27017/network_ranger" python export_mongo.py > data.json
    
Or with individual variables:
    MONGO_HOST=localhost MONGO_PORT=27017 MONGO_USER=user MONGO_PASS=pass MONGO_DB=network_ranger \
        python export_mongo.py > data.json
"""

import json
import os
import sys
from datetime import datetime
from urllib.parse import quote_plus

from pymongo import MongoClient


def get_mongo_client():
    """Create MongoDB client from environment."""
    uri = os.environ.get("MONGO_URI")
    
    if not uri:
        host = os.environ.get("MONGO_HOST", "localhost")
        port = os.environ.get("MONGO_PORT", "27017")
        user = os.environ.get("MONGO_USER")
        password = os.environ.get("MONGO_PASS")
        db = os.environ.get("MONGO_DB", "network_ranger")
        auth_source = os.environ.get("MONGO_AUTHSOURCE", "admin")
        
        if user and password:
            uri = f"mongodb://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}?authSource={auth_source}"
        else:
            uri = f"mongodb://{host}:{port}/{db}"
    
    return MongoClient(uri)


def serialize_datetime(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_collection(db, name):
    """Export a collection to a list of documents."""
    return list(db[name].find())


def main():
    client = get_mongo_client()
    db_name = os.environ.get("MONGO_DB", "network_ranger")
    db = client[db_name]
    
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "database": db_name,
        "collections": {
            "users": export_collection(db, "users"),
            "guilds": export_collection(db, "guilds"),
            "config": export_collection(db, "config"),
        }
    }
    
    # Convert ObjectIds and other BSON types to strings
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(v) for v in obj]
        elif hasattr(obj, '__str__') and type(obj).__name__ == 'ObjectId':
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    data = convert(data)
    
    json.dump(data, sys.stdout, indent=2, default=serialize_datetime)
    print(file=sys.stderr)
    print(f"Exported {len(data['collections']['users'])} users", file=sys.stderr)
    print(f"Exported {len(data['collections']['guilds'])} guilds", file=sys.stderr)
    print(f"Exported {len(data['collections']['config'])} config entries", file=sys.stderr)


if __name__ == "__main__":
    main()
