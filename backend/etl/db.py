"""Database access foundation: asyncpg pool + per-stage transaction boundary.

Reuses the existing application database configuration
(``app.core.config.settings.database_url``) and the asyncpg access model from
``app.core.database``. A standalone pool is created per ETL run because ETL is
a separate CLI process and must not depend on the FastAPI lifespan; this is the
same credential/access model as the running service (plan `01` §4.1).

The runner only creates a pool for ``--apply`` runs. Dry runs never touch the
database; stages receive ``pool=None`` and must use ``context.assert_writable()``
before any write. Per-stage ``transaction`` boundaries allow a future Load/Derive
stage to fail without partially corrupting canonical data — no broad transaction
wraps the whole pipeline.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncpg

from etl.config import etl_config
from etl.exceptions import EtlDatabaseError, EtlDryRunError


async def create_pool(min_size: int = 1, max_size: int = 10) -> asyncpg.Pool:
    """Create the asyncpg pool used by an ``--apply`` ETL run."""
    try:
        return await asyncpg.create_pool(
            dsn=etl_config.database_url,
            min_size=min_size,
            max_size=max_size,
        )
    except Exception as exc:  # noqa: BLE001 - fail loudly on any connect error
        raise EtlDatabaseError(f"Failed to create database pool: {exc}") from exc


@asynccontextmanager
async def transaction(
    pool: asyncpg.Pool,
    *,
    dry_run: bool = False,
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection inside a single transaction.

    Intended for future Load/Derive stages: commit on success, rollback on any
    failure, leaving no partial canonical state. Never usable during a dry run.
    """
    if dry_run:
        raise EtlDryRunError("Database writes are not permitted in dry-run mode")
    conn = await pool.acquire()
    try:
        async with conn.transaction():
            yield conn
    finally:
        await pool.release(conn)
