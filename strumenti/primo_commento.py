#!/usr/bin/env python3
"""PRIMO COMMENTO (16 nov 2026, Giorgio: "sotto ogni video, entro 3-5 minuti dalla pubblicazione, deve esserci il primo commento:
stimola i commenti e YouTube spinge di piu'"). Per video lunghi e Short di tutti i canali.
Come funziona: il giro parte poco prima degli orari di uscita; per ogni canale legge i video programmati che escono entro FINESTRA minuti
(e quelli usciti da poco senza il nostro commento), aspetta l'ora di uscita, controlla che il video sia pubblico e scrive il commento
dal canale stesso. Il testo lo scrive Claude Haiku dal titolo e dalla descrizione (~0,001 $): una domanda breve e coinvolgente nella lingua
del canale, mai link, mai spam. Un video gia' commentato dal canale non si commenta due volte.
Nota: le API di YouTube non permettono di FISSARE (pin) il commento in alto: va fatto a mano dall'app se serve.
Env: FINESTRA (75 minuti), PROVA (SI = scrive solo nel registro), ANTHROPIC_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN_<CANALE>"""
import datetime as dt, json, os, re, time, urllib.parse, urllib.request

E = os.environ.get
ORA = lambda: dt.datetime.now(dt.timezone.utc)
FINESTRA = float(E('FINESTRA') or 75)
PROVA = (E('PROVA') or 'NO').upper() == 'SI'
CANALI = {k[len('YT_REFRESH_TOKEN_'):]: v for k, v in os.environ.items() if k.startswith('YT_REFRESH_TOKEN_') and v.strip()}
REG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'coach', 'primi_commenti.jsonl')


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def http(url, data=None, headers=None, metodo=None, form=False):
    body = (urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    h = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=metodo), timeout=60) as r:
        return json.loads(r.read() or b'{}')


def token(refresh):
    return http('https://oauth2.googleapis.com/token', {'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'),
                                                        'refresh_token': refresh, 'grant_type': 'refresh_token'}, form=True)['access_token']


def yt(tk, percorso, **q):
    return http('https://www.googleapis.com/youtube/v3/' + percorso + '?' + urllib.parse.urlencode(q), headers={'Authorization': 'Bearer ' + tk})


def video_canale(tk):
    """Ultimi 25 video caricati (lunghi e Short) con stato e ora di uscita."""
    ch = yt(tk, 'channels', part='contentDetails,snippet', mine='true')['items'][0]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    ids = [x['contentDetails']['videoId'] for x in yt(tk, 'playlistItems', part='contentDetails', playlistId=up, maxResults=25).get('items', [])]
    vv = yt(tk, 'videos', part='snippet,status', id=','.join(ids)).get('items', []) if ids else []
    return ch['id'], ch['snippet']['title'], vv


def gia_commentato(tk, vid, cid):
    try:
        r = yt(tk, 'commentThreads', part='snippet', videoId=vid, maxResults=50, order='time')
        return any(t['snippet']['topLevelComment']['snippet'].get('authorChannelId', {}).get('value') == cid for t in r.get('items', []))
    except Exception:
        return False


def testo_commento(v):
    sn = v['snippet']; lingua = (sn.get('defaultLanguage') or sn.get('defaultAudioLanguage') or 'it')[:2]
    prompt = (f"You are the creator of this YouTube video. Write the FIRST comment under it, in {'Italian' if lingua == 'it' else 'English'}: "
              "max 2 short sentences (under 220 characters in total), warm and natural, ending with ONE simple question that makes viewers want to answer with their own "
              "experience or opinion about the topic. No links, no hashtags, no emojis spam (max 1 emoji), no 'subscribe', no clickbait. "
              "Answer with the comment text only.\n\nTITLE: " + sn.get('title', '') + '\nDESCRIPTION: ' + (sn.get('description') or '')[:600])
    j = http('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 200, 'messages': [{'role': 'user', 'content': prompt}]},
             {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
    return ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text').strip().strip('"')


def main():
    da_fare = []   # (quando, canale, video)
    for nome, refresh in CANALI.items():
        try:
            tk = token(refresh); cid, titolo_c, vv = video_canale(tk)
        except Exception as e:
            log('canale non letto', nome, str(e)[:120]); continue
        for v in vv:
            st = v['status']; pub = st.get('publishAt')
            quando = dt.datetime.fromisoformat((pub or v['snippet']['publishedAt']).replace('Z', '+00:00'))
            mancano = (quando - ORA()).total_seconds() / 60
            programmato = st.get('privacyStatus') == 'private' and pub and 0 <= mancano <= FINESTRA
            appena_uscito = st.get('privacyStatus') == 'public' and -90 <= mancano <= 0   # uscito da poco (anche se il giro e' partito in ritardo)
            if programmato or appena_uscito:
                da_fare.append((quando, nome, refresh, cid, v))
    da_fare.sort(key=lambda x: x[0])
    log(f'{len(da_fare)} video da commentare nei prossimi {FINESTRA:.0f} minuti:', [(x[1], x[4]['snippet']['title'][:40], x[0].strftime('%H:%M')) for x in da_fare])
    for quando, nome, refresh, cid, v in da_fare:
        attesa = (quando - ORA()).total_seconds() + 45
        if attesa > 0:
            log(f'aspetto l\'uscita di "{v["snippet"]["title"][:50]}" ({nome}) alle {quando.strftime("%H:%M")} UTC'); time.sleep(attesa)
        tk = token(refresh)
        for k in range(16):   # fino a 8 minuti: YouTube a volte rende pubblico con un po' di ritardo
            st = yt(tk, 'videos', part='status', id=v['id']).get('items', [{}])[0].get('status', {})
            if st.get('privacyStatus') == 'public':
                break
            time.sleep(30)
        else:
            log('non ancora pubblico, salto:', v['id']); continue
        if gia_commentato(tk, v['id'], cid):
            log('gia commentato:', v['id']); continue
        testo = testo_commento(v)
        esito = 'PROVA'
        if not PROVA:
            for k in range(3):   # errore 400 "transient" di YouTube subito dopo l'uscita: si riprova
                try:
                    http('https://www.googleapis.com/youtube/v3/commentThreads?part=snippet', {'snippet': {'videoId': v['id'], 'topLevelComment': {'snippet': {'textOriginal': testo}}}},
                         {'Authorization': 'Bearer ' + tk})
                    esito = 'SCRITTO'; break
                except urllib.error.HTTPError as e:
                    esito = f'ERRORE {e.code} ' + e.read().decode()[:300]; time.sleep(40)
        ritardo = (ORA() - quando).total_seconds() / 60
        log(f'{esito} | {nome} | {v["id"]} | {ritardo:.1f} min dopo l\'uscita | {testo}')
        with open(REG, 'a') as f:
            f.write(json.dumps({'ora': ORA().isoformat()[:19], 'canale': nome, 'video': v['id'], 'titolo': v['snippet']['title'], 'minuti_dopo_uscita': round(ritardo, 1),
                                'esito': esito[:120], 'testo': testo}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    import urllib.error
    main()
