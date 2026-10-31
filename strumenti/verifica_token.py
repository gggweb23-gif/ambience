#!/usr/bin/env python3
"""Verifica GRATUITA di un token YouTube: su quale canale apre e con quali permessi. Non stampa mai il token."""
import json, os, urllib.parse, urllib.request
E = os.environ.get
def post(u, d):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, data=urllib.parse.urlencode(d).encode()), timeout=30).read())
def get(u, tk):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'Authorization': 'Bearer ' + tk}), timeout=30).read())
righe = [f"segreto: {E('NOME')}"]
try:
    t = post('https://oauth2.googleapis.com/token', {'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'),
                                                       'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'})
    tk = t['access_token']
    righe.append('permessi: ' + ' '.join(s.rsplit('/', 1)[-1] for s in t.get('scope', '').split()))
    c = get('https://www.googleapis.com/youtube/v3/channels?part=snippet,brandingSettings,statistics&mine=true', tk).get('items', [])
    for x in c:
        s = x['snippet']; b = x.get('brandingSettings', {}).get('channel', {})
        righe.append(f"canale: {s.get('title')} | handle: {s.get('customUrl')} | id: {x['id']} | paese: {s.get('country') or b.get('country')} | lingua: {s.get('defaultLanguage') or b.get('defaultLanguage')} | iscritti: {x.get('statistics', {}).get('subscriberCount')}")
        righe.append(f"descrizione: {s.get('description', '')[:120]!r} | parole chiave: {b.get('keywords', '')[:120]!r}")
    if not c:
        righe.append('ATTENZIONE: il token non apre nessun canale')
except Exception as e:
    righe.append('ERRORE: ' + str(e)[:200])
print('\n'.join(righe))
open('verifica_token.txt', 'w').write('\n'.join(righe) + '\n')
