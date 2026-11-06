#!/usr/bin/env python3
"""CERCA CANALI PER TEMA (gratis, solo lettura su YouTube): trova i canali che vanno forte su un argomento.
PAYLOAD = {"nome": "storia_paesi", "ricerche": ["entire history of", ...], "filtro": "regex titoli del filone", "escludi": ["UC..."]}
Per ogni canale: iscritti, video, data di nascita, quanti video sono del filone, visualizzazioni medie del filone,
visualizzazioni dei video del filone usciti negli ultimi 90 giorni, i 3 video del filone piu' visti.
Uscita: prove_video/ricerca/<nome>/report.md (+ dati.json)."""
import datetime as dt, json, os, re, statistics, urllib.parse, urllib.request

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_video', 'ricerca', P.get('nome') or 'ricerca'); os.makedirs(CART, exist_ok=True)
FILTRO = re.compile(P.get('filtro') or '.', re.I)
ORA = dt.datetime.now(dt.timezone.utc)


def get(u, dati=None, h=None):
    with urllib.request.urlopen(urllib.request.Request(u, data=dati, headers=h or {}), timeout=120) as r:
        return json.loads(r.read().decode() or '{}')


T = get('https://oauth2.googleapis.com/token', urllib.parse.urlencode({
    'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': E('YT_REFRESH_TOKEN', ''),
    'grant_type': 'refresh_token'}).encode())['access_token']
H = {'Authorization': 'Bearer ' + T}
yt = lambda path, **q: get('https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(q), h=H)

trovati = {}
dopo = (ORA - dt.timedelta(days=int(P.get('giorni') or 365))).strftime('%Y-%m-%dT%H:%M:%SZ')
for q in P.get('ricerche', []):
    for ordine in ('viewCount', 'relevance'):
        try:
            r = yt('search', part='snippet', q=q, type='video', order=ordine, maxResults=50, publishedAfter=dopo, videoDuration='medium')
        except Exception as e:
            print('ricerca non riuscita', q, e); continue
        for it in r.get('items', []):
            cid = it['snippet']['channelId']
            trovati.setdefault(cid, set()).add(q)
escludi = set(P.get('escludi') or [])
ids = [c for c in trovati if c not in escludi]
print('canali trovati:', len(ids))
canali = []
for i in range(0, len(ids), 50):
    canali += yt('channels', part='snippet,statistics,contentDetails', id=','.join(ids[i:i + 50]), maxResults=50).get('items', [])
out = []
for c in canali:
    st = c.get('statistics', {}); up = c['contentDetails']['relatedPlaylists']['uploads']
    video, tok = [], None
    for _ in range(4):   # fino a 200 video
        q = dict(part='contentDetails', playlistId=up, maxResults=50)
        if tok:
            q['pageToken'] = tok
        try:
            r = yt('playlistItems', **q)
        except Exception:
            break
        video += [x['contentDetails']['videoId'] for x in r.get('items', [])]
        tok = r.get('nextPageToken')
        if not tok:
            break
    det = []
    for i in range(0, len(video), 50):
        det += yt('videos', part='snippet,statistics,contentDetails', id=','.join(video[i:i + 50])).get('items', [])
    lunghi = [v for v in det if not re.match(r'PT(\d+S|[0-2]M\d*S?)$', v['contentDetails']['duration'])]   # niente Short / sotto i 3 min
    fil = [v for v in lunghi if FILTRO.search(v['snippet']['title'])]
    if not fil:
        continue
    vis = lambda v: int(v.get('statistics', {}).get('viewCount', 0))
    recenti = [v for v in fil if (ORA - dt.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))).days <= 90]
    nascita = c['snippet'].get('publishedAt', '')[:10]
    out.append({'id': c['id'], 'nome': c['snippet']['title'], 'link': 'https://www.youtube.com/' + (c['snippet'].get('customUrl') or 'channel/' + c['id']),
                'lingua': c['snippet'].get('defaultLanguage') or '', 'paese': c['snippet'].get('country') or '',
                'iscritti': int(st.get('subscriberCount', 0)), 'video_totali': int(st.get('videoCount', 0)), 'nato': nascita,
                'video_lunghi': len(lunghi), 'video_filone': len(fil), 'quota_filone': round(len(fil) / max(1, len(lunghi)) * 100),
                'media_filone': int(statistics.median([vis(v) for v in fil])), 'filone_90gg': len(recenti),
                'views_filone_90gg': sum(vis(v) for v in recenti), 'media_filone_90gg': int(statistics.median([vis(v) for v in recenti])) if recenti else 0,
                'top': [(v['snippet']['title'], vis(v), v['id']) for v in sorted(fil, key=vis, reverse=True)[:3]]})
out.sort(key=lambda x: (x['media_filone_90gg'], x['media_filone']), reverse=True)
json.dump(out, open(os.path.join(CART, 'dati.json'), 'w'), ensure_ascii=False, indent=1)
righe = [f"# Canali sul tema: {P.get('nome')} ({ORA:%d/%m/%Y})", '',
         '| Canale | Iscritti | Nato | Video filone / lunghi | Mediana views filone | Filone ultimi 90 gg (n / mediana) | Video più visto del filone |', '|---|---|---|---|---|---|---|']
for x in out:
    t = x['top'][0]
    righe.append(f"| [{x['nome']}]({x['link']}) {x['paese']} | {x['iscritti']:,} | {x['nato']} | {x['video_filone']} / {x['video_lunghi']} ({x['quota_filone']}%) | {x['media_filone']:,} | {x['filone_90gg']} / {x['media_filone_90gg']:,} | {t[0][:70]} ({t[1]:,}) |")
open(os.path.join(CART, 'report.md'), 'w').write('\n'.join(righe) + '\n')
print('\n'.join(righe[:40]))
