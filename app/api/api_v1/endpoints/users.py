from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.api_v1.endpoints.auth import get_current_active_user
from app.api.api_v1.dependencies.auth import get_current_admin, get_current_agent
from app.schemas.user import UserUpdate, User as UserSchema, UserPreferences, LocationUpdate
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.user import (
    update_user, update_user_preferences, update_user_location,
    get_all_users, get_user_by_id
)
from app.services.agent import assign_agent_to_user

router = APIRouter()

@router.get("/profile/", response_model=UserSchema)
async def get_user_profile(current_user: UserSchema = Depends(get_current_active_user)):
    """Get current user profile"""
    return current_user

@router.put("/profile/", response_model=UserSchema)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile"""
    updated_user = await update_user(db, current_user.id, user_update, actor=current_user)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    return updated_user

@router.put("/preferences/", response_model=MessageResponse)
async def update_preferences(
    preferences: UserPreferences,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user preferences"""
    await update_user_preferences(db, current_user.id, preferences.dict())
    return MessageResponse(message="Preferences updated successfully")

@router.put("/location/", response_model=MessageResponse)
async def update_location(
    location_update: LocationUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's current location"""
    await update_user_location(
        db, 
        current_user.id, 
        location_update.latitude, 
        location_update.longitude
    )
    return MessageResponse(message="Location updated successfully")


# Admin/Agent management endpoints
@router.get("/", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Search by name/email/phone"),
    agent_id: int | None = Query(None, description="Filter by agent id (admin only)"),
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List users. Admins see all (optionally filter by agent). Agents see their assigned users."""
    # Resolve effective agent filter based on role
    effective_agent_id = None
    if current_user.role == 'admin':
        effective_agent_id = agent_id
    elif current_user.role == 'agent':
        effective_agent_id = current_user.agent_id
        if effective_agent_id is None:
            # Agents without linked agent profile manage nobody
            return {
                "items": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            }
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    users, total = await get_all_users(db, page=page, limit=limit, search_query=q, filter_agent_id=effective_agent_id)
    # Convert to schema dicts
    from app.schemas.user import User as UserSchemaModel
    items = [UserSchemaModel.model_validate(u) for u in users]
    total_pages = (total + limit - 1) // limit
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/{user_id}/", response_model=UserSchema)
async def get_user_details(
    user_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Authorization
    if current_user.role == 'admin':
        pass
    elif current_user.role == 'agent':
        if current_user.agent_id is None or user.agent_id != current_user.agent_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    from app.schemas.user import User as UserSchemaModel
    return UserSchemaModel.model_validate(user)


@router.put("/{user_id}/", response_model=UserSchema)
async def update_user_details(
    user_id: int,
    user_update: UserUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Admin can update any user; Agent can update limited fields for assigned users
    updated_user = await update_user(db, user_id, user_update, actor=current_user)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")
    from app.schemas.user import User as UserSchemaModel
    return UserSchemaModel.model_validate(updated_user)


@router.post("/{user_id}/assign-agent/", response_model=MessageResponse)
async def assign_agent_to_specific_user(
    user_id: int,
    payload: dict,
    current_user: UserSchema = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    new_agent_id = payload.get("agent_id")
    if not isinstance(new_agent_id, int):
        raise HTTPException(status_code=400, detail="agent_id is required and must be an integer")
    assignment = await assign_agent_to_user(db, user_id, new_agent_id)
    if not assignment:
        raise HTTPException(status_code=400, detail="Failed to assign agent")
    return MessageResponse(message="Agent assigned successfully")
