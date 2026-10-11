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
