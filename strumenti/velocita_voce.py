#!/usr/bin/env python3
"""VELOCITA' DELLA VOCE di alcuni video gia' pubblicati (gratis): scarica i sottotitoli automatici di YouTube (solo canali nostri)
e calcola le parole al secondo del parlato. Serve a riportare la voce alla velocita' di un video che piaceva."""
import json, os, re, urllib.parse, urllib.request
E = os.environ.get
d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()
tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=30).read())['access_token']
H = {'Authorization': 'Bearer ' + tk}
for vid in [v.strip() for v in E('VIDEO', '').split(',') if v.strip()]:
    try:
        caps = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={vid}', headers=H), timeout=30).read()).get('items', [])
        c = next((x for x in caps if x['snippet'].get('trackKind') == 'asr'), caps[0] if caps else None)
        if not c:
            print(vid, ': nessun sottotitolo'); continue
        srt = urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/youtube/v3/captions/{c["id"]}?tfmt=srt', headers=H), timeout=60).read().decode('utf-8', 'ignore')
        blocchi = re.findall(r'(\d\d):(\d\d):(\d\d),(\d+) --> (\d\d):(\d\d):(\d\d),(\d+)\s*\n(.+?)(?:\n\n|\Z)', srt, re.S)
        sec = lambda h, m, s, ms: int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        parole = sum(len(b[8].split()) for b in blocchi)
        parlato = sum(max(0, sec(*b[4:8]) - sec(*b[0:4])) for b in blocchi)
        tot = sec(*blocchi[-1][4:8]) - sec(*blocchi[0][0:4]) if blocchi else 0
        print(f'{vid} | {c["snippet"].get("language")} | parole {parole} | durata parlato {tot:.0f} s | parole al secondo {parole / tot:.2f}' if tot else vid + ': vuoto')
    except urllib.error.HTTPError as e:
        print(vid, ': errore', e.code, e.read().decode()[:200])
