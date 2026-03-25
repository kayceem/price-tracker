"""
Database initialization script.
Run this to create all tables in the database.
"""
import asyncio
from src.database.session import engine, Base
from src.database.models import Scripts, ScriptDetails, User, MeroShareUser, Tracker


async def create_tables():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")


async def drop_tables():
    """Drop all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("Database tables dropped successfully!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        asyncio.run(drop_tables())

    asyncio.run(create_tables())
