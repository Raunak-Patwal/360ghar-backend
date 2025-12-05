"""
Repository for user data access
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository
from app.models.users import User
from app.core.logging import get_logger

logger = get_logger(__name__)

class UserRepository(BaseRepository[User]):
    """User repository with query helpers"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_supabase_id(self, supabase_user_id: str) -> Optional[User]:
        """Get user by Supabase user ID"""
        stmt = select(User).where(User.supabase_user_id == supabase_user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone"""
        stmt = select(User).where(User.phone == phone)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
