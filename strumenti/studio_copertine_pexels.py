#!/usr/bin/env python3
"""STUDIO COPERTINE in stile Pexels (foto vere, come il video) per un canale di storia dei paesi.
3 varianti per ogni video: A = nome del paese gigante sulla foto simbolo; B = antico contro oggi (due foto, freccia);
C = sagoma del paese riempita con la foto simbolo su fondo scuro. Scritte enormi, leggibili da telefono, mai nell'angolo del timer.
PAYLOAD = {"cartella": "prove_video/Storia_in_Minuti/copertine",
           "video": [{"nome": "AFGHANISTAN", "iso": "AFG", "anni": "3000 a.C. → 2026", "simbolo": "Bamiyan Afghanistan", "antico": "ancient ruins Afghanistan", "oggi": "Kabul city"}]}"""
import io, json, os, sys, urllib.parse, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

P = json.loads(os.environ.get('PAYLOAD') or '{}')
K = os.environ.get('PEXELS_API_KEY', '')
RIS = 'risorse_mappe'
W, H = 1280, 720
GIALLO, ROSSO, NERO, BIANCO = (255, 214, 0), (226, 35, 35), (12, 12, 16), (255, 255, 255)
CART = P.get('cartella') or 'prove_video/copertine_pexels'; os.makedirs(CART, exist_ok=True)


def font(s):
    return ImageFont.truetype(os.path.join(RIS, 'Anton-Regular.ttf'), int(s))


def pexels(q, n=0):
    url = 'https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'per_page': 6, 'orientation': 'landscape', 'size': 'large'})
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': K, 'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
    foto = r.get('photos') or []
    if not foto:
        raise RuntimeError('nessuna foto per ' + q)
    f = foto[min(n, len(foto) - 1)]
    b = urllib.request.urlopen(urllib.request.Request(f['src']['large2x'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read()
    print('pexels', q, '->', f['url'])
    return Image.open(io.BytesIO(b)).convert('RGB')


def riempi(im, w, h):
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(.5, .45))


def vivace(im, k=1.25):
    return ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(k)).enhance(1.12)


def testo(d, xy, t, s, fill=BIANCO, stroke=10, anchor='la', ombra=True):
    f = font(s)
    if ombra:
        d.text((xy[0] + 8, xy[1] + 10), t, font=f, fill=(0, 0, 0, 170), anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    d.text(xy, t, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=NERO)


def adatta(t, s, larg):
    while s > 40 and font(s).getlength(t) > larg:
        s -= 4
    return s


def box(d, x, y, t, s, fondo, col, pad=18):
    f = font(s); w = f.getlength(t)
    d.rectangle([x + 7, y + 9, x + w + 2 * pad + 7, y + s * 1.18 + 9], fill=(0, 0, 0, 160))
    d.rectangle([x, y, x + w + 2 * pad, y + s * 1.18], fill=fondo)
    d.text((x + pad, y + s * .08), t, font=f, fill=col)
    return x + w + 2 * pad


def sfuma_sinistra(im, forza=200, quota=.62):
    m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
    for x in range(int(W * quota)):
        dm.line([(x, 0), (x, H)], fill=int(forza * (1 - x / (W * quota)) ** 1.3))
    im.paste(Image.new('RGB', (W, H), (0, 0, 0)), (0, 0), m)


def variante_a(v, simbolo):
    """Nome del paese GIGANTE sulla foto simbolo."""
    im = vivace(riempi(simbolo, W, H)); sfuma_sinistra(im, 190, .7)
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    box(d, 50, 48, 'TUTTA LA STORIA', 64, GIALLO, NERO)
    s = adatta(v['nome'], 260, W - 110)
    testo(d, (50, 150), v['nome'], s, BIANCO, 12)
    box(d, 50, 150 + s * 1.25, v['anni'], 70, ROSSO, BIANCO)
    return im


def variante_b(v, antico, oggi):
    """Antico contro oggi: due foto, freccia, anni grandi."""
    sx = ImageOps.colorize(ImageOps.grayscale(riempi(antico, W // 2, H)), (40, 26, 12), (245, 220, 170))
    dx = vivace(riempi(oggi, W // 2, H), 1.35)
    im = Image.new('RGB', (W, H)); im.paste(sx, (0, 0)); im.paste(dx, (W // 2, 0))
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    d.rectangle([W // 2 - 5, 0, W // 2 + 5, H], fill=BIANCO)
    a, b = [x.strip() for x in (v['anni'].split('→') + [''])[:2]]
    s = adatta(v['nome'], 190, W - 100)
    testo(d, (W / 2, 30), v['nome'], s, GIALLO, 12, 'ma')
    testo(d, (W * .25, H * .62), a, adatta(a, 120, W / 2 - 60), BIANCO, 10, 'mm')
    testo(d, (W * .75, H * .50), b, adatta(b, 140, W / 2 - 60), BIANCO, 10, 'mm')
    cx, cy = W / 2, H * .56   # freccia bianca grande dal passato a oggi
    d.polygon([(cx - 70, cy - 26), (cx + 10, cy - 26), (cx + 10, cy - 56), (cx + 80, cy), (cx + 10, cy + 56), (cx + 10, cy + 26), (cx - 70, cy + 26)],
              fill=ROSSO, outline=NERO, width=6)
    return im


def sagoma(iso):
    g = json.load(open(os.path.join(RIS, 'paesi50.geojson')))['features']
    for f in g:
        p = f['properties']
        if iso in {str(p.get(k)) for k in ('ADM0_A3', 'ISO_A3')}:
            gm = f['geometry']; polys = gm['coordinates'] if gm['type'] == 'MultiPolygon' else [gm['coordinates']]
            return [np.array(pp[0]) for pp in polys]
    return []


def variante_c(v, simbolo, oggi):
    """Sagoma del paese riempita con la foto simbolo, su fondo scuro sfocato."""
    fondo = ImageEnhance.Brightness(riempi(oggi, W, H).filter(ImageFilter.GaussianBlur(14))).enhance(.35)
    im = fondo.convert('RGBA')
    anelli = sagoma(v['iso'])
    if anelli:
        anelli = sorted(anelli, key=len, reverse=True)
        tutti = np.concatenate(anelli[:6]); lo0, lo1 = tutti[:, 0].min(), tutti[:, 0].max(); la0, la1 = tutti[:, 1].min(), tutti[:, 1].max()
        box_w, box_h, x0, y0 = W * .5, H * .8, W * .47, H * .1
        sc = min(box_w / (lo1 - lo0), box_h / (la1 - la0))
        ox = x0 + (box_w - (lo1 - lo0) * sc) / 2; oy = y0 + (box_h - (la1 - la0) * sc) / 2
        pt = lambda lo, la: (ox + (lo - lo0) * sc, oy + (la1 - la) * sc)
        m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
        for r in anelli[:6]:
            if len(r) > 40 or r is anelli[0]:
                dm.polygon([pt(*p) for p in r], fill=255)
        alone = m.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(12))
        im.paste(Image.new('RGBA', (W, H), GIALLO + (255,)), (0, 0), alone.point(lambda x: int(x * .85)))
        bordo = m.filter(ImageFilter.MaxFilter(9))
        im.paste(Image.new('RGBA', (W, H), BIANCO + (255,)), (0, 0), bordo)
        im.paste(vivace(riempi(simbolo, W, H), 1.3).convert('RGBA'), (0, 0), m)
    d = ImageDraw.Draw(im)
    parole = v['nome'].split()
    s = adatta(max(parole, key=len), 210, W * .46)
    y = 70
    for p in parole:
        testo(d, (50, y), p, s, BIANCO, 11); y += s * 1.08
    box(d, 50, y + 20, v['anni'], 64, GIALLO, NERO)
    return im


righe = []
for v in P.get('video') or []:
    try:
        simbolo, antico, oggi = pexels(v['simbolo']), pexels(v['antico']), pexels(v['oggi'])
    except Exception as e:
        print('foto non trovate per', v.get('nome'), e); continue
    nome = v['nome'].lower().replace(' ', '_')
    cop = []
    for lett, fn in (('A', lambda: variante_a(v, simbolo)), ('B', lambda: variante_b(v, antico, oggi)), ('C', lambda: variante_c(v, simbolo, oggi))):
        im = fn().convert('RGB'); p = os.path.join(CART, f'{nome}_{lett}.jpg'); im.save(p, quality=92); cop.append(im)
    riga = Image.new('RGB', (W * 3 + 40, H), 'white')
    for i, c in enumerate(cop):
        riga.paste(c, (i * (W + 20), 0))
    righe.append(riga)
if righe:
    tav = Image.new('RGB', (righe[0].width, len(righe) * (H + 20)), 'white')
    for i, r in enumerate(righe):
        tav.paste(r, (0, i * (H + 20)))
    tav.resize((tav.width // 2, tav.height // 2)).save(os.path.join(CART, 'confronto.jpg'), quality=88)
print('fatto:', len(righe), 'video')
