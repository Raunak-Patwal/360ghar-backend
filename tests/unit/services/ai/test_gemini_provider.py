from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.base import AIMessage, AIProviderConfig, AIRole
from app.services.ai.providers.gemini import GeminiProvider


def _provider() -> GeminiProvider:
    return GeminiProvider(
        AIProviderConfig(
            api_key="secret-gemini-key",
            model="gemini-test",
        )
    )


def test_build_url_does_not_embed_api_key():
    provider = _provider()

    url = provider._build_url()

    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    assert "secret-gemini-key" not in url
    assert "?key=" not in url


@pytest.mark.asyncio
async def test_complete_sends_api_key_header_and_logs_sanitized_endpoint():
    provider = _provider()
    response = MagicMock()
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
    }
    provider._make_request = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with patch("app.services.ai.providers.gemini.logger") as mock_logger:
        result = await provider.complete([AIMessage(role=AIRole.USER, content="hello")])

    assert result == "ok"
    _, url, headers, _ = provider._make_request.await_args.args
    assert "secret-gemini-key" not in url
    assert headers["x-goog-api-key"] == "secret-gemini-key"
    log_extra = mock_logger.info.call_args.kwargs["extra"]
    assert log_extra["endpoint"] == url
    assert "secret-gemini-key" not in log_extra["endpoint"]


@pytest.mark.asyncio
async def test_complete_json_logs_sanitized_endpoint():
    provider = _provider()
    response = MagicMock()
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
    }
    provider._make_request = AsyncMock(return_value=response)  # type: ignore[method-assign]

    with patch("app.services.ai.providers.gemini.logger") as mock_logger:
        result = await provider.complete_json([AIMessage(role=AIRole.USER, content="hello")])

    assert result == {"ok": True}
    _, url, headers, _ = provider._make_request.await_args.args
    assert "secret-gemini-key" not in url
    assert headers["x-goog-api-key"] == "secret-gemini-key"
    log_extra = mock_logger.info.call_args.kwargs["extra"]
    assert log_extra["endpoint"] == url
    assert log_extra["json_mode"] is True
    assert "secret-gemini-key" not in log_extra["endpoint"]
