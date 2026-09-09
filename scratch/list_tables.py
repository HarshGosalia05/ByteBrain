"""Check available tables and data for production students."""
import asyncio
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # List tables
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        )
        print("Tables:")
        for t in tables:
            print(f"  {t['table_name']}")

    await db.disconnect()


asyncio.run(run())
