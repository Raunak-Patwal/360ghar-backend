"""Tests for auth dependency functions in app.api.api_v1.dependencies.auth.

These cover the response-code contract that distinguishes:
  * 401 TOKEN_INVALID           — token is bad / missing
  * 503 AUTH_PROVIDER_UNREACHABLE — Supabase host is unreachable
  * 401 AUTHENTICATION_FAILED   — unexpected exception during auth
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.api.api_v1.dependencies.auth import (
    get_current_user,
    get_current_user_optional,
    get_current_user_sse,
)
from app.core.auth import AuthFailureReason, _make_failure


def _user_payload(user_id: str | None = None) -> dict[str, Any]:
    return {
        "id": user_id or str(uuid4()),
        "email": "user@example.com",
        "phone": "+919876543210",
        "user_metadata": {},
        "app_metadata": {"provider": "phone", "providers": ["phone"]},
        "email_confirmed_at": None,
        "phone_confirmed_at": "2025-01-01T00:00:00Z",
    }


def _tagged(reason: AuthFailureReason, error: str = "boom") -> dict[str, Any]:
    return _make_failure(reason, error)


class TestGetCurrentUser503Path:
    """``get_current_user`` must return 503 when Supabase is unreachable."""

    @pytest.mark.asyncio
    async def test_provider_unreachable_returns_503(self):
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_tagged(AuthFailureReason.PROVIDER_UNREACHABLE)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=MagicMock(),
                    authorization="Bearer any_jwt_token",
                    db=db,
                )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "AUTH_PROVIDER_UNREACHABLE"
        assert exc_info.value.headers == {"Retry-After": "5"}

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=MagicMock(),
                    authorization="Bearer invalid_jwt_token",
                    db=db,
                )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "TOKEN_INVALID"

    @pytest.mark.asyncio
    async def test_provider_error_returns_401(self):
        """Non-retryable error → still 401 (not 503)."""
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(
                return_value=_tagged(AuthFailureReason.PROVIDER_ERROR, "weird")
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=MagicMock(),
                    authorization="Bearer any_jwt_token",
                    db=db,
                )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_authorization_returns_401(self):
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                request=MagicMock(),
                authorization=None,
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTH_HEADER_MISSING"

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_401(self):
        """Generic exceptions map to 401 AUTHENTICATION_FAILED, not 503."""
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(side_effect=RuntimeError("kaboom")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    request=MagicMock(),
                    authorization="Bearer any_jwt_token",
                    db=db,
                )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTHENTICATION_FAILED"

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        db = AsyncMock()
        db_user = MagicMock()
        db_user.id = 1

        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_user_payload()),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(return_value=db_user),
            ):
                result = await get_current_user(
                    request=MagicMock(),
                    authorization="Bearer valid_jwt_token",
                    db=db,
                )

        assert result is db_user
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transient_auth_db_error_returns_503(self):
        db = AsyncMock()

        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_user_payload()),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(
                    side_effect=Exception(
                        "(psycopg.errors.QueryCanceled) "
                        "canceling statement due to statement timeout"
                    )
                ),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(
                        request=MagicMock(),
                        authorization="Bearer valid_jwt_token",
                        db=db,
                    )

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "AUTH_DB_UNAVAILABLE"
        assert exc_info.value.headers == {"Retry-After": "5"}
        db.commit.assert_not_awaited()


class TestGetCurrentUserSSE503Path:
    """``get_current_user_sse`` must return 503 when Supabase is unreachable."""

    @pytest.mark.asyncio
    async def test_provider_unreachable_returns_503_with_retry_after(self):
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_tagged(AuthFailureReason.PROVIDER_UNREACHABLE)),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_sse(
                        request=MagicMock(),
                        authorization="Bearer any_token_xyz",
                        token=None,
                    )

        assert exc_info.value.status_code == 503
        assert exc_info.value.headers == {"Retry-After": "5"}

    @pytest.mark.asyncio
    async def test_query_param_token_unreachable_raises_503(self):
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_tagged(AuthFailureReason.PROVIDER_UNREACHABLE)),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_sse(
                        request=MagicMock(),
                        authorization=None,
                        token="query_token_123",
                    )

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_sse(
                    request=MagicMock(),
                    authorization="Bearer bad_token",
                    token=None,
                )

        assert exc_info.value.status_code == 401


class TestGetCurrentUserOptional503Path:
    """``get_current_user_optional`` returns ``None`` for unreachable / invalid.

    The optional dep must NOT surface 503 / 401 to the caller — it
    silently degrades to "not authenticated" so optional paths don't
    force re-login on a transient outage.
    """

    @pytest.mark.asyncio
    async def test_provider_unreachable_returns_none(self):
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_tagged(AuthFailureReason.PROVIDER_UNREACHABLE)),
        ):
            result = await get_current_user_optional(
                request=MagicMock(),
                authorization="Bearer any_jwt_token",
                db=db,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self):
        db = AsyncMock()
        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=None),
        ):
            result = await get_current_user_optional(
                request=MagicMock(),
                authorization="Bearer bad_token",
                db=db,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_no_authorization_returns_none(self):
        result = await get_current_user_optional(
            request=MagicMock(),
            authorization=None,
            db=AsyncMock(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_commits_auth_sync(self):
        db = AsyncMock()
        db_user = MagicMock()
        db_user.id = 1

        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_user_payload()),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(return_value=db_user),
            ):
                result = await get_current_user_optional(
                    request=MagicMock(),
                    authorization="Bearer valid_jwt_token",
                    db=db,
                )

        assert result is db_user
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auth_sync_failure_rolls_back_before_returning_none(self):
        db = AsyncMock()

        with patch(
            "app.api.api_v1.dependencies.auth.verify_supabase_token",
            new=AsyncMock(return_value=_user_payload()),
        ):
            with patch(
                "app.api.api_v1.dependencies.auth.get_or_create_user_from_supabase",
                new=AsyncMock(
                    side_effect=Exception(
                        "(psycopg.errors.QueryCanceled) "
                        "canceling statement due to statement timeout"
                    )
                ),
            ):
                result = await get_current_user_optional(
                    request=MagicMock(),
                    authorization="Bearer valid_jwt_token",
                    db=db,
                )

        assert result is None
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()


class TestDnsAndConnectErrorIntegration:
    """Sanity: the underlying Supabase call path catches real DNS failures."""

    @pytest.mark.asyncio
    async def test_gaierror_translates_to_tagged_failure(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = socket.gaierror("Name or service not known")

        with patch(
            "app.core.auth.get_supabase_auth_http_client", return_value=mock_client
        ):
            from app.core.auth import SupabaseClientManager

            result = await SupabaseClientManager().verify_token("any_token")

        assert result["reason"] == AuthFailureReason.PROVIDER_UNREACHABLE.value

    @pytest.mark.asyncio
    async def test_httpx_connect_error_translates_to_tagged_failure(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError(
            "[Errno 8] nodename nor servname provided, or not known"
        )

        with patch(
            "app.core.auth.get_supabase_auth_http_client", return_value=mock_client
        ):
            from app.core.auth import SupabaseClientManager

            result = await SupabaseClientManager().verify_token("any_token")

        assert result["reason"] == AuthFailureReason.PROVIDER_UNREACHABLE.value
