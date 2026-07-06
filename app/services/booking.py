from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import settings
from app.core.db_resilience import apply_statement_timeout, execute_with_transient_retry
from app.core.exceptions import (
    BadRequestException,
    BookingConflictError,
    PropertyNotFoundException,
)
from app.core.logging import get_logger
from app.models.bookings import Booking
from app.models.enums import BookingStatus, PaymentStatus, UserRole
from app.models.properties import Property
from app.models.users import User
from app.schemas.booking import BookingCreate, BookingPayment, BookingReview, BookingUpdate
from app.schemas.pagination import keyset_filter, trim_keyset_lookahead

logger = get_logger(__name__)


def _apply_pricing_fields(pricing: dict, target: dict | Booking) -> None:
    """Helper to apply pricing fields to either a dictionary or a Booking object to avoid drift."""
    fields = ["nights", "base_amount", "taxes_amount", "service_charges", "total_amount"]
    if isinstance(target, dict):
        for field in fields:
            target[field] = pricing[field]
        target["discount_amount"] = pricing.get("discount_amount", 0.0)
    else:
        for field in fields:
            setattr(target, field, pricing[field])
        target.discount_amount = pricing.get("discount_amount", 0.0)


async def create_booking(db: AsyncSession, user_id: int, booking: BookingCreate):
    """Create a new booking"""
    booking_data = booking.model_dump()
    booking_data["user_id"] = user_id
    booking_data["booking_reference"] = f"BK{uuid.uuid4().hex[:8].upper()}"

    # Calculate nights using calendar dates (not raw timedelta seconds) so that
    # e.g. check-in at 14:00 and check-out at 11:00 next day correctly yields 1 night.
    check_in = booking_data["check_in_date"]
    check_out = booking_data["check_out_date"]
    check_in_date_only = check_in.date() if hasattr(check_in, "date") else check_in
    check_out_date_only = check_out.date() if hasattr(check_out, "date") else check_out
    nights = (check_out_date_only - check_in_date_only).days
    if nights <= 0:
        logger.warning(
            "Invalid date range in booking creation",
            extra={
                "user_id": user_id,
                "property_id": booking_data["property_id"],
                "check_in": str(check_in),
                "check_out": str(check_out),
                "reason": "invalid_date_range",
            },
        )
        raise BadRequestException(detail="Invalid date range: check-out must be after check-in")

    # Check availability before creating the booking
    availability = await check_availability(
        db,
        booking_data["property_id"],
        booking_data["check_in_date"].isoformat()
        if hasattr(booking_data["check_in_date"], "isoformat")
        else str(booking_data["check_in_date"]),
        booking_data["check_out_date"].isoformat()
        if hasattr(booking_data["check_out_date"], "isoformat")
        else str(booking_data["check_out_date"]),
        booking_data["guests"],
    )
    if not availability.get("available", False):
        reason = availability.get("reason", "Property not available for these dates")
        if reason == "Property not found":
            raise PropertyNotFoundException()
        raise BookingConflictError(detail=reason)

    # Calculate pricing before creating the booking
    pricing = await calculate_pricing(
        db,
        booking_data["property_id"],
        booking_data["check_in_date"],
        booking_data["check_out_date"],
        booking_data["guests"],
    )
    if isinstance(pricing, dict) and pricing.get("error"):
        raise BadRequestException(detail=pricing["error"])

    _apply_pricing_fields(pricing, booking_data)

    # Set initial statuses
    booking_data["booking_status"] = BookingStatus.pending
    booking_data["payment_status"] = PaymentStatus.pending

    db_booking = Booking(**booking_data)
    db.add(db_booking)
    await db.flush()
    await db.refresh(db_booking)
    logger.info(
        "Booking created",
        extra={
            "booking_id": db_booking.id,
            "booking_reference": db_booking.booking_reference,
            "user_id": user_id,
            "property_id": booking_data["property_id"],
            "check_in": str(booking_data["check_in_date"]),
            "check_out": str(booking_data["check_out_date"]),
            "nights": nights,
            "total_amount": float(booking_data["total_amount"]),
        },
    )
    return db_booking


async def get_booking(db: AsyncSession, booking_id: int):
    """Get a booking by ID"""
    stmt = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_bookings(
    db: AsyncSession,
    user_id: int,
    cursor_payload: dict,
    limit: int = 20,
    with_total: bool = False,
) -> tuple[list, dict | None, int | None]:
    """Get all bookings for a user (keyset-paginated)."""
    await apply_statement_timeout(db, settings.DB_READ_STATEMENT_TIMEOUT_MS)
    stmt = select(Booking).where(Booking.user_id == user_id)
    count_total = None
    if with_total:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await execute_with_transient_retry(
            db,
            lambda: db.execute(count_stmt),
            operation_name="booking_user_list_count",
        )
        count_total = count_result.scalar_one()
    predicate = keyset_filter(Booking.created_at, Booking.id, cursor_payload, descending=True)
    if predicate is not None:
        stmt = stmt.where(predicate)
    stmt = stmt.order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit + 1)
    result = await execute_with_transient_retry(
        db,
        lambda: db.execute(stmt),
        operation_name="booking_user_list_query",
    )
    rows = list(result.scalars().all())
    rows, next_payload = trim_keyset_lookahead(
        rows,
        limit=limit,
        sort_value=lambda booking: booking.created_at,
        item_id=lambda booking: booking.id,
    )
    return rows, next_payload, count_total


async def get_user_upcoming_bookings(
    db: AsyncSession,
    user_id: int,
    cursor_payload: dict,
    limit: int = 20,
    with_total: bool = False,
) -> tuple[list, dict | None, int | None]:
    """Get upcoming bookings for a user (keyset-paginated)."""
    await apply_statement_timeout(db, settings.DB_READ_STATEMENT_TIMEOUT_MS)
    now = datetime.now(timezone.utc)
    stmt = select(Booking).where(
        Booking.user_id == user_id,
        Booking.check_in_date > now,
        Booking.booking_status.in_([BookingStatus.confirmed, BookingStatus.pending]),
    )
    count_total = None
    if with_total:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await execute_with_transient_retry(
            db,
            lambda: db.execute(count_stmt),
            operation_name="booking_upcoming_list_count",
        )
        count_total = count_result.scalar_one()
    predicate = keyset_filter(Booking.check_in_date, Booking.id, cursor_payload, descending=False)
    if predicate is not None:
        stmt = stmt.where(predicate)
    stmt = stmt.order_by(Booking.check_in_date.asc(), Booking.id.asc()).limit(limit + 1)
    result = await execute_with_transient_retry(
        db,
        lambda: db.execute(stmt),
        operation_name="booking_upcoming_list_query",
    )
    rows = list(result.scalars().all())
    rows, next_payload = trim_keyset_lookahead(
        rows,
        limit=limit,
        sort_value=lambda booking: booking.check_in_date,
        item_id=lambda booking: booking.id,
    )
    return rows, next_payload, count_total


async def get_user_past_bookings(
    db: AsyncSession,
    user_id: int,
    cursor_payload: dict,
    limit: int = 20,
    with_total: bool = False,
) -> tuple[list, dict | None, int | None]:
    """Get past bookings for a user (keyset-paginated)."""
    await apply_statement_timeout(db, settings.DB_READ_STATEMENT_TIMEOUT_MS)
    now = datetime.now(timezone.utc)
    stmt = select(Booking).where(Booking.user_id == user_id, Booking.check_out_date < now)
    count_total = None
    if with_total:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await execute_with_transient_retry(
            db,
            lambda: db.execute(count_stmt),
            operation_name="booking_past_list_count",
        )
        count_total = count_result.scalar_one()
    predicate = keyset_filter(Booking.check_out_date, Booking.id, cursor_payload, descending=True)
    if predicate is not None:
        stmt = stmt.where(predicate)
    stmt = stmt.order_by(Booking.check_out_date.desc(), Booking.id.desc()).limit(limit + 1)
    result = await execute_with_transient_retry(
        db,
        lambda: db.execute(stmt),
        operation_name="booking_past_list_query",
    )
    rows = list(result.scalars().all())
    rows, next_payload = trim_keyset_lookahead(
        rows,
        limit=limit,
        sort_value=lambda booking: booking.check_out_date,
        item_id=lambda booking: booking.id,
    )
    return rows, next_payload, count_total


async def update_booking(
    db: AsyncSession,
    booking_id: int,
    booking_update: BookingUpdate,
    actor_role: UserRole | None = None,
):
    """Update a booking"""
    stmt = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stmt)
    booking = result.scalar_one_or_none()

    if booking:
        update_data = booking_update.model_dump(exclude_unset=True)

        # Privilege escalation check: only admins or agents can modify internal_notes
        is_staff = actor_role in (UserRole.admin, UserRole.agent) if actor_role else False
        if not is_staff:
            update_data.pop("internal_notes", None)

        # --- FIX: Recalculate pricing and availability if dates or guests change ---
        new_check_in = update_data.get("check_in_date", booking.check_in_date)
        new_check_out = update_data.get("check_out_date", booking.check_out_date)
        new_guests = update_data.get("guests", booking.guests)

        if (
            "check_in_date" in update_data
            or "check_out_date" in update_data
            or "guests" in update_data
        ):
            availability = await check_availability(
                db,
                booking.property_id,
                new_check_in.isoformat()
                if hasattr(new_check_in, "isoformat")
                else str(new_check_in),
                new_check_out.isoformat()
                if hasattr(new_check_out, "isoformat")
                else str(new_check_out),
                new_guests,
                exclude_booking_id=booking_id,
            )
            if not availability.get("available", False):
                reason = availability.get("reason", "Property not available for these dates")
                raise BookingConflictError(detail=reason)

            pricing = await calculate_pricing(
                db,
                booking.property_id,
                new_check_in,
                new_check_out,
                new_guests,
            )
            if isinstance(pricing, dict) and pricing.get("error"):
                raise BadRequestException(detail=pricing["error"])

            # If the price changes, revoke their paid/confirmed status so they have to pay the difference
            new_total = Decimal(str(pricing["total_amount"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            old_total = Decimal(str(booking.total_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if new_total != old_total:
                booking.payment_status = PaymentStatus.pending
                booking.booking_status = BookingStatus.pending

            _apply_pricing_fields(pricing, booking)
        # -------------------------------------------------------------------------

        for field, value in update_data.items():
            setattr(booking, field, value)

        await db.flush()
        await db.refresh(booking)

    return booking


async def cancel_booking(db: AsyncSession, booking_id: int, reason: str):
    """Cancel a booking.

    Guards:
    - Raises BadRequestException if the booking is already cancelled (idempotency).
    - Automatically marks payment as refunded and records refund_amount when the
      booking was already paid, so accounting is never left in an inconsistent state.
    """
    stmt = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(stmt)
    booking = result.scalar_one_or_none()

    if booking:
        # Guard: prevent double-cancellation
        if booking.booking_status == BookingStatus.cancelled:
            raise BadRequestException(detail="Booking is already cancelled")

        booking.booking_status = BookingStatus.cancelled
        booking.cancellation_date = datetime.now(timezone.utc)
        booking.cancellation_reason = reason

        # If the booking was paid, mark it as refunded so accounting stays consistent.
        # Actual gateway refund (e.g. Razorpay) must be triggered separately.
        if booking.payment_status == PaymentStatus.paid:
            booking.payment_status = PaymentStatus.refunded
            booking.refund_amount = booking.total_amount
            logger.info(
                "Paid booking cancelled — refund recorded",
                extra={
                    "booking_id": booking_id,
                    "user_id": booking.user_id,
                    "refund_amount": float(booking.total_amount),
                },
            )

        await db.flush()
        logger.info(
            "Booking cancelled",
            extra={"booking_id": booking_id, "user_id": booking.user_id, "reason": reason},
        )
        return True

    return False


async def process_payment(db: AsyncSession, payment_data: BookingPayment):
    """Process payment for a booking"""
    stmt = select(Booking).where(Booking.id == payment_data.booking_id)
    result = await db.execute(stmt)
    booking = result.scalar_one_or_none()

    if booking:
        # --- FIX: Prevent payment amount bypass ---
        payment_amount_dec = Decimal(str(payment_data.amount))
        booking_amount_dec = Decimal(str(booking.total_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if payment_amount_dec < booking_amount_dec:
            logger.warning(
                "Payment amount mismatch",
                extra={
                    "booking_id": booking.id,
                    "expected": float(booking.total_amount),
                    "received": float(payment_data.amount),
                },
            )
            raise BadRequestException(detail="Payment amount is insufficient")
        # ----------------------------------------

        booking.payment_status = PaymentStatus.paid
        booking.payment_method = payment_data.payment_method
        booking.transaction_id = payment_data.transaction_id
        booking.payment_date = datetime.now(timezone.utc)
        booking.booking_status = BookingStatus.confirmed
        await db.flush()
        logger.info(
            "Booking payment processed",
            extra={
                "booking_id": payment_data.booking_id,
                "payment_method": payment_data.payment_method,
                "transaction_id": payment_data.transaction_id,
            },
        )
        return True

    return False


async def add_review(db: AsyncSession, review_data: BookingReview, actor_id: int):
    """Add a guest review to a completed booking.

    Guards:
    - Only the guest who made the booking (booking.user_id) may submit a guest review.
    - The booking must be in `completed` or `checked_out` status (stay must have occurred).
    """
    from app.core.exceptions import ForbiddenException

    stmt = select(Booking).where(Booking.id == review_data.booking_id)
    result = await db.execute(stmt)
    booking = result.scalar_one_or_none()

    if not booking:
        return False

    # Only the actual guest can submit a guest review
    if booking.user_id != actor_id:
        raise ForbiddenException(detail="Only the guest who made this booking can submit a review")

    # Review only makes sense once the stay has occurred
    if booking.booking_status not in (
        BookingStatus.completed,
        BookingStatus.checked_out,
    ):
        raise BadRequestException(
            detail="Reviews can only be submitted for completed or checked-out bookings"
        )

    booking.guest_rating = review_data.guest_rating
    booking.guest_review = review_data.guest_review
    await db.flush()
    return True


async def check_availability(
    db: AsyncSession,
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int,
    exclude_booking_id: int | None = None,
):
    """Check if property is available for booking.

    Rules applied in order:
    1. Property must exist.
    2. Guest count must not exceed property max_occupancy (when set).
    3. No active (confirmed or pending) booking for this property may overlap
       with the requested date range — prevents double-booking.

    Args:
        exclude_booking_id: When re-checking availability during an update, pass
            the booking being updated so it is excluded from the overlap query.
    """
    # 1. Property existence check
    prop_stmt = select(Property).where(Property.id == property_id)
    prop_result = await db.execute(prop_stmt)
    property_obj = prop_result.scalar_one_or_none()

    if not property_obj:
        return {"available": False, "reason": "Property not found"}

    # 2. Guest count check
    if property_obj.max_occupancy and guests > property_obj.max_occupancy:
        logger.info(
            "Availability check: guests exceed max occupancy",
            extra={
                "property_id": property_id,
                "guests": guests,
                "max_occupancy": property_obj.max_occupancy,
                "check_in": check_in_date,
                "check_out": check_out_date,
            },
        )
        return {
            "available": False,
            "reason": f"Property can accommodate maximum {property_obj.max_occupancy} guests",
        }

    # 3. Date-overlap check — prevents double-booking
    # Two date ranges [A, B) and [C, D) overlap when A < D and C < B.

    # --- P1 Fix: Parse & normalize dates robustly ---
    # (a) Wrap in try/except so malformed strings return a structured error instead of a 500.
    # (b) Always attach UTC tzinfo so comparisons against DateTime(timezone=True) columns are
    #     unambiguous — fromisoformat on offset-less strings (e.g. "2026-01-10T12:00:00" or
    #     bare date strings) returns a naive datetime which PostgreSQL implicit-casts using the
    #     session timezone, causing incorrect overlap results.
    def _parse_and_normalize(date_val: str | datetime) -> datetime | None:
        if isinstance(date_val, datetime):
            dt = date_val
        else:
            try:
                dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
            except ValueError:
                return None
        # Ensure timezone-aware; assume UTC when no tzinfo is present.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    check_in_dt = _parse_and_normalize(check_in_date)
    check_out_dt = _parse_and_normalize(check_out_date)

    if check_in_dt is None or check_out_dt is None:
        return {"available": False, "reason": "Invalid date format"}

    # (c) Reject inverted or equal date ranges immediately — no DB round-trip needed.
    if check_in_dt >= check_out_dt:
        return {"available": False, "reason": "Invalid date range: check-out must be after check-in"}

    overlap_filters = [
        Booking.property_id == property_id,
        Booking.booking_status.in_([BookingStatus.confirmed, BookingStatus.pending]),
        Booking.check_in_date < check_out_dt,
        Booking.check_out_date > check_in_dt,
    ]
    if exclude_booking_id is not None:
        overlap_filters.append(Booking.id != exclude_booking_id)

    overlap_stmt = select(Booking.id).where(and_(*overlap_filters)).limit(1)
    overlap_result = await db.execute(overlap_stmt)
    if overlap_result.scalar_one_or_none() is not None:
        logger.info(
            "Availability check: date overlap detected",
            extra={
                "property_id": property_id,
                "check_in": check_in_date,
                "check_out": check_out_date,
            },
        )
        return {"available": False, "reason": "Property is already booked for these dates"}

    logger.info(
        "Availability check passed",
        extra={
            "property_id": property_id,
            "guests": guests,
            "max_occupancy": property_obj.max_occupancy,
            "check_in": check_in_date,
            "check_out": check_out_date,
        },
    )
    return {"available": True, "max_occupancy": property_obj.max_occupancy}


async def calculate_pricing(
    db: AsyncSession,
    property_id: int,
    check_in_date: datetime,
    check_out_date: datetime,
    guests: int,
):
    """Calculate pricing for a booking.

    - Uses `daily_rate` if available, otherwise falls back to `base_price`.
    - Computes taxes (18%) and service charges (5%).
    - Applies `discount_amount` (currently 0.0 by default).
    """
    stmt = select(Property).where(Property.id == property_id)
    result = await db.execute(stmt)
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        return {"error": "Property not found"}

    # Use calendar-date subtraction so times-of-day don't shorten the night count.
    # e.g. check-in 14:00 → check-out 11:00 next day = 1 calendar night (not 0 hours).
    ci_date = check_in_date.date() if hasattr(check_in_date, "date") else check_in_date
    co_date = check_out_date.date() if hasattr(check_out_date, "date") else check_out_date
    nights = (co_date - ci_date).days
    if nights <= 0:
        return {"error": "Invalid date range"}

    # Choose a per-night rate: prefer daily_rate, else derive from monthly_rent ÷ 30, else fall back to base_price ÷ 30
    if property_obj.daily_rate is not None:
        per_night_rate = float(property_obj.daily_rate)
    elif property_obj.monthly_rent is not None:
        per_night_rate = float(property_obj.monthly_rent) / 30
    else:
        per_night_rate = float(property_obj.base_price or 0.0) / 30

    if per_night_rate <= 0:
        return {"error": "Property has no valid rate configured"}

    base_amount = per_night_rate * nights

    # Placeholder discount logic
    discount_amount = 0.0

    # Calculate taxes and service charges on the discounted subtotal
    taxable_subtotal = max(base_amount - discount_amount, 0.0)
    taxes_amount = taxable_subtotal * settings.GST_RATE
    service_charges = taxable_subtotal * settings.SERVICE_CHARGE_RATE

    total_amount = taxable_subtotal + taxes_amount + service_charges

    return {
        "property_id": property_id,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "guests": guests,
        "nights": nights,
        "base_amount": base_amount,
        "taxes_amount": taxes_amount,
        "service_charges": service_charges,
        "discount_amount": discount_amount,
        "total_amount": total_amount,
        "breakdown": {
            "base_rate_per_night": per_night_rate,
            "total_nights": nights,
            "subtotal": base_amount,
            "discount": discount_amount,
            "taxes_18_percent": taxes_amount,
            "service_charge_5_percent": service_charges,
            "final_total": total_amount,
        },
    }


async def get_all_bookings(
    db: AsyncSession,
    *,
    cursor_payload: dict,
    limit: int = 20,
    with_total: bool = False,
    status: str | None = None,
    filter_agent_id: int | None = None,
    property_id: int | None = None,
    user_id: int | None = None,
) -> tuple[list, dict | None, int | None]:
    """Global bookings listing with optional filters and keyset pagination."""
    await apply_statement_timeout(db, settings.DB_READ_STATEMENT_TIMEOUT_MS)
    Owner = aliased(User)

    stmt = select(Booking)
    filters = []
    if status:
        filters.append(Booking.booking_status == status)
    if property_id:
        filters.append(Booking.property_id == property_id)
    if user_id:
        filters.append(Booking.user_id == user_id)

    if filter_agent_id is not None:
        stmt = (
            stmt.outerjoin(User, Booking.user_id == User.id)
            .outerjoin(Property, Booking.property_id == Property.id)
            .outerjoin(Owner, Property.owner_id == Owner.id)
        )
        filters.append(or_(User.agent_id == filter_agent_id, Owner.agent_id == filter_agent_id))
        # When both the booking user and the property owner share the same agent,
        # the OR join produces two rows for the same Booking.  DISTINCT prevents
        # duplicates from reaching the response and inflating pagination counts.
        stmt = stmt.distinct()

    if filters:
        stmt = stmt.where(and_(*filters))

    count_total = None
    if with_total:
        # Use subquery column reference to avoid cross-join/cartesian product with the base table.
        subq = stmt.subquery()
        count_stmt = select(func.count(subq.c.id)).select_from(subq)
        count_result = await execute_with_transient_retry(
            db,
            lambda: db.execute(count_stmt),
            operation_name="booking_all_list_count",
        )
        count_total = count_result.scalar_one()

    predicate = keyset_filter(Booking.created_at, Booking.id, cursor_payload, descending=True)
    if predicate is not None:
        stmt = stmt.where(predicate)
    stmt = stmt.order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit + 1)
    result = await execute_with_transient_retry(
        db,
        lambda: db.execute(stmt),
        operation_name="booking_all_list_query",
    )
    rows = list(result.scalars().all())
    rows, next_payload = trim_keyset_lookahead(
        rows,
        limit=limit,
        sort_value=lambda booking: booking.created_at,
        item_id=lambda booking: booking.id,
    )
    return rows, next_payload, count_total
