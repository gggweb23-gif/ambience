#!/usr/bin/env python3
"""CARICA IL VIDEO NOTIZIA su YouTube (16 nov 2026). Regole di tutti i canali: titolo = prima riga della descrizione e primo tag,
"contenuti alterati/AI" = No, promozione a pagamento = No, copertina, playlist del filone, uscita all'ora del canale (17:00 italiane)
o subito se l'ora e' gia' passata. Nella descrizione le fonti giornalistiche (credibilita'). Il primo commento lo scrive primo_commento.yml.
Env: NOTIZIA (json del copione), VIDEO (mp4 1440p), COPERTINA, YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET, ORA_USCITA (17:00), PLAYLIST"""
import datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import descrizione as DESCR
import dichiarazioni_yt as DICH

E = os.environ.get
N = json.load(open(E('NOTIZIA')))


def log(*a):
    print(*a, flush=True)


def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': E('YT_REFRESH_TOKEN', ''),
                                'grant_type': 'refresh_token'}).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60).read())['access_token']


def api(metodo, url, dati=None, tk=None):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None, method=metodo,
                                 headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=120).read() or b'{}')


def main():
    titolo = N['titolo'][:100]
    fonti = '\n'.join('- ' + u for u in (N.get('fonti_link') or [])[:12])
    # capitoli (stile dinamico): YouTube li mostra se il primo e' 0:00 e ce ne sono almeno 3
    cap_f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'prove_video', 'notizie', N.get('nome', ''), 'capitoli.json')
    cap = json.load(open(cap_f)) if os.path.exists(cap_f) else []
    capitoli = '\n'.join(f"{c['t'] // 60}:{c['t'] % 60:02d} {c['titolo']}" for c in cap) if len(cap) >= 3 else ''
    corpo = '\n\n'.join(x for x in [titolo, N.get('descrizione', ''), capitoli, ('Sources:\n' if N.get('lingua') == 'en' else 'Fonti:\n') + fonti if fonti else ''] if x)
    descr = DESCR.con_titolo(titolo, corpo)[:4900]
    tags = DESCR.tag_con_titolo(titolo, N.get('tag') or [])
    lingua = N.get('lingua', 'en')
    ora = E('ORA_USCITA') or '17:00'
    oggi = dt.datetime.now(ZoneInfo('Europe/Rome'))
    uscita = oggi.replace(hour=int(ora[:2]), minute=int(ora[3:5]), second=0, microsecond=0)
    status = {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}
    if uscita > oggi + dt.timedelta(minutes=10):
        status['privacyStatus'] = 'private'; status['publishAt'] = uscita.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    tk = token(); size = os.path.getsize(E('VIDEO'))
    sessione = DICH.sessione('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                             {'snippet': {'title': titolo, 'description': descr, 'tags': tags, 'categoryId': '25', 'defaultLanguage': lingua, 'defaultAudioLanguage': lingua},
                              'status': status},
                             {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Length': str(size), 'X-Upload-Content-Type': 'video/mp4'}, 120)
    vid = None
    for k in range(6):
        try:
            put = urllib.request.Request(sessione, data=open(E('VIDEO'), 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'video/mp4'})
            ris = json.loads(urllib.request.urlopen(put, timeout=1800).read()); vid = ris['id']
            DICH.nessuna_promozione(vid, tk, ris); break
        except urllib.error.HTTPError as e:
            if e.code == 401:
                tk = token()
            elif e.code not in (500, 502, 503, 504):
                raise RuntimeError(f'YouTube ha rifiutato il caricamento: {e.code} ' + e.read().decode()[:300])
        except Exception as e:
            log('caricamento, riprovo:', str(e)[:120])
        time.sleep(15 * (k + 1))
    if not vid:
        raise RuntimeError('caricamento non riuscito')
    log('caricato:', vid, '| esce', status.get('publishAt') or 'subito')
    try:
        urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', data=open(E('COPERTINA'), 'rb').read(),
                                                      method='POST', headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'image/jpeg'}), timeout=120).read()
        log('copertina caricata')
    except Exception as e:
        log('copertina non caricata:', str(e)[:150])
    nome_pl = E('PLAYLIST') or ('World Conflicts Today' if N.get('filone') == 'guerra' else 'Tech News')
    try:
        pls = api('GET', 'https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', tk=tk).get('items', [])
        pid = next((p['id'] for p in pls if p['snippet']['title'].strip().lower() == nome_pl.lower()), None)
        if not pid:
            pid = api('POST', 'https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': nome_pl}, 'status': {'privacyStatus': 'public'}}, tk)['id']
        api('POST', 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}}, tk)
        log('playlist:', nome_pl)
    except Exception as e:
        log('playlist non riuscita:', str(e)[:150])
    if E('GITHUB_OUTPUT'):
        open(E('GITHUB_OUTPUT'), 'a').write(f'video_id={vid}\n')
    try:
        registra_per_shorts(vid, titolo, tags, uscita if 'publishAt' in status else oggi)
    except Exception as e:
        log('riga per gli Short non scritta:', str(e)[:200])


def registra_per_shorts(vid, titolo, tags, uscita):
    """17 nov (Giorgio: "gli Short devono partire anche sui nuovi canali"): il video notizie entra nel file di produzione del canale come riga
    Completato, cosi' shorts.yml ne taglia gli Short come per gli altri canali. Il file del video e' nell'artifact video-notizie di questo giro."""
    cid = E('CANALE_ID', '').strip()
    if not cid or not E('GOOGLE_SA_KEY'):
        return
    import avvio_canali as A
    _, _, canali = A.righe(A.CONFIGS)
    cfg = next((c for c in canali if str(c.get('channel_id') or '').strip() == cid), None)
    fid = str((cfg or {}).get('scout_production_sheet_id') or '').strip()
    if not fid:
        log('canale senza file di produzione:', cid); return
    sch, h, prod = A.righe(fid)
    for col in ('file_video',):
        if col not in h:
            pr = next(x['properties'] for x in A.api(fid, 'GET', '?fields=sheets.properties')['sheets'] if x['properties']['title'] == sch)
            if pr['gridProperties']['columnCount'] < len(h) + 1:
                A.api(fid, 'POST', ':batchUpdate', {'requests': [{'appendDimension': {'sheetId': pr['sheetId'], 'dimension': 'COLUMNS', 'length': 3}}]})
            A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!{A.lettera(len(h) + 1)}1", 'values': [[col]]}]})
            h.append(col)
    vals = {'status': 'Completato', 'youtube_video_id': vid, 'titolo_originale': titolo, 'titolo_italiano': titolo, 'tag_seo': ', '.join(tags),
            'data_pubblicazione': uscita.strftime('%Y-%m-%d %H:%M'), 'data_inizio_produzione': dt.datetime.now(ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M'),
            'nome_canale': 'NOTIZIE', 'file_video': f"video-notizie:{os.path.basename(E('VIDEO'))}@{E('GITHUB_RUN_ID', '')}"}
    riga = [vals.get(c, '') for c in h]
    A.api(fid, 'POST', '/values/' + urllib.parse.quote(f"'{sch}'!A{len(prod) + 2}") + ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS', {'values': [riga]})
    log('riga per gli Short aggiunta nel file di produzione di', cid)


if __name__ == '__main__':
    main()
