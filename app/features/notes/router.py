from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from app.db.repo.notes import NotesRepository
from app.features.notes.parser import parse_user_text
from app.features.notes.renderer import render_notes
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
    text = render_notes(await repo.get_snapshot(telegram_user_id))
    message_id = await repo.get_render_message_id(telegram_user_id, chat_id)

    if message_id is not None:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            logger.debug("Could not edit render message: %s", exc)
            await _delete_render_message(bot, chat_id, message_id)

    sent = await bot.send_message(chat_id=chat_id, text=text)
    await repo.set_render_message_id(telegram_user_id, chat_id, sent.message_id)


async def _delete_render_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete old render message: %s", exc)

