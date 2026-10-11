"""One-off: add text_expanded (t.co -> real links) to bookmarks.json and its quoted/replied posts from raw pages."""
import json,glob,sys,os
sys.path.insert(0,os.path.dirname(__file__))
from lib import load_json_loose,url_map,expand_text,ROOT
os.chdir(ROOT)
M={}
for p in glob.glob('raw/*.json')+glob.glob('raw/*/p*.json')+glob.glob('raw/quoted/*.txt'):
    try: d=load_json_loose(p)
    except Exception as e: continue
    if not isinstance(d,dict): continue
    for t in d.get('data',[]) or []:
        if isinstance(t,dict) and 'id' in t: M[t['id']]=url_map(t)
B=json.load(open('bookmarks.json'))
n=0
for o in B:
    o['text_expanded']=expand_text(o['text'],M.get(o['id'],{}),o['id']); n+=o['id'] in M
    for k in ('quoted','replied_to'):
        q=o.get(k)
        if q and q.get('available'): q['text_expanded']=expand_text(q.get('text'),M.get(q['id'],{}),q['id'])
json.dump(B,open('bookmarks.json','w'),ensure_ascii=False,indent=1)
print('expanded',n,'of',len(B))
