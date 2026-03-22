import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Rank, UserRank
from schemas import RankCreate, RankUpdate

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/ranks")
async def get_all_ranks(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Получить все звания (включая неактивные)"""
    verify_admin(authorization)

    result = await db.execute(select(Rank).order_by(Rank.sort_order))
    ranks = result.scalars().all()

    return {
        "success": True,
        "ranks": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "icon_emoji": r.icon_emoji,
                "required_days": r.required_days,
                "color": r.color,
                "is_active": r.is_active,
                "sort_order": r.sort_order
            }
            for r in ranks
        ]
    }


@router.post("/ranks")
async def create_rank(
    rank_data: RankCreate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Создать новое звание"""
    verify_admin(authorization)

    rank = Rank(
        name=rank_data.name,
        description=rank_data.description,
        icon_emoji=rank_data.icon_emoji,
        required_days=rank_data.required_days,
        color=rank_data.color,
        is_active=rank_data.is_active,
        sort_order=rank_data.sort_order
    )

    db.add(rank)
    await db.commit()
    await db.refresh(rank)

    logger.info(f"New rank created: {rank.name} (ID: {rank.id})")

    return {
        "success": True,
        "rank": {
            "id": rank.id,
            "name": rank.name,
            "description": rank.description,
            "icon_emoji": rank.icon_emoji,
            "required_days": rank.required_days,
            "color": rank.color,
            "is_active": rank.is_active,
            "sort_order": rank.sort_order
        }
    }


@router.patch("/ranks/{rank_id}")
async def update_rank(
    rank_id: int,
    rank_data: RankUpdate,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Обновить звание"""
    verify_admin(authorization)

    result = await db.execute(select(Rank).where(Rank.id == rank_id))
    rank = result.scalar_one_or_none()

    if not rank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rank not found")

    if rank_data.name is not None:
        rank.name = rank_data.name
    if rank_data.description is not None:
        rank.description = rank_data.description
    if rank_data.icon_emoji is not None:
        rank.icon_emoji = rank_data.icon_emoji
    if rank_data.required_days is not None:
        rank.required_days = rank_data.required_days
    if rank_data.color is not None:
        rank.color = rank_data.color
    if rank_data.is_active is not None:
        rank.is_active = rank_data.is_active
    if rank_data.sort_order is not None:
        rank.sort_order = rank_data.sort_order

    await db.commit()
    await db.refresh(rank)

    logger.info(f"Rank updated: {rank.name} (ID: {rank.id})")

    return {
        "success": True,
        "rank": {
            "id": rank.id,
            "name": rank.name,
            "description": rank.description,
            "icon_emoji": rank.icon_emoji,
            "required_days": rank.required_days,
            "color": rank.color,
            "is_active": rank.is_active,
            "sort_order": rank.sort_order
        }
    }


@router.delete("/ranks/{rank_id}")
async def delete_rank(
    rank_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Удалить звание"""
    verify_admin(authorization)

    result = await db.execute(select(Rank).where(Rank.id == rank_id))
    rank = result.scalar_one_or_none()

    if not rank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rank not found")

    users_with_rank = await db.execute(
        select(UserRank).where(UserRank.rank_id == rank_id)
    )
    user_rankings = users_with_rank.scalars().all()

    if user_rankings:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Невозможно удалить звание, так как оно присвоено пользователям")

    try:
        await db.delete(rank)
        await db.commit()
        logger.info(f"Rank deleted: {rank.name} (ID: {rank_id})")
        return {"success": True, "message": "Rank deleted"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting rank {rank_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ошибка при удалении: {str(e)}")

