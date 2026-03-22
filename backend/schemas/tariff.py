from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TariffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price_usd: float = Field(..., gt=0)
    price_stars: Optional[int] = Field(None, gt=0)
    duration_days: int = Field(..., gt=0)
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Название тарифа не может быть пустым')
        return v.strip()

    @field_validator('price_usd')
    @classmethod
    def validate_price_usd(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Цена должна быть больше 0')
        if v > 999999:
            raise ValueError('Цена слишком большая')
        return v

    @field_validator('price_stars')
    @classmethod
    def validate_price_stars(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v <= 0:
                raise ValueError('Цена в Stars должна быть больше 0')
            if v > 999999:
                raise ValueError('Цена в Stars слишком большая')
        return v

    @field_validator('duration_days')
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Длительность должна быть больше 0 дней')
        if v > 3650:
            raise ValueError('Длительность не может превышать 10 лет')
        return v


class TariffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price_usd: Optional[float] = Field(None, gt=0)
    price_stars: Optional[int] = Field(None, gt=0)
    duration_days: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None
