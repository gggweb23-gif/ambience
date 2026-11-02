#!/usr/bin/env python3
"""RADAR CANALI (gratis, solo lettura): per ogni canale candidato da copiare scarica dati e immagini per giudicare se si puo' rifare
con archivi gratuiti (Pexels, NASA, archivi storici, dipinti...) o con l'IMPRONTA.
PAYLOAD = {"nome": "radar_2026_11_02", "canali": ["UC...", ...], "fotogrammi": "SI"}
Uscita: prove_video/radar/<nome>/ : report.txt (dati), <canale>_copertine.jpg (copertine dei video piu' visti),
<canale>_fotogrammi.jpg (fotogrammi dei primi 2 minuti del video piu' visto, se si scarica)."""
import io, json, os, re, statistics, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_video', 'radar', P.get('nome') or 'radar'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/radar'; os.makedirs(LAV, exist_ok=True)


def get(u, dati=None, h=None, raw=False):
    req = urllib.request.Request(u, data=dati, headers=dict({'User-Agent': 'Mozilla/5.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=120) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


T = get('https://oauth2.googleapis.com/token', urllib.parse.urlencode({
    'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': E('YT_REFRESH_TOKEN', ''),
    'grant_type': 'refresh_token'}).encode())['access_token']
H = {'Authorization': 'Bearer ' + T}
yt = lambda path, **q: get('https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(q), h=H)


def durata(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0


def foglio(immagini, colonne, larg=480):
    imm = [i for i in immagini if i is not None]
    if not imm:
        return None
    h = int(larg * 9 / 16); righe = (len(imm) + colonne - 1) // colonne
    out = Image.new('RGB', (colonne * larg, righe * h), (20, 20, 20))
    for k, im in enumerate(imm):
        out.paste(im.convert('RGB').resize((larg, h)), ((k % colonne) * larg, (k // colonne) * h))
    return out


rep = []
for cid in P.get('canali') or []:
    try:
        ch = yt('channels', part='snippet,statistics,contentDetails', id=cid)['items'][0]
    except Exception as e:
        rep.append(f'## {cid}: non letto ({str(e)[:80]})\n'); continue
    nome = ch['snippet']['title']; slug = re.sub(r'\W+', '_', nome.lower()).strip('_')[:40]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    ids, pg = [], ''
    for _ in range(2):   # ultimi 100 video
        r = yt('playlistItems', part='contentDetails', playlistId=up, maxResults=50, **({'pageToken': pg} if pg else {}))
        ids += [x['contentDetails']['videoId'] for x in r.get('items', [])]; pg = r.get('nextPageToken') or ''
        if not pg:
            break
    vids = []
    for i in range(0, len(ids), 50):
        vids += yt('videos', part='snippet,statistics,contentDetails', id=','.join(ids[i:i + 50])).get('items', [])
    for v in vids:
        v['_views'] = int(v['statistics'].get('viewCount') or 0); v['_dur'] = durata(v['contentDetails'].get('duration'))
    lunghi = [v for v in vids if v['_dur'] > 180]
    import datetime as _dt
    oggi = _dt.datetime.now(_dt.timezone.utc)
    json.dump([{'id': v['id'], 'titolo': v['snippet']['title'], 'views': v['_views'], 'min': round(v['_dur'] / 60, 1), 'data': v['snippet']['publishedAt'][:10],
                'views_giorno': round(v['_views'] / max(1, (oggi - _dt.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))).days), 1)}
               for v in sorted(vids, key=lambda v: v['snippet']['publishedAt'])], open(os.path.join(CART, slug + '_video.json'), 'w'), ensure_ascii=False, indent=0)
    top = sorted(lunghi or vids, key=lambda v: -v['_views'])
    date = sorted(v['snippet']['publishedAt'][:10] for v in vids)
    s = ch['statistics']
    rep.append(f"## {nome} ({cid})\niscritti {s.get('subscriberCount')} | views totali {s.get('viewCount')} | video {s.get('videoCount')} | "
               f"creato {ch['snippet'].get('publishedAt', '')[:10]} | paese {ch['snippet'].get('country', '-')}\n"
               f"video analizzati {len(vids)} (lunghi >3 min: {len(lunghi)}) | primo {date[0] if date else '-'} | ultimo {date[-1] if date else '-'}\n"
               f"durata mediana lunghi: {statistics.median([v['_dur'] for v in lunghi]) / 60 if lunghi else 0:.1f} min | "
               f"views mediane lunghi: {int(statistics.median([v['_views'] for v in lunghi])) if lunghi else 0}\n"
               f"descrizione canale: {ch['snippet'].get('description', '')[:300].replace(chr(10), ' ')}\n"
               "video piu' visti:\n" + ''.join(f"  {v['_views']:>9} | {v['_dur'] / 60:5.1f} min | {v['snippet']['publishedAt'][:10]} | {v['snippet']['title'][:90]} | {v['id']}\n" for v in top[:10])
               + f"descrizione del piu' visto: {(top[0]['snippet'].get('description', '') if top else '')[:500].replace(chr(10), ' ')}\n")
    # copertine dei 8 piu' visti
    cop = []
    for v in top[:8]:
        try:
            cop.append(Image.open(io.BytesIO(get(f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", raw=True))))
        except Exception:
            pass
    f = foglio(cop, 4)
    if f:
        f.save(os.path.join(CART, slug + '_copertine.jpg'), quality=80)
    # fotogrammi dei primi 2 minuti del piu' visto (si vede il materiale: archivio, AI, Pexels, mappe...)
    if str(P.get('fotogrammi') or 'SI').upper() == 'SI' and top:
        vid = top[0]['id']; base = os.path.join(LAV, vid)
        try:
            subprocess.run(['yt-dlp', '-q', '--no-warnings', '--extractor-args', 'youtube:player_client=tv,ios,mweb,web_safari',
                            '-f', 'bv*[height<=360][ext=mp4]/b[height<=360]/b', '--download-sections', '*0-150', '-o', base + '.%(ext)s',
                            'https://www.youtube.com/watch?v=' + vid], timeout=300)
            src = next((os.path.join(LAV, x) for x in os.listdir(LAV) if x.startswith(vid)), None)
            fr = []
            if src:
                for k in range(12):
                    o = f'{base}_{k}.jpg'
                    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(5 + k * 12), '-i', src, '-frames:v', '1', o])
                    if os.path.exists(o):
                        fr.append(Image.open(o))
            f = foglio(fr, 4, 400)
            if f:
                f.save(os.path.join(CART, slug + '_fotogrammi.jpg'), quality=80); rep[-1] += 'fotogrammi: SI\n'
            else:
                rep[-1] += 'fotogrammi: video non scaricato\n'
        except Exception as e:
            rep[-1] += f'fotogrammi: errore {str(e)[:80]}\n'
    print(rep[-1], flush=True)
open(os.path.join(CART, 'report.txt'), 'w').write('\n'.join(rep))
