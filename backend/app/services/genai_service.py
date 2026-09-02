"""G0 GenAI service: grounded, verified-context-only LLM orchestration.

Single reusable entry point that G1+ (Intent/Tool Router, grounded
response generation, prediction explanation, career guidance) will call.

The service:
  * accepts a structured GenAIRequest containing VERIFIED context only,
  * builds a grounding-enforcing system instruction from that context,
  * calls the configured GenAIProvider (timeout/retry handled by the
    provider adapter),
  * normalizes the response,
  * NEVER touches the database, repositories, SQL, or ML code.

Failures raise GenAI*Error with safe diagnostics; the service never
fabricates an answer when the provider fails and never exposes secrets
or stack traces to callers.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.genai import GenAIRequest, GenAIResponse
from app.services.genai_provider import (
    GenAIConfigurationError,
    GenAIContextError,
    GenAIError,
    GenAIProvider,
    GenAIProviderError,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)

MAX_CONVERSATION_MESSAGES = 20

GROUNDING_SYSTEM_INSTRUCTION = (
    "You are KenexAI, an academic guidance assistant. Follow these rules strictly:\n"
    "\n"
    "RULES:\n"
    "- Use ONLY the verified context data provided below. Never invent any data.\n"
    "- Reply in the same language as the user (English, Hindi, or Hinglish).\n"
    "- Never make up marks, percentages, SGPA, attendance, or prediction numbers.\n"
    "- Never claim information you were not given.\n"
    "- If context is missing, say: \"Required information is unavailable.\"\n"
    "- For predictions, say \"The model estimates...\", never \"You will...\".\n"
    "- For career advice, distinguish verified facts from suggestions.\n"
    "- Format with Markdown: bullet points, bold text. Be concise.\n"
    "\n"
    "VERIFIED CONTEXT (use only this data):\n"
)

_PROVIDER_TYPES: dict[str, type] = {"openai_compatible": OpenAICompatibleProvider}


class GenAIService:
    """Central, provider-agnostic LLM entry point (G0).

    ``provider`` is injectable for isolated tests; when omitted it is
    resolved once per call from ``settings.GENAI_*``.
    """

    def __init__(self, *, provider: GenAIProvider | None = None):
        self._provider = provider

    def _resolve_provider(self) -> GenAIProvider:
        if self._provider is not None:
            return self._provider

        if not settings.GENAI_PROVIDER:
            raise GenAIConfigurationError("GENAI_PROVIDER is not configured")
        provider_cls = _PROVIDER_TYPES.get(settings.GENAI_PROVIDER)
        if provider_cls is None:
            raise GenAIConfigurationError(
                f"Unsupported GENAI_PROVIDER {settings.GENAI_PROVIDER!r}"
            )
        if not settings.GENAI_API_KEY:
            raise GenAIConfigurationError("GENAI_API_KEY is not configured")
        primary_model = settings.GENAI_MODEL or settings.GENAI_PRIMARY_MODEL
        if not primary_model:
            raise GenAIConfigurationError("GENAI_MODEL or GENAI_PRIMARY_MODEL is not configured")

        fallback_models = list(settings.GENAI_FALLBACK_MODELS)
        if settings.GENAI_FALLBACK_MODEL_1:
            fallback_models.append(settings.GENAI_FALLBACK_MODEL_1)
        if settings.GENAI_FALLBACK_MODEL_2:
            fallback_models.append(settings.GENAI_FALLBACK_MODEL_2)

        return provider_cls(
            api_key=settings.GENAI_API_KEY,
            model=primary_model,
            base_url=settings.GENAI_BASE_URL,
            temperature=settings.GENAI_TEMPERATURE,
            max_tokens=settings.GENAI_MAX_TOKENS,
            timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
            max_retries=settings.GENAI_MAX_RETRIES,
            retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
            fallback_models=fallback_models,
        )

    @staticmethod
    def _validate_request(request: GenAIRequest) -> None:
        if not request.user_message or not request.user_message.strip():
            raise GenAIContextError("GenAI request is missing user_message")
        for context in request.verified_context:
            if not context.source or not context.source.strip():
                raise GenAIContextError(
                    "Every verified_context item must declare a source"
                )

    @staticmethod
    def _serialize_context(context) -> str:
        payload: dict = {"source": context.source, "data": context.data}
        if context.metadata:
            payload["metadata"] = context.metadata
        if context.timestamp is not None:
            payload["timestamp"] = context.timestamp.isoformat()
        if context.scope:
            payload["scope"] = context.scope
        if context.model is not None:
            payload["model"] = context.model.model_dump(exclude_none=True)
        if context.uncertainty is not None:
            payload["uncertainty"] = context.uncertainty.model_dump(exclude_none=True)
        return json.dumps(payload, sort_keys=True)

    def _build_system_instruction(self, request: GenAIRequest) -> str:
        role_header = f"\nAuthenticated User Role: {request.role}"
        if not request.verified_context:
            return (
                GROUNDING_SYSTEM_INSTRUCTION
                + "No verified context was provided for this request.\n"
                + "Note: This is a general conversation, greeting, or capability inquiry. "
                + "Be polite, helpful, and concise. Explain your capabilities for the user's role without fabricating student data."
                + role_header
            )
        context_lines = "\n".join(
            self._serialize_context(context) for context in request.verified_context
        )
        return (
            GROUNDING_SYSTEM_INSTRUCTION
            + context_lines
            + role_header
        )

    @staticmethod
    def _history_for_provider(request: GenAIRequest) -> list[dict[str, str]]:
        # Bound the prompt; conversation history is pass-through content only
        # and never carries role/scope authority (see ConversationMessage).
        return [
            {"role": message.role, "content": message.content}
            for message in request.conversation_history[-MAX_CONVERSATION_MESSAGES:]
        ]

    async def generate(self, request: GenAIRequest) -> GenAIResponse:
        """Generate a grounded response from a structured verified request."""
        self._validate_request(request)
        provider = self._resolve_provider()

        started = time.monotonic()
        try:
            completion = await provider.complete(
                system_instruction=self._build_system_instruction(request),
                user_message=request.user_message,
                conversation_history=self._history_for_provider(request),
            )
        except GenAIError as exc:
            logger.warning(
                "genai_request provider=%s status=failure error=%s latency_ms=%.1f",
                provider.provider_name,
                type(exc).__name__,
                (time.monotonic() - started) * 1000,
            )
            raise
        except Exception as exc:
            logger.warning(
                "genai_request provider=%s status=error error=%s latency_ms=%.1f",
                provider.provider_name,
                type(exc).__name__,
                (time.monotonic() - started) * 1000,
            )
            raise GenAIProviderError("GenAI provider call failed unexpectedly") from exc

        logger.info(
            "genai_request provider=%s model=%s status=success latency_ms=%.1f",
            provider.provider_name,
            completion.model or settings.GENAI_MODEL,
            (time.monotonic() - started) * 1000,
        )
        return GenAIResponse(
            content=completion.content,
            provider=provider.provider_name,
            model=completion.model or settings.GENAI_MODEL,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            generated_at=datetime.now(timezone.utc),
        )
