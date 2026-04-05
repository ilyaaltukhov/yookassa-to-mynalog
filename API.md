# API Documentation

Интерактивная документация (Swagger UI) доступна по адресу `/docs` после запуска сервера.

## Base URL

```
https://your-domain.ru
```

## Авторизация

Все запросы требуют заголовок:

```
Authorization: Bearer <API_TOKEN>
```

Токен задаётся в `.env` переменной `API_TOKEN`.

**Ответ при отсутствии/неверном токене:**

```
HTTP 401
{"detail": "Неверный токен"}
```

---

## Endpoints

### POST /checks

Создать чек в «Мой налог».

**Идемпотентность:** если чек для данного `payment_id` уже существует — вернёт `409`.

#### Request

```http
POST /checks
Authorization: Bearer <API_TOKEN>
Content-Type: application/json
```

```json
{
  "payment_id": "2da5c87e-0f88-5000-8000-1a2b3c4d5e6f",
  "amount": 249.00,
  "description": "Оплата услуг сервиса",
  "date": "2026-03-15T14:30:00+03:00"
}
```

| Поле | Тип | Обязательное | Описание |
|---|---|:-:|---|
| `payment_id` | string | да | ID платежа из ЮKassa |
| `amount` | float | да | Сумма в рублях (> 0) |
| `description` | string | да | Текст для чека |
| `date` | string (ISO 8601) | нет | Дата продажи. По умолчанию — текущее время |

#### Response `201 Created`

```json
{
  "payment_id": "2da5c87e-0f88-5000-8000-1a2b3c4d5e6f",
  "receipt_uuid": "2a0bzznrt0",
  "amount": 249.0,
  "description": "Оплата услуг сервиса"
}
```

| Поле | Тип | Описание |
|---|---|---|
| `payment_id` | string | ID платежа из ЮKassa |
| `receipt_uuid` | string | UUID чека в «Мой налог» |
| `amount` | float | Сумма |
| `description` | string | Описание |

#### Errors

| Код | Причина |
|---|---|
| `409 Conflict` | Чек для данного `payment_id` уже существует |
| `401 Unauthorized` | Неверный или отсутствующий токен |

---

### POST /checks/{payment_id}/cancel

Аннулировать чек в «Мой налог» (возврат).

Причина аннулирования: «Чек возвращен».

#### Request

```http
POST /checks/{payment_id}/cancel
Authorization: Bearer <API_TOKEN>
```

Тело запроса не требуется.

| Параметр | Где | Описание |
|---|---|---|
| `payment_id` | path | ID платежа из ЮKassa |

#### Response `200 OK`

```json
{
  "payment_id": "2da5c87e-0f88-5000-8000-1a2b3c4d5e6f",
  "receipt_uuid": "2a0bzznrt0",
  "cancelled": true
}
```

| Поле | Тип | Описание |
|---|---|---|
| `payment_id` | string | ID платежа |
| `receipt_uuid` | string | UUID аннулированного чека |
| `cancelled` | bool | Всегда `true` |

#### Errors

| Код | Причина |
|---|---|
| `404 Not Found` | Чек для данного `payment_id` не найден в базе |
| `409 Conflict` | Чек уже аннулирован |
| `401 Unauthorized` | Неверный или отсутствующий токен |

---

## Примеры

### curl

```bash
# Создать чек
curl -X POST https://your-domain.ru/checks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "2da5c87e-0f88-5000-8000-1a2b3c4d5e6f",
    "amount": 249.00,
    "description": "Оплата услуг сервиса"
  }'

# Аннулировать чек
curl -X POST https://your-domain.ru/checks/2da5c87e-0f88-5000-8000-1a2b3c4d5e6f/cancel \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Python (requests)

```python
import requests

BASE = "https://your-domain.ru"
HEADERS = {"Authorization": "Bearer YOUR_TOKEN"}

# Создать чек
resp = requests.post(f"{BASE}/checks", json={
    "payment_id": "2da5c87e-0f88-5000-8000-1a2b3c4d5e6f",
    "amount": 249.00,
    "description": "Оплата услуг сервиса",
}, headers=HEADERS)
print(resp.json())

# Аннулировать чек
resp = requests.post(
    f"{BASE}/checks/2da5c87e-0f88-5000-8000-1a2b3c4d5e6f/cancel",
    headers=HEADERS,
)
print(resp.json())
```

### Python (aiohttp)

```python
import aiohttp

BASE = "https://your-domain.ru"
HEADERS = {"Authorization": "Bearer YOUR_TOKEN"}

async def create_and_cancel():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Создать чек
        async with session.post(f"{BASE}/checks", json={
            "payment_id": "abc-123",
            "amount": 249.00,
            "description": "Оплата услуг",
        }) as resp:
            data = await resp.json()
            print("Создан:", data)

        # Аннулировать чек
        async with session.post(f"{BASE}/checks/abc-123/cancel") as resp:
            data = await resp.json()
            print("Аннулирован:", data)
```

### JavaScript (fetch)

```javascript
const BASE = "https://your-domain.ru";
const HEADERS = {
  "Authorization": "Bearer YOUR_TOKEN",
  "Content-Type": "application/json",
};

// Создать чек
const createResp = await fetch(`${BASE}/checks`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    payment_id: "abc-123",
    amount: 249.0,
    description: "Оплата услуг",
  }),
});
console.log(await createResp.json());

// Аннулировать чек
const cancelResp = await fetch(`${BASE}/checks/abc-123/cancel`, {
  method: "POST",
  headers: HEADERS,
});
console.log(await cancelResp.json());
```

---

## Хранение данных

Маппинг `payment_id → receipt_uuid` хранится в SQLite (путь задаётся через `DB_PATH` в `.env`).

Схема таблицы `checks`:

| Поле | Тип | Описание |
|---|---|---|
| `payment_id` | TEXT, PK | ID платежа из ЮKassa |
| `receipt_uuid` | TEXT | UUID чека в «Мой налог» |
| `amount` | REAL | Сумма |
| `description` | TEXT | Описание |
| `created_at` | TEXT | Время создания (UTC) |
| `cancelled_at` | TEXT / NULL | Время аннулирования (NULL если не аннулирован) |
