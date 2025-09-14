from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import get_db
from app.api.api_v1.endpoints.auth import get_current_active_user
from app.api.api_v1.dependencies.auth import get_current_admin
from app.schemas.user import User as UserSchema
from app.schemas.core import (
    BugReportCreate, BugReportUpdate, BugReportResponse,
    PageCreate, PageUpdate, PageResponse, PagePublicResponse,
    AppUpdateCreate, AppUpdateUpdate, AppUpdateResponse,
    AppUpdateCheckRequest, AppUpdateCheckResponse
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.core import CoreService
from app.services.storage import storage_service

router = APIRouter()

# Dependency to get core service
def get_core_service(db: AsyncSession = Depends(get_db)) -> CoreService:
    return CoreService(db)

# ============================================================================
# BUG REPORT ENDPOINTS
# ============================================================================

@router.post("/bugs/", response_model=BugReportResponse)
async def create_bug_report(
    bug_data: BugReportCreate,
    current_user: Optional[UserSchema] = Depends(get_current_active_user),
    core_service: CoreService = Depends(get_core_service)
):
    """Create a new bug report"""
    user_id = current_user.id if current_user else None
    return await core_service.create_bug_report(bug_data, user_id)

@router.post("/bugs/with-media/", response_model=BugReportResponse)
async def create_bug_report_with_media(
    source: str,
    bug_type: str,
    severity: str,
    title: str,
    description: str,
    steps_to_reproduce: Optional[str] = None,
    expected_behavior: Optional[str] = None,
    actual_behavior: Optional[str] = None,
    device_info: Optional[str] = None,  # JSON string
    app_version: Optional[str] = None,
    tags: Optional[str] = None,  # JSON string
    files: List[UploadFile] = File(...),
    current_user: Optional[UserSchema] = Depends(get_current_active_user),
    core_service: CoreService = Depends(get_core_service)
):
    """Create a bug report with media uploads"""
    import json

    # Parse JSON fields
    device_info_parsed = json.loads(device_info) if device_info else None
    tags_parsed = json.loads(tags) if tags else None

    # Upload media files
    media_urls = []
    for file in files:
        try:
            upload_result = await storage_service.upload_generic(file)
            # Storage service returns 'public_url'
            media_urls.append(upload_result["public_url"])
        except Exception as e:
            # Log error but continue with other files
            print(f"Failed to upload file {file.filename}: {str(e)}")
            continue

    # Create bug report data
    bug_data = BugReportCreate(
        source=source,
        bug_type=bug_type,
        severity=severity,
        title=title,
        description=description,
        steps_to_reproduce=steps_to_reproduce,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        device_info=device_info_parsed,
        app_version=app_version,
        media_urls=media_urls if media_urls else None,
        tags=tags_parsed
    )

    user_id = current_user.id if current_user else None
    return await core_service.create_bug_report(bug_data, user_id)

@router.get("/bugs/", response_model=List[BugReportResponse])
async def get_bug_reports(
    status: Optional[str] = Query(None, description="Filter by bug status"),
    bug_type: Optional[str] = Query(None, description="Filter by bug type"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: UserSchema = Depends(get_current_active_user),
    core_service: CoreService = Depends(get_core_service)
):
    """Get bug reports (filtered by current user if not admin)"""
    from app.models.enums import BugStatus, BugType

    # Validate and coerce enums, return 400 on invalid values
    try:
        status_enum = BugStatus(status) if status else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid bug status")
    try:
        bug_type_enum = BugType(bug_type) if bug_type else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid bug type")

    # If not admin, only show user's own bug reports
    if current_user.role != "admin":
        user_id = current_user.id
    else:
        user_id = None

    return await core_service.get_bug_reports(
        user_id=user_id,
        status=status_enum,
        bug_type=bug_type_enum,
        limit=limit,
        offset=offset
    )

@router.get("/bugs/{bug_id}", response_model=BugReportResponse)
async def get_bug_report(
    bug_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    core_service: CoreService = Depends(get_core_service)
):
    """Get a specific bug report"""
    bug_report = await core_service.get_bug_report_by_id(bug_id)

    # Check permissions - users can only see their own bugs unless they're admin
    if current_user.role != "admin" and bug_report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this bug report")

    return bug_report

@router.put("/bugs/{bug_id}", response_model=BugReportResponse)
async def update_bug_report(
    bug_id: int,
    update_data: BugReportUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    core_service: CoreService = Depends(get_core_service)
):
    """Update a bug report (admin only for status updates)"""
    # Check if user can update this bug report
    bug_report = await core_service.get_bug_report_by_id(bug_id)

    # Only allow status and assignment updates for non-admin users
    if current_user.role != "admin":
        if bug_report.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this bug report")

        # Non-admin users can only update certain fields
        allowed_fields = {'resolution'} if update_data.resolution else set()
        update_dict = update_data.model_dump(exclude_unset=True)
        if not all(field in allowed_fields for field in update_dict.keys()):
            raise HTTPException(status_code=403, detail="Not authorized to update these fields")

    return await core_service.update_bug_report(bug_id, update_data, current_user.id)

# ============================================================================
# PAGE ENDPOINTS
# ============================================================================

@router.post("/pages/", response_model=PageResponse)
async def create_page(
    page_data: PageCreate,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Create a new page (admin only)"""
    return await core_service.create_page(page_data, current_user.id)

@router.get("/pages/", response_model=List[PageResponse])
async def get_pages(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_draft: Optional[bool] = Query(None, description="Filter by draft status"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Get pages (admin only)"""
    return await core_service.get_pages(
        is_active=is_active,
        is_draft=is_draft,
        limit=limit,
        offset=offset
    )

@router.get("/pages/{unique_name}", response_model=PageResponse)
async def get_page(
    unique_name: str,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Get a specific page by unique name (admin only)"""
    page = await core_service.get_page_by_unique_name(unique_name)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.get("/pages/{unique_name}/public", response_model=PagePublicResponse)
async def get_page_public(unique_name: str, core_service: CoreService = Depends(get_core_service)):
    """Get a page for public access (no auth required)"""
    page = await core_service.get_page_public(unique_name)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.put("/pages/{unique_name}", response_model=PageResponse)
async def update_page(
    unique_name: str,
    update_data: PageUpdate,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Update a page (admin only)"""
    return await core_service.update_page(unique_name, update_data, current_user.id)

@router.delete("/pages/{unique_name}", response_model=MessageResponse)
async def delete_page(
    unique_name: str,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Delete a page (admin only)"""
    success = await core_service.delete_page(unique_name)
    if not success:
        raise HTTPException(status_code=404, detail="Page not found")

    return MessageResponse(message="Page deleted successfully")

# ============================================================================
# APP UPDATE ENDPOINTS
# ============================================================================

@router.post("/updates/", response_model=AppUpdateResponse)
async def create_app_update(
    update_data: AppUpdateCreate,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Create a new app update entry (admin only)"""
    return await core_service.create_app_update(update_data)

@router.post("/updates/check", response_model=AppUpdateCheckResponse)
async def check_for_updates(
    check_data: AppUpdateCheckRequest,
    core_service: CoreService = Depends(get_core_service)
):
    """Check if there's an available update (public endpoint)"""
    return await core_service.check_for_updates(check_data)

@router.get("/updates/", response_model=List[AppUpdateResponse])
async def get_app_updates(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Get app updates (admin only)"""
    return await core_service.get_app_updates(
        platform=platform,
        is_active=is_active,
        limit=limit,
        offset=offset
    )

@router.put("/updates/{update_id}", response_model=AppUpdateResponse)
async def update_app_update(
    update_id: int,
    update_data: AppUpdateUpdate,
    current_user: UserSchema = Depends(get_current_admin),
    core_service: CoreService = Depends(get_core_service)
):
    """Update an app update entry (admin only)"""
    return await core_service.update_app_update(update_id, update_data)

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "360ghar-core"
    }
