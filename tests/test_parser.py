import unittest

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
    SHOW_PUSHES,
    UNDO,
)
from app.features.notes.parser import parse_user_text


class ParserTest(unittest.TestCase):
    def test_minus_without_space_is_plain_inbox_note(self) -> None:
        action = parse_user_text("-2 kg per week")

        self.assertEqual(action.kind, ADD_INBOX_ITEM)
        self.assertEqual(action.text, "-2 kg per week")

    def test_multiline_without_path_is_plain_inbox_note(self) -> None:
        action = parse_user_text("Books\nNotebooks")

        self.assertEqual(action.kind, ADD_INBOX_ITEM)
        self.assertEqual(action.text, "Books\nNotebooks")

    def test_plain_number_marks_inbox_item_done(self) -> None:
        action = parse_user_text("6")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (6,))

    def test_zero_number_marks_inbox_item_done(self) -> None:
        action = parse_user_text("0 6")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (6,))

    def test_plain_range_marks_inbox_items_done(self) -> None:
        action = parse_user_text("2-6")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (2, 3, 4, 5, 6))

    def test_chapter_item_done_action(self) -> None:
        action = parse_user_text("7 2")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_indexes, (2,))

    def test_chapter_item_range_done_action(self) -> None:
        action = parse_user_text("7 2-4")

        self.assertEqual(action.kind, MARK_DONE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_indexes, (2, 3, 4))

    def test_dash_delete_action(self) -> None:
        action = parse_user_text("- 7 2")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_indexes, (2,))

    def test_bullet_delete_action(self) -> None:
        action = parse_user_text("• 7 2-3")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, (7,))
        self.assertEqual(action.item_indexes, (2, 3))

    def test_dash_delete_action_without_space(self) -> None:
        action = parse_user_text("-5")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (5,))

    def test_bullet_delete_action_without_space(self) -> None:
        action = parse_user_text("•5")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (5,))

    def test_delete_inbox_action(self) -> None:
        action = parse_user_text("- 0 1")

        self.assertEqual(action.kind, DELETE)
        self.assertEqual(action.path, ())
        self.assertEqual(action.item_indexes, (1,))

    def test_del_is_no_longer_command(self) -> None:
        action = parse_user_text("/del 7 2")

        self.assertEqual(action.kind, IGNORE)

    def test_unknown_command_is_ignored(self) -> None:
        action = parse_user_text("/unknown")

        self.assertEqual(action.kind, IGNORE)

    def test_remove_chapter_command(self) -> None:
        action = parse_user_text("/rm 7")

        self.assertEqual(action.kind, DELETE_CHAPTER)
        self.assertEqual(action.path, (7,))

    def test_remove_subchapter_command(self) -> None:
        action = parse_user_text("/rm 7 2")

        self.assertEqual(action.kind, DELETE_CHAPTER)
        self.assertEqual(action.path, (7, 2))

    def test_move_up_and_down(self) -> None:
        up = parse_user_text("/up 7 2")
        down = parse_user_text("/down 7 2 3")

        self.assertEqual(up.kind, MOVE_UP)
        self.assertEqual(up.path, (7, 2))
        self.assertEqual(down.kind, MOVE_DOWN)
        self.assertEqual(down.path, (7, 2, 3))

    def test_show_pushes(self) -> None:
        action = parse_user_text("/push")

        self.assertEqual(action.kind, SHOW_PUSHES)

    def test_delete_push_by_display_index(self) -> None:
        action = parse_user_text("/pushdel 5")

        self.assertEqual(action.kind, DELETE_PUSH)
        self.assertEqual(action.item_indexes, (5,))

    def test_delete_push_range_by_display_indexes(self) -> None:
        action = parse_user_text("/pushdel 3-6")

        self.assertEqual(action.kind, DELETE_PUSH)
        self.assertEqual(action.item_indexes, (3, 4, 5, 6))

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

    def test_multiline_add_item_with_first_item_on_header_line(self) -> None:
        action = parse_user_text("3 Books\nNotebooks")

        self.assertEqual(action.kind, ADD_ITEM)
        self.assertEqual(action.path, (3,))
        self.assertEqual(action.text, "Books\nNotebooks")

    def test_multiline_add_item_with_path_on_own_line(self) -> None:
        action = parse_user_text("3\nBooks\nNotebooks")

        self.assertEqual(action.kind, ADD_ITEM)
        self.assertEqual(action.path, (3,))
        self.assertEqual(action.text, "Books\nNotebooks")

    def test_multiline_add_item_to_subchapter(self) -> None:
        action = parse_user_text("3 1\nBooks\nNotebooks")

        self.assertEqual(action.kind, ADD_ITEM)
        self.assertEqual(action.path, (3, 1))
        self.assertEqual(action.text, "Books\nNotebooks")

    def test_rename_subchapter(self) -> None:
        action = parse_user_text("/rename 3 1 NewBuy")

        self.assertEqual(action.kind, RENAME)
        self.assertEqual(action.path, (3, 1))
        self.assertEqual(action.text, "NewBuy")

    def test_undo(self) -> None:
        action = parse_user_text("/undo")

        self.assertEqual(action.kind, UNDO)


if __name__ == "__main__":
    unittest.main()
