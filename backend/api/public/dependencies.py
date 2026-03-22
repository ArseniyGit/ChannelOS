from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import validate_telegram_data
from core.db.database import get_db
from core.db.models import User


def require_telegram_user_data(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No auth")
    if not authorization.startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth scheme",
        )

    user_data = validate_telegram_data(authorization.replace("tma ", ""))
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid data"
        )
    return user_data


async def require_current_user(
    user_data: dict = Depends(require_telegram_user_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == user_data["telegram_id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
