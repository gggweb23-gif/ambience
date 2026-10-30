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
    polys = [[pt(lo, la) for lo, la in r] for r in anelli_lonlat(isos)]   # solo le terre principali: niente pezzi di Alaska sul bordo
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


TIMER = (W - 360, H - 200, 360, 200)   # angolo in basso a destra: su YouTube c'e' la durata del video, il cartellino non va mai li'


def _curva_freccia(a, b, n=30):
    (x0, y0), (x1, y1) = a, b
    mx, my = (x0 + x1) / 2 + (y1 - y0) * .25, (y0 + y1) / 2 - (x1 - x0) * .25
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t ** 2 * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t ** 2 * y1) for t in [i / n for i in range(n + 1)]]


def _dentro(px, py, box, m=30):
    ex, ey, ew, eh = box
    return ex - m < px < ex + ew + m and ey - m < py < ey + eh + m


def metti_cartellino(im, maschera, ox, Wm, prezzo, ricco, evita=()):
    """Cartellino nel punto della meta' dove copre MENO il paese, MAI sulle scritte ne' nell'angolo del timer di YouTube;
    la freccia arriva su una parte del paese fuori dalle scritte e non le attraversa mai."""
    t = cartellino_img(prezzo, ricco, 6 if ricco else -6)
    m = np.asarray(maschera.resize((Wm // 8, H // 8))) > 0
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return
    liberi = []
    for marg in (30, 0):   # paese fuori dalle scritte (prima con un po' di margine, poi senza)
        liberi = [(x * 8, y * 8) for x, y in zip(xs, ys) if not any(_dentro(ox + x * 8, y * 8, b, marg) for b in evita)]
        if liberi:
            break
    if not liberi:   # il paese e' tutto sotto le scritte: la freccia punta alla sua parte piu' bassa
        soglia = np.percentile(ys, 90); liberi = [(x * 8, y * 8) for x, y in zip(xs, ys) if y >= soglia]
    if liberi:
        cx, cy = float(np.mean([p[0] for p in liberi])), float(np.mean([p[1] for p in liberi]))
        if any(_dentro(ox + cx, cy, b) for b in evita) or not m[min(m.shape[0] - 1, int(cy // 8)), min(m.shape[1] - 1, int(cx // 8))]:
            cx, cy = min(liberi, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)   # il punto del paese libero piu' vicino al centro
    else:
        cx, cy = xs.mean() * 8, ys.mean() * 8
    best = None
    for fy in (.06, .20, .30, .42, .55, .64, .72):
        for fx in (.03, .16, .30, .42, .55):
            x, y = int(Wm * fx), int(H * fy)
            x = min(x, Wm - t.width - 10); y = min(y, H - t.height - 10)
            gx0, gy0, gx1, gy1 = ox + x, y, ox + x + t.width, y + t.height
            tx_, ty_, tw_, th_ = TIMER
            if gx1 > tx_ and gy1 > ty_:   # angolo del timer: escluso
                continue
            sub = m[y // 8:(y + t.height) // 8, x // 8:(x + t.width) // 8]
            cop = sub.mean() if sub.size else 1
            dist = math.hypot(x + t.width / 2 - cx, y + t.height / 2 - cy) / Wm
            vic = sum(1 for (ex, ey, ew, eh) in evita if gx0 < ex + ew and ex < gx1 and gy0 < ey + eh and ey < gy1)
            bordo = (x + t.width / 2, y + t.height) if cy > y + t.height else (x + t.width / 2, y)
            curva = _curva_freccia((ox + bordo[0], bordo[1]), (ox + cx, cy))
            taglia = sum(1 for px, py in curva if any(_dentro(px, py, b, 10) for b in evita))   # la freccia passa sopra le scritte?
            punt = cop * 5 + vic * 50 + taglia * 3 + abs(dist - .45)
            if best is None or punt < best[0]:
                best = (punt, x, y)
    if best is None:
        return
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


def _file_parole():
    import os, re as _re
    c = _re.sub(r'\W+', '_', str(VM.P.get('channel_name') or VM.P.get('canale') or 'rich_borders')).strip('_').lower()
    return os.path.join(VM.LIB, 'parole_copertina', c + '.txt')


def parole_usate():
    """Parole GRANDI gia' usate nelle copertine del canale: ogni video deve averne una diversa."""
    try:
        return [x.strip().upper() for x in open(_file_parole(), encoding='utf-8') if x.strip()]
    except Exception:
        return []


def segna_parola(scritta):
    import os
    try:
        p = _file_parole(); os.makedirs(os.path.dirname(p), exist_ok=True)
        grande = str(scritta or '').upper().split()[-1]
        with open(p, 'a', encoding='utf-8') as f:
            f.write(grande + '\n')
    except Exception:
        pass


def piano(comp):
    """Claude guarda la copertina del competitor e il titolo e decide i due luoghi, i prezzi veri e la domanda."""
    img = None
    for q in ('maxresdefault', 'hqdefault'):
        try:
            img = VM.http(f'https://i.ytimg.com/vi/{comp["id"]}/{q}.jpg', raw=True); Image.open(io.BytesIO(img)).verify(); break
        except Exception:
            img = None
    usate = parole_usate()
    vieta = ('\nThe BIG word (the last word of "scritta") must be DIFFERENT from every big word already used by this channel: ' + ', '.join(usate)
             + '. Choose another strong word that fits THIS video (e.g. UNITED?, BROKE?, 44?, HALF?, TRAP?).') if usate else ''
    cont = [{'type': 'text', 'text': DOMANDA.format(t=comp.get('titolo') or '') + vieta}]
    if img:
        buf = io.BytesIO(); Image.open(io.BytesIO(img)).convert('RGB').resize((960, 540)).save(buf, 'JPEG', quality=88)
        cont.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}})
    import os
    rr = VM.http('https://api.anthropic.com/v1/messages', {'model': VM.MODELLO_AI, 'max_tokens': 1500, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    t = ''.join(b.get('text', '') for b in rr.get('content', []))
    pc = json.JSONDecoder().raw_decode(t[t.find('{'):])[0]   # legge solo il primo oggetto JSON (ignora testo dopo)
    grande = str(pc.get('scritta') or '').upper().split()[-1:] 
    if grande and grande[0] in usate and not comp.get('_riprova'):   # parola gia' usata: si chiede di nuovo
        return piano(dict(comp, _riprova=True))
    return pc


# ============================================================ COPERTINA "TITOLO SU MAPPA" (colonna copertina_stile = titolo_mappa)
# Stessa grafica del video: il paese colorato e in rilievo sulla mappa, i disegni della libreria uniti dal tratteggio della storia,
# a sinistra il nome del paese ENORME (caratteri e colori del canale) e sotto la fascia con gli anni (es. "1492 → 2026").
def copertina_titolo(isos, titolo, fascia, icone, path):
    """isos: paese/i protagonisti; titolo: 1-2 parole (es. 'STATI UNITI'); fascia: es. '1492 → 2026';
    icone: [(nome_libreria, lon, lat), ...] da 2 a 4 disegni sul paese, uniti dal tratteggio nell'ordine dato."""
    pts = np.concatenate(anelli_lonlat(isos))
    lo0, lo1, la0, la1 = pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
    larg = max((lo1 - lo0) / .56, (la1 - la0) * 1.15 * W / H, VM.ZOOM_MIN)
    cx = (lo0 + lo1) / 2 - larg * .21          # il paese occupa la parte destra (centro al 71%), a sinistra il titolo
    v = VM.camera({'lon': cx, 'lat': (la0 + la1) / 2, 'larghezza': larg}); base, pt = VM.fondo(v, 0.0)
    im = ImageEnhance.Brightness(base).enhance(.8).convert('RGBA')
    polys = [[pt(lo, la) for lo, la in r] for r in anelli_lonlat(isos)]
    g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
    for xy in polys:
        dg.line(xy + [xy[0]], fill=255, width=34)
    im.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), c) for c in VM.LUCE] + [g.filter(ImageFilter.GaussianBlur(22)).point(lambda x: int(x * .75))]))
    VM.riempi(im, base, polys, VM.ORO, 1.0, 22)
    d = ImageDraw.Draw(im)
    pos = [pt(lo, la) for _, lo, la in icone]
    for a, b in zip(pos, pos[1:]):   # il filo della storia, come nel video
        c = VM._curva(a, b, 30, .2); VM._tratteggio(d, c, (0, 0, 0, 170), 14, 26, 16); VM._tratteggio(d, c, (*VM.LUCE, 255), 8, 26, 16)
        VM._punta(d, c, (*VM.LUCE, 255))
    for (nome, _, _), (x, y) in zip(icone, pos):
        VM.metti(im, VM.icona(nome, 230), x, y)
    # sfumatura scura a sinistra per far leggere il titolo
    sf = Image.new('L', (W, H), 0); ds = ImageDraw.Draw(sf)
    for x in range(int(W * .62)):
        ds.line([(x, 0), (x, H)], fill=int(205 * (1 - x / (W * .62)) ** 1.4))
    im.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), c) for c in VM.mix(VM.NAVY, (0, 0, 0), .45)] + [sf]))
    d = ImageDraw.Draw(im)
    righe = str(titolo).upper().split()
    righe = [' '.join(righe[:len(righe) // 2]), ' '.join(righe[len(righe) // 2:])] if len(righe) > 1 else righe
    fs = 300
    while fs > 120 and max(VM.font('Anton-Regular.ttf', fs).getlength(r) for r in righe) > W * .56:
        fs -= 10
    f = VM.font('Anton-Regular.ttf', fs); y = 90
    for r in righe:
        for z in range(18, 0, -3):
            d.text((70 + z * .7, y + z), r, font=f, fill=VM.mix(VM.NAVY, (0, 0, 0), .5))
        d.text((70, y), r, font=f, fill=VM.CREMA, stroke_width=6, stroke_fill=VM.NAVY)
        y += int(fs * 1.02)
    if fascia:
        f2 = VM.font('Poppins-ExtraBold.ttf', 110); tw = d.textlength(fascia, font=f2); y += 30
        d.rectangle([70 + 10, y + 12, 70 + tw + 70 + 10, y + 170 + 12], fill=(0, 0, 0, 160))
        d.rectangle([70, y, 70 + tw + 70, y + 170], fill=VM.NAVY)
        d.rectangle([70, y + 158, 70 + tw + 70, y + 170], fill=VM.ROSSO)
        d.text((70 + 35 + tw / 2, y + 82), fascia, font=f2, fill=VM.LUCE, anchor='mm')
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=92)
    return path
