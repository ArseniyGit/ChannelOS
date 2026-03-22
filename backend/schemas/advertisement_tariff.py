from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AdvertisementTariffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    channel_type: str = Field(..., min_length=1, max_length=50)
    thread_id: Optional[int] = Field(None, ge=1)
    duration_hours: int = Field(24, gt=0)
    price_usd: float = Field(..., gt=0)
    price_stars: Optional[int] = Field(None, gt=0)
    is_active: bool = True
    sort_order: int = Field(0, ge=0)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Название тарифа не может быть пустым')
        return v.strip()

    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Тип канала не может быть пустым')
        return v.strip()

    @field_validator('price_usd')
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Цена должна быть больше 0')
        if v > 999999:
            raise ValueError('Цена слишком большая')
        return v

    @field_validator('duration_hours')
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Длительность должна быть больше 0 часов')
        if v > 8760:  # 365 дней
            raise ValueError('Длительность не может превышать 365 дней')
        return v


class AdvertisementTariffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    channel_type: Optional[str] = Field(None, min_length=1, max_length=50)
    thread_id: Optional[int] = Field(None, ge=1)
    duration_hours: Optional[int] = Field(None, gt=0)
    price_usd: Optional[float] = Field(None, gt=0)
    price_stars: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)
