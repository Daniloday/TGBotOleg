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

