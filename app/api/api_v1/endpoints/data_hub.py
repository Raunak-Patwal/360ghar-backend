"""
Data Hub API endpoints — all ~30 routes covering circle rates, RERA, auctions,
bank rates, Jamabandi, zoning, colony approvals, gazette, builders,
neighbourhood scores, and admin scraper management.
"""

from datetime import datetime
from datetime import date as date_type
from importlib import import_module
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.dependencies.auth import (
    get_current_active_user,
    get_current_admin,
)
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.data_hub import (
    AuctionAlert,
    BankAuction,
    BankRate,
    CircleRate,
    ColonyApproval,
    CourtAuction,
    GazetteNotification,
    NeighbourhoodScore,
    ReraComplaint,
    ReraProject,
    ScraperRun,
    ZoningData,
)
from app.schemas.data_hub import (
    AuctionAlertCreate,
    AuctionAlertResponse,
    AuctionAlertUpdate,
    AuctionListResponse,
    BankAuctionResponse,
    BankRateListResponse,
    BankRateResponse,
    BuilderListResponse,
    BuilderReputationResponse,
    CircleRateListResponse,
    CircleRateResponse,
    ColonyApprovalListResponse,
    ColonyApprovalResponse,
    CourtAuctionResponse,
    DataHubMeta,
    GazetteNotificationListResponse,
    GazetteNotificationResponse,
    JamabandiLookupRequest,
    JamabandiLookupResponse,
    NeighbourhoodScoreResponse,
    ReraComplaintListResponse,
    ReraComplaintResponse,
    ReraProjectListResponse,
    ReraProjectResponse,
    ScraperRunResponse,
    StampDutyCalculationRequest,
    StampDutyCalculationResponse,
    ZoningDataListResponse,
    ZoningDataResponse,
)
from app.schemas.user import User as UserSchema
from app.services.data_hub.utils import (
    calculate_registration_fee,
    calculate_stamp_duty,
    calculate_builder_score,
)

router = APIRouter()
logger = get_logger(__name__)

_STAMP_DUTY_RATES: Dict[str, float] = {"male": 7.0, "female": 5.0, "joint": 6.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(total: int, page: int, limit: int) -> Dict[str, Any]:
    total_pages = max(1, (total + limit - 1) // limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


async def _meta_from_table(db: AsyncSession, model) -> DataHubMeta:
    """Query max updated_at for a table and return a DataHubMeta."""
    result = await db.execute(select(func.max(model.updated_at)))
    last_updated = result.scalar_one_or_none()
    return DataHubMeta(last_updated=last_updated)


# ===========================================================================
# SECTION 1: CIRCLE RATES
# ===========================================================================

@router.get("/circle-rates", response_model=CircleRateListResponse)
async def list_circle_rates(
    sector: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    property_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List circle rates with optional filters."""
    filters = []
    if sector:
        filters.append(CircleRate.sector.ilike(f"%{sector}%"))
    if year:
        filters.append(CircleRate.revision_year == year)
    if property_type:
        filters.append(CircleRate.property_type.ilike(f"%{property_type}%"))

    count_q = select(func.count()).select_from(CircleRate)
    data_q = select(CircleRate)
    if filters:
        count_q = count_q.where(and_(*filters))
        data_q = data_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
    meta = await _meta_from_table(db, CircleRate)

    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/circle-rates/sectors", response_model=List[str])
async def list_circle_rate_sectors(db: AsyncSession = Depends(get_db)):
    """List distinct sector names from circle rates."""
    result = await db.execute(
        select(distinct(CircleRate.sector)).order_by(CircleRate.sector)
    )
    return [r for r in result.scalars().all() if r]


@router.post("/circle-rates/calculate-duty", response_model=StampDutyCalculationResponse)
async def calculate_duty_from_circle_rates(
    req: StampDutyCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Calculate stamp duty and registration fee (also callable from /calculator/stamp-duty)."""
    duty = calculate_stamp_duty(req.property_value, req.buyer_type)
    reg_fee = calculate_registration_fee(req.property_value)

    circle_rate_per_sqyd: Optional[float] = None
    if req.sector:
        cr_result = await db.execute(
            select(CircleRate.rate_per_sqyd)
            .where(CircleRate.sector.ilike(f"%{req.sector}%"))
            .order_by(CircleRate.revision_year.desc())
            .limit(1)
        )
        cr_val = cr_result.scalar_one_or_none()
        circle_rate_per_sqyd = float(cr_val) if cr_val is not None else None

    bank_rate_result = await db.execute(
        select(BankRate.rate_value)
        .where(BankRate.rate_type == "home_loan_min")
        .order_by(BankRate.effective_date.desc())
        .limit(1)
    )
    bank_rate = bank_rate_result.scalar_one_or_none()

    return StampDutyCalculationResponse(
        property_value=req.property_value,
        circle_rate_per_sqyd=circle_rate_per_sqyd,
        stamp_duty_rate=_STAMP_DUTY_RATES.get(req.buyer_type, 7.0),
        stamp_duty_amount=duty,
        registration_fee=reg_fee,
        total_cost=duty + reg_fee,
        current_bank_rate=float(bank_rate) if bank_rate is not None else None,
    )


@router.get("/circle-rates/{slug}", response_model=CircleRateResponse)
async def get_circle_rate(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single circle rate entry by slug."""
    result = await db.execute(
        select(CircleRate).where(CircleRate.slug == slug)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Circle rate not found")
    return row


# ===========================================================================
# SECTION 2: RERA PROJECTS
# ===========================================================================

@router.get("/rera-projects", response_model=ReraProjectListResponse)
async def list_rera_projects(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search project name or developer"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List RERA projects with optional status filter and text search."""
    filters = []
    if status:
        filters.append(ReraProject.status == status)
    if q:
        filters.append(
            ReraProject.project_name.ilike(f"%{q}%")
            | ReraProject.developer_name.ilike(f"%{q}%")
        )

    count_q = select(func.count()).select_from(ReraProject)
    data_q = select(ReraProject)
    if filters:
        count_q = count_q.where(and_(*filters))
        data_q = data_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
    meta = await _meta_from_table(db, ReraProject)

    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/rera-projects/verify/{rera_number}")
async def verify_rera_project(rera_number: str, db: AsyncSession = Depends(get_db)):
    """Verify a RERA number — returns validity, status, and project name."""
    result = await db.execute(
        select(ReraProject).where(ReraProject.rera_number == rera_number)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {"valid": False, "status": None, "project_name": None}
    return {"valid": True, "status": row.status, "project_name": row.project_name}


@router.get("/rera-projects/{rera_number}", response_model=ReraProjectResponse)
async def get_rera_project(rera_number: str, db: AsyncSession = Depends(get_db)):
    """Get a single RERA project by its RERA number."""
    result = await db.execute(
        select(ReraProject).where(ReraProject.rera_number == rera_number)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="RERA project not found")
    return row


# ===========================================================================
# SECTION 3: AUCTIONS (unified bank + court)
# ===========================================================================

@router.get("/auctions/banks", response_model=List[str])
async def list_auction_banks(db: AsyncSession = Depends(get_db)):
    """List distinct bank names from bank auctions."""
    result = await db.execute(
        select(distinct(BankAuction.bank_name)).order_by(BankAuction.bank_name)
    )
    return [r for r in result.scalars().all() if r]


@router.get("/auctions/alerts/me", response_model=List[AuctionAlertResponse])
async def get_my_auction_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Get the authenticated user's auction alerts."""
    result = await db.execute(
        select(AuctionAlert).where(AuctionAlert.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/auctions/alerts", response_model=AuctionAlertResponse, status_code=201)
async def create_auction_alert(
    payload: AuctionAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Create a new auction alert for the authenticated user."""
    alert = AuctionAlert(
        user_id=current_user.id,
        bank_name=payload.bank_name,
        property_type=payload.property_type,
        min_price=payload.min_price,
        max_price=payload.max_price,
        alert_channels=payload.alert_channels or ["email"],
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.put("/auctions/alerts/{alert_id}", response_model=AuctionAlertResponse)
async def update_auction_alert(
    alert_id: int,
    payload: AuctionAlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Update an auction alert owned by the authenticated user."""
    result = await db.execute(
        select(AuctionAlert).where(
            AuctionAlert.id == alert_id,
            AuctionAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Auction alert not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/auctions/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auction_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Delete an auction alert owned by the authenticated user."""
    result = await db.execute(
        select(AuctionAlert).where(
            AuctionAlert.id == alert_id,
            AuctionAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Auction alert not found")
    await db.delete(alert)
    await db.commit()


@router.get("/auctions/{auction_id}")
async def get_auction(auction_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single auction by ID — checks bank auctions first, then court auctions."""
    bank_result = await db.execute(
        select(BankAuction).where(BankAuction.id == auction_id)
    )
    bank_row = bank_result.scalar_one_or_none()
    if bank_row is not None:
        return BankAuctionResponse.model_validate(bank_row)

    court_result = await db.execute(
        select(CourtAuction).where(CourtAuction.id == auction_id)
    )
    court_row = court_result.scalar_one_or_none()
    if court_row is not None:
        return CourtAuctionResponse.model_validate(court_row)

    raise HTTPException(status_code=404, detail="Auction not found")


@router.get("/auctions", response_model=AuctionListResponse)
async def list_auctions(
    type: Optional[str] = Query(None, description="'bank' or 'court'"),
    bank: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated list of auctions. Defaults to bank auctions; set type='court' for court auctions.
    """
    offset = (page - 1) * limit

    if type == "court":
        filters = []
        if property_type:
            filters.append(CourtAuction.property_type.ilike(f"%{property_type}%"))
        if min_price:
            filters.append(CourtAuction.reserve_price >= min_price)
        if max_price:
            filters.append(CourtAuction.reserve_price <= max_price)
        if date_from:
            filters.append(CourtAuction.auction_date >= date_from)
        if date_to:
            filters.append(CourtAuction.auction_date <= date_to)

        count_q = select(func.count()).select_from(CourtAuction)
        data_q = select(CourtAuction)
        if filters:
            count_q = count_q.where(and_(*filters))
            data_q = data_q.where(and_(*filters))

        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
        # Map CourtAuction rows to BankAuctionResponse-compatible dicts
        items = []
        for r in rows:
            items.append(
                BankAuctionResponse(
                    id=r.id,
                    bank_name=r.court_name or "Court",
                    property_description=r.property_description or "",
                    full_address=r.locality,
                    reserve_price=float(r.reserve_price) if r.reserve_price else None,
                    emd_amount=None,
                    auction_date=r.auction_date,
                    emd_deadline=None,
                    contact_info=r.contact_details,
                    source=r.source,
                    source_url=r.source_url,
                    property_type=r.property_type,
                    lat=None,
                    lng=None,
                    slug=getattr(r, "slug", None),
                    last_scraped_at=None,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
            )
        meta = await _meta_from_table(db, CourtAuction)
        return {
            "items": items,
            "meta": meta,
            **_paginate(total, page, limit),
        }
    else:
        # Default: bank auctions
        filters = []
        if bank:
            filters.append(BankAuction.bank_name.ilike(f"%{bank}%"))
        if property_type:
            filters.append(BankAuction.property_type.ilike(f"%{property_type}%"))
        if min_price:
            filters.append(BankAuction.reserve_price >= min_price)
        if max_price:
            filters.append(BankAuction.reserve_price <= max_price)
        if date_from:
            filters.append(BankAuction.auction_date >= date_from)
        if date_to:
            filters.append(BankAuction.auction_date <= date_to)

        count_q = select(func.count()).select_from(BankAuction)
        data_q = select(BankAuction)
        if filters:
            count_q = count_q.where(and_(*filters))
            data_q = data_q.where(and_(*filters))

        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
        meta = await _meta_from_table(db, BankAuction)
        return {
            "items": rows,
            "meta": meta,
            **_paginate(total, page, limit),
        }


# ===========================================================================
# SECTION 4: BANK RATES & STAMP DUTY
# ===========================================================================

@router.get("/bank-rates", response_model=BankRateListResponse)
async def list_bank_rates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List latest bank interest rates."""
    total = (await db.execute(select(func.count()).select_from(BankRate))).scalar_one()
    offset = (page - 1) * limit
    rows = (
        await db.execute(
            select(BankRate).order_by(BankRate.effective_date.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()
    meta = await _meta_from_table(db, BankRate)
    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.post("/calculator/stamp-duty", response_model=StampDutyCalculationResponse)
async def calculator_stamp_duty(
    req: StampDutyCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Calculate stamp duty and registration fee (alias of /circle-rates/calculate-duty)."""
    duty = calculate_stamp_duty(req.property_value, req.buyer_type)
    reg_fee = calculate_registration_fee(req.property_value)

    circle_rate_per_sqyd: Optional[float] = None
    if req.sector:
        cr_result = await db.execute(
            select(CircleRate.rate_per_sqyd)
            .where(CircleRate.sector.ilike(f"%{req.sector}%"))
            .order_by(CircleRate.revision_year.desc())
            .limit(1)
        )
        cr_val = cr_result.scalar_one_or_none()
        circle_rate_per_sqyd = float(cr_val) if cr_val is not None else None

    bank_rate_result = await db.execute(
        select(BankRate.rate_value)
        .where(BankRate.rate_type == "home_loan_min")
        .order_by(BankRate.effective_date.desc())
        .limit(1)
    )
    bank_rate = bank_rate_result.scalar_one_or_none()

    return StampDutyCalculationResponse(
        property_value=req.property_value,
        circle_rate_per_sqyd=circle_rate_per_sqyd,
        stamp_duty_rate=_STAMP_DUTY_RATES.get(req.buyer_type, 7.0),
        stamp_duty_amount=duty,
        registration_fee=reg_fee,
        total_cost=duty + reg_fee,
        current_bank_rate=float(bank_rate) if bank_rate is not None else None,
    )


# ===========================================================================
# SECTION 5: JAMABANDI
# ===========================================================================

@router.get("/jamabandi/captcha")
async def jamabandi_captcha(
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Proxy the Jamabandi CAPTCHA image."""
    from app.services.data_hub.jamabandi import JamabandiScraper
    scraper = JamabandiScraper()
    try:
        img_bytes = await scraper.get_captcha_bytes()
    except Exception as exc:
        logger.error("Failed to fetch Jamabandi captcha: %s", exc)
        raise HTTPException(status_code=502, detail="Could not fetch captcha from Jamabandi")
    return Response(content=img_bytes, media_type="image/png")


@router.post("/jamabandi/lookup", response_model=JamabandiLookupResponse)
async def jamabandi_lookup(
    req: JamabandiLookupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_active_user),
):
    """Look up a land record (Nakal) via Jamabandi."""
    from app.services.data_hub.jamabandi import JamabandiScraper
    scraper = JamabandiScraper()
    result = await scraper.lookup(
        db,
        tehsil=req.tehsil,
        village=req.village,
        khasra_number=req.khasra_number,
        captcha_token=req.captcha_token,
    )
    if result is None:
        raise HTTPException(status_code=502, detail="Jamabandi lookup failed — check captcha or try again")

    return JamabandiLookupResponse(
        tehsil=result["tehsil"],
        village=result["village"],
        khasra_number=result["khasra_number"],
        owner_names=result.get("owner_names") or [],
        area_acres=result.get("area_kanal"),
        mutation_status=result.get("mutation_status"),
        encumbrance=result.get("encumbrance_details"),
        raw_data=None,
        fetched_at=result.get("fetched_at") or datetime.utcnow(),
        is_cached=result.get("is_cached", False),
    )


# ===========================================================================
# SECTION 6: ZONING & COLONY APPROVALS
# ===========================================================================

@router.get("/zoning/sectors", response_model=List[str])
async def list_zoning_sectors(db: AsyncSession = Depends(get_db)):
    """List distinct sectors from zoning data."""
    result = await db.execute(
        select(distinct(ZoningData.sector)).order_by(ZoningData.sector)
    )
    return [r for r in result.scalars().all() if r]


@router.get("/zoning/{slug}", response_model=ZoningDataResponse)
async def get_zoning(slug: str, db: AsyncSession = Depends(get_db)):
    """Get zoning data for a specific sector by slug."""
    result = await db.execute(
        select(ZoningData).where(ZoningData.slug == slug)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Zoning data not found")
    return row


@router.get("/zoning", response_model=ZoningDataListResponse)
async def list_zoning(
    sector: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List zoning data with optional sector filter."""
    filters = []
    if sector:
        filters.append(ZoningData.sector.ilike(f"%{sector}%"))

    count_q = select(func.count()).select_from(ZoningData)
    data_q = select(ZoningData)
    if filters:
        count_q = count_q.where(and_(*filters))
        data_q = data_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
    meta = await _meta_from_table(db, ZoningData)
    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/colony-approvals", response_model=ColonyApprovalListResponse)
async def list_colony_approvals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List colony approvals."""
    total = (await db.execute(select(func.count()).select_from(ColonyApproval))).scalar_one()
    offset = (page - 1) * limit
    rows = (
        await db.execute(select(ColonyApproval).offset(offset).limit(limit))
    ).scalars().all()
    meta = await _meta_from_table(db, ColonyApproval)
    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


# ===========================================================================
# SECTION 7: GAZETTE
# ===========================================================================

@router.get("/gazette", response_model=GazetteNotificationListResponse)
async def list_gazette(
    type: Optional[str] = Query(None, description="Notification type filter"),
    q: Optional[str] = Query(None, description="Search title or summary"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List gazette notifications with optional type and text search filters."""
    filters = []
    if type:
        filters.append(GazetteNotification.notification_type == type)
    if q:
        filters.append(
            GazetteNotification.title.ilike(f"%{q}%")
            | GazetteNotification.summary.ilike(f"%{q}%")
        )

    count_q = select(func.count()).select_from(GazetteNotification)
    data_q = select(GazetteNotification).order_by(GazetteNotification.notification_date.desc())
    if filters:
        count_q = count_q.where(and_(*filters))
        data_q = data_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
    meta = await _meta_from_table(db, GazetteNotification)
    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/gazette/{gazette_id}", response_model=GazetteNotificationResponse)
async def get_gazette(gazette_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single gazette notification by ID."""
    result = await db.execute(
        select(GazetteNotification).where(GazetteNotification.id == gazette_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Gazette notification not found")
    return row


# ===========================================================================
# SECTION 8: BUILDERS
# ===========================================================================

@router.get("/builders", response_model=BuilderListResponse)
async def list_builders(
    q: Optional[str] = Query(None, description="Search builder name"),
    order_by: Optional[str] = Query(None, description="Set to 'score' to sort by builder score"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List builders aggregated from RERA projects, with complaint counts and scores."""
    # Build subquery: distinct developer slugs with name and project/complaint counts
    filters = []
    if q:
        filters.append(ReraProject.developer_name.ilike(f"%{q}%"))

    slug_q = (
        select(
            ReraProject.developer_slug.label("slug"),
            ReraProject.developer_name.label("builder_name"),
            func.count(ReraProject.id).label("total_projects"),
        )
        .where(ReraProject.developer_slug.isnot(None))
        .group_by(ReraProject.developer_slug, ReraProject.developer_name)
    )
    if filters:
        slug_q = slug_q.where(and_(*filters))

    # Fetch ALL builder rows (no pagination yet) so we can sort before slicing
    all_rows = (await db.execute(slug_q)).all()

    # Collect all builder slugs for bulk lookups
    all_slugs = [r.slug for r in all_rows if r.slug]

    # Bulk-fetch complaint counts
    complaint_counts: Dict[str, int] = {}
    if all_slugs:
        complaint_count_rows = (
            await db.execute(
                select(ReraComplaint.builder_slug, func.count().label("cnt"))
                .where(ReraComplaint.builder_slug.in_(all_slugs))
                .group_by(ReraComplaint.builder_slug)
            )
        ).all()
        complaint_counts = {r.builder_slug: r.cnt for r in complaint_count_rows}

    # Build unsorted list with scores
    all_items: List[BuilderReputationResponse] = []
    for row in all_rows:
        builder_slug = row.slug
        builder_name = row.builder_name or builder_slug
        total_projects = row.total_projects
        total_complaints = complaint_counts.get(builder_slug, 0)
        score = calculate_builder_score(total_complaints, total_projects)
        all_items.append(
            BuilderReputationResponse(
                builder_name=builder_name,
                slug=builder_slug,
                total_projects=total_projects,
                total_complaints=total_complaints,
                builder_score=score,
                rera_projects=[],
                recent_complaints=[],
            )
        )

    # Sort before pagination
    if order_by == "score":
        all_items.sort(key=lambda x: x.builder_score, reverse=True)

    total = len(all_items)
    offset = (page - 1) * limit
    page_items = all_items[offset: offset + limit]

    # Bulk-fetch projects and recent complaints only for the current page slice
    page_slugs = [item.slug for item in page_items if item.slug]

    projects_by_slug: Dict[str, list] = {s: [] for s in page_slugs}
    if page_slugs:
        proj_rows = (
            await db.execute(
                select(ReraProject).where(ReraProject.developer_slug.in_(page_slugs))
            )
        ).scalars().all()
        for p in proj_rows:
            if p.developer_slug in projects_by_slug:
                projects_by_slug[p.developer_slug].append(p)

    complaints_by_slug: Dict[str, list] = {s: [] for s in page_slugs}
    if page_slugs:
        comp_rows = (
            await db.execute(
                select(ReraComplaint)
                .where(ReraComplaint.builder_slug.in_(page_slugs))
                .order_by(ReraComplaint.order_date.desc())
            )
        ).scalars().all()
        for c in comp_rows:
            if c.builder_slug in complaints_by_slug:
                complaints_by_slug[c.builder_slug].append(c)

    # Attach projects/complaints (cap at 5 each) to each page item
    items = []
    for item in page_items:
        item.rera_projects = projects_by_slug.get(item.slug, [])[:5]
        item.recent_complaints = complaints_by_slug.get(item.slug, [])[:5]
        items.append(item)

    meta = await _meta_from_table(db, ReraProject)
    return {
        "items": items,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/builders/{slug}", response_model=BuilderReputationResponse)
async def get_builder(slug: str, db: AsyncSession = Depends(get_db)):
    """Get builder reputation details by slug."""
    projects_result = await db.execute(
        select(ReraProject).where(ReraProject.developer_slug == slug)
    )
    projects = projects_result.scalars().all()
    if not projects:
        raise HTTPException(status_code=404, detail="Builder not found")

    total_projects = len(projects)
    builder_name = projects[0].developer_name or slug

    complaint_count_result = await db.execute(
        select(func.count()).select_from(ReraComplaint)
        .where(ReraComplaint.builder_slug == slug)
    )
    total_complaints = complaint_count_result.scalar_one()

    complaints_result = await db.execute(
        select(ReraComplaint)
        .where(ReraComplaint.builder_slug == slug)
        .order_by(ReraComplaint.order_date.desc())
        .limit(20)
    )
    complaints = complaints_result.scalars().all()

    score = calculate_builder_score(total_complaints, total_projects)

    return BuilderReputationResponse(
        builder_name=builder_name,
        slug=slug,
        total_projects=total_projects,
        total_complaints=total_complaints,
        builder_score=score,
        rera_projects=list(projects),
        recent_complaints=list(complaints),
    )


# ===========================================================================
# SECTION 9: NEIGHBOURHOOD SCORES
# ===========================================================================

@router.get("/neighbourhood/{listing_id}", response_model=NeighbourhoodScoreResponse)
async def get_neighbourhood_score(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Get neighbourhood score for a property listing."""
    result = await db.execute(
        select(NeighbourhoodScore).where(NeighbourhoodScore.listing_id == listing_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Neighbourhood score not found")

    # Populate individual category scores from the JSON dict
    category_scores = row.category_scores or {}
    return NeighbourhoodScoreResponse(
        id=row.id,
        listing_id=row.listing_id,
        overall_score=row.overall_score,
        transit_score=category_scores.get("transit"),
        education_score=category_scores.get("education"),
        health_score=category_scores.get("health"),
        retail_score=category_scores.get("retail"),
        nearby_places=row.nearby_places,
        stale_after=row.stale_after,
        last_fetched_at=row.last_fetched_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/neighbourhood/{listing_id}/refresh")
async def refresh_neighbourhood_score(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_admin),
):
    """Trigger a neighbourhood score refresh for a listing (admin only)."""
    from app.services.data_hub.neighbourhood import NeighbourhoodScraper
    scraper = NeighbourhoodScraper(listing_ids=[listing_id])
    result = await scraper.run(run_type="manual", triggered_by=current_user.id)
    return {"message": "Neighbourhood refresh triggered", "result": result}


# ===========================================================================
# SECTION 10: ADMIN
# ===========================================================================

_SCRAPER_MAP: Dict[str, str] = {
    "circle_rates": "app.services.data_hub.circle_rates.CircleRateScraper",
    "rera_projects": "app.services.data_hub.rera_projects.ReraProjectScraper",
    "bank_auctions": "app.services.data_hub.bank_auctions.BankAuctionScraper",
    "bank_rates": "app.services.data_hub.bank_rates.BankRateScraper",
    "court_auctions": "app.services.data_hub.court_auctions.CourtAuctionScraper",
    "rera_complaints": "app.services.data_hub.rera_complaints.ReraComplaintScraper",
    "zoning": "app.services.data_hub.zoning.ZoningScraper",
    "gazette": "app.services.data_hub.gazette.GazetteScraper",
    "neighbourhood": "app.services.data_hub.neighbourhood.NeighbourhoodScraper",
}


@router.post("/admin/scraper/{scraper_name}/trigger")
async def trigger_scraper(
    scraper_name: str,
    current_user: UserSchema = Depends(get_current_admin),
):
    """Trigger a named scraper manually (admin only)."""
    if scraper_name not in _SCRAPER_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scraper '{scraper_name}'. Available: {list(_SCRAPER_MAP.keys())}",
        )
    try:
        module_path, class_name = _SCRAPER_MAP[scraper_name].rsplit(".", 1)
        module = import_module(module_path)
        scraper_cls = getattr(module, class_name)
        scraper = scraper_cls()
        result = await scraper.run(run_type="manual", triggered_by=current_user.id)
        return {"message": f"Scraper '{scraper_name}' triggered", "result": result}
    except Exception as exc:
        logger.error("Failed to trigger scraper %s: %s", scraper_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Scraper trigger failed — see server logs")


@router.get("/admin/scraper/runs", response_model=List[ScraperRunResponse])
async def list_scraper_runs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: UserSchema = Depends(get_current_admin),
):
    """List recent scraper runs (admin only)."""
    result = await db.execute(
        select(ScraperRun).order_by(ScraperRun.started_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/admin/import/{table_name}")
async def bulk_import(
    table_name: str,
    current_user: UserSchema = Depends(get_current_admin),
):
    """Placeholder for bulk data import (admin only)."""
    _SUPPORTED_TABLES = {
        "circle_rates", "rera_projects", "bank_auctions", "bank_rates",
        "court_auctions", "rera_complaints", "zoning_data", "colony_approvals",
        "gazette_notifications",
    }
    if table_name not in _SUPPORTED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Table '{table_name}' not supported. Supported: {sorted(_SUPPORTED_TABLES)}",
        )
    return {
        "message": f"Bulk import for '{table_name}' is not yet implemented.",
        "table": table_name,
    }
