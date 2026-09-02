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
    "Please retry in Ns" hint from the provider error body.
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
        max_retries: int = 1,
        retry_backoff_seconds: float = 1.0,
        fallback_models: list[str] | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._fallback_models = [m for m in (fallback_models or []) if m and m != model]
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url.strip().rstrip("/"),
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
        models_to_try = [self._model] + self._fallback_models
        last_error: Exception | None = None
        rate_limit_occurred = False

        for model_idx, target_model in enumerate(models_to_try):
            is_fallback = model_idx > 0
            if is_fallback:
                logger.info(
                    "Attempting GenAI fallback model '%s' (fallback %d/%d)",
                    target_model,
                    model_idx,
                    len(models_to_try) - 1,
                )

            payload: dict[str, Any] = {
                "model": target_model,
                "messages": self._build_messages(
                    system_instruction=system_instruction,
                    user_message=user_message,
                    conversation_history=conversation_history,
                ),
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
            }

            model_succeeded = False
            for attempt in range(self._max_retries + 1):
                try:
                    response = await self._client.post("/chat/completions", json=payload)
                except httpx.TimeoutException as exc:
                    logger.warning(
                        "GenAI provider timed out on model '%s' (attempt %d/%d)",
                        target_model,
                        attempt + 1,
                        self._max_retries + 1,
                    )
                    last_error = GenAITimeoutError(
                        f"GenAI provider timed out on model '{target_model}'"
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._retry_backoff * (attempt + 1))
                        continue
                    break
                except httpx.HTTPError as exc:
                    logger.warning(
                        "GenAI HTTP network error on model '%s': %s",
                        target_model,
                        exc,
                    )
                    last_error = GenAIProviderUnavailableError(
                        f"GenAI provider network failure on model '{target_model}'"
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._retry_backoff * (attempt + 1))
                        continue
                    break

                # Permanent Authentication / Authorization Errors (401, 403) FAIL FAST without fallback
                if response.status_code in (401, 403):
                    logger.error(
                        "GenAI provider authentication failed (HTTP %d). Check API key.",
                        response.status_code,
                    )
                    raise GenAIProviderError("GenAI provider rejected the credentials")

                # 429 Rate Limit / Quota Exceeded -> Retry if short wait, otherwise fallback
                if response.status_code == 429:
                    rate_limit_occurred = True
                    wait_seconds = _rate_limit_retry_seconds(
                        response, self._retry_backoff * (attempt + 1)
                    )
                    last_error = GenAIRateLimitError(
                        f"GenAI model '{target_model}' rate limit exceeded",
                        retry_after=wait_seconds,
                    )
                    if wait_seconds <= MAX_RATE_LIMIT_WAIT_SECONDS and attempt < self._max_retries:
                        logger.warning(
                            "GenAI model '%s' 429; retrying in %.1fs (attempt %d/%d)",
                            target_model,
                            wait_seconds,
                            attempt + 1,
                            self._max_retries,
                        )
                        await asyncio.sleep(wait_seconds)
                        continue
                    logger.warning(
                        "GenAI model '%s' rate-limited / quota exceeded (retry_after=%.1fs); moving to next model",
                        target_model,
                        wait_seconds,
                    )
                    break

                # 404 Model Not Available / 5xx Server Error -> Retry if transient, otherwise fallback
                if response.status_code in (404, 500, 502, 503, 504):
                    logger.warning(
                        "GenAI model '%s' returned HTTP %d. Attempting fallback model...",
                        target_model,
                        response.status_code,
                    )
                    last_error = GenAIProviderUnavailableError(
                        f"GenAI provider unavailable on model '{target_model}' (HTTP {response.status_code})"
                    )
                    if response.status_code >= 500 and attempt < self._max_retries:
                        await asyncio.sleep(self._retry_backoff * (attempt + 1))
                        continue
                    break

                if response.status_code >= 400:
                    logger.warning(
                        "GenAI provider rejected request on model '%s' (HTTP %d)",
                        target_model,
                        response.status_code,
                    )
                    last_error = GenAIProviderError(
                        f"GenAI provider rejected the request with HTTP {response.status_code}"
                    )
                    break

                # Successful response (HTTP 200)
                try:
                    body = response.json()
                except Exception as exc:
                    logger.warning("GenAI provider returned non-JSON for model '%s'", target_model)
                    last_error = GenAIInvalidResponseError("GenAI provider returned a non-JSON response")
                    break

                try:
                    content = body["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    logger.warning("GenAI provider response missing content for model '%s'", target_model)
                    last_error = GenAIInvalidResponseError("GenAI provider response is missing message content")
                    break

                if not content or not content.strip():
                    logger.warning("GenAI model '%s' returned empty content; trying fallback", target_model)
                    last_error = GenAIInvalidResponseError("GenAI provider response was empty")
                    break

                usage = body.get("usage") or {}
                final_model = body.get("model") or target_model
                logger.info(
                    "GenAI completion successful | model=%s (attempt %d/%d)",
                    final_model,
                    model_idx + 1,
                    len(models_to_try),
                )
                return ProviderCompletion(
                    content=content.strip(),
                    model=final_model,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                )

            # If this model did not succeed and there are more models to try, pause slightly before next model
            if model_idx < len(models_to_try) - 1:
                await asyncio.sleep(0.1)
                continue

        if last_error is not None:
            raise last_error
        if rate_limit_occurred:
            raise GenAIRateLimitError("All GenAI models in fallback chain were rate-limited")
        raise GenAIProviderUnavailableError(
            f"GenAI provider unavailable across all {len(models_to_try)} models"
        )
