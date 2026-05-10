SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL,
    parent_id TEXT,
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    is_inbox INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES chapters (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL,
    text TEXT NOT NULL,
    position INTEGER NOT NULL,
    is_done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS render_state (
    telegram_user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    section_key TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (telegram_user_id, chat_id, section_key),
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS operation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    sent_message_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chapters_user_parent_position
    ON chapters (telegram_user_id, parent_id, position);
CREATE INDEX IF NOT EXISTS idx_chapters_user_inbox
    ON chapters (telegram_user_id, is_inbox);
CREATE INDEX IF NOT EXISTS idx_items_chapter_done_position
    ON items (chapter_id, is_done, position);
CREATE INDEX IF NOT EXISTS idx_history_user_id
    ON operation_history (telegram_user_id, id);
CREATE INDEX IF NOT EXISTS idx_reminders_status_time
    ON reminders (status, remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_user_status_time
    ON reminders (telegram_user_id, status, remind_at);
"""
