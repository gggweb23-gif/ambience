#!/usr/bin/env python3
"""Elimina da YouTube gli Short indicati (ID separati da virgola) di un canale. Solo per correggere errori."""
import os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import performance as PF
import dichiarazioni_yt as DICH
E = os.environ.get
if not DICH.finestra_ok():   # 8 nov: cancellazioni solo dopo le 09:00 (la quota della notte serve ai caricamenti)
    print('Prima delle 09:00: niente cancellazioni, rilanciare dopo le 09:00 (oppure FORZA_QUOTA=SI)'); sys.exit(0)
cid = E('CANALE', '').strip()
chiave = {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid) or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
tk = PF.token(E(chiave))[0]
for vid in [x.strip() for x in E('IDS', '').split(',') if x.strip()]:
    try:
        urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?id=' + vid, method='DELETE', headers={'Authorization': 'Bearer ' + tk}), timeout=60)
        print('eliminato', vid)
    except Exception as e:
        print('NON eliminato', vid, e)

# 7 nov: link al video intero sbagliato nella descrizione di uno Short -> LINK="idShort=idVideoGiusto,..." lo corregge; CONTROLLA=SI elenca Short e video collegato
import json, urllib.parse
H = {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'}
g = lambda p, **q: json.loads(urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/' + p + '?' + urllib.parse.urlencode(q), headers=H), timeout=60).read())
for coppia in [x.strip() for x in E('LINK', '').split(',') if '=' in x]:
    sid, giusto = [y.strip() for y in coppia.split('=')]
    v = g('videos', part='snippet', id=sid)['items'][0]; sn = v['snippet']
    nuova = re.sub(r'youtu\.be/[\w-]{11}', 'youtu.be/' + giusto, sn.get('description', ''))
    corpo = {'id': sid, 'snippet': {k: sn[k] for k in ('title', 'categoryId', 'tags', 'defaultLanguage', 'defaultAudioLanguage') if k in sn}}
    corpo['snippet']['description'] = nuova
    urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=snippet', method='PUT', data=json.dumps(corpo).encode(), headers=H), timeout=60)
    print('link corretto', sid, '->', giusto)
for coppia in [x for x in E('TITOLO', '').split('||') if '=' in x]:   # TITOLO="idShort=Titolo giusto||..."
    sid, nuovo = coppia.split('=', 1); sid = sid.strip()
    sn = g('videos', part='snippet', id=sid)['items'][0]['snippet']
    corpo = {'id': sid, 'snippet': {k: sn[k] for k in ('categoryId', 'tags', 'defaultLanguage', 'defaultAudioLanguage', 'description') if k in sn}}
    corpo['snippet']['title'] = nuovo.strip()
    urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=snippet', method='PUT', data=json.dumps(corpo).encode(), headers=H), timeout=60)
    print('titolo corretto', sid, '->', nuovo.strip())
if E('CONTROLLA', '').upper() == 'SI':
    up = g('channels', part='contentDetails', mine='true')['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids = [x['contentDetails']['videoId'] for x in g('playlistItems', part='contentDetails', playlistId=up, maxResults=50).get('items', [])]
    vs = g('videos', part='snippet,contentDetails', id=','.join(ids)).get('items', [])
    titoli = {v['id']: v['snippet']['title'] for v in vs}
    for v in vs:
        if '#shorts' in v['snippet']['title']:
            m = re.search(r'youtu\.be/([\w-]{11})', v['snippet'].get('description', ''))
            lk = m.group(1) if m else ''
            print(v['id'], '|', v['snippet']['title'][:60], '->', lk, '|', titoli.get(lk, '(non tra gli ultimi 50)')[:70])
