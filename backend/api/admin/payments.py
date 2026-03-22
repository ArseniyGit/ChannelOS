import logging

from fastapi import APIRouter, Depends, Header
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import get_db
from core.db.models import Payment, User

from .auth import verify_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/payments")
async def get_all_payments(
    authorization: str = Header(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех платежей"""
    verify_admin(authorization)

    query = select(Payment).offset(skip).limit(limit).order_by(desc(Payment.created_at))
    result = await db.execute(query)
    payments = result.scalars().all()

    payments_data = []
    for payment in payments:
        user_result = await db.execute(select(User).where(User.id == payment.user_id))
        user = user_result.scalar_one_or_none()

        payments_data.append({
            "id": payment.id,
            "user_id": payment.user_id,
            "user_telegram_id": user.telegram_id if user else None,
            "user_name": user.first_name if user else "Unknown",
            "username": user.username if user else None,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "payment_system": payment.payment_system or "unknown",
            "transaction_id": payment.transaction_id,
            "created_at": payment.created_at.isoformat() if payment.created_at else None
        })

    return {
        "success": True,
        "payments": payments_data
    }

