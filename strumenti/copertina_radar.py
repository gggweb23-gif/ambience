#!/usr/bin/env python3
"""COPERTINA RADAR (21 nov 2026, Giorgio: "copiare quanto piu' possibile lo stile del competitor, alta qualita', minimo costo").
Copertina nello STILE del competitor del canale (studio in copertine_competitor/radar_<canale>/), sul titolo della prova:
  - lost_america: fascia ROSSA in alto con scritta bianca condensata, foto d'epoca fotorealistica, etichette bianche con freccia rossa
  - beyond_history: scena fotorealistica di una scoperta, grande FRECCIA ROSSA sul soggetto, nessuna scritta
  - intothegreen: scena fotorealistica (animale/foresta dall'alto), 2 righe di scritta (bianca + gialla) e freccia bianca curva
Immagine FLUX.2 Klein (circa 0,009 $ l'una, 2 varianti), Claude Haiku trova dove puntare le frecce. Totale circa 0,03 $.
Mai il punto finale, mai scritte nell'angolo in basso a destra (durata), scritta mai sopra il soggetto.
Uscita: prove_video/radar/<canale>/copertina_1.jpg, copertina_2.jpg"""
import io, json, math, os, re, sys, time
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('CANALE', 'lost_america')
import prova_radar as R

C, NOME, OUT = R.C, R.NOME, R.OUT
W, H = 1280, 720
ANTON = os.path.join(R.ROOT, 'ctr_test', 'Anton.ttf')
BEBAS = os.path.join(R.ROOT, 'fonts_costo_vero', 'BebasNeue-Regular.ttf')
A_FONT = os.path.join(R.ROOT, 'ctr_test', 'Anton.ttf')
ARCHIVO = os.path.join(R.ROOT, 'fonts_costo_vero', 'ArchivoBlack-Regular.ttf')
STILE = 'mappa' if C.get('copertina_stile') == 'mappa' else C.get('copertina_stile') or (NOME if NOME in ('lost_america', 'beyond_history', 'intothegreen') else 'intothegreen')


def spec(titolo):
    regole = {
        'lost_america': 'banner: 2-4 words in CAPS for a red top banner (e.g. "1950s KIDS ONLY", "SUMMER WITHOUT AC"); labels: 1-2 short labels '
                        '(2 words, e.g. "Your Bike", "Your Candy") naming objects visible in the scene; scene: a nostalgic photorealistic 1950s '
                        'American scene with those objects clearly visible, people smiling, warm Kodachrome colors.',
        'beyond_history': 'banner: ""; labels: [] ; scene: a hyper-realistic cinematic photo of an explorer/archaeologist discovering the key object '
                          'of the title (e.g. gold treasure in a cave, a strange structure), dramatic lighting, the object big and clear.',
        'intothegreen': 'lines: 2 short lines (1-2 words each, e.g. "DEEP" / "AMAZON", "HUMAN" / "HUNTER"); scene: hyper-realistic aerial or close '
                        'wildlife photo of the danger of the title (giant animal, river, jungle), a tiny human/boat for scale, vivid greens.',
    }[STILE]
    t = R.claude(f'YouTube thumbnail for the video "{titolo}". Copy the style of a winning channel. {regole}\n'
                 'The object to point at must be named in "soggetto". Reply ONLY JSON: {"banner": "", "lines": ["", ""], "labels": [], '
                 '"scene": "...", "soggetto": "..."}', max_tokens=800)
    return json.loads(t[t.index('{'):t.rindex('}') + 1])


def klein(prompt):
    hd = {'Authorization': 'Key ' + R.E('FAL_KEY', '')}
    inv = R.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': W, 'height': H}, 'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
    for _ in range(90):
        time.sleep(2)
        if R.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    u = R.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
    R.COSTI['fal_$'] = R.COSTI.get('fal_$', 0) + 0.009
    return Image.open(io.BytesIO(R.http(u, raw=True, timeout=120))).convert('RGB')


def dove(img, cosa):
    """Haiku: centro dell'oggetto (in % della foto). Serve per puntare le frecce e tenere la scritta lontana."""
    r = R.claude(f'Where is "{cosa}" in this image? Reply ONLY with x,y of its center as percentages of width and height (e.g. 62,48).',
                 modello='claude-haiku-4-5-20251001', max_tokens=15, immagine=img)
    n = re.findall(r'\d+(?:\.\d+)?', r)
    return (float(n[0]) / 100 * W, float(n[1]) / 100 * H) if len(n) >= 2 else (W * .6, H * .55)


def freccia(d, a, b, colore, spessore=16, curva=.25):
    """Freccia curva disegnata (stile a mano) da a verso b."""
    (x1, y1), (x2, y2) = a, b
    mx, my = (x1 + x2) / 2 - (y2 - y1) * curva, (y1 + y2) / 2 + (x2 - x1) * curva
    pts = [((1 - t) ** 2 * x1 + 2 * (1 - t) * t * mx + t ** 2 * x2, (1 - t) ** 2 * y1 + 2 * (1 - t) * t * my + t ** 2 * y2) for t in [i / 30 for i in range(31)]]
    pts = pts[:-3]
    d.line(pts, fill=(0, 0, 0), width=spessore + 8, joint='curve'); d.line(pts, fill=colore, width=spessore, joint='curve')
    (px, py), (ex, ey) = pts[-2], pts[-1]
    ang = math.atan2(ey - py, ex - px); L = spessore * 3.2
    tri = [(ex + math.cos(ang) * L * .9, ey + math.sin(ang) * L * .9), (ex + math.cos(ang + 2.4) * L, ey + math.sin(ang + 2.4) * L),
           (ex + math.cos(ang - 2.4) * L, ey + math.sin(ang - 2.4) * L)]
    d.polygon(tri, fill=colore, outline=(0, 0, 0))


def font_per(testo, path, larghezza, massimo):
    s = massimo
    while s > 30:
        f = ImageFont.truetype(path, s)
        if ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(testo, font=f) <= larghezza:
            return f
        s -= 4
    return ImageFont.truetype(path, 30)


def volti(img):
    """Riquadri dei volti/teste (Haiku), per non metterci sopra frecce o etichette."""
    r = R.claude('List every human or animal face/head in this image as boxes in percent: x1,y1,x2,y2 one per line (e.g. 20,10,35,40). '
                 'Make boxes generous (include hair). Reply only with the lines, or NONE.', modello='claude-haiku-4-5-20251001', max_tokens=200, immagine=img)
    out = []
    for riga in r.splitlines():
        n = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', riga)]
        if len(n) == 4:
            out.append((n[0] / 100 * W - 15, n[1] / 100 * H - 15, n[2] / 100 * W + 15, n[3] / 100 * H + 15))
    return out


def sovrapp(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def dentro(p, b):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def componi(img, sp, variante):
    im = img.copy(); d = ImageDraw.Draw(im)
    sx, sy = dove(img, sp['soggetto'])
    if STILE == 'lost_america':
        bh = int(H * .2)
        d.rectangle((0, 0, W, bh), fill=(196, 18, 24))
        testo = sp['banner'].upper().rstrip('.')
        f = font_per(testo, BEBAS, W - 60, 150)
        d.text((W / 2, bh / 2 + 4), testo, font=f, fill=(255, 255, 255), anchor='mm')
        facce = volti(img)   # 22 nov (Giorgio): frecce ed etichette MAI sopra persone o scritte
        occupati = [(0, 0, W, bh)] + facce
        for k, lab in enumerate((sp.get('labels') or [])[:2]):
            ox, oy = dove(img, lab.replace('Your ', ''))
            fo = ImageFont.truetype(ARCHIVO, 34)
            lw = d.textlength(lab, font=fo) + 36; lh = 60
            scelta = None
            for dx, dy in ((-lw - 90, -40), (90, -40), (-lw / 2, 110), (-lw / 2, -170), (-lw - 90, 60), (90, 60)):
                lx, ly = max(15, min(W - lw - 15, ox + dx)), max(bh + 15, min(H - lh - 15, oy + dy))
                box = (lx, ly, lx + lw, ly + lh)
                ax, ay = (lx + lw / 2, ly + lh / 2)
                linea = [(ax + (ox - ax) * t / 10, ay + (oy - ay) * t / 10) for t in range(2, 9)]
                if any(sovrapp(box, o) for o in occupati) or any(dentro(pt, o) for pt in linea for o in occupati) or (lx + lw > W * .8 and ly + lh > H * .82):
                    continue
                scelta = (lx, ly); break
            if not scelta:
                R.log('etichetta senza posto libero, saltata:', lab); continue
            lx, ly = scelta
            occupati.append((lx - 10, ly - 10, lx + lw + 10, ly + lh + 10))
            d.rounded_rectangle((lx, ly, lx + lw, ly + lh), radius=18, fill=(255, 255, 255), outline=(0, 0, 0), width=3)
            d.text((lx + 18, ly + 30), lab, font=fo, fill=(0, 0, 0), anchor='lm')
            ax = lx + lw / 2 + (lw / 2 if ox > lx + lw else -lw / 2 if ox < lx else 0); ay = ly + lh / 2 + (lh / 2 if oy > ly + lh else -lh / 2 if oy < ly else 0)
            freccia(d, (ax, ay), (ox, oy), (214, 20, 26), 10, 0.0)
    elif STILE == 'beyond_history':
        a = (sx + (260 if sx < W / 2 else -260), max(60, sy - 230)) if variante == 1 else (sx + (300 if sx < W / 2 else -300), sy - 60)
        freccia(d, a, (sx + (40 if a[0] > sx else -40), sy - 30), (230, 22, 22), 30, .18)
    else:   # intothegreen
        righe = [x.upper().rstrip('.') for x in (sp.get('lines') or ['', ''])[:2]]
        sinistra = sx > W * .5 if variante == 1 else sx > W * .42
        x0 = 36 if sinistra else W * .5
        y = 40
        for k, r in enumerate(righe):
            f = font_per(r, ARCHIVO, W * .46, 110)
            col = (255, 255, 255) if k == 0 else (255, 204, 0)
            ombra = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(ombra).text((x0 + 4, y + 6), r, font=f, fill=(0, 0, 0, 220))
            im.paste(Image.alpha_composite(im.convert('RGBA'), ombra.filter(ImageFilter.GaussianBlur(6))).convert('RGB')); d = ImageDraw.Draw(im)
            d.text((x0, y), r, font=f, fill=col, stroke_width=3, stroke_fill=(0, 0, 0))
            y += f.size * 1.05
        freccia(d, (x0 + 120, y + 30), (sx - (60 if sx > x0 else -60), sy - 20), (255, 255, 255), 14, .3)
    return im



def copertina_mappa(titolo, v):
    """Stile africaregions (22 nov): territorio VERO (confini US Census) rosso luminoso su vista satellitare, segnaposti, freccia bianca,
    STAY AWAY / FROM <STATO>. Nessuna persona, scritta lontana dal territorio, nulla nell'angolo della durata."""
    stato = re.split(r'\s+(?:Is|Are)\s+Hiding', titolo)[0].strip()
    gj = R.http('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json', timeout=60)
    f = next(x for x in gj['features'] if x['properties']['name'].lower() == stato.lower())
    g = f['geometry']; polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    anelli = [[(lo - 360 if lo > 0 else lo, la) for lo, la in pol[0]] for pol in polys]
    pts = [p for a in anelli for p in a]
    import math
    lat0 = sum(p[1] for p in pts) / len(pts); kx = math.cos(math.radians(lat0))
    xs = [p[0] * kx for p in pts]; ys = [p[1] for p in pts]
    bw, bh_ = max(xs) - min(xs), max(ys) - min(ys)
    box = (W * .44, H * .06, W * .96, H * .78)   # territorio a destra, scritta in basso a sinistra
    sc = min((box[2] - box[0]) / bw, (box[3] - box[1]) / bh_)
    ox = box[0] + ((box[2] - box[0]) - bw * sc) / 2; oy = box[1] + ((box[3] - box[1]) - bh_ * sc) / 2
    pr = lambda lo, la: (ox + (lo * kx - min(xs)) * sc, oy + (max(ys) - la) * sc)
    sfondo = klein(f'Top-down satellite photograph of the terrain of {stato}, United States: mountains, rivers, forests, coastline, natural colors, '
                   'sharp, high detail, no text, no labels, no borders')
    im = sfondo.convert('RGBA')
    maschera = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(maschera)
    for a in anelli:
        if len(a) > 8:
            dm.polygon([pr(*p) for p in a], fill=255)
    bagliore = maschera.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10))
    im = Image.composite(Image.new('RGBA', (W, H), (90, 220, 255, 255)), im, bagliore)
    rosso = Image.new('RGBA', (W, H), (235, 30, 35, 255))
    im = Image.composite(Image.blend(im, rosso, .85), im, maschera).convert('RGB'); d = ImageDraw.Draw(im)
    # segnaposti dentro il territorio
    import random as _r
    _r.seed(stato + str(v)); messi = 0
    while messi < 4:
        x = _r.uniform(box[0], box[2]); y = _r.uniform(box[1], box[3])
        if maschera.getpixel((int(x), int(y))) > 0 and all(maschera.getpixel((int(x + dx), int(y + dy))) > 0 for dx, dy in ((-28, 0), (28, 0), (0, -28), (0, 28))):
            d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(180, 10, 15), outline=(255, 255, 255), width=5)
            d.text((x, y + 1), '!', font=ImageFont.truetype(A_FONT, 40), fill=(255, 255, 255), anchor='mm'); messi += 1
    # scritta in basso a sinistra, lontana dal territorio e dalla durata
    righe = ['STAY AWAY', 'FROM ' + stato.upper()]
    y = H * (.56 if v == 1 else .6)
    for k, r in enumerate(righe):
        fo = font_per(r, A_FONT, W * .42, 120)
        tw = d.textlength(r, font=fo)
        d.rectangle((28, y - 6, 28 + tw + 28, y + fo.size * 1.12), fill=(0, 0, 0))
        d.text((42, y), r, font=fo, fill=(255, 255, 255) if k == 0 else (255, 226, 0))
        y += fo.size * 1.2
    cx_, cy_ = [sum(c) / len(c) for c in zip(*[pr(*p) for p in max(anelli, key=len)])]
    freccia(d, (W * .2, H * .5), (cx_ - 60, cy_ + 20), (255, 255, 255), 16, -.25)
    return im


def main():
    c = json.load(open(os.path.join(OUT, 'copione.json')))
    if STILE == 'mappa':
        for v in (1, 2):
            copertina_mappa(c['titolo'], v).save(os.path.join(OUT, f'copertina_{v}.jpg'), quality=92)
        return
    sp = spec(c['titolo']); R.log('copertina:', sp)
    base = (C.get('stile_copertina_ai') or 'Hyper-realistic, highly detailed, vivid colors, cinematic lighting, YouTube thumbnail photo, 16:9, '
            'no text, no letters, no logos, correct anatomy') + '. ' + sp['scene']
    for v in (1, 2):
        img = klein(base + (' Wide shot.' if v == 1 else ' Closer shot, subject bigger.'))
        componi(img, sp, v).save(os.path.join(OUT, f'copertina_{v}.jpg'), quality=92)
    open(os.path.join(OUT, 'copertina.txt'), 'w').write(json.dumps(sp, ensure_ascii=False, indent=1) + f"\ncosto immagini {R.COSTI.get('fal_$', 0):.3f} $ + Haiku {R.COSTI['claude_haiku_$']:.3f} $\n")


if __name__ == '__main__':
    main()
