#!/usr/bin/env python3
"""Reusable tagger for X bookmarks.
Usage: python3 tag.py [bookmarks.json] [--only-untagged] [--report]
Order of precedence per post: manual_tags.json (visual/manual review) > keyword rules + author priors.
Writes fields `tags` (1-3 ids) and `primary_tag` back into the file. Posts with no confident
signal get tags ["other"] and `tag_source`="unclear" so they can be reviewed visually (see README)."""
import json,re,sys,os,collections,urllib.parse
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
from rules import R,AUTHOR
TAX=[t['id'] for t in json.load(open(os.path.join(HERE,'taxonomy.json')))]
MANUAL_P=os.path.join(HERE,'manual_tags.json')
MANUAL=json.load(open(MANUAL_P)) if os.path.exists(MANUAL_P) else {}
PRIORS_P=os.path.join(HERE,'author_priors.json')
CR={k:[(re.compile(r'(?<![a-z0-9])(?:'+p+')',re.I),w) for p,w in v] for k,v in R.items()}

def blob(o):
    parts=[o.get('text') or '']
    for k in ('quoted','replied_to'):
        q=o.get(k)
        if q and q.get('available'): parts.append(q.get('text') or '')
    t=re.sub(r'https://t\.co/\S+','',' \n '.join(parts))
    doms=' '.join(urllib.parse.urlparse(l).netloc for l in (o.get('external_links') or []))
    return t+' '+doms

def score(o,priors):
    t=blob(o); s=collections.Counter()
    for tag,rs in CR.items():
        for rx,w in rs:
            n=len(rx.findall(t))
            if n: s[tag]+=w*min(n,3)
    a=o.get('author_username')
    if a in AUTHOR: s[AUTHOR[a]]+=2.5
    elif a in priors: s[priors[a]]+=2.0
    # coupling rules
    if s['testing'] and not (s['ai-coding'] or re.search(r'agent|claude|codex|ai\b|llm',t,re.I)): s['testing']*=0.3
    if s['ai-news']>0 and s['ai-coding']>=4: s['ai-news']*=0.6
    return s

def assign(o,priors):
    if o['id'] in MANUAL:
        tags=[x for x in MANUAL[o['id']] if x in TAX][:3] or ['other']
        return tags,'manual'
    s=score(o,priors)
    ranked=[(k,v) for k,v in s.most_common() if v>=2]
    if not ranked: return ['other'],'unclear'
    top=ranked[0][1]
    tags=[k for k,v in ranked if v>=max(2,top*0.5)][:3]
    return tags,'rules'

def learn_priors(B):
    c=collections.defaultdict(collections.Counter)
    for o in B:
        if o.get('tag_source') in ('manual','rules') and o.get('primary_tag')!='other':
            c[o['author_username']][o['primary_tag']]+=1
    P={}
    for a,cc in c.items():
        tag,n=cc.most_common(1)[0]; tot=sum(cc.values())
        if n>=3 and n/tot>=0.6: P[a]=tag
    return P

def run(path,only_untagged=False):
    B=json.load(open(path))
    priors=json.load(open(PRIORS_P)) if os.path.exists(PRIORS_P) else {}
    for o in B:
        if only_untagged and o.get('tags'): continue
        tags,src=assign(o,priors); o['tags']=tags; o['primary_tag']=tags[0]; o['tag_source']=src
    if not only_untagged:
        priors=learn_priors(B); json.dump(priors,open(PRIORS_P,'w'),indent=1,sort_keys=True)
        for o in B:
            if o['tag_source']=='unclear':
                tags,src=assign(o,priors); o['tags']=tags; o['primary_tag']=tags[0]; o['tag_source']=src
    json.dump(B,open(path,'w'),ensure_ascii=False,indent=1)
    return B

def report(B):
    c=collections.Counter(o['primary_tag'] for o in B); a=collections.Counter(t for o in B for t in o['tags'])
    for t in TAX: print(f"{t:14s} primary {c[t]:5d}  any {a[t]:5d}")
    print('sources',collections.Counter(o['tag_source'] for o in B))
    print(f"other: {c['other']} ({100*c['other']/len(B):.1f}%)")

if __name__=='__main__':
    args=[a for a in sys.argv[1:] if not a.startswith('--')]
    path=args[0] if args else os.path.join(HERE,'..','bookmarks.json')
    B=run(path,'--only-untagged' in sys.argv)
    report(B)
