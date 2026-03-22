from typing import Optional

from pydantic import BaseModel, Field


class RankCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon_emoji: Optional[str] = Field("🏆", max_length=10)
    required_days: int = Field(..., ge=0)
    color: Optional[str] = Field("#007BFF", max_length=20)
    is_active: bool = True
    sort_order: int = Field(0, ge=0)


class RankUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon_emoji: Optional[str] = Field(None, max_length=10)
    required_days: Optional[int] = Field(None, ge=0)
    color: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)

