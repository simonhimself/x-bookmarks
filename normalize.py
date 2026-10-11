import re
import json,glob,collections
items=[];users={};media={}
def load(p):
    s=open(p).read(); return json.loads(s[s.index('{'):s.rindex('}')+1])
seen=set()
for p in sorted(glob.glob('raw/page*.json'))+sorted(glob.glob('raw/rich50/p*.json'))+sorted(glob.glob('raw/cheap50/p*.json'))+sorted(glob.glob('raw/full50/p*.json')):
    d=load(p)
    for u in d.get('includes',{}).get('users',[]): users[u['id']]=u
    for m in d.get('includes',{}).get('media',[]): media[m['media_key']]=m
    for t in d.get('data',[]):
        if t['id'] not in seen: seen.add(t['id']); items.append(t)
out=[]
for i,t in enumerate(items,1):
    u=users.get(t.get('author_id'),{})
    nt=t.get('note_tweet')
    text=nt['text'] if nt and nt.get('text') else t.get('text','')
    ents=(nt or {}).get('entities') or t.get('entities') or {}
    urls=[]
    for e in (t.get('entities') or {}).get('urls',[])+((nt or {}).get('entities') or {}).get('urls',[]):
        x=e.get('unwound_url') or e.get('expanded_url')
        if x and x not in urls: urls.append(x)
    mk=(t.get('attachments') or {}).get('media_keys',[])
    out.append(dict(bookmark_rank=i,id=t['id'],url=t.get('url') or f"https://x.com/{u.get('username','i')}/status/{t['id']}",
      text=text,created_at=t.get('created_at'),author_id=t.get('author_id'),author_username=u.get('username'),author_name=u.get('name'),
      author_profile_image_url=u.get('profile_image_url'),links=urls,
      external_links=[l for l in urls if not re.match(r'https?://(www\.)?(x|twitter)\.com/',l)],hashtags=[h['tag'] for h in ents.get('hashtags',[])],mentions=[m['username'] for m in ents.get('mentions',[])],
      media=[{f:media.get(k,{}).get(f) for f in ('type','url','preview_image_url')}|{'media_key':k} for k in mk],
      metrics=t.get('public_metrics'),lang=t.get('lang'),referenced_tweets=t.get('referenced_tweets',[]),folders=[]))
json.dump(out,open('bookmarks.json','w'),ensure_ascii=False,indent=1)
print(len(out), len(set(o['id'] for o in out)))
c=collections.Counter
print('url field present:',sum('url' in t for t in items))
ds=sorted(o['created_at'] for o in out);print(ds[0],ds[-1])
print(c(o['created_at'][:7] for o in out).most_common())
print(c((o['author_username'],o['author_name']) for o in out).most_common(15))
print(c(o['lang'] for o in out).most_common())
print('ext links',sum(bool(o['external_links']) for o in out));print('links',sum(bool(o['links']) for o in out),'media',sum(bool(o['media']) for o in out),'note',sum(bool(t.get('note_tweet')) for t in items))
print(c(m['type'] for o in out for m in o['media']))
print('authors',len(set(o['author_id'] for o in out)))
import urllib.parse
print(c(urllib.parse.urlparse(l).netloc for o in out for l in o['external_links']).most_common(15))
