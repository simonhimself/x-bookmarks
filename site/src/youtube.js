// ---- YouTube library (inlined into dist/worker.js by build.py) ----------------------------------
// Read-only YouTube access (youtube.readonly). The refresh token is stored in D1 (table yt_oauth),
// AES-GCM encrypted with the Worker secret TOKEN_KEY; D1 alone never holds a usable token.
// Sync runs from the cron trigger in small batches so each invocation stays under the Free-plan
// limit of 50 subrequests (YT_FETCH_BUDGET, default 40) and does little CPU work.
const YT_SCOPE = "https://www.googleapis.com/auth/youtube.readonly";
const TAG_RULES = __TAG_RULES__;          // generated from tagging/rules.py
const TAG_IDS = TAXONOMY.map(t => t.id);
const COMPILED = Object.fromEntries(Object.entries(TAG_RULES.R).map(([k, v]) => [k, v.map(([p, w]) => [new RegExp("(?<![a-z0-9])(?:" + p + ")", "gi"), w])]));

function ytCfg(env) {
  return {
    api: env.YT_API_BASE || "https://www.googleapis.com/youtube/v3",
    tokenUrl: env.GOOGLE_TOKEN_URL || "https://oauth2.googleapis.com/token",
    authUrl: env.GOOGLE_AUTH_URL || "https://accounts.google.com/o/oauth2/v2/auth",
    budget: Math.max(5, Math.min(45, parseInt(env.YT_FETCH_BUDGET || "40", 10) || 40)),
  };
}

// ---------- tagging (port of tagging/tag.py scoring; parity-tested in tagging/parity_test.mjs) ----------
function tagScore(text, author) {
  const s = {};
  for (const [tag, rs] of Object.entries(COMPILED)) {
    for (const [rx, w] of rs) {
      rx.lastIndex = 0;
      const n = (text.match(rx) || []).length;
      if (n) s[tag] = (s[tag] || 0) + w * Math.min(n, 3);
    }
  }
  if (author && TAG_RULES.AUTHOR[author]) { const t = TAG_RULES.AUTHOR[author]; s[t] = (s[t] || 0) + 2.5; }
  if (s.testing && !(s["ai-coding"] || /agent|claude|codex|ai\b|llm/i.test(text))) s.testing *= 0.3;
  if ((s["ai-news"] || 0) > 0 && (s["ai-coding"] || 0) >= 4) s["ai-news"] *= 0.6;
  return s;
}
function tagAssign(text, author) {
  const s = tagScore(text, author);
  // most_common(): stable by insertion order for ties, like Python's Counter
  const ranked = Object.entries(s).filter(([, v]) => v >= 2).sort((a, b) => b[1] - a[1]);
  if (!ranked.length) return { tags: ["other"], src: "unclear" };
  const top = ranked[0][1];
  const tags = ranked.filter(([, v]) => v >= Math.max(2, top * 0.5)).map(([k]) => k).filter(k => TAG_IDS.includes(k)).slice(0, 3);
  return { tags: tags.length ? tags : ["other"], src: "rules" };
}
function videoTagText(v) {
  const desc = (v.description || "").replace(/https?:\/\/\S+/g, " ").slice(0, 1500);
  return [v.title || "", desc, (v.yt_tags || []).join(" ")].join(" \n ");
}
function tagVideo(v) { return tagAssign(videoTagText(v), v.channel_handle ? v.channel_handle.replace(/^@/, "") : null); }

// ---------- crypto ----------
const enc = new TextEncoder(), dec = new TextDecoder();
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function aesKey(env) {
  if (!env.TOKEN_KEY) throw new Error("TOKEN_KEY secret is not set");
  const raw = b64url(env.TOKEN_KEY.trim());
  if (raw.length !== 32) throw new Error("TOKEN_KEY must be 32 random bytes, base64");
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}
async function seal(env, text) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await aesKey(env), enc.encode(text));
  return "v1." + b64u(iv) + "." + b64u(ct);
}
async function unseal(env, s) {
  const [v, iv, ct] = String(s || "").split(".");
  if (v !== "v1") throw new Error("bad sealed value");
  return dec.decode(await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64url(iv) }, await aesKey(env), b64url(ct)));
}

// ---------- D1 helpers ----------
async function kv(env, k) { return env.DB.prepare("SELECT v FROM meta WHERE k=?1").bind(k).first("v"); }
async function kvSet(env, k, v) { await env.DB.prepare("INSERT INTO meta(k,v) VALUES(?1,?2) ON CONFLICT(k) DO UPDATE SET v=excluded.v").bind(k, v).run(); }
async function bumpYtVersion(env) {
  await env.DB.prepare("INSERT INTO meta(k,v) VALUES('yt_version', ?1) ON CONFLICT(k) DO UPDATE SET v = CAST(MAX(CAST(v AS INTEGER) + 1, CAST(?1 AS INTEGER)) AS TEXT)")
    .bind(String(Math.floor(Date.now() / 1000))).run();
}

// ---------- OAuth ----------
function redirectUri(url) { return url.origin + "/oauth/youtube/callback"; }
const STATE_COOKIE = "yt_oauth_state";

async function oauthStart(req, env, url) {
  if (!env.GOOGLE_CLIENT_ID || !env.GOOGLE_CLIENT_SECRET || !env.TOKEN_KEY) return new Response("YouTube is not configured: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and TOKEN_KEY secrets are required.", { status: 503, headers: { "Content-Type": "text/plain", ...SEC_HEADERS } });
  const state = b64u(crypto.getRandomValues(new Uint8Array(24)));
  const p = new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, redirect_uri: redirectUri(url), response_type: "code", scope: YT_SCOPE, access_type: "offline", prompt: "consent", include_granted_scopes: "false", state });
  const secure = url.protocol === "https:" ? "; Secure" : "";
  return new Response(null, { status: 302, headers: { Location: ytCfg(env).authUrl + "?" + p, "Set-Cookie": `${STATE_COOKIE}=${state}; Path=/oauth/youtube; HttpOnly; SameSite=Lax; Max-Age=600${secure}`, "Cache-Control": "no-store", ...SEC_HEADERS } });
}

function htmlMsg(title, msg, status = 200, extra = {}) {
  const body = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><body style="font:16px/1.5 system-ui;max-width:560px;margin:60px auto;padding:0 20px"><h2>${title}</h2><p>${msg}</p><p><a href="/#src=yt">Back to Library</a></p>`;
  return new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", ...SEC_HEADERS, ...extra } });
}

async function oauthCallback(req, env, url) {
  const clear = { "Set-Cookie": `${STATE_COOKIE}=; Path=/oauth/youtube; HttpOnly; SameSite=Lax; Max-Age=0` };
  const err = url.searchParams.get("error");
  if (err) return htmlMsg("YouTube not connected", "Google returned: " + err.replace(/[^\w.-]/g, "") + ".", 400, clear);
  const state = url.searchParams.get("state") || "", code = url.searchParams.get("code") || "";
  const cookie = getCookie(req, STATE_COOKIE);
  if (!cookie || !state || cookie !== state) return htmlMsg("YouTube not connected", "The sign-in link expired or didn't start here. Click Connect YouTube again.", 400, clear);
  const cfg = ytCfg(env);
  const r = await fetch(cfg.tokenUrl, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ code, client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, redirect_uri: redirectUri(url), grant_type: "authorization_code" }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) return htmlMsg("YouTube not connected", "Token exchange failed (" + String(j.error || r.status).replace(/[^\w.-]/g, "") + ").", 502, clear);
  if (!j.refresh_token) return htmlMsg("YouTube not connected", "Google didn't return a refresh token. Remove the app at myaccount.google.com/permissions and connect again.", 502, clear);
  const scopes = String(j.scope || "").split(/\s+/);
  if (!scopes.includes(YT_SCOPE)) return htmlMsg("YouTube not connected", "Read access to YouTube wasn't granted. Connect again and tick the YouTube box.", 400, clear);
  // Which channel did he authorize? (1 quota unit)
  let chTitle = "", chId = "";
  try {
    const c = await fetch(cfg.api + "/channels?part=snippet&mine=true", { headers: { Authorization: "Bearer " + j.access_token } }).then(x => x.json());
    if (c.items && c.items[0]) { chId = c.items[0].id; chTitle = c.items[0].snippet.title; }
  } catch {}
  const now = new Date().toISOString();
  await env.DB.batch([
    env.DB.prepare("INSERT INTO yt_oauth(k,v) VALUES('refresh_token',?1) ON CONFLICT(k) DO UPDATE SET v=excluded.v").bind(await seal(env, j.refresh_token)),
    env.DB.prepare("INSERT INTO yt_oauth(k,v) VALUES('access_token',?1) ON CONFLICT(k) DO UPDATE SET v=excluded.v").bind(await seal(env, JSON.stringify({ t: j.access_token, exp: Date.now() + (j.expires_in || 3600) * 1000 - 60000 }))),
    env.DB.prepare("INSERT INTO yt_oauth(k,v) VALUES('connected',?1) ON CONFLICT(k) DO UPDATE SET v=excluded.v").bind(JSON.stringify({ at: now, channel_id: chId, channel_title: chTitle })),
  ]);
  await kvSet(env, "yt_state", "");   // start a fresh sync cycle at the next cron run
  return htmlMsg("YouTube connected", `Connected${chTitle ? " as <b>" + chTitle.replace(/[<>&"]/g, "") + "</b>" : ""}. The first sync runs in the background over the next hour or so (every 10 minutes, in small batches).`, 200, clear);
}

class YtAuthError extends Error {}
async function accessToken(env, ctx) {
  const row = await env.DB.prepare("SELECT v FROM yt_oauth WHERE k='access_token'").first("v");
  if (row) { try { const a = JSON.parse(await unseal(env, row)); if (a.exp > Date.now()) return a.t; } catch {} }
  const rt = await env.DB.prepare("SELECT v FROM yt_oauth WHERE k='refresh_token'").first("v");
  if (!rt) throw new YtAuthError("not connected");
  ctx.used++;
  const r = await fetch(ytCfg(env).tokenUrl, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, refresh_token: await unseal(env, rt), grant_type: "refresh_token" }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new YtAuthError("refresh failed: " + (j.error || r.status) + (j.error === "invalid_grant" ? " (reconnect YouTube)" : ""));
  await env.DB.prepare("INSERT INTO yt_oauth(k,v) VALUES('access_token',?1) ON CONFLICT(k) DO UPDATE SET v=excluded.v").bind(await seal(env, JSON.stringify({ t: j.access_token, exp: Date.now() + (j.expires_in || 3600) * 1000 - 60000 }))).run();
  return j.access_token;
}

// ---------- sync ----------
function isoDur(d) { const m = /^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(d || ""); if (!m) return null; return ((+m[1] || 0) * 86400) + ((+m[2] || 0) * 3600) + ((+m[3] || 0) * 60) + (+m[4] || 0); }
function bestThumb(t) { t = t || {}; return (t.medium || t.high || t.default || t.standard || {}).url || null; }

async function api(env, ctx, path, params) {
  if (ctx.used >= ctx.budget) throw Object.assign(new Error("budget"), { budget: true });
  const tok = await accessToken(env, ctx);
  if (ctx.used >= ctx.budget) throw Object.assign(new Error("budget"), { budget: true });
  ctx.used++; ctx.calls++;
  const r = await fetch(ytCfg(env).api + path + "?" + new URLSearchParams(params), { headers: { Authorization: "Bearer " + tok } });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { await env.DB.prepare("DELETE FROM yt_oauth WHERE k='access_token'").run(); throw new YtAuthError("401 from YouTube"); }
  if (!r.ok) { const reason = j.error && j.error.errors && j.error.errors[0] && j.error.errors[0].reason; const e = new Error(`${path} ${r.status} ${reason || ""}`.trim()); e.status = r.status; e.reason = reason; throw e; }
  return j;
}

// Insert stub rows for videos seen in a list; add the source to existing ones.
async function addVideos(env, rows, source) {
  if (!rows.length) return 0;
  const ids = rows.map(r => r.id);
  const known = new Map();
  for (let i = 0; i < ids.length; i += 90) {
    const chunk = ids.slice(i, i + 90);
    const { results } = await env.DB.prepare(`SELECT id, sources FROM videos WHERE id IN (${chunk.map((_, j) => "?" + (j + 1)).join(",")})`).bind(...chunk).all();
    results.forEach(r => known.set(r.id, JSON.parse(r.sources || "[]")));
  }
  const now = new Date().toISOString(); const st = []; let added = 0;
  for (const r of rows) {
    if (known.has(r.id)) {
      const s = known.get(r.id);
      if (!s.includes(source)) { s.push(source); st.push(env.DB.prepare("UPDATE videos SET sources=?2" + (source === "like" ? ", liked_at=COALESCE(liked_at, ?3)" : "") + " WHERE id=?1").bind(...(source === "like" ? [r.id, JSON.stringify(s), r.at || now] : [r.id, JSON.stringify(s)]))); }
    } else {
      added++; known.set(r.id, [source]);
      st.push(env.DB.prepare("INSERT INTO videos(id, channel_id, channel_title, title, published_at, thumb, sources, liked_at, added_at, needs_details) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,1)")
        .bind(r.id, r.channel_id || null, r.channel_title || null, r.title || null, r.published_at || null, r.thumb || null, JSON.stringify([source]), source === "like" ? (r.at || now) : null, now));
    }
  }
  for (let i = 0; i < st.length; i += 50) await env.DB.batch(st.slice(i, i + 50));
  return added;
}
function itemRows(j) {
  return (j.items || []).filter(it => it.contentDetails && it.contentDetails.videoId).map(it => ({
    id: it.contentDetails.videoId, at: it.snippet && it.snippet.publishedAt,
    published_at: it.contentDetails.videoPublishedAt || null, title: it.snippet && it.snippet.title,
    channel_id: it.snippet && it.snippet.videoOwnerChannelId, channel_title: it.snippet && it.snippet.videoOwnerChannelTitle,
    thumb: it.snippet && bestThumb(it.snippet.thumbnails),
  }));
}

const PHASES = ["subs", "uploads", "likes", "playlists", "plitems", "details", "done"];

async function runSync(env, opts = {}) {
  const ctx = { used: 0, calls: 0, budget: opts.budget || ytCfg(env).budget, added: 0, detailed: 0, notes: [] };
  if (!env.TOKEN_KEY || !env.GOOGLE_CLIENT_ID) return { skipped: "not configured" };
  const connected = await env.DB.prepare("SELECT 1 AS x FROM yt_oauth WHERE k='refresh_token'").first("x");
  if (!connected) return { skipped: "not connected" };
  const today = new Date().toISOString().slice(0, 10);
  let s = {}; try { s = JSON.parse((await kv(env, "yt_state")) || "{}"); } catch {}
  if (s.day !== today) {
    if (s.day && s.phase !== "done") ctx.notes.push(`previous cycle ${s.day} ended in phase ${s.phase}`);
    s = { day: today, phase: "subs", tok: null, pages: 0 };
    // live/upcoming videos: re-fetch details once a day until they have a real duration
    await env.DB.prepare("UPDATE videos SET needs_details=1 WHERE live_state IN ('live','upcoming')").run();
  }
  if (s.phase === "done") return { done: true, day: today };
  const started = Date.now(); let changed = false, error = null;
  try {
    while (s.phase !== "done") {
      if (s.phase === "subs") {
        const j = await api(env, ctx, "/subscriptions", { part: "snippet", mine: "true", maxResults: "50", order: "alphabetical", ...(s.tok ? { pageToken: s.tok } : {}) });
        const st = (j.items || []).map(it => { const sn = it.snippet || {}; const cid = sn.resourceId && sn.resourceId.channelId; return cid && env.DB.prepare("INSERT INTO yt_channels(id,title,thumb,uploads_playlist,subscribed,seen_day) VALUES(?1,?2,?3,?4,1,?5) ON CONFLICT(id) DO UPDATE SET title=excluded.title, thumb=excluded.thumb, subscribed=1, seen_day=excluded.seen_day").bind(cid, sn.title || "", bestThumb(sn.thumbnails), "UU" + cid.slice(2), today); }).filter(Boolean);
        if (st.length) await env.DB.batch(st);
        if (j.nextPageToken) { s.tok = j.nextPageToken; continue; }
        // Unsubscribed channels keep their videos; they're just flagged.
        await env.DB.prepare("UPDATE yt_channels SET subscribed=0 WHERE seen_day IS NOT ?1 AND subscribed=1").bind(today).run();
        s.phase = "uploads"; s.tok = null;
      } else if (s.phase === "uploads") {
        const ch = await env.DB.prepare("SELECT id, uploads_playlist, checked_day, last_video_id FROM yt_channels WHERE subscribed=1 AND (checked_day IS NULL OR checked_day <> ?1) ORDER BY checked_day IS NOT NULL, checked_day LIMIT 1").bind(today).first();
        if (!ch) { s.phase = "likes"; s.tok = null; s.pages = 0; continue; }
        let rows = [];
        try {
          const j = await api(env, ctx, "/playlistItems", { part: "snippet,contentDetails", playlistId: ch.uploads_playlist, maxResults: "10" });
          rows = itemRows(j);
        } catch (e) { if (e.budget) throw e; if (e.status !== 404) throw e; ctx.notes.push("uploads 404 for " + ch.id); }
        // first time: last 10 uploads; later: only what's newer than the last seen video (max 10/day)
        if (ch.last_video_id) { const k = rows.findIndex(r => r.id === ch.last_video_id); if (k >= 0) rows = rows.slice(0, k); }
        const a = await addVideos(env, rows, "sub"); ctx.added += a; if (a) changed = true;
        const newest = rows.length ? rows[0].id : ch.last_video_id;
        await env.DB.prepare("UPDATE yt_channels SET checked_day=?2, last_video_id=?3 WHERE id=?1").bind(ch.id, today, newest || null).run();
      } else if (s.phase === "likes") {
        const full = (await kv(env, "yt_likes_complete")) !== "1";
        const j = await api(env, ctx, "/playlistItems", { part: "snippet,contentDetails", playlistId: "LL", maxResults: "50", ...(s.tok ? { pageToken: s.tok } : {}) });
        const rows = itemRows(j);
        const ids = rows.map(r => r.id);
        let anyKnown = false;
        if (ids.length) { const r = await env.DB.prepare(`SELECT COUNT(*) AS n FROM videos WHERE sources LIKE '%"like"%' AND id IN (${ids.map((_, i) => "?" + (i + 1)).join(",")})`).bind(...ids).first("n"); anyKnown = r > 0; }
        const a = await addVideos(env, rows, "like"); ctx.added += a; if (a) changed = true;
        if (j.nextPageToken && (full || !anyKnown)) { s.tok = j.nextPageToken; continue; }
        if (full) await kvSet(env, "yt_likes_complete", "1");
        s.phase = "playlists"; s.tok = null;
      } else if (s.phase === "playlists") {
        const j = await api(env, ctx, "/playlists", { part: "snippet,contentDetails", mine: "true", maxResults: "50", ...(s.tok ? { pageToken: s.tok } : {}) });
        const st = (j.items || []).map(p => env.DB.prepare("INSERT INTO yt_playlists(id,title,item_count,etag,dirty,seen_day) VALUES(?1,?2,?3,?4,1,?5) ON CONFLICT(id) DO UPDATE SET title=excluded.title, item_count=excluded.item_count, dirty=CASE WHEN yt_playlists.etag IS NOT excluded.etag THEN 1 ELSE yt_playlists.dirty END, etag=excluded.etag, seen_day=excluded.seen_day").bind(p.id, p.snippet.title, p.contentDetails.itemCount || 0, p.etag, today));
        if (st.length) await env.DB.batch(st);
        if (j.nextPageToken) { s.tok = j.nextPageToken; continue; }
        s.phase = "plitems"; s.tok = null;
      } else if (s.phase === "plitems") {
        const pl = s.pl ? { id: s.pl } : await env.DB.prepare("SELECT id FROM yt_playlists WHERE dirty=1 AND seen_day=?1 LIMIT 1").bind(today).first();
        if (!pl) { s.phase = "details"; s.pl = null; continue; }
        s.pl = pl.id;
        let j;
        try { j = await api(env, ctx, "/playlistItems", { part: "snippet,contentDetails", playlistId: pl.id, maxResults: "50", ...(s.tok ? { pageToken: s.tok } : {}) }); }
        catch (e) { if (e.budget) throw e; if (e.status !== 404 && e.status !== 403) throw e; j = {}; ctx.notes.push("playlist " + pl.id + " " + e.status); }
        const a = await addVideos(env, itemRows(j), "pl:" + pl.id); ctx.added += a; if (a) changed = true;
        if (j.nextPageToken) { s.tok = j.nextPageToken; continue; }
        await env.DB.prepare("UPDATE yt_playlists SET dirty=0 WHERE id=?1").bind(pl.id).run();
        s.pl = null; s.tok = null;
      } else if (s.phase === "details") {
        const { results } = await env.DB.prepare("SELECT id FROM videos WHERE needs_details=1 LIMIT 50").all();
        if (!results.length) { s.phase = "done"; continue; }
        const ids = results.map(r => r.id);
        const j = await api(env, ctx, "/videos", { part: "snippet,contentDetails,statistics,player,liveStreamingDetails", id: ids.join(","), maxWidth: "320", maxResults: "50" });
        const got = new Map((j.items || []).map(v => [v.id, v]));
        const handles = new Map();
        const st = [];
        for (const id of ids) {
          const v = got.get(id);
          if (!v) { st.push(env.DB.prepare("UPDATE videos SET needs_details=0, unavailable=1 WHERE id=?1").bind(id)); continue; }
          const sn = v.snippet || {}, cd = v.contentDetails || {}, sx = v.statistics || {}, pl = v.player || {};
          const dur = isoDur(cd.duration);
          const live = sn.liveBroadcastContent && sn.liveBroadcastContent !== "none" ? sn.liveBroadcastContent : (v.liveStreamingDetails ? "was_live" : null);
          const w = +pl.embedWidth || 0, h = +pl.embedHeight || 0;
          // Shorts: the API has no flag. Vertical player and <= 3 min, or <= 60 s with #shorts.
          const tagsTxt = ((sn.title || "") + " " + (sn.description || "")).toLowerCase();
          const isShort = dur != null && dur > 0 && dur <= 180 && ((h > w && w > 0) || (dur <= 60 && tagsTxt.includes("#short")));
          const row = { title: sn.title || "", description: sn.description || "", yt_tags: sn.tags || [], channel_handle: handles.get(sn.channelId) };
          const t = tagVideo(row);
          st.push(env.DB.prepare(`UPDATE videos SET channel_id=?2, channel_title=?3, title=?4, description=?5, yt_tags=?6, published_at=?7, duration_s=?8, is_short=?9, live_state=?10,
              thumb=?11, views=?12, lang=?13, tags=?14, primary_tag=?15, tag_source=?16, needs_details=0, unavailable=0 WHERE id=?1`)
            .bind(id, sn.channelId || null, sn.channelTitle || null, sn.title || null, (sn.description || "").slice(0, 5000), JSON.stringify((sn.tags || []).slice(0, 30)), sn.publishedAt || null, dur, isShort ? 1 : 0, live,
              bestThumb(sn.thumbnails), sx.viewCount != null ? +sx.viewCount : null, sn.defaultAudioLanguage || sn.defaultLanguage || null, JSON.stringify(t.tags), t.tags[0], t.src));
        }
        await env.DB.batch(st); ctx.detailed += ids.length; changed = true;
      }
    }
  } catch (e) {
    if (!e.budget) error = String(e.message || e);
  }
  await kvSet(env, "yt_state", JSON.stringify(s));
  if (changed) await bumpYtVersion(env);
  const status = { at: new Date().toISOString(), day: s.day, phase: s.phase, calls: ctx.calls, subrequests: ctx.used, added: ctx.added, detailed: ctx.detailed, ms: Date.now() - started, error, notes: ctx.notes };
  await kvSet(env, "yt_last_run", JSON.stringify(status));
  if (error) await kvSet(env, "yt_last_error", JSON.stringify({ at: status.at, error }));
  // quota estimate per Pacific day (every call we make costs 1 unit)
  const pday = new Date(Date.now() - 7 * 3600e3).toISOString().slice(0, 10);
  let q = {}; try { q = JSON.parse((await kv(env, "yt_quota")) || "{}"); } catch {}
  if (q.day !== pday) q = { day: pday, units: 0 };
  q.units += ctx.calls; await kvSet(env, "yt_quota", JSON.stringify(q));
  return status;
}

// ---------- HTTP API ----------
function videoRow(r) {
  return { i: r.id, c: r.channel_id, n: r.channel_title, a: r.ch_thumb, t: r.title, x: (r.description || "").slice(0, 400), d: r.published_at, s: r.added_at, lk: r.liked_at,
    du: r.duration_s, sh: r.is_short ? 1 : 0, lv: r.live_state, th: r.thumb, v: r.views, g: JSON.parse(r.tags || '["other"]'), so: JSON.parse(r.sources || "[]"),
    st: r.starred_at || null, us: r.subscribed === 0 ? 1 : 0 };
}
async function apiVideos(req, env, ctx) {
  const ver = (await kv(env, "yt_version")) || "0";
  const etag = `"y${ver}"`;
  if (req.headers.get("If-None-Match") === etag) return new Response(null, { status: 304, headers: { ETag: etag, ...SEC_HEADERS } });
  const { results } = await env.DB.prepare(`SELECT v.*, c.thumb AS ch_thumb, c.subscribed, s.starred_at FROM videos v LEFT JOIN yt_channels c ON c.id=v.channel_id LEFT JOIN yt_stars s ON s.id=v.id
      WHERE v.needs_details=0 AND v.unavailable=0 ORDER BY v.added_at DESC, v.published_at DESC`).all();
  const { results: pls } = await env.DB.prepare("SELECT id, title FROM yt_playlists ORDER BY title").all();
  const body = JSON.stringify({ version: ver, items: results.map(videoRow), playlists: pls });
  return new Response(body, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "private, no-cache", ETag: etag, ...SEC_HEADERS } });
}
async function apiYtStatus(env) {
  const parse = async k => { try { return JSON.parse((await kv(env, k)) || "null"); } catch { return null; } };
  const conn = await env.DB.prepare("SELECT v FROM yt_oauth WHERE k='connected'").first("v");
  const hasRt = await env.DB.prepare("SELECT 1 AS x FROM yt_oauth WHERE k='refresh_token'").first("x");
  const counts = await env.DB.prepare("SELECT (SELECT COUNT(*) FROM videos WHERE needs_details=0 AND unavailable=0) AS videos, (SELECT COUNT(*) FROM videos WHERE needs_details=1) AS pending, (SELECT COUNT(*) FROM yt_channels WHERE subscribed=1) AS channels").first();
  return jres({ configured: !!(env.TOKEN_KEY && env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET), connected: !!hasRt, account: conn ? JSON.parse(conn) : null,
    state: await parse("yt_state"), last_run: await parse("yt_last_run"), last_error: await parse("yt_last_error"), quota: await parse("yt_quota"), ...counts });
}
async function ytWrite(req, env, url, ctx) {
  if (!sameOrigin(req, url)) return jres({ error: "cross-origin or non-JSON request refused" }, 403);
  let body; try { body = await req.json(); } catch { return jres({ error: "invalid JSON" }, 400); }
  if (url.pathname === "/api/yt/sync") { const r = await runSync(env); return jres(r); }
  if (url.pathname === "/api/yt/disconnect") { await env.DB.prepare("DELETE FROM yt_oauth").run(); await kvSet(env, "yt_state", ""); return jres({ ok: true }); }
  const id = body && String(body.id || "");
  if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return jres({ error: "invalid video id" }, 400);
  const exists = await env.DB.prepare("SELECT 1 AS x FROM videos WHERE id=?1").bind(id).first("x");
  if (!exists) return jres({ error: "unknown video" }, 404);
  if (url.pathname === "/api/star") await env.DB.prepare("INSERT INTO yt_stars(id, starred_at) VALUES(?1, ?2) ON CONFLICT(id) DO NOTHING").bind(id, new Date().toISOString()).run();
  else await env.DB.prepare("DELETE FROM yt_stars WHERE id=?1").bind(id).run();
  await bumpYtVersion(env);
  return jres({ ok: true, id, starred: url.pathname === "/api/star" });
}

const PRIVACY_HTML = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Privacy – Library</title>
<body style="font:16px/1.6 system-ui,-apple-system,sans-serif;max-width:640px;margin:48px auto;padding:0 20px;color:#222">
<h1>Privacy</h1>
<p><b>Library</b> (x-bookmarks.simons.workers.dev) is a personal, single-user app. Its only user is its owner, Simon. It is not offered to anyone else.</p>
<h2>YouTube data</h2>
<p>With the owner's consent, the app uses the YouTube Data API with <b>read-only</b> access (<code>youtube.readonly</code>) to read his subscriptions, liked videos and playlists, and public details of those videos (title, description, duration, thumbnail, view count). It never posts, rates, comments, subscribes or changes anything on YouTube.</p>
<h2>Where it is stored</h2>
<p>The data is stored in the owner's own Cloudflare account (a Cloudflare D1 database). The Google refresh token is stored encrypted. Access to the app is restricted to the owner's account through Cloudflare Access.</p>
<h2>Sharing</h2>
<p>The data is not sold, shared with, or disclosed to anyone, and is not used for advertising. It is only shown back to the owner.</p>
<h2>Removing access</h2>
<p>Access can be revoked at any time at <a href="https://myaccount.google.com/permissions">myaccount.google.com/permissions</a>; the app's "Disconnect" button also deletes the stored tokens. Use of YouTube data is subject to the <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a> and the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>.</p>
<p>Contact: simonhimself@gmail.com</p>
<p style="color:#777;font-size:14px">Last updated 14 October 2026.</p>
</body></html>`;
