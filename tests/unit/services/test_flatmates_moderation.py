"""Tests for flatmates moderation — report deduplication."""

from __future__ import annotations

import pytest

from app.models.enums import UserReportReason
from app.schemas.flatmates import ReportCreate
from app.services.flatmates.moderation import create_report


class TestCreateReportDedup:
    @pytest.mark.asyncio
    async def test_duplicate_open_report_returns_existing(
        self,
        db_session,
        test_user,
        test_user_2,
    ):
        """A second open report by the same reporter returns the existing row."""
        payload = ReportCreate(
            reported_user_id=test_user_2.id,
            reason=UserReportReason.spam,
            notes="spamming",
        )
        first = await create_report(db_session, test_user.id, payload)
        second = await create_report(db_session, test_user.id, payload)

        assert second.id == first.id
