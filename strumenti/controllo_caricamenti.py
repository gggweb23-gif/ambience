#!/usr/bin/env python3
"""
CONTROLLO CARICAMENTI (tutti i canali, gratis: API YouTube in sola lettura).
Per ogni canale collegato (un token per canale nei segreti) guarda gli ultimi video caricati e segnala tutto cio'
che puo' bloccare o frenare la spinta di YouTube:
- video non pubblico (privato = spesso blocco dei caricamenti API da progetto non verificato), caricamento rifiutato/fallito
- "creato per bambini", limite d'eta', blocchi per paese, incorporamento spento
- lingua del video / dei metadati mancante o diversa da quella del canale
- video pubblico da oltre 48 ore con 0 visualizzazioni
- canale: impostazione predefinita "per bambini", canale non verificato per video lunghi
Uscita: prove_video/controllo_caricamenti/report.txt (tutto) e problemi.txt (solo i problemi; vuoto = tutto a posto)
Variabili: YT_CLIENT_ID, YT_CLIENT_SECRET e un segreto per canale con nome che inizia per YT_REFRESH_TOKEN
"""
import datetime as dt, json, os, re, urllib.parse, urllib.request

E = os.environ.get
CART = os.path.join('prove_video', 'controllo_caricamenti'); os.makedirs(CART, exist_ok=True)
N = int(E('ULTIMI') or 10)
API = 'https://www.googleapis.com/youtube/v3/'
ADESSO = dt.datetime.now(dt.timezone.utc)


def get(u, h=None, dati=None):
    req = urllib.request.Request(u, data=dati, headers=dict({'User-Agent': 'ambience-controllo/1.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '{}')


def token(refresh):
    return get('https://oauth2.googleapis.com/token', dati=urllib.parse.urlencode({
        'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': refresh,
        'grant_type': 'refresh_token'}).encode())['access_token']


report, problemi = [], []
for chiave in sorted(k for k in os.environ if k.startswith('YT_REFRESH_TOKEN') and os.environ[k].strip()):
    try:
        h = {'Authorization': 'Bearer ' + token(os.environ[chiave].strip())}
        ch = get(API + 'channels?part=snippet,status,contentDetails,brandingSettings&mine=true', h)['items'][0]
    except Exception as e:
        report.append(f'\n### {chiave}: token non valido o canale non letto ({str(e)[:100]})')
        problemi.append(f'{chiave}: token non valido o scaduto, i caricamenti su questo canale non funzionano'); continue
    nome = ch['snippet']['title']
    lingua_canale = (ch['brandingSettings'].get('channel', {}).get('defaultLanguage') or ch['snippet'].get('defaultLanguage') or '')[:2]
    report.append(f'\n### {nome} ({chiave}) | lingua canale: {lingua_canale or "NON IMPOSTATA"}')
    st = ch.get('status', {})
    if st.get('madeForKids') or st.get('selfDeclaredMadeForKids'):
        problemi.append(f'{nome}: il CANALE e\' impostato "per bambini" -> distribuzione molto ridotta')
    if st.get('longUploadsStatus') not in (None, 'allowed', 'eligible'):
        problemi.append(f'{nome}: video lunghi non abilitati ({st.get("longUploadsStatus")}) -> verificare il canale col telefono')
    if not lingua_canale:
        problemi.append(f'{nome}: lingua del canale non impostata (Studio > Impostazioni > Canale)')
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    ids = [i['contentDetails']['videoId'] for i in get(API + f'playlistItems?part=contentDetails&maxResults={N}&playlistId={up}', h).get('items', [])]
    if not ids:
        report.append('  nessun video'); continue
    for v in get(API + 'videos?part=snippet,status,statistics,contentDetails&id=' + ','.join(ids), h).get('items', []):
        s, sn, cd, sta = v['status'], v['snippet'], v['contentDetails'], v.get('statistics', {})
        tit = sn['title'][:60]; pub = sn.get('publishedAt', '')
        ore = (ADESSO - dt.datetime.fromisoformat(pub.replace('Z', '+00:00'))).total_seconds() / 3600 if pub else 0
        m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', cd.get('duration', ''))
        sec = sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0
        pv = []
        if s.get('uploadStatus') in ('rejected', 'failed', 'deleted'):
            pv.append(f"caricamento {s['uploadStatus']}: {s.get('rejectionReason') or s.get('failureReason')}")
        if s.get('privacyStatus') == 'private' and not s.get('publishAt'):
            pv.append('PRIVATO senza data di uscita (se doveva essere pubblico: blocco dei caricamenti API da progetto Google non verificato)')
        doppione = s.get('privacyStatus') == 'unlisted' and sec >= 480   # prova non in elenco (voluta): solo nel report
        if s.get('madeForKids') or s.get('selfDeclaredMadeForKids'):
            pv.append('"creato per bambini" -> niente commenti, niente notifiche, spinta ridotta')
        if (cd.get('contentRating') or {}).get('ytRating') == 'ytAgeRestricted':
            pv.append('LIMITE D\'ETA\' -> distribuzione molto ridotta')
        if cd.get('regionRestriction'):
            pv.append(f"bloccato in alcuni paesi: {cd['regionRestriction']}")
        if s.get('embeddable') is False:
            pv.append('incorporamento spento')
        la = (sn.get('defaultAudioLanguage') or '')[:2]; lm = (sn.get('defaultLanguage') or '')[:2]
        if not la:
            pv.append('lingua del video NON impostata')
        elif lingua_canale and la != lingua_canale:
            pv.append(f'lingua del video {la} diversa da quella del canale {lingua_canale}')
        if lm and la and lm != la:
            pv.append(f'lingua titolo/descrizione {lm} diversa dalla lingua del video {la}')
        if s.get('privacyStatus') == 'public' and ore > 48 and int(sta.get('viewCount', 0)) == 0 and sec >= 480:
            pv.append('pubblico da oltre 48 ore con 0 visualizzazioni')
        riga = (f"  {pub[:16].replace('T', ' ')} | {s.get('privacyStatus')}{' (esce ' + s['publishAt'][:16] + ')' if s.get('publishAt') else ''} | "
                f"{sec // 60} min | {sta.get('viewCount', '?')} views | {tit} | {v['id']}")
        if doppione:
            riga += '  [prova non in elenco: se esiste gia\' la versione pubblica conviene cancellarla, due video quasi uguali sullo stesso canale non aiutano]'
        report.append(riga + ('' if not pv else '\n     !! ' + '\n     !! '.join(pv)))
        if pv and sec >= 480 and ore < 24 * 15:          # i problemi contano sui video veri degli ultimi 15 giorni
            problemi += [f'{nome} | {tit} | {p}' for p in pv]

testo = f'Controllo caricamenti {ADESSO:%Y-%m-%d %H:%M} UTC\n' + '\n'.join(report) + '\n'
open(os.path.join(CART, 'report.txt'), 'w').write(testo)
open(os.path.join(CART, 'problemi.txt'), 'w').write('\n'.join(problemi) + ('\n' if problemi else ''))
print(testo); print('PROBLEMI:', len(problemi)); print('\n'.join(problemi))
