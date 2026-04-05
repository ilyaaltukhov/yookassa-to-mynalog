from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateCheckRequest(BaseModel):
    payment_id: str = Field(..., description="ID платежа из ЮKassa", examples=["2da5c87e-0f88-5000-8000-1a2b3c4d5e6f"])
    amount: float = Field(..., gt=0, description="Сумма в рублях", examples=[249.00])
    description: str = Field(..., min_length=1, description="Описание для чека", examples=["Оплата услуг сервиса"])
    date: datetime | None = Field(None, description="Дата продажи (ISO 8601). Если не указана — текущее время", examples=["2026-03-15T14:30:00+03:00"])


class CheckResponse(BaseModel):
    payment_id: str
    receipt_uuid: str = Field(..., description="UUID чека в «Мой налог»")
    amount: float
    description: str


class CancelCheckResponse(BaseModel):
    payment_id: str
    receipt_uuid: str
    cancelled: bool


class ErrorResponse(BaseModel):
    detail: str
