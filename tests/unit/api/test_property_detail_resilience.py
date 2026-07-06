from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import PropertyType, UserRole


class _AsyncContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _PropertyStub:
    property_type = PropertyType.apartment
    listing_preferences = None
    owner_id = 2

    def model_copy(self, *, update):
        self.update = update
        return self


@pytest.mark.asyncio
async def test_property_detail_view_count_failure_does_not_skip_user_enrichment():
    from app.api.api_v1.endpoints.properties import get_property_details

    db = MagicMock()
    db.begin_nested = MagicMock(side_effect=lambda: _AsyncContext())
    request = SimpleNamespace(headers={"user-agent": "Mozilla/5.0"})
    current_user = SimpleNamespace(id=1, role=UserRole.user.value)
    property_data = _PropertyStub()

    with patch(
        "app.api.api_v1.endpoints.properties.get_property",
        new=AsyncMock(return_value=property_data),
    ), patch(
        "app.api.api_v1.endpoints.properties.increment_property_view_count",
        new=AsyncMock(side_effect=Exception("statement timeout")),
    ), patch(
        "app.api.api_v1.endpoints.properties.get_user_like_for_property",
        new=AsyncMock(return_value=True),
    ) as mock_like, patch(
        "app.api.api_v1.endpoints.properties.get_user_property_visit_stats",
        new=AsyncMock(return_value={"count": 0, "next_date": None}),
    ) as mock_visit_stats:
        result = await get_property_details(
            property_id=123,
            request=request,
            current_user=current_user,
            db=db,
        )

    assert result is property_data
    mock_like.assert_awaited_once_with(db, current_user.id, 123)
    mock_visit_stats.assert_awaited_once_with(db, current_user.id, 123)
    assert db.begin_nested.call_count == 2
