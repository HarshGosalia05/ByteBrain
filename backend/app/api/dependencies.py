from fastapi import Depends, HTTPException, status
import asyncpg
from app.core.database import db
from app.core.security import get_current_user

async def get_db_pool() -> asyncpg.Pool:
    if not db.pool:
        await db.connect()
    if not db.pool:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection pool is not initialized")
    return db.pool

def require_student_role(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures the current user has the Student role"""
    if user.get("role") != "Student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access student resources"
        )
    return user

def require_faculty_role(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures the current user has the Faculty role"""
    if user.get("role") != "Faculty":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access faculty resources"
        )
    return user

def require_admin_role(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures the current user has the Admin role"""
    if user.get("role") != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access admin resources"
        )
    return user
