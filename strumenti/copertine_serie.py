#!/usr/bin/env python3
"""
COPERTINE IN SERIE (per tutti i canali) — N copertine nello stesso stile fisso, per vedere come esce il canale.
Stile "C" (volto ritoccato AI): foto d'archivio come riferimento di scena + ritocco fal seedream con un personaggio
INVENTATO (mai una persona reale riconoscibile), soggetto enorme a destra, scritta a sinistra (prime parole bianche,
ultima parola colorata). TETTO RIGIDO di spesa (max 0,25 $ per giro).
PAYLOAD = {"nome": "astronauti-serie-c", "max_spesa": 0.20, "colore": "#4FD2FF",
           "righe": [{"k": 1, "titolo": "...", "testo": "NO WEEKENDS", "foto": "prove_archivi/.../x.jpg", "prompt": "..."}]}
Uscita: prove_archivi/<nome>/c_<k>.jpg, serie.jpg (con i titoli), telefono.jpg (come in home su telefono), costi.txt
"""
import base64, io, json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_archivi', P['nome']); os.makedirs(CART, exist_ok=True)
MAX_SPESA = min(float(P.get('max_spesa') or 0.10), 0.25); SPESA = {'tot': 0.0}; PREZZO = 0.04
W, H = 1280, 720
COMUNE = (' The astronaut is a FICTIONAL person who does not resemble any real astronaut or celebrity; no name tags, no readable patches. '
          'Photorealistic cinematic film still, dramatic light, high contrast, rich colours. The astronaut is very big, head and shoulders filling the RIGHT 60% '
          'of the frame, face sharp and expressive. The LEFT 40% is darker and simple (for the title). No text, no letters, no logos, no watermark.')
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


def riempi(im):
    tw, th = im.width, im.height
    if tw / th > 16 / 9:
        tw = th * 16 / 9
    else:
        th = tw * 9 / 16
    x, y = (im.width - tw) / 2, (im.height - th) / 2
    return im.crop((int(x), int(y), int(x + tw), int(y + th))).resize((W, H), Image.LANCZOS)


def ritocco(base, prompt):
    if SPESA['tot'] + PREZZO > MAX_SPESA + 1e-9 or not E('FAL_KEY'):
        log('LUCCHETTO SPESA: ritocco saltato'); return None
    SPESA['tot'] += PREZZO
    buf = io.BytesIO(); base.save(buf, 'JPEG', quality=90)
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    try:
        inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', {
            'prompt': 'Use the reference photo only for the setting and the real NASA equipment. ' + prompt + COMUNE,
            'image_urls': ['data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()],
            'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, h)
        for _ in range(120):
            time.sleep(4); st = get(inv['status_url'], h=h)
            if st.get('status') == 'COMPLETED':
                r = get(inv['response_url'], h=h)
                return Image.open(io.BytesIO(get(r['images'][0]['url'], raw=True))).convert('RGB').resize((W, H), Image.LANCZOS)
            if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
                log('fal:', json.dumps(st)[:200]); return None
    except Exception as e:
        log('ritocco non riuscito:', str(e)[:200])
    return None


def ombra(im, forza=170, larg=0.5):
    g = Image.new('L', (W, 1))
    for x in range(W):
        g.putpixel((x, 0), int(forza * max(0, ((1 - x / W) - (1 - larg)) / larg)))
    im.paste(Image.new('RGB', (W, H)), (0, 0), g.resize((W, H)))
    return im


def scritta(im, testo, colore):
    d = ImageDraw.Draw(im); parole = testo.split()
    righe = [' '.join(parole[:-1]), parole[-1]] if len(parole) > 1 else parole
    y = 110
    for i, r in enumerate(righe):
        s = 240
        while s > 60 and d.textlength(r, font=F(s)) > 600:
            s -= 4
        d.text((50, y), r, font=F(s), fill=colore if i == len(righe) - 1 and len(righe) > 1 else 'white',
               stroke_width=max(8, s // 11), stroke_fill=(0, 0, 0))
        y += int(s * 1.02)
    return im


fatte = []
for r in P['righe']:
    base = riempi(Image.open(r['foto']).convert('RGB'))
    im = ritocco(base, r['prompt']) or ImageEnhance.Contrast(base).enhance(1.2)
    im = scritta(ombra(im), r['testo'], P.get('colore') or '#4FD2FF')
    p = os.path.join(CART, f"c_{r['k']}.jpg"); im.save(p, quality=92); fatte.append((r, im))
    log('copertina', r['k'], r['testo'], 'fatta | spesa', round(SPESA['tot'], 2))
L = F(26); S = Image.new('RGB', (2 * 640 + 30, ((len(fatte) + 1) // 2) * 420 + 10), 'white'); d = ImageDraw.Draw(S)
for i, (r, im) in enumerate(fatte):
    x, y = 10 + (i % 2) * 650, 10 + (i // 2) * 420
    S.paste(im.resize((640, 360), Image.LANCZOS), (x, y)); d.text((x, y + 366), f"{r['k']}. {r.get('titolo', '')}"[:60], font=L, fill='black')
S.save(os.path.join(CART, 'serie.jpg'), quality=88)
T = Image.new('RGB', (len(fatte) * 256 + 10, 158), (15, 15, 15))
for i, (_, im) in enumerate(fatte):
    T.paste(im.resize((246, 138), Image.LANCZOS), (10 + i * 256, 10))
T.save(os.path.join(CART, 'telefono.jpg'), quality=92)
open(os.path.join(CART, 'costi.txt'), 'w').write(f"ritocchi AI: {SPESA['tot']:.2f} $ (tetto {MAX_SPESA:.2f} $); foto NASA: 0\n")
log('FATTO, spesa', SPESA['tot'])
