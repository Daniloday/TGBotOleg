from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.db.repo.notes import NotesRepository
from app.features.notes.renderer import RenderSection, render_sections

logger = logging.getLogger(__name__)
_RENDER_LOCKS: dict[tuple[int, int], asyncio.Lock] = {}


async def render_current_state(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
) -> None:
    lock = _get_render_lock(telegram_user_id, chat_id)
    async with lock:
        await _render_current_state_unlocked(bot, repo, telegram_user_id, chat_id)


async def _render_current_state_unlocked(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
) -> None:
    sections = render_sections(await repo.get_snapshot(telegram_user_id))
    old_messages = await repo.get_render_messages(telegram_user_id, chat_id)

    if _can_edit_in_place(sections, old_messages):
        await _edit_or_send_sections(bot, repo, telegram_user_id, chat_id, sections, old_messages)
        await _delete_stale_sections(bot, repo, telegram_user_id, chat_id, sections, old_messages)
        return

    for section_key, message_id in old_messages.items():
        await _delete_render_message(bot, chat_id, message_id)
        await repo.delete_render_message_id(telegram_user_id, chat_id, section_key)

    for section in sections:
        await _send_section(bot, repo, telegram_user_id, chat_id, section)


def _get_render_lock(telegram_user_id: int, chat_id: int) -> asyncio.Lock:
    key = (telegram_user_id, chat_id)
    lock = _RENDER_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _RENDER_LOCKS[key] = lock
    return lock


def _can_edit_in_place(sections: list[RenderSection], old_messages: dict[str, int]) -> bool:
    seen_missing = False
    existing_message_ids = []

    for section in sections:
        message_id = old_messages.get(section.key)
        if message_id is None:
            seen_missing = True
            continue
        if seen_missing:
            return False
        existing_message_ids.append(message_id)

    return existing_message_ids == sorted(existing_message_ids)


async def _edit_or_send_sections(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
    sections: list[RenderSection],
    old_messages: dict[str, int],
) -> None:
    for section in sections:
        message_id = old_messages.get(section.key)
        if message_id is None:
            await _send_section(bot, repo, telegram_user_id, chat_id, section)
            continue
        if not await _edit_section(bot, chat_id, message_id, section):
            await _delete_render_message(bot, chat_id, message_id)
            await _send_section(bot, repo, telegram_user_id, chat_id, section)


async def _delete_stale_sections(
    bot: Bot,
    repo: NotesRepository,
    telegram_user_id: int,
    chat_id: int,
    sections: list[RenderSection],
    old_messages: dict[str, int],
) -> None:
    active_keys = {section.key for section in sections}
    for section_key, message_id in old_messages.items():
        if section_key not in active_keys:
            await _delete_render_message(bot, chat_id, message_id)
            await repo.delete_render_message_id(telegram_user_id, chat_id, section_key)


async def _edit_section(bot: Bot, chat_id: int, message_id: int, section: RenderSection) -> bool:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=section.text)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.debug("Could not edit render message: %s", exc)
        return False


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
