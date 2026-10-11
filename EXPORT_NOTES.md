# X bookmarks export notes (2026-10-11)
- 1449 unique bookmarks fetched (ranks 1-1449), NOT complete: last page (raw/rich50/p29.json) still had next_token.
- Resume with get_users_bookmarks id=17562615 max_results=50 pagination_token=7140dibdnow9c7btw4b157mp4uyps6uy75evrcf2khfee
- max_results=100 ends early: page 2 returned 97 posts and no next_token (raw/page02.json). Use 50.
- Credits: 14.02 -> 8.01 after ~1,500 post reads (~0.004/post).
- bookmarks_v1_197.json = first export. normalize.py rebuilds bookmarks.json from raw/.

## Cheap test page (2026-10-11 10:50)
- raw/cheap50/p30.json: ranks 1450-1499, no expansions, post.fields only. Cost $0.25 for 50 posts ($0.005/post), balance $7.76 -> $7.51.
- 25 posts by authors not seen before: author_username/name are null, author_id only. Media entries have media_key only.
- Resume with pagination_token=7140dibdnow9c7btw4b155fkl4grg4twr3low8718pflc (next page after #1,499).
- Earlier "~$0.004/post" was wrong: re-reads of already-billed posts on the same day weren't charged and expansions weren't billed. Real cost is $0.005 per new post.

## Full run (2026-10-11 ~10:55-11:10): COMPLETE
- raw/full50/p31-p47 fetched; p47 returned 15 posts and no next_token, so the export reached the end.
- Total 2,314 unique bookmarks (ranks 1-2314). Balance $7.51 -> $3.43 ($4.08 for 815 new posts, $0.005/post).
- raw/cheap50/p30.json was re-fetched with expansions at no cost (balance unchanged at $3.43). The version without expansions is in raw/archive/.
- To refresh later, page from the start with max_results=50 (NOT 100) and stop at the first already-known id.
