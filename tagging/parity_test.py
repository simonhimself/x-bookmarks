#!/usr/bin/env python3
"""Parity test: the Worker's JS tagger (site/src/youtube.js) vs tagging/tag.py on the same texts.
Rules only (no manual tags / learned priors), since the Worker has neither.
Usage: python3 tagging/parity_test.py [bookmarks.json]   exit 1 if agreement < 99%."""
import json,os,sys,subprocess,tempfile
H=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,H)
import tag as T
from rules import R,AUTHOR
T.MANUAL={}
path=sys.argv[1] if len(sys.argv)>1 else os.path.join(H,'..','bookmarks.json')
B=json.load(open(path))
cases=[{'id':o['id'],'text':T.blob(o),'author':o.get('author_username')} for o in B]
py={c['id']:T.assign(o,{})[0] for c,o in zip(cases,B)}
src=open(os.path.join(H,'..','site','src','youtube.js')).read()
seg=src[src.index('// ---------- tagging'):src.index('// ---------- crypto')]
rules=json.dumps({'R':{k:[[p,w] for p,w in v] for k,v in R.items()},'AUTHOR':AUTHOR})
tax=open(os.path.join(H,'taxonomy.json')).read()
js=f"""const TAXONOMY={tax};const TAG_RULES={rules};const TAG_IDS=TAXONOMY.map(t=>t.id);
const COMPILED=Object.fromEntries(Object.entries(TAG_RULES.R).map(([k,v])=>[k,v.map(([p,w])=>[new RegExp("(?<![a-z0-9])(?:"+p+")","gi"),w])]));
{seg}
const C=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));const out={{}};for(const c of C)out[c.id]=tagAssign(c.text,c.author).tags;console.log(JSON.stringify(out));"""
with tempfile.TemporaryDirectory() as d:
    open(f'{d}/c.json','w').write(json.dumps(cases)); open(f'{d}/t.js','w').write(js)
    js_out=json.loads(subprocess.check_output(['node',f'{d}/t.js',f'{d}/c.json']))
same=sum(py[i]==js_out[i] for i in py); prim=sum(py[i][0]==js_out[i][0] for i in py)
print(f"posts {len(py)}  identical tags {same} ({100*same/len(py):.2f}%)  same primary {prim} ({100*prim/len(py):.2f}%)")
for i in [i for i in py if py[i]!=js_out[i]][:8]: print(' diff',i,py[i],js_out[i])
sys.exit(0 if same/len(py)>=0.99 else 1)
