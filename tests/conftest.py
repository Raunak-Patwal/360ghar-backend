"""
Test configuration and fixtures
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base
from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.
    Uses in-memory SQLite for fast testing.
    """
    # Create in-memory SQLite engine for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def sample_user_data():
    """Sample user data for tests"""
    return {
        "supabase_user_id": "test-supabase-id",
        "email": "test@example.com",
        "phone": "+919876543210",
        "full_name": "Test User",
        "is_active": True,
        "is_verified": True,
    }


@pytest.fixture
def sample_property_data():
    """Sample property data for tests"""
    return {
        "title": "Test Property",
        "description": "A beautiful test property",
        "property_type": "apartment",
        "purpose": "rent",
        "base_price": 25000,
        "city": "Mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "is_available": True,
    }
