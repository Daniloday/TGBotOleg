from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Iterable, List

from app.db.repo.models import ChapterView, ItemView


@dataclass(frozen=True)
class RenderSection:
    key: str
    text: str


def render_sections(chapters: Iterable[ChapterView]) -> List[RenderSection]:
    chapter_list = list(chapters)
    if not chapter_list:
        return [RenderSection(key="empty", text="No notes")]

    sections: List[RenderSection] = []
    for chapter in chapter_list:
        lines: List[str] = []
        _render_chapter(lines, chapter, indent="")
        section_key = "inbox" if chapter.is_inbox else f"chapter:{chapter.id}"
        sections.append(RenderSection(key=section_key, text="\n".join(lines).strip()))
    return sections


def render_notes(chapters: Iterable[ChapterView]) -> str:
    return "\n\n".join(section.text for section in render_sections(chapters))


def _render_chapter(lines: List[str], chapter: ChapterView, indent: str) -> None:
    title = escape(chapter.title)
    if chapter.is_inbox:
        lines.append(f"{indent}<b>{title}</b>")
    else:
        lines.append(f"{indent}<b>{title} ({chapter.display_index})</b>")

    for item in chapter.items:
        lines.append(_render_item(item, indent + "  "))

    for child in chapter.children:
        _render_chapter(lines, child, indent=indent + "  ")


def _render_item(item: ItemView, indent: str) -> str:
    text = escape(item.text)
    value = f"{item.display_index}. {text}"
    if item.is_done:
        value = f"<s>{value}</s>"
    return f"{indent}{value}"
