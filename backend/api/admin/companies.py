import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Company
from schemas import CompanyCreate, CompanyUpdate

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/companies")
async def get_all_companies(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить все компании"""
    verify_admin(authorization)

    result = await db.execute(select(Company).order_by(Company.name))
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
                "icon_emoji": c.icon_emoji,
                "is_active": c.is_active
            }
            for c in companies
        ]
    }


@router.post("/companies")
async def create_company(
    company_data: CompanyCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Создать новую компанию"""
    verify_admin(authorization)

    company = Company(
        name=company_data.name,
        category=company_data.category,
        phone=company_data.phone,
        address=company_data.address,
        description=company_data.description,
        icon_emoji=company_data.icon_emoji,
        is_active=company_data.is_active
    )

    db.add(company)
    await db.commit()
    await db.refresh(company)

    logger.info(f"New company created: {company.name} (ID: {company.id})")

    return {
        "success": True,
        "company": {
            "id": company.id,
            "name": company.name,
            "category": company.category,
            "phone": company.phone,
            "address": company.address,
            "description": company.description,
            "icon_emoji": company.icon_emoji,
            "is_active": company.is_active
        }
    }


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Обновить компанию"""
    verify_admin(authorization)

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if company_data.name is not None:
        company.name = company_data.name
    if company_data.category is not None:
        company.category = company_data.category
    if company_data.phone is not None:
        company.phone = company_data.phone
    if company_data.address is not None:
        company.address = company_data.address
    if company_data.description is not None:
        company.description = company_data.description
    if company_data.icon_emoji is not None:
        company.icon_emoji = company_data.icon_emoji
    if company_data.is_active is not None:
        company.is_active = company_data.is_active

    await db.commit()
    await db.refresh(company)

    logger.info(f"Company updated: {company.name} (ID: {company.id})")

    return {
        "success": True,
        "company": {
            "id": company.id,
            "name": company.name,
            "category": company.category,
            "phone": company.phone,
            "address": company.address,
            "description": company.description,
            "icon_emoji": company.icon_emoji,
            "is_active": company.is_active
        }
    }


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Удалить компанию"""
    verify_admin(authorization)

    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    await db.delete(company)
    await db.commit()

    logger.info(f"Company deleted: {company.name} (ID: {company.id})")

    return {"success": True, "message": "Company deleted"}

