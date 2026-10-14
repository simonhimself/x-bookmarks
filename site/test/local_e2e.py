#!/usr/bin/env python3
"""End-to-end test against `wrangler dev --local --test-scheduled` + test/mock_youtube.mjs (see test/README.md).
Never talks to Google or the live D1."""
import json,os,re,subprocess,sys,urllib.request,urllib.error,http.cookiejar
B=os.environ.get('BASE','http://localhost:8787'); M=os.environ.get('MOCK','http://127.0.0.1:8789')
PERSIST=os.environ['PERSIST']; HERE=os.path.dirname(os.path.abspath(__file__))
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
fails=[]
def ok(c,msg):
    print(('PASS ' if c else 'FAIL ')+msg); (None if c else fails.append(msg))
def req(path,method='GET',body=None,headers=None,opener=op):
    r=urllib.request.Request(B+path if path.startswith('/') else path,data=None if body is None else json.dumps(body).encode(),method=method,headers=headers or {})
    try:
        with opener.open(r) as x: return x.status,x.read().decode(),dict(x.headers)
    except urllib.error.HTTPError as e: return e.code,e.read().decode(),dict(e.headers)
def sql(q):
    out=subprocess.check_output(['wrangler','d1','execute','x-bookmarks','--local','--persist-to',PERSIST,'--json','--command',q],cwd=os.path.join(HERE,'..'),stderr=subprocess.DEVNULL)
    return json.loads(out)[0]['results']
J={'Content-Type':'application/json','Origin':B}
import time
def cron():
    # the scheduled handler finishes in waitUntil, so wait until a new last_run appears
    prev=(json.loads(req('/api/yt/status')[1]).get('last_run') or {}).get('at')
    req('/__scheduled?cron=*/10+*+*+*+*')
    for _ in range(100):
        time.sleep(0.15); lr=json.loads(req('/api/yt/status')[1]).get('last_run') or {}
        if lr.get('at')!=prev: return
        if not json.loads(req('/api/yt/status')[1])['connected']: return

# 1. not connected: cron is a no-op
cron(); ok(json.loads(req('/api/yt/status')[1])['connected'] is False,'status: not connected before OAuth')
ok(json.loads(req('/api/yt/status')[1]).get('last_run') is None,'cron does nothing while not connected')
# 2. OAuth: bad state refused
c,b,_=req('/oauth/youtube/callback?code=mockcode&state=forged'); ok(c==400 and 'expired' in b,'callback refuses a state that has no matching cookie')
# 3. OAuth happy path (start -> mock consent -> callback)
c,b,_=req('/oauth/youtube/start'); ok(c==200 and 'YouTube connected' in b and 'Simon (demo)' in b,'OAuth start -> consent -> callback connects')
rt=sql("SELECT k, v FROM yt_oauth ORDER BY k")
ok(any(r['k']=='refresh_token' and r['v'].startswith('v1.') and 'mock-refresh-token' not in r['v'] for r in rt),'refresh token stored AES-GCM sealed, not in plain text')
# 4. CSRF guards on writes
c,_,_=req('/api/yt/sync','POST',{},{'Content-Type':'application/json','Origin':'https://evil.example'}); ok(c==403,'sync refuses cross-origin POST')
c,_,_=req('/api/star','POST',{'id':'v000000____'},{'Content-Type':'text/plain','Origin':B}); ok(c==403,'star refuses non-JSON POST')
c,_,_=req('/api/star','GET'); ok(c==405,'GET /api/star is 405')
# 5. cron batches until the day's cycle is done
runs=[];
for i in range(60):
    cron(); s=json.loads(req('/api/yt/status')[1]); runs.append(s['last_run'])
    if s['state']['phase']=='done': break
ok(all(r['error'] is None for r in runs),'no sync errors (%d runs)'%len(runs))
mx=max(r['subrequests'] for r in runs); ok(mx<=40,'max subrequests per run = %d (budget 40, Free plan limit 50)'%mx)
ok(s['state']['phase']=='done','cycle finished in %d cron runs'%len(runs))
n=sql("SELECT COUNT(*) n, SUM(is_short) sh, SUM(sources LIKE '%\"sub\"%') sub, SUM(sources LIKE '%\"like\"%') lk, SUM(sources LIKE '%pl:%') pl, SUM(needs_details) pend, SUM(tags IS NULL) untagged FROM videos")[0]
print('     videos:',n)
ok(n['sub']==600,'first sync took the last 10 uploads of each of 60 channels (%s)'%n['sub'])
ok(n['lk']==70,'all 70 likes imported (%s)'%n['lk'])
ok(n['pl']>0 and n['pend']==0 and n['untagged']==0,'playlists imported, all videos detailed and tagged')
ok(n['sh']>0,'Shorts detected (%s)'%n['sh'])
quota=json.loads(req('/api/yt/status')[1])['quota']; print('     quota units used:',quota)
# 6. tags make sense on the made-up titles
t=sql("SELECT title, primary_tag FROM videos WHERE title LIKE 'Building a raised bed%' LIMIT 1")[0]; ok(t['primary_tag']=='home','"%s" -> %s'%(t['title'],t['primary_tag']))
t=sql("SELECT title, primary_tag FROM videos WHERE title LIKE 'Claude Code subagents%' LIMIT 1")[0]; ok(t['primary_tag']=='ai-coding','"%s" -> %s'%(t['title'],t['primary_tag']))
# 7. /api/videos + ETag
c,b,h=req('/api/videos'); j=json.loads(b); ok(c==200 and len(j['items'])==n['n'],'/api/videos returns %d items'%len(j['items']))
c2,_,_=req('/api/videos',headers={'If-None-Match':h['ETag']}); ok(c2==304,'ETag -> 304')
# 8. stars
vid=j['items'][0]['i']
c,b,_=req('/api/star','POST',{'id':vid},J); ok(c==200,'star a video')
c,b,_=req('/api/star','POST',{'id':'nope'},J); ok(c==400,'invalid id refused')
c,b,_=req('/api/videos'); ok([x for x in json.loads(b)['items'] if x['i']==vid][0]['st'],'star shows in /api/videos (version bumped)')
c,b,_=req('/api/unstar','POST',{'id':vid},J); ok(c==200 and not [x for x in json.loads(req('/api/videos')[1])['items'] if x['i']==vid][0]['st'],'unstar')
req('/api/star','POST',{'id':vid},J)
# 9. next day: unsubscribed channel kept; incremental sync only checks for new uploads
sql("UPDATE meta SET v=json_set(v,'$.day','2000-01-01') WHERE k='yt_state'")
sql("UPDATE yt_channels SET seen_day='2000-01-01', checked_day='2000-01-01'")
sql("INSERT INTO yt_channels(id,title,uploads_playlist,subscribed,seen_day) VALUES('UCgoneChannelxxxxxxxxxxx','Gone','UUgoneChannelxxxxxxxxxxx',1,'2000-01-01')")
before=n['n']; runs=[]
for i in range(30):
    cron(); s=json.loads(req('/api/yt/status')[1]); runs.append(s['last_run'])
    if s['state']['phase']=='done': break
n2=sql("SELECT COUNT(*) n FROM videos")[0]['n']
ok(n2==before,'next day: no duplicates, %d videos (was %d)'%(n2,before))
ok(sql("SELECT subscribed FROM yt_channels WHERE id='UCgoneChannelxxxxxxxxxxx'")[0]['subscribed']==0,'channel missing from subscriptions is flagged unsubscribed, not deleted')
calls=sum(r['calls'] for r in runs); ok(calls<=70,'incremental day used %d API units (2 sub pages + 60 channels + likes + playlists)'%calls)
# 10. access token refresh path used the refresh token
log=json.loads(urllib.request.urlopen(M+'/__log').read()); 
ok(not any(e['p'].startswith('/yt/search') for e in log),'never calls search.list')
print('\n%d failures'%len(fails)); sys.exit(1 if fails else 0)
