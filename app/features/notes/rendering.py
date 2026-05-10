from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.db.repo.notes import NotesRepository
from app.features.notes.renderer import RenderSection, render_sections

logger = logging.getLogger(__name__)


async def render_current_state(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
) -> None:
    sections = render_sections(await repo.get_snapshot(telegram_user_id))
    old_messages = await repo.get_render_messages(telegram_user_id, chat_id)

    for section_key, message_id in old_messages.items():
        await _delete_render_message(bot, chat_id, message_id)
        await repo.delete_render_message_id(telegram_user_id, chat_id, section_key)

    for section in sections:
        await _send_section(bot, repo, telegram_user_id, chat_id, section)


async def _send_section(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
    section: RenderSection,
) -> None:
    sent = await bot.send_message(chat_id=chat_id, text=section.text)
    await repo.set_render_message_id(telegram_user_id, chat_id, section.key, sent.message_id)


async def _delete_render_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete old render message: %s", exc)
