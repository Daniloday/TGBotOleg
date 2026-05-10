from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiosqlite

from app.db.database import Database
from app.db.repo.models import ChapterView, ItemView, ReminderView


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _format_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class NotesRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def ensure_user(self, telegram_user_id: int) -> None:
        conn = self.database.require_connection()
        await self._ensure_user(conn, telegram_user_id)
        await conn.commit()

    async def get_snapshot(self, telegram_user_id: int) -> List[ChapterView]:
        conn = self.database.require_connection()
        await self._ensure_user(conn, telegram_user_id)
        await conn.commit()

        result: List[ChapterView] = []
        top_chapters = await self._get_top_chapters(conn, telegram_user_id)
        for index, chapter in enumerate(top_chapters, start=1):
            result.append(await self._build_chapter_view(conn, telegram_user_id, chapter, index))

        inbox = await self._get_inbox(conn, telegram_user_id)
        if inbox is not None:
            inbox_items = await self._get_item_views(conn, inbox["id"])
            if inbox_items:
                result.append(
                    ChapterView(
                        id=inbox["id"],
                        display_index=None,
                        title=inbox["title"],
                        is_inbox=True,
                        items=inbox_items,
                    )
                )
        return result

    async def create_chapter(
        self,
        telegram_user_id: int,
        title: str,
        parent_path: Optional[Sequence[int]] = None,
    ) -> Optional[str]:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            parent_id = None
            if parent_path:
                parent = await self._resolve_chapter_path(conn, telegram_user_id, parent_path)
                if parent is None:
                    await conn.rollback()
                    return None
                parent_id = parent["id"]

            chapter_id = _new_id("c")
            position = await self._next_chapter_position(conn, telegram_user_id, parent_id)
            await conn.execute(
                """
                INSERT INTO chapters (id, telegram_user_id, parent_id, title, position, is_inbox)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (chapter_id, telegram_user_id, parent_id, title.strip(), position),
            )
            moved_items: List[Dict[str, Any]] = []
            if parent_id is not None:
                moved_items = await self._move_direct_items_to_child(conn, parent_id, chapter_id)
            await self._record_history(
                conn,
                telegram_user_id,
                "create_chapter",
                {"chapter_id": chapter_id, "moved_items": moved_items},
            )
            await conn.commit()
            return chapter_id
        except Exception:
            await conn.rollback()
            raise

    async def add_item(self, telegram_user_id: int, chapter_path: Sequence[int], text: str) -> Optional[str]:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, chapter_path)
            if chapter is None:
                await conn.rollback()
                return None
            if await self._has_children(conn, telegram_user_id, chapter["id"]):
                await conn.rollback()
                return None
            item_id = await self._insert_item(conn, chapter["id"], text.strip())
            await self._record_history(conn, telegram_user_id, "create_item", {"item_id": item_id})
            await conn.commit()
            return item_id
        except Exception:
            await conn.rollback()
            raise

    async def add_inbox_item(self, telegram_user_id: int, text: str) -> Optional[str]:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            inbox = await self._get_inbox(conn, telegram_user_id)
            if inbox is None:
                await conn.rollback()
                return None
            item_id = await self._insert_item(conn, inbox["id"], text.strip())
            await self._record_history(conn, telegram_user_id, "create_item", {"item_id": item_id})
            await conn.commit()
            return item_id
        except Exception:
            await conn.rollback()
            raise

    async def mark_done(
        self,
        telegram_user_id: int,
        chapter_path: Sequence[int],
        item_index: int,
    ) -> bool:
        return await self.mark_done_many(telegram_user_id, chapter_path, (item_index,))

    async def mark_done_many(
        self,
        telegram_user_id: int,
        chapter_path: Sequence[int],
        item_indexes: Sequence[int],
    ) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            chapter = await self._resolve_item_chapter_path(conn, telegram_user_id, chapter_path)
            if chapter is None:
                await conn.rollback()
                return False

            items = await self._resolve_item_indexes(conn, chapter["id"], item_indexes)
            items = [item for item in items if not bool(item["is_done"])]
            if not items:
                await conn.rollback()
                return False

            payload = []
            for item in items:
                payload.append(
                    {
                        "item_id": item["id"],
                        "chapter_id": item["chapter_id"],
                        "old_position": item["position"],
                        "old_is_done": item["is_done"],
                    }
                )
                await self._mark_item_done_by_id(conn, item["id"])

            action_type = "done_item" if len(payload) == 1 else "bulk_done_items"
            history_payload = payload[0] if len(payload) == 1 else {"items": payload}
            await self._record_history(conn, telegram_user_id, action_type, history_payload)
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def delete_items(
        self,
        telegram_user_id: int,
        chapter_path: Sequence[int],
        item_indexes: Sequence[int],
    ) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            chapter = await self._resolve_item_chapter_path(conn, telegram_user_id, chapter_path)
            if chapter is None:
                await conn.rollback()
                return False

            items = await self._resolve_item_indexes(conn, chapter["id"], item_indexes)
            if not items:
                await conn.rollback()
                return False

            payload = [self._row_to_dict(item) for item in items]
            for item in items:
                current = await self._fetchone(conn, "SELECT * FROM items WHERE id = ?", (item["id"],))
                if current is None:
                    continue
                await conn.execute("DELETE FROM items WHERE id = ?", (current["id"],))
                await self._remove_item_position(conn, current["chapter_id"], current["is_done"], current["position"])

            action_type = "delete_item" if len(payload) == 1 else "bulk_delete_items"
            history_payload = {"item": payload[0]} if len(payload) == 1 else {"items": payload}
            await self._record_history(conn, telegram_user_id, action_type, history_payload)
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def delete_by_path(self, telegram_user_id: int, path: Sequence[int]) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            target = await self._resolve_delete_target(conn, telegram_user_id, path)
            if target is None:
                await conn.rollback()
                return False

            target_type, row = target
            if target_type == "chapter":
                payload = {"chapter": await self._serialize_chapter_tree(conn, row["id"])}
                await conn.execute("DELETE FROM chapters WHERE id = ?", (row["id"],))
                await self._remove_chapter_position(
                    conn,
                    telegram_user_id,
                    row["parent_id"],
                    row["position"],
                )
                await self._record_history(conn, telegram_user_id, "delete_chapter", payload)
            else:
                payload = {"item": self._row_to_dict(row)}
                await conn.execute("DELETE FROM items WHERE id = ?", (row["id"],))
                await self._remove_item_position(conn, row["chapter_id"], row["is_done"], row["position"])
                await self._record_history(conn, telegram_user_id, "delete_item", payload)
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def rename_chapter(self, telegram_user_id: int, path: Sequence[int], title: str) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, path)
            if chapter is None:
                await conn.rollback()
                return False
            new_title = title.strip()
            if not new_title or new_title == chapter["title"]:
                await conn.rollback()
                return False
            await conn.execute(
                "UPDATE chapters SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_title, chapter["id"]),
            )
            await self._record_history(
                conn,
                telegram_user_id,
                "rename_chapter",
                {
                    "chapter_id": chapter["id"],
                    "old_title": chapter["title"],
                    "new_title": new_title,
                },
            )
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def move_path(self, telegram_user_id: int, path: Sequence[int], to_top: bool) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            target = await self._resolve_move_target(conn, telegram_user_id, path)
            if target is None:
                await conn.rollback()
                return False

            target_type, row = target
            if target_type == "chapter":
                max_position = await self._max_chapter_position(conn, telegram_user_id, row["parent_id"])
                new_position = 1 if to_top else max_position
                if row["position"] == new_position:
                    await conn.rollback()
                    return False
                payload = {
                    "chapter_id": row["id"],
                    "telegram_user_id": telegram_user_id,
                    "parent_id": row["parent_id"],
                    "old_position": row["position"],
                    "new_position": new_position,
                }
                await self._move_chapter_to_position(conn, row, new_position)
                await self._record_history(conn, telegram_user_id, "move_chapter", payload)
            else:
                max_position = await self._max_item_position(conn, row["chapter_id"], row["is_done"])
                new_position = 1 if to_top else max_position
                if row["position"] == new_position:
                    await conn.rollback()
                    return False
                payload = {
                    "item_id": row["id"],
                    "chapter_id": row["chapter_id"],
                    "is_done": row["is_done"],
                    "old_position": row["position"],
                    "new_position": new_position,
                }
                await self._move_item_to_position(conn, row, new_position)
                await self._record_history(conn, telegram_user_id, "move_item", payload)
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def create_reminder(
        self,
        telegram_user_id: int,
        chat_id: int,
        text: str,
        remind_at: datetime,
    ) -> str:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            reminder_id = _new_id("p")
            await conn.execute(
                """
                INSERT INTO reminders (id, telegram_user_id, chat_id, text, remind_at, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (reminder_id, telegram_user_id, chat_id, text.strip(), _format_dt(remind_at)),
            )
            await conn.commit()
            return reminder_id
        except Exception:
            await conn.rollback()
            raise

    async def get_active_reminders(self, telegram_user_id: int) -> List[ReminderView]:
        conn = self.database.require_connection()
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM reminders
            WHERE telegram_user_id = ? AND status = 'active'
            ORDER BY remind_at ASC, created_at ASC
            """,
            (telegram_user_id,),
        )
        return [self._row_to_reminder(row) for row in rows]

    async def get_due_reminders(self, now: datetime) -> List[ReminderView]:
        conn = self.database.require_connection()
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM reminders
            WHERE status = 'active' AND remind_at <= ?
            ORDER BY remind_at ASC, created_at ASC
            """,
            (_format_dt(now),),
        )
        return [self._row_to_reminder(row) for row in rows]

    async def mark_reminder_sent(self, reminder_id: str, message_id: int) -> None:
        conn = self.database.require_connection()
        await conn.execute(
            """
            UPDATE reminders
            SET status = 'sent', sent_message_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (message_id, reminder_id),
        )
        await conn.commit()

    async def delete_reminder(self, reminder_id: str) -> None:
        conn = self.database.require_connection()
        await conn.execute(
            """
            UPDATE reminders
            SET status = 'deleted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reminder_id,),
        )
        await conn.commit()

    async def undo_last(self, telegram_user_id: int) -> bool:
        conn = self.database.require_connection()
        try:
            await self._ensure_user(conn, telegram_user_id)
            history = await self._fetchone(
                conn,
                """
                SELECT id, action_type, payload
                FROM operation_history
                WHERE telegram_user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (telegram_user_id,),
            )
            if history is None:
                await conn.rollback()
                return False

            payload = json.loads(history["payload"])
            await self._apply_undo(conn, history["action_type"], payload)
            await conn.execute("DELETE FROM operation_history WHERE id = ?", (history["id"],))
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

    async def get_render_messages(self, telegram_user_id: int, chat_id: int) -> Dict[str, int]:
        conn = self.database.require_connection()
        rows = await self._fetchall(
            conn,
            """
            SELECT section_key, message_id
            FROM render_state
            WHERE telegram_user_id = ? AND chat_id = ?
            """,
            (telegram_user_id, chat_id),
        )
        return {row["section_key"]: int(row["message_id"]) for row in rows}

    async def set_render_message_id(
        self,
        telegram_user_id: int,
        chat_id: int,
        section_key: str,
        message_id: int,
    ) -> None:
        conn = self.database.require_connection()
        await self._ensure_user(conn, telegram_user_id)
        await conn.execute(
            """
            INSERT INTO render_state (telegram_user_id, chat_id, section_key, message_id, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id, chat_id, section_key)
            DO UPDATE SET message_id = excluded.message_id, updated_at = CURRENT_TIMESTAMP
            """,
            (telegram_user_id, chat_id, section_key, message_id),
        )
        await conn.commit()

    async def delete_render_message_id(self, telegram_user_id: int, chat_id: int, section_key: str) -> None:
        conn = self.database.require_connection()
        await conn.execute(
            """
            DELETE FROM render_state
            WHERE telegram_user_id = ? AND chat_id = ? AND section_key = ?
            """,
            (telegram_user_id, chat_id, section_key),
        )
        await conn.commit()

    async def _ensure_user(self, conn: aiosqlite.Connection, telegram_user_id: int) -> None:
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_user_id) VALUES (?)",
            (telegram_user_id,),
        )
        inbox = await self._get_inbox(conn, telegram_user_id)
        if inbox is None:
            await conn.execute(
                """
                INSERT INTO chapters (id, telegram_user_id, parent_id, title, position, is_inbox)
                VALUES (?, ?, NULL, 'Inbox', 0, 1)
                """,
                (_new_id("c"), telegram_user_id),
            )

    async def _insert_item(self, conn: aiosqlite.Connection, chapter_id: str, text: str) -> str:
        item_id = _new_id("i")
        position = await self._next_item_position(conn, chapter_id, False)
        await conn.execute(
            """
            INSERT INTO items (id, chapter_id, text, position, is_done)
            VALUES (?, ?, ?, ?, 0)
            """,
            (item_id, chapter_id, text, position),
        )
        return item_id

    async def _move_direct_items_to_child(
        self,
        conn: aiosqlite.Connection,
        parent_id: str,
        child_id: str,
    ) -> List[Dict[str, Any]]:
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM items
            WHERE chapter_id = ?
            ORDER BY is_done ASC, position ASC, created_at ASC
            """,
            (parent_id,),
        )
        moved_items = [self._row_to_dict(row) for row in rows]
        active_position = 1
        done_position = 1
        for row in rows:
            if bool(row["is_done"]):
                position = done_position
                done_position += 1
            else:
                position = active_position
                active_position += 1
            await conn.execute(
                """
                UPDATE items
                SET chapter_id = ?, position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (child_id, position, row["id"]),
            )
        return moved_items

    async def _build_chapter_view(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        chapter: aiosqlite.Row,
        display_index: int,
    ) -> ChapterView:
        children_rows = await self._get_children(conn, telegram_user_id, chapter["id"])
        children = [
            await self._build_chapter_view(conn, telegram_user_id, child, index)
            for index, child in enumerate(children_rows, start=1)
        ]
        return ChapterView(
            id=chapter["id"],
            display_index=display_index,
            title=chapter["title"],
            is_inbox=bool(chapter["is_inbox"]),
            items=await self._get_item_views(conn, chapter["id"]),
            children=children,
        )

    async def _get_inbox(self, conn: aiosqlite.Connection, telegram_user_id: int) -> Optional[aiosqlite.Row]:
        return await self._fetchone(
            conn,
            """
            SELECT *
            FROM chapters
            WHERE telegram_user_id = ? AND is_inbox = 1
            LIMIT 1
            """,
            (telegram_user_id,),
        )

    async def _get_top_chapters(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
    ) -> List[aiosqlite.Row]:
        return await self._fetchall(
            conn,
            """
            SELECT *
            FROM chapters
            WHERE telegram_user_id = ? AND parent_id IS NULL AND is_inbox = 0
            ORDER BY position ASC, created_at ASC
            """,
            (telegram_user_id,),
        )

    async def _get_children(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        parent_id: str,
    ) -> List[aiosqlite.Row]:
        return await self._fetchall(
            conn,
            """
            SELECT *
            FROM chapters
            WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0
            ORDER BY position ASC, created_at ASC
            """,
            (telegram_user_id, parent_id),
        )

    async def _get_item_views(self, conn: aiosqlite.Connection, chapter_id: str) -> List[ItemView]:
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM items
            WHERE chapter_id = ?
            ORDER BY is_done ASC, position ASC, created_at ASC
            """,
            (chapter_id,),
        )
        return [
            ItemView(
                id=row["id"],
                display_index=index,
                text=row["text"],
                is_done=bool(row["is_done"]),
            )
            for index, row in enumerate(rows, start=1)
        ]

    async def _resolve_chapter_path(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        path: Sequence[int],
    ) -> Optional[aiosqlite.Row]:
        if not path or len(path) > 2:
            return None

        current_rows = await self._get_top_chapters(conn, telegram_user_id)
        current = self._by_display_index(current_rows, path[0])
        if current is None or len(path) == 1:
            return current

        child_rows = await self._get_children(conn, telegram_user_id, current["id"])
        return self._by_display_index(child_rows, path[1])

    async def _resolve_item_chapter_path(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        path: Sequence[int],
    ) -> Optional[aiosqlite.Row]:
        if len(path) == 0:
            return await self._get_inbox(conn, telegram_user_id)
        return await self._resolve_chapter_path(conn, telegram_user_id, path)

    async def _has_children(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        chapter_id: str,
    ) -> bool:
        row = await self._fetchone(
            conn,
            """
            SELECT 1
            FROM chapters
            WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0
            LIMIT 1
            """,
            (telegram_user_id, chapter_id),
        )
        return row is not None

    async def _resolve_item_index(
        self,
        conn: aiosqlite.Connection,
        chapter_id: str,
        display_index: int,
    ) -> Optional[aiosqlite.Row]:
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM items
            WHERE chapter_id = ?
            ORDER BY is_done ASC, position ASC, created_at ASC
            """,
            (chapter_id,),
        )
        return self._by_display_index(rows, display_index)

    async def _resolve_item_indexes(
        self,
        conn: aiosqlite.Connection,
        chapter_id: str,
        display_indexes: Sequence[int],
    ) -> List[aiosqlite.Row]:
        rows = await self._fetchall(
            conn,
            """
            SELECT *
            FROM items
            WHERE chapter_id = ?
            ORDER BY is_done ASC, position ASC, created_at ASC
            """,
            (chapter_id,),
        )
        result: List[aiosqlite.Row] = []
        seen: set[str] = set()
        for display_index in display_indexes:
            row = self._by_display_index(rows, display_index)
            if row is not None and row["id"] not in seen:
                result.append(row)
                seen.add(row["id"])
        return result

    async def _mark_item_done_by_id(self, conn: aiosqlite.Connection, item_id: str) -> None:
        item = await self._fetchone(conn, "SELECT * FROM items WHERE id = ?", (item_id,))
        if item is None or bool(item["is_done"]):
            return
        await self._remove_item_position(conn, item["chapter_id"], item["is_done"], item["position"])
        new_position = await self._next_item_position(conn, item["chapter_id"], True)
        await conn.execute(
            """
            UPDATE items
            SET is_done = 1, position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_position, item_id),
        )

    async def _resolve_delete_target(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        path: Sequence[int],
    ) -> Optional[Tuple[str, aiosqlite.Row]]:
        if len(path) == 2 and path[0] == 0:
            inbox = await self._get_inbox(conn, telegram_user_id)
            if inbox is None:
                return None
            item = await self._resolve_item_index(conn, inbox["id"], path[1])
            return None if item is None else ("item", item)

        if len(path) == 1:
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, path)
            return None if chapter is None else ("chapter", chapter)

        if len(path) == 2:
            top = await self._resolve_chapter_path(conn, telegram_user_id, [path[0]])
            if top is None:
                return None
            children = await self._get_children(conn, telegram_user_id, top["id"])
            child = self._by_display_index(children, path[1])
            if child is not None:
                return "chapter", child
            item = await self._resolve_item_index(conn, top["id"], path[1])
            return None if item is None else ("item", item)

        if len(path) == 3:
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, path[:2])
            if chapter is None:
                return None
            item = await self._resolve_item_index(conn, chapter["id"], path[2])
            return None if item is None else ("item", item)

        return None

    async def _resolve_move_target(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        path: Sequence[int],
    ) -> Optional[Tuple[str, aiosqlite.Row]]:
        if len(path) == 1:
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, path)
            return None if chapter is None else ("chapter", chapter)

        if len(path) == 2 and path[0] == 0:
            inbox = await self._get_inbox(conn, telegram_user_id)
            if inbox is None:
                return None
            item = await self._resolve_item_index(conn, inbox["id"], path[1])
            return None if item is None else ("item", item)

        if len(path) == 2:
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, [path[0]])
            if chapter is None:
                return None
            children = await self._get_children(conn, telegram_user_id, chapter["id"])
            child = self._by_display_index(children, path[1])
            if child is not None:
                return "chapter", child
            item = await self._resolve_item_index(conn, chapter["id"], path[1])
            return None if item is None else ("item", item)

        if len(path) == 3:
            chapter = await self._resolve_chapter_path(conn, telegram_user_id, path[:2])
            if chapter is None:
                return None
            item = await self._resolve_item_index(conn, chapter["id"], path[2])
            return None if item is None else ("item", item)

        return None

    async def _next_chapter_position(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        parent_id: Optional[str],
    ) -> int:
        if parent_id is None:
            row = await self._fetchone(
                conn,
                """
                SELECT COALESCE(MAX(position), 0) AS max_position
                FROM chapters
                WHERE telegram_user_id = ? AND parent_id IS NULL AND is_inbox = 0
                """,
                (telegram_user_id,),
            )
        else:
            row = await self._fetchone(
                conn,
                """
                SELECT COALESCE(MAX(position), 0) AS max_position
                FROM chapters
                WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0
                """,
                (telegram_user_id, parent_id),
            )
        return int(row["max_position"]) + 1

    async def _next_item_position(self, conn: aiosqlite.Connection, chapter_id: str, is_done: bool) -> int:
        row = await self._fetchone(
            conn,
            """
            SELECT COALESCE(MAX(position), 0) AS max_position
            FROM items
            WHERE chapter_id = ? AND is_done = ?
            """,
            (chapter_id, int(is_done)),
        )
        return int(row["max_position"]) + 1

    async def _max_chapter_position(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        parent_id: Optional[str],
    ) -> int:
        if parent_id is None:
            row = await self._fetchone(
                conn,
                """
                SELECT COALESCE(MAX(position), 0) AS max_position
                FROM chapters
                WHERE telegram_user_id = ? AND parent_id IS NULL AND is_inbox = 0
                """,
                (telegram_user_id,),
            )
        else:
            row = await self._fetchone(
                conn,
                """
                SELECT COALESCE(MAX(position), 0) AS max_position
                FROM chapters
                WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0
                """,
                (telegram_user_id, parent_id),
            )
        return int(row["max_position"])

    async def _max_item_position(self, conn: aiosqlite.Connection, chapter_id: str, is_done: int) -> int:
        row = await self._fetchone(
            conn,
            """
            SELECT COALESCE(MAX(position), 0) AS max_position
            FROM items
            WHERE chapter_id = ? AND is_done = ?
            """,
            (chapter_id, is_done),
        )
        return int(row["max_position"])

    async def _move_chapter_to_position(
        self,
        conn: aiosqlite.Connection,
        chapter: aiosqlite.Row,
        new_position: int,
    ) -> None:
        old_position = int(chapter["position"])
        if new_position < old_position:
            comparator = "position >= ? AND position < ?"
            delta = 1
            params = (new_position, old_position)
        else:
            comparator = "position > ? AND position <= ?"
            delta = -1
            params = (old_position, new_position)

        parent_clause = "parent_id IS NULL" if chapter["parent_id"] is None else "parent_id = ?"
        base_params: Tuple[Any, ...]
        if chapter["parent_id"] is None:
            base_params = (delta, chapter["telegram_user_id"])
        else:
            base_params = (delta, chapter["telegram_user_id"], chapter["parent_id"])
        await conn.execute(
            f"""
            UPDATE chapters
            SET position = position + ?, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_user_id = ? AND {parent_clause} AND is_inbox = 0
              AND id != ? AND {comparator}
            """,
            base_params + (chapter["id"],) + params,
        )
        await conn.execute(
            "UPDATE chapters SET position = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_position, chapter["id"]),
        )

    async def _move_item_to_position(
        self,
        conn: aiosqlite.Connection,
        item: aiosqlite.Row,
        new_position: int,
    ) -> None:
        old_position = int(item["position"])
        if new_position < old_position:
            comparator = "position >= ? AND position < ?"
            delta = 1
            params = (new_position, old_position)
        else:
            comparator = "position > ? AND position <= ?"
            delta = -1
            params = (old_position, new_position)

        await conn.execute(
            f"""
            UPDATE items
            SET position = position + ?, updated_at = CURRENT_TIMESTAMP
            WHERE chapter_id = ? AND is_done = ? AND id != ? AND {comparator}
            """,
            (delta, item["chapter_id"], item["is_done"], item["id"]) + params,
        )
        await conn.execute(
            "UPDATE items SET position = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_position, item["id"]),
        )

    async def _remove_chapter_position(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        parent_id: Optional[str],
        position: int,
    ) -> None:
        if parent_id is None:
            await conn.execute(
                """
                UPDATE chapters
                SET position = position - 1, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_user_id = ? AND parent_id IS NULL AND is_inbox = 0 AND position > ?
                """,
                (telegram_user_id, position),
            )
        else:
            await conn.execute(
                """
                UPDATE chapters
                SET position = position - 1, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0 AND position > ?
                """,
                (telegram_user_id, parent_id, position),
            )

    async def _remove_item_position(
        self,
        conn: aiosqlite.Connection,
        chapter_id: str,
        is_done: int,
        position: int,
    ) -> None:
        await conn.execute(
            """
            UPDATE items
            SET position = position - 1, updated_at = CURRENT_TIMESTAMP
            WHERE chapter_id = ? AND is_done = ? AND position > ?
            """,
            (chapter_id, is_done, position),
        )

    async def _record_history(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        action_type: str,
        payload: Dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            INSERT INTO operation_history (telegram_user_id, action_type, payload)
            VALUES (?, ?, ?)
            """,
            (telegram_user_id, action_type, json.dumps(payload, ensure_ascii=False)),
        )

    async def _apply_undo(
        self,
        conn: aiosqlite.Connection,
        action_type: str,
        payload: Dict[str, Any],
    ) -> None:
        if action_type == "create_chapter":
            row = await self._fetchone(
                conn,
                "SELECT * FROM chapters WHERE id = ?",
                (payload["chapter_id"],),
            )
            if row is not None:
                await self._restore_moved_items(conn, payload.get("moved_items", []))
                await conn.execute("DELETE FROM chapters WHERE id = ?", (row["id"],))
                await self._remove_chapter_position(conn, row["telegram_user_id"], row["parent_id"], row["position"])
            return

        if action_type == "create_item":
            row = await self._fetchone(conn, "SELECT * FROM items WHERE id = ?", (payload["item_id"],))
            if row is not None:
                await conn.execute("DELETE FROM items WHERE id = ?", (row["id"],))
                await self._remove_item_position(conn, row["chapter_id"], row["is_done"], row["position"])
            return

        if action_type == "delete_item":
            await self._restore_item(conn, payload["item"])
            return

        if action_type == "bulk_delete_items":
            for item in payload["items"]:
                await self._restore_item(conn, item)
            return

        if action_type == "delete_chapter":
            await self._restore_chapter_tree(conn, payload["chapter"])
            return

        if action_type == "rename_chapter":
            await conn.execute(
                "UPDATE chapters SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload["old_title"], payload["chapter_id"]),
            )
            return

        if action_type == "done_item":
            await self._undo_done_item(conn, payload)
            return

        if action_type == "bulk_done_items":
            for item in payload["items"]:
                await self._undo_done_item(conn, item)
            return

        if action_type == "move_chapter":
            row = await self._fetchone(conn, "SELECT * FROM chapters WHERE id = ?", (payload["chapter_id"],))
            if row is not None:
                await self._move_chapter_to_position(conn, row, payload["old_position"])
            return

        if action_type == "move_item":
            row = await self._fetchone(conn, "SELECT * FROM items WHERE id = ?", (payload["item_id"],))
            if row is not None:
                await self._move_item_to_position(conn, row, payload["old_position"])
            return

        raise RuntimeError(f"Unknown history action: {action_type}")

    async def _restore_item(self, conn: aiosqlite.Connection, item: Dict[str, Any]) -> None:
        await conn.execute(
            """
            UPDATE items
            SET position = position + 1, updated_at = CURRENT_TIMESTAMP
            WHERE chapter_id = ? AND is_done = ? AND position >= ?
            """,
            (item["chapter_id"], item["is_done"], item["position"]),
        )
        await conn.execute(
            """
            INSERT INTO items (id, chapter_id, text, position, is_done, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                item["chapter_id"],
                item["text"],
                item["position"],
                item["is_done"],
                item["created_at"],
                item["updated_at"],
            ),
        )

    async def _restore_moved_items(self, conn: aiosqlite.Connection, items: List[Dict[str, Any]]) -> None:
        for item in items:
            await conn.execute(
                """
                UPDATE items
                SET chapter_id = ?, position = ?, is_done = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (item["chapter_id"], item["position"], item["is_done"], item["id"]),
            )

    async def _undo_done_item(self, conn: aiosqlite.Connection, payload: Dict[str, Any]) -> None:
        current = await self._fetchone(conn, "SELECT * FROM items WHERE id = ?", (payload["item_id"],))
        if current is None:
            return
        await self._remove_item_position(conn, current["chapter_id"], current["is_done"], current["position"])
        await conn.execute(
            """
            UPDATE items
            SET position = position + 1, updated_at = CURRENT_TIMESTAMP
            WHERE chapter_id = ? AND is_done = ? AND position >= ?
            """,
            (payload["chapter_id"], payload["old_is_done"], payload["old_position"]),
        )
        await conn.execute(
            """
            UPDATE items
            SET is_done = ?, position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload["old_is_done"], payload["old_position"], payload["item_id"]),
        )

    async def _serialize_chapter_tree(self, conn: aiosqlite.Connection, chapter_id: str) -> Dict[str, Any]:
        chapter = await self._fetchone(conn, "SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        if chapter is None:
            raise RuntimeError(f"Chapter not found: {chapter_id}")
        items = await self._fetchall(
            conn,
            "SELECT * FROM items WHERE chapter_id = ? ORDER BY is_done ASC, position ASC",
            (chapter_id,),
        )
        children = await self._fetchall(
            conn,
            "SELECT * FROM chapters WHERE parent_id = ? ORDER BY position ASC",
            (chapter_id,),
        )
        node = self._row_to_dict(chapter)
        node["items"] = [self._row_to_dict(item) for item in items]
        node["children"] = [await self._serialize_chapter_tree(conn, child["id"]) for child in children]
        return node

    async def _restore_chapter_tree(self, conn: aiosqlite.Connection, chapter: Dict[str, Any]) -> None:
        await self._shift_chapters_for_restore(
            conn,
            chapter["telegram_user_id"],
            chapter["parent_id"],
            chapter["position"],
        )
        await self._insert_chapter_tree(conn, chapter)

    async def _shift_chapters_for_restore(
        self,
        conn: aiosqlite.Connection,
        telegram_user_id: int,
        parent_id: Optional[str],
        position: int,
    ) -> None:
        if parent_id is None:
            await conn.execute(
                """
                UPDATE chapters
                SET position = position + 1, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_user_id = ? AND parent_id IS NULL AND is_inbox = 0 AND position >= ?
                """,
                (telegram_user_id, position),
            )
        else:
            await conn.execute(
                """
                UPDATE chapters
                SET position = position + 1, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_user_id = ? AND parent_id = ? AND is_inbox = 0 AND position >= ?
                """,
                (telegram_user_id, parent_id, position),
            )

    async def _insert_chapter_tree(self, conn: aiosqlite.Connection, chapter: Dict[str, Any]) -> None:
        await conn.execute(
            """
            INSERT INTO chapters (
                id, telegram_user_id, parent_id, title, position, is_inbox, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chapter["id"],
                chapter["telegram_user_id"],
                chapter["parent_id"],
                chapter["title"],
                chapter["position"],
                chapter["is_inbox"],
                chapter["created_at"],
                chapter["updated_at"],
            ),
        )
        for item in chapter["items"]:
            await conn.execute(
                """
                INSERT INTO items (id, chapter_id, text, position, is_done, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["chapter_id"],
                    item["text"],
                    item["position"],
                    item["is_done"],
                    item["created_at"],
                    item["updated_at"],
                ),
            )
        for child in chapter["children"]:
            await self._insert_chapter_tree(conn, child)

    @staticmethod
    async def _fetchone(
        conn: aiosqlite.Connection,
        sql: str,
        params: Sequence[Any] = (),
    ) -> Optional[aiosqlite.Row]:
        async with conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    @staticmethod
    async def _fetchall(
        conn: aiosqlite.Connection,
        sql: str,
        params: Sequence[Any] = (),
    ) -> List[aiosqlite.Row]:
        async with conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    @staticmethod
    def _by_display_index(rows: Sequence[aiosqlite.Row], display_index: int) -> Optional[aiosqlite.Row]:
        if display_index < 1 or display_index > len(rows):
            return None
        return rows[display_index - 1]

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    @staticmethod
    def _row_to_reminder(row: aiosqlite.Row) -> ReminderView:
        return ReminderView(
            id=row["id"],
            telegram_user_id=int(row["telegram_user_id"]),
            chat_id=int(row["chat_id"]),
            text=row["text"],
            remind_at=_parse_dt(row["remind_at"]),
        )
