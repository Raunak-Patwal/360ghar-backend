from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.cache import set_cache_manager
from app.models.enums import UserRole
from app.services.auth_user_cache import (
    AuthUserSnapshot,
    cache_auth_user,
    get_cached_auth_user,
    invalidate_auth_user,
    snapshot_from_user,
)


class _FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> object | None:
        return self.values.get(key)

    async def set(self, key: str, value: object, ttl: int | None = None) -> bool:
        self.values[key] = value
        self.ttls[key] = ttl
        return True

    async def delete(self, key: str) -> bool:
        self.values.pop(key, None)
        return True


@pytest.fixture
def fake_cache():
    cache = _FakeCache()
    set_cache_manager(cache)  # type: ignore[arg-type]
    yield cache
    set_cache_manager(None)


def test_snapshot_from_user_normalizes_role() -> None:
    user = SimpleNamespace(
        id=7,
        supabase_user_id="auth-sub",
        is_active=True,
        role=UserRole.user,
        agent_id=None,
        email="u@example.com",
        phone="+919999999999",
    )

    snapshot = snapshot_from_user(user)  # type: ignore[arg-type]

    assert snapshot.id == 7
    assert snapshot.supabase_user_id == "auth-sub"
    assert snapshot.role == UserRole.user


@pytest.mark.asyncio
async def test_cache_round_trip_and_invalidation(fake_cache: _FakeCache) -> None:
    snapshot = AuthUserSnapshot(
        id=7,
        supabase_user_id="auth-sub",
        is_active=True,
        role=UserRole.user,
    )

    await cache_auth_user(snapshot)

    cached = await get_cached_auth_user("auth-sub")
    assert cached == snapshot
    assert fake_cache.ttls["auth:user:supabase:auth-sub:v1"] == 45

    await invalidate_auth_user("auth-sub")

    assert await get_cached_auth_user("auth-sub") is None
