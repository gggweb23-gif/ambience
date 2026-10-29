#!/usr/bin/env python3
"""
STUDIO CARTELLINI (canali a mappe): l'idea "cartellino del prezzo" in 3 varianti, accanto alla copertina originale del competitor.
I cartellini NON coprono mai i paesi: stanno nel mare / nello spazio libero e una freccia li collega al paese.
  A  COME LORO + CARTELLINI - schermo diviso con linea rossa, mappa chiara e colori fluo come il competitor, la loro scritta (WHY?) + i cartellini
  B  RIFLETTORE             - mappa scura, solo i paesi accesi, cartellini + domanda in alto (SAME CONTINENT?)
  C  IL DIVARIO             - come A, al posto della scritta un grande bollo giallo sulla linea con quante volte e' piu' ricco (9X)
Disegnato in codice, gratis: riusa i dati (paesi e prezzi veri) di prove_angoli/<piano_da>/piano.json.
Ingresso: PAYLOAD = {"nome": "...", "piano_da": "rich-borders-idee", "testi_loro": {"<id>": "WHY?"}}
"""
import json, math, os, re, sys
sys.argv = sys.argv[:1]
P0 = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'copertina_presentatore': ''})
sys.path.insert(0, os.getcwd())
import video_mappe as VM
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

W, H = VM.W, VM.H
SRC = os.path.join('prove_angoli', P0.get('piano_da', 'rich-borders-idee'))
CART = os.path.join('prove_angoli', P0['nome']); os.makedirs(CART, exist_ok=True)
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
    """Mezza copertina (Wm x H) centrata su questi paesi. Ritorna immagine e i poligoni in pixel (coordinate della meta')."""
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


def bollo(im, x, y, testo):
    d = ImageDraw.Draw(im); r = 150
    d.ellipse([x - r - 10, y - r - 10, x + r + 10, y + r + 10], fill=(0, 0, 0))
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 214, 0))
    f = VM.font('Anton-Regular.ttf', 150 if len(testo) <= 3 else 110)
    d.text((x, y - 6), testo, font=f, fill=(0, 0, 0), anchor='mm')


def numero(p):
    m = re.sub(r'[^\d.]', '', str(p).replace(',', ''))
    try:
        return float(m)
    except Exception:
        return 0.0


def copertina(variante, luoghi, testo_loro, domanda, path):
    scuro = variante == 'B'
    if len(luoghi) >= 2:
        meta = W // 2
        ordina = sorted(luoghi[:2], key=lambda l: 0 if l.get('ricco') else 1)   # chi vince a sinistra, come il competitor
        im = Image.new('RGBA', (W, H)); maschere = []
        for k, l in enumerate(ordina):
            mi, mm = mezza([str(c) for c in l.get('iso') or []], LIME if l.get('ricco') else RUGGINE, meta, scuro)
            im.paste(mi, (k * meta, 0)); maschere.append(mm)
        d = ImageDraw.Draw(im); d.rectangle([meta - 12, 0, meta + 12, H], fill=(0, 0, 0)); d.rectangle([meta - 7, 0, meta + 7, H], fill=(235, 30, 40))
        evita = [(W * .25, H * .70, W * .5, H * .3)] if variante == 'A' else [(W * .2, 0, W * .6, 230)] if variante == 'B' else [(meta - 170, H * .5 - 170, 340, 340)]
        for k, l in enumerate(ordina):
            metti_cartellino(im, maschere[k], k * meta, meta, str(l.get('prezzo') or ''), bool(l.get('ricco')),
                             [(ex - k * meta, ey, ew, eh) for ex, ey, ew, eh in evita])
        if variante == 'A':
            VM.riquadro(im, meta, H * .84, testo_loro, 150 if len(testo_loro) <= 8 else 105)
        elif variante == 'B':
            VM.riquadro(im, meta, 115, domanda, 130 if len(domanda) <= 14 else 100)
        else:
            a, b = numero(ordina[0].get('prezzo')), numero(ordina[1].get('prezzo'))
            bollo(im, meta, H * .5, f'{round(a / b)}X' if a and b and a / b >= 1.5 else '?')
    else:
        l = luoghi[0]; mi, mm = mezza([str(c) for c in l.get('iso') or []], LIME, W, scuro); im = mi
        metti_cartellino(im, mm, 0, W, str(l.get('prezzo') or ''), True)
        VM.riquadro(im, W / 2, H * .84 if variante != 'B' else 115, testo_loro if variante != 'B' else domanda, 120)
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)


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


def b_varianti(variante, luoghi, domanda, path):
    """B1 domanda enorme in riquadro nero | B2 parola gigante color crema stile 'grandi scritte' | B3 prezzi giganti al posto dei cartellini."""
    meta = W // 2
    if variante == 'B1':
        im, ordina, mm = riflettore_base(luoghi, .30)
        d = ImageDraw.Draw(im); f, fs = testo_fit(d, domanda, 'Anton-Regular.ttf', 210, W - 220)
        w = d.textlength(domanda, font=f); h = fs * .82
        d.rectangle([W / 2 - w / 2 - 50, 30, W / 2 + w / 2 + 50, 30 + h + 90], fill=(235, 30, 40))
        d.rectangle([W / 2 - w / 2 - 38, 42, W / 2 + w / 2 + 38, 18 + h + 90], fill=(0, 0, 0))
        d.text((W / 2, 30 + (h + 90) / 2), domanda, font=f, fill='white', anchor='mm')
        for k, l in enumerate(ordina):
            metti_cartellino(im, mm[k], k * meta, meta, str(l.get('prezzo') or ''), bool(l.get('ricco')), [(0, 0, W, 330)])
    elif variante == 'B2':
        im, ordina, mm = riflettore_base(luoghi, .42)
        parole = domanda.split(); piccola, grande = (' '.join(parole[:-1]), parole[-1]) if len(parole) > 1 else ('', parole[0])
        d = ImageDraw.Draw(im)
        if piccola:
            f1, fs1 = testo_fit(d, piccola.title(), 'Poppins-ExtraBold.ttf', 96, W * .6)
            w1 = d.textlength(piccola.title(), font=f1)
            d.rectangle([W / 2 - w1 / 2 - 34, 28, W / 2 + w1 / 2 + 34, 28 + fs1 * 1.25], fill=(252, 240, 222))
            d.text((W / 2, 28 + fs1 * .62), piccola.title(), font=f1, fill=(12, 60, 40), anchor='mm')
            y2 = 28 + fs1 * 1.25 + 10
        else:
            y2 = 30
        f2, fs2 = testo_fit(d, grande, 'Poppins-ExtraBold.ttf', 300, W - 140)
        d.text((W / 2 + 10, y2 + fs2 * .55 + 12), grande, font=f2, fill=(0, 0, 0, 170), anchor='mm')
        d.text((W / 2, y2 + fs2 * .55), grande, font=f2, fill=(252, 240, 222), anchor='mm', stroke_width=4, stroke_fill=(20, 40, 30))
        for k, l in enumerate(ordina):
            metti_cartellino(im, mm[k], k * meta, meta, str(l.get('prezzo') or ''), bool(l.get('ricco')), [(0, 0, W, y2 + fs2 * 1.1)])
    else:   # B3: prezzi giganti, niente cartellini
        im, ordina, mm = riflettore_base(luoghi, .38)
        d = ImageDraw.Draw(im)
        for k, l in enumerate(ordina):
            prezzo = str(l.get('prezzo') or '')
            f, fs = testo_fit(d, prezzo, 'Anton-Regular.ttf', 230, meta - 90)
            cx = k * meta + meta / 2; cy = 40 + fs * .55
            d.text((cx + 8, cy + 10), prezzo, font=f, fill=(0, 0, 0), anchor='mm')
            d.text((cx, cy), prezzo, font=f, fill=LIME if l.get('ricco') else (255, 90, 50), anchor='mm', stroke_width=8, stroke_fill=(0, 0, 0))
            m = np.asarray(mm[k].resize((meta // 8, H // 8))) > 0; ys, xs = np.nonzero(m)
            if len(xs):
                freccia(im, (cx, cy + fs * .55), (k * meta + xs.mean() * 8, ys.mean() * 8))
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)


piani = json.load(open(os.path.join(SRC, 'piano.json')))
righe = []
for x in piani:
    n, vid, tit, pc = x['n'], x['id'], x['titolo'], x['piano'].get('cartellino') or {}
    luoghi = pc.get('luoghi') or []
    if not luoghi:
        continue
    testo_loro = str((P0.get('testi_loro') or {}).get(vid) or 'WHY?').upper()
    domanda = str(pc.get('scritta') or 'WHY?').upper()
    Image.open(os.path.join(SRC, f'{n}_loro.jpg')).save(os.path.join(CART, f'{n}_loro.jpg'), quality=90)
    for v in (P0.get('varianti') or ['A', 'B', 'C']):
        try:
            if v.startswith('B') and len(v) == 2 and len(luoghi) >= 2:
                b_varianti(v, luoghi, domanda, os.path.join(CART, f'{n}_{v}.jpg'))
            else:
                copertina(v, luoghi, testo_loro, domanda, os.path.join(CART, f'{n}_{v}.jpg'))
        except Exception as e:
            print('variante', v, 'non riuscita', vid, str(e)[:200], flush=True); Image.new('RGB', (1280, 720), (60, 60, 60)).save(os.path.join(CART, f'{n}_{v}.jpg'))
    righe.append((n, tit, pc.get('fonte', ''))); print('fatto', n, flush=True)

F = VM.font('Anton-Regular.ttf', 30); F2 = VM.font('Anton-Regular.ttf', 22)
tw, th = 640, 360
S = Image.new('RGB', (tw * 4, (th + 50) * len(righe) + 50), 'white'); d = ImageDraw.Draw(S)
VARI = P0.get('varianti') or ['A', 'B', 'C']
NOMI = {'A': 'A · COME LORO + CARTELLINI', 'B': 'B · RIFLETTORE', 'C': 'C · IL DIVARIO', 'B1': 'B1 · DOMANDA ENORME', 'B2': 'B2 · PAROLA GIGANTE', 'B3': 'B3 · PREZZI GIGANTI'}
for j, t in enumerate(['LORO'] + [NOMI.get(v, v) for v in VARI]):
    d.text((j * tw + 10, 8), t, font=F, fill='black')
M = Image.new('RGB', (4 * 256 + 10, len(righe) * 148 + 10), (15, 15, 15))
for i, (n, tit, fonte) in enumerate(righe):
    y = 50 + i * (th + 50)
    d.text((10, y + 6), f'{tit[:70]}   |   dati: {str(fonte)[:90]}', font=F2, fill='grey')
    for j, k in enumerate(['loro'] + VARI):
        im = Image.open(os.path.join(CART, f'{n}_{k}.jpg')).convert('RGB')
        S.paste(im.resize((tw, th)), (j * tw, y + 40)); M.paste(im.resize((246, 138), Image.LANCZOS), (10 + j * 256, 10 + i * 148))
S.save(os.path.join(CART, 'confronto.jpg'), quality=85); M.save(os.path.join(CART, 'telefono.jpg'), quality=90)
print('FATTO', flush=True)
