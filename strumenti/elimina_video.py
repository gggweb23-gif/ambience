#!/usr/bin/env python3
"""Cancella da YouTube UN video sbagliato (solo su richiesta esplicita di Giorgio). PAYLOAD = {"video_id": "...", "motivo": "..."}"""
import json, os, time, urllib.parse, urllib.request
P = json.loads(os.environ.get('PAYLOAD') or '{}')
tk = json.loads(urllib.request.urlopen('https://oauth2.googleapis.com/token', urllib.parse.urlencode({
    'client_id': os.environ['YT_CLIENT_ID'], 'client_secret': os.environ['YT_CLIENT_SECRET'], 'refresh_token': os.environ['YT_REFRESH_TOKEN'],
    'grant_type': 'refresh_token'}).encode(), timeout=60).read())['access_token']
req = urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?id=' + P['video_id'], method='DELETE', headers={'Authorization': 'Bearer ' + tk})
urllib.request.urlopen(req, timeout=60)
riga = time.strftime('%Y-%m-%d %H:%M') + f" cancellato {P['video_id']} | {P.get('motivo', '')}"
print(riga); os.makedirs('coach', exist_ok=True); open('coach/video_cancellati.log', 'a').write(riga + '\n')
