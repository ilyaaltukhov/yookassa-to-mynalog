"""
Async-клиент для API ФНС «Мой налог» (lknpd.nalog.ru).

Адаптировано из библиотеки nalogovich (https://github.com/Ramedon1/nalogovich).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import aiohttp

from .enums import (
    PaymentType,
    SortBy,
    CommentReturn,
    ReceiptType,
    BuyerType,
    IncomeType,
)
from .exceptions import ValidationError, AuthenticationError, ApiError
from .models import (
    ServiceCheck,
    OperationResponse,
    Income,
    IncomeInfo,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)


class NpdClient:
    def __init__(
        self,
        inn: str,
        password: str,
        proxy: str | None = None,
    ):
        self.base_url = "https://lknpd.nalog.ru/api/v1/"
        self.inn = inn
        self.password = password
        self.proxy = proxy
        self.headers: dict[str, str] = {
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/json",
        }
        self.device_info = {
            "sourceDeviceId": "-YWmoFV_Tw8ATGRD8Zym3",
            "sourceType": "WEB",
            "appVersion": "1.0.0",
            "metaDetails": {"userAgent": _USER_AGENT},
        }
        self.token: str | None = None
        self.refresh_token: str | None = None
        self.session: aiohttp.ClientSession | None = None

    # ── Session lifecycle ──────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # ── HTTP layer ─────────────────────────────────────────────────────

    def _proxy_kwargs(self) -> dict[str, str]:
        return {"proxy": self.proxy} if self.proxy else {}

    async def _request(self, method: str, endpoint: str, _retry: bool = True, **kwargs) -> Any:
        session = await self._get_session()
        kwargs.setdefault("proxy", self.proxy) if self.proxy else None

        try:
            async with session.request(
                method, self.base_url + endpoint, **kwargs
            ) as response:
                response.raise_for_status()
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()

        except aiohttp.ClientResponseError as e:
            if e.status == 401 and _retry:
                await self._re_auth()
                return await self._request(method, endpoint, _retry=False, **kwargs)
            raise

    # ── Auth ───────────────────────────────────────────────────────────

    def _apply_token(self, data: dict) -> None:
        if token := data.get("token"):
            self.token = token
            self.refresh_token = data.get("refreshToken")
            self.headers["Authorization"] = f"Bearer {token}"
            if self.session and not self.session.closed:
                self.session.headers.update({"Authorization": f"Bearer {token}"})

    async def _auth_post(self, endpoint: str, payload: dict) -> dict:
        session = await self._get_session()
        try:
            async with session.request(
                "POST", self.base_url + endpoint,
                json=payload, **self._proxy_kwargs(),
            ) as response:
                data = None
                if "application/json" in response.headers.get("Content-Type", ""):
                    data = await response.json()
                return {"status": response.status, "data": data}
        except aiohttp.ClientError as e:
            raise ApiError(f"Ошибка сети: {e}", status_code=0)

    async def auth(self) -> None:
        """Авторизация через ЛК ФЛ (lkfl)."""
        result = await self._auth_post("auth/lkfl", {
            "username": self.inn,
            "password": self.password,
            "deviceInfo": self.device_info,
        })
        status, data = result["status"], result["data"]

        if status == 422:
            msg = (data or {}).get("message", "Неверный ИНН или пароль")
            raise AuthenticationError(msg, status_code=422, response_data=data)
        if status == 401:
            raise AuthenticationError("Неавторизован. Проверьте учетные данные.", status_code=401, response_data=data)
        if status == 403:
            raise AuthenticationError("Доступ запрещен. Возможно, аккаунт заблокирован.", status_code=403, response_data=data)
        if status >= 400:
            msg = (data or {}).get("message", f"Ошибка авторизации: HTTP {status}")
            raise ApiError(msg, status_code=status, response_data=data)

        self._apply_token(data)
        logger.info("Авторизация в Мой Налог успешна")

    async def _re_auth(self) -> None:
        """Повторная авторизация через refresh token, с fallback на полный auth."""
        if not self.refresh_token:
            return await self.auth()

        result = await self._auth_post("auth/token", {
            "refreshToken": self.refresh_token,
            "deviceInfo": self.device_info,
        })
        status, data = result["status"], result["data"]

        if status in (401, 422):
            self.refresh_token = None
            return await self.auth()
        if status >= 400:
            msg = (data or {}).get("message", f"Ошибка обновления токена: HTTP {status}")
            raise ApiError(msg, status_code=status, response_data=data)

        self._apply_token(data)
        logger.debug("Токен обновлен")

    # ── Business methods ───────────────────────────────────────────────

    async def create_check(
        self,
        name: str | None = None,
        amount: float | None = None,
        services: list[ServiceCheck] | None = None,
        is_business: bool = False,
        is_foreign_organization: bool = False,
        inn_of_organization: str | None = None,
        name_of_organization: str | None = None,
        date_of_sale: datetime.datetime | None = None,
        payment_type: PaymentType = PaymentType.CASH,
        ignore_max_total_income_restriction: bool = False,
    ) -> Income:
        """Регистрация дохода (создание чека)."""
        if services:
            final_services = services
        elif name and amount is not None:
            final_services = [ServiceCheck(name=name, amount=amount, quantity=1)]
        else:
            raise ValidationError("Необходимо указать либо (name и amount), либо список services")

        total_sum = sum(s.amount * s.quantity for s in final_services)

        if is_foreign_organization:
            if not name_of_organization:
                raise ValidationError("Имя обязательно для иностранцев")
            client_payload = {"incomeType": IncomeType.FROM_FOREIGN_AGENCY.value, "displayName": name_of_organization}
        elif is_business:
            if not inn_of_organization:
                raise ValidationError("ИНН обязателен для бизнеса")
            client_payload = {"incomeType": IncomeType.FROM_LEGAL_ENTITY.value, "inn": inn_of_organization, "displayName": name_of_organization}
        else:
            client_payload = {"incomeType": IncomeType.FROM_INDIVIDUAL.value, "displayName": None, "inn": None}

        now = datetime.datetime.now().astimezone()
        sale_time = date_of_sale.astimezone() if date_of_sale else now

        payload = {
            "operationTime": sale_time.isoformat(),
            "requestTime": now.isoformat(),
            "services": [s.model_dump(by_alias=True) for s in final_services],
            "totalAmount": str(round(total_sum, 2)),
            "client": client_payload,
            "paymentType": payment_type.value,
            "ignoreMaxTotalIncomeRestriction": ignore_max_total_income_restriction,
        }

        response = await self._request("POST", "income", json=payload)
        return Income.model_validate(response)

    async def cancel_check(
        self,
        receipt_uuid: str,
        comment: CommentReturn | str = CommentReturn.wrong_receipt,
    ) -> IncomeInfo:
        """Аннулирование чека."""
        now = datetime.datetime.now().astimezone().isoformat()
        payload = {
            "operationTime": now,
            "requestTime": now,
            "comment": comment.value if isinstance(comment, CommentReturn) else comment,
            "receiptUuid": receipt_uuid,
        }
        response = await self._request("POST", "cancel", json=payload)
        return IncomeInfo.model_validate(response.get("incomeInfo", response))

    async def get_checks(
        self,
        from_date: datetime.datetime | None = None,
        to_date: datetime.datetime | None = None,
        offset: int = 0,
        limit: int = 30,
        sort_by: SortBy = SortBy.operation_time_desc,
        receipt_type: ReceiptType | None = None,
        buyer_type: BuyerType | None = None,
    ) -> OperationResponse:
        """Получение чеков за период."""
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
            "sortBy": sort_by.value,
        }
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if receipt_type:
            params["receiptType"] = receipt_type.value
        if buyer_type:
            params["buyerType"] = buyer_type.value

        response = await self._request("GET", "incomes", params=params)
        return OperationResponse.model_validate(response)
