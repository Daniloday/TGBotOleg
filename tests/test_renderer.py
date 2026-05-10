import unittest

from app.db.repo.models import ChapterView, ItemView
from app.features.notes.renderer import render_sections


class RendererTest(unittest.TestCase):
    def test_empty_text_is_no_notes_without_title(self) -> None:
        self.assertEqual(render_sections([])[0].text, "No notes")

    def test_top_chapters_are_separate_sections(self) -> None:
        sections = render_sections(
            [
                ChapterView(id="c1", display_index=1, title="Buy", is_inbox=False),
                ChapterView(id="c2", display_index=2, title="Read", is_inbox=False),
            ]
        )

        self.assertEqual([section.key for section in sections], ["chapter:c1", "chapter:c2"])
        self.assertEqual([section.text for section in sections], ["<b>Buy (1)</b>", "<b>Read (2)</b>"])

    def test_subchapter_uses_local_numbering_with_indent(self) -> None:
        sections = render_sections(
            [
                ChapterView(
                    id="c1",
                    display_index=1,
                    title="Buy",
                    is_inbox=False,
                    children=[
                        ChapterView(
                            id="c2",
                            display_index=1,
                            title="Food",
                            is_inbox=False,
                            items=[ItemView(id="i1", display_index=1, text="Milk", is_done=False)],
                        )
                    ],
                )
            ]
        )

        self.assertEqual(sections[0].text, "<b>Buy (1)</b>\n  <b>Food (1)</b>\n    1. Milk")


if __name__ == "__main__":
    unittest.main()
