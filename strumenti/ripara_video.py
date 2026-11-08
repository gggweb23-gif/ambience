#!/usr/bin/env python3
"""RIPARA UN VIDEO GIA' CARICATO (gratis, per tutti i canali): copertina e/o playlist rimaste indietro
(es. quota YouTube esaurita durante il caricamento). Env: VIDEO_ID, COPERTINA (percorso nel repository, facoltativo),
PLAYLIST (nome, facoltativo; la crea se manca), YT_CLIENT_ID/SECRET, YT_REFRESH_TOKEN (segreto del canale)."""
import json, os, sys, time, urllib.parse, urllib.request

E = os.environ.get
VID, COP, PL = E('VIDEO_ID', '').strip(), E('COPERTINA', '').strip(), E('PLAYLIST', '').strip()
d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                            'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
tok = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60).read())['access_token']
H = {'Authorization': 'Bearer ' + tok}


def api(url, corpo=None, tipo='application/json'):
    dati = corpo if isinstance(corpo, bytes) else (json.dumps(corpo).encode() if corpo is not None else None)
    req = urllib.request.Request(url, data=dati, headers=dict(H, **({'Content-Type': tipo} if dati else {})), method='POST' if dati else 'GET')
    return json.loads(urllib.request.urlopen(req, timeout=120).read() or b'{}')


errori = 0
if COP:
    try:
        dati = urllib.request.urlopen(COP, timeout=120).read() if COP.startswith('http') else open(COP, 'rb').read()   # percorso nel repository oppure indirizzo (es. fal)
        api(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={VID}', dati, 'image/png' if dati[:4] == b'\x89PNG' else 'image/jpeg')
        print('copertina caricata:', COP)
    except Exception as e:
        errori += 1; print('copertina NON caricata:', e, getattr(e, 'read', lambda: b'')().decode()[:200])
if PL:
    try:
        tutte = api('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50').get('items', [])
        pid = next((p['id'] for p in tutte if p['snippet']['title'].strip().lower() == PL.lower()), None)
        if not pid:
            pid = api('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': PL}, 'status': {'privacyStatus': 'public'}})['id']
            print('playlist creata:', PL); time.sleep(8)
        api('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': VID}}})
        print('video aggiunto alla playlist:', PL)
    except Exception as e:
        errori += 1; print('playlist NON aggiornata:', e, getattr(e, 'read', lambda: b'')().decode()[:200])
sys.exit(1 if errori else 0)
