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
| `sync/inbox/`, `sync/out/` | Pages fetched by each sync run, and the SQL/connector batches it applied |
| `tagging/manual_tags.json` | Manual and visual-review tag overrides, keyed by post ID |
| `tagging/author_priors.json` | Author priors learned on full tagging runs |

The working copy with data, which the daily sync uses, is `/workspace/x-bookmarks`
on the Grok Bot box. This repository is a code-only copy of it. Without
`manual_tags.json` and `author_priors.json`, the tagger still runs with rules only.

## Daily sync

A Grok Bot routine, "Daily X bookmarks sync", is owned by the Cloudflare bot and
runs every day at 07:31 Europe/Zurich (`31 7 * * *`). It checks the 10 newest
bookmarks first and fetches further pages of 50 only when all of them are new,
up to 10 pages per run. Quoted posts come from the free public X reader. The
routine runs `sync/sync.py` in `/workspace/x-bookmarks` and applies the result to
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
# then: CallDynamicTool user-Cloudflare execute {"code": "$file:/workspace/x-bookmarks/site/dist/deploy.js"}
```

`deploy.js` uploads the Worker with its D1 and `ACCESS_AUD` bindings, keeps the
workers.dev route on and turns preview URLs off.

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
