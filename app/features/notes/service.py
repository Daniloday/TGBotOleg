from __future__ import annotations

from app.db.repo.notes import NotesRepository
from app.features.notes.actions import (
    ADD_INBOX_ITEM,
    ADD_ITEM,
    CREATE_CHAPTER,
    DELETE_CHAPTER,
    DELETE_PUSH,
    DELETE,
    IGNORE,
    MARK_DONE,
    MOVE_DOWN,
    MOVE_UP,
    RENAME,
    SHOW,
    SHOW_PUSHES,
    UNDO,
    NoteAction,
)


async def apply_note_action(repo: NotesRepository, telegram_user_id: int, action: NoteAction) -> None:
    if action.kind == IGNORE:
        return

    if action.kind == SHOW:
        await repo.ensure_user(telegram_user_id)
        return

    if action.kind == UNDO:
        await repo.undo_last(telegram_user_id)
        return

    if action.kind == SHOW_PUSHES:
        await repo.ensure_user(telegram_user_id)
        return

    if action.kind == CREATE_CHAPTER and action.text:
        await repo.create_chapter(telegram_user_id, action.text, action.path or None)
        return

    if action.kind == ADD_ITEM and action.text:
        await repo.add_items(telegram_user_id, action.path, _split_item_lines(action.text))
        return

    if action.kind == ADD_INBOX_ITEM and action.text:
        await repo.add_inbox_items(telegram_user_id, _split_item_lines(action.text))
        return

    if action.kind == MARK_DONE and action.item_indexes:
        await repo.mark_done_many(telegram_user_id, action.path, action.item_indexes)
        return

    if action.kind == DELETE and action.item_indexes:
        await repo.delete_items(telegram_user_id, action.path, action.item_indexes)
        return

    if action.kind == DELETE_CHAPTER:
        await repo.delete_chapter_by_path(telegram_user_id, action.path)
        return

    if action.kind in {MOVE_UP, MOVE_DOWN}:
        await repo.move_path(telegram_user_id, action.path, to_top=action.kind == MOVE_UP)
        return

    if action.kind == RENAME and action.text:
        await repo.rename_chapter(telegram_user_id, action.path, action.text)
        return

    if action.kind == DELETE_PUSH and action.item_indexes:
        await repo.delete_active_reminders_by_indexes(telegram_user_id, action.item_indexes)
        return


def _split_item_lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())
