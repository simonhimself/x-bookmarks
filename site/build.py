import json,os
H=os.path.dirname(os.path.abspath(__file__))
html=open(f'{H}/src/index.html').read()
tax=json.load(open(f'{H}/../tagging/taxonomy.json'))
w=open(f'{H}/src/worker.template.js').read().replace('__HTML__',json.dumps(html)).replace('__TAXONOMY__',json.dumps(tax))
os.makedirs(f'{H}/dist',exist_ok=True)
open(f'{H}/dist/worker.js','w').write(w)
print('dist/worker.js',len(w))
