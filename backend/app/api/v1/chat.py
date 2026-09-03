"""Authenticated unified Chat API endpoint (POST /api/v1/chat).

Handles:
  * Mandatory authentication via get_current_user.
  * Per-user/IP rate limiting to protect the GenAI-backed endpoint.
  * Role and context ID extraction.
  * Delegating execution to ChatOrchestrator.
  * Returning structured ChatResponse.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import get_db_pool
from app.core.ratelimit import chat_limiter, chat_rate_limit_key
from app.core.security import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_orchestrator import ChatOrchestrator

router = APIRouter()


def get_chat_orchestrator(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ChatOrchestrator:
    return ChatOrchestrator(pool=pool)


async def _enforce_rate_limit(request: Request, user: dict) -> JSONResponse | None:
    """Return a 429 JSONResponse when the caller exceeds the rate limit."""
    client_host = request.client.host if request.client else None
    key = chat_rate_limit_key(user, client_host)
    allowed, retry_after = chat_limiter.allow(key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please wait a moment before sending another message.",
            },
            headers={"Retry-After": str(retry_after)},
        )
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    http_request: Request,
    user: dict = Depends(get_current_user),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
) -> ChatResponse | JSONResponse:
    """Unified authenticated GenAI chat endpoint.

    Routes natural-language queries to allowlisted tools and generates grounded,
    verified-context-only answers.
    """
    limited = await _enforce_rate_limit(http_request, user)
    if limited is not None:
        return limited
    return await orchestrator.process_chat(user=user, request=request)
