#!/usr/bin/env python3
"""DESCRIZIONE E PAROLE CHIAVE DEL CANALE (gratis, 21 nov 2026): aggiorna la descrizione (e le parole chiave) di un canale YouTube
mantenendo tutte le altre impostazioni del canale. Env: YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET, DESCRIZIONE, PAROLE_CHIAVE (facoltativo)."""
import json, os, urllib.parse, urllib.request

E = os.environ.get


def http(u, dati=None, tk=None, metodo=None, form=False):
    h = {'Authorization': 'Bearer ' + tk} if tk else {}
    if dati is not None:
        body = urllib.parse.urlencode(dati).encode() if form else json.dumps(dati).encode()
        h['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    else:
        body = None
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, data=body, headers=h, method=metodo), timeout=60).read())


tk = http('https://oauth2.googleapis.com/token', {'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'),
                                                   'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}, form=True)['access_token']
c = http('https://www.googleapis.com/youtube/v3/channels?part=brandingSettings,snippet&mine=true', tk=tk)['items'][0]
b = c.get('brandingSettings', {}); ch = b.setdefault('channel', {})
ch['description'] = E('DESCRIZIONE', '').replace('\\n', '\n')
if E('PAROLE_CHIAVE'):
    ch['keywords'] = ' '.join('"' + k.strip() + '"' if ' ' in k.strip() else k.strip() for k in E('PAROLE_CHIAVE').split(',') if k.strip())
r = http('https://www.googleapis.com/youtube/v3/channels?part=brandingSettings', {'id': c['id'], 'brandingSettings': b}, tk=tk, metodo='PUT')
print('canale:', c['snippet']['title'], '| descrizione aggiornata:', r['brandingSettings']['channel'].get('description', '')[:80], '...')
print('parole chiave:', r['brandingSettings']['channel'].get('keywords', '')[:200])
