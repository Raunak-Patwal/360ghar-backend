from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_supabase_auth_client, verify_supabase_token, admin_find_user_by_phone
from app.core.logging import get_logger
from app.schemas.user import UserCreate, UserLogin, User as UserSchema
from app.services.user import get_or_create_user_from_supabase
import anyio
from typing import Optional

router = APIRouter()
logger = get_logger(__name__)

async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> UserSchema:
    """Get current user from token"""
    if not authorization:
        logger.debug("Authorization header missing")
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_HEADER_MISSING",
                "message": "Authorization header missing",
            },
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            logger.warning("Invalid authentication scheme")
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_AUTH_SCHEME",
                    "message": "Invalid authentication scheme. Use Bearer.",
                },
            )
    except ValueError:
        logger.warning("Invalid authorization header format")
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_AUTH_HEADER",
                "message": "Invalid authorization header format",
            },
        )
    
    try:
        supabase_user_data = await verify_supabase_token(token)
        if not supabase_user_data:
            logger.warning("Invalid or expired token")
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "TOKEN_INVALID",
                    "message": "Invalid or expired token",
                },
            )
        
        db_user = await get_or_create_user_from_supabase(db, supabase_user_data)
        logger.debug(f"User authenticated successfully: {db_user.id}")
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTHENTICATION_FAILED",
                "message": "Authentication failed",
            },
        )

async def get_current_active_user(current_user: UserSchema = Depends(get_current_user)) -> UserSchema:
    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "USER_INACTIVE",
                "message": "Inactive user",
            },
        )
    return current_user

async def get_current_user_optional(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[UserSchema]:
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        
        supabase_user_data = await verify_supabase_token(token)
        if supabase_user_data:
            return await get_or_create_user_from_supabase(db, supabase_user_data)
    except Exception:
        pass
    
    return None

@router.post("/login")
async def login(user_login: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login with Supabase Auth using phone + password"""
    try:
        supabase = get_supabase_auth_client()
        data = await anyio.to_thread.run_sync(
            lambda: supabase.auth.sign_in_with_password({
                "phone": user_login.phone,
                "password": user_login.password,
            })
        )

        # If the response lacks a usable session/token, try to classify the cause
        if not getattr(data, "session", None) or not getattr(data.session, "access_token", None):
            # Attempt admin lookup to distinguish not found vs wrong password
            supa_user = await admin_find_user_by_phone(user_login.phone)
            if not supa_user:
                logger.warning("Login failed: user not found (admin lookup)", extra={"phone": user_login.phone})
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "USER_NOT_FOUND",
                        "message": "User with this phone does not exist",
                    },
                )
            logger.warning("Login failed: invalid credentials", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid phone or password",
                },
            )

        # Verify token and ensure account is verified where applicable
        supabase_user_data = await verify_supabase_token(data.session.access_token)
        if not supabase_user_data:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "TOKEN_INVALID",
                    "message": "Invalid or expired token",
                },
            )

        if not supabase_user_data.get("email_verified", False):
            logger.warning("Login blocked: unverified account", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UNVERIFIED_ACCOUNT",
                    "message": "Please verify your email or phone before logging in",
                },
            )

        db_user = await get_or_create_user_from_supabase(db, supabase_user_data)

        return {
            "access_token": data.session.access_token,
            "token_type": "bearer",
            "user": db_user,
        }
    except HTTPException:
        # Re-raise structured exceptions
        raise
    except Exception as e:
        # Heuristic classification for common Supabase auth errors
        msg = str(e).lower()

        if any(k in msg for k in ["confirm", "verified", "verification"]):
            logger.error(f"Authentication failed (unverified): {e}", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "UNVERIFIED_ACCOUNT",
                    "message": "Please verify your email or phone before logging in",
                },
            )
        if any(k in msg for k in ["too many", "rate", "rate limit", "throttle"]):
            logger.error(f"Authentication rate limited: {e}", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": "Too many attempts. Please try again later",
                },
            )

        # Try admin lookup as a fallback to classify not found vs invalid password
        try:
            supa_user = await admin_find_user_by_phone(user_login.phone)
        except Exception:
            supa_user = None

        if not supa_user:
            logger.error(f"Authentication failed: user not found ({e})", extra={"phone": user_login.phone})
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": "User with this phone does not exist",
                },
            )

        logger.error(f"Authentication failed: invalid credentials ({e})", extra={"phone": user_login.phone})
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid phone or password",
            },
        )

@router.post("/register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register via Supabase Auth using phone as primary identifier"""
    try:
        supabase = get_supabase_auth_client()
        data = await anyio.to_thread.run_sync(
            lambda: supabase.auth.sign_up({
                "phone": user_data.phone,
                "password": user_data.password,
                "options": {
                    "data": {
                        "full_name": user_data.full_name,
                        "email": user_data.email
                    }
                }
            })
        )
        
        if data.user:
            supabase_user_data = {
                "id": data.user.id,
                "phone": data.user.phone,
                "email": data.user.email,
                "user_metadata": data.user.user_metadata or {}
            }
            
            db_user = await get_or_create_user_from_supabase(db, supabase_user_data)
            
            return {
                "message": "User registered successfully",
                "user": db_user,
                "access_token": data.session.access_token if data.session else None
            }
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "REGISTRATION_FAILED",
                    "message": "Registration failed",
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REGISTRATION_FAILED",
                "message": f"Registration failed: {str(e)}",
            },
        )
