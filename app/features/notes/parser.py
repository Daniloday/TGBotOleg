from __future__ import annotations

import re
from typing import Optional

from app.features.notes.actions import (
    ADD_INBOX_ITEM,
    ADD_ITEM,
    CREATE_CHAPTER,
    DELETE_PUSH,
    DELETE,
    MARK_DONE,
    MOVE_DOWN,
    MOVE_UP,
    RENAME,
    SHOW,
    SHOW_PUSHES,
    UNDO,
    NoteAction,
)

CREATE_RE = re.compile(r"^\+\s+(?:(\d+)\s+)?(.+)$")
ADD_RE = re.compile(r"^(\d+)(?:\s+(\d+))?\s+(.+)$")
DELETE_RE = re.compile(r"^[-•]\s+(.+)$")
DONE_RE = re.compile(r"^\d+(?:-\d+)?(?:\s+\d+(?:-\d+)?){0,2}$")
MOVE_RE = re.compile(r"^/(up|down)\s+(\d+(?:\s+\d+){0,2})\s*$")
RENAME_RE = re.compile(r"^/rename\s+(\d+(?:\s+\d+)?)\s+(.+)$")
PUSHDEL_RE = re.compile(r"^/pushdel\s+(\d+)\s*$")


def parse_user_text(raw_text: str) -> NoteAction:
    text = raw_text.strip()
    if not text:
        return NoteAction(kind=SHOW)

    if text in {"/start", "/help"}:
        return NoteAction(kind=SHOW)

    if text == "/undo":
        return NoteAction(kind=UNDO)

    if text == "/push":
        return NoteAction(kind=SHOW_PUSHES)

    match = PUSHDEL_RE.match(text)
    if match:
        return NoteAction(kind=DELETE_PUSH, item_index=int(match.group(1)))

    match = MOVE_RE.match(text)
    if match:
        kind = MOVE_UP if match.group(1) == "up" else MOVE_DOWN
        return NoteAction(kind=kind, path=_parse_path(match.group(2)))

    match = DELETE_RE.match(text)
    if match:
        parsed = _parse_item_address(match.group(1))
        if parsed is not None:
            path, item_indexes = parsed
            return NoteAction(kind=DELETE, path=path, item_indexes=item_indexes)

    match = RENAME_RE.match(text)
    if match:
        return NoteAction(kind=RENAME, path=_parse_path(match.group(1)), text=match.group(2).strip())

    multiline_add = _parse_multiline_add(text)
    if multiline_add is not None:
        path, item_text = multiline_add
        return NoteAction(kind=ADD_ITEM, path=path, text=item_text)

    if DONE_RE.match(text):
        parsed = _parse_item_address(text)
        if parsed is not None:
            path, item_indexes = parsed
            return NoteAction(kind=MARK_DONE, path=path, item_indexes=item_indexes)

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


def _parse_item_address(value: str) -> Optional[tuple[tuple[int, ...], tuple[int, ...]]]:
    parts = value.split()
    if not 1 <= len(parts) <= 3:
        return None

    try:
        if len(parts) == 1:
            return (), _parse_index_part(parts[0])

        if len(parts) == 2 and parts[0] == "0":
            return (), _parse_index_part(parts[1])

        if len(parts) == 2:
            return (int(parts[0]),), _parse_index_part(parts[1])

        return (int(parts[0]), int(parts[1])), _parse_index_part(parts[2])
    except ValueError:
        return None


def _parse_index_part(value: str) -> tuple[int, ...]:
    if "-" not in value:
        index = int(value)
        if index < 1:
            raise ValueError("Indexes are 1-based.")
        return (index,)

    start_raw, end_raw = value.split("-", 1)
    start = int(start_raw)
    end = int(end_raw)
    if start < 1 or end < start:
        raise ValueError("Invalid index range.")
    return tuple(range(start, end + 1))


def _parse_multiline_add(value: str) -> Optional[tuple[tuple[int, ...], str]]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    first_parts = lines[0].split(maxsplit=2)
    if not first_parts or not first_parts[0].isdigit():
        return None

    if len(first_parts) >= 2 and first_parts[1].isdigit():
        path = (int(first_parts[0]), int(first_parts[1]))
        first_item = first_parts[2].strip() if len(first_parts) == 3 else ""
    else:
        path = (int(first_parts[0]),)
        first_item = lines[0][len(first_parts[0]):].strip()

    item_lines = []
    if first_item:
        item_lines.append(first_item)
    item_lines.extend(lines[1:])
    if not item_lines:
        return None
    return path, "\n".join(item_lines)
