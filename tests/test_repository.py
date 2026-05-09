import tempfile
import unittest
from pathlib import Path

from app.db.database import Database
from app.db.repo.notes import NotesRepository


class NotesRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        await self.database.connect()
        await self.database.init_schema()
        self.repo = NotesRepository(self.database)
        self.user_id = 1001

    async def asyncTearDown(self) -> None:
        await self.database.close()
        self.temp_dir.cleanup()

    async def test_inbox_is_hidden_when_empty_and_visible_when_filled(self) -> None:
        await self.repo.ensure_user(self.user_id)
        self.assertEqual(await self.repo.get_snapshot(self.user_id), [])

        await self.repo.add_inbox_item(self.user_id, "Buy pants")
        snapshot = await self.repo.get_snapshot(self.user_id)

        self.assertEqual(len(snapshot), 1)
        self.assertTrue(snapshot[0].is_inbox)
        self.assertEqual(snapshot[0].items[0].text, "Buy pants")

    async def test_display_indexes_recalculate_after_chapter_delete(self) -> None:
        await self.repo.create_chapter(self.user_id, "One")
        await self.repo.create_chapter(self.user_id, "Two")
        await self.repo.create_chapter(self.user_id, "Three")

        await self.repo.delete_by_path(self.user_id, (2,))
        snapshot = await self.repo.get_snapshot(self.user_id)

        self.assertEqual([(chapter.display_index, chapter.title) for chapter in snapshot], [(1, "One"), (2, "Three")])

    async def test_users_do_not_see_each_other_data(self) -> None:
        await self.repo.create_chapter(self.user_id, "Mine")
        await self.repo.create_chapter(2002, "Other")

        my_snapshot = await self.repo.get_snapshot(self.user_id)
        other_snapshot = await self.repo.get_snapshot(2002)

        self.assertEqual([chapter.title for chapter in my_snapshot], ["Mine"])
        self.assertEqual([chapter.title for chapter in other_snapshot], ["Other"])

    async def test_done_item_moves_to_bottom(self) -> None:
        await self.repo.create_chapter(self.user_id, "Buy")
        await self.repo.add_item(self.user_id, (1,), "Milk")
        await self.repo.add_item(self.user_id, (1,), "Bread")
        await self.repo.add_item(self.user_id, (1,), "Eggs")

        await self.repo.mark_done(self.user_id, (1,), 1)
        items = (await self.repo.get_snapshot(self.user_id))[0].items

        self.assertEqual([(item.display_index, item.text, item.is_done) for item in items], [
            (1, "Bread", False),
            (2, "Eggs", False),
            (3, "Milk", True),
        ])

    async def test_undo_create_item_restores_empty_chapter(self) -> None:
        await self.repo.create_chapter(self.user_id, "Buy")
        await self.repo.add_item(self.user_id, (1,), "Milk")

        await self.repo.undo_last(self.user_id)
        snapshot = await self.repo.get_snapshot(self.user_id)

        self.assertEqual(snapshot[0].title, "Buy")
        self.assertEqual(snapshot[0].items, [])

    async def test_undo_delete_chapter_restores_by_stable_id(self) -> None:
        first_id = await self.repo.create_chapter(self.user_id, "One")
        second_id = await self.repo.create_chapter(self.user_id, "Two")
        await self.repo.add_item(self.user_id, (2,), "Milk")

        await self.repo.delete_by_path(self.user_id, (1,))
        await self.repo.undo_last(self.user_id)
        snapshot = await self.repo.get_snapshot(self.user_id)

        self.assertEqual([chapter.id for chapter in snapshot], [first_id, second_id])
        self.assertEqual(snapshot[1].items[0].text, "Milk")

    async def test_undo_rename_and_done(self) -> None:
        await self.repo.create_chapter(self.user_id, "Buy")
        await self.repo.add_item(self.user_id, (1,), "Milk")

        await self.repo.rename_chapter(self.user_id, (1,), "Shop")
        await self.repo.undo_last(self.user_id)
        self.assertEqual((await self.repo.get_snapshot(self.user_id))[0].title, "Buy")

        await self.repo.mark_done(self.user_id, (1,), 1)
        await self.repo.undo_last(self.user_id)
        item = (await self.repo.get_snapshot(self.user_id))[0].items[0]

        self.assertEqual(item.text, "Milk")
        self.assertFalse(item.is_done)


if __name__ == "__main__":
    unittest.main()
