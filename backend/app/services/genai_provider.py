"""G0 GenAI provider abstraction.

One stable internal interface (GenAIProvider) plus the default
OpenAI-compatible chat-completions adapter. Per the approved plan (§15)
the provider is a swappable adapter: trying OpenAI, Claude, Gemini or a
self-hosted model later is a configuration + adapter change, never a
rewrite of the rest of the application.

Only this module talks to an external LLM endpoint. Everything else in the
application depends solely on ``GenAIProvider`` and the ``GenAI*Error``
hierarchy below.

Safety rules:
  * API keys/credentials are injected via configuration - never embedded.
  * Error messages are generic and never echo request/response bodies or
    credentials (bodies may contain sensitive student content).
  * Timeout / retry / rate-limit / server-error handling lives here.
"""
from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _rate_limit_retry_seconds(response: httpx.Response, default: float) -> float:
    """Best-effort wait before retrying a rate-limited provider call.

    Prefers an explicit ``Retry-After`` header, otherwise parses the safe
    "Please retry in Ns" hint from the provider error body (used by Gemini).
    Falls back to ``default`` when no hint is available.
    """
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            retry_after = headers.get("retry-after")
        except (AttributeError, TypeError):
            retry_after = None
        if retry_after:
            try:
                return max(default, float(retry_after))
            except (TypeError, ValueError):
                pass
    try:
        body = response.json()
    except Exception:
        return default
    if isinstance(body, list) and body:
        body = body[0]
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if isinstance(message, str):
        match = re.search(r"retry in\s+([\d.]+)\s*s", message, re.IGNORECASE)
        if match:
            try:
                return max(default, float(match.group(1)))
            except ValueError:
                return default
    return default


class GenAIError(Exception):
    """Base class for all controlled GenAI failures."""


class GenAIConfigurationError(GenAIError):
    """Provider/model/credential configuration is missing or invalid."""


class GenAIContextError(GenAIError):
    """The request does not satisfy the structured verified-context contract."""


class GenAIProviderError(GenAIError):
    """Base class for provider-level failures."""


class GenAIProviderUnavailableError(GenAIProviderError):
    """Provider endpoint unreachable, or persistent server error."""


class GenAITimeoutError(GenAIProviderError):
    """Provider call exceeded the configured timeout."""


MAX_RATE_LIMIT_WAIT_SECONDS: float = 3.0


class GenAIRateLimitError(GenAIProviderError):
    """Provider returned a rate-limit / quota response."""

    def __init__(
        self,
        message: str = "GenAI provider rate limit exceeded",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GenAIInvalidResponseError(GenAIProviderError):
    """Provider returned an unparseable or malformed response."""


class ProviderCompletion:
    """Normalized, minimal provider output (no raw payload escaping)."""

    __slots__ = ("content", "model", "prompt_tokens", "completion_tokens")

    def __init__(
        self,
        content: str,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ):
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class GenAIProvider(ABC):
    """Stable internal LLM interface. Never extended outside this module."""

    provider_name: str

    @abstractmethod
    async def complete(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> ProviderCompletion:
        """Invoke the LLM and return a normalized completion.

        Raises GenAIProviderError subclasses on any failure. ``system_instruction``
        and ``user_message`` contain only grounded, verified text.
        """


class OpenAICompatibleProvider(GenAIProvider):
    """Chat-completions HTTP adapter (OpenAI, Azure OpenAI-compatible,
    vLLM/Ollama gateways, etc.). The default provider for G0."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        max_retries: int,
        retry_backoff_seconds: float,
    ):
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _build_messages(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_instruction}
        ]
        for message in conversation_history or []:
            if message.get("role") in ("user", "assistant"):
                messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": user_message})
        return messages

    async def complete(
        self,
        *,
        system_instruction: str,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> ProviderCompletion:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(
                system_instruction=system_instruction,
                user_message=user_message,
                conversation_history=conversation_history,
            ),
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                raise GenAITimeoutError(
                    f"GenAI provider timed out after {self._client.timeout.connect}s"
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))
                    continue
                break

            if response.status_code == 429:
                wait_seconds = _rate_limit_retry_seconds(
                    response, self._retry_backoff * (attempt + 1)
                )
                if wait_seconds > MAX_RATE_LIMIT_WAIT_SECONDS:
                    logger.warning(
                        "GenAI provider 429 rate limit retry-after (%.1fs) exceeds max wait threshold (%.1fs); failing fast.",
                        wait_seconds,
                        MAX_RATE_LIMIT_WAIT_SECONDS,
                    )
                    raise GenAIRateLimitError(
                        "GenAI provider rate limit exceeded",
                        retry_after=wait_seconds,
                    )

                if attempt < self._max_retries:
                    logger.warning(
                        "GenAI provider rate limit (HTTP 429); retrying in %.1fs "
                        "(attempt %d/%d)",
                        wait_seconds,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue
                raise GenAIRateLimitError(
                    "GenAI provider rate limit exceeded",
                    retry_after=wait_seconds,
                )
            if response.status_code in (401, 403):
                raise GenAIProviderError("GenAI provider rejected the credentials")
            if response.status_code >= 500:
                last_error = GenAIProviderUnavailableError(
                    f"GenAI provider server error (HTTP {response.status_code})"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_backoff * (attempt + 1))
                    continue
                break
            if response.status_code >= 400:
                raise GenAIProviderError(
                    f"GenAI provider rejected the request (HTTP {response.status_code})"
                )

            try:
                body = response.json()
            except Exception as exc:
                raise GenAIInvalidResponseError(
                    "GenAI provider returned a non-JSON response"
                ) from exc

            try:
                content = body["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise GenAIInvalidResponseError(
                    "GenAI provider response is missing message content"
                ) from exc

            usage = body.get("usage") or {}
            return ProviderCompletion(
                content=content,
                model=body.get("model") or self._model,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )

        raise GenAIProviderUnavailableError(
            f"GenAI provider unavailable after {self._max_retries + 1} attempt(s)"
        ) from last_error
