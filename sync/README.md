# x-bookmarks sync

Adds newly bookmarked X posts to the private site at https://x-bookmarks.simons.workers.dev
(Worker `x-bookmarks`, D1 database `x-bookmarks` / 14bf4a21-7cb1-403f-b558-f709ed307260).

`bookmarks.json` (one level up) is the local mirror of D1 and the source of "known ids". Every
`sync.py run` updates it and D1 together, so always run the sync from this box.

Data changes need **no redeploy**: the Worker reads D1 on each request and the cache key is the
`meta.data_version` row, which every sync bumps.

## Commands

```
python3 sync/sync.py check --page DIR/pNN.json   # exit 0 = STOP paging, exit 10 = fetch the next page
python3 sync/sync.py plan  --pages DIR           # count new posts, write DIR/missing_ref_ids.txt
python3 sync/sync.py run   --pages DIR [--apply auto|wrangler|connector] [--allow-gap]
python3 sync/sync.py push  --ids ID,ID [--apply ...]   # re-push posts after editing tags by hand
```

`--apply auto` (the default) uses `wrangler d1 execute --remote` if `wrangler whoami` is
authenticated. Otherwise (today's setup: wrangler isn't logged in on the box) it writes
`sync/out/<timestamp>/apply_NN.js` and prints them. Run each one, in order, with the Cloudflare
connector:

```
CallDynamicTool namespace=user-Cloudflare toolName=execute arguments={"code": "$file:/workspace/code/x-bookmarks/sync/out/<ts>/apply_00.js"}
```

Each call should return `success: true`. `sync/out/<ts>/upsert.sql` has the same SQL in plain form.

## Contract for the scheduled routine

The routine does the X fetch (the only step that costs money) and then runs this script.

1. Make a fresh folder: `DIR=/workspace/code/x-bookmarks/sync/inbox/$(date +%Y%m%d-%H%M)`.
2. Page through bookmarks **from the start**: call `user-X` `get_users_bookmarks` with
   - `id=17562615`, `max_results=50` (never 100: it ends early, see EXPORT_NOTES.md)
   - `post.fields=created_at,author_id,note_tweet,entities,attachments,public_metrics,lang,referenced_tweets`
   - `expansions=author_id,attachments.media_keys,referenced_tweets.id,referenced_tweets.id.author_id`
   - `user.fields=username,name,profile_image_url`, `media.fields=type,url,preview_image_url`
   - `pagination_token=<meta.next_token of the previous page>` from page 2 on
   - `write_to_file: true`

   Copy each result to `$DIR/p01.json`, `$DIR/p02.json`, … (p01 = first/newest page). Wrapper text
   around the JSON is fine.
3. After saving each page run `python3 sync/sync.py check --page $DIR/pNN.json`.
   **Exit 0 means stop**: the page contains a post id that's already in the DB, or there's no
   next_token. Exit 10 means fetch the next page. Also stop after at most 10 pages per run as a
   spending cap, and report it if the cap was hit.
4. `python3 sync/sync.py plan --pages $DIR`. If `$DIR/missing_ref_ids.txt` isn't empty, fetch each
   line (up to 25 comma-separated ids) with the **free** public reader: namespace `x`, tool
   `get_posts_by_ids`, `ids=<line>`, `expansions=author_id,attachments.media_keys`,
   `post.fields=created_at,author_id,note_tweet,entities,attachments,lang`,
   `user.fields=username,name,profile_image_url`, `media.fields=type,url,preview_image_url`, with
   `write_to_file: true`. Save the results as `$DIR/quoted/q01.json`, … Never use `user-X` for this.
5. `python3 sync/sync.py run --pages $DIR`, then run the printed `apply_NN.js` files through the
   connector as shown above.
6. Optional: if `$DIR/unclear.txt` exists (posts with no usable text, tagged `other`), look at the
   listed images, add `"<id>": ["tag", ...]` entries to `tagging/manual_tags.json`, then run
   `python3 sync/sync.py push --ids <ids>` and apply the files it prints.
7. **Unbookmark removed posts** (see below).
8. Report the number of new bookmarks, the number unbookmarked and still pending, the X credit used, and anything left unclear.

### Removals: unbookmark on X

Clicking **Remove** in the app inserts the id into the D1 `removals` table (`done_at` NULL =
pending) and hides it from the site. The row in `bookmarks` and in `bookmarks.json` is kept on
purpose: the id stays "known", so `check`/`run` stop at it and never re-add it, even if X still
returns it because the unbookmark hasn't happened yet or failed.

1. `python3 sync/unbookmark.py pending` writes `sync/out/unbookmark-<ts>/pending.txt` (up to 50
   ids, oldest removal first). With the connector it writes `read_pending.js` instead: run it with
   `user-Cloudflare` `execute` (`write_to_file: true`), then
   `python3 sync/unbookmark.py pending --from-result <result file>`.
2. For each id call `user-X` `delete_users_bookmark` with `id=17562615`, `tweet_id=<id>`. Only ids
   from `pending.txt`, one call each, no retries in a loop. A response with
   `data.bookmarked == false` is success (also when it was already unbookmarked).
3. `python3 sync/unbookmark.py done --ok ID,ID --failed 'ID=reason' ...` sets `done_at` for
   successes and records `attempts`/`last_error` for failures, which stay pending for the next run.
   Apply the printed `apply_done.js` with the connector if wrangler isn't logged in.

Unbookmarking is a write and isn't billed per post like reads; it doesn't change `data_version`.
Undo in the app only works while the id is still pending.

### Cost note (important)

X bills $0.005 for every post returned by `get_users_bookmarks`, including posts already in the
DB. A page of 50 therefore costs about $0.25 even when only one post is new, which is about
$7.50 a month for a daily run. Simon has about $3.43 of credit left. Cheaper options, if Simon
agrees: run it weekly, or make the first request `max_results=10` and switch to 50 only when all
10 are new (`check` and `run` work with any page size).

## Tagging

`tagging/tag.py` holds the taxonomy (`taxonomy.json`), keyword rules (`rules.py`), author priors
(`author_priors.json`, learned on full runs) and manual or visual overrides (`manual_tags.json`,
keyed by post id; these win over the rules). Re-tag everything with
`python3 tagging/tag.py bookmarks.json`, then push the changed ids.

## Site code changes (rare)

```
python3 site/build.py && python3 site/make_deploy_js.py
# then: CallDynamicTool user-Cloudflare execute {"code": "$file:/workspace/code/x-bookmarks/site/dist/deploy.js"}
```
`deploy.js` uploads the Worker with its D1 and Access-AUD bindings and keeps preview URLs off.
Local preview: `cd site && npx wrangler dev --local --var ALLOW_LOCAL:1` (local D1; load it with
`npx wrangler d1 execute x-bookmarks --local --file <sql>`).

## Recover from Cloudflare

If the box was wiped, `sync/restore.py` rebuilds `bookmarks.json` from D1, read-only:

```
python3 sync/restore.py fetch [--via auto|wrangler|connector]   # wrangler: reads D1 and builds directly
python3 sync/restore.py build --dump <result files...>          # connector: turn read_NN.js results into the file
python3 sync/restore.py compare                                 # bookmarks.json vs bookmarks.restored.json
python3 sync/restore.py tagging                                 # recreate author_priors.json + manual_tags.json
```

Output goes to `bookmarks.restored.json`; it replaces `bookmarks.json` only with
`--out bookmarks.json --force`. With the connector, run `read_00.js` first, give its
result file to `build`, which writes the remaining `read_NN.js` parts, then pass all
result files to `build`. Full steps and what can't be recovered are in
[docs/OPERATIONS.md](../docs/OPERATIONS.md#recover-from-cloudflare).
