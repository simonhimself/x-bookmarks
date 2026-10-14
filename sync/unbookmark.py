#!/usr/bin/env python3
"""Unbookmark on X the posts Simon removed in the app (the D1 `removals` table).

  python3 sync/unbookmark.py pending [--via auto|wrangler|connector|local]
      Writes sync/out/unbookmark-<ts>/pending.txt (one id per line, max 50, oldest first).
      With the connector it writes read_pending.js instead: run it with user-Cloudflare execute
      and pass the result file to `pending --from-result FILE` to get pending.txt.
  python3 sync/unbookmark.py done --ok ID,ID [--failed ID=reason ...] [--via ...]
      Marks ids as unbookmarked (done_at=now) and records failures (attempts+1, last_error);
      failed ids stay pending for the next run.

The routine calls user-X delete_users_bookmark (id=17562615, tweet_id=<id>) for every pending id
between the two steps. `--via local` targets the local wrangler D1 (tests; XBM_D1_PERSIST=<dir> sets --persist-to). Rows in `bookmarks` and bookmarks.json are kept on purpose: they keep the id
"known", so the incremental sync stops at it and never re-adds a removed post.
"""
import json,os,sys,time,argparse,subprocess
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import ROOT,sqlv,connector_js,ACCOUNT,DB_ID
SITE=os.path.join(ROOT,'site')
LIMIT=50
SELECT=f"SELECT id FROM removals WHERE done_at IS NULL ORDER BY removed_at LIMIT {LIMIT};"

def outdir():
    d=os.path.join(ROOT,'sync','out','unbookmark-'+time.strftime('%Y%m%d-%H%M%S'));os.makedirs(d,exist_ok=True);return d

def via(a):
    if a.via!='auto': return a.via
    from sync import wrangler_ok
    return 'wrangler' if wrangler_ok() else 'connector'

def d1(sql,mode):
    """Run SQL with wrangler (remote or --local); return the result rows of the last statement."""
    flag=['--local']+(['--persist-to',os.environ['XBM_D1_PERSIST']] if os.environ.get('XBM_D1_PERSIST') else []) if mode=='local' else ['--remote']
    r=subprocess.run(['npx','wrangler','d1','execute','x-bookmarks',*flag,'--yes','--json','--command',sql],cwd=SITE,capture_output=True,text=True)
    if r.returncode: sys.exit('wrangler d1 execute failed:\n'+r.stderr+r.stdout)
    res=json.loads(r.stdout)
    return res[-1].get('results',[]) if res else []

def write_pending(ids,d):
    f=os.path.join(d,'pending.txt');open(f,'w').write('\n'.join(ids)+('\n' if ids else ''))
    print(json.dumps({'pending':len(ids),'file':f}));return f

def cmd_pending(a):
    d=outdir()
    if a.from_result:
        s=open(a.from_result).read();i=s.find('{');j=json.JSONDecoder().raw_decode(s[i:])[0]
        if not j.get('success'): sys.exit('read failed: '+json.dumps(j.get('errors')))
        return write_pending([str(x) for x in j['ids']],d)
    m=via(a)
    if m in('wrangler','local'): return write_pending([str(r['id']) for r in d1(SELECT,m)],d)
    js=("async () => { const r = await cloudflare.request({method:'POST', path:'/accounts/"+ACCOUNT+"/d1/database/"+DB_ID+"/query', body:{sql:"+json.dumps(SELECT)+"}});\n"
        "return {success: r.success, errors: r.errors, ids: r.success ? r.result[0].results.map(x => x.id) : []}; }")
    f=os.path.join(d,'read_pending.js');open(f,'w').write(js)
    print('RUN_WITH_CONNECTOR (write_to_file=true), then: python3 sync/unbookmark.py pending --from-result <result file>')
    print('  '+f)

def done_sql(ok,failed,now=None):
    now=now or time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    s=[]
    for i in ok: s.append(f"UPDATE removals SET done_at={sqlv(now)}, attempts=attempts+1, last_error=NULL WHERE id={sqlv(i)} AND done_at IS NULL;")
    for i,why in failed: s.append(f"UPDATE removals SET attempts=attempts+1, last_error={sqlv(why[:500])} WHERE id={sqlv(i)} AND done_at IS NULL;")
    return s

def cmd_done(a):
    ok=[x for x in (a.ok or '').split(',') if x]
    failed=[tuple(f.split('=',1)) if '=' in f else (f,'error') for f in a.failed or []]
    for i in ok+[f[0] for f in failed]:
        if not i.isdigit(): sys.exit(f'bad id: {i}')
    stmts=done_sql(ok,failed)
    if not stmts: print('nothing to mark'); return
    d=outdir();open(os.path.join(d,'done.sql'),'w').write('\n'.join(stmts))
    m=via(a)
    if m in('wrangler','local'):
        d1('\n'.join(stmts),m);print(f'marked done: {len(ok)}, failed (still pending): {len(failed)}')
    else:
        f=os.path.join(d,'apply_done.js');open(f,'w').write(connector_js(stmts))
        print('APPLY_WITH_CONNECTOR: run with user-Cloudflare execute {"code": "$file:'+f+'"} and check success=true')

if __name__=='__main__':
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('pending');p.add_argument('--via',choices=['auto','wrangler','connector','local'],default='auto');p.add_argument('--from-result')
    p=sp.add_parser('done');p.add_argument('--ok');p.add_argument('--failed',nargs='*');p.add_argument('--via',choices=['auto','wrangler','connector','local'],default='auto')
    a=ap.parse_args();{'pending':cmd_pending,'done':cmd_done}[a.cmd](a)
