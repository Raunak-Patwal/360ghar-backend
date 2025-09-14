from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from app.core.database import get_db
from app.api.api_v1.endpoints.auth import get_current_active_user
from app.schemas.user import User as UserSchema
from app.services.storage import storage_service

router = APIRouter()

@router.post("/", response_model=Dict[str, Any])
async def upload_file(
    file: UploadFile = File(...),
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # For now, upload to a generic folder. Frontend can associate URL later.
    return await storage_service.upload_generic(file)

