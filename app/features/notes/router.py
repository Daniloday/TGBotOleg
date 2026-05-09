from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from app.db.repo.notes import NotesRepository
from app.features.notes.parser import parse_user_text
from app.features.notes.renderer import RenderSection, render_sections
from app.features.notes.service import apply_note_action

logger = logging.getLogger(__name__)


def create_notes_router(repo: NotesRepository) -> Router:
    router = Router(name="notes")

    @router.message()
    async def handle_message(message: Message, bot: Bot) -> None:
        if message.from_user is None:
            return

        telegram_user_id = message.from_user.id
        text = message.text or message.caption or ""
        action = parse_user_text(text)
        await apply_note_action(repo, telegram_user_id, action)
        await _delete_user_message(message)
        await _render_current_state(bot, repo, telegram_user_id, message.chat.id)

    return router


async def _delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete user message: %s", exc)


async def _render_current_state(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
) -> None:
    sections = render_sections(await repo.get_snapshot(telegram_user_id))
    old_messages = await repo.get_render_messages(telegram_user_id, chat_id)
    active_keys = {section.key for section in sections}

    for section in sections:
        await _render_section(bot, repo, telegram_user_id, chat_id, section, old_messages.get(section.key))

    for stale_key, message_id in old_messages.items():
        if stale_key not in active_keys:
            await _delete_render_message(bot, chat_id, message_id)
            await repo.delete_render_message_id(telegram_user_id, chat_id, stale_key)


async def _render_section(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
    section: RenderSection,
    message_id: int | None,
) -> None:
    if message_id is not None:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=section.text)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            logger.debug("Could not edit render message: %s", exc)
            await _delete_render_message(bot, chat_id, message_id)

    sent = await bot.send_message(chat_id=chat_id, text=section.text)
    await repo.set_render_message_id(telegram_user_id, chat_id, section.key, sent.message_id)


async def _delete_render_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete old render message: %s", exc)
