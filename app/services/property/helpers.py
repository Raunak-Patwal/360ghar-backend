"""Shared helpers for the property service package."""

from __future__ import annotations

from app.core.exceptions import BadRequestException
from app.core.logging import get_logger
from app.models.enums import PG_FLATMATE_TYPES, PropertyPurpose, PropertyType
from app.utils.geo import wkt_point

logger = get_logger(__name__)


def validate_listing_contract(property_type: PropertyType, purpose: PropertyPurpose) -> None:
    """Ensure PG/flatmate listings use purpose 'rent'."""
    if property_type in PG_FLATMATE_TYPES and purpose != PropertyPurpose.rent:
        raise BadRequestException(detail="PG and flatmate listings must use purpose 'rent'")


_validate_listing_contract = validate_listing_contract


def build_location_wkt(latitude: float | None, longitude: float | None) -> str | None:
    """Build a PostGIS WKT POINT string with SRID=4326.

    Returns None if either coordinate is missing.
    """
    if latitude is not None and longitude is not None:
        return wkt_point(longitude, latitude)
    return None
