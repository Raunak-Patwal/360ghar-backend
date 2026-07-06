"""Supabase Realtime Broadcast publisher for flatmates events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.http import get_general_client
from app.core.logging import get_logger
from app.core.utils import utc_now_iso

logger = get_logger(__name__)

EVENT_NEW_MATCH = "new_match"
EVENT_NEW_MESSAGE = "new_message"
EVENT_CONVERSATION_UPDATED = "conversation_updated"
EVENT_VISIT_UPDATED = "visit_updated"
EVENT_LISTING_STATUS_CHANGED = "listing_status_changed"
EVENT_NEW_NOTIFICATION = "new_notification"

FLATMATES_REALTIME_EVENTS = (
    EVENT_NEW_MATCH,
    EVENT_NEW_MESSAGE,
    EVENT_CONVERSATION_UPDATED,
    EVENT_VISIT_UPDATED,
    EVENT_LISTING_STATUS_CHANGED,
    EVENT_NEW_NOTIFICATION,
)

_SESSION_EVENTS_KEY = "flatmates_realtime_events"
_SESSION_HOOK_KEY = "flatmates_realtime_after_commit_hooked"


@dataclass(frozen=True, slots=True)
class FlatmatesRealtimeEvent:
    user_id: int
    event_type: str
    payload: dict[str, Any]

    @property
    def topic(self) -> str:
        return flatmates_user_channel(self.user_id)


def flatmates_user_channel(user_id: int) -> str:
    return f"flatmates:user:{int(user_id)}"


def flatmates_realtime_config(user_id: int) -> dict[str, Any]:
    return {
        "provider": "supabase",
        "channel": flatmates_user_channel(user_id),
        "private": True,
        "events": list(FLATMATES_REALTIME_EVENTS),
    }


async def publish_flatmates_realtime_event(event_payload: FlatmatesRealtimeEvent) -> None:
    if not settings.FLATMATES_REALTIME_ENABLED:
        return

    topic = quote(event_payload.topic, safe="")
    event_type = quote(event_payload.event_type, safe="")
    url = (
        f"{settings.SUPABASE_URL.rstrip('/')}/realtime/v1/api/broadcast/"
        f"{topic}/events/{event_type}?private=true"
    )
    headers = {
        "apikey": settings.SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "type": event_payload.event_type,
        "data": event_payload.payload,
        "sent_at": utc_now_iso(),
    }

    try:
        response = await get_general_client().post(
            url,
            headers=headers,
            json=body,
            timeout=settings.SUPABASE_REALTIME_BROADCAST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Flatmates realtime broadcast failed",
            extra={
                "user_id": event_payload.user_id,
                "event_type": event_payload.event_type,
                "error": str(exc),
            },
        )


async def publish_flatmates_realtime_events(events: list[FlatmatesRealtimeEvent]) -> None:
    if not events:
        return
    await asyncio.gather(
        *(publish_flatmates_realtime_event(event_payload) for event_payload in events),
        return_exceptions=True,
    )


def _schedule_task(events: list[FlatmatesRealtimeEvent]) -> None:
    if not events:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as exc:
        logger.warning("Could not schedule flatmates realtime publish: %s", exc, exc_info=True)
        return
    loop.create_task(publish_flatmates_realtime_events(events))


def queue_flatmates_realtime_event(
    db: AsyncSession,
    *,
    user_id: int | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish now if outside a transaction, otherwise after commit."""
    if user_id is None:
        return
    event_payload = FlatmatesRealtimeEvent(
        user_id=int(user_id),
        event_type=event_type,
        payload=payload or {},
    )

    in_transaction = db.in_transaction()
    if in_transaction is not True:
        _schedule_task([event_payload])
        return

    session = db.sync_session
    events = session.info.setdefault(_SESSION_EVENTS_KEY, [])
    events.append(event_payload)

    if session.info.get(_SESSION_HOOK_KEY):
        return
    session.info[_SESSION_HOOK_KEY] = True

    @event.listens_for(session, "after_commit", once=True)
    def _after_commit(_session: Any) -> None:  # noqa: ANN001
        queued = list(_session.info.pop(_SESSION_EVENTS_KEY, []))
        _session.info.pop(_SESSION_HOOK_KEY, None)
        _schedule_task(queued)

    @event.listens_for(session, "after_rollback", once=True)
    def _after_rollback(_session: Any) -> None:  # noqa: ANN001
        _session.info.pop(_SESSION_EVENTS_KEY, None)
        _session.info.pop(_SESSION_HOOK_KEY, None)
