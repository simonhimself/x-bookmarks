import json,sys
def load(p):
    s=open(p).read(); i=s.index('{'); j=s.rindex('}')
    return json.loads(s[i:j+1])
for p in sys.argv[1:]:
    d=load(p); D=d.get('data',[])
    print(p, d.get('meta'), 'errors=',len(d.get('errors',[])), 'n=',len(D), (D[-1]['created_at'] if D else None))
