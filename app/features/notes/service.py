from __future__ import annotations

from app.db.repo.notes import NotesRepository
from app.features.notes.actions import (
    ADD_INBOX_ITEM,
    ADD_ITEM,
    CREATE_CHAPTER,
    DELETE,
    MARK_DONE,
    RENAME,
    SHOW,
    UNDO,
    NoteAction,
)


async def apply_note_action(repo: NotesRepository, telegram_user_id: int, action: NoteAction) -> None:
    if action.kind == SHOW:
        await repo.ensure_user(telegram_user_id)
        return

    if action.kind == UNDO:
        await repo.undo_last(telegram_user_id)
        return

    if action.kind == CREATE_CHAPTER and action.text:
        await repo.create_chapter(telegram_user_id, action.text, action.path or None)
        return

    if action.kind == ADD_ITEM and action.text:
        await repo.add_item(telegram_user_id, action.path, action.text)
        return

    if action.kind == ADD_INBOX_ITEM and action.text:
        await repo.add_inbox_item(telegram_user_id, action.text)
        return

    if action.kind == MARK_DONE and action.item_index is not None:
        await repo.mark_done(telegram_user_id, action.path, action.item_index)
        return

    if action.kind == DELETE:
        await repo.delete_by_path(telegram_user_id, action.path)
        return

    if action.kind == RENAME and action.text:
        await repo.rename_chapter(telegram_user_id, action.path, action.text)

