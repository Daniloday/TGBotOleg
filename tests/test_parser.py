import unittest

from app.features.notes.actions import (
    ADD_INBOX_ITEM,
    ADD_ITEM,
    CREATE_CHAPTER,
    DELETE,
    MARK_DONE,
    RENAME,
    UNDO,
)
from app.features.notes.parser import parse_user_text


class ParserTest(unittest.TestCase):
    def test_minus_without_space_is_plain_inbox_note(self) -> None:
        action = parse_user_text("-2 kg за неделю")

        self.assertEqual(action.kind, ADD_INBOX_ITEM)
        self.assertEqual(action.text, "-2 kg за неделю")

    def test_dash_done_action(self) -> None:
        action = parse_user_text("- 7 2")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_index, 2)

    def test_dash_done_inbox_action(self) -> None:
        action = parse_user_text("- 2")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_index, 2)

    def test_bullet_done_action(self) -> None:
        action = parse_user_text("• 7 2")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_index, 2)

    def test_del_action(self) -> None:
        action = parse_user_text("/del 7 2")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, (7, 2))

    def test_del_inbox_action(self) -> None:
        action = parse_user_text("/del 0 1")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, (0, 1))

    def test_create_top_chapter(self) -> None:
        action = parse_user_text("+ Buy")

        self.assertEqual(action.kind, CREATE_CHAPTER)
        self.assertEqual(action.path, ())
        self.assertEqual(action.text, "Buy")

    def test_create_subchapter(self) -> None:
        action = parse_user_text("+ 3 Pharmacy")

        self.assertEqual(action.kind, CREATE_CHAPTER)
        self.assertEqual(action.path, (3,))
        self.assertEqual(action.text, "Pharmacy")

    def test_add_item_to_chapter(self) -> None:
        action = parse_user_text("7 Milk")

        self.assertEqual(action.kind, ADD_ITEM)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.text, "Milk")

    def test_add_item_to_subchapter(self) -> None:
        action = parse_user_text("3 1 Pills")

        self.assertEqual(action.kind, ADD_ITEM)
        self.assertEqual(action.path, (3, 1))
        self.assertEqual(action.text, "Pills")

    def test_rename_subchapter(self) -> None:
        action = parse_user_text("/rename 3 1 NewApteka")

        self.assertEqual(action.kind, RENAME)
        self.assertEqual(action.path, (3, 1))
        self.assertEqual(action.text, "NewApteka")

    def test_undo(self) -> None:
        action = parse_user_text("/undo")

        self.assertEqual(action.kind, UNDO)


if __name__ == "__main__":
    unittest.main()
