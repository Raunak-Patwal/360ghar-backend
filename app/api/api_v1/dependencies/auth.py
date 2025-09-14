from fastapi import HTTPException, status, Depends
from app.api.api_v1.endpoints.auth import get_current_active_user
from app.schemas.user import User as UserSchema


async def get_current_agent(current_user: UserSchema = Depends(get_current_active_user)) -> UserSchema:
    if current_user.role != 'agent':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent privileges required",
        )
    return current_user


async def get_current_admin(current_user: UserSchema = Depends(get_current_active_user)) -> UserSchema:
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user

