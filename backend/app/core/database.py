import asyncpg
from typing import Optional
from app.core.config import settings

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=10,
                # Supabase uses Postgres which might require ssl mode depending on the setup.
                # Locally or standard configurations without ssl could break with ssl="require".
                # For this setup we will not enforce ssl="require" locally unless specified, 
                # but Supabase pool usually works fine without it if pgbouncer isn't enforcing it.
            )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

db = Database()
