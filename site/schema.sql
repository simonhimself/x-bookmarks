CREATE TABLE IF NOT EXISTS bookmarks (
  id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL,            -- bookmark order: higher = bookmarked more recently
  created_at TEXT,
  author_username TEXT, author_name TEXT, author_img TEXT,
  text TEXT, url TEXT,
  ext_links TEXT, media TEXT, tags TEXT, primary_tag TEXT,
  quoted TEXT, replied TEXT,
  likes INTEGER DEFAULT 0, lang TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookmarks_seq ON bookmarks(seq);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS removals (
  id TEXT PRIMARY KEY,             -- bookmarks.id
  removed_at TEXT NOT NULL,        -- ISO time the remove button was pressed
  done_at TEXT,                    -- ISO time the post was unbookmarked on X (NULL = pending)
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_removals_pending ON removals(done_at);
