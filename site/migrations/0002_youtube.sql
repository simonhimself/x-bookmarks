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
