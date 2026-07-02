from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.api_v1.endpoints import auth, users


@pytest.mark.asyncio
async def test_delete_my_account_converts_unexpected_service_error() -> None:
    current_user = SimpleNamespace(id=123)
    db = AsyncMock()

    with patch(
        "app.api.api_v1.endpoints.users.delete_user_account",
        new=AsyncMock(side_effect=Exception("Unexpected error")),
    ) as delete_user_account:
        with pytest.raises(HTTPException) as exc_info:
            await users.delete_my_account(current_user=current_user, db=db)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal server error. Please try again later."
    delete_user_account.assert_awaited_once_with(db, current_user)


@pytest.mark.asyncio
async def test_auth_delete_account_converts_unexpected_service_error() -> None:
    current_user = SimpleNamespace(id=456)
    db = AsyncMock()

    with patch(
        "app.api.api_v1.endpoints.auth.delete_user_account",
        new=AsyncMock(side_effect=Exception("Unexpected error")),
    ) as delete_user_account:
        with pytest.raises(HTTPException) as exc_info:
            await auth.delete_account(current_user=current_user, db=db)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Internal server error. Please try again later."
    delete_user_account.assert_awaited_once_with(db, current_user)
