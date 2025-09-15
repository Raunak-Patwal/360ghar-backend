from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.models import BugReport, Page, AppUpdate, User
from app.models.enums import BugStatus, PageFormat, BugType
from app.schemas.core import (
    BugReportCreate, BugReportUpdate, BugReportResponse,
    PageCreate, PageUpdate, PageResponse, PagePublicResponse,
    AppUpdateCreate, AppUpdateUpdate, AppUpdateResponse,
    AppUpdateCheckRequest, AppUpdateCheckResponse
)
from app.core.exceptions import NotFoundException, ValidationException

class CoreService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Bug Report Methods
    async def create_bug_report(self, bug_data: BugReportCreate, user_id: Optional[int] = None) -> BugReportResponse:
        """Create a new bug report"""
        bug_report = BugReport(
            user_id=user_id,
            **bug_data.model_dump()
        )

        self.db.add(bug_report)
        await self.db.commit()
        await self.db.refresh(bug_report)

        return BugReportResponse.model_validate(bug_report)

    async def get_bug_reports(
        self,
        user_id: Optional[int] = None,
        status: Optional[BugStatus] = None,
        bug_type: Optional[BugType] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[BugReportResponse]:
        """Get bug reports with optional filtering"""
        query = select(BugReport).options(
            selectinload(BugReport.user),
            selectinload(BugReport.assignee)
        )

        if user_id:
            query = query.where(BugReport.user_id == user_id)

        if status:
            query = query.where(BugReport.status == status)

        if bug_type:
            query = query.where(BugReport.bug_type == bug_type)

        query = query.order_by(desc(BugReport.created_at)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        bug_reports = result.scalars().all()

        return [BugReportResponse.model_validate(bug) for bug in bug_reports]

    async def get_bug_report_by_id(self, bug_id: int) -> BugReportResponse:
        """Get a specific bug report by ID"""
        query = select(BugReport).options(
            selectinload(BugReport.user),
            selectinload(BugReport.assignee)
        ).where(BugReport.id == bug_id)

        result = await self.db.execute(query)
        bug_report = result.scalar_one_or_none()

        if not bug_report:
            raise NotFoundException(f"Bug report with ID {bug_id} not found")

        return BugReportResponse.model_validate(bug_report)

    async def update_bug_report(
        self,
        bug_id: int,
        update_data: BugReportUpdate,
        updated_by: Optional[int] = None
    ) -> BugReportResponse:
        """Update a bug report"""
        # Get the bug report
        bug_report = await self.get_bug_report_by_id(bug_id)

        # Prepare update data
        update_dict = update_data.model_dump(exclude_unset=True)

        # If status is being changed to resolved, set resolved_at
        if update_dict.get('status') == BugStatus.resolved and bug_report.status != BugStatus.resolved:
            update_dict['resolved_at'] = datetime.utcnow()

        # Update the bug report
        query = (
            update(BugReport)
            .where(BugReport.id == bug_id)
            .values(**update_dict)
        )

        await self.db.execute(query)
        await self.db.commit()

        # Return updated bug report
        return await self.get_bug_report_by_id(bug_id)

    # Page Methods
    async def create_page(self, page_data: PageCreate, created_by: Optional[int] = None) -> PageResponse:
        """Create a new page"""
        # Check if unique_name already exists
        existing_page = await self.get_page_by_unique_name(page_data.unique_name)
        if existing_page:
            raise ValidationException(f"Page with unique_name '{page_data.unique_name}' already exists")

        page = Page(
            created_by=created_by,
            **page_data.model_dump()
        )

        self.db.add(page)
        await self.db.commit()
        await self.db.refresh(page)

        return PageResponse.model_validate(page)

    async def get_page_by_unique_name(self, unique_name: str) -> Optional[PageResponse]:
        """Get a page by its unique name"""
        query = select(Page).options(
            selectinload(Page.creator),
            selectinload(Page.updater)
        ).where(
            and_(Page.unique_name == unique_name, Page.is_active == True)
        )

        result = await self.db.execute(query)
        page = result.scalar_one_or_none()

        if page:
            # Increment view count
            page.view_count += 1
            await self.db.commit()

            return PageResponse.model_validate(page)
        return None

    async def get_page_public(self, unique_name: str) -> Optional[PagePublicResponse]:
        """Get a page for public access (without sensitive data)"""
        query = select(Page).where(
            and_(
                Page.unique_name == unique_name,
                Page.is_active == True,
                Page.is_draft == False,
                Page.is_private == False,
            )
        )

        result = await self.db.execute(query)
        page = result.scalar_one_or_none()

        if page:
            # Increment view count
            page.view_count += 1
            await self.db.commit()

            return PagePublicResponse.model_validate(page)
        return None

    async def get_pages(
        self,
        is_active: Optional[bool] = None,
        is_draft: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[PageResponse]:
        """Get pages with optional filtering"""
        query = select(Page).options(
            selectinload(Page.creator),
            selectinload(Page.updater)
        )

        if is_active is not None:
            query = query.where(Page.is_active == is_active)

        if is_draft is not None:
            query = query.where(Page.is_draft == is_draft)

        query = query.order_by(desc(Page.updated_at)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        pages = result.scalars().all()

        return [PageResponse.model_validate(page) for page in pages]

    async def update_page(
        self,
        unique_name: str,
        update_data: PageUpdate,
        updated_by: Optional[int] = None
    ) -> PageResponse:
        """Update a page"""
        # Check if page exists
        existing_page = await self.db.execute(
            select(Page).where(Page.unique_name == unique_name)
        )
        page = existing_page.scalar_one_or_none()

        if not page:
            raise NotFoundException(f"Page with unique_name '{unique_name}' not found")

        # Prepare update data
        update_dict = update_data.model_dump(exclude_unset=True)

        if updated_by:
            update_dict['updated_by'] = updated_by

        # Update the page
        query = (
            update(Page)
            .where(Page.unique_name == unique_name)
            .values(**update_dict)
        )

        await self.db.execute(query)
        await self.db.commit()

        # Return updated page
        updated_page = await self.get_page_by_unique_name(unique_name)
        return updated_page

    async def delete_page(self, unique_name: str) -> bool:
        """Soft delete a page by setting is_active to False"""
        query = (
            update(Page)
            .where(Page.unique_name == unique_name)
            .values(is_active=False)
        )

        result = await self.db.execute(query)
        await self.db.commit()

        return result.rowcount > 0

    # App Update Methods
    async def create_app_update(self, update_data: AppUpdateCreate) -> AppUpdateResponse:
        """Create a new app update"""
        app_update = AppUpdate(**update_data.model_dump())

        self.db.add(app_update)
        await self.db.commit()
        await self.db.refresh(app_update)

        return AppUpdateResponse.model_validate(app_update)

    async def check_for_updates(self, check_data: AppUpdateCheckRequest) -> AppUpdateCheckResponse:
        """Check if there's an available update for the given platform and version"""
        # Get the latest active update for the platform
        query = select(AppUpdate).where(
            and_(
                AppUpdate.platform == check_data.platform,
                AppUpdate.is_active == True
            )
        ).order_by(desc(AppUpdate.created_at)).limit(1)

        result = await self.db.execute(query)
        latest_update = result.scalar_one_or_none()

        if not latest_update:
            return AppUpdateCheckResponse(update_available=False)

        # Compare versions (simple string comparison - in production, use proper version comparison)
        current_version = check_data.current_version
        latest_version = latest_update.version

        # Simple version comparison (you might want to use a proper version comparison library)
        update_available = latest_version != current_version

        # Check if current version is below minimum supported version
        min_supported = latest_update.min_supported_version
        is_below_min = False
        if min_supported and current_version < min_supported:
            is_below_min = True
            update_available = True

        return AppUpdateCheckResponse(
            update_available=update_available,
            is_mandatory=latest_update.is_mandatory or is_below_min,
            latest_version=latest_version,
            download_url=latest_update.download_url,
            release_notes=latest_update.release_notes,
            min_supported_version=min_supported
        )

    async def get_app_updates(
        self,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[AppUpdateResponse]:
        """Get app updates with optional filtering"""
        query = select(AppUpdate)

        if platform:
            query = query.where(AppUpdate.platform == platform)

        if is_active is not None:
            query = query.where(AppUpdate.is_active == is_active)

        query = query.order_by(desc(AppUpdate.created_at)).limit(limit).offset(offset)

        result = await self.db.execute(query)
        updates = result.scalars().all()

        return [AppUpdateResponse.model_validate(update) for update in updates]

    async def update_app_update(
        self,
        update_id: int,
        update_data: AppUpdateUpdate
    ) -> AppUpdateResponse:
        """Update an app update entry"""
        # Check if update exists
        existing_update = await self.db.execute(
            select(AppUpdate).where(AppUpdate.id == update_id)
        )
        app_update = existing_update.scalar_one_or_none()

        if not app_update:
            raise NotFoundException(f"App update with ID {update_id} not found")

        # Prepare update data
        update_dict = update_data.model_dump(exclude_unset=True)

        # Update the app update
        query = (
            update(AppUpdate)
            .where(AppUpdate.id == update_id)
            .values(**update_dict)
        )

        await self.db.execute(query)
        await self.db.commit()

        # Return updated app update
        result = await self.db.execute(select(AppUpdate).where(AppUpdate.id == update_id))
        updated_update = result.scalar_one()

        return AppUpdateResponse.model_validate(updated_update)
