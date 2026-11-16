#!/usr/bin/env python3
"""VIDEO NOTIZIE (16 nov 2026, Giorgio: "cavalchiamo le notizie tech con le caricature dei personaggi veri").
Dal file notizie/<nome>.json (copione scritto SOLO con fatti delle fonti, scena per scena) al video finito 2560x1440:
  1) voce ElevenLabs con i tempi di ogni lettera (sottotitoli parola per parola)
  2) caricature dei personaggi: foto vera da Wikimedia Commons -> caricatura (Nano Banana 2) -> scontorno (birefnet)
     salvate in caricature/<persona>/<posa>.png e riusate nei video dopo (si paga una volta sola)
  3) sfondi a cartone (Seedream 4.5, ~0,04 $) controllati da Claude Haiku (niente difetti, niente scritte) + clip vere Pexels (gratis)
  4) grafica animata in codice: timbro, contatori, titoli, carta della banca, ULTIM'ORA, fonte sempre a schermo
  5) musica di sottofondo bassa che si abbassa sotto la voce + pulsante iscriviti + copertina
Env: NOTIZIA (percorso del json), FAL_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY, PEXELS_API_KEY, TETTO_DOLLARI (default 0.70)
Uscita: prove_video/notizie/<nome>/video.mp4, copertina.jpg, costi.txt"""
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


def _allinea(mp3, testo):
    """Tempi di ogni lettera di un audio gia' fatto (ElevenLabs forced alignment), se il modello non li da' da solo."""
    bnd = 'notizie' + str(random.randint(10 ** 8, 10 ** 9))
    corpo = (f'--{bnd}\r\nContent-Disposition: form-data; name="text"\r\n\r\n{testo}\r\n'
             f'--{bnd}\r\nContent-Disposition: form-data; name="file"; filename="v.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode() + open(mp3, 'rb').read() + f'\r\n--{bnd}--\r\n'.encode()
    j = http('https://api.elevenlabs.io/v1/forced-alignment', corpo, {'xi-api-key': E('ELEVENLABS_API_KEY', ''), 'Content-Type': f'multipart/form-data; boundary={bnd}'}, timeout=300)
    ch = j['characters']
    return {'characters': [c['text'] for c in ch], 'character_start_times_seconds': [c['start'] for c in ch], 'character_end_times_seconds': [c['end'] for c in ch]}


def voce_a_blocchi(testo, p, pj):
    """Voce a blocchi di scene (max ~2.400 caratteri, i video lunghi superano il limite di una chiamata), poi tutto unito con i tempi giusti."""
    blocchi, cur = [], ''
    for s in N['scene']:
        t = s['testo'].strip()
        if cur and len(cur) + len(t) + 1 > 2400:
            blocchi.append(cur); cur = t
        else:
            cur = (cur + ' ' + t).strip()
    blocchi.append(cur)
    imp = ({'stability': .5, 'similarity_boost': .8, 'style': 0, 'use_speaker_boost': True} if 'v3' in MODELLO_VOCE else
           {'stability': .42, 'similarity_boost': .78, 'style': .28, 'speed': float(N.get('voce_velocita') or 1.08), 'use_speaker_boost': True})
    parti, al = [], {'characters': [], 'character_start_times_seconds': [], 'character_end_times_seconds': []}
    off = 0.0
    for i, b in enumerate(blocchi):
        f = os.path.join(LAV, f'voce_{i:02d}.mp3'); a = None
        for k in range(4):
            try:
                try:
                    j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_192',
                             {'text': b, 'model_id': MODELLO_VOCE, 'voice_settings': imp}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300)
                    open(f, 'wb').write(base64.b64decode(j['audio_base64'])); a = j.get('alignment')
                except urllib.error.HTTPError as e:
                    log('voce con i tempi non disponibile per', MODELLO_VOCE, e.code, '-> audio semplice + allineamento')
                    open(f, 'wb').write(http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_192',
                                             {'text': b, 'model_id': MODELLO_VOCE, 'voice_settings': imp}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300, raw=True))
                if not a or not a.get('characters'):
                    a = _allinea(f, b)
                CO.registra('elevenlabs', MODELLO_VOCE, crediti=len(b)); break
            except Exception as e:
                log('voce non riuscita, riprovo:', str(e)[:200]); time.sleep(5 * (k + 1))
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
        shutil.copy(parti[0], p)
    else:
        lst = os.path.join(LAV, 'voci.txt'); open(lst, 'w').write(''.join(f"file '{x}'\n" for x in parti))
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c:a', 'libmp3lame', '-b:a', '192k', p], check=True)
    json.dump(al, open(pj, 'w'))


# ============================================================ 1) VOCE
def voce():
    p = os.path.join(MAT, 'voce.mp3'); pj = p[:-4] + '.json'
    testo = ' '.join(s['testo'].strip() for s in N['scene'])
    pt = p[:-4] + '_testo.txt'
    chiave = MODELLO_VOCE + '|' + VOCE + '|' + testo   # cambia il testo, la voce o il modello: voce nuova
    if not os.path.exists(pt) or open(pt).read() != chiave:
        for x in (p, pj):
            os.path.exists(x) and os.remove(x)
    if not (os.path.exists(p) and os.path.exists(pj)):
        voce_a_blocchi(testo, p, pj); open(pt, 'w').write(chiave)
    al = json.load(open(pj))
    ch, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    # parole con i tempi
    parole, cur, t0 = [], '', None
    for c, a, b in zip(ch, st, en):
        if c.isspace():
            if cur:
                parole.append({'w': cur, 'a': t0, 'b': fine}); cur = ''
            continue
        if not cur:
            t0 = a
        cur += c; fine = b
    if cur:
        parole.append({'w': cur, 'a': t0, 'b': fine})
    # inizio di ogni scena (posizione del suo primo carattere nel testo unito)
    inizi, pos = [], 0
    for s in N['scene']:
        inizi.append(st[min(pos, len(st) - 1)]); pos += len(s['testo'].strip()) + 1
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip())
    return p, parole, inizi, dur


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


# ============================================================ 3) SFONDI E CLIP
MAT = os.path.join(OUT, 'materiali'); os.makedirs(MAT, exist_ok=True)


def sfondo(chiave):
    dest = os.path.join(MAT, f'sfondo_{chiave}.jpg')
    if os.path.exists(dest):
        return dest
    if N.get('materiali_da'):   # versione in un'altra lingua: stesse immagini del video gemello, gratis
        gem = os.path.join(ROOT, 'prove_video', 'notizie', N['materiali_da'], 'materiali', f'sfondo_{chiave}.jpg')
        if os.path.exists(gem):
            shutil.copy(gem, dest); return dest
    descr = N.get('sfondi', {}).get(chiave) or chiave.replace('_', ' ')
    vuota = bool(re.search(r'empty of people|no people|nobody', descr, re.I))
    for k in range(4):
        try:
            semplice = 'Very simple, clean composition: no screens, no papers, no signs, no clocks, nothing with writing. ' if k >= 2 else ''
            prompt = STILE + f'Scene: {descr}. Wide 16:9 shot. ' + semplice + ('Absolutely NO people, no characters, no faces. ' if vuota else '') + NO_TESTO
            r = fal('fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': prompt, 'image_size': {'width': W, 'height': H}, 'num_images': 1}, 0.04)
            im = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True, timeout=120))).convert('RGB')
            if max(ImageStat.Stat(im.resize((64, 36))).mean) < 18:
                log('sfondo nero, rifaccio'); continue
            dom = DIFETTI + (' Also answer SI if ANY person, character or face is visible (this scene must be empty of people).' if vuota else '')
            if k < 3 and haiku_immagine(im, dom).startswith('SI'):   # 16 nov: controllo su ogni tentativo; il 4o (semplificato) si tiene, cosi' non si ripete mai un'altra immagine
                log('sfondo con un difetto o scritte, lo rifaccio:', chiave); continue
            im = im.resize((W, H), Image.LANCZOS) if im.size != (W, H) else im
            im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2)).save(dest, quality=95); return dest
        except RuntimeError:
            raise
        except Exception as e:
            log('sfondo non riuscito, riprovo:', chiave, str(e)[:200]); time.sleep(4)
    return None


CLIP_USATE = {38687556}   # grafico EUR/USD: sbagliato per Borsa e Nasdaq


def clip_adatta(v, contesto):
    if not contesto or not v.get('image'):
        return True
    try:
        im = Image.open(io.BytesIO(http(v['image'], raw=True, timeout=60))).convert('RGB')
        return haiku_immagine(im, f'A news video says: "{contesto[:300]}". Would this stock footage frame look clearly coherent and relevant as b-roll '
                                  'for that sentence (same subject or setting, serious news tone)? Random unrelated people, objects or places = NO. Answer only SI or NO.').startswith('SI')
    except Exception:
        return True


def clip_pexels(cartella, domande, sec, contesto=''):
    if os.path.isdir(cartella) and len(os.listdir(cartella)) >= int(sec * FPS):
        return cartella
    for q in domande if isinstance(domande, list) else [domande]:
        try:
            r = http('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 15, 'orientation': 'landscape', 'size': 'large'}),
                     headers={'Authorization': E('PEXELS_API_KEY', '')}, timeout=60)
        except Exception as e:
            log('pexels non risponde', q, str(e)[:80]); continue
        for v in r.get('videos', []):
            if v.get('duration', 0) < sec + 1.5 or v['id'] in CLIP_USATE:
                continue
            fs = sorted([x for x in v['video_files'] if (x.get('width') or 0) >= 1920 and x.get('file_type') == 'video/mp4'], key=lambda x: -(x.get('width') or 0))
            fs = [x for x in fs if (x.get('width') or 0) <= 3840] or fs
            if not fs:
                continue
            if not clip_adatta(v, contesto):
                log('clip scartata (non c\'entra con la frase):', q, v['id']); CLIP_USATE.add(v['id']); continue
            raw = cartella + '.mp4'
            try:
                open(raw, 'wb').write(http(fs[0]['link'], raw=True, timeout=300))
                shutil.rmtree(cartella, ignore_errors=True); os.makedirs(cartella)
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '0.8', '-i', raw, '-t', f'{sec + .2:.2f}', '-vf',
                                f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS}', '-q:v', '2',
                                os.path.join(cartella, '%04d.jpg')], check=True)
                CLIP_USATE.add(v['id']); log('clip pexels:', q, v['id'], fs[0].get('width'))
                return cartella
            except Exception as e:
                log('clip non scaricata', str(e)[:80])
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


# ============================================================ 5) REGIA E RENDER
INQ, GRUPPI = [], []


def zona_grafica(inq):
    if inq.get('personaggio'):
        return (120, 230, int(W * .52)) if inq.get('lato', 'dx') == 'dx' else (int(W * .48), 230, W - 120)
    return (120, 260, int(W * .62))


def base_frame(inq, tl):
    if inq['tipo'] == 'pexels':
        fr = inq.get('_fr') or inq.setdefault('_fr', sorted(os.listdir(inq['_clip'])))
        i = min(len(fr) - 1, int(tl * FPS))
        return Image.open(os.path.join(inq['_clip'], fr[i])).convert('RGBA')
    if '_bg' not in inq:
        inq['_bg'] = Image.open(inq['_sfondo']).convert('RGBA')
    return inq['_bg'].copy()


def rendi_inquadratura(i):
    inq = INQ[i]; out = os.path.join(LAV, f'inq_{i:03d}.mp4')
    n = max(1, int(round(inq['_dur'] * FPS)))
    pr = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(FPS), out], stdin=subprocess.PIPE)
    grad = Image.linear_gradient('L').resize((W, H)).point(lambda v: int(max(0, v - 150) * 1.6))   # scurisce il fondo sotto i sottotitoli
    ombra_basso = Image.new('RGBA', (W, H), (0, 0, 0, 255)); ombra_basso.putalpha(grad)
    for f in range(n):
        tl = f / FPS; tg = inq['_t0'] + tl
        im = base_frame(inq, tl)
        im.alpha_composite(ombra_basso)
        g = inq.get('grafica') or {}
        if inq.get('personaggio') and inq.get('_png'):
            disegna_personaggio(im, tl, inq['_png'], inq.get('lato', 'dx'))
        z = zona_grafica(inq)
        if g.get('tipo') == 'carta':
            cx = W * (.33 if inq.get('lato', 'dx') == 'dx' else .67)
            disegna_carta(im, tl - .1, cx, H * .45, W * .34, g.get('timbro'))
        elif g.get('tipo') == 'numero':
            disegna_numero(im, tl - .15, g, z)
        elif g.get('tipo') == 'titolo':
            disegna_titolo(im, tl - .1, g, z)
        if inq.get('didascalia'):
            disegna_didascalia(im, tl, inq['didascalia'], 'sx' if inq.get('lato', 'dx') == 'dx' else 'dx')
        disegna_fisse(im, tg, inq.get('_fonte'))
        disegna_sottotitoli(im, tg, GRUPPI)
        pr.stdin.write(im.convert('RGB').tobytes())
    pr.stdin.close(); pr.wait()
    if inq.get('_clip') and os.path.isdir(inq['_clip']):
        shutil.rmtree(inq['_clip'], ignore_errors=True)
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
    im = Image.open(sfondo(c['sfondo'])).convert('RGBA')
    lato = c.get('lato', 'dx')
    if c.get('personaggio'):
        png = posa(c['personaggio'], c['posa'])
        if png:
            p = Image.open(png).convert('RGBA'); hh = int(H * 1.0)
            p = p.resize((int(p.width * hh / p.height), hh), Image.LANCZOS)
            x = int(W * (.72 if lato == 'dx' else .28) - p.width / 2); im.alpha_composite(p, (x, H - p.height + 60))
    if c.get('carta'):
        disegna_carta(im, 5, W * (.70 if lato == 'dx' else .30) - (0 if not c.get('personaggio') else W * .12), H * .62, W * .26, None)
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


def main():
    global INQ, GRUPPI
    t_start = time.time()
    voce_mp3, parole, inizi, dur_voce = voce()
    GRUPPI = gruppi_sottotitoli(parole)
    dur = dur_voce + 1.2
    log(f'voce: {dur_voce:.1f} s, {len(parole)} parole')
    # tempi di ogni inquadratura
    for si, s in enumerate(N['scene']):
        a = 0 if si == 0 else inizi[si] - .05
        b = (inizi[si + 1] - .05) if si + 1 < len(N['scene']) else dur
        qq = s['inquadrature']; p = (b - a) / len(qq)
        for k, q in enumerate(qq):
            q = dict(q); q['_t0'] = a + k * p; q['_dur'] = p; q['_fonte'] = s.get('fonte'); q['_testo'] = s['testo']; INQ.append(q)
    # 16 nov (Giorgio: "come un film, mai la stessa immagine"): ogni inquadratura a cartone ha il suo sfondo
    usati = {}
    for q in INQ:
        if q['tipo'] == 'cartone':
            k = q['sfondo']; usati[k] = usati.get(k, 0) + 1
            if usati[k] > 1:
                nk = f'{k}_v{usati[k]}'
                N.setdefault('sfondi', {})[nk] = (N.get('sfondi', {}).get(k) or k.replace('_', ' ')) + \
                    f' A DIFFERENT shot of this subject (version {usati[k]}): different camera angle, framing, distance and details.'
                q['sfondo'] = nk
    cop = N.get('copertina') or {}
    if cop.get('sfondo'):   # la copertina ha uno sfondo suo, senza persone (solo la caricatura del protagonista)
        N.setdefault('sfondi', {})['copertina'] = (N['sfondi'].get(cop['sfondo']) or cop['sfondo']) + ' Dramatic thumbnail background, completely empty of people.'
        cop['sfondo'] = 'copertina'
    # materiali: pose e sfondi in parallelo (pochi), clip pexels
    pose = sorted({(q['personaggio'], q['posa']) for q in INQ if q.get('personaggio')} | ({(N['copertina']['personaggio'], N['copertina']['posa'])} if N.get('copertina', {}).get('personaggio') else set()))
    sf = sorted({q['sfondo'] for q in INQ if q['tipo'] == 'cartone'} | {N['copertina']['sfondo']})
    log(f"{len(INQ)} inquadrature, {len(sf)} sfondi, {len(pose)} pose, {sum(1 for q in INQ if q['tipo'] == 'pexels')} clip vere")
    with ThreadPoolExecutor(4) as ex:
        rp = {k: ex.submit(posa, *k) for k in pose}
        rs = {k: ex.submit(sfondo, k) for k in sf}
        PNG = {k: v.result() for k, v in rp.items()}; SF = {k: v.result() for k, v in rs.items()}
    for i, q in enumerate(INQ):
        if q['tipo'] == 'pexels':
            testo_scena = q.get('_testo', '')
            q['_clip'] = clip_pexels(os.path.join(LAV, f'clip_{i:03d}'), q['q'], q['_dur'], testo_scena)
            if not q['_clip']:   # niente clip adatta: scena a cartone NUOVA fatta apposta su quella frase (mai un buco, mai un'immagine ripetuta)
                k = f'auto_{i:03d}'
                N['sfondi'][k] = f'Editorial illustration of this news moment: {testo_scena[:300]}. Empty of people, no text.'
                q['tipo'] = 'cartone'; q['sfondo'] = k; SF[k] = sfondo(k)
        if q['tipo'] == 'cartone':
            q['_sfondo'] = SF.get(q['sfondo']) or next(v for v in SF.values() if v)
        if q.get('personaggio'):
            q['_png'] = PNG.get((q['personaggio'], q['posa']))
    log(f'materiali pronti, spesa finora {CO.totale():.3f} $')
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
    testo = (f"{N['titolo']}\ndurata {dur:.1f} s, render {(time.time() - t_start) / 60:.1f} min\n"
             f"spesa {rp['totale_dollari']:.3f} $ + {rp['crediti_voce']} crediti voce\n" + json.dumps(rp['dettaglio'], indent=1) + '\n\nFONTI:\n' + '\n'.join(N.get('fonti_link') or []))
    open(os.path.join(OUT, 'costi.txt'), 'w').write(testo); log(testo)
    # anteprima: 6 fotogrammi
    for k, t in enumerate([1.0, dur * .2, dur * .4, dur * .6, dur * .8, dur - 2]):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', finale, '-frames:v', '1', '-vf', 'scale=1280:-1', os.path.join(OUT, f'fotogramma_{k}.jpg')])


if __name__ == '__main__':
    main()
