"""G0 GenAI provider adapter tests.

Verifies the OpenAI-compatible adapter against a MOCKED HTTP client:
success parsing, retry/rate-limit/server-error handling, timeouts, invalid
responses, payload structure, and that secrets never appear in payloads or
error messages. No external LLM API is ever contacted.
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from app.services.genai_provider import (
    GenAIInvalidResponseError,
    GenAIProviderError,
    GenAIProviderUnavailableError,
    GenAIRateLimitError,
    GenAITimeoutError,
    OpenAICompatibleProvider,
)


def run(coro):
    return asyncio.run(coro)


def _provider(max_retries=0, **overrides):
    args = dict(
        api_key="sk-test-secret-key",
        model="test-model",
        base_url="https://llm.example.test/v1",
        temperature=0.2,
        max_tokens=256,
        timeout_seconds=5.0,
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )
    args.update(overrides)
    return OpenAICompatibleProvider(**args)


class _Response:
    def __init__(self, status_code, body=None, json_raises=None):
        self.status_code = status_code
        self._body = body
        self._json_raises = json_raises

    def json(self):
        if self._json_raises is not None:
            raise self._json_raises
        return self._body


def _body(content="ok", model="returned-model"):
    return {
        "id": "x",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3},
    }


class _Patched:
    def __init__(self, post):
        self.patcher = mock.patch(
            "app.services.genai_provider.httpx.AsyncClient"
        )
        self.post = post

    def __enter__(self):
        self.client_class = self.patcher.start()
        self.client = self.client_class.return_value
        self.client.post = self.post
        return self.client

    def __exit__(self, *exc):
        self.patcher.stop()
        return False


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_success_path_normalizes_response(self):
        async def post(*args, **kwargs):
            return _Response(200, _body(content="grounded", model="m9"))

        with _Patched(AsyncMock(side_effect=post)) as client:
            result = run(_provider().complete(system_instruction="s", user_message="u"))
        self.assertEqual(result.content, "grounded")
        self.assertEqual(result.model, "m9")
        self.assertEqual(result.prompt_tokens, 7)
        self.assertEqual(result.completion_tokens, 3)

    def test_payload_never_contains_api_key(self):
        captured = {}

        async def post(*args, **kwargs):
            captured["payload"] = kwargs.get("json", {})
            return _Response(200, _body())

        with _Patched(AsyncMock(side_effect=post)):
            run(_provider().complete(system_instruction="s", user_message="u"))

        payload_json = str(captured["payload"])
        self.assertNotIn("sk-test-secret-key", payload_json)
        self.assertEqual(captured["payload"]["model"], "test-model")
        messages = captured["payload"]["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["role"], "user")
        self.assertNotIn("sql", payload_json)

    def test_retry_then_success(self):
        calls = {"n": 0}

        async def post(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _Response(429)
            return _Response(200, _body())

        with _Patched(AsyncMock(side_effect=post)):
            result = run(_provider(max_retries=1).complete(system_instruction="s", user_message="u"))
        self.assertEqual(result.content, "ok")
        self.assertEqual(calls["n"], 2)

    def test_rate_limit_after_retries(self):
        async def post(*args, **kwargs):
            return _Response(429)

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIRateLimitError):
                run(_provider(max_retries=1).complete(system_instruction="s", user_message="u"))

    def test_server_error_after_retries(self):
        async def post(*args, **kwargs):
            return _Response(503)

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIProviderUnavailableError):
                run(_provider(max_retries=1).complete(system_instruction="s", user_message="u"))

    def test_authentication_error_message_has_no_secret(self):
        async def post(*args, **kwargs):
            return _Response(401)

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIProviderError) as ctx:
                run(_provider().complete(system_instruction="s", user_message="u"))
        self.assertNotIn("sk-test-secret-key", str(ctx.exception))

    def test_timeout_raises_timeout_error(self):
        async def post(*args, **kwargs):
            raise httpx.ConnectTimeout("connection timed out")

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAITimeoutError):
                run(_provider().complete(system_instruction="s", user_message="u"))

    def test_network_error_after_retries(self):
        async def post(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIProviderUnavailableError):
                run(_provider(max_retries=1).complete(system_instruction="s", user_message="u"))

    def test_non_json_response_raises_invalid_response(self):
        async def post(*args, **kwargs):
            return _Response(200, json_raises=ValueError("no json"))

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIInvalidResponseError):
                run(_provider().complete(system_instruction="s", user_message="u"))

    def test_missing_content_raises_invalid_response(self):
        async def post(*args, **kwargs):
            return _Response(200, {"choices": [{"message": {}}]})

        with _Patched(AsyncMock(side_effect=post)):
            with self.assertRaises(GenAIInvalidResponseError):
                run(_provider().complete(system_instruction="s", user_message="u"))

    def test_credentials_are_configuration_only(self):
        provider = _provider(api_key="another-secret")
        self.assertEqual(provider._api_key, "another-secret")
        # the API key only ever appears in the Authorization header, never in payloads
        self.assertIsNotNone(provider._client)

    def test_primary_429_triggers_fallback_1_success(self):
        called_models = []

        async def post(path, json=None, **kwargs):
            model = json.get("model")
            called_models.append(model)
            if model == "primary-model":
                return _Response(429)
            return _Response(200, _body(content="fallback-1-content", model="fallback-1-model"))

        with _Patched(AsyncMock(side_effect=post)):
            provider = _provider(
                model="primary-model",
                fallback_models=["fallback-1-model", "fallback-2-model"],
            )
            result = run(provider.complete(system_instruction="s", user_message="u"))

        self.assertEqual(result.content, "fallback-1-content")
        self.assertEqual(result.model, "fallback-1-model")
        self.assertEqual(called_models, ["primary-model", "fallback-1-model"])

    def test_primary_and_fallback_1_429_triggers_fallback_2_success(self):
        called_models = []

        async def post(path, json=None, **kwargs):
            model = json.get("model")
            called_models.append(model)
            if model in ("primary-model", "fallback-1-model"):
                return _Response(429)
            return _Response(200, _body(content="fallback-2-content", model="fallback-2-model"))

        with _Patched(AsyncMock(side_effect=post)):
            provider = _provider(
                model="primary-model",
                fallback_models=["fallback-1-model", "fallback-2-model"],
            )
            result = run(provider.complete(system_instruction="s", user_message="u"))

        self.assertEqual(result.content, "fallback-2-content")
        self.assertEqual(result.model, "fallback-2-model")
        self.assertEqual(called_models, ["primary-model", "fallback-1-model", "fallback-2-model"])

    def test_all_models_rate_limited_raises_rate_limit_error(self):
        called_models = []

        async def post(path, json=None, **kwargs):
            called_models.append(json.get("model"))
            return _Response(429)

        with _Patched(AsyncMock(side_effect=post)):
            provider = _provider(
                model="primary-model",
                fallback_models=["fallback-1-model", "fallback-2-model"],
            )
            with self.assertRaises(GenAIRateLimitError):
                run(provider.complete(system_instruction="s", user_message="u"))

        self.assertEqual(called_models, ["primary-model", "fallback-1-model", "fallback-2-model"])

    def test_auth_error_fails_fast_without_trying_fallbacks(self):
        called_models = []

        async def post(path, json=None, **kwargs):
            called_models.append(json.get("model"))
            return _Response(401)

        with _Patched(AsyncMock(side_effect=post)):
            provider = _provider(
                model="primary-model",
                fallback_models=["fallback-1-model", "fallback-2-model"],
            )
            with self.assertRaises(GenAIProviderError):
                run(provider.complete(system_instruction="s", user_message="u"))

        # Exactly 1 call was made (no fallbacks attempted on credential rejection)
        self.assertEqual(called_models, ["primary-model"])


if __name__ == "__main__":
    unittest.main()
