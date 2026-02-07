#!/usr/bin/env python3
"""
Migration CLI for netranger-db.

Usage:
    nrdb-migrate status    # Show migration status
    nrdb-migrate migrate   # Apply pending migrations
    
Environment variables:
    DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
"""

import argparse
import asyncio
import sys

from .connection import Database
from .migrations import MigrationRunner


async def run_status(db: Database) -> None:
    """Show migration status."""
    runner = MigrationRunner(db)
    await runner.status()


async def run_migrate(db: Database) -> int:
    """Run pending migrations."""
    runner = MigrationRunner(db)
    return await runner.migrate()


async def async_main(args: argparse.Namespace) -> int:
    """Async main entry point."""
    db = Database.from_env()
    
    try:
        await db.connect()
        
        if args.command == "status":
            await run_status(db)
            return 0
        elif args.command == "migrate":
            await run_migrate(db)
            return 0
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            return 1
    finally:
        await db.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Database migration tool for Network Ranger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  DB_HOST      Database host (default: localhost)
  DB_PORT      Database port (default: 3306)
  DB_USER      Database user (default: netranger)
  DB_PASS      Database password
  DB_NAME      Database name (default: netranger)

Examples:
  nrdb-migrate status     Show pending migrations
  nrdb-migrate migrate    Apply all pending migrations
        """,
    )
    
    parser.add_argument(
        "command",
        choices=["status", "migrate"],
        help="Command to run",
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = asyncio.run(async_main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
