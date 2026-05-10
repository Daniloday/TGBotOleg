from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.db.repo.notes import NotesRepository
from app.features.notes.rendering import render_current_state
from app.features.notes.router import delete_push_keyboard

logger = logging.getLogger(__name__)


async def run_notifications_worker(
    bot: Bot,
    repo: NotesRepository,
    interval_seconds: int = 180,
) -> None:
    while True:
        await _send_due_reminders(bot, repo)
        await asyncio.sleep(interval_seconds)


async def _send_due_reminders(bot: Bot, repo: NotesRepository) -> None:
    reminders = await repo.get_due_reminders(datetime.now(timezone.utc))
    for reminder in reminders:
        try:
            sent = await bot.send_message(
                chat_id=reminder.chat_id,
                text=reminder.text,
                reply_markup=delete_push_keyboard(reminder.id),
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.debug("Could not send reminder %s: %s", reminder.id, exc)
            continue

        await repo.mark_reminder_sent(reminder.id, sent.message_id)
        await repo.add_inbox_item(reminder.telegram_user_id, reminder.text)
        await render_current_state(bot, repo, reminder.telegram_user_id, reminder.chat_id)
