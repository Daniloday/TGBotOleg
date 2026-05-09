from __future__ import annotations

from html import escape
from typing import Iterable, List

from app.db.repo.models import ChapterView, ItemView


def render_notes(chapters: Iterable[ChapterView]) -> str:
    chapter_list = list(chapters)
    if not chapter_list:
        return "<b>Notes</b>\n\nNo notes yet."

    lines: List[str] = ["<b>Notes</b>", ""]
    for chapter in chapter_list:
        _render_chapter(lines, chapter, prefix="", indent="")
        lines.append("")
    return "\n".join(lines).strip()


def _render_chapter(lines: List[str], chapter: ChapterView, prefix: str, indent: str) -> None:
    title = escape(chapter.title)
    if chapter.is_inbox:
        lines.append(f"{indent}<b>{title}</b>")
    else:
        current_prefix = str(chapter.display_index) if not prefix else f"{prefix}.{chapter.display_index}"
        lines.append(f"{indent}<b>{current_prefix}. {title}</b>")
        prefix = current_prefix

    for item in chapter.items:
        lines.append(_render_item(item, indent + "  "))

    for child in chapter.children:
        _render_chapter(lines, child, prefix=prefix, indent=indent + "  ")


def _render_item(item: ItemView, indent: str) -> str:
    text = escape(item.text)
    value = f"{item.display_index}. {text}"
    if item.is_done:
        value = f"<s>{value}</s>"
    return f"{indent}{value}"

