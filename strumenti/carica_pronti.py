#!/usr/bin/env python3
"""CARICA SU YOUTUBE I VIDEO "DA CARICARE A MANO" GIA' PRONTI (9 nov, Giorgio: basta caricare a mano, carica tu).
Per un canale: prende video e copertina dall'artifact "DA CARICARE <canale>" (scaricato in pronti/), la riga del file di produzione
in stato "Da caricare a mano" con lo stesso titolo, e carica con titolo, descrizione, tag, playlist e orario di uscita della riga.
Utilizzo dell'AI = No e promozione a pagamento = No nel caricamento. Poi trova_caricati scrive youtube_video_id e Completato."""
import datetime as dt, glob, json, os, re, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import dichiarazioni_yt as DICH

E = os.environ.get
CANALE = E('CANALE', '').strip()
ROMA = ZoneInfo('Europe/Rome')
nome = lambda t: re.sub(r'[^A-Za-z0-9]+', '_', str(t or '')).strip('_').lower()

cfg = next(x for x in A.righe(A.CONFIGS)[2] if str(x.get('channel_id') or '').strip() == CANALE)
_, h, prod = A.righe(str(cfg.get('scout_production_sheet_id') or '').strip())
video = [f for f in glob.glob('pronti/**/*.mp4', recursive=True)]
print('file nell artifact:', [os.path.basename(f) for f in video], flush=True)

d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                            'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
tok = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60).read())['access_token']
H = {'Authorization': 'Bearer ' + tok}


def api(url, corpo=None, tipo='application/json', metodo=None):
    dati = corpo if isinstance(corpo, bytes) else (json.dumps(corpo).encode() if corpo is not None else None)
    req = urllib.request.Request(url, data=dati, headers=dict(H, **({'Content-Type': tipo} if dati else {})), method=metodo or ('POST' if dati else 'GET'))
    return json.loads(urllib.request.urlopen(req, timeout=600).read() or b'{}')


fatti = 0
RIGA = int(E('RIGA') or 0)   # 12 nov: ricarica di UNA riga precisa (es. video gia' fatto ma cancellato da YouTube per sbaglio), qualunque sia lo stato
for k_, r in enumerate(prod):
    if RIGA:
        if k_ + 2 != RIGA:
            continue
    elif str(r.get('status') or '').strip() != 'Da caricare a mano' or str(r.get('youtube_video_id') or '').strip():
        continue
    tit = str(r.get('titolo_italiano') or '').strip()
    f = next((v for v in video if nome(tit)[:60] and nome(os.path.basename(v)).find(nome(tit)[:40]) >= 0), None)
    if not f and len(video) == 1:
        f = video[0]
    if not f:
        print('manca il file per:', tit, flush=True); continue
    q = dt.datetime.fromisoformat(str(r.get('data_pubblicazione') or '').strip()[:16]).replace(tzinfo=ROMA)
    if q < dt.datetime.now(ROMA) + dt.timedelta(minutes=20):
        q = dt.datetime.now(ROMA) + dt.timedelta(minutes=30)
    tags = [t.strip() for t in str(r.get('tag_seo') or '').split(',') if t.strip()]
    corpo = {'snippet': {'title': tit[:100], 'description': str(r.get('descrizione_youtube') or ''), 'tags': tags[:40],
                         'categoryId': str(cfg.get('youtube_category_id') or cfg.get('categoria') or 27), 'defaultLanguage': str(cfg.get('language') or 'en')[:2],
                         'defaultAudioLanguage': str(cfg.get('language') or 'en')[:2]},
             'status': {'privacyStatus': 'private', 'publishAt': q.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}}
    loc = DICH.sessione('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', corpo,
                        dict(H, **{'Content-Type': 'application/json', 'X-Upload-Content-Type': 'video/mp4'}))
    ris = json.loads(urllib.request.urlopen(urllib.request.Request(loc, data=open(f, 'rb').read(), method='PUT',
                                                                   headers={'Content-Type': 'video/mp4'}), timeout=1800).read())
    vid = ris['id']
    print('caricato', vid, '|', tit, '| esce', q.strftime('%d/%m %H:%M'), flush=True)
    DICH.nessuna_promozione(vid, tok, ris)
    cop = next((c for c in glob.glob('pronti/**/*.jpg', recursive=True) if nome(os.path.basename(c)).startswith(nome(os.path.basename(f))[:-4][:50])), None) \
        or (glob.glob('pronti/**/*.jpg', recursive=True) or [None])[0]
    if E('COPERTINA_REPO'):
        cop = E('COPERTINA_REPO')
        if cop.startswith('http'):
            open('copertina_link.jpg', 'wb').write(urllib.request.urlopen(urllib.request.Request(cop, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read()); cop = 'copertina_link.jpg'
    try:
        api(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', open(cop, 'rb').read(), 'image/jpeg'); print('copertina:', cop, flush=True)
    except Exception as e:
        print('copertina NON caricata:', e, flush=True)
    pl = str(r.get('playlist') or '').strip()
    if pl:
        try:
            tutte = api('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50').get('items', [])
            pid = next((p['id'] for p in tutte if p['snippet']['title'].strip().lower() == pl.lower()), None)
            if not pid:
                pid = api('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': pl}, 'status': {'privacyStatus': 'public'}})['id']; time.sleep(8)
            api('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}})
            print('playlist:', pl, flush=True)
        except Exception as e:
            print('playlist NON aggiornata:', e, flush=True)
    if RIGA:   # nuovo id nella riga del file di produzione
        try:
            sch_ = A.righe(str(cfg.get('scout_production_sheet_id') or '').strip())[0]
            A.api(str(cfg.get('scout_production_sheet_id') or '').strip(), 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
                {'range': f"'{sch_}'!{A.lettera(h.index('youtube_video_id') + 1)}{RIGA}", 'values': [[vid]]}]})
            print('foglio: riga', RIGA, 'youtube_video_id =', vid, flush=True)
        except Exception as e:
            print('foglio NON aggiornato:', e, flush=True)
    fatti += 1
print('FATTO', CANALE, fatti, 'video caricati', flush=True)
sys.exit(0 if fatti else 1)
