from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=_to_camel)


class ServiceCheck(CamelModel):
    name: str
    quantity: int
    amount: float


class Service(CamelModel):
    name: str
    quantity: int
    service_number: int
    amount: float


class Income(CamelModel):
    approved_receipt_uuid: str


class CancellationInfo(CamelModel):
    operation_time: str
    register_time: str
    tax_period_id: int
    comment: str


class IncomeInfo(CamelModel):
    approved_receipt_uuid: str
    name: str
    operation_time: str
    request_time: str
    payment_type: str
    partner_code: str | None = None
    total_amount: float
    cancellation_info: CancellationInfo | None = None
    source_device_id: str


class Operation(CamelModel):
    approved_receipt_uuid: str
    name: str
    services: list[Service]
    operation_time: str
    request_time: str
    register_time: str
    tax_period_id: int
    payment_type: str
    income_type: str
    partner_code: str | None = None
    total_amount: float
    cancellation_info: dict | None = None
    source_device_id: str
    client_inn: str | None = None
    client_display_name: str | None = None
    partner_display_name: str | None = None
    partner_logo: str | None = None
    partner_inn: str | None = None
    inn: str
    profession: str
    description: list[str] = []
    invoice_id: str | None = None


class OperationResponse(CamelModel):
    content: list[Operation]
    has_more: bool
    current_offset: int
    current_limit: int
