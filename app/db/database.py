from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiosqlite

from app.db.schema import SCHEMA_SQL


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA foreign_keys = ON")
        return self.connection

    async def init_schema(self) -> None:
        if self.connection is None:
            raise RuntimeError("Database is not connected.")
        await self._migrate_render_state()
        await self.connection.executescript(SCHEMA_SQL)
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    def require_connection(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database is not connected.")
        return self.connection

    async def _migrate_render_state(self) -> None:
        if self.connection is None:
            raise RuntimeError("Database is not connected.")

        async with self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'render_state'"
        ) as cursor:
            exists = await cursor.fetchone()
        if exists is None:
            return

        async with self.connection.execute("PRAGMA table_info(render_state)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
        if "section_key" not in columns:
            await self.connection.execute("DROP TABLE render_state")
