"""Shared helpers: normalize X API pages, expand t.co links, build D1 rows and SQL."""
import json,re,glob,os,sys,html
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TCO=re.compile(r'https://t\.co/\w+')
XSTATUS=re.compile(r'https?://(www\.)?(x|twitter)\.com/')

def load_json_loose(path):
    """Load a JSON file that may carry wrapper text (tool output) around the JSON object."""
    s=open(path,encoding='utf-8').read()
    i=s.find('{'); 
    return json.JSONDecoder().raw_decode(s[i:])[0]

def url_map(t):
    m={}
    for src in ((t.get('entities') or {}), ((t.get('note_tweet') or {}).get('entities') or {})):
        for e in src.get('urls',[]) or []:
            if e.get('url'):
                m[e['url']]=None if e.get('media_key') else (e.get('unwound_url') or e.get('expanded_url'))
    return m

def expand_text(text,m,self_id=None):
    def rep(mo):
        u=mo.group(0)
        if u in m:
            x=m[u]
            if x is None: return ''          # media link -> drop (shown as thumbnail)
            if self_id and f'/status/{self_id}' in x: return ''
            return x
        return u
    return html.unescape(TCO.sub(rep,text or '').strip())

def norm_post(t,users,media):
    """Normalize one API post object (data[] item) into the bookmarks.json shape (minus rank/tags)."""
    u=users.get(t.get('author_id'),{})
    nt=t.get('note_tweet') or {}
    text=nt.get('text') or t.get('text','')
    m=url_map(t)
    urls=[]
    for x in m.values():
        if x and x not in urls and f"/status/{t['id']}" not in x: urls.append(x)
    ents=nt.get('entities') or t.get('entities') or {}
    mk=(t.get('attachments') or {}).get('media_keys',[])
    return dict(id=t['id'],url=t.get('url') or f"https://x.com/{u.get('username','i')}/status/{t['id']}",
        text=text,text_expanded=expand_text(text,m,t['id']),created_at=t.get('created_at'),author_id=t.get('author_id'),
        author_username=u.get('username'),author_name=u.get('name'),author_profile_image_url=u.get('profile_image_url'),
        links=urls,external_links=[l for l in urls if not XSTATUS.match(l)],
        hashtags=[h['tag'] for h in ents.get('hashtags',[]) or []],mentions=[x['username'] for x in ents.get('mentions',[]) or []],
        media=[{f:media.get(k,{}).get(f) for f in ('type','url','preview_image_url')}|{'media_key':k} for k in mk],
        metrics=t.get('public_metrics'),lang=t.get('lang'),referenced_tweets=t.get('referenced_tweets',[]) or [],folders=[])

def parse_page(d):
    users={u['id']:u for u in d.get('includes',{}).get('users',[]) or []}
    media={m['media_key']:m for m in d.get('includes',{}).get('media',[]) or []}
    inc_posts={p['id']:p for p in d.get('includes',{}).get('tweets',[]) or []}
    return [norm_post(t,users,media) for t in d.get('data',[]) or []], users, media, inc_posts

def quoted_obj(q):
    if not q: return None
    if not q.get('available',True): return {'id':q['id'],'url':q.get('url'),'available':False}
    return {'id':q['id'],'url':q.get('url'),'text':q.get('text_expanded') or q.get('text'),'author_username':q.get('author_username'),
            'author_name':q.get('author_name'),'author_img':q.get('author_profile_image_url'),'created_at':q.get('created_at'),
            'media':[{'type':m.get('type'),'src':m.get('preview_image_url') or m.get('url')} for m in q.get('media') or [] if (m.get('preview_image_url') or m.get('url'))],
            'available':True}

def strip_ref_links(text,o):
    for r in o.get('referenced_tweets') or []:
        text=re.sub(r'\s*https?://(www\.)?(x|twitter)\.com/\w+/status/'+r['id']+r'\S*','',text)
    return text.strip()

def to_row(o,seq):
    return dict(id=o['id'],seq=seq,created_at=o.get('created_at'),author_username=o.get('author_username') or '',
        author_name=o.get('author_name') or '',author_img=o.get('author_profile_image_url') or '',
        text=strip_ref_links(o.get('text_expanded') or o.get('text') or '',o),url=o['url'],
        ext_links=json.dumps(o.get('external_links') or [],ensure_ascii=False),
        media=json.dumps([{'type':m.get('type'),'src':m.get('preview_image_url') or m.get('url')} for m in o.get('media') or [] if (m.get('preview_image_url') or m.get('url'))],ensure_ascii=False),
        tags=json.dumps(o.get('tags') or ['other']),primary_tag=o.get('primary_tag') or 'other',
        quoted=json.dumps(quoted_obj(o.get('quoted')),ensure_ascii=False) if o.get('quoted') else None,
        replied=json.dumps(quoted_obj(o.get('replied_to')),ensure_ascii=False) if o.get('replied_to') else None,
        likes=(o.get('metrics') or {}).get('like_count') or 0,lang=o.get('lang') or '')

COLS=['id','seq','created_at','author_username','author_name','author_img','text','url','ext_links','media','tags','primary_tag','quoted','replied','likes','lang']
def sqlv(v):
    if v is None: return 'NULL'
    if isinstance(v,(int,float)): return str(v)
    return "'"+str(v).replace("'","''")+"'"

def upsert_sql(r):
    vals=','.join(sqlv(r[c]) for c in COLS)
    upd=','.join(f'{c}=excluded.{c}' for c in COLS if c not in ('id','seq'))
    return f"INSERT INTO bookmarks ({','.join(COLS)}) VALUES ({vals}) ON CONFLICT(id) DO UPDATE SET {upd};"

def chunk_statements(stmts,max_bytes=400_000):
    out=[];cur=[];n=0
    for s in stmts:
        b=len(s.encode())
        if cur and n+b>max_bytes: out.append(cur);cur=[];n=0
        cur.append(s);n+=b
    if cur: out.append(cur)
    return out

DB_ID='14bf4a21-7cb1-403f-b558-f709ed307260'
ACCOUNT='2423947c3898625c52d1d37070dffd03'
def connector_js(stmts):
    """A complete async arrow function for the Cloudflare connector `execute` tool that runs the SQL batch on D1."""
    sql='\n'.join(stmts)
    return ("async () => { const sql = "+json.dumps(sql,ensure_ascii=False)+";\n"
            f"const r = await cloudflare.request({{method:'POST', path:'/accounts/{ACCOUNT}/d1/database/{DB_ID}/query', body:{{sql}}}});\n"
            "return {success: r.success, errors: r.errors, statements: Array.isArray(r.result) ? r.result.length : 0, changes: Array.isArray(r.result) ? r.result.reduce((a,x)=>a+((x.meta&&x.meta.changes)||0),0) : 0}; }")
