#!/usr/bin/env python3
"""Rifa' con lo stile "foto simbolo" (copertina_foto.py) le copertine dei video GIA' presenti in un canale e le carica su YouTube.
PAYLOAD = {"lingua": "it", "carica": "SI", "solo": ["id1", ...] (vuoto = tutti), "escludi": [...], "cartella": "prove_video/Storia_in_Minuti/copertine_canale"}
Ogni copertina caricata viene salvata anche in copertine_storia/<id>_1.jpg (cosi' "Copertine Storia" non la rifa')."""
import json, os, shutil, sys, urllib.parse, urllib.request
sys.path.insert(0, os.getcwd())
import copertina_foto as CF

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = P.get('cartella') or 'prove_video/copertine_canale'; os.makedirs(CART, exist_ok=True)


def token():
    d = urllib.parse.urlencode({'client_id': os.environ['YT_CLIENT_ID'], 'client_secret': os.environ['YT_CLIENT_SECRET'],
                                'refresh_token': os.environ['YT_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
    return json.loads(urllib.request.urlopen('https://oauth2.googleapis.com/token', d, timeout=60).read())['access_token']


T = token(); H = {'Authorization': 'Bearer ' + T}


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60).read())


up = get('https://www.googleapis.com/youtube/v3/channels?part=contentDetails,snippet&mine=true')['items'][0]
print('canale:', up['snippet']['title'])
lista, pg = [], ''
while True:
    r = get('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode(
        {'part': 'snippet', 'playlistId': up['contentDetails']['relatedPlaylists']['uploads'], 'maxResults': 50, 'pageToken': pg}))
    lista += [(x['snippet']['resourceId']['videoId'], x['snippet']['title']) for x in r.get('items', [])]
    pg = r.get('nextPageToken') or ''
    if not pg:
        break
solo, escludi = set(P.get('solo') or []), set(P.get('escludi') or [])
esiti = []
for vid, titolo in lista:
    if (solo and vid not in solo) or vid in escludi:
        continue
    path = os.path.join(CART, f'{vid}.jpg')
    try:
        if not CF.crea(titolo, P.get('lingua') or 'it', path):
            esiti.append(f'{vid} | {titolo} | NESSUNA FOTO superata al controllo: copertina lasciata com\'era'); continue
    except Exception as e:
        esiti.append(f'{vid} | {titolo} | errore: {str(e)[:150]}'); continue
    stato = 'creata (non caricata)'
    if str(P.get('carica') or 'NO').upper() == 'SI':
        try:
            req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', data=open(path, 'rb').read(),
                                         method='POST', headers={**H, 'Content-Type': 'image/jpeg'})
            urllib.request.urlopen(req, timeout=120).read(); stato = 'CARICATA'
            os.makedirs('copertine_storia', exist_ok=True); shutil.copy(path, os.path.join('copertine_storia', f'{vid}_1.jpg'))
        except Exception as e:
            stato = 'NON caricata: ' + str(e)[:150]
    esiti.append(f'{vid} | {titolo} | {stato}')
    print(esiti[-1])
open(os.path.join(CART, 'esito.txt'), 'w').write('\n'.join(esiti) + '\n')
open(os.path.join(CART, 'controlli.txt'), 'w').write('\n'.join(CF.REGISTRO) + '\n')
print('\n'.join(esiti))
