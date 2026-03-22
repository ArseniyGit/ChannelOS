from typing import Optional

from pydantic import BaseModel


class AdvertisementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    delete_after_hours: Optional[int] = None
    status: Optional[str] = None
    price: Optional[float] = None
    channel_id: Optional[str] = None
