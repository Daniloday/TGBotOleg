from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


SHOW = "show"
CREATE_CHAPTER = "create_chapter"
ADD_ITEM = "add_item"
ADD_INBOX_ITEM = "add_inbox_item"
MARK_DONE = "mark_done"
DELETE = "delete"
DELETE_CHAPTER = "delete_chapter"
MOVE_UP = "move_up"
MOVE_DOWN = "move_down"
RENAME = "rename"
UNDO = "undo"
SHOW_PUSHES = "show_pushes"
DELETE_PUSH = "delete_push"
IGNORE = "ignore"


@dataclass(frozen=True)
class NoteAction:
    kind: str
    text: Optional[str] = None
    path: Tuple[int, ...] = ()
    item_index: Optional[int] = None
    item_indexes: Tuple[int, ...] = ()
