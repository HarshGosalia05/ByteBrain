"""Lightweight in-memory rate limiting for API endpoints.

Phase 1 stability fix. Uses a sliding-window / fixed-window counter keyed by
authenticated user id (falling back to client IP when no user is available) so
a single caller cannot flood the GenAI-backed chat endpoint.

Policy is read from settings (env-configurable) and applied per endpoint.
This is per-process; when running multiple uvicorn workers each worker keeps
its own counters. That is acceptable for the stability goal (bounding abuse)
and avoids an external store dependency.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class _Bucket:
    window_start: float = field(default_factory=time.time)
    count: int = 0


class RateLimiter:
    """Fixed-window in-memory limiter with a per-key lock."""

    def __init__(
        self,
        limit: int | None = None,
        window_seconds: int = 60,
        burst_limit: int | None = None,
    ) -> None:
        self._limit = limit if limit is not None else settings.CHAT_RATE_LIMIT_PER_MINUTE
        self._window_seconds = window_seconds
        self._burst_limit = (
            burst_limit
            if burst_limit is not None
            else settings.CHAT_RATE_LIMIT_BURST
        )
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = window_seconds * 10

    def _maybe_cleanup(self) -> None:
        """Evict stale buckets to prevent unbounded memory growth."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_cutoff = now - self._window_seconds * 3
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if bucket.window_start < stale_cutoff
        ]
        for key in stale_keys:
            del self._buckets[key]

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds) for a request keyed by ``key``."""
        now = time.time()
        with self._lock:
            self._maybe_cleanup()

            bucket = self._buckets.get(key)
            if bucket is None or (now - bucket.window_start) >= self._window_seconds:
                bucket = _Bucket(window_start=now, count=0)
                self._buckets[key] = bucket

            # Decide based on which threshold binds:
            #   burst_limit -> hard ceiling within the window (defaults equal to
            #   the per-minute limit unless explicitly lowered).
            ceil = min(self._limit, self._burst_limit)
            if bucket.count >= ceil:
                retry_after = max(1, int(self._window_seconds - (now - bucket.window_start)))
                return False, retry_after

            bucket.count += 1
            return True, 0

    def reset(self) -> None:
        """Clear all counters (used by tests between cases)."""
        with self._lock:
            self._buckets.clear()


# Shared singleton used by the chat endpoint.
chat_limiter = RateLimiter()


def chat_rate_limit_key(user: dict | None, client_host: str | None) -> str:
    """Build a stable rate-limit key from the authenticated user or client IP."""
    if user and user.get("user_id"):
        return f"user:{user.get('user_id')}"
    ip = client_host or "unknown"
    return f"ip:{ip}"
