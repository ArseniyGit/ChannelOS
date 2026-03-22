from pydantic import BaseModel


class PaymentRequest(BaseModel):
    tariff_id: int
    payment_method: str  # "stars" or "stripe"

