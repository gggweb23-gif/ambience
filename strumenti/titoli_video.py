#!/usr/bin/env python3
"""11 nov (Giorgio): cambia il titolo di video gia' pubblicati mantenendo le regole di caricamento:
il titolo resta la prima riga della descrizione e uno dei tag. Gratis (solo quota YouTube).
Ingresso (env): YT_REFRESH_TOKEN, CAMBI = JSON [{"video_id", "titolo"}]; con CAMBI vuoto elenca gli ultimi video del canale."""
import json, os, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import performance as PF
E = os.environ.get
h = {'Authorization': 'Bearer ' + PF.token(E('YT_REFRESH_TOKEN'))[0]}
def api(p, q, corpo=None):
    r = urllib.request.Request('https://www.googleapis.com/youtube/v3/' + p + '?' + urllib.parse.urlencode(q),
                               data=json.dumps(corpo).encode() if corpo else None, headers=dict(h, **({'Content-Type': 'application/json'} if corpo else {})),
                               method='PUT' if corpo else 'GET')
    return json.loads(urllib.request.urlopen(r, timeout=60).read())
cambi = json.loads(E('CAMBI') or '[]')
if not cambi:
    up = api('channels', {'part': 'contentDetails', 'mine': 'true'})['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids = [x['contentDetails']['videoId'] for x in api('playlistItems', {'part': 'contentDetails', 'playlistId': up, 'maxResults': 15})['items']]
    for v in api('videos', {'part': 'snippet,contentDetails', 'id': ','.join(ids)})['items']:
        if PF.secondi(v['contentDetails']['duration']) > 180:
            print(json.dumps({'id': v['id'], 'titolo': v['snippet']['title'], 'descrizione': v['snippet'].get('description', '')[:700]}, ensure_ascii=False))
for c in cambi:
    v = api('videos', {'part': 'snippet', 'id': c['video_id']})['items'][0]; s = v['snippet']
    vecchio, nuovo = s['title'], c['titolo'].strip()[:100]
    righe = (s.get('description') or '').split('\n')
    if righe and righe[0].strip().lower() == vecchio.strip().lower():
        righe[0] = nuovo
    else:
        righe = [nuovo, ''] + righe
    tag = [t for t in (s.get('tags') or []) if t.strip().lower() != vecchio.strip().lower()]
    tag = [nuovo] + [t for t in tag if t.lower() != nuovo.lower()]
    while len(','.join(tag)) > 480:
        tag.pop()
    corpo = {'id': c['video_id'], 'snippet': {'title': nuovo, 'description': '\n'.join(righe), 'tags': tag, 'categoryId': s['categoryId'],
                                              **({'defaultLanguage': s['defaultLanguage']} if s.get('defaultLanguage') else {})}}
    api('videos', {'part': 'snippet'}, corpo)
    print('TITOLO CAMBIATO', c['video_id'], '|', vecchio, '->', nuovo)
