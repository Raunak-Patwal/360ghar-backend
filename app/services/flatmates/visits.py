"""Flatmate visit scheduling helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.enums import VisitContext
from app.models.properties import Visit
from app.services.flatmates.realtime import EVENT_VISIT_UPDATED, queue_flatmates_realtime_event


async def update_visit_status(
    db: AsyncSession,
    user_id: int,
    visit_id: int,
    payload: Any,
) -> dict[str, Any]:
    result = await db.execute(select(Visit).where(Visit.id == visit_id))
    visit = result.scalar_one_or_none()
    if (
        visit is None
        or visit.visit_context != VisitContext.flatmate_meet.value
        or user_id not in {visit.user_id, visit.counterparty_user_id}
    ):
        raise BadRequestException(detail="Visit not found")

    new_status = payload.status.value if payload.status is not None else None
    new_date = payload.scheduled_date
    if new_status is not None:
        visit.status = new_status
    if new_date is not None:
        visit.scheduled_date = new_date
    await db.flush()

    effective_status = new_status or visit.status

    for uid in (visit.user_id, visit.counterparty_user_id):
        queue_flatmates_realtime_event(
            db,
            user_id=uid,
            event_type=EVENT_VISIT_UPDATED,
            payload={"visit_id": visit_id, "status": effective_status},
        )
    await db.commit()

    # Note: Push notifications for visit status changes are handled by
    # app.services.visit.update_visit (canonical endpoint). This stub
    # duplicates that endpoint and should be removed once consolidated.

    return {"id": visit_id, "status": effective_status, "updated": True}
