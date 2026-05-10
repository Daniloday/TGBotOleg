from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.repo.notes import NotesRepository
from app.features.notes.actions import ADD_INBOX_ITEM, DELETE_PUSH, SHOW_PUSHES
from app.features.notes.parser import parse_user_text
from app.features.notes.reminders import KYIV_TZ, parse_reminder_text
from app.features.notes.rendering import render_current_state
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

        if action.kind == SHOW_PUSHES:
            await repo.ensure_user(telegram_user_id)
            await _delete_user_message(message)
            await _send_active_pushes(message, repo, telegram_user_id)
            return

        if action.kind == DELETE_PUSH and action.item_indexes:
            await repo.delete_active_reminders_by_indexes(telegram_user_id, action.item_indexes)
            await _delete_user_message(message)
            await _send_active_pushes(message, repo, telegram_user_id)
            return

        if action.kind == ADD_INBOX_ITEM and action.text:
            parsed_reminder = parse_reminder_text(action.text, datetime.now(KYIV_TZ))
            if parsed_reminder is not None:
                await repo.create_reminder(
                    telegram_user_id,
                    message.chat.id,
                    parsed_reminder.text,
                    parsed_reminder.remind_at,
                )
                await _delete_user_message(message)
                return

        await apply_note_action(repo, telegram_user_id, action)
        await _delete_user_message(message)
        await render_current_state(bot, repo, telegram_user_id, message.chat.id)

    @router.callback_query(F.data == "push:close")
    async def close_pushes(callback: CallbackQuery) -> None:
        await _delete_callback_message(callback)
        await callback.answer()

    @router.callback_query(F.data.startswith("push:delete:"))
    async def delete_push_message(callback: CallbackQuery) -> None:
        reminder_id = callback.data.rsplit(":", 1)[-1] if callback.data else ""
        if reminder_id:
            await repo.delete_reminder(reminder_id)
        await _delete_callback_message(callback)
        await callback.answer()

    return router


async def _delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete user message: %s", exc)


async def _send_active_pushes(
    message: Message,
    repo: NotesRepository,
    telegram_user_id: int,
) -> None:
    reminders = await repo.get_active_reminders(telegram_user_id)
    if reminders:
        lines = ["<b>Активные пуши</b>"]
        for index, reminder in enumerate(reminders, start=1):
            when = reminder.remind_at.astimezone(KYIV_TZ).strftime("%d.%m %H:%M")
            lines.append(f"{index}. {when} - {reminder.text}")
        text = "\n".join(lines)
    else:
        text = "Активных пушей нет"

    await message.answer(text, reply_markup=close_keyboard())


async def _delete_callback_message(callback: CallbackQuery) -> None:
    if callback.message is None or not hasattr(callback.message, "delete"):
        return
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.debug("Could not delete callback message: %s", exc)


def delete_push_keyboard(reminder_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data=f"push:delete:{reminder_id}")]
        ]
    )


def close_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Закрыть", callback_data="push:close")]
        ]
    )
