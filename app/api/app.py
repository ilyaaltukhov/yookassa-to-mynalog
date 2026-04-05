"""
FastAPI-приложение для создания и отмены чеков в «Мой налог».

    uvicorn api.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import config
from nalog import NpdClient, CommentReturn
from .db import CheckDB
from .schemas import CreateCheckRequest, CheckResponse, CancelCheckResponse, ErrorResponse

logger = logging.getLogger(__name__)

db = CheckDB(path=config.DB_PATH)
nalog: NpdClient | None = None

_bearer = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if not config.API_TOKEN:
        raise HTTPException(status_code=500, detail="API_TOKEN не задан в .env")
    if credentials.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Неверный токен")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nalog

    config.validate_config(dry_run=False)

    if not config.API_TOKEN:
        logger.warning("API_TOKEN не задан — API не защищено!")

    await db.connect()
    logger.info("SQLite подключена: %s", db.path)

    nalog = NpdClient(config.MOY_NALOG_LOGIN, config.MOY_NALOG_PASSWORD)
    await nalog.auth()
    logger.info("NpdClient авторизован")

    yield

    await nalog.close()
    await db.close()


app = FastAPI(
    title="YooKassa → Мой Налог",
    version="1.0.0",
    description=(
        "API для создания и аннулирования чеков самозанятого в «Мой налог» (ФНС).\n\n"
        "Все запросы требуют заголовок `Authorization: Bearer <API_TOKEN>`."
    ),
    lifespan=lifespan,
    dependencies=[Depends(verify_token)],
)


@app.post(
    "/checks",
    response_model=CheckResponse,
    status_code=201,
    summary="Создать чек",
    responses={
        201: {"description": "Чек успешно создан"},
        409: {"description": "Чек для данного payment_id уже существует", "model": ErrorResponse},
        401: {"description": "Неверный или отсутствующий токен", "model": ErrorResponse},
    },
)
async def create_check(req: CreateCheckRequest):
    """
    Создать чек в «Мой налог» по платежу из ЮKassa.

    - **payment_id** — ID платежа из ЮKassa (используется как ключ для идемпотентности)
    - **amount** — сумма в рублях
    - **description** — текст, который будет указан в чеке
    - **date** — дата продажи; если не указана, используется текущее время
    """
    existing = await db.get_check(req.payment_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Чек для payment_id={req.payment_id} уже существует")

    receipt = await nalog.create_check(
        name=req.description,
        amount=req.amount,
        date_of_sale=req.date,
    )

    await db.save_check(
        payment_id=req.payment_id,
        receipt_uuid=receipt.approved_receipt_uuid,
        amount=req.amount,
        description=req.description,
    )

    logger.info("Чек создан: payment_id=%s receipt=%s", req.payment_id, receipt.approved_receipt_uuid)

    return CheckResponse(
        payment_id=req.payment_id,
        receipt_uuid=receipt.approved_receipt_uuid,
        amount=req.amount,
        description=req.description,
    )


@app.post(
    "/checks/{payment_id}/cancel",
    response_model=CancelCheckResponse,
    summary="Аннулировать чек (возврат)",
    responses={
        200: {"description": "Чек успешно аннулирован"},
        404: {"description": "Чек для данного payment_id не найден", "model": ErrorResponse},
        409: {"description": "Чек уже аннулирован", "model": ErrorResponse},
        401: {"description": "Неверный или отсутствующий токен", "model": ErrorResponse},
    },
)
async def cancel_check(payment_id: str):
    """
    Аннулировать чек в «Мой налог» по payment_id из ЮKassa.

    Причина аннулирования: «Чек возвращен».
    """
    check = await db.get_check(payment_id)
    if not check:
        raise HTTPException(status_code=404, detail=f"Чек для payment_id={payment_id} не найден")

    if check["cancelled_at"]:
        raise HTTPException(status_code=409, detail=f"Чек для payment_id={payment_id} уже аннулирован")

    await nalog.cancel_check(check["receipt_uuid"], comment=CommentReturn.receipt_return)
    await db.mark_cancelled(payment_id)

    logger.info("Чек аннулирован: payment_id=%s receipt=%s", payment_id, check["receipt_uuid"])

    return CancelCheckResponse(
        payment_id=payment_id,
        receipt_uuid=check["receipt_uuid"],
        cancelled=True,
    )
