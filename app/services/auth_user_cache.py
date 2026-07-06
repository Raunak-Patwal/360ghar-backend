"""Short-lived cache for local user auth snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.config import settings
from app.core.cache import get_cache_manager
from app.core.logging import get_logger
from app.models.enums import UserRole
from app.models.users import User

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AuthUserSnapshot:
    """Small authenticated-user shape for high-burst read paths."""

    id: int
    supabase_user_id: str
    is_active: bool
    role: UserRole
    agent_id: int | None = None
    email: str | None = None
    phone: str | None = None


def _key(supabase_user_id: str) -> str:
    return f"auth:user:supabase:{supabase_user_id}:v1"


def snapshot_from_user(user: User) -> AuthUserSnapshot:
    role = user.role if isinstance(user.role, UserRole) else UserRole(str(user.role))
    return AuthUserSnapshot(
        id=int(user.id),
        supabase_user_id=str(user.supabase_user_id),
        is_active=bool(user.is_active),
        role=role,
        agent_id=getattr(user, "agent_id", None),
        email=getattr(user, "email", None),
        phone=getattr(user, "phone", None),
    )


async def get_cached_auth_user(supabase_user_id: str) -> AuthUserSnapshot | None:
    try:
        raw = await get_cache_manager().get(_key(supabase_user_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Auth user cache read failed: %s", exc)
        return None

    if not isinstance(raw, dict):
        return None
    try:
        return AuthUserSnapshot(
            id=int(raw["id"]),
            supabase_user_id=str(raw["supabase_user_id"]),
            is_active=bool(raw["is_active"]),
            role=UserRole(str(raw["role"])),
            agent_id=raw.get("agent_id"),
            email=raw.get("email"),
            phone=raw.get("phone"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Invalid auth user cache payload: %s", exc)
        return None


async def cache_auth_user(snapshot: AuthUserSnapshot) -> None:
    try:
        payload: dict[str, Any] = asdict(snapshot)
        payload["role"] = snapshot.role.value
        await get_cache_manager().set(
            _key(snapshot.supabase_user_id),
            payload,
            ttl=settings.AUTH_USER_CACHE_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Auth user cache write failed: %s", exc)


async def invalidate_auth_user(supabase_user_id: str) -> None:
    try:
        await get_cache_manager().delete(_key(supabase_user_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Auth user cache invalidation failed: %s", exc)
