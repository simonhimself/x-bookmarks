# Local tests (no Google, no live D1)

```bash
S=/tmp/xbm-local; mkdir -p $S
cat > $S/dev.vars <<V
ALLOW_LOCAL=1
TOKEN_KEY=$(head -c32 /dev/urandom | base64)
GOOGLE_CLIENT_ID=mock-client
GOOGLE_CLIENT_SECRET=mock-secret
YT_API_BASE=http://127.0.0.1:8789/yt
GOOGLE_TOKEN_URL=http://127.0.0.1:8789/token
GOOGLE_AUTH_URL=http://127.0.0.1:8789/auth
V
cd site && python3 build.py
npx wrangler d1 execute x-bookmarks --local --persist-to $S/state --file schema.sql
node test/mock_youtube.mjs 8789 60 &            # made-up channels/videos, no real data
npx wrangler dev --local --port 8787 --persist-to $S/state --env-file $S/dev.vars --test-scheduled &
PERSIST=$S/state python3 test/local_e2e.py      # OAuth, CSRF, batched cron sync, stars, next-day sync
python3 ../tagging/parity_test.py               # JS tagger == tag.py rules on bookmarks.json
```
Open http://localhost:8787/#src=yt for the YouTube view. `--local` everywhere: nothing touches the live database.
