from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.services.flatmates.realtime import (
    EVENT_NEW_MATCH,
    FlatmatesRealtimeEvent,
    flatmates_realtime_config,
    flatmates_user_channel,
    publish_flatmates_realtime_event,
    queue_flatmates_realtime_event,
)


def test_flatmates_realtime_config_uses_private_user_channel() -> None:
    config = flatmates_realtime_config(42)

    assert config["provider"] == "supabase"
    assert config["channel"] == "flatmates:user:42"
    assert config["private"] is True
    assert EVENT_NEW_MATCH in config["events"]


@pytest.mark.asyncio
async def test_publish_flatmates_realtime_event_posts_private_broadcast() -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(return_value=response)

    with patch("app.services.flatmates.realtime.get_general_client", return_value=client):
        await publish_flatmates_realtime_event(
            FlatmatesRealtimeEvent(
                user_id=42,
                event_type=EVENT_NEW_MATCH,
                payload={"conversation_id": 99},
            )
        )

    client.post.assert_awaited_once()
    url = client.post.await_args.args[0]
    kwargs = client.post.await_args.kwargs
    assert "flatmates%3Auser%3A42" in url
    assert url.endswith(f"/events/{EVENT_NEW_MATCH}?private=true")
    assert kwargs["json"]["type"] == EVENT_NEW_MATCH
    assert kwargs["json"]["data"] == {"conversation_id": 99}
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_flatmates_user_channel() -> None:
    assert flatmates_user_channel(7) == "flatmates:user:7"


@pytest.mark.asyncio
async def test_queue_flatmates_realtime_event_publishes_after_commit() -> None:
    sync_session = Session()

    class FakeAsyncSession:
        def __init__(self, session: Session) -> None:
            self.sync_session = session

        def in_transaction(self) -> bool:
            return True

    with patch(
        "app.services.flatmates.realtime.publish_flatmates_realtime_events",
        new_callable=AsyncMock,
    ) as mock_publish:
        queue_flatmates_realtime_event(
            FakeAsyncSession(sync_session),  # type: ignore[arg-type]
            user_id=42,
            event_type=EVENT_NEW_MATCH,
            payload={"conversation_id": 99},
        )

        assert mock_publish.await_count == 0
        sync_session.commit()
        await asyncio.sleep(0)

    mock_publish.assert_awaited_once()
    queued = mock_publish.await_args.args[0]
    assert queued == [
        FlatmatesRealtimeEvent(
            user_id=42,
            event_type=EVENT_NEW_MATCH,
            payload={"conversation_id": 99},
        )
    ]
