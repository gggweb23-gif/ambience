#!/usr/bin/env python3
"""Elimina da YouTube gli Short indicati (ID separati da virgola) di un canale. Solo per correggere errori."""
import os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import performance as PF
E = os.environ.get
cid = E('CANALE', '').strip()
chiave = {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid) or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
tk = PF.token(E(chiave))[0]
for vid in [x.strip() for x in E('IDS', '').split(',') if x.strip()]:
    try:
        urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?id=' + vid, method='DELETE', headers={'Authorization': 'Bearer ' + tk}), timeout=60)
        print('eliminato', vid)
    except Exception as e:
        print('NON eliminato', vid, e)
