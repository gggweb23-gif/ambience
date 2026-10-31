#!/usr/bin/env python3
"""
LIBRERIA CLIP (per tutti i canali che usano archivi video gratuiti) — si fa UNA VOLTA per archivio/argomento.
1) cerca nell'archivio (oggi NASA) i video di riprese vere (b-roll, riprese dalla Stazione, time-lapse), niente conferenze/interviste
2) li taglia in spezzoni da 3-4 s sui cambi di scena (mai l'inizio e la fine: titoli e crediti), scarta bande nere e spezzoni fermi
3) Claude Haiku guarda UN fotogramma per spezzone (10 per chiamata) e scrive l'etichetta: cosa si vede, dove, se c'e' gente
   che parla in camera, se ci sono scritte, qualita' 1-5, parole chiave
4) salva l'indice: i video poi pescano gli spezzoni da qui, senza piu' spendere nulla
Spesa: SOLO le chiamate Haiku, con TETTO RIGIDO 'max_spesa' (si ferma prima di superarlo).
PAYLOAD = {"nome": "nasa_spazio", "max_spezzoni": 300, "max_spesa": 0.45, "ricerche": ["space station b-roll", ...]}
Uscita: libreria_clip/<nome>/ (indice.json, controllo.jpg, costi.txt)
"""
import base64, io, json, os, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageChops, ImageDraw, ImageStat

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = P.get('nome') or 'nasa_spazio'
CART = os.path.join('libreria_clip', NOME); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/lib'; os.makedirs(LAV, exist_ok=True)
MAX_N = int(P.get('max_spezzoni') or 300)
MAX_SPESA = min(float(P.get('max_spesa') or 0.45), 0.50)          # tetto deciso da Giorgio: mai oltre 0,50 $
MODELLO = 'claude-haiku-4-5-20251001'; PREZZO = (1.0, 5.0)         # $ per milione di token (input, output)
SPESA = {'tot': 0.0, 'chiamate': 0}
UA = {'User-Agent': 'ambience-libreria-clip/1.0 (gggweb23@gmail.com)'}
NO_CLIP = re.compile(r'brief|conference|interview|news|q ?& ?a|panel|talk|chat|replay|update|event|coverage|town hall|live|speech|remarks|'
                     r'podcast|webinar|explain|animation|graphic|trailer|countdown|speaks|call|engagement|discuss|student|school|media|magazine|'
                     r'governor|official|tour|education|in-?flight|virtual|ceremony|award|reporter|answers|questions|launch|barge|rollout|test', re.I)
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
RICERCHE = P.get('ricerche') or [
    'space station b-roll', 'spacewalk b-roll', 'Expedition b-roll', 'crew activities space station', 'space station time lapse',
    'Earth from space station time lapse', 'spacewalk', 'astronaut exercise space station', 'astronaut eating space station',
    'cupola Earth view', 'space station docking', 'astronauts microgravity', 'ISS crew', 'space station Earth views']


def get(u, dati=None, h=None, raw=False, timeout=180):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict(UA, **({'Content-Type': 'application/json'} if dati is not None else {}), **(h or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def sh(c, **k):
    return subprocess.run([str(x) for x in c], capture_output=True, text=True, **k)


# ---------------- 1) video sorgente ----------------
sorgenti, visti = [], set()
for q in RICERCHE:
    try:
        items = get('https://images-api.nasa.gov/search?' + urllib.parse.urlencode({'q': q, 'media_type': 'video'})).get('collection', {}).get('items', [])
    except Exception as e:
        log('ricerca non riuscita', q, str(e)[:80]); continue
    n = 0
    for it in items:
        d0 = it['data'][0]; nid = d0['nasa_id']; tit = d0.get('title', ''); desc = d0.get('description', '')[:400]
        if nid in visti or NO_CLIP.search(tit + ' ' + ' '.join(d0.get('keywords') or [])):
            continue
        if not re.search(r'space station|\bISS\b|orbit|spacewalk|expedition|astronaut|Earth', tit + ' ' + desc, re.I):
            continue
        visti.add(nid); sorgenti.append((nid, tit, it['href'])); n += 1
        if n >= 4:
            break
log(len(sorgenti), 'video sorgente')

# ---------------- 2) spezzoni ----------------
spezzoni = []
for nid, tit, href in sorgenti:
    if len(spezzoni) >= MAX_N:
        break
    try:
        files = get(href)
        mp4 = next((f for suf in ('~small.mp4', '~mobile.mp4', '~medium.mp4', '~preview.mp4') for f in files if f.endswith(suf)), None)
        if not mp4:
            continue
        mp4 = mp4.replace('http://', 'https://')
        p = os.path.join(LAV, re.sub(r'\W', '_', nid)[:80] + '.mp4')
        open(p, 'wb').write(get(mp4, raw=True, timeout=600))
        wh = sh(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', p]).stdout.strip().split(',')
        lung = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).stdout.strip() or 0)
        if len(wh) < 2 or int(wh[0]) < 600 or int(wh[0]) < int(wh[1]) or lung < 20:
            os.remove(p); continue
        # cambi di scena
        o = sh(['ffmpeg', '-v', 'info', '-i', p, '-vf', "scale=320:-2,select='gt(scene,0.30)',metadata=print", '-an', '-f', 'null', '-']).stderr
        tagli = [0.0] + [float(x) for x in re.findall(r'pts_time:([\d.]+)', o)] + [lung]
        presi = 0
        for a, b in zip(tagli, tagli[1:]):
            if b - a < 3.8 or a < lung * .08 or b > lung * .92:
                continue
            # spezzoni da 3,5 s dentro la scena (uno ogni 12 s se la scena e' lunga)
            t = a + .3
            while t + 3.5 < b - .2 and presi < 25 and len(spezzoni) < MAX_N:
                f1, f2 = os.path.join(LAV, 'a.jpg'), os.path.join(LAV, 'b.jpg')
                sh(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t + .4:.2f}', '-i', p, '-frames:v', '1', '-vf', 'scale=512:-2', f1])
                sh(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t + 3.0:.2f}', '-i', p, '-frames:v', '1', '-vf', 'scale=512:-2', f2])
                if os.path.exists(f1) and os.path.exists(f2):
                    i1, i2 = Image.open(f1).convert('L'), Image.open(f2).convert('L')
                    mov = ImageStat.Stat(ImageChops.difference(i1, i2)).mean[0]
                    luce = ImageStat.Stat(i1).mean[0]
                    # bande nere: righe/colonne ai bordi quasi nere
                    bordo = min(ImageStat.Stat(i1.crop((0, 0, 30, i1.height))).mean[0], ImageStat.Stat(i1.crop((i1.width - 30, 0, i1.width, i1.height))).mean[0])
                    centro = ImageStat.Stat(i1.crop((i1.width // 3, 0, 2 * i1.width // 3, i1.height))).mean[0]
                    bande = bordo < 6 and centro > 30
                    if mov >= 2.5 and luce > 18 and not bande:          # niente spezzoni fermi, neri o con bande
                        mid = os.path.join(LAV, f'sp_{len(spezzoni):04d}.jpg'); Image.open(f1).convert('RGB').save(mid, quality=80)
                        spezzoni.append({'n': len(spezzoni), 'nasa_id': nid, 'titolo': tit, 'url': mp4, 'da': round(t, 2), 'durata': 3.5,
                                         'movimento': round(mov, 1), 'img': mid})
                        presi += 1
                t += 12
        log(nid[:50], '->', presi, 'spezzoni (totale', len(spezzoni), ')')
        os.remove(p)
    except Exception as e:
        log('sorgente scartata', nid[:50], str(e)[:100])

# ---------------- 3) etichette (Haiku, con tetto rigido) ----------------
DOMANDA = ('These are frames from NASA videos. For EACH frame answer one JSON object. Answer ONLY a JSON array, same order: '
           '[{"k": <frame number>, "cosa": "what is visible, 6-12 English words", '
           '"luogo": "inside_station | outside_station | earth_from_orbit | spacecraft | on_earth | other", '
           '"parla_in_camera": true/false (a person talking to the camera or an interview/press setting), '
           '"scritte": true/false (any overlay text, captions, logos, titles, subtitles burned in), '
           '"qualita": 1-5 (5 = sharp, beautiful, cinematic; 1 = blurry, dark, boring), '
           '"tag": ["3-6 lowercase English keywords, e.g. spacewalk, treadmill, food, sleeping, earth, cupola, robotic arm"]}]')
STIMA_CHIAMATA = (10 * 400 + 600) * PREZZO[0] / 1e6 + 900 * PREZZO[1] / 1e6     # stima prudente prima di ogni chiamata
for i in range(0, len(spezzoni), 10):
    if SPESA['tot'] + STIMA_CHIAMATA > MAX_SPESA:
        log('TETTO DI SPESA raggiunto: mi fermo a', i, 'spezzoni etichettati'); break
    gruppo = spezzoni[i:i + 10]
    cont = []
    for s in gruppo:
        cont.append({'type': 'text', 'text': f'Frame {s["n"]}:'})
        cont.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(s['img'], 'rb').read()).decode()}})
    cont.append({'type': 'text', 'text': DOMANDA})
    try:
        r = get('https://api.anthropic.com/v1/messages', {'model': MODELLO, 'max_tokens': 1500, 'messages': [{'role': 'user', 'content': cont}]},
                {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        u = r.get('usage', {}); SPESA['tot'] += (u.get('input_tokens', 0) * PREZZO[0] + u.get('output_tokens', 0) * PREZZO[1]) / 1e6; SPESA['chiamate'] += 1
        t = ''.join(b.get('text', '') for b in r.get('content', []))
        for x in json.loads(t[t.find('['): t.rfind(']') + 1]):
            s = next((s for s in gruppo if s['n'] == int(x.get('k', -1))), None)
            if s:
                s.update({k: x.get(k) for k in ('cosa', 'luogo', 'parla_in_camera', 'scritte', 'qualita', 'tag')})
    except Exception as e:
        log('etichette non riuscite per il gruppo', i, str(e)[:150])
    log(f'etichettati {min(i + 10, len(spezzoni))}/{len(spezzoni)} | spesa {SPESA["tot"]:.3f} $')

# ---------------- 4) indice + foglio di controllo ----------------
def buono(s):
    return (s.get('cosa') and not s.get('parla_in_camera') and not s.get('scritte') and int(s.get('qualita') or 0) >= 3
            and s.get('luogo') in ('inside_station', 'outside_station', 'earth_from_orbit', 'spacecraft'))


for s in spezzoni:
    s['ok'] = bool(buono(s))
ok = [s for s in spezzoni if s['ok']]
json.dump([{k: v for k, v in s.items() if k != 'img'} for s in spezzoni], open(os.path.join(CART, 'indice.json'), 'w'), ensure_ascii=False, indent=1)
col = 8; tw, th = 240, 135
G = Image.new('RGB', (col * tw, ((len(spezzoni) + col - 1) // col) * (th + 30)), 'black'); d = ImageDraw.Draw(G)
for i, s in enumerate(spezzoni):
    x, y = (i % col) * tw, (i // col) * (th + 30)
    im = Image.open(s['img']); im.thumbnail((tw, th)); G.paste(im, (x, y))
    d.rectangle((x, y + th, x + tw - 2, y + th + 28), fill=(0, 110, 0) if s['ok'] else (130, 0, 0))
    d.text((x + 3, y + th + 2), f"{s['n']} {str(s.get('cosa') or '')[:34]}", fill='white')
    d.text((x + 3, y + th + 14), f"{s.get('luogo') or '?'} q{s.get('qualita') or '?'}", fill='white')
G.save(os.path.join(CART, 'controllo.jpg'), quality=75)
riepilogo = (f'sorgenti: {len(sorgenti)} | spezzoni: {len(spezzoni)} | buoni: {len(ok)} | chiamate Haiku: {SPESA["chiamate"]} | '
             f'spesa: {SPESA["tot"]:.3f} $ (tetto {MAX_SPESA:.2f} $)\n')
open(os.path.join(CART, 'costi.txt'), 'w').write(riepilogo)
log(riepilogo)
