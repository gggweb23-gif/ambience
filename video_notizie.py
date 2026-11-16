#!/usr/bin/env python3
"""VIDEO NOTIZIE (16 nov 2026, Giorgio: "cavalchiamo le notizie tech con le caricature dei personaggi veri").
Dal file notizie/<nome>.json (copione scritto SOLO con fatti delle fonti, scena per scena) al video finito 2560x1440:
  1) voce ElevenLabs con i tempi di ogni lettera (sottotitoli parola per parola)
  2) caricature dei personaggi: foto vera da Wikimedia Commons -> caricatura (Nano Banana 2) -> scontorno (birefnet)
     salvate in caricature/<persona>/<posa>.png e riusate nei video dopo (si paga una volta sola)
  3) scene a cartone in 4K (Seedream 4.5, ~0,04 $) controllate da Claude Haiku (niente difetti, niente scritte); niente Pexels (16 nov sera)
  4) STILE DINAMICO: da ogni scena piu' riprese (largo, mezzo busto, medio, dettagli) ogni ~2,5 s, mappe animate, dossier, frasi a effetto,
     dichiarazioni vere con una seconda voce, nome e luogo a schermo, capitoli, contatori e titoli animati
  5) musica di sottofondo bassa che si abbassa sotto la voce + pulsante iscriviti + copertina
Env: NOTIZIA (percorso del json), FAL_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY, TETTO_DOLLARI (default 1.0)
Uscita: prove_video/notizie/<nome>/video.mp4, copertina.jpg, capitoli.json, costi.txt"""
import base64, io, json, math, os, random, re, shutil, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

ROOT = os.path.dirname(os.path.abspath(__file__))
E = os.environ.get
N = json.load(open(E('NOTIZIA')))
NOME = N['nome']
OUT = os.path.join(ROOT, 'prove_video', 'notizie', NOME); os.makedirs(OUT, exist_ok=True)
LAV = os.path.join(ROOT, 'lavoro_notizie', NOME); os.makedirs(LAV, exist_ok=True)
CAR = os.path.join(ROOT, 'caricature')
os.environ.setdefault('COSTI_FILE', os.path.join(LAV, 'costi_video.jsonl'))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'strumenti'))
import costi as CO
import iscrizione as IS

W, H, FPS = 2560, 1440, 30
TETTO = float(N.get('budget_dollari') or E('TETTO_DOLLARI') or 1.0)   # colonna budget del canale (Giorgio: max 3 $ a video)
VOCE = str(N.get('voce') or 'glnsgBC77wt5zOYU0szz')
F_TITOLI = os.path.join(ROOT, 'ctr_test', 'Anton.ttf')
F_TESTI = os.path.join(ROOT, 'fonts_costo_vero', 'ArchivoBlack-Regular.ttf')
GIALLO, ROSSO, NERO, BIANCO, BLU = (255, 214, 0), (226, 35, 45), (14, 16, 24), (255, 255, 255), (40, 120, 255)
STILE = ('Bold editorial cartoon illustration for a news explainer: thick clean dark outlines, flat vibrant colors with soft cel shading, '
         'slightly exaggerated proportions, rich detail, cinematic composition, crisp and sharp. ')
NO_TESTO = 'Absolutely no text, no letters, no numbers, no words, no logos, no signs with writing anywhere in the image. '


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def http(url, data=None, headers=None, timeout=180, raw=False):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'User-Agent': 'NotizieBot/1.0 (github.com/gggweb23-gif/ambience)'}
    if isinstance(data, (dict, list)):
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def spesa_ok(prossima):
    if CO.totale() + prossima > TETTO:
        raise RuntimeError(f'tetto di spesa del video raggiunto ({CO.totale():.2f} $ + {prossima:.2f} > {TETTO:.2f} $)')


def fal(endpoint, dati, costo):
    spesa_ok(costo)
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/' + endpoint, dati, hd, timeout=120)
    for _ in range(200):
        time.sleep(2.5)
        st = http(inv['status_url'], headers=hd, timeout=60).get('status')
        if st == 'COMPLETED':
            break
    r = http(inv['response_url'], headers=hd, timeout=60)
    CO.registra('fal', endpoint, dollari=costo)
    return r


def haiku_immagine(im, domanda, max_tokens=5):
    if not E('ANTHROPIC_API_KEY'):
        return ''
    buf = io.BytesIO(); im.convert('RGB').resize((768, int(768 * im.height / im.width))).save(buf, 'JPEG', quality=88)
    r = http('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
        {'type': 'text', 'text': domanda}]}]}, {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'}, timeout=60)
    CO.registra('claude', 'claude-haiku-4-5-20251001', usage=r.get('usage'), nota='controllo immagine')
    return r['content'][0]['text'].strip().upper()


DIFETTI = ('Look carefully at this AI cartoon image. Count the arms, hands and legs of every person and animal. Answer SI if there is ANY error: '
           'extra or missing arms, hands or legs, more than one head on a body, fused or duplicated bodies, deformed faces, impossible objects, '
           'or ANY visible text, letters, numbers or logo. Otherwise answer NO. Answer only SI or NO.')


MODELLO_VOCE = str(N.get('voce_modello') or 'eleven_v3')   # 16 nov (Giorgio): voce C, stessa voce col modello eleven_v3, piu' umana e autorevole
# 16 nov sera (Giorgio, stile dinamico): le dichiarazioni VERE riportate dalle fonti le legge una seconda voce, come un dialogo (mai battute inventate)
VOCE_CITAZIONI = str(N.get('voce_citazioni') or 'onwK4e9ZLuTAKqWW03F9')


def segmenti():
    """Pezzi di testo nell'ordine in cui si dicono: (voce, testo, scena, tipo). La citazione segue il testo della sua scena."""
    out = []
    for i, s in enumerate(N['scene']):
        out.append((VOCE, s['testo'].strip(), i, 'testo'))
        c = s.get('citazione') or {}
        if c.get('testo', '').strip():
            out.append((VOCE_CITAZIONI, c['testo'].strip(), i, 'citazione'))
    return out


def _allinea(mp3, testo):
    """Tempi di ogni lettera di un audio gia' fatto (ElevenLabs forced alignment), se il modello non li da' da solo."""
    bnd = 'notizie' + str(random.randint(10 ** 8, 10 ** 9))
    corpo = (f'--{bnd}\r\nContent-Disposition: form-data; name="text"\r\n\r\n{testo}\r\n'
             f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="v.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode() + open(mp3, 'rb').read() + f'\r\n--{bnd}--\r\n'.encode()
    j = http('https://api.elevenlabs.io/v1/forced-alignment', corpo, {'xi-api-key': E('ELEVENLABS_API_KEY', ''), 'Content-Type': f'multipart/form-data; boundary={bnd}'}, timeout=300)
    ch = j['characters']
    return {'characters': [c['text'] for c in ch], 'character_start_times_seconds': [c['start'] for c in ch], 'character_end_times_seconds': [c['end'] for c in ch]}


def _una_voce(voce_id, b, f):
    imp = ({'stability': .5, 'similarity_boost': .8, 'style': 0, 'use_speaker_boost': True} if 'v3' in MODELLO_VOCE else
           {'stability': .42, 'similarity_boost': .78, 'style': .28, 'speed': float(N.get('voce_velocita') or 1.08), 'use_speaker_boost': True})
    a = None
    try:
        j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{voce_id}/with-timestamps?output_format=mp3_44100_192',
                 {'text': b, 'model_id': MODELLO_VOCE, 'voice_settings': imp}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300)
        open(f, 'wb').write(base64.b64decode(j['audio_base64'])); a = j.get('alignment')
    except urllib.error.HTTPError as e:
        log('voce con i tempi non disponibile per', MODELLO_VOCE, e.code, '-> audio semplice + allineamento')
        open(f, 'wb').write(http(f'https://api.elevenlabs.io/v1/text-to-speech/{voce_id}?output_format=mp3_44100_192',
                                 {'text': b, 'model_id': MODELLO_VOCE, 'voice_settings': imp}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300, raw=True))
    if not a or not a.get('characters'):
        a = _allinea(f, b)
    CO.registra('elevenlabs', MODELLO_VOCE, crediti=len(b))
    return a


def voce_a_blocchi(segs, p, pj):
    """Voce a blocchi (max ~2.400 caratteri e una sola voce per blocco), poi tutto unito con i tempi giusti."""
    blocchi = []   # [voce, testo]
    for v, t, _, _ in segs:
        if blocchi and blocchi[-1][0] == v and len(blocchi[-1][1]) + len(t) + 1 <= 2400:
            blocchi[-1][1] += ' ' + t
        else:
            blocchi.append([v, t])
    parti, al = [], {'characters': [], 'character_start_times_seconds': [], 'character_end_times_seconds': []}
    off = 0.0
    for i, (v, b) in enumerate(blocchi):
        f = os.path.join(LAV, f'voce_{i:02d}.mp3'); a = None
        for k in range(4):
            try:
                a = _una_voce(v, b, f); break
            except Exception as e:
                log('voce non riuscita, riprovo:', str(e)[:200]); time.sleep(5 * (k + 1))
                if v != VOCE and k >= 1:   # la seconda voce non va: la citazione la legge la voce principale (mai un buco)
                    v = VOCE
        if a is None:
            raise RuntimeError('ElevenLabs non risponde')
        d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip())
        if i:   # lo spazio tra un blocco e l'altro
            al['characters'].append(' '); al['character_start_times_seconds'].append(off); al['character_end_times_seconds'].append(off)
        al['characters'] += a['characters']
        al['character_start_times_seconds'] += [x + off for x in a['character_start_times_seconds']]
        al['character_end_times_seconds'] += [x + off for x in a['character_end_times_seconds']]
        parti.append(f); off += d
    if len(parti) == 1:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', parti[0], '-c:a', 'libmp3lame', '-b:a', '192k', p], check=True)
    else:   # voci diverse: si ricodifica tutto insieme (stesso formato)
        lst = os.path.join(LAV, 'voci.txt'); open(lst, 'w').write(''.join(f"file '{x}'\n" for x in parti))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-ar', '44100', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '192k', p], check=True)
    json.dump(al, open(pj, 'w'))


# ============================================================ 1) VOCE
def voce():
    p = os.path.join(MAT, 'voce.mp3'); pj = p[:-4] + '.json'
    segs = segmenti()
    testo = ' '.join(t for _, t, _, _ in segs)
    pt = p[:-4] + '_testo.txt'
    chiave = MODELLO_VOCE + '|' + VOCE + '|' + VOCE_CITAZIONI + '|' + '\n'.join(v + ':' + t for v, t, _, _ in segs)   # cambia testo o voce: voce nuova
    if not os.path.exists(pt) or open(pt).read() != chiave:
        for x in (p, pj):
            os.path.exists(x) and os.remove(x)
    if not (os.path.exists(p) and os.path.exists(pj)):
        voce_a_blocchi(segs, p, pj); open(pt, 'w').write(chiave)
    al = json.load(open(pj))
    ch, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    parole, cur, t0, i0 = [], '', None, 0
    for idx, (c, a, b) in enumerate(zip(ch, st, en)):
        if c.isspace():
            if cur:
                parole.append({'w': cur, 'a': t0, 'b': fine, 'i': i0}); cur = ''
            continue
        if not cur:
            t0 = a; i0 = idx
        cur += c; fine = b
    if cur:
        parole.append({'w': cur, 'a': t0, 'b': fine, 'i': i0})
    # inizio di ogni pezzo (posizione del suo primo carattere nel testo unito)
    pos = 0
    for k, (v, t, si, tipo) in enumerate(segs):
        a = st[min(pos, len(st) - 1)]
        segs[k] = {'voce': v, 'testo': t, 'scena': si, 'tipo': tipo, 'a': a, 'p0': pos, 'p1': pos + len(t)}
        pos += len(t) + 1
    for w in parole:   # ogni parola sa di quale pezzo fa parte (sottotitoli e scritte a tempo)
        w['seg'] = next((k for k, s in enumerate(segs) if s['p0'] <= w['i'] < s['p1'] + 1), len(segs) - 1)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip())
    return p, parole, segs, dur


# ============================================================ 2) CARICATURE
def foto_commons(nome, dest):
    if os.path.exists(dest):
        return dest
    q = urllib.parse.urlencode({'action': 'query', 'generator': 'search', 'gsrsearch': nome, 'gsrnamespace': 6, 'gsrlimit': 15, 'prop': 'imageinfo',
                                'iiprop': 'url|size|mime|extmetadata', 'iiurlwidth': 1200, 'format': 'json'})
    j = http('https://commons.wikimedia.org/w/api.php?' + q, timeout=60)
    pagine = sorted((j.get('query') or {}).get('pages', {}).values(), key=lambda x: x.get('index', 99))
    cognome = nome.split()[-1].lower()
    for pg in pagine:
        ii = (pg.get('imageinfo') or [{}])[0]
        if cognome not in pg.get('title', '').lower() or ii.get('mime') not in ('image/jpeg', 'image/png') or (ii.get('width') or 0) < 500:
            continue
        try:
            im = Image.open(io.BytesIO(http(ii.get('thumburl') or ii['url'], raw=True, timeout=120))).convert('RGB')
            if haiku_immagine(im, f'Is this a clear photo of ONE real person (face clearly visible, not a group, not a drawing, not a logo)? Answer only SI or NO.').startswith('SI'):
                im.save(dest, quality=95)
                md = ii.get('extmetadata') or {}
                open(dest[:-4] + '_fonte.txt', 'w').write(f"{pg['title']}\n{ii.get('descriptionurl', '')}\nlicenza: {(md.get('LicenseShortName') or {}).get('value', '')}\n"
                                                          f"autore: {re.sub('<[^>]+>', '', (md.get('Artist') or {}).get('value', ''))}\n")
                log('foto vera da Commons:', pg['title']); return dest
        except Exception as e:
            log('foto commons scartata', pg.get('title'), str(e)[:80])
    return None


def scontorna(url, dest):
    r = fal('fal-ai/birefnet', {'image_url': url}, 0.002)
    im = Image.open(io.BytesIO(http(r['image']['url'], raw=True, timeout=120))).convert('RGBA')
    bb = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
    im = im.crop(bb) if bb else im
    im.save(dest); return dest


def posa(chi, nome_posa):
    """caricature/<chi>/<posa>.png (trasparente). Si fa una volta sola e resta nella libreria."""
    d = os.path.join(CAR, chi); os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, nome_posa + '.png')
    if os.path.exists(dest):
        return dest
    pp = N['personaggi'][chi]; descr_posa = pp['pose'][nome_posa]
    stile = STILE
    if isinstance(descr_posa, dict):   # una posa puo' avere uno stile di disegno suo (per confrontare gli stili)
        descr_posa = descr_posa['posa']   # 16 nov (Giorgio): UN SOLO stile di caricatura (il primo, cartone editoriale), mai 3D o altri
    foto = foto_commons(pp['commons'], os.path.join(d, 'foto.jpg')) if pp.get('commons') else None
    for k in range(3):
        try:
            if foto:
                prompt = (f"Turn the real person in this photo ({pp.get('chi', '')}) into a FULL-BODY editorial cartoon caricature, head to feet visible: "
                          'big head on a smaller body, strongly recognizable likeness (same face shape, hairline, hair color, glasses or beard if present, skin tone), '
                          f'friendly professional caricature, not mocking. Pose: {descr_posa}. Exactly two arms and two hands with five fingers, normal anatomy. '
                          + stile + 'Isolated on a plain pure white background, no shadow, no floor. ' + NO_TESTO)
                img = 'data:image/jpeg;base64,' + base64.b64encode(open(foto, 'rb').read()).decode()
                r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': [img], 'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1}, 0.08)
            else:
                prompt = (f"FULL-BODY editorial cartoon character, head to feet visible: {pp.get('descrizione') or pp.get('chi') or chi}. Big head on a smaller body. Pose: {descr_posa}. "
                          'Exactly two arms and two hands with five fingers, normal anatomy. ' + stile + 'Isolated on a plain pure white background, no shadow, no floor. ' + NO_TESTO)
                r = fal('fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': prompt, 'image_size': {'width': 1536, 'height': 2048}, 'num_images': 1}, 0.04)
            url = r['images'][0]['url']
            im = Image.open(io.BytesIO(http(url, raw=True, timeout=120))).convert('RGB')
            if k < 2 and haiku_immagine(im, DIFETTI).startswith('SI'):
                log('caricatura con un difetto, la rifaccio:', chi, nome_posa); continue
            scontorna(url, dest); log('caricatura pronta:', chi, nome_posa); return dest
        except RuntimeError:
            raise
        except Exception as e:
            log('caricatura non riuscita, riprovo:', chi, str(e)[:200]); time.sleep(4)
    return None


# ============================================================ 3) SFONDI (16 nov sera, Giorgio: niente piu' Pexels, solo i nostri disegni)
MAT = os.path.join(OUT, 'materiali'); os.makedirs(MAT, exist_ok=True)
GW, GH = 3840, 2160   # i set si disegnano in 4K: dalla stessa scena si tagliano piu' inquadrature nitide (largo, medio, dettaglio)


def descr_sfondo(chiave):
    st = (N.get('sets') or {}).get(chiave) or {}
    return (N.get('sfondi') or {}).get(chiave) or st.get('descr') or chiave.replace('_', ' ')


LIB = os.path.join(ROOT, 'libreria_scene')                        # immagini dei luoghi gia' disegnati (cache di GitHub, non nel repository)
LIB_INDICE = os.path.join(ROOT, 'notizie', 'libreria_scene.json')  # elenco dei luoghi: descrizione, luogo, filone, quando usati


def sfondo(chiave):
    dest = os.path.join(MAT, f'sfondo_{chiave}.jpg')
    if os.path.exists(dest):
        return dest
    lib_id = ((N.get('sets') or {}).get(chiave) or {}).get('lib')
    if lib_id and os.path.exists(os.path.join(LIB, lib_id + '.jpg')):   # luogo gia' disegnato in un altro giorno: gratis
        shutil.copy(os.path.join(LIB, lib_id + '.jpg'), dest); log('scena dalla libreria dei luoghi:', chiave, '<-', lib_id); return dest
    if N.get('materiali_da'):   # versione in un'altra lingua: stesse immagini del video gemello, gratis
        gem = os.path.join(ROOT, 'prove_video', 'notizie', N['materiali_da'], 'materiali', f'sfondo_{chiave}.jpg')
        if os.path.exists(gem):
            shutil.copy(gem, dest); return dest
    descr = descr_sfondo(chiave)
    vuota = bool(re.search(r'empty of people|no people|nobody', descr, re.I))
    for k in range(3):   # 16 nov sera: max 3 immagini per scena (prima fino a 4: troppi scarti, troppa spesa)
        try:
            semplice = 'Very simple, clean composition: no screens, no papers, no signs, no flags, no maps, no clocks, nothing with writing. ' if k >= 1 else ''
            prompt = (STILE + f'Scene: {descr}. Wide 16:9 cinematic establishing shot, rich detail everywhere so that close crops still look good. ' + semplice
                      + ('Absolutely NO people, no characters, no faces. ' if vuota else '') + NO_TESTO)
            r = fal('fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': prompt, 'image_size': {'width': GW, 'height': GH}, 'num_images': 1}, 0.04)
            im = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True, timeout=180))).convert('RGB')
            if max(ImageStat.Stat(im.resize((64, 36))).mean) < 18:
                log('sfondo nero, rifaccio'); continue
            if k < 2:
                dom = ('Look at this AI cartoon background. Answer "SI: <reason in 5 words>" ONLY if there is a clear problem: deformed or duplicated people '
                       '(extra arms, hands, heads), impossible broken objects, or clearly READABLE words, letters or a logo (tiny unreadable marks are fine)'
                       + ('; or any person or face is visible (this scene must be empty of people)' if vuota else '') + '. Otherwise answer only NO.')
                esito = haiku_immagine(im, dom, max_tokens=20)
                if esito.startswith('SI'):
                    log('sfondo scartato:', chiave, esito[:60]); continue
            im = im.resize((GW, GH), Image.LANCZOS) if im.size != (GW, GH) else im
            im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2)).save(dest, quality=94); return dest
        except RuntimeError:
            raise
        except Exception as e:
            log('sfondo non riuscito, riprovo:', chiave, str(e)[:200]); time.sleep(4)
    return None


# ============================================================ 4) GRAFICA
_FONT = {}


def font(f, s):
    k = (f, s)
    if k not in _FONT:
        _FONT[k] = ImageFont.truetype(f, s)
    return _FONT[k]


def ease(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def back(x):
    x = max(0.0, min(1.0, x)); c = 1.70158; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def testo_box(d, xy, t, f, fill, stroke=0, sfill=NERO, anchor='la'):
    d.text(xy, t, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill, anchor=anchor)


def it_num(v, dec):
    s = f'{abs(v):,.{dec}f}'
    if N.get('lingua', 'it') != 'en':   # stile italiano: 1.000 e 76,5
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return ('-' if v < 0 else '') + s


def disegna_carta(im, t, cx, cy, larg, timbro=None):
    """Carta della banca disegnata in codice (nera, nome REVOLUT) che entra ruotando; poi il timbro rosso che sbatte sopra."""
    k = back(t / .45)
    if k <= 0:
        return
    w, h = int(larg), int(larg * .63)
    c = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(w * .06), fill=(22, 24, 30, 255), outline=(90, 95, 110, 255), width=6)
    d.rounded_rectangle((int(w * .08), int(h * .34), int(w * .2), int(h * .54)), radius=10, fill=(212, 180, 90, 255))
    testo_box(d, (int(w * .08), int(h * .1)), 'Revolut', font(F_TESTI, int(h * .14)), BIANCO)
    testo_box(d, (int(w * .08), int(h * .7)), '••••  ••••  ••••  2026', font(F_TESTI, int(h * .08)), (200, 200, 210))
    ang = (1 - k) * 25 - 6
    c = c.rotate(ang, expand=True, resample=Image.BICUBIC)
    s = max(.05, .6 + .4 * k)
    c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.LANCZOS)
    ombra = Image.new('RGBA', c.size, (0, 0, 0, 0)); ombra.putalpha(c.getchannel('A').point(lambda v: int(v * .55)))
    ombra = ombra.filter(ImageFilter.GaussianBlur(18))
    im.alpha_composite(ombra, (int(cx - c.width / 2 + 18), int(cy - c.height / 2 + 26)))
    im.alpha_composite(c, (int(cx - c.width / 2), int(cy - c.height / 2)))
    if timbro and t > .6:
        disegna_timbro(im, t - .6, cx, cy, timbro, larg * 1.05)


def disegna_timbro(im, t, cx, cy, testo, larg):
    k = ease(t / .18)
    f = font(F_TITOLI, int(larg / max(6, len(testo)) * 2.0))
    tw = f.getbbox(testo)[2]; th = f.size
    w, h = tw + 90, int(th * 1.45)
    c = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rounded_rectangle((6, 6, w - 6, h - 6), radius=18, fill=(250, 246, 238, 235), outline=ROSSO + (255,), width=14)
    testo_box(d, (w // 2, h // 2), testo, f, ROSSO + (255,), anchor='mm')
    random.seed(7)   # timbro "vero": qualche buco nell'inchiostro
    buchi = Image.new('L', c.size, 255); db = ImageDraw.Draw(buchi)
    for _ in range(260):
        x, y, r = random.randint(0, w), random.randint(0, h), random.randint(2, 7); db.ellipse((x, y, x + r, y + r), fill=random.randint(0, 120))
    c.putalpha(Image.composite(c.getchannel('A'), Image.new('L', c.size, 0), buchi))
    c = c.rotate(-9, expand=True, resample=Image.BICUBIC)
    s = 1.9 - .9 * k
    c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    a = c.getchannel('A').point(lambda v: int(v * min(1, k * 1.4))); c.putalpha(a)
    im.alpha_composite(c, (int(cx - c.width / 2), int(cy - c.height / 2)))


def disegna_numero(im, t, g, zona):
    """Contatore che sale fino al valore, in un pannello scuro con barra rossa."""
    if t <= 0:
        return
    k = ease(t / .35); v = g['valore'] * ease((t - .1) / 1.0)
    x0, y0, x1 = zona
    fn, fu, fs = font(F_TITOLI, 260), font(F_TESTI, 60), font(F_TESTI, 50)
    dec = int(g.get('decimali') or 0); pre = g.get('prefisso') or ''
    num = pre + it_num(v, dec); finale = pre + it_num(g['valore'], dec)
    bb = fn.getbbox(finale, anchor='ls')
    while fu.size > 36 and fu.getbbox(g.get('unita', ''))[2] > (x1 - x0) - 120:
        fu = font(F_TESTI, fu.size - 4)
    w = max(bb[2], fu.getbbox(g.get('unita', ''))[2], fs.getbbox(g.get('sopra', ''))[2] if g.get('sopra') else 0) + 130
    y = 34
    ys = y
    if g.get('sopra'):
        y += 66
    yb = y - bb[1]                       # linea di base del numero (la cima tocca y)
    yu = yb + 40
    h = yu + fu.size + 46
    pan = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(pan)
    d.rounded_rectangle((0, 0, w, h), radius=28, fill=(10, 12, 18, 228))
    d.rectangle((0, 0, 18, h), fill=ROSSO + (255,))
    if g.get('sopra'):
        testo_box(d, (62, ys), g['sopra'], fs, (210, 210, 220))
    testo_box(d, (58, yb), num, fn, (ROSSO if g.get('rosso') else GIALLO) + (255,), anchor='ls')
    testo_box(d, (62, yu), g.get('unita', ''), fu, BIANCO)
    pan.putalpha(pan.getchannel('A').point(lambda a: int(a * k)))
    im.alpha_composite(pan, (x0 + int((1 - k) * -120), y0))


def disegna_titolo(im, t, g, zona):
    k = ease(t / .3)
    x0, y0, x1 = zona; w = x1 - x0
    t1, t2 = g.get('testo', ''), g.get('sotto', '')
    s1 = 210
    while s1 > 90 and font(F_TITOLI, s1).getbbox(t1)[2] > w - 100:
        s1 -= 8
    f1, f2 = font(F_TITOLI, s1), font(F_TESTI, 56)
    while t2 and f2.size > 34 and f2.getbbox(t2)[2] > w - 100:
        f2 = font(F_TESTI, f2.size - 4)
    larg1 = f1.getbbox(t1)[2] + 90
    h1 = int(s1 * 1.22)
    dx = int((1 - k) * (-(larg1 + 100) if x0 < W * .3 else (W - x0)))
    b = Image.new('RGBA', (larg1, h1), ROSSO + (255,)); d = ImageDraw.Draw(b)
    testo_box(d, (45, h1 // 2), t1, f1, BIANCO, anchor='lm')
    im.alpha_composite(b, (x0 + dx, y0))
    if t2:
        k2 = ease((t - .18) / .3)
        larg2 = f2.getbbox(t2)[2] + 70; h2 = 96
        b2 = Image.new('RGBA', (larg2, h2), (10, 12, 18, 235)); d2 = ImageDraw.Draw(b2)
        testo_box(d2, (35, h2 // 2), t2, f2, GIALLO, anchor='lm')
        b2.putalpha(b2.getchannel('A').point(lambda a: int(a * k2)))
        im.alpha_composite(b2, (x0 + int((1 - k2) * (-60 if x0 < W * .3 else 60)), y0 + h1 + 14))


def disegna_didascalia(im, t, testo, lato):
    k = ease((t - .5) / .3)
    if k <= 0:
        return
    f = font(F_TESTI, 46); w = f.getbbox(testo)[2] + 60; h = 80
    b = Image.new('RGBA', (w, h), (255, 255, 255, 240)); d = ImageDraw.Draw(b)
    d.rectangle((0, 0, 12, h), fill=ROSSO + (255,))
    testo_box(d, (34, h // 2), testo, f, NERO, anchor='lm')
    b.putalpha(b.getchannel('A').point(lambda a: int(a * k)))
    x = int(W * .58) if lato == 'dx' else 120
    x = min(x, W - w - 60)
    im.alpha_composite(b, (x, int(H * .62)))


_POSE = {}


def disegna_personaggio(im, t, png, lato):
    if png not in _POSE:
        p = Image.open(png).convert('RGBA'); hh = int(H * .86)
        _POSE[png] = p.resize((int(p.width * hh / p.height), hh), Image.LANCZOS)
    p = _POSE[png]
    k = back(t / .45)
    resp = 1 + .012 * math.sin(t * 2 * math.pi / 2.4)   # respiro: sempre qualcosa che si muove
    pw, ph = int(p.width), int(p.height * resp)
    q = p.resize((pw, ph), Image.BILINEAR) if resp != 1 else p
    cx = W * (.73 if lato == 'dx' else .27)
    entra = (1 - k) * (W * .45) * (1 if lato == 'dx' else -1)
    x = int(cx - pw / 2 + entra); y = H - ph + 30
    om = Image.new('RGBA', (pw, 70), (0, 0, 0, 0)); ImageDraw.Draw(om).ellipse((pw * .15, 10, pw * .85, 60), fill=(0, 0, 0, 90))
    im.alpha_composite(om.filter(ImageFilter.GaussianBlur(14)), (x, H - 70))
    im.alpha_composite(q, (x, y))


def disegna_fisse(im, tg, fonte):
    """ULTIM'ORA + data in alto a sinistra (sempre), fonte in basso a sinistra."""
    f = font(F_TESTI, 44)
    et = N.get('etichetta') or "ULTIM'ORA"
    w1 = f.getbbox(et)[2] + 110
    d = ImageDraw.Draw(im)
    d.rectangle((70, 60, 70 + w1, 140), fill=ROSSO + (255,))
    pul = .5 + .5 * math.sin(tg * 2 * math.pi / 1.1)
    d.ellipse((95, 87, 121, 113), fill=(255, 255, 255, int(110 + 145 * pul)))
    testo_box(d, (140, 100), et, f, BIANCO, anchor='lm')
    dt = N.get('data') or ''
    if dt:
        w2 = f.getbbox(dt)[2] + 60
        d.rectangle((70 + w1, 60, 70 + w1 + w2, 140), fill=(10, 12, 18, 230))
        testo_box(d, (70 + w1 + 30, 100), dt, f, BIANCO, anchor='lm')
    if fonte and N.get('fonte_a_schermo'):   # 16 nov (Giorgio): la fonte NON va a schermo, resta solo nel file della notizia
        fs = font(F_TESTI, 34); tx = 'FONTE: ' + fonte.upper()
        w3 = fs.getbbox(tx)[2] + 40
        d.rectangle((70, H - 92, 70 + w3, H - 40), fill=(10, 12, 18, 200))
        testo_box(d, (90, H - 66), tx, fs, (230, 230, 235), anchor='lm')


def gruppi_sottotitoli(parole):
    g, cur = [], []
    for p in parole:
        cur.append(p)
        if len(cur) >= 3 or re.search(r'[.,:;?!]$', p['w']):
            g.append(cur); cur = []
    if cur:
        g.append(cur)
    out = []
    for i, x in enumerate(g):
        fine = g[i + 1][0]['a'] if i + 1 < len(g) else x[-1]['b'] + .4
        out.append({'a': x[0]['a'], 'b': min(fine, x[-1]['b'] + .5), 'parole': x})
    return out


def disegna_sottotitoli(im, tg, gruppi):
    g = next((x for x in gruppi if x['a'] <= tg < x['b']), None)
    if not g:
        return
    f = font(F_TITOLI, 118)
    pezzi = [re.sub(r'[.,:;]$', '', p['w']).upper() for p in g['parole']]
    spazio = 30
    larg = sum(f.getbbox(x)[2] for x in pezzi) + spazio * (len(pezzi) - 1)
    k = ease((tg - g['a']) / .12)
    x = (W - larg) // 2; y = int(H * .83) + int((1 - k) * 25)
    d = ImageDraw.Draw(im)
    for p, tx in zip(g['parole'], pezzi):
        on = p['a'] <= tg
        testo_box(d, (x, y), tx, f, GIALLO if on and tg < p['b'] + .15 else BIANCO, stroke=10, sfill=NERO, anchor='ls')
        x += f.getbbox(tx)[2] + spazio


# ============================================================ 5) STILE DINAMICO (16 nov sera, Giorgio dopo il video di Paper Billions)
# "I personaggi restano i nostri, piu' fedeli alla realta'; serve solo piu' dinamicita'": un cambio d'inquadratura ogni ~2,5 secondi.
# Il trucco del cinema: da ogni scena disegnata (in 4K) si tagliano piu' riprese (largo, mezzo busto di ogni persona, medio, dettagli),
# poi mappe animate, il dossier del protagonista, frasi a effetto scritte a mano SOPRA la scena, dichiarazioni vere lette da una
# seconda voce, nome e luogo a schermo, capitoli con il loro titolo. Niente Pexels.
F_MANO = os.path.join(ROOT, 'fonts_notizie', 'PermanentMarker-Regular.ttf')
GEO = os.path.join(ROOT, 'risorse_notizie', 'paesi50.geojson')
PASSO = float(N.get('secondi_per_inquadratura') or 3.2)
MAX_RIPRESE = int(N.get('riprese_per_scena') or 3)   # 16 nov sera (Giorgio: troppe riprese della stessa immagine): max 3 angoli per scena disegnata, mai ripetuti
INQ, GRUPPI, SEGS = [], [], []
COLORI = {'rosso': (214, 40, 48), 'blu': (24, 72, 178), 'giallo': (250, 190, 20), 'verde': (40, 160, 90), 'arancio': (240, 120, 30), 'viola': (130, 70, 200)}


def chi_nome(chi):
    pp = (N.get('personaggi') or {}).get(chi) or {}
    t = pp.get('chi') or pp.get('commons') or chi
    nome, _, ruolo = t.partition(',')
    return nome.strip().upper(), ruolo.strip().upper()


# ---------------- immagini in memoria (per processo)
_IMG = {}


def img(p, size=None):
    k = (p, size)
    if k not in _IMG:
        im = Image.open(p).convert('RGBA') if size is None else img(p).resize(size, Image.LANCZOS)
        _IMG[k] = im
    return _IMG[k]


def persona_alta(png, h):
    p = img(png); w = max(1, int(p.width * h / p.height))
    return img(png, (w, int(h)))


def ritaglio(bg, fx, fy, frac):
    """Taglio del fondo 4K: frazione frac della larghezza, centrato su (fx, fy) in 0..1, portato a 2560x1440."""
    cw, ch = bg.width * frac, bg.height * frac
    x0 = min(max(0, fx * bg.width - cw / 2), bg.width - cw); y0 = min(max(0, fy * bg.height - ch / 2), bg.height - ch)
    return bg.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)


def ombra_piedi(im, cx, w):
    om = Image.new('RGBA', (int(w), 80), (0, 0, 0, 0)); ImageDraw.Draw(om).ellipse((w * .12, 12, w * .88, 66), fill=(0, 0, 0, 100))
    im.alpha_composite(om.filter(ImageFilter.GaussianBlur(16)), (int(cx - w / 2), H - 84))


def cast_set(k):
    out = []
    for c in ((N.get('sets') or {}).get(k) or {}).get('cast') or []:
        png = PNG.get((c['chi'], c['posa']))
        if png:
            out.append(dict(c, png=png))
    return out[:2]


PNG, SF = {}, {}


def base_set(q):
    """Immagine ferma dell'inquadratura (fondo + persone) e punto verso cui spinge la camera."""
    bg = img(SF[q['set']]); cast = cast_set(q['set']); fr = q['framing']
    if fr == 'largo':
        im = bg.resize((W, H), Image.LANCZOS) if bg.size != (W, H) else bg.copy()
        hh = H * (.80 if len(cast) < 2 else .76)
        for c in cast:
            p = persona_alta(c['png'], hh); cx = W * (.73 if c.get('lato', 'dx') == 'dx' else .27)
            ombra_piedi(im, cx, p.width); im.alpha_composite(p, (int(cx - p.width / 2), int(H - p.height + 24)))
        return im, (.5, .45)
    if fr == 'medio':
        im = ritaglio(bg, .5, .55, .74)
        for c in cast:
            p = persona_alta(c['png'], H * 1.18); cx = W * (.72 if c.get('lato', 'dx') == 'dx' else .28)
            im.alpha_composite(p, (int(cx - p.width / 2), int(H * .1)))
        return im, (.5, .35)
    if fr.startswith('pp:'):
        c = next((x for x in cast if x['chi'] == fr[3:]), cast[0] if cast else None)
        dx = c and c.get('lato', 'dx') == 'dx'
        im = ritaglio(bg, .7 if dx else .3, .5, .56).filter(ImageFilter.GaussianBlur(7))   # profondita' di campo: la persona a fuoco, il fondo morbido
        if c:
            p = persona_alta(c['png'], H * 1.7); cx = W * (.6 if dx else .4)
            im.alpha_composite(p, (int(cx - p.width / 2), int(H * .05)))
            return im, (.6 if dx else .4, .3)
        return im, (.5, .4)
    if fr in ('det_sx', 'det_dx', 'det_c'):
        fx = {'det_sx': .3, 'det_dx': .7, 'det_c': .5}[fr]
        return ritaglio(bg, fx, .45, .58).filter(ImageFilter.UnsharpMask(radius=1.4, percent=35, threshold=2)), (.5, .45)
    return bg.resize((W, H), Image.LANCZOS), (.5, .5)


def inquadrature_set(k, n, stato):
    """n riprese diverse dalla stessa scena, senza mai ripetere quella appena vista."""
    cast = cast_set(k)
    if len(cast) >= 2:
        giro = ['largo', 'pp:' + cast[0]['chi'], 'pp:' + cast[1]['chi'], 'det_c']
    elif cast:
        giro = ['largo', 'pp:' + cast[0]['chi'], 'det_' + ('sx' if cast[0].get('lato', 'dx') == 'dx' else 'dx'), 'medio']
    else:
        giro = ['largo', 'det_sx', 'det_dx', 'det_c']
    i = stato.get(k, 0); out = [giro[(i + j) % len(giro)] for j in range(n)]
    stato[k] = i + n
    return out


# ---------------- mappe disegnate in codice (vettoriali: nitide a ogni zoom)
_GEO = []


def geo():
    if not _GEO:
        for f in json.load(open(GEO))['features']:
            p = f['properties']; gm = f['geometry']
            polys = gm['coordinates'] if gm['type'] == 'MultiPolygon' else [gm['coordinates']]
            nome = (p.get('NAME_IT') if N.get('lingua') == 'it' else None) or p.get('NAME') or p.get('NAME_EN')
            _GEO.append({'iso': {str(p.get(x) or '') for x in ('ADM0_A3', 'ISO_A3', 'SOV_A3', 'GU_A3')} - {'', '-99'}, 'nome': str(nome or ''),
                         'anelli': [poly[0] for poly in polys]})
        # la Crimea si disegna con l'Ucraina, come nei confini riconosciuti dall'ONU (Natural Earth la mette con la Russia)
        rus = next(f for f in _GEO if 'RUS' in f['iso']); ukr = next(f for f in _GEO if 'UKR' in f['iso'])
        for r in list(rus['anelli']):
            xs = [a for a, b in r]; ys = [b for a, b in r]
            if min(xs) > 32 and max(xs) < 37 and min(ys) > 44 and max(ys) < 46.5:
                rus['anelli'].remove(r); ukr['anelli'].append(r)
    return _GEO


def proiezione(m):
    lon0, lat0 = m.get('centro') or [30, 48]
    larg = float(m.get('larghezza') or 30); c = math.cos(math.radians(lat0)); k = W / (larg * c)
    return lambda lon, lat: (W / 2 + (lon - lon0) * c * k, H / 2 + (lat0 - lat) * k)


def base_mappa(m):
    S = 2; pt = proiezione(m)
    im = Image.new('RGB', (W * S, H * S), (150, 196, 224)); d = ImageDraw.Draw(im)
    for y in range(0, H * S, 46):   # leggera trama del mare
        d.line((0, y, W * S, y), fill=(160, 204, 230), width=2)
    evid = {str(x.get('iso', '')).upper(): COLORI.get(x.get('colore', 'rosso'), COLORI['rosso']) for x in m.get('paesi') or []}
    for f in geo():
        for r in f['anelli']:
            xy = [(pt(lo, la)[0] * S, pt(lo, la)[1] * S) for lo, la in r]
            xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
            if max(xs) < 0 or min(xs) > W * S or max(ys) < 0 or min(ys) > H * S:
                continue
            d.polygon(xy, fill=(240, 229, 200))
    for f in geo():   # confini sopra a tutto
        for r in f['anelli']:
            xy = [(pt(lo, la)[0] * S, pt(lo, la)[1] * S) for lo, la in r]
            if max(p[0] for p in xy) < 0 or min(p[0] for p in xy) > W * S:
                continue
            d.line(xy + [xy[0]], fill=(96, 84, 70), width=5, joint='curve')
    return im.resize((W, H), Image.LANCZOS).convert('RGBA'), evid


def strati_paesi(m, evid):
    """Maschera colorata di ogni paese evidenziato e punto dove scrivere il nome."""
    S = 2; pt = proiezione(m); out = []
    for iso, col in evid.items():
        mk = Image.new('L', (W * S, H * S), 0); dm = ImageDraw.Draw(mk); nome, best = '', (0, None)
        for f in geo():
            if iso not in f['iso']:
                continue
            nome = nome or f['nome']
            for r in f['anelli']:
                xy = [(pt(lo, la)[0] * S, pt(lo, la)[1] * S) for lo, la in r]
                dm.polygon(xy, fill=255)
                xs = [p[0] for p in xy]; ys = [p[1] for p in xy]; area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                if area > best[0]:
                    best = (area, (sum(xs) / len(xs) / S, sum(ys) / len(ys) / S))
        mk = mk.resize((W, H), Image.LANCZOS)
        if mk.getbbox():
            pic = mk.resize((128, 72)); px = pic.load(); sx = sy = n = 0   # nome al centro della parte VISIBILE del paese
            for x in range(8, 120):
                for y in range(8, 64):
                    if px[x, y] > 128:
                        sx += x; sy += y; n += 1
            c = (sx / n * W / 128, sy / n * H / 72) if n > 12 else None
            out.append({'mask': mk, 'col': col, 'nome': nome.upper(), 'c': c})
    return out


def disegna_mappa(im, t, q):
    m = q['mappa']; pt = proiezione(m); d = ImageDraw.Draw(im)
    for i, s in enumerate(q['_strati']):
        a = ease((t - .15 - i * .35) / .5)
        if a > 0:
            im.paste(Image.new('RGBA', (W, H), s['col'] + (255,)), (0, 0), s['mask'].point(lambda v: int(v * .72 * a)))
    for i, s in enumerate(q['_strati']):   # nomi dei paesi
        a = ease((t - .45 - i * .35) / .35)
        if a > 0 and s['c'] and 0 < s['c'][0] < W and 0 < s['c'][1] < H:
            f = font(F_TITOLI, 92); x, y = s['c']
            mezzo = f.getbbox(s['nome'])[2] / 2 + 40; x = min(max(x, mezzo), W - mezzo)   # il nome resta tutto dentro lo schermo
            testo_box(d, (x, y + (1 - a) * 30), s['nome'], f, (255, 255, 255, int(255 * a)), stroke=10, sfill=(30, 26, 22), anchor='mm')
    for i, fr in enumerate(m.get('frecce') or []):   # frecce che si disegnano (attacchi, rotte, spostamenti)
        a = ease((t - .8 - i * .6) / .9)
        if a <= 0:
            continue
        (x0, y0), (x1, y1) = pt(*fr['da']), pt(*fr['a'])
        mx, my = (x0 + x1) / 2 - (y1 - y0) * .18, (y0 + y1) / 2 + (x1 - x0) * .18
        pts = [((1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u * u * x1, (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u * u * y1) for u in [j / 40 * a for j in range(41)]]
        col = COLORI.get(fr.get('colore', 'rosso'), COLORI['rosso'])
        d.line(pts, fill=(255, 255, 255, 230), width=30, joint='curve'); d.line(pts, fill=col + (255,), width=18, joint='curve')
        (ax, ay), (bx, by) = pts[-2], pts[-1]; ang = math.atan2(by - ay, bx - ax)
        tri = [(bx + 44 * math.cos(ang), by + 44 * math.sin(ang)), (bx + 34 * math.cos(ang + 2.4), by + 34 * math.sin(ang + 2.4)),
               (bx + 34 * math.cos(ang - 2.4), by + 34 * math.sin(ang - 2.4))]
        d.polygon(tri, fill=col + (255,), outline=(255, 255, 255, 230))
    for i, p in enumerate(m.get('punti') or []):   # puntine con il nome del luogo
        a = back((t - .5 - i * .45) / .4)
        if a <= 0:
            continue
        x, y = pt(p['lon'], p['lat'])
        y -= (1 - min(1, a)) * 120
        d.ellipse((x - 30, y - 92, x + 30, y - 32), fill=ROSSO + (255,), outline=(255, 255, 255, 255), width=6)
        d.polygon([(x - 22, y - 50), (x + 22, y - 50), (x, y)], fill=ROSSO + (255,))
        d.ellipse((x - 11, y - 73, x + 11, y - 51), fill=(255, 255, 255, 255))
        if p.get('nome'):
            f = font(F_TESTI, 50); tw = f.getbbox(p['nome'])[2]; lx = x + 46 if x < W * .75 else x - 46 - tw - 40
            d.rounded_rectangle((lx, y - 110, lx + tw + 40, y - 40), radius=10, fill=(14, 16, 24, 230))
            testo_box(d, (lx + 20, y - 75), p['nome'], f, BIANCO, anchor='lm')


# ---------------- dossier del protagonista (bacheca da indagine)
def base_dossier(q):
    random.seed(len(q['dossier'].get('chi', '')) * 7 + 3)
    sm = Image.new('RGB', (160, 90), (118, 84, 54)); px = sm.load()
    for x in range(160):
        for y in range(90):
            v = random.randint(-14, 14); px[x, y] = (118 + v, 84 + v, 54 + v)
    im = sm.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(3)).convert('RGBA')
    vign = Image.radial_gradient('L').resize((W, H)).point(lambda v: int(v * .7)); nero = Image.new('RGBA', (W, H), (0, 0, 0, 255)); nero.putalpha(vign)
    im.alpha_composite(nero)
    return im


def disegna_dossier(im, t, q):
    ds = q['dossier']; png = q.get('_png'); d = ImageDraw.Draw(im)
    # foto (polaroid) che cade sulla bacheca
    a = back(t / .45)
    if a > 0 and png:
        fw, fh = 760, 900
        fo = Image.new('RGBA', (fw, fh), (250, 248, 242, 255)); ph = Image.new('RGBA', (fw - 70, fh - 220), (226, 222, 212, 255))
        p = persona_alta(png, int((fh - 220) * 1.75)); ph.alpha_composite(p, (int((ph.width - p.width) / 2), 18)); fo.alpha_composite(ph, (35, 35))
        testo_box(ImageDraw.Draw(fo), (fw // 2, fh - 92), chi_nome(ds.get('chi'))[0], font(F_MANO, 64), (30, 30, 40), anchor='mm')
        fo = fo.rotate(-4, expand=True, resample=Image.BICUBIC); s = .7 + .3 * a
        fo = fo.resize((int(fo.width * s), int(fo.height * s)), Image.LANCZOS)
        ombra = Image.new('RGBA', fo.size, (0, 0, 0, 0)); ombra.putalpha(fo.getchannel('A').point(lambda v: int(v * .5)))
        x, y = int(W * .28 - fo.width / 2), int(H * .5 - fo.height / 2)
        im.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(20)), (x + 24, y + 30)); im.alpha_composite(fo, (x, y))
        d.ellipse((W * .28 - 22, y + 18, W * .28 + 22, y + 62), fill=ROSSO + (255,))
    # scheda con le righe scritte a mano
    a2 = ease((t - .5) / .35)
    if a2 > 0:
        cw, chh = 1000, 160 + 110 * max(1, len(ds.get('righe') or []))
        c = Image.new('RGBA', (cw, chh), (252, 249, 236, 255)); dc = ImageDraw.Draw(c)
        for i, r in enumerate(ds.get('righe') or []):
            n = int(len(r) * max(0, min(1, (t - .9 - i * .5) / .5)))
            dc.line((50, 150 + i * 110, cw - 50, 150 + i * 110), fill=(180, 200, 230), width=3)
            testo_box(dc, (60, 140 + i * 110), r[:n], font(F_MANO, 62), (25, 35, 80), anchor='ls')
        testo_box(dc, (60, 70), chi_nome(ds.get('chi'))[1][:34] or 'DOSSIER', font(F_TESTI, 44), ROSSO, anchor='lm')
        c = c.rotate(2.5, expand=True, resample=Image.BICUBIC)
        c.putalpha(c.getchannel('A').point(lambda v: int(v * a2)))
        cx, cy = int(W * .67 - c.width / 2 + (1 - a2) * 80), int(H * .42 - c.height / 2)
        im.alpha_composite(c, (cx, cy)); d.ellipse((W * .67 - 20, cy + 16, W * .67 + 20, cy + 56), fill=(40, 90, 200, 255))
        a3 = ease((t - 1.3) / .6)   # filo rosso tra foto e scheda
        if a3 > 0 and png:
            x0, y0, x1, y1 = W * .28, H * .5 - 380, W * .67, cy + 36
            d.line((x0, y0, x0 + (x1 - x0) * a3, y0 + (y1 - y0) * a3), fill=(200, 30, 30, 255), width=8)
    if ds.get('timbro') and t > 2.0:
        disegna_timbro(im, t - 2.0, W * .67, H * .78, ds['timbro'][:16].upper(), W * .3)


# ---------------- scritte animate
def a_capo(testo, f, larg):
    righe, cur = [], ''
    for p in testo.split():
        prova = (cur + ' ' + p).strip()
        if cur and f.getbbox(prova)[2] > larg:
            righe.append(cur); cur = p
        else:
            cur = prova
    return righe + ([cur] if cur else [])


def disegna_frase(im, t, q):
    """Frase a effetto scritta a mano SOPRA la scena scurita (mai scritte su fondo vuoto), una parola alla volta."""
    testo = q['frase']; parole = testo.split(); dur = q['_dur']
    f = font(F_MANO, 150); righe = a_capo(testo, f, W * .78)
    while len(righe) > 3 and f.size > 90:
        f = font(F_MANO, f.size - 10); righe = a_capo(testo, f, W * .78)
    n = int(len(parole) * min(1, t / max(.6, dur * .55))) + 1
    d = ImageDraw.Draw(im); y = H / 2 - (len(righe) - 1) * f.size * .62; k = 0
    for r in righe:
        ws = r.split(); vis = ' '.join(ws[:max(0, n - k)]); k += len(ws)
        x = (W - f.getbbox(r)[2]) / 2
        if vis:
            testo_box(d, (x, y), vis, f, BIANCO, stroke=6, sfill=(10, 10, 14), anchor='lm')
        y += f.size * 1.24


def disegna_citazione(im, t, q):
    """Dichiarazione vera (riportata dalle fonti) a schermo mentre la legge la seconda voce."""
    c = q['citazione']; dx = q.get('_lato', 'dx') == 'dx'
    larg = int(W * .44); f = font(F_TESTI, 60); righe = a_capo(c['testo'], f, larg - 140)
    while len(righe) > 7 and f.size > 40:
        f = font(F_TESTI, f.size - 4); righe = a_capo(c['testo'], f, larg - 140)
    h = 150 + len(righe) * int(f.size * 1.32) + 60
    a = ease(t / .3)
    b = Image.new('RGBA', (larg, h), (250, 248, 242, 245)); db = ImageDraw.Draw(b)
    db.rectangle((0, 0, 16, h), fill=ROSSO + (255,))
    testo_box(db, (50, 10), '“', font(F_TITOLI, 190), ROSSO, anchor='la')
    parole = [w for w in GRUPPI_TUTTE if w['seg'] == q['_seg']]
    tg = q['_t0'] + t
    detto = sum(1 for w in parole if w['a'] <= tg) if parole else int(len(c['testo'].split()) * min(1, t / max(1, q['_dur'] * .8)))
    k = 0; y = 160
    for r in righe:
        ws = r.split(); vis = ' '.join(ws[:max(0, detto - k)]); k += len(ws)
        testo_box(db, (70, y), r, f, (200, 200, 205))
        if vis:
            testo_box(db, (70, y), vis, f, NERO)
        y += int(f.size * 1.32)
    b.putalpha(b.getchannel('A').point(lambda v: int(v * a)))
    x = int(W * .06) if dx else int(W * .5)
    im.alpha_composite(b, (x + int((1 - a) * (-80 if dx else 80)), int(H * .14)))
    nome, ruolo = chi_nome(c.get('chi'))
    disegna_nome(im, t - .25, nome, ruolo, x, int(H * .14) + h + 26)


def disegna_nome(im, t, nome, ruolo, x, y):
    """Etichetta con nome e ruolo (come in TV), alla prima apparizione di una persona."""
    a = ease(t / .3)
    if a <= 0 or not nome:
        return
    f1, f2 = font(F_TITOLI, 76), font(F_TESTI, 38)
    w = max(f1.getbbox(nome)[2], f2.getbbox(ruolo)[2] if ruolo else 0) + 80; h = 120 + (52 if ruolo else 0)
    b = Image.new('RGBA', (w, h), (12, 14, 20, 232)); db = ImageDraw.Draw(b)
    db.rectangle((0, 0, 14, h), fill=ROSSO + (255,))
    testo_box(db, (40, 60), nome, f1, BIANCO, anchor='lm')
    if ruolo:
        testo_box(db, (40, 138), ruolo, f2, GIALLO, anchor='lm')
    vis = int(w * a); b = b.crop((0, 0, max(1, vis), h))
    im.alpha_composite(b, (int(min(max(40, x), W - w - 40)), int(y)))


def disegna_luogo(im, t, testo):
    n = int(len(testo) * min(1, max(0, t - .2) / .7))
    if n <= 0:
        return
    f = font(F_MANO, 60); w = f.getbbox(testo)[2] + 60
    d = ImageDraw.Draw(im)
    d.rectangle((70, 168, 70 + w, 250), fill=(12, 14, 20, 215))
    testo_box(d, (100, 209), testo[:n], f, GIALLO, anchor='lm')


def disegna_capitolo(im, t, n, titolo):
    if t > 2.8:
        return
    a = ease(t / .25) * (1 - ease((t - 2.4) / .4))
    scuro = Image.new('RGBA', (W, H), (0, 0, 0, int(165 * a))); im.alpha_composite(scuro)
    d = ImageDraw.Draw(im)
    lab = (f'CAPITOLO {n}' if N.get('lingua') == 'it' else f'CHAPTER {n}')
    testo_box(d, (W / 2, H * .38), lab, font(F_TESTI, 56), GIALLO + (int(255 * a),), anchor='mm')
    f = font(F_MANO, 170)
    while f.getbbox(titolo)[2] > W * .86 and f.size > 90:
        f = font(F_MANO, f.size - 8)
    k = int(len(titolo) * min(1, max(0, t - .2) / .9))
    x = (W - f.getbbox(titolo)[2]) / 2
    testo_box(d, (x, H * .52), titolo[:k], f, (255, 255, 255, int(255 * a)), stroke=6, sfill=(10, 10, 14), anchor='lm')


def disegna_titolo_video(im, t):
    if t > 3.4:
        return
    a = back(t / .4) * (1 - ease((t - 3.0) / .4))
    if a <= 0:
        return
    im.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(120 * min(1, a)))))
    f = font(F_TITOLI, 200); righe = a_capo(N['titolo'].upper(), f, W * .84)
    while len(righe) > 3 and f.size > 110:
        f = font(F_TITOLI, f.size - 10); righe = a_capo(N['titolo'].upper(), f, W * .84)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    y = H / 2 - (len(righe) - 1) * f.size * .58
    for i, r in enumerate(righe):
        bb = f.getbbox(r, anchor='mm')
        if i == len(righe) - 1:
            d.rectangle((W / 2 + bb[0] - 34, y + bb[1] - 20, W / 2 + bb[2] + 34, y + bb[3] + 20), fill=ROSSO + (255,))
        testo_box(d, (W / 2, y), r, f, BIANCO, stroke=12 if i < len(righe) - 1 else 0, sfill=NERO, anchor='mm')
        y += f.size * 1.16
    s = .85 + .15 * min(1, a)
    lay = lay.resize((int(W * s), int(H * s)), Image.BILINEAR)
    im.alpha_composite(lay, (int((W - lay.width) / 2), int((H - lay.height) / 2)))


# ---------------- effetti di scena
def disegna_effetto(im, t, eff, seme):
    if eff in ('pioggia', 'neve'):
        rnd = random.Random(seme); d = ImageDraw.Draw(im)
        for _ in range(240 if eff == 'pioggia' else 160):
            x0, y0, v, l = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1400, 2200), rnd.uniform(40, 90)
            if eff == 'pioggia':
                y = (y0 + v * t) % (H + 100) - 50; x = (x0 - v * .18 * t) % W
                d.line((x, y, x - l * .18, y + l), fill=(220, 230, 255, 110), width=3)
            else:
                y = (y0 + v * .12 * t) % (H + 40) - 20; x = (x0 + 30 * math.sin(t * 1.3 + x0)) % W; r = rnd.uniform(4, 9)
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 200))
    elif eff == 'mirino':
        d = ImageDraw.Draw(im); m, l, w = 120, 150, 8
        for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
            d.line((x, y, x + sx * l, y), fill=(255, 255, 255, 230), width=w); d.line((x, y, x, y + sy * l), fill=(255, 255, 255, 230), width=w)
        if int(t * 2) % 2 == 0:
            d.ellipse((m + 40, m + 40, m + 84, m + 84), fill=ROSSO + (255,))
        testo_box(d, (m + 104, m + 62), 'REC', font(F_TESTI, 46), BIANCO, anchor='lm')
        d.line((W / 2 - 50, H / 2, W / 2 + 50, H / 2), fill=(255, 255, 255, 170), width=4); d.line((W / 2, H / 2 - 50, W / 2, H / 2 + 50), fill=(255, 255, 255, 170), width=4)


def spinta(im, t, dur, fuoco, forza=.055):
    """Leggera spinta della camera verso il soggetto: l'immagine non e' mai ferma."""
    z = 1 + forza * ease(t / max(.5, dur)) * .5 + forza * .5 * (t / max(.5, dur))
    cw, ch = W / z, H / z
    x0 = min(max(0, fuoco[0] * W - cw / 2), W - cw); y0 = min(max(0, fuoco[1] * H - ch / 2), H - ch)
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def frusta(im, t):
    """Stacco veloce tra una scena e l'altra (effetto mosso, 5 fotogrammi)."""
    k = 1 - t / .17
    if k <= 0:
        return im
    sm = im.resize((max(8, int(W / (6 + 60 * k))), H), Image.BILINEAR).resize((W, H), Image.BILINEAR)
    return Image.blend(im, sm, min(1, k * 1.1))


# ---------------- sottotitoli (solo la voce narrante; le citazioni hanno il loro riquadro)
GRUPPI_TUTTE = []


# ---------------- costruzione delle inquadrature
def costruisci(segs, dur):
    stato, gia_visti, luoghi_visti, ultimo_set = {}, set(), set(), [None]
    inizio_scena = {}
    for s in segs:
        inizio_scena.setdefault(s['scena'], s['a'])
    nscene = len(N['scene']); cap_n = 0; out = []
    for si, sc in enumerate(N['scene']):
        a = 0.0 if si == 0 else inizio_scena[si] - .05
        b = (inizio_scena[si + 1] - .05) if si + 1 < nscene else dur
        cit = next((s for s in segs if s['scena'] == si and s['tipo'] == 'citazione'), None)
        qa = (cit['a'] - .05) if cit else b
        v = sc.get('visivo') or {}; tipo = v.get('tipo', 'set')
        if tipo == 'frase' and len((v.get('testo') or sc['testo']).split()) > 14:   # una frase a effetto e' breve: se no, scena normale
            v = {'tipo': 'set', 'set': ultimo_set[0]}; tipo = 'set'
        if tipo == 'set' and v.get('set') not in SF:
            v = dict(v, set=ultimo_set[0] or next(iter(SF), None))
        span = max(.4, qa - a); shots = []
        if tipo == 'mappa':
            shots.append({'tipo': 'mappa', 'mappa': v})
            for j in range(1, max(1, int(round(span / 4.2)))):   # la mappa cambia inquadratura ogni ~4 s (piu' vicina, poi di nuovo larga)
                fz = [.6, .8, .5, .9][(j - 1) % 4]
                m2 = dict(v, larghezza=max(6, float(v.get('larghezza') or 30) * fz), centro=v.get('zoom_su') or v.get('centro')) if j % 2 else dict(v)
                shots.append({'tipo': 'mappa', 'mappa': m2, '_avanti': 9})
        elif tipo == 'dossier':
            shots.append({'tipo': 'dossier', 'dossier': v})
            if span > 6.5 and ultimo_set[0]:   # poi la persona da vicino nella scena di prima
                cst = [c for c in cast_set(ultimo_set[0]) if c['chi'] == v.get('chi')]
                shots.append({'tipo': 'set', 'set': ultimo_set[0], 'framing': 'pp:' + v['chi']} if cst else {'tipo': 'dossier', 'dossier': v, '_avanti': 9})
        elif tipo == 'frase':
            shots.append({'tipo': 'frase', 'frase': v.get('testo') or sc['testo'], 'set': ultimo_set[0]})
        else:
            k = v.get('set'); resta = MAX_RIPRESE - stato.get(k, 0)
            n = max(1, min(int(round(span / PASSO)), resta)) if resta > 0 else 1   # mai piu' di 3 angoli della stessa scena
            for fr in inquadrature_set(k, n, stato):
                shots.append({'tipo': 'set', 'set': k, 'framing': fr})
            ultimo_set[0] = k
        p = span / len(shots)
        for j, q in enumerate(shots):
            q.update(_t0=a + j * p, _dur=p, scena=si)
            out.append(q)
        first = out[-len(shots)]
        if sc.get('capitolo'):
            cap_n += 1; first['capitolo'] = (cap_n, sc['capitolo'].upper())
        if sc.get('titolo_card'):
            first['titolo_card'] = True
        g = sc.get('grafica')
        if g and g.get('tipo') in ('numero', 'titolo'):
            sh = out[-len(shots):]
            libero = lambda q: not (q.get('capitolo') or q.get('titolo_card'))
            cand = ([q for q in sh if q['tipo'] == 'set' and not q['framing'].startswith('pp:') and libero(q)] +
                    [q for q in sh if q['tipo'] == 'set' and libero(q)] + [q for q in sh if q['tipo'] == 'mappa' and libero(q)] +
                    [q for q in sh if q['tipo'] in ('set', 'mappa')])
            if cand:
                cand[0]['grafica'] = g
                if not libero(cand[0]):
                    cand[0]['_g0'] = 2.8   # la grafica entra dopo il titolo del capitolo, mai sopra
        for q in out[-len(shots):]:   # nome alla prima apparizione, luogo alla prima volta della scena
            if q['tipo'] == 'set':
                st = (N.get('sets') or {}).get(q['set']) or {}
                if st.get('luogo') and q['set'] not in luoghi_visti:
                    q['luogo'] = st['luogo'].upper(); luoghi_visti.add(q['set'])
                vis = [c['chi'] for c in cast_set(q['set'])] if q['framing'] in ('largo', 'medio') else ([q['framing'][3:]] if q['framing'].startswith('pp:') else [])
                nuovi = [c for c in vis if c not in gia_visti]
                if nuovi:
                    q['nomi'] = nuovi; gia_visti.update(nuovi)
        if cit:
            c = sc.get('citazione') or {}
            chi = c.get('chi'); pose = [pz for (cc, pz) in PNG if cc == chi and PNG[(cc, pz)]]
            out.append({'tipo': 'citazione', 'citazione': dict(c, testo=cit['testo']), 'set': ultimo_set[0], '_png': PNG.get((chi, pose[0])) if pose else None,
                        '_t0': qa, '_dur': max(.4, b - qa), 'scena': si, '_seg': segs.index(cit), '_lato': 'dx'})
            gia_visti.add(chi)
    for i, q in enumerate(out):   # stacco "a frusta" quando cambia la scena disegnata
        prima = out[i - 1] if i else None
        q['_frusta'] = bool(prima) and (prima['tipo'] != q['tipo'] or prima.get('set') != q.get('set')) and q['tipo'] != 'citazione'
    return out


def prepara_base(q):
    """Immagine ferma dell'inquadratura + punto di spinta + quanto spingere."""
    if q['tipo'] == 'set':
        im, fu = base_set(q); return im, fu, .06
    if q['tipo'] == 'mappa':
        im, evid = base_mappa(q['mappa']); q['_strati'] = strati_paesi(q['mappa'], evid); return im, (.5, .5), .05
    if q['tipo'] == 'dossier':
        return base_dossier(q), (.5, .5), .05
    bg = img(SF[q['set']]) if q.get('set') in SF else Image.new('RGBA', (W, H), (30, 34, 46, 255))
    im = bg.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(16))
    im.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 120 if q['tipo'] == 'citazione' else 150)))
    if q['tipo'] == 'citazione' and q.get('_png'):
        p = persona_alta(q['_png'], H * 1.6); cx = W * .76
        im.alpha_composite(p, (int(cx - p.width / 2), int(H * .1)))
    return im, (.5, .5), .03


def rendi_inquadratura(i):
    q = INQ[i]; out = os.path.join(LAV, f'inq_{i:03d}.mp4')
    n = max(1, int(round(q['_dur'] * FPS)))
    pr = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(FPS), out], stdin=subprocess.PIPE)
    grad = Image.linear_gradient('L').resize((W, H)).point(lambda v: int(max(0, v - 150) * 1.6))   # scurisce il fondo sotto i sottotitoli
    ombra_basso = Image.new('RGBA', (W, H), (0, 0, 0, 255)); ombra_basso.putalpha(grad)
    base, fuoco, forza = prepara_base(q)
    eff = ((N.get('sets') or {}).get(q.get('set')) or {}).get('effetto') if q['tipo'] == 'set' else None
    if q['tipo'] == 'set' and q['framing'].startswith('det'):
        eff = eff if eff in ('pioggia', 'neve') else None
    cast = {c['chi']: c for c in cast_set(q['set'])} if q['tipo'] == 'set' else {}
    avanti = q.get('_avanti', 0)
    for f in range(n):
        tl = f / FPS; tg = q['_t0'] + tl
        im = spinta(base, tl, q['_dur'], fuoco, forza)
        if q['tipo'] == 'mappa':
            disegna_mappa(im, tl + avanti, q)
        elif q['tipo'] == 'dossier':
            disegna_dossier(im, tl + avanti, q)
        if eff:
            disegna_effetto(im, tg, eff, hash(q.get('set')) & 0xffff)
        im.alpha_composite(ombra_basso)
        g = q.get('grafica') or {}
        if g:
            lati = [c.get('lato', 'dx') for k, c in cast.items() if not q.get('framing', '').startswith('pp:') or q['framing'][3:] == k]
            z = (120, 260, int(W * .52)) if lati == ['dx'] else ((int(W * .48), 260, W - 120) if lati == ['sx'] else (120, 260, int(W * .62)))
            if len(lati) >= 2:
                z = (int(W * .3), 230, int(W * .7))
            g0 = q.get('_g0', 0)
            if g.get('tipo') == 'numero':
                disegna_numero(im, tl - .15 - g0, g, z)
            elif g.get('tipo') == 'titolo' and tl > g0:
                disegna_titolo(im, tl - .1 - g0, g, z)
        for j, chi in enumerate(q.get('nomi') or []):
            nome, ruolo = chi_nome(chi); c = cast.get(chi, {})
            if q['framing'].startswith('pp:'):
                x = W * (.6 if c.get('lato', 'dx') == 'dx' else .4) - 300
            else:
                x = W * (.73 if c.get('lato', 'dx') == 'dx' else .27) - 300
            disegna_nome(im, tl - .3 - j * .3, nome, ruolo, x, H * .56)
        if q.get('luogo'):
            disegna_luogo(im, tl, q['luogo'])
        if q['tipo'] == 'frase':
            disegna_frase(im, tl, q)
        if q['tipo'] == 'citazione':
            disegna_citazione(im, tl, q)
        if q.get('capitolo'):
            disegna_capitolo(im, tl, *q['capitolo'])
        if q.get('titolo_card'):
            disegna_titolo_video(im, tl)
        disegna_fisse(im, tg, None)
        coperto = q['tipo'] in ('frase', 'citazione') or (q.get('titolo_card') and tl < 3.4) or (q.get('capitolo') and tl < 2.6)
        if not coperto:
            disegna_sottotitoli(im, tg, GRUPPI)
        if q.get('_frusta') and tl < .17:
            im = frusta(im, tl)
        pr.stdin.write(im.convert('RGB').tobytes())
    pr.stdin.close(); pr.wait()
    return out


def musica(voce_mp3, dur):
    gen = N.get('musica') or 'tensione'
    cand = sorted(x for x in os.listdir(os.path.join(ROOT, 'libreria_musica')) if x.startswith(gen) and x.endswith('.mp3'))
    m = os.path.join(ROOT, 'libreria_musica', random.Random(NOME).choice(cand))
    out = os.path.join(LAV, 'audio.m4a')
    fl = ('[0:a]apad=pad_dur=1.2,asplit=2[vo][vk];[1:a]loudnorm=I=-24:TP=-3,volume=0.16,afade=t=in:d=1,'
          f'afade=t=out:st={dur - 1.5:.2f}:d=1.5[m0];[m0][vk]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[m];'
          '[vo]loudnorm=I=-15:TP=-1.5[v2];[v2][m]amix=inputs=2:duration=first:normalize=0[a]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', voce_mp3, '-stream_loop', '-1', '-i', m, '-filter_complex', fl, '-map', '[a]',
                    '-t', f'{dur:.3f}', '-c:a', 'aac', '-b:a', '192k', out], check=True)
    log('musica:', os.path.basename(m))
    return out


def copertina():
    c = N.get('copertina') or {}
    im = Image.open(sfondo(c['sfondo'])).convert('RGBA').resize((W, H), Image.LANCZOS)
    lato = c.get('lato', 'dx')
    if c.get('personaggio'):
        png = posa(c['personaggio'], c['posa'])
        if png:
            p = Image.open(png).convert('RGBA'); hh = int(H * 1.0)
            p = p.resize((int(p.width * hh / p.height), hh), Image.LANCZOS)
            x = int(W * (.72 if lato == 'dx' else .28) - p.width / 2); im.alpha_composite(p, (x, H - p.height + 60))
    # testo grande dal lato libero (mai sopra il personaggio, mai in basso a destra sulla durata)
    righe = c['righe']; ev = c.get('evidenzia', -1)
    x0 = 110 if lato == 'dx' else int(W * .5); larg = int(W * .48)
    y = 170
    d = ImageDraw.Draw(im)
    for i, r in enumerate(righe):
        s = 420
        while font(F_TITOLI, s).getbbox(r)[2] > larg - 60 and s > 120:
            s -= 10
        f = font(F_TITOLI, s); bb = f.getbbox(r)
        if i == ev:
            d.rectangle((x0 - 30, y + bb[1] - 30, x0 + bb[2] + 30, y + bb[3] + 30), fill=ROSSO + (255,))
            testo_box(d, (x0, y), r, f, BIANCO, stroke=0)
        else:
            testo_box(d, (x0, y), r, f, BIANCO, stroke=16, sfill=NERO)
        y += bb[3] + 70
    p = os.path.join(OUT, 'copertina.jpg'); im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(p, quality=93)
    im.convert('RGB').save(os.path.join(OUT, 'copertina_grande.jpg'), quality=92)
    log('copertina pronta'); return p


def libreria_aggiorna(ordine):
    """Ogni scena disegnata entra nella libreria dei luoghi (si potra' riusare gratis dopo almeno 7 giorni); quelle riusate segnano la data."""
    if N.get('materiali_da'):
        return
    os.makedirs(LIB, exist_ok=True)
    ind = json.load(open(LIB_INDICE)) if os.path.exists(LIB_INDICE) else {}
    oggi = time.strftime('%Y-%m-%d')
    for k in ordine:
        st = (N.get('sets') or {}).get(k) or {}; src = SF.get(k)
        if not src:
            continue
        lid = st.get('lib') or re.sub(r'[^a-z0-9]+', '_', (oggi + '_' + NOME[11:40] + '_' + k).lower()).strip('_')
        if not os.path.exists(os.path.join(LIB, lid + '.jpg')):
            Image.open(src).convert('RGB').save(os.path.join(LIB, lid + '.jpg'), quality=90)
        e = ind.setdefault(lid, {'descr': descr_sfondo(k)[:300], 'luogo': st.get('luogo', ''), 'filone': N.get('filone', ''), 'usato': []})
        if oggi not in e['usato']:
            e['usato'].append(oggi)
    json.dump(ind, open(LIB_INDICE, 'w'), ensure_ascii=False, indent=0)
    log(f'libreria luoghi: {len(ind)} scene')


def da_vecchio_formato():
    """I copioni di prima (inquadrature con clip Pexels) diventano scene disegnate: le clip non si usano piu'."""
    sets = N.setdefault('sets', {})
    for i, s in enumerate(N['scene']):
        if s.get('visivo') or not s.get('inquadrature'):
            continue
        car = next((q for q in s['inquadrature'] if q.get('tipo') == 'cartone'), None)
        k = f'scena_{i:03d}'
        sets[k] = {'descr': descr_sfondo(car['sfondo']) if car else f"Editorial illustration of this news moment: {s['testo'][:300]}. Empty of people, no text.",
                   'cast': [{'chi': car['personaggio'], 'posa': car['posa'], 'lato': car.get('lato', 'dx')}] if car and car.get('personaggio') else []}
        s['visivo'] = {'tipo': 'set', 'set': k}
        g = next((q.get('grafica') for q in s['inquadrature'] if q.get('grafica')), None)
        if g:
            s['grafica'] = g


def main():
    global INQ, GRUPPI, SEGS, GRUPPI_TUTTE
    t_start = time.time()
    da_vecchio_formato()
    sets = N.setdefault('sets', {})
    usati = [s['visivo']['set'] for s in N['scene'] if (s.get('visivo') or {}).get('tipo', 'set') == 'set' and (s.get('visivo') or {}).get('set')]
    ordine = list(dict.fromkeys(usati))
    pose = sorted({(c['chi'], c['posa']) for k in ordine for c in (sets.get(k) or {}).get('cast') or []}
                  | {(s['visivo']['chi'], s['visivo'].get('posa')) for s in N['scene'] if (s.get('visivo') or {}).get('tipo') == 'dossier' and s['visivo'].get('posa')}
                  | {(s['citazione']['chi'], s['citazione']['posa']) for s in N['scene'] if (s.get('citazione') or {}).get('posa')})
    cop = N.get('copertina') or {}
    if not cop.get('personaggio'):   # in copertina sempre la persona piu' importante della notizia
        conta = {}
        for k in usati:
            for c in (sets.get(k) or {}).get('cast') or []:
                conta[(c['chi'], c['posa'])] = conta.get((c['chi'], c['posa']), 0) + 1
        if conta:
            cop['personaggio'], cop['posa'] = max(conta, key=conta.get)
    if cop.get('personaggio'):
        pose = sorted(set(pose) | {(cop['personaggio'], cop['posa'])})
    pose = [p for p in pose if p[1] and p[0] in (N.get('personaggi') or {})]
    # tetto di spesa: se le scene disegnate non ci stanno, le ultime riusano la scena precedente (il video si fa sempre)
    nuove_pose = sum(1 for c, p in pose if not os.path.exists(os.path.join(CAR, c, p + '.png')))
    posti = int((TETTO - CO.totale() - nuove_pose * .1 - .12) / .05)
    gratis = [k for k in ordine if os.path.exists(os.path.join(LIB, str((sets.get(k) or {}).get('lib')) + '.jpg'))]   # luoghi dalla libreria: non costano
    if not N.get('materiali_da') and len(ordine) - len(gratis) > posti:
        nuovi = [k for k in ordine if k not in gratis]
        tieni = set(gratis) | set(nuovi[:max(4, posti)]); prec = None
        for s in N['scene']:
            v = s.get('visivo') or {}
            if v.get('tipo', 'set') == 'set':
                if v.get('set') in tieni:
                    prec = v['set']
                elif prec:
                    v['set'] = prec
        log(f'budget: {len(ordine)} scene disegnate richieste, {len(tieni)} possibili -> le altre riusano la scena prima')
        ordine = [k for k in ordine if k in tieni]
    if cop.get('sfondo'):
        sets['copertina'] = {'descr': descr_sfondo(cop['sfondo']) + ' Dramatic thumbnail background, completely empty of people.'}
        cop['sfondo'] = 'copertina'
    voce_mp3, parole, segs, dur_voce = voce()
    SEGS = segs; GRUPPI_TUTTE = parole
    GRUPPI = gruppi_sottotitoli([w for w in parole if segs[w['seg']]['tipo'] == 'testo'])
    dur = dur_voce + 1.2
    log(f'voce: {dur_voce:.1f} s, {len(parole)} parole, {sum(1 for s in segs if s["tipo"] == "citazione")} citazioni')
    log(f"{len(ordine)} scene disegnate, {len(pose)} pose, {sum(1 for s in N['scene'] if (s.get('visivo') or {}).get('tipo') == 'mappa')} mappe")
    with ThreadPoolExecutor(4) as ex:
        rp = {k: ex.submit(posa, *k) for k in pose}
        rs = {k: ex.submit(sfondo, k) for k in ordine}
        PNG.update({k: v.result() for k, v in rp.items()}); SF.update({k: v.result() for k, v in rs.items() if v.result()})
    for s in N['scene']:
        v = s.get('visivo') or {}
        if v.get('tipo') == 'dossier' and not v.get('posa'):
            v['posa'] = next((p for (c, p) in PNG if c == v.get('chi') and PNG[(c, p)]), None)
    log(f'materiali pronti, spesa finora {CO.totale():.3f} $')
    try:
        libreria_aggiorna(ordine)
    except Exception as e:
        log('libreria luoghi non aggiornata:', str(e)[:150])
    INQ = costruisci(segs, dur)
    for q in INQ:
        if q['tipo'] == 'dossier':
            q['_png'] = PNG.get((q['dossier'].get('chi'), q['dossier'].get('posa')))
    dd = [q['_dur'] for q in INQ]
    log(f'{len(INQ)} inquadrature, durata media {sum(dd) / len(dd):.1f} s, la piu lunga {max(dd):.1f} s')
    with ProcessPoolExecutor(4) as ex:
        parti = list(ex.map(rendi_inquadratura, range(len(INQ))))
    lista = os.path.join(LAV, 'lista.txt'); open(lista, 'w').write(''.join(f"file '{p}'\n" for p in parti))
    muto = os.path.join(LAV, 'muto.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto], check=True)
    audio = musica(voce_mp3, dur)
    unito = os.path.join(LAV, 'unito.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', muto, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'copy', '-shortest', unito], check=True)
    finale = os.path.join(OUT, 'video.mp4')
    cfg = {'language': N.get('lingua', 'it'), 'subscribe_overlay_second': round(dur * .55, 1)}
    if not IS.applica(unito, finale, cfg, os.path.join(LAV, 'iscriviti'), enc=['-c:v', 'libx264', '-preset', 'medium', '-crf', '19']):
        shutil.copy(unito, finale)
    # capitoli per la descrizione di YouTube (il primo sempre a 0:00)
    cap = [{'t': 0, 'titolo': 'Intro' if N.get('lingua') != 'it' else 'Introduzione'}]
    for q in INQ:
        if q.get('capitolo'):
            tt = int(q['_t0'])
            if tt - cap[-1]['t'] >= 12:
                cap.append({'t': tt, 'titolo': q['capitolo'][1].title()})
            elif len(cap) == 1:
                cap[0]['titolo'] = q['capitolo'][1].title()
    json.dump(cap, open(os.path.join(OUT, 'capitoli.json'), 'w'), ensure_ascii=False, indent=1)
    if os.path.getsize(finale) > 90e6:   # troppo grande per il repository: il 1440p va negli artefatti, qui l'anteprima 720p
        pieno = os.path.join(ROOT, 'video_pieni', NOME + '.mp4'); os.makedirs(os.path.dirname(pieno), exist_ok=True)
        shutil.move(finale, pieno)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', pieno, '-vf', 'scale=1280:720:flags=lanczos', '-c:v', 'libx264', '-preset', 'medium', '-crf', '26',
                        '-maxrate', '850k', '-bufsize', '1700k', '-c:a', 'aac', '-b:a', '96k', os.path.join(OUT, 'anteprima_720p.mp4')], check=True)
        finale = pieno
        log(f"video 1440p: {os.path.getsize(pieno) / 1e6:.0f} MB (artefatto), anteprima 720p: {os.path.getsize(os.path.join(OUT, 'anteprima_720p.mp4')) / 1e6:.0f} MB")
    else:
        log(f'video: {os.path.getsize(finale) / 1e6:.1f} MB')
    try:
        copertina()
    except Exception as e:
        log('copertina non riuscita:', str(e)[:200])
    rp = CO.riepilogo()
    testo = (f"{N['titolo']}\ndurata {dur:.1f} s, {len(INQ)} inquadrature (media {sum(dd) / len(dd):.1f} s), render {(time.time() - t_start) / 60:.1f} min\n"
             f"spesa {rp['totale_dollari']:.3f} $ + {rp['crediti_voce']} crediti voce\n" + json.dumps(rp['dettaglio'], indent=1) + '\n\nFONTI:\n' + '\n'.join(N.get('fonti_link') or []))
    open(os.path.join(OUT, 'costi.txt'), 'w').write(testo); log(testo)
    for k, t in enumerate([1.0, dur * .2, dur * .4, dur * .6, dur * .8, dur - 2]):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', finale, '-frames:v', '1', '-vf', 'scale=1280:-1', os.path.join(OUT, f'fotogramma_{k}.jpg')])


if __name__ == '__main__':
    main()
