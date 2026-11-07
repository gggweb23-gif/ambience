"""Dichiarazioni YouTube (6 nov 2026, Giorgio): "Promozione a pagamento" = No su tutti i video e gli Short.
8 nov 2026 (Giorgio, quota YouTube): la dichiarazione va DENTRO il caricamento (sessione()), cosi' non serve la modifica dopo
(videos.update = 50 unita' di quota a video). La modifica dopo resta solo come riserva, se il caricamento non l'ha presa.
Mai bloccante: se YouTube rifiuta, il video resta caricato e si scrive solo un avviso nel registro."""
import json, urllib.error, urllib.request

PARTE = 'paidProductPlacementDetails'
NO = {'hasPaidProductPlacement': False}


def sessione(url, corpo, headers, timeout=120):
    """Apre la sessione di caricamento (resumable) con la dichiarazione dentro e ne restituisce l'indirizzo.
    Se YouTube rifiutasse la parte in piu' (errore 400), riapre la sessione come prima: il caricamento non si blocca mai."""
    u2 = url.replace('part=snippet,status', 'part=snippet,status,' + PARTE) if PARTE not in url else url
    c2 = dict(corpo, **{PARTE: NO})
    try:
        with urllib.request.urlopen(urllib.request.Request(u2, data=json.dumps(c2).encode(), method='POST', headers=headers), timeout=timeout) as r:
            return r.headers['Location']
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
        print('dichiarazione nel caricamento rifiutata (400), carico come prima:', e.read().decode('utf-8', 'ignore')[:150], flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(corpo).encode(), method='POST', headers=headers), timeout=timeout) as r:
        return r.headers['Location']


def nessuna_promozione(video_id, token, risposta=None):
    """risposta = il video restituito dal caricamento: se la dichiarazione e' gia' 'No' non si spende niente."""
    if isinstance(risposta, dict) and (risposta.get(PARTE) or {}).get('hasPaidProductPlacement') is False:
        print('promozione a pagamento: No (gia\' nel caricamento, 0 unita\' di quota)', flush=True); return
    try:
        req = urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=' + PARTE, method='PUT',
                                     data=json.dumps({'id': video_id, PARTE: NO}).encode(),
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=60).read()
        print('promozione a pagamento: No', flush=True)
    except Exception as e:
        print('promozione a pagamento non impostata:', str(e)[:150], flush=True)


def finestra_ok():
    """8 nov 2026 (Giorgio): sistemazioni di massa (cancellazioni, modifiche su molti video) solo DOPO le 09:00 italiane,
    quando la quota YouTube si azzera: tra mezzanotte e le 09:00 la quota rimasta serve ai caricamenti della notte.
    FORZA_QUOTA=SI per farle comunque (solo se lo decide Giorgio)."""
    import datetime as dt, os
    from zoneinfo import ZoneInfo
    return os.environ.get('FORZA_QUOTA', '').strip().upper() == 'SI' or dt.datetime.now(ZoneInfo('Europe/Rome')).hour >= 9
