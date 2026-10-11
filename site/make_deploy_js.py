"""Build dist/deploy.js: an async arrow function for the Cloudflare connector `execute` tool that uploads
dist/worker.js as the x-bookmarks Worker (module syntax, D1 binding, Access AUD var), keeps the workers.dev
route on and preview URLs off. Run build.py first."""
import json,os
H=os.path.dirname(os.path.abspath(__file__))
code=open(f'{H}/dist/worker.js').read()
ACCOUNT='2423947c3898625c52d1d37070dffd03'
meta={"main_module":"worker.js","compatibility_date":"2026-09-01",
      "bindings":[{"type":"d1","name":"DB","id":"14bf4a21-7cb1-403f-b558-f709ed307260"},
                  {"type":"plain_text","name":"ACCESS_AUD","text":"b0c59ac7f696d3899b34faf887dac46f4b4087950da8b516fa7fa45df5460b6a"}]}
js=f"""async () => {{
const code = {json.dumps(code)};
const metadata = {json.dumps(meta)};
const b = 'XBM' + Date.now();
const body = ['--'+b, 'Content-Disposition: form-data; name="metadata"', 'Content-Type: application/json', '', JSON.stringify(metadata),
  '--'+b, 'Content-Disposition: form-data; name="worker.js"; filename="worker.js"', 'Content-Type: application/javascript+module', '', code, '--'+b+'--', ''].join('\\r\\n');
const up = await cloudflare.request({{method:'PUT', path:'/accounts/{ACCOUNT}/workers/scripts/x-bookmarks', body, contentType:'multipart/form-data; boundary='+b, rawBody:true}});
if (!up.success) return {{step:'upload', errors: up.errors}};
const sub = await cloudflare.request({{method:'POST', path:'/accounts/{ACCOUNT}/workers/scripts/x-bookmarks/subdomain', body:{{enabled:true, previews_enabled:false}}}});
return {{uploaded: true, etag: up.result && up.result.etag, subdomain: sub.success ? sub.result : sub.errors}};
}}"""
open(f'{H}/dist/deploy.js','w').write(js)
print('dist/deploy.js',len(js))
