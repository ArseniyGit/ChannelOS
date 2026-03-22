import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    icon_emoji: Optional[str] = Field("🏢", max_length=10)
    is_active: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Название компании не может быть пустым')
        return v.strip()

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Категория не может быть пустой')
        return v.strip()

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None

        phone_clean = v.strip()
        if not re.match(r'^[\d\s\+\-\(\)]+$', phone_clean):
            raise ValueError('Телефон может содержать только цифры и символы: + - ( )')

        digits_only = re.sub(r'[\s\+\-\(\)]', '', phone_clean)
        if len(digits_only) < 5:
            raise ValueError('Номер телефона слишком короткий (минимум 5 цифр)')

        if len(digits_only) > 15:
            raise ValueError('Номер телефона слишком длинный (максимум 15 цифр)')

        return phone_clean


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    icon_emoji: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError('Название компании не может быть пустым')
        return v.strip() if v else v

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v or not v.strip()):
            raise ValueError('Категория не может быть пустой')
        return v.strip() if v else v

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None

        phone_clean = v.strip()
        if not re.match(r'^[\d\s\+\-\(\)]+$', phone_clean):
            raise ValueError('Телефон может содержать только цифры и символы: + - ( )')

        digits_only = re.sub(r'[\s\+\-\(\)]', '', phone_clean)
        if len(digits_only) < 5:
            raise ValueError('Номер телефона слишком короткий (минимум 5 цифр)')

        if len(digits_only) > 15:
            raise ValueError('Номер телефона слишком длинный (максимум 15 цифр)')

        return phone_clean

