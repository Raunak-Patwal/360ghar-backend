from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.amenity import Amenity
from app.services.property import get_all_amenities

router = APIRouter()

@router.get("/", response_model=List[Amenity])
async def list_amenities(db: AsyncSession = Depends(get_db)):
    return await get_all_amenities(db)

