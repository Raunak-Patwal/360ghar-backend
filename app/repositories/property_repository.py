"""
Repository for property data access
"""
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import func as geofunc
from app.repositories.base import BaseRepository
from app.models.properties import Property, PropertyAmenity
from app.models.users import User
from app.schemas.property import SortBy
from app.core.logging import get_logger

logger = get_logger(__name__)

class PropertyRepository(BaseRepository[Property]):
    """Property repository with query helpers"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Property, session)
    
    async def get_property_with_owner(self, property_id: int) -> Optional[Property]:
        stmt = (
            select(Property)
            .options(
                selectinload(Property.images),
                selectinload(Property.owner)
            )
            .where(Property.id == property_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_properties_filtered(
        self,
        filters: Dict[str, Any],
        skip: int,
        limit: int,
        sort_by: SortBy,
        sort_order: str,
        include_owner: bool = False,
        include_images: bool = False
    ) -> List[Property]:
        stmt = select(Property)
        
        if include_owner:
            stmt = stmt.options(selectinload(Property.owner))
        if include_images:
            stmt = stmt.options(selectinload(Property.images))
        
        # Apply filters
        stmt = self._apply_filters(stmt, filters)
        
        # Sorting
        stmt = self._apply_sorting(stmt, sort_by, sort_order)
        
        # Pagination
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_properties_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius_km: int,
        filters: Dict[str, Any],
        skip: int,
        limit: int
    ) -> List[Property]:
        center_point = geofunc.ST_SetSRID(geofunc.ST_MakePoint(longitude, latitude), 4326)
        stmt = select(Property)
        stmt = stmt.where(
            geofunc.ST_DWithin(
                Property.location,
                center_point,
                radius_km * 1000  # Convert km to meters
            )
        )
        
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(geofunc.ST_Distance(Property.location, center_point))
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def count_filtered(self, filters: Dict[str, Any]) -> int:
        stmt = select(func.count(Property.id))
        stmt = self._apply_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()
    
    def _apply_filters(self, stmt, filters: Dict[str, Any]):
        """Apply dynamic filters to a SQLAlchemy statement"""
        if not filters:
            return stmt
        
        for field, value in filters.items():
            if value is None:
                continue
            
            if field == "price_range":
                min_price, max_price = value
                if min_price is not None:
                    stmt = stmt.where(Property.base_price >= min_price)
                if max_price is not None:
                    stmt = stmt.where(Property.base_price <= max_price)
            elif field == "bedrooms":
                stmt = stmt.where(Property.bedrooms >= value)
            elif field == "bathrooms":
                stmt = stmt.where(Property.bathrooms >= value)
            elif hasattr(Property, field):
                stmt = stmt.where(getattr(Property, field) == value)
        return stmt
    
    def _apply_sorting(self, stmt, sort_by: SortBy, sort_order: str):
        """Apply sorting to statement"""
        order_column = getattr(Property, sort_by.value, Property.created_at)
        if sort_order == "desc":
            stmt = stmt.order_by(order_column.desc())
        else:
            stmt = stmt.order_by(order_column.asc())
        return stmt
