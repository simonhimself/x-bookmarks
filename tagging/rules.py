# Keyword rules per tag: list of (regex, weight). Matched case-insensitively against
# post text + quoted/replied text + external link domains.
R = {
'ai-coding': [
 (r'claude code|\bcodex\b|agents?\.md|claude\.md|\bskills?\b|subagents?|\bopus\b|\bsonnet\b|\bhaiku\b|coding agents?|agentic|\bmcp\b|cursor|vibe ?cod|\bralph\b|openclaw|opencode|\bharness|worktree|context window|\bprompts?\b|\bagents?\b|\bpi\b agent|amp ?code|windsurf|copilot|lovable|bolt\.new|replit|v0\b|\btokens?\b|\bplugins?\b|slash command|hooks?\b|claude', 2),
 (r'\bllm\b|\bpr\b|\bprs\b|pull request|repo\b|refactor|codebase|\bcli\b|terminal|\bspec\b|plan mode', 1)],
'ai-creative': [
 (r'midjourney|nano banana|seedream|\bkrea\b|runway|\bsora\b|\bveo\b|kling|higgsfield|freepik|elevenlabs|image gen|ai video|ai ads?\b|gpt-4o.*image|\bprompt\b.*(image|style|photo)|motion design|figma|\bui\b|\bux\b|landing page|design(er|s)?\b|animation|3d\b|blender|typography|font|logo|illustration|aesthetic|tldraw|excalidraw|slides?\b|render', 2),
 (r'\bstyle\b|visuals?|cinematic|photoreal|creative', 1)],
'ai-news': [
 (r'openai|anthropic|deepmind|gemini|\bgpt-?\d|chatgpt|\bgrok\b|xai\b|\bllama\b|mistral|deepseek|qwen|altman|karpathy|amodei|hassabis|benchmark|frontier model|new model|\bagi\b|model release|fable \d|llms?|fine.?tun\w*|rag\b|perplexity|kv cach\w*|gpt\w*|\bai\b|artificial intelligence|machine learning|neural', 1.5)],
'testing': [
 (r'unit tests?|\btests?\b|\btesting\b|\btdd\b|\be2e\b|playwright|test suite|regression|qa\b|verification|evals?\b', 2)],
'devtools': [
 (r'linux|\bmac ?mini\b|hetzner|tailscale|docker|kubernetes|\bvps\b|server|cloudflare|vercel|supabase|postgres|sqlite|database|github|\bgit\b|xcode|neovim|\bvim\b|tmux|terminal|browser|computer use|lightpanda|rust\b|typescript|javascript|python|react\b|next\.?js|bun\b|deno|\bnode\b|api\b|open.?source|self.?host|homelab|raspberry', 1.5)],
'product': [
 (r'\bmrr\b|\barr\b|saas|startup|founders?\b|onboarding|paywall|conversion|growth|marketing|distribution|indie ?hack|\bapp store\b|launch(ed)?\b|users\b|customers?|revenue|pricing|y ?combinator|\byc\b|product.?market|\bmvp\b|seed round|raised|vcs?\b|venture|a16z|ship(ped|ping)?\b|mobile app|build(ing)? an? app|side hustles?|dropshipping|e-?commerce|ecom\b|llc\b|small business|newsletters?|side project|\bsaas\b', 1.5)],
'investing': [
 (r'\$[A-Z]{2,5}\b|invest|stocks?\b|etf\b|bitcoin|\bbtc\b|crypto|trading|trader|portfolio|market cap|hedge fund|munger|buffett|dividend|s&p|nasdaq|fed\b|inflation|interest rates?|bonds?\b|treasur|fiscal|recession|valuation|earnings|ipo\b|watchlist|lyn alden|gold price|silver price|uranium|macro\b|compounding', 2)],
'tesla': [
 (r'tesla|spacex|starship|falcon|\bfsd\b|robotaxi|optimus|model [3ysx]\b|cybertruck|powerwall|\bev\b|\bevs\b|electric vehicle|battery|batteries|solar|nuclear|grid storage|power grid|elon|neuralink|starlink', 2)],
'home': [
 (r'house|home\b|homes|kitchen|bathroom|bedroom|living room|interior|garden|gardening|raised beds?|soil|plants?\b|landscap|patio|porch|deck\b|backyard|yard\b|architect|cabin|villa|renovat|diy\b|furniture|sofa|wall|floor|tiles?|ceiling|windows?\b|staircase|stairs|fireplace|pool\b|courtyard|facade|wood|stone|decor|lighting|lamp|shelf|shelves|closet|wardrobe|storage idea|cozy', 1.5)],
'property': [
 (r'real estate|property|properties|listing|for sale|mortgage|rent(al)?\b|landlord|housing market|square (feet|meters)|sqm|sq ?ft|€ ?\d|buy(ing)? a house|apartment prices|airbnb', 2)],
'travel': [
 (r'travel|trip\b|visit|vacation|holiday|hotel|island|beach|mountains?|alps|lake\b|village|old town|city of|\bcastle|national park|hike|hiking|switzerland|swiss|zurich|norway|iceland|japan|kyoto|tokyo|italy|italian|tuscany|amalfi|portugal|lisbon|sintra|algarve|spain|france|paris|provence|riviera|greece|croatia|dubrovnik|netherlands|amsterdam|utrecht|scotland|england|london|ireland|austria|germany|bavaria|finland|vermont|oregon|bali|thailand|scenic|📍|🇨🇭|🇳🇴|🇮🇹|🇵🇹|🇪🇸|🇫🇷|🇬🇷|🇭🇷|🇯🇵|🇮🇸|🇳🇱|🇬🇧|🇦🇹|🇩🇪', 2)],
'productivity': [
 (r'discipline|habits?|productiv|focus|deep work|mindset|stoic|stoicism|seneca|marcus aurelius|motivation|self.?respect|regret|life lesson|happiness|wisdom|advice|meditat|journal|routine|morning|books? (to|that|you)|read(ing)? list|learning|mental model|feynman|naval|success|life hacks|things i (know|learned|wish)|ted talks|time.?management|self.?improvement|purpose|meaning|parents|marriage|kids|relationship', 1.5)],
'movies': [
 (r'movies?\b|films?\b|tv series|tv shows?|netflix|\bhbo\b|episodes?\b|season \d|cinema|breaking bad|chernobyl|watchlist|imdb|rotten tomatoes|documentar|anime|trailer|box office|masterpiece', 2)],
'lifestyle': [
 (r'recipe|food|cook|cooking|rice|fondue|pasta|pizza|coffee|wine|restaurant|breakfast|dinner|snack|chef|bake|gadget|amazon|buy this|get yours|🛒|clothing|sportswear|shorts|fashion|watch(es)?\b|speakers?|headphones|cleaning|kitchen hack|life ?hack', 1.5)],
'health': [
 (r'health|healthy|fitness|workouts?|gym\b|exercises?|mobility|stretch\w*|diet|protein|fasting|longevity|supplements?|vitamins?|magnesium|hydrat\w*|electrolytes?|sauna|cold plunge|cold exposure|testosterone|cancer|inflammation|gut\b|sleep|biohack\w*|mitochondria\w*|muscles?|lower back|posture|knee|joint|seed oils|blood|doctor|dentist|teeth|metabolic|insulin|glucose|cardio|running|vo2', 1.5)],
'curiosities': [
 (r'science|scientist|physics|space\b|nasa|universe|planet|history|historical|ancient|engineering|invention|museum|did you know|fact\b|facts|study finds|researchers|geography|map\b|population|war\b|president|trump|politic|government|election|europe|china|russia|ukraine', 1.5)],
'humor': [
 (r'😂|🤣|lol\b|lmao|funny|hilarious|meme|joke|\bdog\b|dogs|puppy|cat\b|cats|kitten|animal|bird|wholesome|no context|wtf|💀', 2)],
}
# Author priors: account -> tag (applied with weight 2.5, plus learned priors from tagged posts)
AUTHOR = {
 'interiorsuckerr':'home','interiorstellar':'home','INTERIORPORN1':'home','HomeAdore':'home','ajisafeolumuyi2':'home','Arcfunmi':'home','SabrimaHomes':'home',
 'TimurNegru':'property','em3dia':'travel','MozartCultures':'travel','echoesofworld':'travel','earthpix':'travel','mamboitaliano__':'travel',
 'mattpocockuk':'ai-coding','steipete':'ai-coding','bcherny':'ai-coding','trq212':'ai-coding','ClaudeDevs':'ai-coding','claudeai':'ai-coding','thsottiaux':'ai-coding','OpenAIDevs':'ai-coding','RayFernando1337':'ai-coding','dani_avila7':'ai-coding','kunchenguid':'ai-coding','ericzakariasson':'ai-coding','badlogicgames':'ai-coding','thdxr':'ai-coding',
 'rileybrown':'product','PrajwalTomar_':'product','gregisenberg':'product','levelsio':'product','jackfriks':'product','natiakourdadze':'product','Siron93':'product',
 'egeberkina':'ai-creative','thealepalombo':'ai-creative','venturetwins':'ai-creative','4AAAAart':'ai-creative',
 'LynAldenContact':'investing','TylerDurden':'investing','moninvestor':'investing','CryptoCred':'investing','athuinvests':'investing',
 'elonmusk':'tesla','TastyUK':'lifestyle','Rainmaker1973':'curiosities','JamesLucasIT':'travel','__iffff':'home','visualsofearth1':'travel','Ortgeist':'travel','italianhouses':'property','RikiRealEstate':'property','summer_food':'lifestyle','DiscussingFilm':'movies','TheFigen_':'humor','HumansNoContext':'humor','awkwardgoogle':'humor',
 '1scene01':'movies','SahilBloom':'productivity','BookNoteApp':'productivity',
}
