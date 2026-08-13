"""Authenticated unified Chat API endpoint (POST /api/v1/chat).

Handles:
  * Mandatory authentication via get_current_user.
  * Role and context ID extraction.
  * Delegating execution to ChatOrchestrator.
  * Returning structured ChatResponse.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_pool
from app.core.security import get_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_orchestrator import ChatOrchestrator

router = APIRouter()


def get_chat_orchestrator(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> ChatOrchestrator:
    return ChatOrchestrator(pool=pool)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
) -> ChatResponse:
    """Unified authenticated GenAI chat endpoint.

    Routes natural-language queries to allowlisted tools and generates grounded,
    verified-context-only answers.
    """
    return await orchestrator.process_chat(user=user, request=request)
