#!/usr/bin/env python3
"""SPOSTA L'USCITA di un video gia' caricato (gratis): nuova data di pubblicazione su YouTube e nel file di produzione.
La riga del foglio prende come data_inizio_produzione il giorno della nuova uscita: cosi' quel giorno l'avvio dei canali
lo conta come video del giorno e non ne produce un altro."""
import datetime as dt, json, os, sys, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
E = os.environ.get
vid, quando = E('VIDEO_ID').strip(), E('QUANDO').strip()   # QUANDO in ora italiana: 2026-11-05 17:00
PRIVATO = quando.lower() == 'privato'   # 11 nov: QUANDO = privato -> il video diventa privato senza nessuna uscita programmata
q = None if PRIVATO else dt.datetime.strptime(quando, '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('Europe/Rome'))
tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
    'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()), timeout=30).read())['access_token']
H = {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'}
v = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/youtube/v3/videos?part=status&id={vid}', headers=H), timeout=30).read())['items'][0]
st = v['status']
if PRIVATO:
    st['privacyStatus'] = 'private'; st['publishAt'] = None   # null = toglie l'uscita programmata
else:
    st.update(privacyStatus='private', publishAt=q.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
r = json.loads(urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=status', data=json.dumps({'id': vid, 'status': st}).encode(), headers=H, method='PUT'), timeout=30).read())
print('YouTube:', vid, 'esce', r['status'].get('publishAt'), '| privacy', r['status'].get('privacyStatus'))
fid = E('FOGLIO', '').strip()
if fid and not PRIVATO:
    sch, h, prod = A.righe(fid)
    n = next((i + 2 for i, x in enumerate(prod) if str(x.get('youtube_video_id') or '').strip() == vid), None)
    if n:
        val = {'data_pubblicazione': quando, 'data_inizio_produzione': q.replace(hour=0, minute=30).strftime('%Y-%m-%d %H:%M:%S')}
        A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
            {'range': f"'{sch}'!{A.lettera(h.index(c) + 1)}{n}", 'values': [[x]]} for c, x in val.items() if c in h]})
        print('foglio: riga', n, val)
    else:
        print('foglio: video non trovato nel file di produzione')
