import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Company

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/companies")
async def get_companies(
        category: str = None,
        search: str = None,
        db: AsyncSession = Depends(get_db)
):
    """Получить список компаний из справочного каталога"""
    query = select(Company).where(Company.is_active == True)

    if category:
        query = query.where(Company.category == category)

    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    companies = result.scalars().all()

    return {
        "success": True,
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "category": c.category,
                "phone": c.phone,
                "address": c.address,
                "description": c.description,
                "icon_emoji": c.icon_emoji
            }
            for c in companies
        ]
    }

