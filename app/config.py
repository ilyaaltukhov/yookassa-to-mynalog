import os
import time
from dotenv import load_dotenv

load_dotenv()

TZ = os.getenv("TZ")
if TZ:
    os.environ["TZ"] = TZ
    time.tzset()

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_API_KEY = os.getenv("YOOKASSA_API_KEY")
MOY_NALOG_LOGIN = os.getenv("MOY_NALOG_LOGIN")
MOY_NALOG_PASSWORD = os.getenv("MOY_NALOG_PASSWORD")

INCOME_DESCRIPTION_TEMPLATE = os.getenv("INCOME_DESCRIPTION_TEMPLATE", "Платеж #{description}")

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "checks.db"))

API_TOKEN = os.getenv("API_TOKEN")


def validate_config(*, dry_run: bool = False):
    required = [
        ("YOOKASSA_SHOP_ID", YOOKASSA_SHOP_ID),
        ("YOOKASSA_API_KEY", YOOKASSA_API_KEY),
    ]
    if not dry_run:
        required += [
            ("MOY_NALOG_LOGIN", MOY_NALOG_LOGIN),
            ("MOY_NALOG_PASSWORD", MOY_NALOG_PASSWORD),
        ]

    missing = [name for name, val in required if not val]
    if missing:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")
