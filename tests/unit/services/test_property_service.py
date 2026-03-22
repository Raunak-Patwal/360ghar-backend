"""
Tests for property service module.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.properties import Property
from app.models.enums import (
    ListingGenderPreference,
    ListingSharingType,
    PropertyPurpose,
    PropertyStatus,
    PropertyType,
)


class TestCreateProperty:
    """Tests for create_property function."""

    @pytest.mark.asyncio
    async def test_create_property_success(
        self,
        db_session: AsyncSession,
        test_user,
    ):
        """Test successful property creation."""
        from app.services.property import create_property
        from app.schemas.property import PropertyCreate

        property_data = PropertyCreate(
            title="New Test Property",
            description="A beautiful test property",
            property_type=PropertyType.apartment,
            purpose=PropertyPurpose.rent,
            base_price=Decimal("5000000"),
            monthly_rent=Decimal("50000"),
            city="Mumbai",
            locality="Andheri",
            full_address="123 Test Street, Andheri, Mumbai",
            pincode="400069",
            state="Maharashtra",
            country="India",
            latitude=19.1136,
            longitude=72.8697,
            bedrooms=2,
            bathrooms=2,
            area_sqft=Decimal("1000"),
        )

        # Create mock property result
        mock_result = MagicMock()
        mock_result.id = 1
        mock_result.title = "New Test Property"
        mock_result.owner_id = test_user.id
        mock_result.property_type = PropertyType.apartment

        with patch("app.services.property.PropertyRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_property = MagicMock()
            mock_repo.create = AsyncMock(return_value=mock_property)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.property.PropertyCacheManager.invalidate_property_caches", new_callable=AsyncMock):
                with patch("app.services.property.PropertySchema.model_validate", return_value=mock_result):
                    result = await create_property(db_session, property_data, test_user.id, test_user)

                    assert result is not None
                    assert result.title == "New Test Property"
                    assert result.owner_id == test_user.id
                    assert result.property_type == PropertyType.apartment

    @pytest.mark.asyncio
    async def test_create_property_rejects_pg_with_non_rent_purpose(self):
        """Test PG listings are restricted to rent purpose."""
        from app.schemas.property import PropertyCreate

        with pytest.raises(ValidationError):
            PropertyCreate(
                title="Invalid PG",
                property_type=PropertyType.pg,
                purpose=PropertyPurpose.buy,
                base_price=Decimal("18000"),
            )


class TestGetProperty:
    """Tests for get_property function."""

    @pytest.mark.asyncio
    async def test_get_property_success(
        self,
        db_session: AsyncSession,
        test_property,
    ):
        """Test getting property by ID."""
        from app.services.property import get_property

        result = await get_property(db_session, test_property.id)

        assert result is not None
        assert result.id == test_property.id
        assert result.title == test_property.title

    @pytest.mark.asyncio
    async def test_get_property_not_found(self, db_session: AsyncSession):
        """Test getting non-existent property."""
        from app.services.property import get_property
        from app.core.exceptions import PropertyNotFoundException

        with pytest.raises(PropertyNotFoundException):
            await get_property(db_session, 99999)


class TestUpdateProperty:
    """Tests for update_property function."""

    @pytest.mark.asyncio
    async def test_update_property_success(
        self,
        db_session: AsyncSession,
        test_property,
        test_user,
    ):
        """Test successful property update."""
        from app.services.property import update_property
        from app.schemas.property import PropertyUpdate

        update_data = PropertyUpdate(title="Updated Title")

        # Create mock result
        mock_result = MagicMock()
        mock_result.id = test_property.id
        mock_result.title = "Updated Title"

        with patch("app.services.property.PropertyRepository") as mock_repo_class:
            mock_repo = MagicMock()
            mock_property = MagicMock()
            mock_property.owner_id = test_user.id
            mock_property.owner = None
            mock_repo.get_property_with_owner = AsyncMock(return_value=mock_property)
            mock_repo_class.return_value = mock_repo

            # Mock the db session operations
            with patch.object(db_session, "flush", new_callable=AsyncMock):
                with patch.object(db_session, "refresh", new_callable=AsyncMock):
                    with patch("app.services.property.PropertyCacheManager.invalidate_property_caches", new_callable=AsyncMock):
                        with patch("app.services.property.PropertySchema.model_validate", return_value=mock_result):
                            result = await update_property(
                                db_session, test_property.id, update_data, test_user
                            )

                            assert result is not None
                            assert result.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_property_rejects_pg_with_non_rent_purpose(
        self,
        db_session: AsyncSession,
        test_property,
        test_user,
    ):
        """Test updates cannot move PG listings outside the rent purpose."""
        from app.core.exceptions import BadRequestException
        from app.services.property import update_property
        from app.schemas.property import PropertyUpdate

        update_data = PropertyUpdate(
            property_type=PropertyType.pg,
            purpose=PropertyPurpose.buy,
        )

        with pytest.raises(BadRequestException):
            await update_property(db_session, test_property.id, update_data, test_user)

    @pytest.mark.asyncio
    async def test_update_property_not_found(
        self,
        db_session: AsyncSession,
        test_user,
    ):
        """Test updating non-existent property."""
        from app.services.property import update_property
        from app.schemas.property import PropertyUpdate
        from fastapi import HTTPException

        update_data = PropertyUpdate(title="Updated Title")

        with pytest.raises(HTTPException) as exc_info:
            await update_property(db_session, 99999, update_data, test_user)

        assert exc_info.value.status_code == 404


class TestDeleteProperty:
    """Tests for delete_property function."""

    @pytest.mark.asyncio
    async def test_delete_property_success(
        self,
        db_session: AsyncSession,
        test_property,
        test_user,
    ):
        """Test successful property deletion."""
        from app.services.property import delete_property, get_property
        from app.core.exceptions import PropertyNotFoundException

        property_id = test_property.id

        # Mock the cache invalidation to avoid MagicMock await issues
        with patch("app.services.property.PropertyCacheManager.invalidate_property_caches", new_callable=AsyncMock):
            result = await delete_property(db_session, property_id, test_user)

        assert result is True

        # Verify deleted - should raise exception
        with pytest.raises(PropertyNotFoundException):
            await get_property(db_session, property_id)


class TestListUserProperties:
    """Tests for list_user_properties function."""

    @pytest.mark.asyncio
    async def test_list_user_properties(
        self,
        db_session: AsyncSession,
        test_user,
        test_properties,
    ):
        """Test listing properties for a user."""
        from app.services.property import list_user_properties

        result = await list_user_properties(db_session, test_user.id)

        assert len(result) == len(test_properties)


class TestPropertyFiltering:
    """Tests for property filtering."""

    @pytest.mark.asyncio
    async def test_filter_by_city(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        """Test filtering properties by city."""
        from app.services.property import get_unified_properties_optimized
        from app.schemas.property import UnifiedPropertyFilter

        filters = UnifiedPropertyFilter(city="Mumbai")

        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10
        )

        assert "items" in result
        for prop in result["items"]:
            assert prop.city == "Mumbai"

    @pytest.mark.asyncio
    async def test_filter_by_purpose(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        """Test filtering properties by purpose."""
        from app.services.property import get_unified_properties_optimized
        from app.schemas.property import UnifiedPropertyFilter

        filters = UnifiedPropertyFilter(purpose=PropertyPurpose.rent)

        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10
        )

        assert "items" in result
        for prop in result["items"]:
            assert prop.purpose == PropertyPurpose.rent

    @pytest.mark.asyncio
    async def test_filter_by_property_type(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        """Test filtering properties by type."""
        from app.services.property import get_unified_properties_optimized
        from app.schemas.property import UnifiedPropertyFilter

        filters = UnifiedPropertyFilter(property_type=[PropertyType.apartment])

        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10
        )

        assert "items" in result
        for prop in result["items"]:
            assert prop.property_type == PropertyType.apartment

    @pytest.mark.asyncio
    async def test_filter_by_gender_preference(
        self,
        db_session: AsyncSession,
        test_special_listing_properties,
        test_user,
    ):
        """Test filtering specialized listings by gender preference."""
        from app.services.property import get_unified_properties_optimized
        from app.schemas.property import UnifiedPropertyFilter

        filters = UnifiedPropertyFilter(
            gender_preference=ListingGenderPreference.female,
        )

        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10
        )

        assert "items" in result
        assert any(prop.property_type == PropertyType.pg for prop in result["items"])
        for prop in result["items"]:
            assert prop.listing_preferences is not None
            assert prop.listing_preferences.gender_preference == ListingGenderPreference.female

    @pytest.mark.asyncio
    async def test_filter_by_sharing_type(
        self,
        db_session: AsyncSession,
        test_special_listing_properties,
        test_user,
    ):
        """Test filtering specialized listings by sharing type."""
        from app.services.property import get_unified_properties_optimized
        from app.schemas.property import UnifiedPropertyFilter

        filters = UnifiedPropertyFilter(
            property_type=[PropertyType.flatmate],
            sharing_type=ListingSharingType.private_room,
        )

        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10
        )

        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0].property_type == PropertyType.flatmate
        assert result["items"][0].listing_preferences is not None
        assert (
            result["items"][0].listing_preferences.sharing_type
            == ListingSharingType.private_room
        )


class TestPropertyViewCount:
    """Tests for property view count functionality."""

    @pytest.mark.asyncio
    async def test_increment_view_count(
        self,
        db_session: AsyncSession,
        test_property,
    ):
        """Test incrementing property view count."""
        from app.services.property import increment_property_view_count

        initial_views = test_property.view_count or 0

        await increment_property_view_count(db_session, test_property.id)

        await db_session.refresh(test_property)
        assert test_property.view_count == initial_views + 1


class TestPropertyRecommendations:
    """Tests for property recommendations."""

    @pytest.mark.asyncio
    async def test_get_recommendations(
        self,
        db_session: AsyncSession,
        test_user,
        test_properties,
    ):
        """Test getting property recommendations."""
        from app.services.property import get_property_recommendations

        result = await get_property_recommendations(
            db_session,
            user_id=test_user.id,
            limit=5,
        )

        assert isinstance(result, list)
