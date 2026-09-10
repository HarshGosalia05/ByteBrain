"""Authenticated unified Chat API endpoints.

  POST /api/v1/chat       - Send a message, get a grounded AI response
  GET  /api/v1/chat/context - Load role-specific portal data snapshot (ETL preload)
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.dependencies import get_db_pool
from app.core.ratelimit import chat_limiter, chat_rate_limit_key
from app.core.security import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.chat_context import ChatContextResponse
from app.services.chat_context_preloader import ChatContextPreloader
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


@router.get("/context", response_model=ChatContextResponse)
async def chat_context_endpoint(
    http_request: Request,
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ChatContextResponse | JSONResponse:
    """Load role-specific portal data snapshot for the chatbot (ETL preload).

    Runs at chat-open time. Returns a compact summary of the authenticated
    user's portal data (student / faculty / admin) so the AI assistant can
    give richer, context-aware answers without per-message data queries.
    """
    limited = await _enforce_rate_limit(http_request, user)
    if limited is not None:
        return limited
    role = user.get("role")
    if role == "Student":
        context_id = user.get("student_id") or user.get("user_id")
    elif role == "Faculty":
        context_id = user.get("faculty_id") or user.get("user_id")
    else:
        context_id = "admin"
    if not context_id:
        return JSONResponse(
            status_code=400,
            content={"detail": "Authenticated user identity is not available in the token."},
        )
    preloader = ChatContextPreloader(pool=pool)
    return await preloader.load(role=role, user_context_id=str(context_id))
