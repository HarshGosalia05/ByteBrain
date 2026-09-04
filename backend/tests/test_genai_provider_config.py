"""Groq primary + Ollama fallback provider configuration tests.

Verifies the configuration-driven provider selection in GenAIService:
  * Groq is selected as the PRIMARY provider from GENAI_PRIMARY_PROVIDER,
  * Ollama is used as the FALLBACK provider on transient Groq failures,
  * missing GROQ_API_KEY fails closed (never fabricates / never calls out),
  * provider keys and secrets never leak into errors or logs.

External LLM endpoints are always mocked - no paid/external API is called.
"""
import asyncio
import logging
import sys
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import Settings, settings
from app.schemas.genai import GenAIRequest
from app.services.genai_provider import (
    GenAIRateLimitError,
    GenAIProviderError,
    GenAIProviderUnavailableError,
    FailoverProvider,
    GroqProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
)
from app.services.genai_service import (
    GenAIConfigurationError,
    GenAIService,
)


def run(coro):
    return asyncio.run(coro)


def _request(**overrides):
    base = dict(
        role="Student",
        user_context_id="STU000001",
        user_message="How is my attendance?",
    )
    base.update(overrides)
    return GenAIRequest(**base)


class _Response:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def _body(content="ok", model="groq-model"):
    return {
        "id": "x",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }


class _Patched:
    """Mocks httpx.AsyncClient and dispatches by requested provider URL/model."""

    def __init__(self, handler):
        self.patcher = mock.patch("app.services.genai_provider.httpx.AsyncClient")
        self.handler = handler

    def __enter__(self):
        self.client_class = self.patcher.start()
        self.client = self.client_class.return_value
        self.client.post = AsyncMock(side_effect=self.handler)
        return self.client

    def __exit__(self, *exc):
        self.patcher.stop()
        return False


class ConfigurationDefaultsTests(unittest.TestCase):
    def test_new_fields_have_safe_defaults(self):
        fresh = Settings(_env_file=())
        self.assertEqual(fresh.GENAI_PRIMARY_PROVIDER, "")
        self.assertEqual(fresh.GENAI_FALLBACK_PROVIDER, "")
        self.assertEqual(fresh.GROQ_API_KEY, "")
        self.assertEqual(fresh.GROQ_MODEL, "openai/gpt-oss-120b")
        self.assertEqual(fresh.GROQ_BASE_URL, "https://api.groq.com/openai/v1")
        self.assertEqual(fresh.OLLAMA_MODEL, "qwen2.5:3b")
        self.assertEqual(fresh.OLLAMA_BASE_URL, "http://localhost:11434/v1")

    def test_legacy_fields_unchanged_for_backward_compatibility(self):
        fresh = Settings(_env_file=())
        self.assertEqual(fresh.GENAI_PROVIDER, "openai_compatible")
        self.assertEqual(fresh.GENAI_BASE_URL, "https://api.openai.com/v1")

    def test_provider_classes_exist_with_expected_names(self):
        self.assertEqual(GroqProvider.provider_name, "groq")
        self.assertEqual(OllamaProvider.provider_name, "ollama")
        self.assertIsInstance(FailoverProvider, type)


class ProviderSelectionTests(unittest.TestCase):
    def test_legacy_path_used_when_primary_unset(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", ""):
            with mock.patch.object(settings, "GENAI_PROVIDER", "openai_compatible"):
                with mock.patch.object(settings, "GENAI_API_KEY", "k"):
                    with mock.patch.object(settings, "GENAI_MODEL", "m"):
                        service = GenAIService()
                        provider = service._resolve_provider()
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.provider_name, "openai_compatible")

    def test_primary_groq_fallback_ollama_builds_failover_chain(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "grok-key"):
                    service = GenAIService()
                    provider = service._resolve_provider()
        self.assertIsInstance(provider, FailoverProvider)
        self.assertEqual(
            provider.provider_names, ["groq", "ollama"]
        )

    def test_bravo_primary_unset_fallback_unset_is_legacy_single(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", ""):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", ""):
                with mock.patch.object(settings, "GENAI_PROVIDER", "openai_compatible"):
                    with mock.patch.object(settings, "GENAI_API_KEY", "k"):
                        with mock.patch.object(settings, "GENAI_MODEL", "m"):
                            provider = GenAIService()._resolve_provider()
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertNotIsInstance(provider, FailoverProvider)

    def test_unsupported_primary_provider_raises_configuration_error(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "bogus"):
            service = GenAIService()
            with self.assertRaises(GenAIConfigurationError):
                service._resolve_provider()


class MissingGroqKeyTests(unittest.TestCase):
    def test_primary_groq_with_empty_key_fails_closed(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", ""):
                    service = GenAIService()
                    with self.assertRaises(GenAIConfigurationError):
                        service._resolve_provider()

    def test_primary_groq_missing_key_generate_fails_closed(self):
        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GROQ_API_KEY", ""):
                service = GenAIService()
                with self.assertRaises(GenAIConfigurationError):
                    run(service.generate(_request()))


class GroqSuccessTests(unittest.TestCase):
    def test_groq_success_returns_groq_content(self):
        async def handler(*args, **kwargs):
            model = kwargs.get("json", {}).get("model")
            self.assertTrue(str(args[0]).endswith("/chat/completions"))
            self.assertEqual(model, "openai/gpt-oss-120b")
            return _Response(200, _body(content="from-groq", model="openai/gpt-oss-120b"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler) as client:
                        response = run(GenAIService().generate(_request()))
                    calls = client.post.await_args_list

        self.assertEqual(response.content, "from-groq")
        self.assertEqual(response.provider, "groq")
        self.assertEqual(len(calls), 1)


class FailoverTests(unittest.TestCase):
    def test_groq_timeout_falls_back_to_ollama(self):
        import httpx

        async def handler(*args, **kwargs):
            model = kwargs.get("json", {}).get("model")
            if model == "openai/gpt-oss-120b":
                raise httpx.ConnectTimeout("connection timed out")
            return _Response(200, _body(content="from-ollama", model="qwen2.5:3b"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler) as client:
                        response = run(GenAIService().generate(_request()))
                    calls = client.post.await_args_list

        self.assertEqual(response.content, "from-ollama")
        self.assertEqual(response.provider, "ollama")
        self.assertGreaterEqual(len(calls), 2)

    def test_groq_rate_limit_falls_back_to_ollama(self):
        async def handler(*args, **kwargs):
            model = kwargs.get("json", {}).get("model")
            if model == "openai/gpt-oss-120b":
                return _Response(429)
            return _Response(200, _body(content="from-ollama", model="qwen2.5:3b"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler) as client:
                        response = run(GenAIService().generate(_request()))
                    calls = client.post.await_args_list

        self.assertEqual(response.content, "from-ollama")
        self.assertEqual(response.provider, "ollama")
        self.assertGreaterEqual(len(calls), 2)

    def test_groq_unavailable_falls_back_to_ollama(self):
        async def handler(*args, **kwargs):
            model = kwargs.get("json", {}).get("model")
            if model == "openai/gpt-oss-120b":
                return _Response(503)
            return _Response(200, _body(content="from-ollama", model="qwen2.5:3b"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler) as client:
                        response = run(GenAIService().generate(_request()))
                    calls = client.post.await_args_list

        self.assertEqual(response.content, "from-ollama")
        self.assertEqual(response.provider, "ollama")
        self.assertGreaterEqual(len(calls), 2)

    def test_both_providers_unavailable_raises_controlled_error(self):
        import httpx

        async def handler(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler):
                        with self.assertRaises(GenAIProviderUnavailableError) as ctx:
                            run(GenAIService().generate(_request()))
        self.assertNotIn("groq-secret", str(ctx.exception))

    def test_both_providers_rate_limited_raises_rate_limit_error(self):
        async def handler(*args, **kwargs):
            return _Response(429)

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler):
                        with self.assertRaises(GenAIRateLimitError):
                            run(GenAIService().generate(_request()))

    def test_groq_auth_rejection_does_not_fall_back_to_ollama(self):
        async def handler(*args, **kwargs):
            model = kwargs.get("json", {}).get("model")
            if model == "openai/gpt-oss-120b":
                return _Response(401)
            return _Response(200, _body(content="should-not-happen", model="qwen2.5:3b"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "groq-secret"):
                    with _Patched(handler) as client:
                        with self.assertRaises(GenAIProviderError):
                            run(GenAIService().generate(_request()))
                    calls = client.post.await_args_list

        # Credential rejection must fail fast - no Ollama fallback attempted.
        self.assertEqual(len(calls), 1)


class SecretSafetyTests(unittest.TestCase):
    def test_groq_key_never_appears_in_payloads(self):
        captured = []

        async def handler(*args, **kwargs):
            captured.append(str(kwargs.get("json", {})))
            return _Response(200, _body(content="ok", model="m"))

        with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
            with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                with mock.patch.object(settings, "GROQ_API_KEY", "super-secret-groq-key-xyz"):
                    with _Patched(handler):
                        run(GenAIService().generate(_request()))

        for payload in captured:
            self.assertNotIn("super-secret-groq-key-xyz", payload)

    def test_groq_key_never_appears_in_logs_or_errors_on_failure(self):
        key = "gh_never_log_groq_zzz"
        captured = _RecordCapture()
        logger = logging.getLogger("app.services.genai_service")
        logger.addHandler(captured)
        try:
            async def handler(*args, **kwargs):
                return _Response(503)

            with mock.patch.object(settings, "GENAI_PRIMARY_PROVIDER", "groq"):
                with mock.patch.object(settings, "GENAI_FALLBACK_PROVIDER", "ollama"):
                    with mock.patch.object(settings, "GROQ_API_KEY", key):
                        with _Patched(handler):
                            with self.assertRaises(Exception) as ctx:
                                run(GenAIService().generate(_request()))
                            self.assertNotIn(key, str(ctx.exception))
        finally:
            logger.removeHandler(captured)
        for record in captured.records:
            self.assertNotIn(key, record)


class _RecordCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


if __name__ == "__main__":
    unittest.main()