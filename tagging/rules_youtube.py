# YouTube tagging rules, derived from the X rules (rules.py) but stricter: video descriptions are long and
# full of boilerplate, so ambiguous words that work for short X posts ("skills", "agent", "focus", "watch",
# "shorts", "wall", "test", "visit"...) are dropped per topic, and YouTube-specific phrases are added.
# build.py embeds YT_RULES into the Worker. X tagging (rules.py / tag.py) is unchanged.
import re
from rules import R

# Alternatives removed from each X pattern for YouTube (exact alternative text, as written in rules.py).
DROP = {
 'ai-coding': [r'\bskills?\b', r'\bagents?\b', r'\bprompts?\b', r'\btokens?\b', r'\bplugins?\b', r'hooks?\b', r'cursor', r'\bharness',
               r'v0\b', r'copilot', r'lovable', r'replit', r'\bopus\b', r'\bhaiku\b', r'\bsonnet\b', r'\bspec\b', r'terminal', r'repo\b', r'\bpr\b', r'\bprs\b', r'\bllm\b'],
 'ai-creative': [r'\bui\b', r'\bux\b', r'design(er|s)?\b', r'animation', r'3d\b', r'font', r'logo', r'illustration', r'aesthetic', r'slides?\b', r'render',
                 r'typography', r'landing page', r'\bstyle\b', r'visuals?', r'cinematic', r'photoreal', r'creative', r'runway', r'blender', r'kling'],
 'ai-news': [r'benchmark', r'new model', r'rag\b', r'neural', r'fable \d'],
 'testing': [r'\btests?\b', r'\btesting\b', r'regression', r'qa\b', r'verification'],
 'devtools': [r'server', r'browser', r'api\b', r'\bnode\b', r'database', r'bun\b', r'react\b', r'raspberry', r'rust\b', r'computer use'],
 'product': [r'growth', r'marketing', r'distribution', r'users\b', r'customers?', r'launch(ed)?\b', r'ship(ped|ping)?\b', r'raised', r'conversion',
             r'onboarding', r'pricing', r'vcs?\b', r'venture', r'newsletters?', r'\barr\b', r'llc\b'],
 'investing': [r'watchlist', r'trading', r'trader', r'gold price', r'silver price', r'compounding'],
 'tesla': [r'battery', r'batteries', r'solar', r'nuclear', r'falcon', r'power grid', r'grid storage'],
 'home': [r'house', r'home\b', r'homes', r'wall', r'floor', r'windows?\b', r'wood', r'stone', r'lighting', r'lamp', r'deck\b', r'pool\b', r'yard\b',
          r'storage idea', r'cozy', r'tiles?', r'ceiling', r'stairs', r'shelf', r'shelves', r'soil', r'plants?\b', r'facade'],
 'property': [r'listing', r'for sale', r'rent(al)?\b', r'€ ?\d', r'properties', r'airbnb'],
 'travel': [r'visit', r'trip\b', r'mountains?', r'lake\b', r'island', r'city of', r'scenic', r'village', r'\bcastle', r'england', r'germany', r'france', r'italy', r'japan', r'spain'],
 'productivity': [r'focus', r'routine', r'success', r'learning', r'morning', r'advice', r'parents', r'kids', r'marriage', r'relationship', r'purpose',
                  r'meaning', r'regret', r'happiness', r'journal', r'motivation', r'books? (to|that|you)'],
 'movies': [r'episodes?\b', r'season \d', r'trailer', r'masterpiece', r'watchlist', r'anime'],
 'lifestyle': [r'shorts', r'watch(es)?\b', r'amazon', r'get yours', r'buy this', r'🛒', r'cleaning', r'rice', r'dinner', r'snack', r'clothing', r'sportswear'],
 'health': [r'running', r'blood', r'joint', r'knee', r'muscles?', r'gut\b', r'teeth', r'dentist', r'cardio', r'doctor'],
 'curiosities': [r'war\b', r'president', r'europe', r'china', r'russia', r'ukraine', r'map\b', r'fact\b', r'facts', r'population', r'trump', r'government', r'space\b', r'planet'],
 'humor': [r'bird', r'lol\b', r'wtf', r'💀', r'no context', r'wholesome', r'meme'],
}
# YouTube-only additions (regex, weight).
ADD = {
 'ai-coding': [(r'ai coding|agentic coding|coding agents?|vibe ?cod\w*|claude skills?|agent skills?|\bcodex\b|claude code|\bmcp\b|build(ing)? (an? )?apps? with (ai|claude|gpt)|ai (developer|engineer)s?\b|software engineering|programming|\bcoding\b', 2)],
 'ai-news': [(r'\bai (agents?|models?|labs?|tools?|assistants?|sidekicks?|news|safety|startups?)\b|voice agents?|agent builder|\bllms?\b|openai|anthropic|\bclaude\b|chatgpt|gemini|\bgrok\b|\bgpt-?\d|superintelligence|\bagi\b|automate\w*', 1.5)],
 'ai-creative': [(r'\bkling\b|ai (art|design|video|image|music)|image generation|video generation|claude design|nano banana|\bveo\b|midjourney', 2)],
 'devtools': [(r'\bcli\b|cloudflare|homelab|self.?host\w*|linux|docker|airgapped', 1.5)],
 'product': [(r'startups?|founders?|saas|business model|digital bank|fintech|entrepreneur\w*|product management|go.to.market', 1.5)],
 'investing': [(r'personal finance|financial|finance|debasement|money|banks?\b|banking|stock market|wealth|\bfed\b|rate (cut|hike)|hiking into|monetary', 1.5)],
 'home': [(r'interior design|home tour|house tour|room (layout|makeover)|bedrooms?|renovat\w*|ch[aâ]teau|makeover|furniture|garden(ing)?|raised beds?|architecture|house (build|renovation)|bricklaying|masons?', 2)],
 'travel': [(r'travel guide|road trip|train ride|cab ride|driver.?s? view|solo hiking|hiking trail|skiurlaub|ski (holiday|resort|trip)|e-bike.?tour|cenote|explor(e|ing) |things to do in|switzerland|swiss|alps|\bbern\b|zurich|z[uü]rich', 2)],
 'productivity': [(r'commitment|leaders(hip)?|coaching|planning ahead|feelings|self.?improvement|mental health|discipline|habits?|mindset|stoic\w*', 1.5)],
 'movies': [(r'\bfilms?\b|\bmovies?\b|tv shows?|series review|documentar\w*|\boled\b|qd-oled|tv shootout|home cinema', 1.5)],
 'lifestyle': [(r'hi-?fi|audiophile|amplifier|turntable|\bdac\b|\bsacd\b|loudspeakers?|\w*lautsprecher|speakers?|headphones|espresso|coffee|recipe|cooking|\bporsche\b|\bferrari\b|\b911\b|supercar|first drive|review\b', 1.5)],
 'health': [(r'longevity|training routine|recovery|in shape|workout|fitness|remedy|colds?\b|flu\b|nutrition|supplements?|sleep|bryan johnson|enhanced games', 1.5)],
 'curiosities': [(r'explained|why (we|you|all|the)|world record|weltrekord|robots?|engineering|history|national trust|science|politics|election|democrats?|republicans?', 1.5)],
 'humor': [(r'chicks|puppies|kittens?|\bcats?\b|\bdogs?\b|funny', 2)],
}

def split_alts(p):
    out, depth, cur = [], 0, ''
    i = 0
    while i < len(p):
        ch = p[i]
        if ch == '\\' and i + 1 < len(p): cur += p[i:i+2]; i += 2; continue
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == '|' and depth == 0: out.append(cur); cur = ''
        else: cur += ch
        i += 1
    out.append(cur)
    return out

def build():
    Y = {}
    for tag, rules in R.items():
        drop = set(DROP.get(tag, []))
        rs = []
        for p, w in rules:
            alts = [a for a in split_alts(p) if a not in drop]
            if alts: rs.append(['|'.join(alts), w])
        rs += [[p, w] for p, w in ADD.get(tag, [])]
        Y[tag] = rs
    unknown = {t: [d for d in ds if not any(d in split_alts(p) for p, _ in R.get(t, []))] for t, ds in DROP.items()}
    unknown = {t: d for t, d in unknown.items() if d}
    assert not unknown, f"DROP entries not found in rules.py: {unknown}"
    for t, rs in Y.items():
        for p, _ in rs: re.compile(p)
    return Y

YT_RULES = build()
