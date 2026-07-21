CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS fictional_characters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    birth_date TEXT,
    death_date TEXT,
    profile_photo_url TEXT
);

CREATE TABLE IF NOT EXISTS groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    fictional_character_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    media_url TEXT,
    content_type TEXT NOT NULL CHECK (content_type IN ('text', 'image', 'video', 'reel')),
    thumbnail_url TEXT,
    historical_start_year INTEGER NOT NULL,
    historical_end_year INTEGER,
    historical_precision TEXT NOT NULL
        CHECK (historical_precision IN ('year', 'month', 'day', 'range', 'circa')),
    historical_date_label TEXT NOT NULL,
    label TEXT,
    tags TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags) AND json_type(tags) = 'array'),
    source_url TEXT,
    source_title TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (fictional_character_id) REFERENCES fictional_characters(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS post_groups (
    post_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    PRIMARY KEY (post_id, group_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS likes (
    profile_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (profile_id, post_id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_group_follows (
    profile_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (profile_id, group_id),
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_posts_character_event_date
    ON posts(fictional_character_id, historical_start_year);
CREATE INDEX IF NOT EXISTS idx_post_groups_group_post
    ON post_groups(group_id, post_id);
CREATE INDEX IF NOT EXISTS idx_comments_post_created_at
    ON comments(post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_profile_group_follows_profile_group
    ON profile_group_follows(profile_id, group_id);
