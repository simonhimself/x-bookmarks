"""Build the initial D1 load from bookmarks.json: schema + upserts, as connector JS batch files."""
import json,os,sys
sys.path.insert(0,os.path.dirname(__file__))
from lib import *
os.chdir(ROOT)
B=json.load(open('bookmarks.json'))
N=len(B)
stmts=[s.strip()+';' for s in open('site/schema.sql').read().split(';') if s.strip() and not s.strip().startswith('--')]
# schema.sql contains inline comments; strip them
stmts=[ '\n'.join(l.split('--')[0] for l in s.splitlines()) for s in stmts]
rows=[to_row(o,N-o['bookmark_rank']+1) for o in B]
stmts+= [upsert_sql(r) for r in rows]
import time
stmts.append(f"INSERT INTO meta(k,v) VALUES('data_version','{int(time.time())}') ON CONFLICT(k) DO UPDATE SET v=excluded.v;")
out='sync/out/initial'; os.makedirs(out,exist_ok=True)
for f in os.listdir(out): os.remove(os.path.join(out,f))
for i,ch in enumerate(chunk_statements(stmts)):
    open(f'{out}/apply_{i:02d}.js','w').write(connector_js(ch))
print(len(stmts),'statements in',i+1,'batches ->',out)
