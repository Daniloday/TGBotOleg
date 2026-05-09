from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import load_settings
from app.db.database import Database
from app.db.repo.notes import NotesRepository
from app.features.notes.router import create_notes_router
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = load_settings()

    database = Database(settings.database_path)
    await database.connect()
    await database.init_schema()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(create_notes_router(NotesRepository(database)))

    try:
        logger.info("Starting polling.")
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await database.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

