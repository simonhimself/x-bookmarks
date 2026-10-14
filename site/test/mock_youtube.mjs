// Local mock of Google OAuth + the YouTube Data API v3 endpoints the Worker uses. Made-up demo data only.
// Usage: node test/mock_youtube.mjs [port=8789] [channels=60]
import http from "node:http";
const PORT = +(process.argv[2] || 8789), NCH = +(process.argv[3] || 60);
const log = []; // every API call, for assertions
const pick = (a, i) => a[i % a.length];
const TOPICS = [
  ["Claude Code subagents and skills: my full agentic coding workflow", "ai-coding"], ["Building a raised bed vegetable garden from scratch", "home"],
  ["Tesla FSD v14 drive through the Alps", "tesla"], ["How I invest in ETFs: portfolio review 2026", "investing"],
  ["Hiking Switzerland: the most beautiful lake trails", "travel"], ["Docker, Tailscale and a Mac mini home server", "devtools"],
  ["Deep work: how I rebuilt my focus habits", "productivity"], ["Modern kitchen interior tour of a minimalist house", "home"],
  ["New OpenAI and Anthropic model benchmarks explained", "ai-news"], ["Pizza dough recipe: 48 hour cold ferment", "lifestyle"],
  ["Playwright e2e tests written by coding agents", "testing"], ["Startup growth: from 0 to 10k MRR as an indie hacker", "product"],
  ["Ancient Roman engineering: how the aqueducts worked", "curiosities"], ["Strength workouts and mobility for desk workers", "health"],
  ["Best movies of the year: our watchlist", "movies"], ["Midjourney and Veo for cinematic AI video", "ai-creative"],
];
const COLORS = ["#7c3aed", "#b45309", "#dc2626", "#16a34a", "#0d9488", "#475569", "#9333ea", "#a16207", "#2563eb", "#d97706", "#0891b2", "#ea580c", "#4f46e5", "#059669", "#e11d48", "#db2777"];
const svg = (bg, txt, w, h) => "data:image/svg+xml;base64," + Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><defs><linearGradient id="g" x2="1" y2="1"><stop offset="0" stop-color="${bg}"/><stop offset="1" stop-color="#111"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/><text x="50%" y="55%" font-family="sans-serif" font-size="${h / 6}" fill="#fff" text-anchor="middle" opacity=".9">${txt}</text></svg>`).toString("base64");
const CH = Array.from({ length: NCH }, (_, i) => ({ id: "UC" + ("demo" + String(i).padStart(4, "0")).padEnd(22, "x"), title: pick(["Garden Lab", "Agent Workshop", "Alpine Trails", "EV Weekly", "Index Investor", "Homelab Hero", "Focus Notes", "Kitchen Stories", "AI Explained", "Dough Nerd", "Test Pilot", "Indie Founder", "History Bytes", "Mobility Coach", "Film Club", "Prompt Studio"], i) + (i >= 16 ? " " + (Math.floor(i / 16) + 1) : "") }));
const vid = (c, k) => ("v" + String(c).padStart(3, "0") + String(k).padStart(3, "0")).padEnd(11, "_").slice(0, 11);
const VIDEOS = new Map();
const base = Date.parse("2026-10-13T18:00:00Z");
CH.forEach((ch, c) => {
  const n = 12;
  for (let k = 0; k < n; k++) {
    const [t, tag] = pick(TOPICS, c + k * 3);
    const id = vid(c, k);
    const short = (c + k) % 7 === 0;
    const dur = short ? 45 : [312, 754, 1290, 2410, 3920, 545, 1840][(c * 3 + k) % 7];
    VIDEOS.set(id, { id, ch, title: short ? t.split(":")[0] + " #shorts" : t + (k ? " (part " + (k + 1) + ")" : ""), dur, short,
      at: new Date(base - (c * 7 + k * 26) * 3600e3).toISOString(), views: ((c + 1) * 1371 * (k + 3)) % 2400000 + 900, color: pick(COLORS, c + k * 3), tag });
  }
});
const uploads = ch => [...VIDEOS.values()].filter(v => v.ch === ch).sort((a, b) => b.at.localeCompare(a.at));
const LIKES = [...VIDEOS.values()].filter((v, i) => i % 9 === 1).slice(0, 70);
const PLS = [{ id: "PLdemoWatchSoon", title: "Watch soon", items: [...VIDEOS.values()].filter((v, i) => i % 13 === 4) }, { id: "PLdemoGarden", title: "Garden ideas", items: [...VIDEOS.values()].filter(v => v.tag === "home").slice(0, 12) }];
const item = (v, addedAt) => ({ kind: "youtube#playlistItem", snippet: { publishedAt: addedAt || v.at, title: v.title, videoOwnerChannelId: v.ch.id, videoOwnerChannelTitle: v.ch.title, thumbnails: { medium: { url: svg(v.color, "▶", 320, 180) } } }, contentDetails: { videoId: v.id, videoPublishedAt: v.at } });
function page(list, req, size) { const start = +(req.searchParams.get("pageToken") || 0), max = Math.min(+(req.searchParams.get("maxResults") || 5), size || 50); const sl = list.slice(start, start + max); return { items: sl, ...(start + max < list.length ? { nextPageToken: String(start + max) } : {}), pageInfo: { totalResults: list.length } }; }
function send(res, code, obj) { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); }
let tokenN = 0;
http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  let body = ""; req.on("data", d => body += d); req.on("end", () => {
    log.push({ m: req.method, p: u.pathname, q: Object.fromEntries(u.searchParams), auth: req.headers.authorization || null });
    if (u.pathname === "/__log") return send(res, 200, log);
    if (u.pathname === "/auth") { // pretend consent; bounce back with a code
      const to = new URL(u.searchParams.get("redirect_uri")); to.searchParams.set("code", "mockcode"); to.searchParams.set("state", u.searchParams.get("state")); to.searchParams.set("scope", u.searchParams.get("scope"));
      res.writeHead(302, { Location: to.toString() }); return res.end();
    }
    if (u.pathname === "/token") {
      const f = new URLSearchParams(body);
      if (f.get("client_secret") !== "mock-secret") return send(res, 401, { error: "invalid_client" });
      if (f.get("grant_type") === "authorization_code") { if (f.get("code") !== "mockcode") return send(res, 400, { error: "invalid_grant" }); return send(res, 200, { access_token: "at" + (++tokenN), expires_in: 3599, refresh_token: "mock-refresh-token", scope: "https://www.googleapis.com/auth/youtube.readonly", token_type: "Bearer" }); }
      if (f.get("grant_type") === "refresh_token") { if (f.get("refresh_token") !== "mock-refresh-token") return send(res, 400, { error: "invalid_grant" }); return send(res, 200, { access_token: "at" + (++tokenN), expires_in: 3599, scope: "https://www.googleapis.com/auth/youtube.readonly" }); }
      return send(res, 400, { error: "unsupported_grant_type" });
    }
    if (!/^Bearer at\d+$/.test(req.headers.authorization || "")) return send(res, 401, { error: { code: 401, errors: [{ reason: "authError" }] } });
    const p = u.pathname.replace(/^\/yt/, "");
    if (p === "/channels") return send(res, 200, { items: [{ id: "UCsimonDemoChannel000000", snippet: { title: "Simon (demo)" } }] });
    if (p === "/subscriptions") return send(res, 200, page(CH.map(ch => ({ snippet: { title: ch.title, resourceId: { kind: "youtube#channel", channelId: ch.id }, thumbnails: { medium: { url: svg(pick(COLORS, CH.indexOf(ch)), ch.title[0], 88, 88) } } } })), u));
    if (p === "/playlistItems") {
      const pl = u.searchParams.get("playlistId");
      if (pl === "LL") return send(res, 200, page(LIKES.map((v, i) => item(v, new Date(base - i * 5e6).toISOString())), u));
      if (pl.startsWith("UU")) { const ch = CH.find(c => c.id.slice(2) === pl.slice(2)); if (!ch) return send(res, 404, { error: { code: 404, errors: [{ reason: "playlistNotFound" }] } }); return send(res, 200, page(uploads(ch).map(v => item(v)), u)); }
      const P = PLS.find(x => x.id === pl); if (!P) return send(res, 404, { error: { code: 404, errors: [{ reason: "playlistNotFound" }] } });
      return send(res, 200, page(P.items.map(v => item(v)), u));
    }
    if (p === "/playlists") return send(res, 200, page(PLS.map(P => ({ id: P.id, etag: "e" + P.items.length, snippet: { title: P.title }, contentDetails: { itemCount: P.items.length } })), u));
    if (p === "/videos") {
      const ids = (u.searchParams.get("id") || "").split(",");
      return send(res, 200, { items: ids.map(id => VIDEOS.get(id)).filter(Boolean).map(v => ({ id: v.id,
        snippet: { publishedAt: v.at, channelId: v.ch.id, channelTitle: v.ch.title, title: v.title, description: `In this video: ${v.title.toLowerCase()}.\nChapters, links and gear below.\nhttps://example.com/links`, tags: [v.tag], liveBroadcastContent: "none", thumbnails: { medium: { url: svg(v.color, v.title.split(" ").slice(0, 3).join(" ").replace(/[<&>]/g, ""), 320, 180) } } },
        contentDetails: { duration: `PT${Math.floor(v.dur / 3600) ? Math.floor(v.dur / 3600) + "H" : ""}${Math.floor(v.dur % 3600 / 60)}M${v.dur % 60}S` },
        statistics: { viewCount: String(v.views) }, player: v.short ? { embedWidth: "180", embedHeight: "320" } : { embedWidth: "320", embedHeight: "180" } })) });
    }
    send(res, 404, { error: { code: 404, errors: [{ reason: "notFound" }] } });
  });
}).listen(PORT, "127.0.0.1", () => console.log(`mock youtube on :${PORT}, ${NCH} channels, ${VIDEOS.size} videos, ${LIKES.length} likes`));
