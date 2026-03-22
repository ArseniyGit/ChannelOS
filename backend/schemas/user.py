from typing import Optional

from pydantic import BaseModel


class UserUpdate(BaseModel):
    is_subscribed: Optional[bool] = None
    is_blocked: Optional[bool] = None
