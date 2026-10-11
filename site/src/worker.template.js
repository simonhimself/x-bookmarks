// x-bookmarks Worker: serves Simon's private X bookmarks browser.
// Read-only: there are NO write endpoints. Data is written to D1 from the box (sync/).
// Protected by Cloudflare Access; the Worker also verifies the Access JWT itself (defense in depth).
const HTML = __HTML__;
const TAXONOMY = __TAXONOMY__;
const TEAM = "https://simonhimself.cloudflareaccess.com";
const ALLOWED_EMAILS = ["simonhimself@gmail.com"];

let jwksCache = { keys: null, at: 0 };
async function getKeys() {
  if (jwksCache.keys && Date.now() - jwksCache.at < 3600_000) return jwksCache.keys;
  const r = await fetch(`${TEAM}/cdn-cgi/access/certs`);
  const j = await r.json();
  jwksCache = { keys: j.keys || [], at: Date.now() };
  return jwksCache.keys;
}
function b64url(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; return Uint8Array.from(atob(s), c => c.charCodeAt(0)); }
function getCookie(req, name) {
  const c = req.headers.get("Cookie") || "";
  for (const part of c.split(/;\s*/)) { const i = part.indexOf("="); if (i > 0 && part.slice(0, i) === name) return part.slice(i + 1); }
  return null;
}
async function verifyAccess(req, env) {
  const token = req.headers.get("Cf-Access-Jwt-Assertion") || getCookie(req, "CF_Authorization");
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  let header, payload;
  try { header = JSON.parse(new TextDecoder().decode(b64url(parts[0]))); payload = JSON.parse(new TextDecoder().decode(b64url(parts[1]))); } catch { return null; }
  if (header.alg !== "RS256") return null;
  const keys = await getKeys();
  const jwk = keys.find(k => k.kid === header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(parts[2]), new TextEncoder().encode(parts[0] + "." + parts[1]));
  if (!ok) return null;
  const now = Math.floor(Date.now() / 1000);
  const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!aud.includes(env.ACCESS_AUD)) return null;
  if (payload.iss !== TEAM) return null;
  if (!payload.exp || payload.exp < now) return null;
  if (!payload.email || !ALLOWED_EMAILS.includes(String(payload.email).toLowerCase())) return null;
  return payload;
}

const SEC_HEADERS = {
  "Content-Security-Policy": "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src https://pbs.twimg.com https://abs.twimg.com data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-Robots-Tag": "noindex, nofollow",
};

function rowToItem(r) {
  return {
    i: r.id, s: r.seq, d: r.created_at, u: r.author_username, n: r.author_name, a: r.author_img,
    t: r.text, l: JSON.parse(r.ext_links || "[]"), m: JSON.parse(r.media || "[]"),
    g: JSON.parse(r.tags || "[]"), p: r.primary_tag, q: r.quoted ? JSON.parse(r.quoted) : null,
    r: r.replied ? JSON.parse(r.replied) : null, k: r.likes || 0,
  };
}

async function bookmarks(req, env, ctx) {
  const ver = (await env.DB.prepare("SELECT v FROM meta WHERE k='data_version'").first("v")) || "0";
  const etag = `"v${ver}"`;
  if (req.headers.get("If-None-Match") === etag) return new Response(null, { status: 304, headers: { ETag: etag, ...SEC_HEADERS } });
  const cache = caches.default;
  const ckey = new Request(`https://cache.x-bookmarks.internal/bookmarks/${ver}`);
  let body = null;
  const hit = await cache.match(ckey);
  if (hit) body = await hit.text();
  if (!body) {
    const { results } = await env.DB.prepare("SELECT * FROM bookmarks ORDER BY seq DESC").all();
    body = JSON.stringify({ version: ver, taxonomy: TAXONOMY, items: results.map(rowToItem) });
    ctx.waitUntil(cache.put(ckey, new Response(body, { headers: { "Cache-Control": "max-age=86400" } })));
  }
  return new Response(body, { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "private, no-cache", ETag: etag, ...SEC_HEADERS } });
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const local = env.ALLOW_LOCAL === "1" && (url.hostname === "localhost" || url.hostname === "127.0.0.1");
    if (!local) {
      const user = await verifyAccess(req, env);
      if (!user) return new Response("Forbidden: sign in through Cloudflare Access.", { status: 403, headers: { "Content-Type": "text/plain", ...SEC_HEADERS } });
    }
    if (req.method !== "GET" && req.method !== "HEAD") return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD", ...SEC_HEADERS } });
    if (url.pathname === "/" || url.pathname === "/index.html")
      return new Response(HTML, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "private, no-cache", ...SEC_HEADERS } });
    if (url.pathname === "/api/bookmarks") return bookmarks(req, env, ctx);
    return new Response("Not found", { status: 404, headers: { "Content-Type": "text/plain", ...SEC_HEADERS } });
  },
};
