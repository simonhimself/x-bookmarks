"""Parse public-reader get_posts_by_ids results (raw/quoted/*.txt) into quoted.json and attach to bookmarks.json."""
import json,glob,re,sys
posts={};users={};media={};errs={}
dec=json.JSONDecoder()
for p in sorted(glob.glob('raw/quoted/*.txt')):
    s=open(p).read()
    i=s.find('{"data"')
    if i<0: i=s.find('{"errors"')
    if i<0: print('skip',p); continue
    d,_=dec.raw_decode(s[i:])
    for u in d.get('includes',{}).get('users',[]): users[u['id']]=u
    for m in d.get('includes',{}).get('media',[]): media[m['media_key']]=m
    for t in d.get('data',[]): posts[t['id']]=t
    for e in d.get('errors',[]):
        rid=e.get('resource_id') or e.get('value')
        if rid: errs[rid]=e.get('title') or e.get('detail')
Q={}
for pid,t in posts.items():
    u=users.get(t.get('author_id'),{})
    nt=t.get('note_tweet') or {}
    text=nt.get('text') or t.get('text','')
    urls=[]
    for e in (t.get('entities') or {}).get('urls',[])+(nt.get('entities') or {}).get('urls',[]):
        x=e.get('unwound_url') or e.get('expanded_url')
        if x and x not in urls and not re.match(r'https?://(www\.)?(x|twitter)\.com/\w+/status/'+pid,x): urls.append(x)
    mk=(t.get('attachments') or {}).get('media_keys',[])
    Q[pid]=dict(id=pid,url=t.get('url') or f"https://x.com/{u.get('username','i')}/status/{pid}",text=text,
        author_username=u.get('username'),author_name=u.get('name'),author_profile_image_url=u.get('profile_image_url'),
        created_at=t.get('created_at'),links=urls,
        media=[{f:media.get(k,{}).get(f) for f in ('type','url','preview_image_url')} for k in mk],available=True)
json.dump(Q,open('quoted.json','w'),ensure_ascii=False,indent=1)
print('fetched',len(Q),'errors',len(errs),list(errs.items())[:5])
if __name__=='__main__' and '--attach' in sys.argv:
    B=json.load(open('bookmarks.json'))
    na=0
    for o in B:
        ref=o.get('referenced_tweets') or []
        q=next((r for r in ref if r['type']=='quoted'),None)
        rp=next((r for r in ref if r['type']=='replied_to'),None)
        for key,r in (('quoted',q),('replied_to',rp)):
            if not r: o.pop(key,None); continue
            if r['id'] in Q: o[key]=Q[r['id']]
            else: o[key]=dict(id=r['id'],url=f"https://x.com/i/status/{r['id']}",available=False,reason=errs.get(r['id'],'not returned')); na+=1
    json.dump(B,open('bookmarks.json','w'),ensure_ascii=False,indent=1)
    print('attached; unavailable',na,'quoted',sum('quoted' in o for o in B),'replied',sum('replied_to' in o for o in B))
