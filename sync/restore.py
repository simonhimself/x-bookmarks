#!/usr/bin/env python3
"""Rebuild the local bookmarks.json from the live D1 database (read-only), e.g. after the box was wiped.

  python3 sync/restore.py fetch [--via auto|wrangler|connector] [--out PATH] [--force]
        wrangler:  reads every row with `wrangler d1 execute --remote` (SELECT only), then builds PATH
        connector: writes sync/out/restore-<ts>/read_00.js for the Cloudflare connector and prints the next step
  python3 sync/restore.py build --dump FILE [FILE ...] [--out PATH] [--force]
        connector result files -> PATH. With only some parts, writes the missing read_NN.js and exits 10.
  python3 sync/restore.py compare [--a bookmarks.json] [--b bookmarks.restored.json]
  python3 sync/restore.py tagging [--from PATH] [--force] [--dry-run]
        recreate tagging/author_priors.json and tagging/manual_tags.json from the restored tags (skips existing files)

PATH defaults to bookmarks.restored.json (gitignored). An existing bookmarks.json is only replaced with --force.
Nothing here writes to D1: the only SQL sent is the fixed SELECT in READ_SQL. See sync/README.md and
docs/OPERATIONS.md ("Recover from Cloudflare") for what D1 stores and what can't be recovered.
"""
import json,os,re,sys,glob,time,argparse,subprocess,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import ROOT,DB_ID,ACCOUNT,COLS,load_json_loose,XSTATUS
BM=os.path.join(ROOT,'bookmarks.json')
DEFAULT_OUT=os.path.join(ROOT,'bookmarks.restored.json')
PAGE=500
# Keyset pagination, newest first. The only statement this module ever sends to D1.
READ_SQL=f"SELECT {','.join(COLS)} FROM bookmarks WHERE seq < ? ORDER BY seq DESC LIMIT ?"
COUNT_SQL="SELECT COUNT(*) AS n FROM bookmarks"

# ---------- fetch ----------
# The connector returns at most ~24,000 characters per call, and D1 holds ~2 MB. So each connector call reads
# every row (SELECT only), deflates the JSON, packs 14 bits per character into CJK code points (U+4E00-U+8DFF)
# and returns one slice of PART_CHARS characters. `build` reassembles the slices and checks a SHA-256 of the
# whole encoded dump, so a sync that lands between two calls is detected instead of mixing snapshots.
PART_CHARS=22000
CJK0=0x4E00
def read_js(part):
    path=f'/accounts/{ACCOUNT}/d1/database/{DB_ID}/raw'
    return ("async () => {\n"
        f"const PART = {int(part)}, PART_CHARS = {PART_CHARS}, CJK0 = {CJK0};\n"
        f"const path = {json.dumps(path)};\n"
        f"const READ = {json.dumps(READ_SQL)};\n"
        f"const COUNT = {json.dumps(COUNT_SQL)};\n"
        "const q = async (sql, params) => { const r = await cloudflare.request({method:'POST', path, body: params ? {sql, params} : {sql}});\n"
        "  if (!r.success || !r.result || !r.result[0] || !r.result[0].success) throw new Error('D1 read failed: ' + JSON.stringify(r.errors || r.result));\n"
        "  return r.result[0].results; };\n"
        "const total = (await q(COUNT)).rows[0][0];\n"
        "let cursor = 9007199254740991, columns = null, rows = [];\n"
        "for (let i = 0; i < 1000; i++) {\n"
        f"  const res = await q(READ, [cursor, {PAGE}]);\n"
        "  columns = res.columns; rows = rows.concat(res.rows);\n"
        f"  if (res.rows.length < {PAGE}) break;\n"
        "  cursor = res.rows[res.rows.length - 1][columns.indexOf('seq')];\n"
        "}\n"
        "const raw = new TextEncoder().encode(JSON.stringify({total, columns, rows}));\n"
        "const z = new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer());\n"
        "let out = [], acc = 0, bits = 0;\n"
        "for (const b of z) { acc = (acc << 8) | b; bits += 8; while (bits >= 14) { bits -= 14; out.push(CJK0 + ((acc >> bits) & 0x3fff)); } acc &= (1 << bits) - 1; }\n"
        "if (bits) out.push(CJK0 + ((acc << (14 - bits)) & 0x3fff));\n"
        "let enc = ''; for (let i = 0; i < out.length; i += 4096) enc += String.fromCharCode.apply(null, out.slice(i, i + 4096));\n"
        "const h = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(enc)))).map(x => x.toString(16).padStart(2, '0')).join('');\n"
        "const parts = Math.ceil(enc.length / PART_CHARS);\n"
        "return {xbm_restore: 2, part: PART, parts, total, fetched: rows.length, bytes: z.length, sha256: h, data: enc.slice(PART * PART_CHARS, (PART + 1) * PART_CHARS)};\n}")

def wrangler_ok():
    try:
        r=subprocess.run(['npx','wrangler','whoami'],cwd=os.path.join(ROOT,'site'),capture_output=True,text=True,timeout=60)
        return 'not authenticated' not in (r.stdout+r.stderr).lower() and r.returncode==0
    except Exception: return False

def sql_lit(v): return str(int(v))

def wrangler_query(sql):
    assert sql.lstrip().upper().startswith('SELECT'), 'read-only: SELECT only'
    r=subprocess.run(['npx','wrangler','d1','execute','x-bookmarks','--remote','--json','--command',sql],
                     cwd=os.path.join(ROOT,'site'),capture_output=True,text=True)
    if r.returncode: sys.exit('wrangler d1 execute failed:\n'+r.stderr[-2000:])
    res=json.loads(r.stdout)
    return res[0]['results']

def fetch_wrangler():
    total=wrangler_query(COUNT_SQL)[0]['n'];rows=[];cursor=2**53-1
    while True:
        sql=READ_SQL.replace('?',sql_lit(cursor),1).replace('?',sql_lit(PAGE),1)
        page=wrangler_query(sql); rows+= [[o.get(c) for c in COLS] for o in page]
        print(f'  read {len(rows)} / {total}')
        if len(page)<PAGE: break
        cursor=page[-1]['seq']
    return {'xbm_restore':1,'total':total,'fetched':len(rows),'columns':COLS,'rows':rows}

def restore_dir(new=False):
    ds=sorted(glob.glob(os.path.join(ROOT,'sync','out','restore-*')))
    if ds and not new: return ds[-1]
    d=os.path.join(ROOT,'sync','out','restore-'+time.strftime('%Y%m%d-%H%M%S'));os.makedirs(d,exist_ok=True);return d

def connector_hint(files):
    print('READ_WITH_CONNECTOR: run each read-only script below with the Cloudflare connector, with write_to_file: true:')
    for f in files: print(f'  CallDynamicTool namespace=user-Cloudflare toolName=execute write_to_file=true arguments={{"code": "$file:{f}"}}')

def cmd_fetch(a):
    via=a.via
    if via=='auto': via='wrangler' if wrangler_ok() else 'connector'
    out=restore_dir(new=True)
    if via=='wrangler':
        dump=fetch_wrangler(); f=os.path.join(out,'dump.json'); json.dump(dump,open(f,'w'),ensure_ascii=False)
        print('dump:',f); a.dump=[f]; cmd_build(a)
    else:
        f=os.path.join(out,'read_00.js'); open(f,'w').write(read_js(0))
        connector_hint([f])
        print('then pass the result file it reports to:')
        print('  python3 sync/restore.py build --dump <result file>')
        print('build tells you how many more parts to read (read_01.js, ...); pass all result files to build at the end.')

# ---------- build ----------
def parse_result(path):
    s=open(path,encoding='utf-8').read()
    i=s.find('{"xbm_restore"')
    if i<0: i=s.find('{')
    d=json.JSONDecoder().raw_decode(s[i:])[0]
    if 'xbm_restore' not in d and isinstance(d.get('result'),dict): d=d['result']
    if 'xbm_restore' not in d: sys.exit(f'{path}: not a restore result')
    return d

def decode_cjk(enc,nbytes):
    acc=0;bits=0;out=bytearray()
    for ch in enc:
        v=ord(ch)-CJK0
        if not 0<=v<0x4000: raise ValueError(f'unexpected character U+{ord(ch):04X} in dump (output truncated or altered?)')
        acc=(acc<<14)|v;bits+=14
        while bits>=8: bits-=8;out.append((acc>>bits)&0xff)
        acc&=(1<<bits)-1
    return bytes(out[:nbytes])

def load_dump(paths):
    """Returns (rows, None) when complete, or (None, missing_part_numbers) for a partial connector read."""
    import hashlib,zlib
    ds=[parse_result(p) for p in paths]
    whole=[d for d in ds if d.get('xbm_restore')==1]
    if whole: d=whole[0]
    else:
        latest=max(ds,key=lambda d:d['total'])
        sha=ds[-1]['sha256']; same=[d for d in ds if d['sha256']==sha]
        if len(same)<len(ds):
            sys.exit('the parts come from different snapshots (D1 changed between calls, e.g. a sync ran). '
                     'Run every read_NN.js again and pass only the new result files.')
        got={d['part']:d['data'] for d in same}; n=same[0]['parts']
        missing=[k for k in range(n) if k not in got]
        if missing: return None,missing
        enc=''.join(got[k] for k in range(n))
        if hashlib.sha256(enc.encode()).hexdigest()!=sha: sys.exit('checksum mismatch: a part was truncated or altered; read it again')
        d=json.loads(zlib.decompress(decode_cjk(enc,same[0]['bytes']),-15))
        d['fetched']=len(d['rows'])
    cols=d['columns']; rows=[dict(zip(cols,r)) for r in d['rows']]
    if d.get('total') is not None and d['total']!=len(rows):
        sys.exit(f"dump is incomplete: {len(rows)} rows fetched, D1 reported {d['total']}; fetch again")
    return rows,None

def media_back(m):
    # D1 keeps only {type, src}; src = preview_image_url (video/gif) or url (photo). media_key is not stored.
    if m.get('type')=='photo': return {'type':'photo','url':m.get('src'),'preview_image_url':None}
    return {'type':m.get('type'),'url':None,'preview_image_url':m.get('src')}

def ref_back(q):
    if q is None: return None
    if not q.get('available',True): return {'id':q['id'],'url':q.get('url'),'available':False}
    return {'id':q['id'],'url':q.get('url'),'text':q.get('text'),'author_username':q.get('author_username'),
            'author_name':q.get('author_name'),'author_profile_image_url':q.get('author_img'),'created_at':q.get('created_at'),
            'links':[],'media':[media_back(m) for m in q.get('media') or []],'available':True,'text_expanded':q.get('text')}

HASH=re.compile(r'(?<![\w&/])#(\w*[^\W\d_]\w*)'); MENT=re.compile(r'(?<![\w/])@(\w{1,15})\b')
def manual_ids():
    p=os.path.join(ROOT,'tagging','manual_tags.json')
    return set(json.load(open(p))) if os.path.exists(p) else set()

def from_row(r,top,manual):
    tags=json.loads(r['tags'] or '["other"]'); ext=json.loads(r['ext_links'] or '[]')
    q=ref_back(json.loads(r['quoted'])) if r['quoted'] else None
    rp=ref_back(json.loads(r['replied'])) if r['replied'] else None
    text=r['text'] or ''
    refs=([{'id':q['id'],'type':'quoted'}] if q else [])+([{'id':rp['id'],'type':'replied_to'}] if rp else [])
    links=list(ext)
    for x in (q,rp):
        if x and x.get('url') and x['url'] not in links: links.append(x['url'])
    src='manual' if r['id'] in manual else ('unclear' if tags==['other'] else 'rules')
    o=dict(bookmark_rank=top-r['seq']+1,id=r['id'],url=r['url'],text=text,created_at=r['created_at'],author_id=None,
        author_username=r['author_username'],author_name=r['author_name'],author_profile_image_url=r['author_img'] or None,
        links=links,external_links=ext,hashtags=HASH.findall(text),mentions=MENT.findall(text),
        media=[media_back(m) for m in json.loads(r['media'] or '[]')],metrics={'like_count':r['likes'] or 0},
        lang=r['lang'],referenced_tweets=refs,folders=[])
    if q: o['quoted']=q
    if rp: o['replied_to']=rp
    o.update(tags=tags,primary_tag=r['primary_tag'] or tags[0],tag_source=src,text_expanded=text,seq=r['seq'])
    return o

def build(rows):
    top=max(r['seq'] for r in rows); man=manual_ids()
    return [from_row(r,top,man) for r in sorted(rows,key=lambda r:-r['seq'])]

def cmd_build(a):
    paths=[p for x in a.dump for p in (sorted(glob.glob(x)) or [x])]
    rows,missing=load_dump(paths)
    if missing:
        d=restore_dir(); files=[]
        for k in missing:
            f=os.path.join(d,f'read_{k:02d}.js'); open(f,'w').write(read_js(k)); files.append(f)
        print(f'have {len(paths)} of {len(paths)+len(missing)} parts.')
        connector_hint(files)
        print('then run build again with ALL result files:')
        print('  python3 sync/restore.py build --dump '+' '.join(paths)+' <new result files...>')
        sys.exit(10)
    B=build(rows)
    out=os.path.abspath(a.out)
    if os.path.exists(out) and out!=DEFAULT_OUT:
        if not a.force: sys.exit(f'refusing to overwrite {out}: pass --force (the default output is bookmarks.restored.json)')
        bak=os.path.join(ROOT,'bookmarks.before-restore-'+time.strftime('%Y%m%d-%H%M%S')+'.json') if out==os.path.abspath(BM) else out+'.bak'
        os.replace(out,bak); print('previous file moved to',bak)
    json.dump(B,open(out,'w'),ensure_ascii=False,indent=1)
    print(f'restored {len(B)} bookmarks (seq {B[-1]["seq"]}-{B[0]["seq"]}) -> {out}')
    if os.path.exists(BM) and os.path.abspath(BM)!=out: compare(BM,out)

# ---------- compare ----------
def compare(pa,pb,show=5):
    A={o['id']:o for o in json.load(open(pa))}; B={o['id']:o for o in json.load(open(pb))}
    print(f'\ncompare {os.path.relpath(pa,ROOT)} ({len(A)}) vs {os.path.relpath(pb,ROOT)} ({len(B)})')
    oa=sorted(set(A)-set(B)); ob=sorted(set(B)-set(A))
    print(f'  only in {os.path.basename(pa)}: {len(oa)} {oa[:10]}'); print(f'  only in {os.path.basename(pb)}: {len(ob)} {ob[:10]}')
    diff=collections.Counter(); ex={}
    def walk(x,y,path,i):
        if isinstance(x,dict) and isinstance(y,dict):
            for k in set(x)|set(y): walk(x.get(k,'<missing>'),y.get(k,'<missing>'),f'{path}.{k}' if path else k,i)
        elif x!=y: diff[path]+=1; ex.setdefault(path,(i,x,y))
    for i in set(A)&set(B): walk(A[i],B[i],'',i)
    if not diff: print('  all shared posts identical'); return 0
    print('  fields that differ (posts affected):')
    for k,n in sorted(diff.items(),key=lambda kv:(kv[0].split('.')[0],kv[0])):
        i,x,y=ex[k]; print(f'    {k:42s} {n:5d}   e.g. {i}: {json.dumps(x,ensure_ascii=False)[:70]} -> {json.dumps(y,ensure_ascii=False)[:70]}')
    return 1

def cmd_compare(a): compare(os.path.abspath(a.a),os.path.abspath(a.b))

def recover_tagging(B):
    """Rebuild the two local-only tagging files from restored bookmarks.
    author_priors.json: learned from tags exactly as tag.py does (identical to the original when the tags match).
    manual_tags.json: the original list of hand-fixed ids isn't in D1, so this pins every post whose current tags
    differ from what the rules alone would assign. Re-tagging then reproduces every tag stored in D1."""
    sys.path.insert(0,os.path.join(ROOT,'tagging')); import tag as T
    T.MANUAL.clear()
    priors=T.learn_priors(B)
    manual={o['id']:o['tags'] for o in B if T.assign(o,priors)[0]!=o['tags']}
    return T,priors,manual

def cmd_tagging(a):
    B=json.load(open(a.src)); T,priors,manual=recover_tagging(B)
    for path,data,what in ((T.PRIORS_P,priors,'author priors'),(T.MANUAL_P,manual,'manual tag overrides')):
        if os.path.exists(path) and not a.force: print(f'kept existing {os.path.relpath(path,ROOT)} (pass --force to replace); recovered {len(data)} {what}'); continue
        if a.dry_run: print(f'would write {len(data)} {what} -> {os.path.relpath(path,ROOT)}'); continue
        json.dump(data,open(path,'w'),indent=1,sort_keys=True,ensure_ascii=False); print(f'wrote {len(data)} {what} -> {os.path.relpath(path,ROOT)}')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('fetch');p.add_argument('--via',choices=['auto','wrangler','connector'],default='auto')
    p.add_argument('--out',default=DEFAULT_OUT);p.add_argument('--force',action='store_true')
    p=sp.add_parser('build');p.add_argument('--dump',required=True,nargs='+');p.add_argument('--out',default=DEFAULT_OUT);p.add_argument('--force',action='store_true')
    p=sp.add_parser('compare');p.add_argument('--a',default=BM);p.add_argument('--b',default=DEFAULT_OUT)
    p=sp.add_parser('tagging');p.add_argument('--from',dest='src',default=BM);p.add_argument('--force',action='store_true');p.add_argument('--dry-run',action='store_true')
    a=ap.parse_args()
    {'fetch':cmd_fetch,'build':cmd_build,'compare':cmd_compare,'tagging':cmd_tagging}[a.cmd](a)
