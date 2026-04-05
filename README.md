# YooKassa → Мой Налог

Создание чеков в «Мой Налог» на основе платежей из ЮKassa. Два режима работы:

- **CLI-скрипт** — массовое создание чеков за период дат
- **HTTP API** — создание и отмена чеков по одному (для интеграции с вашим сервисом)

## Требования

- Python 3.11+
- Учётные данные ЮKassa (Shop ID + API ключ) — только для CLI
- Учётные данные Мой Налог (ИНН + пароль от ЛК ФЛ)

## Установка

```bash
git clone https://github.com/grandvan709/yookassa-to-mynalog.git
cd yookassa-to-mynalog
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполнить .env своими данными
```

## Конфигурация (.env)

| Переменная | Обязательная | Описание |
|---|:-:|---|
| `YOOKASSA_SHOP_ID` | CLI | ID магазина в ЮKassa |
| `YOOKASSA_API_KEY` | CLI | API ключ ЮKassa |
| `MOY_NALOG_LOGIN` | да | ИНН (логин от ЛК налоговой) |
| `MOY_NALOG_PASSWORD` | да | Пароль от ЛК налоговой |
| `TZ` | нет | Часовой пояс (по умолчанию `Europe/Moscow`) |
| `INCOME_DESCRIPTION_TEMPLATE` | нет | Шаблон описания дохода (по умолчанию `Платеж #{description}`) |
| `DB_PATH` | нет | Путь к SQLite базе для API (по умолчанию `app/checks.db`) |
| `API_TOKEN` | API | Токен авторизации для API (`Authorization: Bearer <token>`) |

---

## CLI-скрипт

Массовое создание чеков за период. Забирает платежи из ЮKassa, создаёт чеки в «Мой Налог». Полностью возвращённые платежи автоматически аннулируются.

### Просмотр платежей (dry-run)

```bash
python app/main.py --from 2026-01-01 --to 2026-03-31 --dry-run
```

### Создание чеков

```bash
python app/main.py --from 2026-01-01 --to 2026-03-31
```

### Переменные шаблона INCOME_DESCRIPTION_TEMPLATE

| Переменная | Описание |
|---|---|
| `{description}` | Описание платежа из ЮKassa (или ID, если нет) |
| `{id}` | ID платежа (UUID) |
| `{order_number}` | Номер счёта/заказа |
| `{customer_name}` | Имя покупателя |
| `{amount}` | Сумма платежа |

---

## HTTP API

Два эндпоинта для интеграции с вашим сервисом. Данные о чеках хранятся в SQLite.

### Запуск

```bash
cd app
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Документация: `http://localhost:8000/docs`

Все запросы требуют заголовок `Authorization: Bearer <API_TOKEN>`.

### POST /checks — создать чек

```bash
curl -X POST http://localhost:8000/checks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"payment_id": "abc-123", "amount": 249.00, "description": "Оплата услуг"}'
```

Ответ `201`:
```json
{
  "payment_id": "abc-123",
  "receipt_uuid": "2a0bzznrt0",
  "amount": 249.0,
  "description": "Оплата услуг"
}
```

### POST /checks/{payment_id}/cancel — аннулировать чек (возврат)

```bash
curl -X POST http://localhost:8000/checks/abc-123/cancel \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Ответ `200`:
```json
{
  "payment_id": "abc-123",
  "receipt_uuid": "2a0bzznrt0",
  "cancelled": true
}
```

### Ошибки

| Код | Когда |
|---|---|
| `409` | Чек для этого payment_id уже существует / уже аннулирован |
| `404` | Чек для этого payment_id не найден (при отмене) |

---

## Деплой

См. [DEPLOY.md](DEPLOY.md) — настройка systemd + nginx.

## Структура проекта

```
app/
  main.py          — CLI-скрипт (массовое создание чеков)
  config.py        — конфигурация из .env
  utils.py         — шаблоны описаний платежей
  nalog/           — клиент API «Мой Налог»
    client.py      — NpdClient (авторизация, создание/отмена чеков)
    models.py      — Pydantic-модели
    enums.py       — перечисления
    exceptions.py  — исключения
  api/             — HTTP API (FastAPI)
    app.py         — приложение, эндпоинты, lifespan
    db.py          — async SQLite (маппинг payment_id → receipt_uuid)
    schemas.py     — схемы запросов/ответов
```
