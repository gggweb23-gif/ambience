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
SOLO_PROVA = str(P.get('solo_prova') or '').upper() == 'SI'   # prova a secco: trova e taglia le clip, NIENTE Haiku, indice non toccato (costo 0)
MAX_SPESA = 0.0 if SOLO_PROVA else min(float(P.get('max_spesa') or 0.45), 0.50)          # tetto deciso da Giorgio: mai oltre 0,50 $
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


# ---------------- 0) libreria esistente: si AGGIUNGE, mai si riscrive ----------------
F_IND = os.path.join(CART, 'indice.json')
VECCHI = json.load(open(F_IND)) if os.path.exists(F_IND) else []
GIA_FATTE = {x.get('nasa_id') for x in VECCHI}
log(len(VECCHI), 'spezzoni gia' + "'" + ' in libreria,', len(GIA_FATTE), 'video gia' + "'" + ' tagliati')

# ---------------- 1) video sorgente ----------------
ARCHIVIO = str(P.get('archivio') or 'nasa').lower()   # nasa | storico (archive.org + Wikimedia Commons, solo pubblico dominio)
# collezioni di archive.org di pubblico dominio: cinegiornali Universal (donati al pubblico dominio), film del governo USA (FedFlix, Archivi Nazionali)
COLLEZIONI_PD = ['universal_newsreels', 'FedFlix', 'usnationalarchives']   # Prelinger tolto: dentro ci sono anche film di Hollywood
NO_STORICO = re.compile(r'cartoon|animated|animation|trailer|commercial|advertis|colorized|coloriz|remaster|reenact|re-enact|movie clip|hollywood|music video|tiktok|game', re.I)
LIBERE = re.compile(r'public domain|publicdomain|^pd|cc0|cc-zero|no restrictions|mark/1\.0', re.I)


def archive_org(q, quanti=4):
    out = []
    try:
        coll = ' OR '.join('collection:' + c for c in COLLEZIONI_PD)
        r = get('https://archive.org/advancedsearch.php?' + urllib.parse.urlencode(
            [('q', f'({q}) AND mediatype:movies AND ({coll})'), ('fl[]', 'identifier'), ('fl[]', 'title'), ('rows', 15), ('output', 'json')]))
    except Exception as e:
        log('archive.org non risponde per', q, str(e)[:80]); return out
    for d in r.get('response', {}).get('docs', []):
        ide = d.get('identifier'); tit = str(d.get('title') or ide)
        if not ide or 'ia:' + ide in visti or NO_STORICO.search(tit):
            continue
        try:
            m = get('https://archive.org/metadata/' + urllib.parse.quote(ide))
        except Exception:
            continue
        colls = m.get('metadata', {}).get('collection') or []; colls = colls if isinstance(colls, list) else [colls]
        lic = str(m.get('metadata', {}).get('licenseurl') or '')
        if 'prelinger' in colls and not LIBERE.search(lic):   # Prelinger: solo i film marcati di pubblico dominio
            continue
        mp4 = [f for f in m.get('files', []) if str(f.get('name', '')).lower().endswith('.mp4') and 5e6 < float(f.get('size') or 0) < 6e8]
        if not mp4:
            continue
        f = sorted(mp4, key=lambda f: (0 if 'h.264' in str(f.get('format', '')).lower() else 1, float(f.get('size') or 0)))[0]
        out.append(('ia:' + ide, tit, 'DIRETTO:https://archive.org/download/' + urllib.parse.quote(ide) + '/' + urllib.parse.quote(f['name']),
                    'pubblico dominio (' + (lic or ', '.join(c for c in colls if c in COLLEZIONI_PD)) + ')'))
        visti.add('ia:' + ide)
        if len(out) >= quanti:
            break
    return out


def commons_video(q, quanti=3):
    out = []
    try:
        j = get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': q + ' filetype:video', 'gsrlimit': 20,
            'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata'}))
    except Exception as e:
        log('Commons non risponde per', q, str(e)[:80]); return out
    for pg in sorted((j.get('query') or {}).get('pages', {}).values(), key=lambda x: x.get('index', 99)):
        t = pg.get('title', ''); ii = (pg.get('imageinfo') or [{}])[0]; m = ii.get('extmetadata') or {}
        lic = ((m.get('LicenseShortName') or {}).get('value', '') + ' ' + (m.get('License') or {}).get('value', '')).strip()
        nid = 'cm:' + t[5:][:120]
        if nid in visti or not LIBERE.search(lic) or NO_STORICO.search(t) or ii.get('width', 0) < 480 or float(ii.get('size') or 0) > 6e8:
            continue
        out.append((nid, t[5:], 'DIRETTO:' + ii.get('url', ''), lic[:60])); visti.add(nid)
        if len(out) >= quanti:
            break
    return out


sorgenti, visti = [], set(GIA_FATTE)
LICENZE = {}
if ARCHIVIO != 'nasa':
    for q in RICERCHE:
        for nid, tit, href, lic in archive_org(q) + commons_video(q):
            sorgenti.append((nid, tit, href)); LICENZE[nid] = lic
for q in (RICERCHE if ARCHIVIO == 'nasa' else []):
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
BASE_N = max([int(x.get('n', 0)) for x in VECCHI] + [-1]) + 1
for nid, tit, href in sorgenti:
    if len(spezzoni) >= MAX_N:
        break
    try:
        if href.startswith('DIRETTO:'):   # archivi storici: link diretto al file
            mp4 = href[8:]
        else:
            files = get(href)
            mp4 = next((f for suf in ('~small.mp4', '~mobile.mp4', '~medium.mp4', '~preview.mp4') for f in files if f.endswith(suf)), None)
            if not mp4:
                continue
            mp4 = mp4.replace('http://', 'https://')
        p = os.path.join(LAV, re.sub(r'\W', '_', nid)[:80] + '.mp4')
        open(p, 'wb').write(get(mp4, raw=True, timeout=600))
        wh = sh(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', p]).stdout.strip().split(',')
        lung = float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).stdout.strip() or 0)
        if len(wh) < 2 or int(wh[0]) < (600 if ARCHIVIO == 'nasa' else 480) or int(wh[0]) < int(wh[1]) or lung < 20:   # i film d'epoca sono 640x480
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
            while t + 3.5 < b - .2 and presi < (25 if ARCHIVIO == 'nasa' else 6) and len(spezzoni) < MAX_N:   # archivi storici: max 6 per film, piu' varieta'
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
                        # inizio e fine dello spezzone affiancati: una scritta o una persona che entra a meta' si vede
                        mid = os.path.join(LAV, f'sp_{len(spezzoni):04d}.jpg')
                        ia, ib = Image.open(f1).convert('RGB'), Image.open(f2).convert('RGB')
                        dop = Image.new('RGB', (ia.width * 2 + 8, ia.height), 'black'); dop.paste(ia, (0, 0)); dop.paste(ib, (ia.width + 8, 0))
                        dop.save(mid, quality=78)
                        spezzoni.append({'n': BASE_N + len(spezzoni), 'nasa_id': nid, 'titolo': tit, 'url': mp4, 'da': round(t, 2), 'durata': 3.5,
                                         'movimento': round(mov, 1), 'img': mid, **({'licenza': LICENZE[nid]} if nid in LICENZE else {})})
                        presi += 1
                t += 12
        log(nid[:50], '->', presi, 'spezzoni (totale', len(spezzoni), ')')
        os.remove(p)
    except Exception as e:
        log('sorgente scartata', nid[:50], str(e)[:100])

# ---------------- 3) etichette (Haiku, con tetto rigido) ----------------
DOMANDA = ('These are frames from NASA videos (each image = start and end of the same short clip, side by side). For EACH frame answer one JSON object. Answer ONLY a JSON array, same order: '
           '[{"k": <frame number>, "cosa": "what is visible, 6-12 English words", '
           '"luogo": "inside_station | outside_station | earth_from_orbit | spacecraft | on_earth | other", '
           '"parla_in_camera": true/false (a person talking to the camera or an interview/press setting), '
           '"scritte": true/false (ANY overlay text in EITHER half: captions, lower thirds, logos, titles, subtitles, date or time stamps burned in), '
           '"animazione": true/false (computer animation, render, graphic or simulation instead of a real camera shot), '
           '"qualita": 1-5 (5 = sharp, beautiful, cinematic; 1 = blurry, dark, boring), '
           '"tag": ["3-6 lowercase English keywords, e.g. spacewalk, treadmill, food, sleeping, earth, cupola, robotic arm"]}]')
if ARCHIVIO != 'nasa':
    DOMANDA = ('These are frames from historical archive films (each image = start and end of the same short clip, side by side). For EACH frame answer one JSON object. Answer ONLY a JSON array, same order: '
               '[{"k": <frame number>, "cosa": "what is visible, 6-12 English words (people, place, action)", '
               '"luogo": "short place type, e.g. prison_camp, battlefield, city_ruins, factory, farm, train, ship, office, street, home_front, aircraft, other", '
               '"epoca": "decade it looks like: 1930s | 1940s | 1950s | later", '
               '"parla_in_camera": true/false (a person talking to the camera, interview or speech setting), '
               '"scritte": true/false (ANY overlay text in EITHER half: titles, captions, intertitles, logos, subtitles, credits, burned-in stamps), '
               '"animazione": true/false (animation, map graphic, drawing or cartoon instead of a real camera shot), '
               '"simboli_nazisti": true/false (a swastika, Nazi flag or Nazi banner is LARGE and clearly visible in EITHER half), '
               '"qualita": 1-5 (5 = sharp, well exposed, striking; 1 = blurry, damaged, too dark, boring), '
               '"tag": ["3-6 lowercase English keywords of what is visible, e.g. soldiers, prisoners, barbed wire, train, tanks, farm, food, bombers"]}]')
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
                s.update({k: x.get(k) for k in ('cosa', 'luogo', 'epoca', 'parla_in_camera', 'scritte', 'animazione', 'simboli_nazisti', 'qualita', 'tag')})
    except Exception as e:
        log('etichette non riuscite per il gruppo', i, str(e)[:150])
    log(f'etichettati {min(i + 10, len(spezzoni))}/{len(spezzoni)} | spesa {SPESA["tot"]:.3f} $')

# ---------------- 4) indice + foglio di controllo ----------------
EPOCHE_OK = [e.lower() for e in (P.get('epoche') or ['1930s', '1940s'])]


def buono(s):
    if ARCHIVIO != 'nasa':   # archivi storici: ripresa vera dell'epoca giusta, senza scritte, nessuno che parla in camera
        if s.get('anno') and f"{str(s['anno'])[:3]}0s" not in EPOCHE_OK:   # il titolo del film dice un'altra epoca (es. 1917, 1960): fuori
            return False
        return bool(s.get('cosa') and not s.get('parla_in_camera') and not s.get('scritte') and not s.get('animazione')
                    and int(s.get('qualita') or 0) >= int(P.get('qualita_minima') or 2) and str(s.get('epoca') or '').lower() in EPOCHE_OK)
    # (archivi storici: qualita' minima 2 e non 3: Haiku giudica "sfocate" quasi tutte le pellicole degli anni '40, che sono cosi' anche nei canali che copiamo)
    if re.search(r'airplane|aircraft|jet|plane|satellite imagery|map|chart|diagram', str(s.get('cosa')), re.I):
        return False
    return (s.get('cosa') and not s.get('parla_in_camera') and not s.get('scritte') and not s.get('animazione') and int(s.get('qualita') or 0) >= 3
            and s.get('luogo') in ('inside_station', 'outside_station', 'earth_from_orbit', 'spacecraft'))


ANNO = re.compile(r'(?:^|[\s(,/])(19[1-6]\d)(?=[\s),.:;/-]|$)')   # un anno vero: non i numeri di catalogo tipo "111-adc-1921"


def anno_film(x):   # anno del film d'archivio dal titolo o dal nome del file (cinegiornali: "1945-05-14_...")
    m = re.match(r'ia:(19[1-6]\d)-\d\d', str(x.get('nasa_id') or '')) or ANNO.search(str(x.get('titolo') or '').replace('_', ' '))
    return int(m.group(1)) if m else None


for s in spezzoni + VECCHI:
    if ARCHIVIO != 'nasa':
        s['anno'] = anno_film(s)
        if s.get('simboli_nazisti') is None and re.search(r'swastika|nazi flag|nazi banner|nazi symbol', str(s.get('cosa')) + ' ' + ' '.join(s.get('tag') or []), re.I):
            s['simboli_nazisti'] = True
for s in spezzoni:
    s['ok'] = bool(buono(s))
for s in VECCHI:   # regole aggiornate valgono anche per gli spezzoni gia' etichettati (gratis)
    if s.get('cosa'):
        s['ok'] = bool(buono(s))
ok = [s for s in spezzoni if s['ok']]
if not SOLO_PROVA:
    json.dump(VECCHI + [{k: v for k, v in s.items() if k != 'img'} for s in spezzoni], open(F_IND, 'w'), ensure_ascii=False, indent=1)
col = 8; tw, th = 240, 135
G = Image.new('RGB', (col * tw, ((len(spezzoni) + col - 1) // col) * (th + 30)), 'black'); d = ImageDraw.Draw(G)
for i, s in enumerate(spezzoni):
    x, y = (i % col) * tw, (i // col) * (th + 30)
    im = Image.open(s['img']); im.thumbnail((tw, th)); G.paste(im, (x, y))
    d.rectangle((x, y + th, x + tw - 2, y + th + 28), fill=(0, 110, 0) if s['ok'] else (130, 0, 0))
    d.text((x + 3, y + th + 2), f"{s['n']} {str(s.get('cosa') or '')[:34]}", fill='white')
    d.text((x + 3, y + th + 14), f"{s.get('luogo') or '?'} q{s.get('qualita') or '?'}", fill='white')
G.save(os.path.join(CART, 'controllo.jpg'), quality=75)   # solo gli spezzoni di questo giro
riepilogo = (time.strftime('%Y-%m-%d') + f' | sorgenti: {len(sorgenti)} | spezzoni nuovi: {len(spezzoni)} | buoni nuovi: {len(ok)} | '
             f'buoni in libreria: {sum(1 for x in VECCHI if x.get("ok")) + len(ok)} | chiamate Haiku: {SPESA["chiamate"]} | '
             f'spesa: {SPESA["tot"]:.3f} $ (tetto {MAX_SPESA:.2f} $)\n')
if not SOLO_PROVA:
    open(os.path.join(CART, 'costi.txt'), 'a').write(riepilogo)   # storico di tutti i giri
else:
    open(os.path.join(CART, 'prova_a_secco.txt'), 'w').write(riepilogo + '\n'.join(f"{x['nasa_id']} | {x['titolo'][:80]} | {x.get('licenza', '')}" for x in spezzoni) + '\n')
log(riepilogo)
