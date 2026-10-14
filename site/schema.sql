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
-- YouTube library (additive only; X tables untouched).
CREATE TABLE IF NOT EXISTS yt_channels (
  id TEXT PRIMARY KEY,               -- UC… channel id
  title TEXT, thumb TEXT,
  uploads_playlist TEXT,             -- UU… (derived from the channel id)
  subscribed INTEGER NOT NULL DEFAULT 1,   -- 0 = unsubscribed; its videos are kept
  seen_day TEXT,                     -- UTC day the channel was last seen in subscriptions
  checked_day TEXT,                  -- UTC day its uploads were last checked
  last_video_id TEXT                 -- newest upload seen, to stop paging
);
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,               -- 11-char YouTube video id
  channel_id TEXT, channel_title TEXT,
  title TEXT, description TEXT, yt_tags TEXT,
  published_at TEXT, duration_s INTEGER,
  is_short INTEGER NOT NULL DEFAULT 0,
  live_state TEXT,                   -- NULL | live | upcoming | was_live
  thumb TEXT, views INTEGER, lang TEXT,
  sources TEXT NOT NULL DEFAULT '[]',  -- JSON: "sub", "like", "pl:<playlist id>"
  liked_at TEXT,
  added_at TEXT NOT NULL,            -- first time the sync saw it
  tags TEXT, primary_tag TEXT, tag_source TEXT,
  needs_details INTEGER NOT NULL DEFAULT 1,
  unavailable INTEGER NOT NULL DEFAULT 0     -- private/deleted
);
CREATE INDEX IF NOT EXISTS idx_videos_added ON videos(added_at);
CREATE INDEX IF NOT EXISTS idx_videos_pending ON videos(needs_details);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
CREATE TABLE IF NOT EXISTS yt_playlists (
  id TEXT PRIMARY KEY, title TEXT, item_count INTEGER, etag TEXT,
  dirty INTEGER NOT NULL DEFAULT 1, seen_day TEXT
);
CREATE TABLE IF NOT EXISTS yt_stars (
  id TEXT PRIMARY KEY,               -- videos.id
  starred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS yt_oauth (
  k TEXT PRIMARY KEY,                -- refresh_token / access_token (AES-GCM sealed with TOKEN_KEY), connected (JSON)
  v TEXT
);
-- YouTube tagger v2: channel priors and retag bookkeeping (additive).
ALTER TABLE videos ADD COLUMN base_tag TEXT;               -- primary topic without the channel prior
ALTER TABLE videos ADD COLUMN tag_ver INTEGER NOT NULL DEFAULT 0;  -- TAGGER_VERSION*10+1 = base done, +2 = final
ALTER TABLE yt_channels ADD COLUMN prior_tag TEXT;         -- majority topic of the channel's videos
