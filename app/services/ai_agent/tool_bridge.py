"""
Tool bridge: adapts MCP tool logic into Pydantic AI tool functions.

Each tool receives ``RunContext[AgentDeps]`` which carries the authenticated
user and an async DB session.  The functions call the **same service layer**
that the MCP servers use, so authorisation rules are preserved.

Tools are grouped by category to mirror ``user_server.py`` and
``admin_server.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic_ai import RunContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.mcp.utils import (
    serialize_booking,
    serialize_lease,
    serialize_maintenance_request,
    serialize_property_basic,
    serialize_property_full,
    serialize_user_basic,
)
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Dependency container passed through RunContext
# ---------------------------------------------------------------------------

@dataclass
class AgentDeps:
    """Injected into every tool call via ``RunContext``."""

    user: Any  # SQLAlchemy User model instance
    db: AsyncSession
    user_role: str  # "user", "agent", "admin"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _user_schema(user: Any):
    """Convert a SQLAlchemy User to the Pydantic UserSchema expected by services."""
    from app.schemas.user import User as UserSchema
    return UserSchema.model_validate(user)


# ============================================================================
# USER TOOLS — Owner Property Management
# ============================================================================

async def owner_properties_list(
    ctx: RunContext[AgentDeps],
    page: int = 1,
    limit: int = 20,
    occupancy: Optional[str] = None,
    q: Optional[str] = None,
) -> dict[str, Any]:
    """List all properties owned by the current user with occupancy stats."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease
    from app.models.users import User as UserModel
    from app.services.pm_properties import list_managed_properties

    limit = min(max(1, limit), 100)
    db, user = ctx.deps.db, ctx.deps.user
    actor = _user_schema(user)

    properties = await list_managed_properties(
        db, actor=actor, owner_id=user.id, occupancy=occupancy, q=q,
        limit=limit, offset=(page - 1) * limit,
    )

    property_ids = [p.id for p in properties]
    active_lease_tenants: dict[int, str | None] = {}
    if property_ids:
        stmt = (
            select(Lease.property_id, UserModel.full_name)
            .join(UserModel, UserModel.id == Lease.tenant_user_id)
            .where(Lease.property_id.in_(property_ids), Lease.status == LeaseStatus.active)
        )
        for prop_id, tenant_name in (await db.execute(stmt)).all():
            if prop_id not in active_lease_tenants:
                active_lease_tenants[prop_id] = tenant_name

    items = []
    for prop in properties:
        item = serialize_property_basic(prop)
        tenant_name = active_lease_tenants.get(prop.id)
        item["has_active_lease"] = prop.id in active_lease_tenants
        if tenant_name:
            item["tenant_name"] = tenant_name
        items.append(item)

    occupied = sum(1 for p in items if p.get("has_active_lease"))
    return {
        "items": items,
        "total": len(items),
        "page": page,
        "stats": {
            "total_properties": len(items),
            "occupied": occupied,
            "vacant": len(items) - occupied,
            "total_monthly_income": sum(
                float(p.get("monthly_rent") or 0)
                for p in items if p.get("has_active_lease")
            ),
        },
    }


async def owner_properties_create(
    ctx: RunContext[AgentDeps],
    title: str,
    property_type: str,
    purpose: str,
    full_address: str,
    city: str,
    locality: str,
    latitude: float,
    longitude: float,
    base_price: float,
    description: Optional[str] = None,
    sub_locality: Optional[str] = None,
    pincode: Optional[str] = None,
    state: Optional[str] = None,
    monthly_rent: Optional[float] = None,
    daily_rate: Optional[float] = None,
    security_deposit: Optional[float] = None,
    maintenance_charges: Optional[float] = None,
    area_sqft: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    balconies: Optional[int] = None,
    parking_spaces: Optional[int] = None,
    floor_number: Optional[int] = None,
    total_floors: Optional[int] = None,
    max_occupancy: Optional[int] = None,
    minimum_stay_days: Optional[int] = None,
    main_image_url: Optional[str] = None,
    virtual_tour_url: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new property listing for the current user."""
    from app.models.enums import PropertyPurpose, PropertyType
    from app.schemas.property import PropertyCreate
    from app.services.pm_properties import create_managed_property

    db, user = ctx.deps.db, ctx.deps.user
    prop_type = PropertyType(property_type.lower())
    prop_purpose = PropertyPurpose(purpose.lower())

    data = PropertyCreate(
        title=title, description=description, property_type=prop_type,
        purpose=prop_purpose, full_address=full_address, city=city,
        locality=locality, sub_locality=sub_locality, pincode=pincode,
        state=state, latitude=latitude, longitude=longitude,
        base_price=base_price, monthly_rent=monthly_rent,
        daily_rate=daily_rate, security_deposit=security_deposit,
        maintenance_charges=maintenance_charges, area_sqft=area_sqft,
        bedrooms=bedrooms, bathrooms=bathrooms, balconies=balconies,
        parking_spaces=parking_spaces, floor_number=floor_number,
        total_floors=total_floors, max_occupancy=max_occupancy,
        minimum_stay_days=minimum_stay_days, main_image_url=main_image_url,
        virtual_tour_url=virtual_tour_url,
    )
    prop = await create_managed_property(db, actor=_user_schema(user), owner_id=user.id,
                                         property_data=data)
    await db.commit()
    return {"message": "Property created successfully", "property": serialize_property_basic(prop)}


async def owner_properties_get(
    ctx: RunContext[AgentDeps],
    property_id: int,
) -> dict[str, Any]:
    """Get detailed information about one of the user's properties."""
    from app.services.pm_properties import get_managed_property_detail

    db, user = ctx.deps.db, ctx.deps.user
    result = await get_managed_property_detail(db, actor=_user_schema(user),
                                               property_id=property_id)
    prop = result["property"]
    active_lease = result.get("active_lease")
    return {
        "property": serialize_property_full(prop),
        "active_lease": serialize_lease(active_lease) if active_lease else None,
    }


async def owner_properties_update(
    ctx: RunContext[AgentDeps],
    property_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    base_price: Optional[float] = None,
    monthly_rent: Optional[float] = None,
    daily_rate: Optional[float] = None,
    is_available: Optional[bool] = None,
    max_occupancy: Optional[int] = None,
    main_image_url: Optional[str] = None,
) -> dict[str, Any]:
    """Update one of the user's properties (partial update)."""
    from app.services.pm_authz import assert_can_access_property

    db, user = ctx.deps.db, ctx.deps.user
    prop = await assert_can_access_property(db, actor=_user_schema(user),
                                            property_id=property_id)
    updates = {
        "title": title, "description": description, "base_price": base_price,
        "monthly_rent": monthly_rent, "daily_rate": daily_rate,
        "is_available": is_available, "max_occupancy": max_occupancy,
        "main_image_url": main_image_url,
    }
    for field, value in updates.items():
        if value is not None:
            setattr(prop, field, value)
    await db.flush()
    await db.refresh(prop)
    await db.commit()
    return {"message": "Property updated successfully", "property": serialize_property_basic(prop)}


async def owner_properties_toggle_availability(
    ctx: RunContext[AgentDeps],
    property_id: int,
    is_available: bool,
) -> dict[str, Any]:
    """Toggle a property's availability status."""
    from app.services.pm_authz import assert_can_access_property

    db, user = ctx.deps.db, ctx.deps.user
    prop = await assert_can_access_property(db, actor=_user_schema(user),
                                            property_id=property_id)
    prop.is_available = is_available
    await db.flush()
    await db.commit()
    status = "available" if is_available else "unavailable"
    return {"message": f"Property marked as {status}", "property_id": property_id}


# ============================================================================
# USER TOOLS — Tenant
# ============================================================================

async def tenant_lease_current(
    ctx: RunContext[AgentDeps],
) -> dict[str, Any]:
    """Get the current active lease for the tenant."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease
    from app.models.properties import Property

    db, user = ctx.deps.db, ctx.deps.user
    stmt = (
        select(Lease)
        .where(Lease.tenant_user_id == user.id, Lease.status == LeaseStatus.active)
        .order_by(Lease.created_at.desc())
        .limit(1)
    )
    lease = (await db.execute(stmt)).scalar_one_or_none()
    if not lease:
        return {"lease": None, "message": "No active lease found."}

    prop = (await db.execute(
        select(Property).where(Property.id == lease.property_id)
    )).scalar_one_or_none()

    lease_data = serialize_lease(lease)
    if prop:
        lease_data["property"] = {
            "id": prop.id, "title": prop.title, "locality": prop.locality,
            "city": prop.city, "full_address": getattr(prop, "full_address", None),
        }
    return {"lease": lease_data}


async def tenant_rent_history(
    ctx: RunContext[AgentDeps],
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """Get rent payment history for the tenant."""
    from app.models.pm_finance import RentPayment
    from app.models.pm_leases import Lease

    limit = min(max(1, limit), 100)
    db, user = ctx.deps.db, ctx.deps.user

    lease_ids = [
        r[0] for r in (await db.execute(
            select(Lease.id).where(Lease.tenant_user_id == user.id)
        )).all()
    ]
    if not lease_ids:
        return {"payments": [], "total": 0, "total_collected": 0, "page": page}

    stmt = (
        select(RentPayment)
        .where(RentPayment.lease_id.in_(lease_ids))
        .order_by(RentPayment.paid_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    payments = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": p.id,
            "amount": float(p.amount_paid or 0),
            "payment_date": p.paid_at.isoformat() if p.paid_at else None,
            "payment_method": p.payment_method,
            "transaction_id": p.reference,
        }
        for p in payments
    ]
    return {
        "payments": items,
        "total": len(items),
        "total_collected": sum(p["amount"] for p in items),
        "page": page,
    }


async def tenant_maintenance_create(
    ctx: RunContext[AgentDeps],
    property_id: int,
    title: str,
    description: str,
    category: str,
    priority: str = "medium",
) -> dict[str, Any]:
    """Submit a maintenance request for a property the user is renting."""
    from app.models.enums import (
        LeaseStatus,
        MaintenanceCategory,
        MaintenanceRequestStatus,
        MaintenanceUrgency,
    )
    from app.models.pm_leases import Lease
    from app.models.pm_maintenance import MaintenanceRequest

    db, user = ctx.deps.db, ctx.deps.user
    cat = MaintenanceCategory(category.lower())
    urgency_map = {
        "low": MaintenanceUrgency.low, "medium": MaintenanceUrgency.medium,
        "high": MaintenanceUrgency.high, "urgent": MaintenanceUrgency.emergency,
        "emergency": MaintenanceUrgency.emergency,
    }
    urgency = urgency_map.get(priority.lower().strip())
    if urgency is None:
        return {"error": True, "message": f"Invalid priority: {priority}"}

    lease = (await db.execute(
        select(Lease).where(
            Lease.property_id == property_id,
            Lease.tenant_user_id == user.id,
            Lease.status == LeaseStatus.active,
        )
    )).scalar_one_or_none()
    if not lease:
        return {"error": True, "message": "You do not have an active lease for this property."}

    request = MaintenanceRequest(
        property_id=property_id, lease_id=lease.id, owner_id=lease.owner_id,
        tenant_user_id=user.id, title=title, description=description,
        category=cat, urgency=urgency, priority=priority.lower().strip(),
        request_status=MaintenanceRequestStatus.open,
    )
    db.add(request)
    await db.flush()
    await db.refresh(request)
    await db.commit()
    return {"request": serialize_maintenance_request(request)}


async def tenant_maintenance_list(
    ctx: RunContext[AgentDeps],
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
) -> dict[str, Any]:
    """List maintenance requests submitted by the tenant."""
    from app.models.enums import MaintenanceRequestStatus, WorkOrderStatus
    from app.models.pm_maintenance import MaintenanceRequest

    limit = min(max(1, limit), 100)
    db, user = ctx.deps.db, ctx.deps.user

    stmt = select(MaintenanceRequest).where(MaintenanceRequest.tenant_user_id == user.id)
    if status:
        sn = status.lower().strip()
        filter_map = {
            "open": MaintenanceRequest.request_status == MaintenanceRequestStatus.open,
            "in_progress": MaintenanceRequest.work_order_status == WorkOrderStatus.in_progress,
            "scheduled": MaintenanceRequest.scheduled_for.is_not(None),
            "completed": MaintenanceRequest.completed_at.is_not(None),
            "cancelled": MaintenanceRequest.work_order_status == WorkOrderStatus.cancelled,
        }
        if sn in filter_map:
            stmt = stmt.where(filter_map[sn])
        else:
            return {"error": True, "message": f"Invalid status: {status}"}

    stmt = stmt.order_by(MaintenanceRequest.created_at.desc()).offset((page - 1) * limit).limit(limit)
    items = [serialize_maintenance_request(r) for r in (await db.execute(stmt)).scalars().all()]
    return {"items": items, "total": len(items), "page": page}


# ============================================================================
# USER TOOLS — Bookings
# ============================================================================

async def bookings_check_availability(
    ctx: RunContext[AgentDeps],
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
) -> dict[str, Any]:
    """Check if a property is available for booking."""
    from app.services import booking as booking_svc

    db = ctx.deps.db
    result = await booking_svc.check_availability(db, property_id, check_in_date,
                                                   check_out_date, guests)
    return {
        "available": result.get("available", False),
        "reason": result.get("reason"),
        "max_occupancy": result.get("max_occupancy"),
    }


async def bookings_get_pricing(
    ctx: RunContext[AgentDeps],
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
) -> dict[str, Any]:
    """Get pricing details for a potential booking."""
    from app.services import booking as booking_svc

    db = ctx.deps.db
    check_in = datetime.fromisoformat(check_in_date)
    check_out = datetime.fromisoformat(check_out_date)
    pricing = await booking_svc.calculate_pricing(db, property_id, check_in, check_out, guests)
    if isinstance(pricing, dict) and pricing.get("error"):
        return {"error": True, "message": pricing["error"]}
    return {"pricing": pricing}


async def bookings_create(
    ctx: RunContext[AgentDeps],
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
    special_requests: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new booking for a short-stay property."""
    from app.schemas.booking import BookingCreate
    from app.services import booking as booking_svc

    db, user = ctx.deps.db, ctx.deps.user
    check_in = datetime.fromisoformat(check_in_date)
    check_out = datetime.fromisoformat(check_out_date)
    if check_out <= check_in:
        return {"error": True, "message": "Check-out must be after check-in."}

    availability = await booking_svc.check_availability(db, property_id, check_in_date,
                                                         check_out_date, guests)
    if not availability.get("available"):
        return {"error": True, "message": availability.get("reason", "Not available")}

    booking = await booking_svc.create_booking(
        db, user.id,
        BookingCreate(property_id=property_id, check_in_date=check_in,
                      check_out_date=check_out, guests=guests,
                      special_requests=special_requests),
    )
    await db.commit()
    return {"message": "Booking created successfully", "booking": serialize_booking(booking)}


async def bookings_list(
    ctx: RunContext[AgentDeps],
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
) -> dict[str, Any]:
    """List the current user's bookings."""
    from app.services import booking as booking_svc

    db, user = ctx.deps.db, ctx.deps.user
    limit = min(max(1, limit), 100)
    data = await booking_svc.get_user_bookings(db, user.id)
    bookings = data.get("bookings", [])
    if status:
        bookings = [b for b in bookings if b.booking_status == status]
    start = (page - 1) * limit
    items = [serialize_booking(b) for b in bookings[start:start + limit]]
    return {
        "total": data.get("total", 0), "upcoming": data.get("upcoming", 0),
        "completed": data.get("completed", 0), "cancelled": data.get("cancelled", 0),
        "bookings": items, "page": page,
    }


async def bookings_get(
    ctx: RunContext[AgentDeps],
    booking_id: int,
) -> dict[str, Any]:
    """Get details of a specific booking."""
    from app.models.properties import Property
    from app.services import booking as booking_svc

    db, user = ctx.deps.db, ctx.deps.user
    booking = await booking_svc.get_booking(db, booking_id)
    if not booking:
        return {"error": True, "message": f"Booking {booking_id} not found."}
    if booking.user_id != user.id:
        return {"error": True, "message": "You can only view your own bookings."}

    prop = (await db.execute(
        select(Property).where(Property.id == booking.property_id)
    )).scalar_one_or_none()
    return {
        "booking": serialize_booking(booking),
        "property": serialize_property_basic(prop) if prop else None,
    }


async def bookings_cancel(
    ctx: RunContext[AgentDeps],
    booking_id: int,
    reason: str,
) -> dict[str, Any]:
    """Cancel a booking."""
    from app.services import booking as booking_svc

    db, user = ctx.deps.db, ctx.deps.user
    booking = await booking_svc.get_booking(db, booking_id)
    if not booking:
        return {"error": True, "message": f"Booking {booking_id} not found."}
    if booking.user_id != user.id:
        return {"error": True, "message": "You can only cancel your own bookings."}
    if booking.booking_status in ("cancelled", "completed", "checked_out"):
        return {"error": True, "message": f"Cannot cancel (status: {booking.booking_status})"}

    await booking_svc.cancel_booking(db, booking_id, reason)
    await db.commit()
    return {"message": "Booking cancelled successfully", "booking_id": booking_id}


async def user_system_status(
    ctx: RunContext[AgentDeps],
) -> dict[str, Any]:
    """Get system status and available user features."""
    user = ctx.deps.user
    return {
        "status": "operational",
        "auth": {
            "status": "authenticated",
            "user": {
                "id": user.id,
                "role": getattr(user, "role", "user"),
                "full_name": getattr(user, "full_name", None),
            },
        },
    }


# ============================================================================
# ADMIN TOOLS — Agent Property Management
# ============================================================================

async def agent_properties_list(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
    page: int = 1,
    limit: int = 50,
    occupancy: Optional[str] = None,
    q: Optional[str] = None,
) -> dict[str, Any]:
    """List managed properties (agents see assigned owners; admins see all)."""
    from app.services.pm_properties import list_managed_properties

    db, user = ctx.deps.db, ctx.deps.user
    limit = min(max(1, limit), 100)
    actor = _user_schema(user)
    properties = await list_managed_properties(
        db, actor=actor, owner_id=owner_id, occupancy=occupancy, q=q,
        limit=limit, offset=(page - 1) * limit,
    )
    items = [serialize_property_basic(p) for p in properties]
    return {"items": items, "total": len(items), "page": page}


async def agent_properties_get(
    ctx: RunContext[AgentDeps],
    property_id: int,
) -> dict[str, Any]:
    """Get managed property details including owner, lease, and tenant info."""
    from app.services.pm_properties import get_managed_property_detail

    db, user = ctx.deps.db, ctx.deps.user
    result = await get_managed_property_detail(db, actor=_user_schema(user),
                                               property_id=property_id)
    prop = result["property"]
    lease = result.get("active_lease")
    return {
        "property": serialize_property_full(prop),
        "active_lease": serialize_lease(lease) if lease else None,
    }


async def agent_properties_create_for_owner(
    ctx: RunContext[AgentDeps],
    owner_id: int,
    title: str,
    property_type: str,
    purpose: str,
    full_address: str,
    city: str,
    locality: str,
    latitude: float,
    longitude: float,
    base_price: float,
    description: Optional[str] = None,
    monthly_rent: Optional[float] = None,
    area_sqft: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
) -> dict[str, Any]:
    """Create a property listing on behalf of an owner."""
    from app.models.enums import PropertyPurpose, PropertyType
    from app.schemas.property import PropertyCreate
    from app.services.pm_properties import create_managed_property

    db, user = ctx.deps.db, ctx.deps.user
    data = PropertyCreate(
        title=title, description=description,
        property_type=PropertyType(property_type.lower()),
        purpose=PropertyPurpose(purpose.lower()),
        full_address=full_address, city=city, locality=locality,
        latitude=latitude, longitude=longitude, base_price=base_price,
        monthly_rent=monthly_rent, area_sqft=area_sqft,
        bedrooms=bedrooms, bathrooms=bathrooms,
    )
    prop = await create_managed_property(db, actor=_user_schema(user), owner_id=owner_id,
                                         property_data=data)
    await db.commit()
    return {"message": "Property created for owner", "property": serialize_property_basic(prop)}


async def agent_properties_verify(
    ctx: RunContext[AgentDeps],
    property_id: int,
    is_verified: bool,
    verification_notes: Optional[str] = None,
) -> dict[str, Any]:
    """Mark a property as verified or unverified."""
    from app.services.pm_authz import assert_can_access_property

    db, user = ctx.deps.db, ctx.deps.user
    prop = await assert_can_access_property(db, actor=_user_schema(user),
                                            property_id=property_id)
    features = prop.features or {}
    features["verified"] = is_verified
    features["verification_notes"] = verification_notes
    features["verified_by"] = user.id
    prop.features = features
    await db.flush()
    await db.commit()
    return {"message": "Property verification updated", "property_id": property_id,
            "is_verified": is_verified}


# ============================================================================
# ADMIN TOOLS — Lease Management
# ============================================================================

async def agent_leases_list(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
    property_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """List leases, filterable by owner, property, and status."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease

    db = ctx.deps.db
    limit = min(max(1, limit), 100)
    stmt = select(Lease)
    if owner_id:
        stmt = stmt.where(Lease.owner_id == owner_id)
    if property_id:
        stmt = stmt.where(Lease.property_id == property_id)
    if status:
        stmt = stmt.where(Lease.status == LeaseStatus(status.lower()))
    stmt = stmt.order_by(Lease.created_at.desc()).offset((page - 1) * limit).limit(limit)
    leases = (await db.execute(stmt)).scalars().all()
    return {"items": [serialize_lease(l) for l in leases], "total": len(leases), "page": page}


async def agent_leases_create(
    ctx: RunContext[AgentDeps],
    property_id: int,
    tenant_user_id: int,
    start_date: str,
    end_date: str,
    monthly_rent: float,
    security_deposit: float = 0,
    payment_due_day: int = 1,
    grace_period_days: int = 5,
    terms: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new lease between an owner and a tenant."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease
    from app.models.properties import Property
    from app.services.user import get_user_by_id

    db, user = ctx.deps.db, ctx.deps.user
    prop = (await db.execute(
        select(Property).where(Property.id == property_id)
    )).scalar_one_or_none()
    if not prop:
        return {"error": True, "message": f"Property {property_id} not found"}

    tenant = await get_user_by_id(db, tenant_user_id)
    if not tenant:
        return {"error": True, "message": f"Tenant user {tenant_user_id} not found"}

    lease = Lease(
        property_id=property_id, owner_id=prop.owner_id,
        tenant_user_id=tenant_user_id,
        start_date=datetime.fromisoformat(start_date).date(),
        end_date=datetime.fromisoformat(end_date).date(),
        monthly_rent=monthly_rent, security_deposit=security_deposit,
        payment_due_day=payment_due_day, grace_period_days=grace_period_days,
        terms=terms, notes=notes, status=LeaseStatus.active,
    )
    db.add(lease)
    await db.flush()
    await db.refresh(lease)
    await db.commit()
    return {"message": "Lease created", "lease": serialize_lease(lease)}


async def agent_leases_terminate(
    ctx: RunContext[AgentDeps],
    lease_id: int,
    reason: str,
    termination_date: Optional[str] = None,
) -> dict[str, Any]:
    """Terminate an active lease."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease

    db = ctx.deps.db
    lease = (await db.execute(
        select(Lease).where(Lease.id == lease_id)
    )).scalar_one_or_none()
    if not lease:
        return {"error": True, "message": f"Lease {lease_id} not found"}

    lease.status = LeaseStatus.terminated
    existing_notes = lease.notes or ""
    lease.notes = f"{existing_notes}\n[Terminated] {reason}".strip()
    await db.flush()
    await db.commit()
    return {"message": "Lease terminated", "lease_id": lease_id}


# ============================================================================
# ADMIN TOOLS — Rent Collection
# ============================================================================

async def agent_rent_list_due(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
    property_id: Optional[int] = None,
    overdue_only: bool = False,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """List rent charges, optionally filtering for overdue ones."""
    from app.models.enums import LeaseStatus
    from app.models.pm_leases import Lease

    db = ctx.deps.db
    limit = min(max(1, limit), 100)
    stmt = select(Lease).where(Lease.status == LeaseStatus.active)
    if owner_id:
        stmt = stmt.where(Lease.owner_id == owner_id)
    if property_id:
        stmt = stmt.where(Lease.property_id == property_id)
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    leases = (await db.execute(stmt)).scalars().all()

    items = []
    now = datetime.now(timezone.utc)
    for lease in leases:
        due_day = getattr(lease, "payment_due_day", 1) or 1
        grace = getattr(lease, "grace_period_days", 0) or 0
        due_date = now.replace(day=min(due_day, 28))
        deadline = due_date.replace(day=min(due_day + grace, 28))
        is_overdue = now > deadline
        if overdue_only and not is_overdue:
            continue
        items.append({
            "lease_id": lease.id, "property_id": lease.property_id,
            "tenant_user_id": lease.tenant_user_id,
            "monthly_rent": float(lease.monthly_rent or 0),
            "payment_due_day": due_day,
            "is_overdue": is_overdue,
            "days_overdue": max(0, (now - deadline).days) if is_overdue else 0,
        })
    return {"items": items, "total": len(items), "page": page}


async def agent_rent_record_payment(
    ctx: RunContext[AgentDeps],
    lease_id: int,
    amount: float,
    payment_date: str,
    payment_method: str = "bank_transfer",
    transaction_reference: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Record a rent payment for a lease."""
    from app.models.pm_finance import RentPayment
    from app.models.pm_leases import Lease

    db = ctx.deps.db
    valid_methods = ("cash", "bank_transfer", "upi", "cheque", "online", "other")
    if payment_method not in valid_methods:
        return {"error": True, "message": f"Invalid payment method. Valid: {valid_methods}"}

    lease = (await db.execute(select(Lease).where(Lease.id == lease_id))).scalar_one_or_none()
    if not lease:
        return {"error": True, "message": f"Lease {lease_id} not found"}

    payment = RentPayment(
        lease_id=lease_id,
        amount_paid=amount,
        paid_at=datetime.fromisoformat(payment_date),
        payment_method=payment_method,
        reference=transaction_reference,
    )
    db.add(payment)
    await db.flush()
    await db.commit()
    return {"message": "Payment recorded", "payment_id": payment.id, "amount": amount}


# ============================================================================
# ADMIN TOOLS — Maintenance Management
# ============================================================================

async def agent_maintenance_list(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
    property_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """List maintenance requests across managed properties."""
    from app.models.pm_maintenance import MaintenanceRequest
    from app.models.properties import Property

    db = ctx.deps.db
    limit = min(max(1, limit), 100)
    stmt = select(MaintenanceRequest)
    if owner_id:
        stmt = stmt.join(Property, Property.id == MaintenanceRequest.property_id).where(
            Property.owner_id == owner_id
        )
    if property_id:
        stmt = stmt.where(MaintenanceRequest.property_id == property_id)
    # status filtering is approximate — mirrors MCP admin logic
    stmt = stmt.order_by(MaintenanceRequest.created_at.desc()).offset((page - 1) * limit).limit(limit)
    items = [serialize_maintenance_request(r) for r in (await db.execute(stmt)).scalars().all()]
    return {"items": items, "total": len(items), "page": page}


async def agent_maintenance_update_status(
    ctx: RunContext[AgentDeps],
    request_id: int,
    status: str,
    notes: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    vendor_name: Optional[str] = None,
    vendor_contact: Optional[str] = None,
    estimated_cost: Optional[float] = None,
    actual_cost: Optional[float] = None,
) -> dict[str, Any]:
    """Update the status of a maintenance request."""
    from app.models.enums import MaintenanceRequestStatus, WorkOrderStatus
    from app.models.pm_maintenance import MaintenanceRequest

    db = ctx.deps.db
    req = (await db.execute(
        select(MaintenanceRequest).where(MaintenanceRequest.id == request_id)
    )).scalar_one_or_none()
    if not req:
        return {"error": True, "message": f"Maintenance request {request_id} not found"}

    status_norm = status.lower().strip()
    if status_norm == "in_progress":
        req.work_order_status = WorkOrderStatus.in_progress
    elif status_norm == "scheduled":
        req.work_order_status = WorkOrderStatus.in_progress
        if scheduled_date:
            req.scheduled_for = datetime.fromisoformat(scheduled_date)
    elif status_norm == "completed":
        req.request_status = MaintenanceRequestStatus.resolved
        req.completed_at = datetime.now(timezone.utc)
    elif status_norm == "cancelled":
        req.work_order_status = WorkOrderStatus.cancelled

    if vendor_name:
        req.vendor_name = vendor_name
    if vendor_contact:
        req.vendor_contact = vendor_contact
    if estimated_cost is not None:
        req.estimated_cost = estimated_cost
    if actual_cost is not None:
        req.actual_cost = actual_cost
    if notes:
        req.completion_notes = notes

    await db.flush()
    await db.commit()
    return {"message": f"Maintenance request updated to {status_norm}", "request_id": request_id}


# ============================================================================
# ADMIN TOOLS — Booking Management
# ============================================================================

async def agent_bookings_list_all(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
    property_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """List all bookings across managed properties."""
    from app.models.bookings import Booking
    from app.models.properties import Property

    db = ctx.deps.db
    limit = min(max(1, limit), 100)
    stmt = select(Booking)
    if owner_id:
        stmt = stmt.join(Property, Property.id == Booking.property_id).where(
            Property.owner_id == owner_id
        )
    if property_id:
        stmt = stmt.where(Booking.property_id == property_id)
    if status:
        stmt = stmt.where(Booking.booking_status == status)
    stmt = stmt.order_by(Booking.created_at.desc()).offset((page - 1) * limit).limit(limit)
    items = [serialize_booking(b) for b in (await db.execute(stmt)).scalars().all()]
    return {"items": items, "total": len(items), "page": page}


async def agent_bookings_update_status(
    ctx: RunContext[AgentDeps],
    booking_id: int,
    status: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Update the status of a booking."""
    from app.models.bookings import Booking

    db = ctx.deps.db
    valid = ("confirmed", "checked_in", "checked_out", "cancelled", "completed")
    if status not in valid:
        return {"error": True, "message": f"Invalid status. Valid: {valid}"}

    booking = (await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )).scalar_one_or_none()
    if not booking:
        return {"error": True, "message": f"Booking {booking_id} not found"}

    booking.booking_status = status
    if notes:
        booking.internal_notes = notes
    if status == "cancelled":
        booking.cancellation_date = datetime.now(timezone.utc)
        booking.cancellation_reason = notes
    await db.flush()
    await db.commit()
    return {"message": f"Booking updated to {status}", "booking_id": booking_id}


# ============================================================================
# ADMIN TOOLS — Dashboard
# ============================================================================

async def agent_dashboard_overview(
    ctx: RunContext[AgentDeps],
    owner_id: Optional[int] = None,
) -> dict[str, Any]:
    """Get an overview dashboard: occupancy, rent, maintenance, bookings."""
    from app.models.bookings import Booking
    from app.models.enums import LeaseStatus, MaintenanceRequestStatus
    from app.models.pm_leases import Lease
    from app.models.pm_maintenance import MaintenanceRequest
    from app.models.properties import Property

    db = ctx.deps.db
    prop_filter = select(Property.id)
    if owner_id:
        prop_filter = prop_filter.where(Property.owner_id == owner_id)

    total_props = (await db.execute(
        select(func.count()).select_from(prop_filter.subquery())
    )).scalar() or 0

    active_leases_count = (await db.execute(
        select(func.count(Lease.id)).where(
            Lease.status == LeaseStatus.active,
            *([Lease.owner_id == owner_id] if owner_id else []),
        )
    )).scalar() or 0

    open_maintenance = (await db.execute(
        select(func.count(MaintenanceRequest.id)).where(
            MaintenanceRequest.request_status == MaintenanceRequestStatus.open,
            *([MaintenanceRequest.owner_id == owner_id] if owner_id else []),
        )
    )).scalar() or 0

    monthly_rent = (await db.execute(
        select(func.coalesce(func.sum(Lease.monthly_rent), 0)).where(
            Lease.status == LeaseStatus.active,
            *([Lease.owner_id == owner_id] if owner_id else []),
        )
    )).scalar() or 0

    occupancy = (active_leases_count / total_props * 100) if total_props else 0

    return {
        "total_properties": total_props,
        "active_leases": active_leases_count,
        "occupancy_rate": round(occupancy, 1),
        "open_maintenance_requests": open_maintenance,
        "monthly_rent_expected": float(monthly_rent),
    }


async def admin_system_status(
    ctx: RunContext[AgentDeps],
) -> dict[str, Any]:
    """Admin system status with role and feature info."""
    user = ctx.deps.user
    return {
        "status": "operational",
        "auth": {
            "status": "authenticated",
            "user": {
                "id": user.id,
                "role": getattr(user, "role", "user"),
                "full_name": getattr(user, "full_name", None),
            },
        },
        "access_level": "full" if getattr(user, "role", "") == "admin" else "agent_scope",
    }


# ============================================================================
# ============================================================================
# GUEST TOOLS — Public property discovery (no auth required)
# ============================================================================

async def guest_property_search(
    ctx: RunContext[AgentDeps],
    query: Optional[str] = None,
    city: Optional[str] = None,
    locality: Optional[str] = None,
    property_type: Optional[str] = None,
    purpose: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    bedrooms_min: Optional[int] = None,
    bedrooms_max: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """Search for properties with optional filters. No authentication required."""
    from app.schemas.property import UnifiedPropertyFilter
    from app.services.property import get_unified_properties_optimized

    limit = min(max(1, limit), 50)
    page = max(1, page)

    filter_data: dict[str, Any] = {}
    if query:
        filter_data["search_query"] = query
    if city:
        filter_data["city"] = city
    if locality:
        filter_data["locality"] = locality
    if property_type:
        filter_data["property_type"] = property_type
    if purpose:
        filter_data["purpose"] = purpose
    if price_min is not None:
        filter_data["price_min"] = price_min
    if price_max is not None:
        filter_data["price_max"] = price_max
    if bedrooms_min is not None:
        filter_data["bedrooms_min"] = bedrooms_min
    if bedrooms_max is not None:
        filter_data["bedrooms_max"] = bedrooms_max

    filters = UnifiedPropertyFilter(**filter_data)
    result = await get_unified_properties_optimized(
        ctx.deps.db,
        filters=filters,
        user_id=None,
        page=page,
        limit=limit,
    )

    properties = [serialize_property_basic(p) for p in result.get("items", [])]
    return {
        "properties": properties,
        "total": result.get("total", 0),
        "page": page,
        "total_pages": result.get("total_pages", 0),
    }


async def guest_property_details(
    ctx: RunContext[AgentDeps],
    property_id: int,
) -> dict[str, Any]:
    """Get full details for a specific property. No authentication required."""
    from app.services.property import get_property

    property_obj = await get_property(ctx.deps.db, property_id)
    return {"property": serialize_property_full(property_obj)}


async def guest_property_recommendations(
    ctx: RunContext[AgentDeps],
    city: Optional[str] = None,
    purpose: Optional[str] = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Get a list of recommended properties for discovery. No authentication required."""
    from app.schemas.property import UnifiedPropertyFilter
    from app.services.property import get_unified_properties_optimized

    limit = min(max(1, limit), 20)

    filter_data: dict[str, Any] = {}
    if city:
        filter_data["city"] = city
    if purpose:
        filter_data["purpose"] = purpose

    filters = UnifiedPropertyFilter(**filter_data)
    result = await get_unified_properties_optimized(
        ctx.deps.db,
        filters=filters,
        user_id=None,
        page=1,
        limit=limit,
    )

    properties = [serialize_property_basic(p) for p in result.get("items", [])]
    return {
        "properties": properties,
        "count": len(properties),
    }


# ============================================================================
# Tool Registration
# ============================================================================

# Maps tool name → (function, description, is_admin_only)
USER_TOOLS: list[tuple[str, Any, str]] = [
    ("owner_properties_list", owner_properties_list, "List all properties owned by the user"),
    ("owner_properties_create", owner_properties_create, "Create a new property listing"),
    ("owner_properties_get", owner_properties_get, "Get detailed property info"),
    ("owner_properties_update", owner_properties_update, "Update a property listing"),
    ("owner_properties_toggle_availability", owner_properties_toggle_availability,
     "Toggle property availability"),
    ("tenant_lease_current", tenant_lease_current, "View current active lease"),
    ("tenant_rent_history", tenant_rent_history, "View rent payment history"),
    ("tenant_maintenance_create", tenant_maintenance_create, "Submit a maintenance request"),
    ("tenant_maintenance_list", tenant_maintenance_list, "List maintenance requests"),
    ("bookings_check_availability", bookings_check_availability, "Check booking availability"),
    ("bookings_get_pricing", bookings_get_pricing, "Get booking pricing breakdown"),
    ("bookings_create", bookings_create, "Create a booking"),
    ("bookings_list", bookings_list, "List user bookings"),
    ("bookings_get", bookings_get, "Get booking details"),
    ("bookings_cancel", bookings_cancel, "Cancel a booking"),
    ("user_system_status", user_system_status, "Get system status"),
]

ADMIN_TOOLS: list[tuple[str, Any, str]] = [
    ("agent_properties_list", agent_properties_list, "List managed properties"),
    ("agent_properties_get", agent_properties_get, "Get managed property details"),
    ("agent_properties_create_for_owner", agent_properties_create_for_owner,
     "Create property for an owner"),
    ("agent_properties_verify", agent_properties_verify, "Verify a property listing"),
    ("agent_leases_list", agent_leases_list, "List leases"),
    ("agent_leases_create", agent_leases_create, "Create a lease"),
    ("agent_leases_terminate", agent_leases_terminate, "Terminate a lease"),
    ("agent_rent_list_due", agent_rent_list_due, "List overdue rent"),
    ("agent_rent_record_payment", agent_rent_record_payment, "Record a rent payment"),
    ("agent_maintenance_list", agent_maintenance_list, "List maintenance requests (admin)"),
    ("agent_maintenance_update_status", agent_maintenance_update_status,
     "Update maintenance request status"),
    ("agent_bookings_list_all", agent_bookings_list_all, "List all bookings (admin)"),
    ("agent_bookings_update_status", agent_bookings_update_status, "Update booking status"),
    ("agent_dashboard_overview", agent_dashboard_overview, "Get dashboard overview"),
    ("admin_system_status", admin_system_status, "Admin system status"),
]


GUEST_TOOLS: list[tuple[str, Any, str]] = [
    ("guest_property_search", guest_property_search,
     "Search properties by city, type, purpose, price, bedrooms, or text query"),
    ("guest_property_details", guest_property_details,
     "Get full details for a specific property by ID"),
    ("guest_property_recommendations", guest_property_recommendations,
     "Get a list of recommended properties to browse"),
]


def get_tools_for_role(role: str) -> list[tuple[str, Any, str]]:
    """Return the list of tools available for a given user role."""
    if role == "guest":
        return list(GUEST_TOOLS)
    tools = list(USER_TOOLS)
    if role in ("agent", "admin"):
        tools.extend(ADMIN_TOOLS)
    return tools
