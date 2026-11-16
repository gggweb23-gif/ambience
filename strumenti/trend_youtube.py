#!/usr/bin/env python3
"""TREND SU YOUTUBE (16 nov 2026, Giorgio: "conta sempre le views"). Per ogni argomento cerca i video pubblicati negli ultimi N giorni,
ordinati per visualizzazioni, e stampa views, eta' e views all'ora: si vede se un'onda sta salendo o e' gia' stata cavalcata.
Costo: 100 unita' di quota YouTube per argomento, sulla chiave del radar (YT_API_KEY_RADAR), non su quella dei caricamenti.
ARGOMENTI = "revolut;nvidia jensen huang;anthropic ipo", GIORNI = 7"""
import datetime as dt, json, os, urllib.parse, urllib.request
K = os.environ['YT_API_KEY_RADAR']; ora = dt.datetime.now(dt.timezone.utc)
giorni = int(os.environ.get('GIORNI') or 7)


def get(p, **q):
    q['key'] = K
    return json.loads(urllib.request.urlopen('https://www.googleapis.com/youtube/v3/' + p + '?' + urllib.parse.urlencode(q), timeout=60).read())


import time
for a in [x.strip() for x in os.environ['ARGOMENTI'].split(';') if x.strip()]:
    time.sleep(2)
    try:
        r = get('search', part='snippet', q=a, type='video', order='viewCount', maxResults=15,
            publishedAfter=(ora - dt.timedelta(days=giorni)).strftime('%Y-%m-%dT%H:%M:%SZ'), relevanceLanguage=os.environ.get('LINGUA') or 'en')
    except Exception as e:
        print(f'\n=== {a}: ricerca non riuscita ({str(e)[:80]})'); continue
    ids = [x['id']['videoId'] for x in r.get('items', [])]
    if not ids:
        print(f'\n=== {a}: nessun video'); continue
    v = get('videos', part='snippet,statistics,contentDetails', id=','.join(ids)).get('items', [])
    tot = 0; righe = []
    for x in v:
        pub = dt.datetime.fromisoformat(x['snippet']['publishedAt'].replace('Z', '+00:00')); ore = max(1, (ora - pub).total_seconds() / 3600)
        n = int(x['statistics'].get('viewCount', 0)); tot += n
        righe.append((n, f"{n:>10,} views | {ore / 24:4.1f} gg | {n / ore:>8,.0f}/ora | {x['contentDetails']['duration']:>9} | {x['snippet']['channelTitle'][:22]:22} | {x['snippet']['title'][:80]}"))
    print(f'\n=== {a}: {tot:,} views nei primi {len(v)} video degli ultimi {giorni} giorni')
    for _, t in sorted(righe, reverse=True)[:10]:
        print(t)
