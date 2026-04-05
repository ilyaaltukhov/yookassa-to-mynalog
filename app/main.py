"""
Создание чеков в «Мой налог» на основе платежей из ЮKassa.

    python main.py --from 2026-01-01 --to 2026-03-31
    python main.py --from 2026-01-01 --to 2026-03-31 --dry-run
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

from yookassa import Configuration, Payment

import config
from nalog import NpdClient, CommentReturn
from utils import build_template_vars

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


def _yk_ts(dt: datetime) -> str:
    """Формат timestamp для YooKassa API: YYYY-MM-DDThh:mm:ss.mmmZ."""
    utc = dt.astimezone(timezone.utc)
    ms = utc.microsecond // 1000
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def _parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Неверный формат даты: {value!r} (ожидается YYYY-MM-DD)")


def _payment_amount(payment) -> float:
    return float(payment.amount.value)


def _is_fully_refunded(payment) -> bool:
    """Платёж полностью возвращён, если refunded_amount >= amount."""
    if not payment.refunded_amount:
        return False
    return float(payment.refunded_amount.value) >= float(payment.amount.value)


def _payment_description(payment) -> str:
    return config.INCOME_DESCRIPTION_TEMPLATE.format_map(build_template_vars(payment))


def _payment_date(payment) -> datetime:
    return datetime.fromisoformat(payment.created_at.replace("Z", "+00:00"))


# ── YooKassa ────────────────────────────────────────────────────────────

def fetch_payments(date_from: datetime, date_to: datetime) -> list:
    """Все успешные платежи из ЮKassa за период."""
    params = {
        "status": "succeeded",
        "created_at.gte": _yk_ts(date_from),
        "created_at.lte": _yk_ts(date_to),
    }

    payments = []
    res = Payment.list(params)
    payments.extend(res.items)

    while res.next_cursor:
        params["cursor"] = res.next_cursor
        res = Payment.list(params)
        payments.extend(res.items)

    return payments


# ── Output ──────────────────────────────────────────────────────────────

def print_dry_run(payments: list) -> None:
    if not payments:
        print("\nПлатежей не найдено.")
        return

    total = 0.0
    refunded_count = 0
    print(f"\n{'='*80}")
    print("  DRY RUN — чеки НЕ будут созданы")
    print(f"{'='*80}")
    print(f"\n  {'#':<4}  {'Дата':<20}  {'Сумма':>12}  {'':>10}  Описание")
    print(f"  {'-'*76}")

    for i, p in enumerate(payments, 1):
        amount = _payment_amount(p)
        total += amount
        refunded = _is_fully_refunded(p)
        if refunded:
            refunded_count += 1
        status = "ВОЗВРАТ" if refunded else ""
        date_str = p.created_at[:19].replace("T", " ")
        print(f"  {i:<4}  {date_str:<20}  {amount:>10.2f} р.  {status:>10}  {_payment_description(p)}")

    print(f"  {'-'*76}")
    print(f"  {'Итого':<26} {total:>10.2f} р.  ({len(payments)} платежей, {refunded_count} возвратов)")
    print(f"{'='*80}\n")


# ── Core ────────────────────────────────────────────────────────────────

async def create_checks(payments: list) -> None:
    async with NpdClient(config.MOY_NALOG_LOGIN, config.MOY_NALOG_PASSWORD) as client:
        await client.auth()

        success = 0
        cancelled = 0
        failed = 0
        total = len(payments)

        for i, p in enumerate(payments, 1):
            amount = _payment_amount(p)
            desc = _payment_description(p)
            refunded = _is_fully_refunded(p)

            try:
                receipt = await client.create_check(
                    name=desc,
                    amount=amount,
                    date_of_sale=_payment_date(p),
                )
                uuid = receipt.approved_receipt_uuid
                success += 1
                logging.info(
                    "[%d/%d] Чек создан: %s | %.2f р. | %s",
                    i, total, uuid, amount, desc,
                )

                if refunded:
                    await client.cancel_check(uuid, comment=CommentReturn.receipt_return)
                    cancelled += 1
                    logging.info(
                        "[%d/%d] Чек аннулирован (возврат): %s | %.2f р.",
                        i, total, uuid, amount,
                    )

            except Exception as e:
                failed += 1
                logging.error("[%d/%d] Ошибка для платежа %s (%.2f р.): %s", i, total, p.id, amount, e)

        logging.info("Готово: создано=%d, из них аннулировано=%d, ошибок=%d", success, cancelled, failed)


# ── CLI ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создание чеков в «Мой налог» по платежам из ЮKassa")
    parser.add_argument("--from", dest="date_from", required=True, type=_parse_date, help="Начало периода (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", required=True, type=_parse_date, help="Конец периода (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Только показать платежи, не создавать чеки")
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None):
    args = parse_args(argv)
    date_to = args.date_to.replace(hour=23, minute=59, second=59)

    config.validate_config(dry_run=args.dry_run)
    Configuration.configure(config.YOOKASSA_SHOP_ID, config.YOOKASSA_API_KEY)

    logging.info("Загрузка платежей из ЮKassa за %s — %s ...",
                 args.date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"))
    payments = fetch_payments(args.date_from, date_to)
    logging.info("Найдено платежей: %d", len(payments))

    if args.dry_run:
        print_dry_run(payments)
        return

    if not payments:
        logging.info("Нечего обрабатывать.")
        return

    await create_checks(payments)


if __name__ == "__main__":
    asyncio.run(main())
