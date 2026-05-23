-- posts: one row per IG post
CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    caption         TEXT,
    media_type      TEXT,
    permalink       TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    like_count      INTEGER,
    comment_count   INTEGER,
    thumbnail_url   TEXT,
    fetched_at      TEXT NOT NULL
);

-- comments: one row per IG comment, including replies
CREATE TABLE IF NOT EXISTS comments (
    id                  TEXT PRIMARY KEY,
    post_id             TEXT NOT NULL,
    parent_comment_id   TEXT,
    author_handle       TEXT,
    text                TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    like_count          INTEGER,
    fetched_at          TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id);
CREATE INDEX IF NOT EXISTS idx_comments_timestamp ON comments(timestamp);

-- comment_analysis: derived sentiment + future analysis outputs
CREATE TABLE IF NOT EXISTS comment_analysis (
    comment_id          TEXT PRIMARY KEY,
    sentiment_label     TEXT NOT NULL,
    sentiment_score     REAL,
    model_name          TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    analyzed_at         TEXT NOT NULL,
    FOREIGN KEY (comment_id) REFERENCES comments(id)
);

-- fetch_log: observability for every fetch run
CREATE TABLE IF NOT EXISTS fetch_log (
    run_id              TEXT PRIMARY KEY,
    scope_type          TEXT NOT NULL,
    scope_value         TEXT,
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    api_calls_made      INTEGER DEFAULT 0,
    comments_fetched    INTEGER DEFAULT 0,
    error               TEXT
);
