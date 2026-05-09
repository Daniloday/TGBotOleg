from __future__ import annotations

import re

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

DONE_RE = re.compile(r"^[-•]\s+\d+(?:\s+\d+){1,2}$")
CREATE_RE = re.compile(r"^\+\s+(?:(\d+)\s+)?(.+)$")
ADD_RE = re.compile(r"^(\d+)(?:\s+(\d+))?\s+(.+)$")
DELETE_RE = re.compile(r"^/del\s+(\d+(?:\s+\d+){0,2})\s*$")
RENAME_RE = re.compile(r"^/rename\s+(\d+(?:\s+\d+)?)\s+(.+)$")


def parse_user_text(raw_text: str) -> NoteAction:
    text = raw_text.strip()
    if not text:
        return NoteAction(kind=SHOW)

    if text in {"/start", "/help"}:
        return NoteAction(kind=SHOW)

    if text == "/undo":
        return NoteAction(kind=UNDO)

    match = DELETE_RE.match(text)
    if match:
        return NoteAction(kind=DELETE, path=_parse_path(match.group(1)))

    match = RENAME_RE.match(text)
    if match:
        return NoteAction(kind=RENAME, path=_parse_path(match.group(1)), text=match.group(2).strip())

    if DONE_RE.match(text):
        numbers = _parse_path(text[1:].strip())
        return NoteAction(kind=MARK_DONE, path=numbers[:-1], item_index=numbers[-1])

    match = CREATE_RE.match(text)
    if match:
        parent = match.group(1)
        parent_path = () if parent is None else (int(parent),)
        return NoteAction(kind=CREATE_CHAPTER, path=parent_path, text=match.group(2).strip())

    match = ADD_RE.match(text)
    if match:
        path = (int(match.group(1)),)
        if match.group(2) is not None:
            path = (path[0], int(match.group(2)))
        return NoteAction(kind=ADD_ITEM, path=path, text=match.group(3).strip())

    return NoteAction(kind=ADD_INBOX_ITEM, text=text)


def _parse_path(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split())

