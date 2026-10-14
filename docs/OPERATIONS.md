# Operations

Account-specific configuration, deployment, data locations and recovery for the
live site. For what the project does and how to run it locally, see the
[README](../README.md).

## Account configuration

| Item | Value |
| --- | --- |
| Live URL | https://x-bookmarks.simons.workers.dev |
| Cloudflare account ID | `2423947c3898625c52d1d37070dffd03` |
| Worker | `x-bookmarks` (workers.dev route on, preview URLs off) |
| D1 database | `x-bookmarks`, ID `14bf4a21-7cb1-403f-b558-f709ed307260`, bound as `DB` |
| Access team domain | `https://simonhimself.cloudflareaccess.com` |
| Access application AUD | `ACCESS_AUD` variable in [`site/wrangler.toml`](../site/wrangler.toml) |
| Allowed email | `simonhimself@gmail.com` (one-time PIN login) |
| X user ID (bookmarks owner) | `17562615` |

These values are set in code, not in secrets: the account, D1 and AUD values in
[`site/wrangler.toml`](../site/wrangler.toml) and
[`site/make_deploy_js.py`](../site/make_deploy_js.py), the team domain and allowed
email in [`site/src/worker.template.js`](../site/src/worker.template.js), and the X
user ID in the [sync routine contract](../sync/README.md). Change them there when
moving to another account.

The Access application and its policy are configured in the Cloudflare dashboard,
not in this repository. The Worker checks the Access token on every request as
well (signature, audience, issuer, expiry and email), so the allow-list in
`worker.template.js` must match the Access policy.

The repository has no credential files. Wrangler and the Cloudflare connector use
their own logins; `.dev.vars`, `.env*` and token or key files are gitignored.

## Where the data lives

All scripts resolve paths relative to the repository root and expect the data
next to the code. These files are gitignored and never committed:

| Path | Contents |
| --- | --- |
| `bookmarks.json` | Local mirror of D1 and the source of "known ids" for the sync |
| `quoted.json` | Quoted and replied-to posts from the initial export |
| `raw/` | Raw X API pages from the initial export |
| `sync/inbox/`, `sync/out/` | Pages fetched by each sync run, the SQL/connector batches it applied, and restore read scripts |
| `bookmarks.restored.json`, `bookmarks.before-restore-*.json` | Output of `sync/restore.py`, and the file it replaced when run with `--force` |
| `tagging/manual_tags.json` | Manual and visual-review tag overrides, keyed by post ID |
| `tagging/author_priors.json` | Author priors learned on full tagging runs |

The working copy with data, which the daily sync uses, is `/workspace/code/x-bookmarks`
on the Grok Bot box: a checkout of this repository with the data files ignored.
Without `manual_tags.json` and `author_priors.json`, the tagger still runs with
rules only. If the box is wiped, rebuild the data from D1 (see
[Recover from Cloudflare](#recover-from-cloudflare)).

## Daily sync

A Grok Bot routine, "Daily X bookmarks sync", is owned by the Cloudflare bot and
runs every day at 07:31 Europe/Zurich (`31 7 * * *`). It checks the 10 newest
bookmarks first and fetches further pages of 50 only when all of them are new,
up to 10 pages per run. Quoted posts come from the free public X reader. The
routine runs `sync/sync.py` in `/workspace/code/x-bookmarks` and applies the result to
D1. Data changes need no redeploy: the Worker reads D1 on each request and caches
by the `meta.data_version` row, which every sync bumps.

The step-by-step contract, the exact X API parameters and cost notes are in
[`sync/README.md`](../sync/README.md). The commands are:

```bash
python3 sync/sync.py check --page DIR/pNN.json   # exit 0 = stop paging, 10 = fetch next page
python3 sync/sync.py plan  --pages DIR           # count new posts, list quoted ids to fetch
python3 sync/sync.py run   --pages DIR           # normalize, tag, update bookmarks.json, write + apply SQL
python3 sync/sync.py push  --ids ID,ID           # re-push posts after editing tags by hand
```

`--apply auto` (the default) uses `wrangler d1 execute --remote` when Wrangler is
logged in. Otherwise it writes `sync/out/<timestamp>/apply_NN.js` files to run, in
order, with the Cloudflare connector's `execute` tool.

### Removals

The site's **Remove** button queues the post in the D1 `removals` table and hides it at once
(Undo un-queues it while pending). The daily routine reads the pending ids with
`sync/unbookmark.py pending`, calls `user-X` `delete_users_bookmark` (user `17562615`) for each,
and marks them with `sync/unbookmark.py done`. Failures stay pending with `attempts` and
`last_error`. Bookmark rows are never deleted, so a removed post stays "known" to the sync and
is never re-added. Details in [`sync/README.md`](../sync/README.md#removals-unbookmark-on-x).

Inspect the queue: `SELECT * FROM removals WHERE done_at IS NULL;` (pending) or
`... WHERE last_error IS NOT NULL;` (failing).

### Cost

X bills about $0.005 for every post `get_users_bookmarks` returns, including posts
already in the database. Checking 10 posts costs about $0.05; a full page of 50
costs about $0.25. X API credit is prepaid and is managed in the
[X Developer Console](https://console.x.com). Notes from the initial export,
including the `max_results=100` paging quirk, are in
[`EXPORT_NOTES.md`](../EXPORT_NOTES.md).

## Deploy

Data changes never need a deploy. Deploy only after changing `site/` or the
taxonomy.

With a logged-in Wrangler:

```bash
python3 site/build.py            # inlines index.html + taxonomy into site/dist/worker.js
cd site && npx wrangler deploy   # uses wrangler.toml (D1 binding, ACCESS_AUD var)
```

Without a logged-in Wrangler, use the Cloudflare connector:

```bash
python3 site/build.py && python3 site/make_deploy_js.py
# then: CallDynamicTool user-Cloudflare execute {"code": "$file:/workspace/code/x-bookmarks/site/dist/deploy.js"}
```

`deploy.js` uploads the Worker with its D1 and `ACCESS_AUD` bindings, keeps the
workers.dev route on and turns preview URLs off.

## Migrations

Existing databases need [`site/migrations/0001_removals.sql`](../site/migrations/0001_removals.sql)
(creates `removals`; idempotent, doesn't touch `bookmarks`) **before** deploying a Worker with the
Remove button, because `/api/bookmarks` reads that table:

```bash
cd site && npx wrangler d1 execute x-bookmarks --remote --file migrations/0001_removals.sql
```

`schema.sql` already includes it for new databases.

## YouTube

The site has an 𝕏 | YouTube switch. YouTube data comes from the YouTube Data API v3 with read-only
access (`youtube.readonly`), Google Cloud project `x-bookmarks-youtube`, OAuth client
`449518142865-mjkqjg7i3ueco2iabnlv0s6isqi911lj.apps.googleusercontent.com`, redirect URI
`https://x-bookmarks.simons.workers.dev/oauth/youtube/callback`. The consent screen is published
(in production, unverified), so refresh tokens don't expire after 7 days.

| Item | Where |
| --- | --- |
| Worker secrets | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TOKEN_KEY` (32 random bytes, base64) |
| Refresh/access token | D1 table `yt_oauth`, AES-GCM sealed with `TOKEN_KEY` |
| Tables | `yt_channels`, `videos`, `yt_playlists`, `yt_stars` ([migration 0002](../site/migrations/0002_youtube.sql)) |
| Sync | cron `*/10 * * * *`; each run makes at most 40 subrequests (`YT_FETCH_BUDGET`) |
| Status | `GET /api/yt/status`; the YouTube view shows it with a "Sync now" button |

Daily cycle (UTC day): subscriptions → newest uploads of each subscribed channel (first time: last 10;
later: everything newer than the last seen video, up to 10) → likes (full history the first time) →
playlists whose etag changed → video details, Shorts detection and topic tags (the same rules as X,
ported to JS by `build.py`; `tagging/parity_test.py` checks they agree). Then runs are no-ops until
the next UTC day. About 70 quota units/day for 60 channels; roughly 550 for 500 (limit 10,000).
Unsubscribed channels keep their videos (flagged). Stars live only in the app.

Connect: open the YouTube view and click **Connect YouTube** (Google shows an "unverified app" warning
once: Advanced → Go to …). Reconnect the same way if the status shows `invalid_grant`.
`/privacy` is a short privacy note; it is behind Access like the rest of the host.

## Recovery

- **Create the database schema** (first time or on a new database):
  `cd site && npx wrangler d1 execute x-bookmarks --remote --file schema.sql`
- **Reload all rows from the local mirror:** `python3 sync/build_initial.py` writes
  the schema plus an upsert for every post in `bookmarks.json` as connector batches
  in `sync/out/initial/`. Run them in order with the Cloudflare connector.
- **Fix tags by hand:** add `"<id>": ["tag", ...]` entries to
  `tagging/manual_tags.json`, then `python3 sync/sync.py push --ids <ids>` and apply
  the files it prints.
- **Missed sync days:** the next run pages from the newest bookmark until it finds
  a known post, so gaps fill in automatically within the 10-page cap. `plan` warns
  and `run` refuses if no known post was reached; fetch more pages, or pass
  `--allow-gap` to accept the gap.
- **"Forbidden" after signing in:** the Worker rejected the Access token. Check that
  the Access application's AUD matches `ACCESS_AUD` and that the signed-in email is
  in `ALLOWED_EMAILS`.

## Recover from Cloudflare

D1 is the durable copy of the data. If the box is wiped, `sync/restore.py`
rebuilds `bookmarks.json` from it. It only ever sends one fixed `SELECT` to D1,
reads every row in pages of 500 (newest first, by `seq`), and never writes,
deploys or bumps `data_version`.

### Steps on a fresh machine

1. Clone the repository where the sync expects it:

   ```bash
   git clone https://github.com/simonhimself/x-bookmarks.git /workspace/code/x-bookmarks
   cd /workspace/code/x-bookmarks
   ```

2. Read D1. `fetch` picks Wrangler when `npx wrangler whoami` is logged in, and
   the Cloudflare connector otherwise (force one with `--via wrangler` or
   `--via connector`).

   - **Wrangler:** `python3 sync/restore.py fetch` reads every row with
     `wrangler d1 execute x-bookmarks --remote --json` and writes
     `bookmarks.restored.json` in one go. Continue with step 4.
   - **Connector:** `python3 sync/restore.py fetch --via connector` writes
     `sync/out/restore-<ts>/read_00.js`. Run it with the connector, saving the
     result to a file:

     ```
     CallDynamicTool namespace=user-Cloudflare toolName=execute write_to_file=true
       arguments={"code": "$file:/workspace/code/x-bookmarks/sync/out/restore-<ts>/read_00.js"}
     ```

3. Connector only: the connector returns at most about 24,000 characters per
   call, so each script reads the whole table, compresses it and returns one
   numbered slice. Pass the first result file to
   `python3 sync/restore.py build --dump <result file>`. It writes the
   remaining `read_01.js` … `read_NN.js` (about 18 for 2,300 bookmarks) and exits
   with code 10. Run them all the same way, then pass every result file:

   ```bash
   python3 sync/restore.py build --dump <file 00> <file 01> … <file NN>
   ```

   Each slice carries a SHA-256 of the whole dump. If a sync ran between two
   calls, `build` stops and asks you to read all parts again instead of mixing
   two snapshots. It also checks that the row count matches `COUNT(*)`.

4. Check the output. `build` writes `bookmarks.restored.json` and, when a
   `bookmarks.json` exists, prints a comparison: counts, ids on only one side and
   every differing field. `python3 sync/restore.py compare` repeats it.

5. Put it in place. On a wiped machine there is no `bookmarks.json` yet:
   `mv bookmarks.restored.json bookmarks.json`. To replace an existing file, run
   `build` again with `--out bookmarks.json --force`; the old file is moved to
   `bookmarks.before-restore-<ts>.json` first. Without `--force` it refuses.

6. Recreate the tagging files: `python3 sync/restore.py tagging`. It writes
   `tagging/author_priors.json` and `tagging/manual_tags.json` only if they're
   missing (`--dry-run` shows the counts, `--force` replaces them).

The daily sync then works unchanged: it only needs each post's id, `seq`, tags
and the fields `sync.py push` writes back, and those all come back exactly.

### What comes back, and what doesn't

D1 stores the 16 columns in [`site/schema.sql`](../site/schema.sql), not the
full `bookmarks.json` record. Tested against the live database on 2026-10-11
(2,314 rows): the id sets matched, and for every post the restored record turns
back into exactly the D1 row (`to_row` in `sync/lib.py`), so a later `push` of a
restored post changes nothing.

Exact: `id`, `url`, `created_at`, `author_username`, `author_name`,
`author_profile_image_url`, `external_links`, media type and image URL,
`lang`, `metrics.like_count`, `tags`, `primary_tag`, `seq`, `bookmark_rank`,
`folders` (always empty), `referenced_tweets` (from the quoted and replied
posts), and the quoted or replied post's id, URL, author, date, media and
availability.

Not stored in D1, so lost or approximated:

| Field | After a restore |
| --- | --- |
| `text` | The cleaned text D1 shows: `t.co` links expanded, links to the quoted or replied post removed. The raw API text is lost (differed for about 1,630 posts). |
| `text_expanded` | Same as `text`; differs only where a link to the quoted or replied post was removed (about 440 posts). |
| `author_id` | `null` |
| `metrics` | Only `like_count`; bookmark, impression, quote, reply and repost counts are lost. |
| `media[].media_key` | Lost; `type`, `url` and `preview_image_url` are exact. |
| `links` | External links plus the quoted or replied post's URL; other X links are lost. |
| `hashtags`, `mentions` | Re-extracted from the text, so close but not identical (1 and 18 posts differed). |
| `tag_source` | `manual` for ids in `manual_tags.json`, `unclear` for posts tagged only "Other", `rules` otherwise. |
| Quoted and replied posts | `text` is the cleaned text; `links` is empty; the `reason` for an unavailable post is lost. |

None of these are used by the sync, the tagger's stored tags or the site.

`restore.py` reads only `bookmarks`; the `removals` table stays in D1 and keeps hiding removed
posts. Removed posts come back into `bookmarks.json` like any other, which is what keeps them
"known" to the sync.

`tagging/author_priors.json` is recovered exactly: it's learned from the tags,
which D1 keeps. `tagging/manual_tags.json` is not in D1 as such: D1 keeps the
tags it produced but not which posts were fixed by hand. `restore.py tagging`
writes an equivalent file that pins every post whose stored tags differ from what
the rules alone give (538 posts in the test; the original had 539, 77 of which
the rules reproduce anyway). Re-tagging with it reproduces every tag in D1.

`quoted.json`, `raw/`, `tagging/visual_review/`, `tagging/manual_by_rank_*.txt`
and old `sync/out/` batches are not recoverable. Only the initial-export helpers
used them; the sync, tagger and site don't need them.
