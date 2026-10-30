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


import base64
CONTROLLATE = []


def claude_vede(im, domanda):
    buf = io.BytesIO(); x = im.copy(); x.thumbnail((900, 900)); x.save(buf, 'JPEG', quality=85)
    corpo = {'model': P.get('modello_controllo') or 'claude-sonnet-5-5', 'max_tokens': 300, 'messages': [{'role': 'user', 'content': [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
        {'type': 'text', 'text': domanda}]}]}
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(corpo).encode(),
                                 headers={'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    t = ''.join(b.get('text', '') for b in json.loads(urllib.request.urlopen(req, timeout=120).read()).get('content', []))
    return json.JSONDecoder().raw_decode(t[t.find('{'):])[0]


def foto_simbolo(v):
    """La foto della copertina: un luogo SIMBOLO del paese, controllato da Claude (paese giusto, luogo riconoscibile, ben visibile).
    Si provano piu' ricerche e piu' foto; vince quella con il voto piu' alto. Restituisce (foto, riquadro del monumento 0-1)."""
    domanda = (f'Questa foto andra\' sulla copertina di un video su TUTTA LA STORIA di: {v["nome"]}. Rispondi SOLO JSON: '
               '{"cosa": "cosa mostra esattamente (luogo, citta, paese)", "paese_giusto": true/false (il luogo si trova DAVVERO in quel paese? se non ne sei sicuro: false), '
               '"simbolo": 1-10 (quanto e\' un simbolo famoso e riconoscibile di quel paese per un italiano), "visibile": 1-10 (quanto il soggetto e\' grande, nitido, ben illuminato), '
               '"box": [x0, y0, x1, y1] (riquadro del soggetto principale, frazioni 0-1 della foto)}')
    migliore = None
    for q in v.get('simboli') or [v.get('simbolo')]:
        url = 'https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'per_page': 6, 'orientation': 'landscape', 'size': 'large'})
        try:
            foto = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': K, 'User-Agent': 'Mozilla/5.0'}), timeout=60).read()).get('photos') or []
        except Exception as e:
            print('pexels', q, e); continue
        for f in foto[:4]:
            try:
                im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(f['src']['large2x'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())).convert('RGB')
                g = claude_vede(im, domanda)
            except Exception as e:
                print('controllo non riuscito', q, str(e)[:100]); continue
            voto = (g.get('simbolo') or 0) + (g.get('visibile') or 0) if g.get('paese_giusto') else -1
            CONTROLLATE.append(f"{v['nome']} | {q} | {g.get('cosa')} | paese {g.get('paese_giusto')} | simbolo {g.get('simbolo')} | visibile {g.get('visibile')} | {f['url']}")
            print(CONTROLLATE[-1])
            if g.get('paese_giusto') and (g.get('simbolo') or 0) >= 8 and (g.get('visibile') or 0) >= 7 and (migliore is None or voto > migliore[0]):
                migliore = (voto, im, g.get('box') or [.2, .2, .8, .8])
        if migliore and migliore[0] >= 18:
            break
    if not migliore:
        raise RuntimeError('nessuna foto superata al controllo per ' + v['nome'])
    return migliore[1], migliore[2]


def ritaglia_su(im, box, w, h, quota=.78):
    """Ritaglio (w x h) centrato sul monumento, che occupa circa 'quota' dell'altezza o della larghezza: grande e ben visibile."""
    W0, H0 = im.size; x0, y0, x1, y1 = [float(c) for c in box]
    bw, bh = max(.05, x1 - x0) * W0, max(.05, y1 - y0) * H0; cx, cy = (x0 + x1) / 2 * W0, (y0 + y1) / 2 * H0
    sc = min(w * quota / bw, h * quota / bh); sc = max(sc, w / W0, h / H0)
    im2 = im.resize((int(W0 * sc), int(H0 * sc)), Image.LANCZOS)
    left = min(max(0, cx * sc - w / 2), im2.width - w); top = min(max(0, cy * sc - h / 2), im2.height - h)
    return im2.crop((int(left), int(top), int(left) + w, int(top) + h))


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


def box2(d, x, y, t, s, fondo, col, padx=26, pady=14, centro=False):
    """Rettangolo che CONTIENE sempre tutta la scritta (misurata sul disegno vero delle lettere), con margine uguale."""
    f = font(s); l, tp, r, b = d.textbbox((0, 0), t, font=f)
    w, h = r - l + 2 * padx, b - tp + 2 * pady
    if centro:
        x = x - w / 2
    d.rectangle([x + 8, y + 10, x + w + 8, y + h + 10], fill=(0, 0, 0, 150))
    d.rectangle([x, y, x + w, y + h], fill=fondo)
    d.text((x + padx - l, y + pady - tp), t, font=f, fill=col)
    return x, y, w, h


def adatta_box(t, s, larg, padx=26):
    while s > 36 and font(s).getlength(t) + 2 * padx > larg:
        s -= 4
    return s


def a1(v, simbolo):
    """A1: come A, ma ogni scritta dentro il suo rettangolo pieno (giallo, nero, rosso)."""
    im = vivace(riempi(simbolo, W, H)); sfuma_sinistra(im, 150, .6)
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    _, y, _, h = box2(d, 50, 44, 'TUTTA LA STORIA', 58, GIALLO, NERO)
    s = adatta_box(v['nome'], 210, W - 120, 30)
    _, y2, _, h2 = box2(d, 50, y + h + 26, v['nome'], s, NERO, BIANCO, 30, 18)
    box2(d, 50, y2 + h2 + 26, v['anni'], 64, ROSSO, BIANCO)
    return im


def a2(v, simbolo):
    """A2: foto simbolo a tutto schermo, scritte centrate in alto dentro i rettangoli (il monumento resta libero in basso)."""
    im = vivace(riempi(simbolo, W, H)).convert('RGBA'); d = ImageDraw.Draw(im)
    s = adatta_box(v['nome'], 200, W - 140, 30)
    _, y, _, h = box2(d, W / 2, 34, v['nome'], s, NERO, GIALLO, 30, 16, centro=True)
    box2(d, W / 2, y + h + 26, v['anni'], 66, ROSSO, BIANCO, centro=True)
    return im


def a3(v, simbolo):
    """A3: pannello blu pieno a sinistra con le scritte impilate, foto simbolo a destra."""
    im = Image.new('RGB', (W, H), (16, 52, 120)); im.paste(vivace(riempi(simbolo, int(W * .58), H)), (int(W * .42), 0))
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    d.polygon([(int(W * .42) - 2, 0), (int(W * .42) + 70, 0), (int(W * .42) - 2, H)], fill=(16, 52, 120))
    larg = W * .42 - 60
    _, y, _, h = box2(d, 40, 70, 'TUTTA LA STORIA', adatta_box('TUTTA LA STORIA', 54, larg), GIALLO, NERO)
    parole = v['nome'].split(); s = min(adatta_box(p, 190, larg, 0) for p in parole)
    altezza = lambda s_: sum(d.textbbox((0, 0), p, font=font(s_))[3] - d.textbbox((0, 0), p, font=font(s_))[1] + 18 for p in parole)
    while s > 60 and y + h + 30 + altezza(s) + 110 > H - 30:   # tutto dentro l'altezza della copertina
        s -= 6
    y += h + 30
    for p in parole:
        l, tp, r, b = d.textbbox((0, 0), p, font=font(s))
        d.text((40 - l + 6, y - tp + 8), p, font=font(s), fill=(0, 0, 0, 160)); d.text((40 - l, y - tp), p, font=font(s), fill=BIANCO)
        y += b - tp + 18
    box2(d, 40, y + 14, v['anni'], adatta_box(v['anni'], 60, larg), ROSSO, BIANCO)
    return im


def pannello(d, v, larg, x=40):
    _, y, _, h = box2(d, x, 70, 'TUTTA LA STORIA', adatta_box('TUTTA LA STORIA', 54, larg), GIALLO, NERO)
    parole = v['nome'].split(); s = min(adatta_box(p, 190, larg, 0) for p in parole)
    alt = lambda s_: sum(d.textbbox((0, 0), p, font=font(s_))[3] - d.textbbox((0, 0), p, font=font(s_))[1] + 18 for p in parole)
    while s > 60 and y + h + 30 + alt(s) + 110 > H - 30:
        s -= 6
    y += h + 30
    for p in parole:
        l, tp, r_, b = d.textbbox((0, 0), p, font=font(s))
        d.text((x - l + 6, y - tp + 8), p, font=font(s), fill=(0, 0, 0, 160)); d.text((x - l, y - tp), p, font=font(s), fill=BIANCO)
        y += b - tp + 18
    box2(d, x, y + 14, v['anni'], adatta_box(v['anni'], 60, larg), ROSSO, BIANCO)


BLU = (16, 52, 120)


def a3a(v, foto, box_):
    """A3a: come A3, ma la foto e' ritagliata sul monumento: grande e al centro della sua parte."""
    xs = int(W * .42); im = Image.new('RGB', (W, H), BLU); im.paste(vivace(ritaglia_su(foto, box_, W - xs, H)), (xs, 0))
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    d.polygon([(xs - 2, 0), (xs + 60, 0), (xs - 2, H)], fill=BLU); pannello(d, v, W * .42 - 60)
    return im


def a3b(v, foto, box_):
    """A3b: pannello piu' stretto (35%), foto piu' grande (65%) ritagliata sul monumento."""
    xs = int(W * .35); im = Image.new('RGB', (W, H), BLU); im.paste(vivace(ritaglia_su(foto, box_, W - xs, H, .85)), (xs, 0))
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    d.rectangle([xs - 6, 0, xs, H], fill=GIALLO); pannello(d, v, W * .35 - 50, 32)
    return im


def a3c(v, foto, box_):
    """A3c: il pannello blu sfuma dentro la foto (nessun taglio netto); il monumento grande nella parte destra."""
    xs = int(W * .30); base = Image.new('RGB', (W, H), BLU)
    base.paste(vivace(ritaglia_su(foto, box_, W - xs, H, .82)), (xs, 0))
    m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
    for x in range(int(W * .56)):
        a_ = 255 if x <= xs + 10 else int(255 * (1 - (x - xs - 10) / (W * .56 - xs - 10)) ** 1.2)
        dm.line([(x, 0), (x, H)], fill=a_)
    base.paste(Image.new('RGB', (W, H), BLU), (0, 0), m)
    im = base.convert('RGBA'); d = ImageDraw.Draw(im); pannello(d, v, W * .42 - 60)
    return im


VARIANTI = {'A': lambda v, f: variante_a(v, f['simbolo']), 'B': lambda v, f: variante_b(v, f['antico'], f['oggi']), 'C': lambda v, f: variante_c(v, f['simbolo'], f['oggi']),
            'A1': lambda v, f: a1(v, f['simbolo']), 'A2': lambda v, f: a2(v, f['simbolo']), 'A3': lambda v, f: a3(v, f['simbolo']),
            'A3a': lambda v, f: a3a(v, f['simbolo'], f['box']), 'A3b': lambda v, f: a3b(v, f['simbolo'], f['box']), 'A3c': lambda v, f: a3c(v, f['simbolo'], f['box'])}
SCELTE = [x.strip() for x in str(P.get('varianti') or 'A,B,C').split(',') if x.strip() in VARIANTI]

righe = []
for v in P.get('video') or []:
    try:
        foto = {k: pexels(v[k]) for k in ('antico', 'oggi') if v.get(k)}
        if v.get('simboli'):   # foto della copertina scelta e CONTROLLATA da Claude
            foto['simbolo'], foto['box'] = foto_simbolo(v)
        elif v.get('simbolo'):
            foto['simbolo'], foto['box'] = pexels(v['simbolo']), [.2, .2, .8, .8]
    except Exception as e:
        print('foto non trovate per', v.get('nome'), e); continue
    nome = v['nome'].lower().replace(' ', '_')
    cop = []
    for lett in SCELTE:
        im = VARIANTI[lett](v, foto).convert('RGB'); p = os.path.join(CART, f'{nome}_{lett}.jpg'); im.save(p, quality=92); cop.append(im)
    riga = Image.new('RGB', (W * len(cop) + 20 * (len(cop) - 1), H), 'white')
    for i, c in enumerate(cop):
        riga.paste(c, (i * (W + 20), 0))
    righe.append(riga)
if righe:
    tav = Image.new('RGB', (righe[0].width, len(righe) * (H + 20)), 'white')
    for i, r in enumerate(righe):
        tav.paste(r, (0, i * (H + 20)))
    tav.resize((tav.width // 2, tav.height // 2)).save(os.path.join(CART, 'confronto.jpg'), quality=88)
open(os.path.join(CART, 'controlli.txt'), 'w').write('\n'.join(CONTROLLATE) + '\n')
print('fatto:', len(righe), 'video')
