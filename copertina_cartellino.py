#!/usr/bin/env python3
"""
COPERTINA "CARTELLINO" per i canali a mappe (Rich Borders, colonna copertina_stile = cartellino):
schermo diviso con linea rossa (come il competitor), mappa scura con solo i due paesi accesi (verde chi e' ricco, arancio chi e' povero),
cartellino del prezzo vero (PIL per abitante) nello spazio libero con una freccia verso il paese,
in alto una parola piccola nel riquadro crema e sotto la PAROLA GIGANTE color crema (es. "Same" / "CONTINENT?").
Il modulo usa le funzioni di mappa del motore: prima di usarlo  copertina_cartellino.VM = <modulo video_mappe>.
"""
import base64, io, json, math, re
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

VM = None
W, H = 1920, 1080

LIME, RUGGINE = (90, 255, 60), (235, 80, 30)


def _area(r):
    x, y = r[:, 0], r[:, 1]
    return abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))) / 2


def anelli_lonlat(isos):
    """Terre principali (90% della superficie) e vicine tra loro: niente Alaska, Hawaii, Guyana francese, isole lontane."""
    R = VM.risorse(); out = []
    for cd in isos:
        rs = [r for r in R['paesi'].get(str(cd).upper(), []) if float(r[:, 0].max() - r[:, 0].min()) < 180]
        if not rs:
            continue
        rs = sorted(rs, key=_area, reverse=True)
        c0 = rs[0].mean(axis=0)
        rs = [r for r in rs if np.hypot(*(r.mean(axis=0) - c0)) < 45] or rs[:1]
        tot = sum(_area(r) for r in rs) or 1; acc = 0
        for r in rs:
            out.append(r); acc += _area(r)
            if acc >= .9 * tot:
                break
    return out


def vista_per(isos, Wm, margine=1.35, alto=0.0):
    """Vista che mostra il paese INTERO e grande nella parte bassa (alto = quota in alto lasciata alle scritte)."""
    pts = np.concatenate(anelli_lonlat(isos))
    lo0, lo1, la0, la1 = pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
    larg = max((lo1 - lo0) * margine * W / Wm, (la1 - la0) * margine * W / (H * (1 - alto)), VM.ZOOM_MIN)
    if larg > 330:   # paesi enormi (Russia): meno margine, mai tagliati
        larg = max(330, (lo1 - lo0) * 1.02 * W / Wm)
    hd = larg * H / W
    return {'lon': (lo0 + lo1) / 2, 'lat': (la0 + la1) / 2 + hd * alto / 2, 'larghezza': larg}


def mezza(isos, col, Wm, scuro=False, alto=0.0):
    """Mezza copertina (Wm x H) centrata su questi paesi. Paesi enormi (Russia) che non entrano nella meta': disegnati a tutto schermo e rimpiccioliti."""
    pts = np.concatenate(anelli_lonlat(isos)); lon_c = float((pts[:, 0].min() + pts[:, 0].max()) / 2); span = float(pts[:, 0].max() - pts[:, 0].min())
    serve = span * 1.1 * W / Wm
    if Wm < W and (serve > 330 or serve / 2 > 180 - abs(lon_c)):
        im, m = _mezza(isos, col, W, scuro, 0.0)
        h2 = int(H * Wm / W); y0 = int((H - h2) * (.5 + alto / 2))
        fondo = Image.new('RGBA', (Wm, H), (14, 24, 38, 255) if scuro else (60, 120, 190, 255))
        pezzo = im.resize((Wm, h2), Image.LANCZOS); bordo = max(10, h2 // 8)
        alfa = Image.new('L', (Wm, h2), 255); da = ImageDraw.Draw(alfa)
        for i in range(bordo):   # bordi sopra e sotto sfumati: niente fasce nette
            da.line([(0, i), (Wm, i)], fill=int(255 * i / bordo)); da.line([(0, h2 - 1 - i), (Wm, h2 - 1 - i)], fill=int(255 * i / bordo))
        pezzo.putalpha(alfa); fondo.alpha_composite(pezzo, (0, y0)); mm = Image.new('L', (Wm, H), 0); mm.paste(m.resize((Wm, h2)), (0, y0))
        return fondo, mm
    return _mezza(isos, col, Wm, scuro, alto)


def _mezza(isos, col, Wm, scuro=False, alto=0.0):
    v = VM.camera(vista_per(isos, Wm, alto=alto)); base, pt = VM.fondo(v, 0.0)
    base = ImageEnhance.Contrast(ImageEnhance.Color(base).enhance(1.45)).enhance(1.12)
    if scuro:
        sc = ImageEnhance.Brightness(ImageEnhance.Color(base).enhance(.45)).enhance(.42)
        im = Image.blend(sc, Image.new('RGB', (W, H), (8, 22, 48)), .35).convert('RGBA')
    else:
        im = base.convert('RGBA')
    polys = VM.anelli_visibili(isos, pt)
    g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
    for xy in polys:
        dg.line(xy + [xy[0]], fill=255, width=30)
    im.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), c) for c in col] + [g.filter(ImageFilter.GaussianBlur(18)).point(lambda x: int(x * .9))]))
    m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
    for xy in polys:
        dm.polygon(xy, fill=255)
    chiaro = ImageEnhance.Brightness(ImageOps.grayscale(base).convert('RGB')).enhance(1.55)
    im.paste(ImageEnhance.Color(ImageChops.multiply(chiaro, Image.new('RGB', (W, H), col))).enhance(1.3).convert('RGBA'), (0, 0), m)
    d = ImageDraw.Draw(im)
    for xy in polys:
        d.line(xy + [xy[0]], fill=(255, 255, 255, 220), width=3)
    cx = (W - Wm) // 2
    return im.crop((cx, 0, cx + Wm, H)), m.crop((cx, 0, cx + Wm, H))


def cartellino_img(prezzo, ricco, ang):
    f = VM.font('Anton-Regular.ttf', 120); tw = ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(prezzo, font=f)
    w, h = int(tw + 130), 190
    t = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    corpo = [(20 + 60, 20), (20 + w, 20), (20 + w, 20 + h), (20 + 60, 20 + h), (20, 20 + h / 2)]
    d.polygon([(x + 9, y + 11) for x, y in corpo], fill=(0, 0, 0, 150))
    d.polygon(corpo, fill=(255, 248, 225), outline=(20, 20, 20), width=7)
    d.ellipse([20 + 28, 20 + h / 2 - 14, 20 + 56, 20 + h / 2 + 14], fill=(20, 20, 20))
    d.text((20 + 70 + tw / 2 + 22, 20 + h / 2), prezzo, font=f, fill=(20, 140, 40) if ricco else (200, 40, 30), anchor='mm')
    return t.rotate(ang, resample=Image.BICUBIC, expand=True)


def freccia(im, a, b, col=(255, 255, 255)):
    """Freccia curva dal cartellino (a) al paese (b), bianca con bordo nero."""
    d = ImageDraw.Draw(im); (x0, y0), (x1, y1) = a, b
    mx, my = (x0 + x1) / 2 + (y1 - y0) * .25, (y0 + y1) / 2 - (x1 - x0) * .25
    pts = [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t ** 2 * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t ** 2 * y1) for t in [i / 30 for i in range(31)]]
    d.line(pts[:-2], fill=(0, 0, 0), width=26, joint='curve'); d.line(pts[:-2], fill=col, width=14, joint='curve')
    (ax, ay), (bx, by) = pts[-4], pts[-1]; ang = math.atan2(by - ay, bx - ax); L = 58
    tri = [(bx, by), (bx - L * math.cos(ang - .55), by - L * math.sin(ang - .55)), (bx - L * math.cos(ang + .55), by - L * math.sin(ang + .55))]
    d.polygon(tri, fill=col, outline=(0, 0, 0), width=6)


def metti_cartellino(im, maschera, ox, Wm, prezzo, ricco, evita=()):
    """Cartellino nel punto della meta' dove copre MENO il paese (e le scritte), freccia fino al paese."""
    t = cartellino_img(prezzo, ricco, 6 if ricco else -6)
    m = np.asarray(maschera.resize((Wm // 8, H // 8))) > 0
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return
    cx, cy = xs.mean() * 8, ys.mean() * 8
    best = None
    for fy in (.06, .30, .55, .72):
        for fx in (.03, .30, .55):
            x, y = int(Wm * fx), int(H * fy)
            x = min(x, Wm - t.width - 10); y = min(y, H - t.height - 10)
            sub = m[y // 8:(y + t.height) // 8, x // 8:(x + t.width) // 8]
            cop = sub.mean() if sub.size else 1
            dist = math.hypot(x + t.width / 2 - cx, y + t.height / 2 - cy) / Wm
            vic = sum(1 for (ex, ey, ew, eh) in evita if x < ex + ew and ex < x + ox + t.width and y < ey + eh and ey < y + t.height)
            punt = cop * 5 + vic * 5 + abs(dist - .45)
            if best is None or punt < best[0]:
                best = (punt, x, y)
    _, x, y = best
    bordo = (x + t.width / 2, y + t.height) if cy > y + t.height else (x + t.width / 2, y)
    freccia(im, (ox + bordo[0], bordo[1]), (ox + cx, cy))
    im.alpha_composite(t, (ox + x, y))


def testo_fit(d, testo, nome_font, fs, larg):
    f = VM.font(nome_font, fs)
    while d.textlength(testo, font=f) > larg and fs > 40:
        fs -= 6; f = VM.font(nome_font, fs)
    return f, fs


def riflettore_base(luoghi, alto):
    meta = W // 2
    ordina = sorted(luoghi[:2], key=lambda l: 0 if l.get('ricco') else 1)
    im = Image.new('RGBA', (W, H)); maschere = []
    for k, l in enumerate(ordina):
        mi, mm = mezza([str(c) for c in l.get('iso') or []], LIME if l.get('ricco') else RUGGINE, meta, True, alto)
        im.paste(mi, (k * meta, 0)); maschere.append(mm)
    d = ImageDraw.Draw(im); d.rectangle([meta - 12, 0, meta + 12, H], fill=(0, 0, 0)); d.rectangle([meta - 7, 0, meta + 7, H], fill=(235, 30, 40))
    return im, ordina, maschere



def copertina_b2(luoghi, domanda, path):
    """La copertina scelta (B2). luoghi = [{iso, prezzo, ricco}] (2 luoghi), domanda = 'SAME CONTINENT?'"""
    meta = W // 2
    im, ordina, mm = riflettore_base(luoghi, .48)
    parole = str(domanda or 'WHY?').upper().split()
    piccola, grande = (' '.join(parole[:-1]), parole[-1]) if len(parole) > 1 else ('', parole[0])
    d = ImageDraw.Draw(im)
    if piccola:
        f1, fs1 = testo_fit(d, piccola.title(), 'Poppins-ExtraBold.ttf', 96, W * .6)
        w1 = d.textlength(piccola.title(), font=f1)
        d.rectangle([W / 2 - w1 / 2 - 34, 26, W / 2 + w1 / 2 + 34, 26 + fs1 * 1.25], fill=(252, 240, 222))
        d.text((W / 2, 26 + fs1 * .62), piccola.title(), font=f1, fill=(12, 60, 40), anchor='mm')
        y2 = 26 + fs1 * 1.25 + 8
    else:
        y2 = 30
    f2, fs2 = testo_fit(d, grande, 'Poppins-ExtraBold.ttf', 270, W - 140)
    d.text((W / 2 + 10, y2 + fs2 * .55 + 12), grande, font=f2, fill=(0, 0, 0, 170), anchor='mm')
    d.text((W / 2, y2 + fs2 * .55), grande, font=f2, fill=(252, 240, 222), anchor='mm', stroke_width=4, stroke_fill=(20, 40, 30))
    for k, l in enumerate(ordina):
        metti_cartellino(im, mm[k], k * meta, meta, str(l.get('prezzo') or ''), bool(l.get('ricco')), [(0, 0, W, y2 + fs2 * 1.1)])
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)
    return path


DOMANDA = """This is the thumbnail of a very successful YouTube video titled "{t}" (channel about why one country is rich and its neighbour is poor).
Our thumbnail shows the TWO places of the video with a price tag each (true GDP per capita) and a short hook question. Use only TRUE, well-known public data (World Bank, IMF). Answer ONLY JSON:
{{"luoghi": [{{"nome": "USA", "iso": ["USA"], "prezzo": "$82,000", "ricco": true}}, {{"nome": "LATIN AMERICA", "iso": ["MEX","BRA","ARG","COL","PER","CHL","VEN","ECU","BOL","PRY","URY"], "prezzo": "$9,000", "ricco": false}}],
 "scritta": "2-3 words in CAPS, the LAST word is the big one, e.g. SAME CONTINENT?  SAME ALPS?  2X RICHER?", "fonte": "one line: data used (GDP per capita, year, source)"}}
Rules: exactly 2 places, the rich one first; "prezzo" = GDP per capita in current US$, rounded, with $ and comma; ISO-3 codes of every country of each place;
for a single country video use that country and the most meaningful neighbour; for a world video use the richest countries vs the poorest ones."""


def piano(comp):
    """Claude guarda la copertina del competitor e il titolo e decide i due luoghi, i prezzi veri e la domanda."""
    img = None
    for q in ('maxresdefault', 'hqdefault'):
        try:
            img = VM.http(f'https://i.ytimg.com/vi/{comp["id"]}/{q}.jpg', raw=True); Image.open(io.BytesIO(img)).verify(); break
        except Exception:
            img = None
    cont = [{'type': 'text', 'text': DOMANDA.format(t=comp.get('titolo') or '')}]
    if img:
        buf = io.BytesIO(); Image.open(io.BytesIO(img)).convert('RGB').resize((960, 540)).save(buf, 'JPEG', quality=88)
        cont.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}})
    import os
    rr = VM.http('https://api.anthropic.com/v1/messages', {'model': VM.MODELLO_AI, 'max_tokens': 1500, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    t = ''.join(b.get('text', '') for b in rr.get('content', []))
    return json.JSONDecoder().raw_decode(t[t.find('{'):])[0]   # legge solo il primo oggetto JSON (ignora testo dopo)
