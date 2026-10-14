import json,os,sys
H=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(H,'..','tagging'))
from rules import R,AUTHOR
from rules_youtube import YT_RULES
html=open(f'{H}/src/index.html').read()
tax=json.load(open(f'{H}/../tagging/taxonomy.json'))
rules={'R':{k:[[p,w] for p,w in v] for k,v in R.items()},'AUTHOR':AUTHOR,'YT':YT_RULES}
yt=open(f'{H}/src/youtube.js').read().replace('__TAG_RULES__',json.dumps(rules))
w=open(f'{H}/src/worker.template.js').read().replace('__YOUTUBE__',yt).replace('__HTML__',json.dumps(html)).replace('__TAXONOMY__',json.dumps(tax))
os.makedirs(f'{H}/dist',exist_ok=True)
open(f'{H}/dist/worker.js','w').write(w)
print('dist/worker.js',len(w))
