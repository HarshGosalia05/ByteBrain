"""Check columns and data for production students."""
import asyncio
import sys

sys.path.insert(0, "backend")
from app.core.database import db


async def run():
    await db.connect()
    pool = db.pool
    async with pool.acquire() as conn:
        # Check columns of student_subject_performance
        cols = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'student_subject_performance' ORDER BY ordinal_position"
        )
        print("student_subject_performance columns:")
        for c in cols:
            print(f"  {c['column_name']}")

        # Check columns of attendance
        cols2 = await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'attendance' ORDER BY ordinal_position"
        )
        print("\nattendance columns:")
        for c in cols2:
            print(f"  {c['column_name']}")

    await db.disconnect()


asyncio.run(run())
