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
    FailoverProvider,
    GenAIConfigurationError,
    GenAIContextError,
    GenAIError,
    GenAIProvider,
    GenAIProviderError,
    GroqProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)

MAX_CONVERSATION_MESSAGES = 20

GROUNDING_SYSTEM_INSTRUCTION = (
    "You are CampusX, an academic guidance assistant. Follow these rules strictly:\n"
    "\n"
    "RULES:\n"
    "- Use ONLY the verified context data provided below. Never invent any data.\n"
    "- Reply in the same language as the user (English, Hindi, Hinglish, or "
    "Gujarati/Romanized Gujarati). Language must NEVER change the data used; "
    "always answer from the verified context regardless of language.\n"
    "- Never make up marks, percentages, SGPA, attendance, or prediction numbers.\n"
    "- Never claim information you were not given.\n"
    "- If context is missing, say: \"Required information is unavailable.\"\n"
    "- For predictions, say \"The model estimates...\", never \"You will...\".\n"
    "- For career advice, distinguish verified facts from suggestions.\n"
    "- Format with Markdown: bullet points, bold text. Be concise.\n"
    "- When the verified context contains tabular data (lists of subjects, students,\n"
    "  attendance records, flagged/defaulters, marks, or timetable sessions), present\n"
    "  it as a proper Markdown table with a header row, aligned '---' separator, and\n"
    "  one row per record. Keep the column layout clean and readable - do not dump raw\n"
    "  JSON, do not cram multiple values into a single cell, and do not use bullets\n"
    "  for list-oriented data that fits a table.\n"
    "- For a timetable, use a table with Day/Time/Slot/Subject columns, grouping by\n"
    "  day; do not merge the whole week into one cell.\n"
    "- If asked for a student's name but no verified name is present, say the name "
    "is not available in the authorized context. Never substitute CGPA, semester, "
    "attendance, or any other metric for a name.\n"
    "- If the user asks about a specific semester but that semester's verified data "
    "is not present, say that semester's information is unavailable. Never silently "
    "substitute the current/latest semester, another subject, or another value.\n"
    "- Aggregate (average across all subjects/predictions) is only available if "
    "explicitly present in the verified context; otherwise say aggregate data is "
    "unavailable rather than computing it yourself.\n"
    "- A context item with source \"portal_context_snapshot\" is a user-portal "
    "overview (profile, subjects, attendance, predictions, class/institution "
    "metrics). Use it to give context-aware conversational answers (e.g. names, "
    "current semester, department, general state). For precise per-question facts "
    "prefer the specific tool source when present; if the tool source is absent, "
    "you may answer from the portal snapshot but keep the summary level.\n"
    "\n"
    "VERIFIED CONTEXT (use only this data):\n"
)

_PROVIDER_TYPES: dict[str, type] = {"openai_compatible": OpenAICompatibleProvider}


def _build_openai_compatible(model: str, *, fallback_models: list[str] | None = None) -> OpenAICompatibleProvider:
    """Build the legacy OpenAI-compatible provider from ``settings.GENAI_*``."""
    return OpenAICompatibleProvider(
        api_key=settings.GENAI_API_KEY,
        model=model,
        base_url=settings.GENAI_BASE_URL,
        temperature=settings.GENAI_TEMPERATURE,
        max_tokens=settings.GENAI_MAX_TOKENS,
        timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
        max_retries=settings.GENAI_MAX_RETRIES,
        retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
        fallback_models=fallback_models,
    )


def _legacy_primary_model() -> str:
    """Primary model when using the legacy single-provider path."""
    return settings.GENAI_MODEL or settings.GENAI_PRIMARY_MODEL


def _legacy_fallback_models() -> list[str]:
    fallback_models = list(settings.GENAI_FALLBACK_MODELS)
    if settings.GENAI_FALLBACK_MODEL_1:
        fallback_models.append(settings.GENAI_FALLBACK_MODEL_1)
    if settings.GENAI_FALLBACK_MODEL_2:
        fallback_models.append(settings.GENAI_FALLBACK_MODEL_2)
    return fallback_models


def _build_primary_provider(name: str) -> GenAIProvider:
    """Build the primary provider named by configuration."""
    if name == "groq":
        if not settings.GROQ_API_KEY:
            raise GenAIConfigurationError("GROQ_API_KEY is not configured")
        return GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            base_url=settings.GROQ_BASE_URL,
            temperature=settings.GENAI_TEMPERATURE,
            max_tokens=settings.GENAI_MAX_TOKENS,
            timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
            max_retries=settings.GENAI_MAX_RETRIES,
            retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
        )
    if name == "ollama":
        return OllamaProvider(
            model=settings.OLLAMA_MODEL,
            api_key="",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.GENAI_TEMPERATURE,
            max_tokens=settings.GENAI_MAX_TOKENS,
            timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
            max_retries=settings.GENAI_MAX_RETRIES,
            retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
        )
    if name == "openai_compatible":
        if not settings.GENAI_API_KEY:
            raise GenAIConfigurationError("GENAI_API_KEY is not configured")
        primary_model = _legacy_primary_model()
        if not primary_model:
            raise GenAIConfigurationError(
                "GENAI_MODEL or GENAI_PRIMARY_MODEL is not configured"
            )
        return _build_openai_compatible(
            primary_model, fallback_models=_legacy_fallback_models()
        )
    raise GenAIConfigurationError(f"Unsupported GENAI provider {name!r}")


def _build_fallback_provider(name: str) -> GenAIProvider | None:
    """Build the fallback provider named by configuration, or ``None`` if unset."""
    if not name:
        return None
    if name == "groq":
        if not settings.GROQ_API_KEY:
            raise GenAIConfigurationError("GROQ_API_KEY is not configured")
        return GroqProvider(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            base_url=settings.GROQ_BASE_URL,
            temperature=settings.GENAI_TEMPERATURE,
            max_tokens=settings.GENAI_MAX_TOKENS,
            timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
            max_retries=settings.GENAI_MAX_RETRIES,
            retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
        )
    if name == "ollama":
        return OllamaProvider(
            model=settings.OLLAMA_MODEL,
            api_key="",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.GENAI_TEMPERATURE,
            max_tokens=settings.GENAI_MAX_TOKENS,
            timeout_seconds=settings.GENAI_TIMEOUT_SECONDS,
            max_retries=settings.GENAI_MAX_RETRIES,
            retry_backoff_seconds=settings.GENAI_RETRY_BACKOFF_SECONDS,
        )
    if name == "openai_compatible":
        if not settings.GENAI_API_KEY:
            raise GenAIConfigurationError("GENAI_API_KEY is not configured")
        return _build_openai_compatible(
            _legacy_primary_model(), fallback_models=_legacy_fallback_models()
        )
    raise GenAIConfigurationError(f"Unsupported GENAI provider {name!r}")


class GenAIService:
    """Central, provider-agnostic LLM entry point (G0).

    ``provider`` is injectable for isolated tests; when omitted it is
    resolved once per call from ``settings.GENAI_PRIMARY_PROVIDER`` /
    ``settings.GENAI_FALLBACK_PROVIDER`` (with the legacy ``GENAI_PROVIDER``
    path retained for backward compatibility when the primary is unset).
    """

    def __init__(self, *, provider: GenAIProvider | None = None):
        self._provider = provider

    def _resolve_provider(self) -> GenAIProvider:
        if self._provider is not None:
            return self._provider

        primary_name = settings.GENAI_PRIMARY_PROVIDER or settings.GENAI_PROVIDER
        if not primary_name:
            raise GenAIConfigurationError(
                "GENAI_PRIMARY_PROVIDER or GENAI_PROVIDER is not configured"
            )

        if not settings.GENAI_PRIMARY_PROVIDER:
            provider_cls = _PROVIDER_TYPES.get(settings.GENAI_PROVIDER)
            if provider_cls is None:
                raise GenAIConfigurationError(
                    f"Unsupported GENAI_PROVIDER {settings.GENAI_PROVIDER!r}"
                )
            if not settings.GENAI_API_KEY:
                raise GenAIConfigurationError("GENAI_API_KEY is not configured")
            primary_model = _legacy_primary_model()
            if not primary_model:
                raise GenAIConfigurationError(
                    "GENAI_MODEL or GENAI_PRIMARY_MODEL is not configured"
                )
            return _build_openai_compatible(
                primary_model, fallback_models=_legacy_fallback_models()
            )

        primary = _build_primary_provider(primary_name)
        fallback = _build_fallback_provider(settings.GENAI_FALLBACK_PROVIDER)
        if fallback is None:
            return primary
        return FailoverProvider([primary, fallback])

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
        if request.page_context:
            role_header += (
                f"\nCurrent Page/Context: {request.page_context}\n"
                "The current page is context ONLY. Use it only to interpret "
                "vague references (\"this\", \"this prediction\", \"why is it low?\"). "
                "It never authorizes or fabricates data access - rely only on the "
                "verified context below."
            )
        if request.explicit_semester is not None:
            role_header += (
                f"\nThe user asked specifically about Semester {request.explicit_semester}.\n"
                "Answer ONLY using verified data for that semester. If that semester's "
                "data is NOT present, say the information for that semester is "
                "unavailable - never substitute another semester, subject, or value."
            )
        if request.format_instruction:
            role_header += f"\nFormatting instruction: {request.format_instruction}"
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
