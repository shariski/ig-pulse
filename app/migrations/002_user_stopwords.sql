-- Per-user custom stopwords that overlay app/analysis/stopwords_custom.txt
-- without modifying the checked-in file. INSERT OR IGNORE on add makes
-- the add path idempotent.
CREATE TABLE IF NOT EXISTS user_stopwords (
    word        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
