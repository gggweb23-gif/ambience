#!/usr/bin/env python3
"""PEZZI COMUNI DEI MOTORI NUOVI (9 nov 2026: Billion Ruin e Costo Vero), presi da video_cartoni.py cosi' ogni motore ha le stesse cose
gia' confermate sugli altri canali: caricamento con dichiarazioni (AI = No, promozione = No), uscita programmata, copertina,
playlist (quella della riga del file di produzione, altrimenti le regole della colonna playlist; se manca la crea), descrizione con il
titolo nella prima riga e il titolo anche nei tag, esito per il file di produzione, caricamento a mano se carica = MANUALE."""
import json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import descrizione as DESCR
import manuale as MAN
try:
    import dichiarazioni_yt as DICH
except Exception:
    DICH = None
E = os.environ.get
MIN_SEC_YT = 480   # mai su YouTube sotto gli 8 minuti


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def http(url, data=None, headers=None, timeout=900, raw=False):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def esito(e, root='.'):
    log('esito:', json.dumps(e, ensure_ascii=False)[:600])
    json.dump(e, open(os.path.join(root, 'esito_video.json'), 'w'), ensure_ascii=False)


def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60).read())['access_token']


def scegli_playlist(P, titolo):
    """Prima la playlist scritta nella riga del file di produzione; altrimenti la colonna playlist di Channel Configs
    (Nome: parola1, parola2 || Altra playlist; senza parole = tutti i video)."""
    riga = str((P.get('riga') or {}).get('playlist') or '').strip()
    if riga:
        return [riga[:150]]
    regole = [x.strip() for x in str(P.get('playlist') or '').split('||') if x.strip()]
    return [n.strip()[:150] for n, _, p in (r.partition(':') for r in regole)
            if n.strip() and (not p.strip() or any(w.strip().lower() in titolo.lower() for w in p.split(',') if w.strip()))]


def metti_in_playlist(P, vid, titolo, tok):
    scelte = scegli_playlist(P, titolo)
    if not scelte:
        return 'nessuna playlist (colonna playlist della riga o di Channel Configs)'
    h = {'Authorization': 'Bearer ' + tok}
    try:
        tutte = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', headers=h).get('items', [])
        esistenti = {it['snippet']['title'].strip().lower(): it['id'] for it in tutte}
        for nome in scelte:
            pid = esistenti.get(nome.lower())
            if not pid:   # la playlist non c'e' ancora: si crea (Giorgio, 9 nov: "le crei tu in automatico quando pubblichi")
                pid = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': nome}, 'status': {'privacyStatus': 'public'}}, h)['id']
                time.sleep(8)
            http('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}}, h)
            log('playlist:', nome)
        return ''
    except Exception as e:
        return 'playlist non aggiornata: ' + str(e)[:150]


def carica_youtube(P, path, titolo, descr, tags, cop, lingua):
    tok = token()
    status = {'privacyStatus': P.get('privacy') or 'public', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}   # AI = No
    if P.get('pubblica_il') and status['privacyStatus'] == 'public':
        status['privacyStatus'] = 'private'; status['publishAt'] = P['pubblica_il']
    snip = {'title': titolo[:100], 'description': descr, 'tags': tags, 'categoryId': str(P.get('youtube_category_id') or '27'),
            'defaultLanguage': lingua, 'defaultAudioLanguage': lingua}
    hd = {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Length': str(os.path.getsize(path)), 'X-Upload-Content-Type': 'video/mp4'}
    url = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'
    if DICH:   # promozione a pagamento = No dentro il caricamento
        sess = DICH.sessione(url, {'snippet': snip, 'status': status}, hd, 120)
    else:
        with urllib.request.urlopen(urllib.request.Request(url, data=json.dumps({'snippet': snip, 'status': status}).encode(), method='POST', headers=hd), timeout=120) as r:
            sess = r.headers['Location']
    for k in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(sess, data=open(path, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'video/mp4'}), timeout=1800) as r:
                ris = json.loads(r.read().decode()); vid = ris['id']
            break
        except Exception as e:
            log('upload, riprovo:', str(e)[:150]); time.sleep(15 * (k + 1)); tok = token()
    else:
        raise RuntimeError('caricamento su YouTube non riuscito')
    if DICH:
        try:
            DICH.nessuna_promozione(vid, tok, ris)
        except Exception:
            pass
    nota = metti_in_playlist(P, vid, titolo, tok)
    try:
        urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', data=open(cop, 'rb').read(), method='POST',
                                                      headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'image/jpeg'}), timeout=120).read()
    except Exception as e:
        nota = (nota + ' | ' if nota else '') + 'copertina non caricata: ' + str(e)[:150]
    return vid, nota


def testi(P, titolo, descr_breve, capitoli, tag, nota_finale=''):
    """Descrizione: titolo (prima riga) + testo + capitoli + nota + chiusura del canale. Tag: quelli del copione + del canale, titolo compreso."""
    cap = '\n'.join(capitoli) if len(capitoli) >= 3 else ''
    descr = '\n\n'.join(x for x in [titolo, str(descr_breve or '').strip(), cap, nota_finale, str(P.get('youtube_description_footer') or '').strip()] if x)
    descr = DESCR.con_titolo(titolo, descr)
    tags = DESCR.tag_con_titolo(titolo, [str(x) for x in (tag or [])] + [x.strip() for x in str(P.get('youtube_default_tags') or '').split(',') if x.strip()])
    return descr, (tags if isinstance(tags, list) else [x.strip() for x in str(tags).split(',') if x.strip()])


def chiudi(P, finale, cop, titolo, descr, tags, extra, prova, carica, durata_s, lingua, root='.'):
    """Ultimo passo uguale per tutti: prova -> solo esito; carica = SI -> YouTube programmato; altrimenti cartella da caricare a mano."""
    extra = dict(extra, titolo=titolo, descrizione=descr, tag=', '.join(tags), playlist=', '.join(scegli_playlist(P, titolo)), minuti_video=round(durata_s / 60, 1))
    if prova or durata_s < MIN_SEC_YT:
        if durata_s < MIN_SEC_YT and not prova:
            log(f'video di {durata_s / 60:.1f} minuti: sotto gli 8 minuti NON va su YouTube')
        esito({'stato': 'PROVA OK', **extra}, root); return
    if carica and E('YT_REFRESH_TOKEN'):
        vid, nota = carica_youtube(P, finale, titolo, descr, tags, cop, lingua)
        esito({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'pubblica_il': P.get('pubblica_il') or '', 'errore': nota, **extra}, root)
    else:
        if carica:
            log('carica = SI ma manca la chiave YouTube del canale: preparo il caricamento a mano')
        MAN.prepara(finale, cop, titolo, root)
        esito({'stato': 'CREATO', **extra}, root)
