# x-bookmarks

A private browser for Simon's X (Twitter) bookmarks, running on Cloudflare Workers + D1 and locked
behind Cloudflare Access (only simonhimself@gmail.com can sign in, via one-time PIN).

Live: https://x-bookmarks.simons.workers.dev

This repo holds **code and docs only**. No bookmark data is committed (see "Where the data lives").

## Architecture

1. **Export.** Bookmarks are read from the X API through Grok Bot's X plugin (`get_users_bookmarks`,
   50 per page; X bills about $0.005 per post returned). Quoted and replied-to posts are fetched free
   through the public X reader. `normalize.py` / `sync/lib.py` turn raw API pages into `bookmarks.json`.
2. **Tagging.** `tagging/tag.py` assigns 1-3 topic tags per post from `taxonomy.json`, keyword rules
   (`rules.py`), learned author priors and manual/visual overrides (`manual_tags.json`, which wins).
3. **Storage.** Cloudflare D1 database `x-bookmarks` (schema in `site/schema.sql`): one `bookmarks`
   table plus a `meta` table whose `data_version` row is bumped on every sync (used as cache key/ETag).
4. **UI.** A single Worker (`site/src/worker.template.js` + `index.html`) serves the page and a
   read-only `/api/bookmarks` endpoint. It also verifies the Cloudflare Access JWT itself. There are
   no write endpoints. Filters: topic, month/year, author, media/link/quote, full-text search.
5. **Daily sync.** A Grok Bot routine (owned by Simon's Cloudflare bot, 07:31 Europe/Zurich) fetches
   the newest bookmarks (10 first, more only if all are new), fetches their quoted posts, tags them and
   upserts them into D1. Data changes need no redeploy. Details: `sync/README.md`.

## Deploy

```
python3 site/build.py            # inlines index.html + taxonomy into site/dist/worker.js
cd site && npx wrangler deploy   # uses wrangler.toml (D1 binding, ACCESS_AUD var)
npx wrangler d1 execute x-bookmarks --remote --file schema.sql   # first time only
```

Without a logged-in wrangler, `python3 site/make_deploy_js.py` writes `site/dist/deploy.js`, which
uploads the Worker through the Cloudflare connector's `execute` tool instead.
Local preview: `cd site && npx wrangler dev --local --var ALLOW_LOCAL:1`.

The Access application and policy are configured in the Cloudflare dashboard, not in this repo.

## Sync

```
python3 sync/sync.py check --page DIR/pNN.json   # exit 0 = stop paging, 10 = fetch next page
python3 sync/sync.py plan  --pages DIR           # count new posts, list quoted ids to fetch
python3 sync/sync.py run   --pages DIR           # normalize, tag, update bookmarks.json, write + apply SQL
```

See `sync/README.md` for the full routine contract and cost notes.

## Layout

```
site/        Worker source (src/), build.py, make_deploy_js.py, schema.sql, wrangler.toml
sync/        incremental sync (sync.py, lib.py), one-off loaders, README with routine contract
tagging/     tagger (tag.py, rules.py, taxonomy.json)
scripts/     small helpers (page_meta.py: print meta of saved API pages)
normalize.py, parse_quoted.py, savepage.py, cluster.py   initial-export helpers
EXPORT_NOTES.md   notes from the initial export (paging quirks, costs)
x-guide.md        copy of the X plugin's usage guide
```

## Where the data lives

All scripts resolve paths relative to the repo root and expect data next to the code:
`bookmarks.json` (local mirror of D1), `quoted.json`, `raw/` (API pages), `sync/out/` and
`sync/inbox/` (sync runs), and `tagging/manual_tags.json` / `author_priors.json` (personal tag
overrides). All of these are gitignored. The working copy with data, which the daily sync uses, is
`/workspace/x-bookmarks` on the Grok Bot box; this repo is a code-only copy of it.
Without `manual_tags.json` / `author_priors.json` the tagger still runs, using rules only.
