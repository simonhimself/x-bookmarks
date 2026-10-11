#!/usr/bin/env python3
"""Incremental sync of new X bookmarks into the x-bookmarks D1 database.

  python3 sync/sync.py plan --pages DIR      # find new posts, list quoted/replied ids still needed
  python3 sync/sync.py run  --pages DIR      # normalize, attach quotes, tag, update bookmarks.json, write + apply SQL
  python3 sync/sync.py push --ids ID,ID      # re-push specific posts (e.g. after fixing tags by hand)

DIR holds get_users_bookmarks response pages saved as p01.json, p02.json, ... (p01 = newest). Files may contain
wrapper text around the JSON; the first {...} object is used. Optional DIR/quoted/*.json|txt hold free
`x.get_posts_by_ids` responses for quoted/replied posts not present in the pages' includes.tweets.
See sync/README.md for the routine contract.
"""
import json,os,sys,glob,re,subprocess,time,argparse
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
sys.path.insert(0,os.path.join(ROOT,'tagging'))
BM=os.path.join(ROOT,'bookmarks.json')

def page_files(d):
    fs=sorted(glob.glob(os.path.join(d,'p*.json')),key=lambda p:int(re.sub(r'\D','',os.path.basename(p)) or 0))
    if not fs: sys.exit(f'no p*.json pages in {d}')
    return fs

def collect_new(pages_dir,known):
    new=[];inc_posts={};inc_users={};inc_media={};hit_known=False
    for f in page_files(pages_dir):
        d=load_json_loose(f)
        posts,users,media,incp=parse_page(d)
        inc_users.update(users);inc_media.update(media);inc_posts.update(incp)
        for p in posts:
            if p['id'] in known: hit_known=True;break
            if p['id'] not in {x['id'] for x in new}: new.append(p)
        if hit_known: break
    return new,inc_posts,inc_users,inc_media,hit_known

def load_quoted_dir(pages_dir):
    Q={}
    for f in glob.glob(os.path.join(pages_dir,'quoted','*')):
        try: d=load_json_loose(f)
        except Exception: continue
        posts,_,_,_=parse_page(d)
        for p in posts: Q[p['id']]=p
        for e in d.get('errors',[]) or []:
            rid=e.get('resource_id') or e.get('value')
            if rid and rid not in Q: Q[rid]={'id':rid,'available':False}
    return Q

def ref_ids(p):
    return [(r['type'],r['id']) for r in p.get('referenced_tweets') or [] if r['type'] in ('quoted','replied_to')]

def cmd_check(a):
    """Exit 0 = STOP (page contains an already-known id, or no next_token); exit 10 = fetch the next page."""
    B=json.load(open(BM));known={o['id'] for o in B}
    d=load_json_loose(a.page)
    ids=[t['id'] for t in d.get('data',[]) or []]
    k=[i for i in ids if i in known]
    nt=(d.get('meta') or {}).get('next_token')
    new=len(ids) if not k else ids.index(k[0])
    print(json.dumps({'posts':len(ids),'new_before_known':new,'known_found':bool(k),'next_token':nt}))
    sys.exit(0 if (k or not nt) else 10)

def cmd_plan(a):
    B=json.load(open(BM));known={o['id'] for o in B}
    new,incp,_,_,hit=collect_new(a.pages,known)
    have=set(incp)|set(load_quoted_dir(a.pages))
    need=sorted({rid for p in new for _,rid in ref_ids(p) if rid not in have})
    print(f'new bookmarks: {len(new)}  reached known id: {hit}')
    if not hit: print('WARNING: no already-known id found in the pages; fetch more pages before running (or the gap stays).')
    out=os.path.join(a.pages,'missing_ref_ids.txt')
    open(out,'w').write('\n'.join(','.join(need[i:i+25]) for i in range(0,len(need),25)))
    print(f'referenced posts still needed: {len(need)} -> {out} (one line = one get_posts_by_ids call of up to 25 ids)')

def cmd_run(a):
    import tag as T
    B=json.load(open(BM));known={o['id'] for o in B}
    new,incp,iu,im,hit=collect_new(a.pages,known)
    if not new: print('nothing new'); return
    if not hit and not a.allow_gap: sys.exit('no already-known id found in the pages: fetch more pages, or pass --allow-gap')
    # referenced posts: includes.tweets from the pages first, then the quoted/ folder
    refs={}
    for pid,t in incp.items(): refs[pid]=norm_post(t,iu,im)|{'available':True}
    for pid,p in load_quoted_dir(a.pages).items():
        if pid not in refs or not refs[pid].get('available'): refs[pid]=p if 'available' in p else p|{'available':True}
    maxseq=max(o.get('seq',0) for o in B)
    n=len(new)
    for i,p in enumerate(new):
        p['seq']=maxseq+n-i     # first post on page 1 = most recently bookmarked = highest seq
        for typ,rid in ref_ids(p):
            key='quoted' if typ=='quoted' else 'replied_to'
            r=refs.get(rid)
            p[key]=(r|{'available':True}) if r and r.get('available',True) and r.get('text') is not None else {'id':rid,'url':f'https://x.com/i/status/{rid}','available':False}
        p['tags']=None
    priors=json.load(open(T.PRIORS_P)) if os.path.exists(T.PRIORS_P) else {}
    unclear=[]
    for p in new:
        tags,src=T.assign(p,priors); p['tags']=tags;p['primary_tag']=tags[0];p['tag_source']=src
        if src=='unclear': unclear.append(p)
    B=new+B
    top=max(o['seq'] for o in B)
    for o in B: o['bookmark_rank']=top-o['seq']+1
    json.dump(B,open(BM,'w'),ensure_ascii=False,indent=1)
    print(f'added {n} new bookmarks (seq {maxseq+1}-{maxseq+n}); unclear (tagged other): {len(unclear)}')
    if unclear:
        uf=os.path.join(a.pages,'unclear.txt')
        open(uf,'w').write('\n'.join(f"{p['id']}\t{(p['media'][0].get('preview_image_url') or p['media'][0].get('url')) if p['media'] else ''}\t{p['text'][:120]!r}" for p in unclear))
        print(f'  review list: {uf}  (look at the images, add tags to tagging/manual_tags.json, then: sync.py push --ids ...)')
    apply([to_row(p,p['seq']) for p in new],a)

def cmd_push(a):
    import tag as T
    B=json.load(open(BM));ids=set(a.ids.split(','))
    rows=[]
    for o in B:
        if o['id'] in ids:
            tags,src=T.assign(o,{}) if o['id'] in T.MANUAL else (o['tags'],o.get('tag_source'))
            o['tags']=tags;o['primary_tag']=tags[0];o['tag_source']=src
            rows.append(to_row(o,o['seq']))
    json.dump(B,open(BM,'w'),ensure_ascii=False,indent=1)
    print(f'pushing {len(rows)} posts'); apply(rows,a)

def wrangler_ok():
    try:
        r=subprocess.run(['npx','wrangler','whoami'],cwd=os.path.join(ROOT,'site'),capture_output=True,text=True,timeout=60)
        return 'not authenticated' not in (r.stdout+r.stderr).lower() and r.returncode==0
    except Exception: return False

def apply(rows,a):
    stmts=[upsert_sql(r) for r in rows]
    stmts.append(f"INSERT INTO meta(k,v) VALUES('data_version','{int(time.time())}') ON CONFLICT(k) DO UPDATE SET v=excluded.v;")
    out=os.path.join(ROOT,'sync','out',time.strftime('%Y%m%d-%H%M%S'));os.makedirs(out,exist_ok=True)
    open(os.path.join(out,'upsert.sql'),'w').write('\n'.join(stmts))
    files=[]
    for i,ch in enumerate(chunk_statements(stmts)):
        f=os.path.join(out,f'apply_{i:02d}.js');open(f,'w').write(connector_js(ch));files.append(f)
    mode=a.apply
    if mode=='auto': mode='wrangler' if wrangler_ok() else 'connector'
    if mode=='wrangler':
        r=subprocess.run(['npx','wrangler','d1','execute','x-bookmarks','--remote','--yes','--file',os.path.join(out,'upsert.sql')],cwd=os.path.join(ROOT,'site'),text=True)
        if r.returncode: sys.exit('wrangler d1 execute failed')
        print('APPLIED via wrangler. Site picks up new data automatically (no redeploy needed).')
    else:
        print('APPLY_WITH_CONNECTOR: run each file below with the Cloudflare connector (namespace user-Cloudflare,')
        print('tool execute, arguments {"code": "$file:<path>"}), in order, and check success=true:')
        for f in files: print('  '+f)
        print('No redeploy is needed for data changes.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    for c in ('plan','run'):
        p=sp.add_parser(c);p.add_argument('--pages',required=True)
        p.add_argument('--apply',choices=['auto','wrangler','connector'],default='auto');p.add_argument('--allow-gap',action='store_true')
    p=sp.add_parser('check');p.add_argument('--page',required=True)
    p=sp.add_parser('push');p.add_argument('--ids',required=True);p.add_argument('--apply',choices=['auto','wrangler','connector'],default='auto')
    a=ap.parse_args()
    {'plan':cmd_plan,'run':cmd_run,'push':cmd_push,'check':cmd_check}[a.cmd](a)
