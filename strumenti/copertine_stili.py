#!/usr/bin/env python3
"""
COPERTINE STILI (per tutti i canali) — la stessa copertina in 3 stili diversi, per scegliere lo stile fisso del canale.
Parte da foto d'archivio gia' scelte (prove_archivi/<nome>/cand/...). Lo stile C usa un ritocco AI (fal seedream) con TETTO RIGIDO.
PAYLOAD = {"nome": "astronauti-stili", "max_spesa": 0.10,
           "A": {"foto": "cand/visiera_1_0.jpg", "testo": "TOO COLD?", "fuoco": [0.5, 0.4]},
           "B": {"foto": "cand/terra_1_0.jpg", "sinistra": "-150°C", "destra": "+120°C", "fuoco": [0.5, 0.5]},
           "C": {"foto": "cand/volto_1_0.jpg", "testo": "TOO COLD?", "prompt": "..."}}
Uscita: prove_archivi/<nome>/stile_A.jpg, stile_B.jpg, stile_C.jpg, confronto_stili.jpg, telefono_stili.jpg, costi_stili.txt
"""
import base64, io, json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_archivi', P['nome'])
MAX_SPESA = min(float(P.get('max_spesa') or 0.10), 0.10); SPESA = {'tot': 0.0}; PREZZO = 0.04
W, H = 1280, 720
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


FP = '/tmp/anton.ttf'
open(FP, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
F = lambda s: ImageFont.truetype(FP, s)


def riempi(im, fuoco=(0.5, 0.45), zoom=1.0):
    """Riempie 16:9 tenendo il soggetto (fuoco = punto in proporzione) e stringendo l'inquadratura di 'zoom'."""
    tw, th = im.width / zoom, im.height / zoom
    if tw / th > 16 / 9:
        tw = th * 16 / 9
    else:
        th = tw * 9 / 16
    x = min(max(0, im.width * fuoco[0] - tw / 2), im.width - tw); y = min(max(0, im.height * fuoco[1] - th / 2), im.height - th)
    im = im.crop((int(x), int(y), int(x + tw), int(y + th))).resize((W, H), Image.LANCZOS)
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.2)).enhance(1.15)


def testo_grande(d, xy, t, colore, alt_max, larg_max, ancora='la', bordo=None):
    s = alt_max
    while s > 60 and d.textlength(t, font=F(s)) > larg_max:
        s -= 4
    d.text(xy, t, font=F(s), fill=colore, stroke_width=bordo or max(8, s // 11), stroke_fill=(0, 0, 0), anchor=ancora)
    return s


def ombra(im, lato='sinistra', forza=200, larg=0.6):
    g = Image.new('L', (W, 1))
    for x in range(W):
        f = x / W if lato == 'destra' else 1 - x / W
        g.putpixel((x, 0), int(forza * max(0, (f - (1 - larg)) / larg)))
    im.paste(Image.new('RGB', (W, H)), (0, 0), g.resize((W, H)))
    return im


out = {}
# ---- A: VISIERA / PRIMO PIANO — soggetto enorme a destra, 2 parole gialle giganti a sinistra
a = P['A']; im = riempi(Image.open(os.path.join(CART, a['foto'])).convert('RGB'), a.get('fuoco', (0.5, 0.4)), a.get('zoom', 1.4))
im = ombra(im, 'sinistra', 210, 0.55); d = ImageDraw.Draw(im)
parole = a['testo'].split()
righe = [' '.join(parole[:len(parole) // 2 or 1]), ' '.join(parole[len(parole) // 2 or 1:])] if len(parole) > 1 else parole
y = 90
for r in righe:
    s = testo_grande(d, (50, y), r, '#FFD400', 260, 640); y += int(s * 1.02)
out['A'] = im

# ---- B: CONTRASTO TERMICO — meta' ghiaccio e meta' fuoco, i due numeri giganti
b = P['B']; im = riempi(Image.open(os.path.join(CART, b['foto'])).convert('RGB'), b.get('fuoco', (0.5, 0.5)), b.get('zoom', 1.1))
fredda = Image.blend(im, Image.new('RGB', (W, H), (40, 140, 255)), 0.38)
calda = Image.blend(im, Image.new('RGB', (W, H), (255, 90, 0)), 0.38)
m = Image.new('L', (W, H)); dm = ImageDraw.Draw(m); dm.polygon([(0, 0), (W * .58, 0), (W * .42, H), (0, H)], fill=255)
im = Image.composite(fredda, calda, m.filter(ImageFilter.GaussianBlur(6))); d = ImageDraw.Draw(im)
d.line([(W * .58, 0), (W * .42, H)], fill='white', width=10)
testo_grande(d, (40, 40), b['sinistra'], 'white', 210, 520)
testo_grande(d, (W - 40, H - 40), b['destra'], '#FFE14D', 210, 520, 'rd')
out['B'] = im

# ---- C: VOLTO RITOCCATO CON AI — stessa foto vera, resa drammatica (gelo sulla visiera, espressione tesa)
c = P['C']; base = riempi(Image.open(os.path.join(CART, c['foto'])).convert('RGB'), c.get('fuoco', (0.5, 0.4)), c.get('zoom', 1.2))
buf = io.BytesIO(); base.save(buf, 'JPEG', quality=90)
im = None
if SPESA['tot'] + PREZZO <= MAX_SPESA and E('FAL_KEY'):
    SPESA['tot'] += PREZZO
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    try:
        inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', {
            'prompt': c.get('prompt') or ('Keep this exact real NASA astronaut and spacesuit, photorealistic. Make it a dramatic cinematic YouTube thumbnail close-up: '
                                          'thick frost and ice crystals on the helmet visor and suit, cold breath fog inside the visor, tense worried expression, '
                                          'icy blue rim light, deep black space and a thin bright Earth horizon behind. Subject very big, filling the right 60% of the frame, '
                                          'left side darker and simple. No text, no letters, no logos.'),
            'image_urls': ['data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()],
            'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, h)
        for _ in range(120):
            time.sleep(4); st = get(inv['status_url'], h=h)
            if st.get('status') == 'COMPLETED':
                r = get(inv['response_url'], h=h)
                im = Image.open(io.BytesIO(get(r['images'][0]['url'], raw=True))).convert('RGB').resize((W, H)); break
            if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
                log('fal:', json.dumps(st)[:200]); break
    except Exception as e:
        log('ritocco AI non riuscito:', str(e)[:200])
if im is None:
    im = base
im = ombra(im, 'sinistra', 170, 0.5); d = ImageDraw.Draw(im)
parole = c['testo'].split(); y = 110
for r in ([' '.join(parole[:-1]), parole[-1]] if len(parole) > 1 else parole):
    s = testo_grande(d, (50, y), r, 'white' if y == 110 else '#4FD2FF', 240, 600); y += int(s * 1.02)
out['C'] = im

# ---- fogli
for k, v in out.items():
    v.save(os.path.join(CART, f'stile_{k}.jpg'), quality=92)
L = F(30); S = Image.new('RGB', (3 * 640 + 40, 420), 'white'); d = ImageDraw.Draw(S)
for i, (k, v) in enumerate(out.items()):
    S.paste(v.resize((640, 360)), (10 + i * 650, 50)); d.text((10 + i * 650, 8), {'A': 'A · PRIMO PIANO', 'B': 'B · CALDO / FREDDO', 'C': 'C · VOLTO RITOCCATO AI'}[k], font=L, fill='black')
S.save(os.path.join(CART, 'confronto_stili.jpg'), quality=88)
T = Image.new('RGB', (3 * 256 + 20, 160), (15, 15, 15))
for i, v in enumerate(out.values()):
    T.paste(v.resize((246, 138), Image.LANCZOS), (10 + i * 256, 10))
T.save(os.path.join(CART, 'telefono_stili.jpg'), quality=92)
open(os.path.join(CART, 'costi_stili.txt'), 'w').write(f'ritocco AI: {SPESA["tot"]:.2f} $ (tetto {MAX_SPESA:.2f} $); foto NASA: 0\n')
log('FATTO, spesa', SPESA['tot'])
