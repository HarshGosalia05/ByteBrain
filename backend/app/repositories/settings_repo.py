import json
from typing import Any, Dict, Optional
import asyncpg


class SettingsRepository:
    """Row-scoped persistence for the shared Preference Engine.

    All reads/writes target the `preferences` JSONB column on `users` and are
    strictly scoped to the resolved `users.user_id` from the token (plan 13 §Role validation).
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        row = await self.pool.fetchrow(
            "SELECT preferences FROM users WHERE user_id = $1", user_id
        )
        if row is None:
            return None
        prefs = row["preferences"]
        if isinstance(prefs, str):
            prefs = json.loads(prefs)
        return prefs if isinstance(prefs, dict) else None

    async def update_preferences(self, user_id: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
        row = await self.pool.fetchrow(
            "UPDATE users SET preferences = $1 WHERE user_id = $2 RETURNING preferences",
            json.dumps(prefs),
            user_id,
        )
        if row is None:
            raise KeyError(f"User {user_id} not found")
        stored = row["preferences"]
        if isinstance(stored, str):
            stored = json.loads(stored)
        return stored

    async def resolve_user_id(self, faculty_id: str) -> Optional[str]:
        row = await self.pool.fetchrow(
            "SELECT user_id FROM users WHERE faculty_id = $1", faculty_id
        )
        return row["user_id"] if row else None

    async def resolve_user_id_by_student(self, student_id: str) -> Optional[str]:
        row = await self.pool.fetchrow(
            "SELECT user_id FROM users WHERE student_id = $1", student_id
        )
        return row["user_id"] if row else None

    async def resolve_user_id_by_username(self, username: str) -> Optional[str]:
        row = await self.pool.fetchrow(
            "SELECT user_id FROM users WHERE username = $1", username
        )
        return row["user_id"] if row else None
