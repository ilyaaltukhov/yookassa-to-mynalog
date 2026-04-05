"""Async SQLite storage для маппинга payment_id → receipt_uuid."""

from __future__ import annotations

import aiosqlite

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS checks (
    payment_id  TEXT PRIMARY KEY,
    receipt_uuid TEXT NOT NULL,
    amount       REAL NOT NULL,
    description  TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_at TEXT
)
"""


class CheckDB:
    def __init__(self, path: str = "checks.db"):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def save_check(
        self, payment_id: str, receipt_uuid: str, amount: float, description: str,
    ) -> None:
        await self._db.execute(
            "INSERT INTO checks (payment_id, receipt_uuid, amount, description) VALUES (?, ?, ?, ?)",
            (payment_id, receipt_uuid, amount, description),
        )
        await self._db.commit()

    async def get_check(self, payment_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM checks WHERE payment_id = ?", (payment_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def mark_cancelled(self, payment_id: str) -> None:
        await self._db.execute(
            "UPDATE checks SET cancelled_at = datetime('now') WHERE payment_id = ?",
            (payment_id,),
        )
        await self._db.commit()
