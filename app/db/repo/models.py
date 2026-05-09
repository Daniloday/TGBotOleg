from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ItemView:
    id: str
    display_index: int
    text: str
    is_done: bool


@dataclass(frozen=True)
class ChapterView:
    id: str
    display_index: Optional[int]
    title: str
    is_inbox: bool
    items: List[ItemView] = field(default_factory=list)
    children: List["ChapterView"] = field(default_factory=list)

