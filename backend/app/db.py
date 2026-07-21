import sqlite3
from contextlib import closing
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent / "data" / "app.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fictional_characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    birth_date TEXT,
    death_date TEXT
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    fictional_character_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    media_url TEXT,
    event_date TEXT,
    event_date_label TEXT,
    label TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fictional_character_id) REFERENCES fictional_characters(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS post_groups (
    post_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, group_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS likes (
    profile_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, post_id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_group_follows (
    profile_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, group_id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_character_event_date
    ON posts(fictional_character_id, event_date);
CREATE INDEX IF NOT EXISTS idx_post_groups_group_post
    ON post_groups(group_id, post_id);
CREATE INDEX IF NOT EXISTS idx_comments_post_created_at
    ON comments(post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_profile_group_follows_profile_group
    ON profile_group_follows(profile_id, group_id);
"""


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize() -> None:
    with closing(connect()) as connection:
        connection.executescript(SCHEMA)
        connection.commit()


def is_ready() -> bool:
    try:
        with closing(connect()) as connection:
            connection.execute("SELECT 1")
        return True
    except (OSError, sqlite3.Error):
        return False
