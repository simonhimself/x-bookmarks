-- Removals queue: posts Simon removed in the app. The bookmark row stays (so the incremental
-- sync still treats the id as known and never re-adds it); the site hides any id listed here.
-- done_at is set once the daily routine has unbookmarked the post on X. Idempotent.
CREATE TABLE IF NOT EXISTS removals (
  id TEXT PRIMARY KEY,             -- bookmarks.id
  removed_at TEXT NOT NULL,        -- ISO time the remove button was pressed
  done_at TEXT,                    -- ISO time the post was unbookmarked on X (NULL = pending)
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_removals_pending ON removals(done_at);
