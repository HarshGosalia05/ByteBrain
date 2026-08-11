from fastapi import APIRouter
from app.api.v1 import admin, student, faculty
from app.api.dependencies import get_db_pool
from fastapi import Depends
import asyncpg

api_router = APIRouter()

@api_router.get("/health", tags=["system"])
async def health_check(pool: asyncpg.Pool = Depends(get_db_pool)):
    # Verify DB connectivity
    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return {
        "status": "healthy",
        "database": db_status
    }

@api_router.get("/", tags=["system"])
async def root_v1():
    return {
        "version": "v1",
        "service": "kenexai-backend"
    }

api_router.include_router(student.router, prefix="/students", tags=["students"])
api_router.include_router(faculty.router, prefix="/faculty", tags=["faculty"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
