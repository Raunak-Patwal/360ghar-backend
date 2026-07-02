"""
Unit test specific fixtures.

Provides mock database sessions and repository fixtures
that avoid hitting real databases in unit tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """
    Mock AsyncSession for unit tests that don't need a real database.

    Use this when testing service functions in isolation.
    The mock has flush/refresh/execute/rollback configured as AsyncMocks.
    """
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=None)
    session.begin_nested = MagicMock(return_value=nested)
    session.add = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def mock_property_repository() -> MagicMock:
    """Mock PropertyRepository for service unit tests."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.get_property_with_owner = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.count = AsyncMock(return_value=0)
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.exists = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_booking_repository() -> MagicMock:
    """Mock BookingRepository for service unit tests."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.count = AsyncMock(return_value=0)
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def disable_cache():
    """
    Disable cache for the duration of a test.

    Patches the cache manager to use NullCacheBackend behavior.
    """
    with patch("app.core.cache.get_cache_manager") as mock_get:
        mock_manager = AsyncMock()
        mock_manager.get = AsyncMock(return_value=None)
        mock_manager.set = AsyncMock(return_value=True)
        mock_manager.delete = AsyncMock(return_value=True)
        mock_manager.delete_pattern = AsyncMock(return_value=0)
        mock_manager.is_available.return_value = False
        mock_get.return_value = mock_manager
        yield mock_manager
