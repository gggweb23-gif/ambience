#!/usr/bin/env python3
"""MOCK "possesso" livello 2 (9 nov, richiesta di Giorgio): 3 fotogrammi di esempio.
Sfondo illustrato AI (fal nano-banana-2, senza scritte) + grafica che spiega disegnata in codice sopra (cartellino, scontrini che si accumulano, svalutazione).
Uscita: prove_video/Mock_Possesso/fotogramma_*.jpg. Costo: 3 immagini (circa 0,24 $)."""
import io, json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

E = os.environ.get
OUT = 'prove_video/Mock_Possesso'; os.makedirs(OUT, exist_ok=True)
W, H = 1920, 1080
FONT = 'ctr_test/Anton.ttf'
STILE = ('Premium editorial illustration for an Italian personal-finance YouTube explainer, semi-realistic 2.5D style with soft shading, warm cinematic light, '
         'clean composition with empty space on the LEFT half for graphics, Italian setting. Absolutely no text, no numbers, no logos, no license plates. ')
SCENE = [
    'A shiny new compact red city car in a bright Italian car showroom, a young man looking at it from the right side, hopeful.',
    'The same young man at a kitchen table at night in a small Italian apartment, worried, a laptop and a pile of paper bills and envelopes on the table, the red car visible through the window.',
    'The same red city car five years later parked on an Italian street, slightly dusty and scratched, autumn leaves, the young man walking away with a for-sale sign in his hand.',
]


def http(url, data=None, headers=None, raw=False):
    body = json.dumps(data).encode() if data is not None else None
    h = {'Content-Type': 'application/json'} if data is not None else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=300) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def img(desc):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/fal-ai/nano-banana-2', {'prompt': STILE + desc, 'aspect_ratio': '16:9', 'output_format': 'jpeg', 'num_images': 1}, hd)
    for _ in range(150):
        time.sleep(3)
        if http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = http(inv['response_url'], headers=hd)['images'][0]['url']
    return Image.open(io.BytesIO(http(u, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS)


F = lambda s: ImageFont.truetype(FONT, s)
INK, Y, R, G, BIANCO = (30, 34, 53), (255, 201, 60), (232, 57, 70), (43, 182, 115), (255, 255, 255)


def ombra(base, box, r=26):
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(sh)
    d.rounded_rectangle((box[0] + 10, box[1] + 14, box[2] + 10, box[3] + 14), r, fill=(0, 0, 0, 110))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))


def pannello(im, box, fill=(255, 255, 255, 240), r=26):
    ombra(im, box, r); d = ImageDraw.Draw(im); d.rounded_rectangle(box, r, fill=fill)


def testo(d, xy, t, size, col, anc='la'):
    d.text(xy, t, font=F(size), fill=col, anchor=anc)


def f1(bg):
    """Cartellino: prezzo che tutti vedono + domanda."""
    im = bg.convert('RGBA')
    pannello(im, (110, 250, 760, 560), (255, 255, 255, 245)); d = ImageDraw.Draw(im)
    testo(d, (150, 285), 'PREZZO SUL CARTELLINO', 46, (90, 95, 115))
    testo(d, (150, 350), '25.000 €', 150, INK)
    pannello(im, (110, 620, 980, 780), R + (255,)); d = ImageDraw.Draw(im)
    testo(d, (150, 650), 'MA QUANTO COSTA DAVVERO?', 74, BIANCO)
    return im


def f2(bg):
    """Scontrini che si accumulano + totale che corre."""
    im = bg.convert('RGBA')
    voci = [('Rate + interessi', '27.600 €'), ('Assicurazione', '3.500 €'), ('Bollo', '900 €'), ('Tagliandi e gomme', '3.000 €'), ('Carburante', '7.000 €')]
    pannello(im, (100, 120, 900, 760), (255, 250, 236, 248)); d = ImageDraw.Draw(im)
    testo(d, (140, 150), 'IN 5 ANNI PAGHI', 60, INK)
    for i, (n, v) in enumerate(voci):
        y = 250 + i * 92
        d.line((140, y + 78, 860, y + 78), fill=(220, 214, 196), width=3)
        testo(d, (140, y), n, 52, (60, 64, 85)); testo(d, (860, y), v, 56, R, 'ra')
    pannello(im, (100, 800, 900, 960), INK + (255,)); d = ImageDraw.Draw(im)
    testo(d, (140, 845), 'TOTALE', 60, Y); testo(d, (860, 815), '42.000 €', 100, Y, 'ra')
    return im


def f3(bg):
    """Svalutazione: barra che si accorcia anno per anno + costo vero."""
    im = bg.convert('RGBA')
    pannello(im, (90, 110, 1000, 640), (255, 255, 255, 245)); d = ImageDraw.Draw(im)
    testo(d, (130, 140), 'QUANTO VALE LA TUA AUTO', 58, INK)
    val = [25000, 20000, 16500, 13800, 11800, 10000]
    for i, v in enumerate(val):
        y = 240 + i * 64; w = int(480 * v / 25000)
        testo(d, (130, y), 'oggi' if i == 0 else f'anno {i}', 40, (90, 95, 115))
        d.rounded_rectangle((300, y + 4, 300 + w, y + 48), 12, fill=G if i == 0 else (R if i == 5 else (120, 160, 230)))
        testo(d, (310 + w, y + 2), f'{v:,}'.replace(',', '.') + ' €', 40, INK)
    pannello(im, (90, 690, 1000, 950), INK + (255,)); d = ImageDraw.Draw(im)
    testo(d, (130, 710), '42.000 € PAGATI  -  10.000 € RIVENDUTA', 46, BIANCO)
    testo(d, (130, 790), 'COSTO VERO 32.000 €', 110, Y)
    return im


def main():
    for k, (sc, fn) in enumerate(zip(SCENE, [f1, f2, f3]), 1):
        bg = img(sc)
        bg.save(os.path.join(OUT, f'sfondo_{k}.jpg'), quality=90)
        fn(bg).convert('RGB').save(os.path.join(OUT, f'fotogramma_{k}.jpg'), quality=92)
        print('fatto', k, flush=True)


if __name__ == '__main__':
    main()
