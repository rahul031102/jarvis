"""
Explicit, user-controlled persistent memory. JARVIS never infers and stores
facts on its own — only via the `remember` tool the user asked for.
"""
from __future__ import annotations

import aiosqlite

from pathlib import Path

from config.settings import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


class Memory:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.memory_db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    async def set(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(_SCHEMA)
            await conn.execute(
                "INSERT INTO memory (key, value, updated_at) VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                (key, value),
            )
            await conn.commit()

    async def get(self, key: str) -> str | None:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(_SCHEMA)
            cursor = await conn.execute("SELECT value FROM memory WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_all(self) -> dict[str, str]:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(_SCHEMA)
            cursor = await conn.execute("SELECT key, value FROM memory ORDER BY updated_at DESC")
            rows = await cursor.fetchall()
            return {k: v for k, v in rows}

    async def delete(self, key: str) -> bool:
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(_SCHEMA)
            cursor = await conn.execute("DELETE FROM memory WHERE key = ?", (key,))
            await conn.commit()
            return cursor.rowcount > 0
