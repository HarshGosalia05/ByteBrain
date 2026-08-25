import asyncpg
from typing import Optional
from app.core.config import settings

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not self.pool:
            ssl_mode = "require" if ("supabase" in settings.DB_HOST or settings.DB_PORT == 6543) else None
            self.pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=5,
                ssl=ssl_mode,
                statement_cache_size=0,
            )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

db = Database()
