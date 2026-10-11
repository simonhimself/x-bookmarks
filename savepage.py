import json,sys,os,re
src,n=sys.argv[1],sys.argv[2]
os.makedirs('raw/full50',exist_ok=True)
dst=f'raw/full50/p{int(n):02d}.json'
s=open(src).read(); d=json.loads(s[s.index('{'):s.rindex('}')+1])
json.dump(d,open(dst,'w'),ensure_ascii=False); os.remove(src)
m=d.get('meta',{}); D=d.get('data',[])
print(dst,m.get('result_count'),'next' if m.get('next_token') else 'END','errors',len(d.get('errors',[])),D[0]['created_at'] if D else '',D[-1]['created_at'] if D else '')
t=m.get('next_token','NONE (end reached)')
notes=open('EXPORT_NOTES.md').read()
notes=re.sub(r'\n## Full run resume.*','',notes,flags=re.S)
notes+=f"\n## Full run resume (auto-updated)\n- Last saved page: {dst}\n- Resume pagination_token={t}\n"
open('EXPORT_NOTES.md','w').write(notes)
print('TOKEN',t)
