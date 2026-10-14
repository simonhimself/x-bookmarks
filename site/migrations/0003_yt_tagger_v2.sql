-- YouTube tagger v2: channel priors and retag bookkeeping (additive).
ALTER TABLE videos ADD COLUMN base_tag TEXT;               -- primary topic without the channel prior
ALTER TABLE videos ADD COLUMN tag_ver INTEGER NOT NULL DEFAULT 0;  -- TAGGER_VERSION*10+1 = base done, +2 = final
ALTER TABLE yt_channels ADD COLUMN prior_tag TEXT;         -- majority topic of the channel's videos
