from __future__ import annotations

import enum


class PaymentType(str, enum.Enum):
    CASH = "CASH"
    ACCOUNT = "ACCOUNT"


class CommentReturn(str, enum.Enum):
    wrong_receipt = "Чек сформирован ошибочно"
    receipt_return = "Чек возвращен"


class IncomeType(str, enum.Enum):
    FROM_INDIVIDUAL = "FROM_INDIVIDUAL"
    FROM_LEGAL_ENTITY = "FROM_LEGAL_ENTITY"
    FROM_FOREIGN_AGENCY = "FROM_FOREIGN_AGENCY"


class SortBy(str, enum.Enum):
    operation_time_asc = "operation_time:asc"
    operation_time_desc = "operation_time:desc"
    total_amount_asc = "total_amount:asc"
    total_amount_desc = "total_amount:desc"


class ReceiptType(str, enum.Enum):
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


class BuyerType(str, enum.Enum):
    PERSON = "PERSON"
    COMPANY = "COMPANY"
    FOREIGN_AGENCY = "FOREIGN_AGENCY"
