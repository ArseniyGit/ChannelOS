from fastapi import HTTPException, status

from core.auth import validate_telegram_data
from core.settings.config import settings


def verify_admin(authorization: str) -> dict:
    """Проверка что пользователь является администратором"""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No authorization")

    user_data = validate_telegram_data(authorization.replace("tma ", ""))
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid telegram data")

    telegram_id = user_data['telegram_id']
    if telegram_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Admin only")

    return user_data

