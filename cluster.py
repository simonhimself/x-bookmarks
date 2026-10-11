import json,re,collections
B=json.load(open('bookmarks.json'))
R=[
('AI coding agents & skills (Claude Code, Codex, AGENTS.md)',r'claude|codex|agents?\.md|skill|subagent|opus|sonnet|haiku|prompt|coding agent|\bPRs?\b|mcp|cursor|hermes|herdr|harness|agent'),
('Testing in the agent era',r'unit tests?|e2e|tests\b'),
('AI models, labs & industry news',r'openai|anthropic|gpt|astra|fable|altman|devday|\bai\b|llm|language model|muse|karpathy|grokbot'),
('AI for design, UI, video & creative',r'design|\bui\b|video|motion|slide|tldraw|excalidraw|blender|cad|render|image gen|grid'),
('Dev tools, infra & computer use',r'linux|mac mini|hetzner|tailscale|browser|computer use|cua|lightpanda|github|xcode|kvm|vm\b'),
('Travel & places (scenic photos)',r'switzerland|norway|vermont|japan|hokkaido|portugal|algarve|finland|hamburg|united kingdom|oregon|netherlands|provence|bergen|castle|🇨🇭|🇳🇴|🇺🇸|🇬🇧|🇫🇮'),
('Home, garden, architecture & real estate',r'house|home|kitchen|garden|raised bed|soil|porch|patio|landscap|hardscap|interior|ikea|bedroom|architect|island|stone home|hinge|ac unit|led bulb|windows in'),
('Tesla, EVs & energy',r'tesla|powerwall|fsd|model y|model 3|v2l|800 v|data center'),
('Investing, markets & startups',r'invest|munger|hedge fund|bulls|seed|founders ?fund|a16z|scale|chip design|nvidia|vending'),
('Productivity, mindset & quotes',r'mental|discipline|habit|feynman|stoic|virtues|kierkegaard|windows to|bed ?time|deep.*work|reading date|regret|iteration is|worry|focus'),
('Movies & TV',r'movies|series|masterpiece|breaking bad|tv series'),
('Food & lifestyle products',r'rice|fondue|sportswear|swim shorts|speakers|edifier|ninja|snack|bougie'),
]
cl=collections.defaultdict(list)
for o in B:
    t=o['text'].lower()+' '+' '.join(o['external_links']).lower()
    hit=[n for n,p in R if re.search(p,t,re.I)]
    o['_c']=hit or ['Other / humor / unclear']
    for h in hit or ['Other / humor / unclear']: cl[h].append(o)
for n,_ in R+[('Other / humor / unclear',0)]:
    L=cl[n];print(f"\n## {n}: {len(L)}")
    for o in L[:40]: print('  ',o['bookmark_rank'],'@'+o['author_username'],' '.join(o['text'].split())[:90])
order=['Travel & places (scenic photos)','Tesla, EVs & energy','Movies & TV','Testing in the agent era','AI coding agents & skills (Claude Code, Codex, AGENTS.md)','AI for design, UI, video & creative','AI models, labs & industry news','Home, garden, architecture & real estate','Investing, markets & startups','Productivity, mindset & quotes','Food & lifestyle products','Dev tools, infra & computer use','Other / humor / unclear']
P=collections.defaultdict(list)
for o in B:
    p=next(n for n in order if n in o['_c']); P[p].append(o)
print('\n\nPRIMARY')
for n in order: print(len(P[n]),n)
for n in ['Travel & places (scenic photos)','Home, garden, architecture & real estate','AI for design, UI, video & creative','Dev tools, infra & computer use']:
    print('\n##',n); [print('  ',o['bookmark_rank'],'@'+o['author_username'],' '.join(o['text'].split())[:80]) for o in P[n]]
