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
ARCHIVO = os.path.join(R.ROOT, 'fonts_costo_vero', 'ArchivoBlack-Regular.ttf')
STILE = C.get('copertina_stile') or (NOME if NOME in ('lost_america', 'beyond_history', 'intothegreen') else 'intothegreen')


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


def componi(img, sp, variante):
    im = img.copy(); d = ImageDraw.Draw(im)
    sx, sy = dove(img, sp['soggetto'])
    if STILE == 'lost_america':
        bh = int(H * .2)
        d.rectangle((0, 0, W, bh), fill=(196, 18, 24))
        testo = sp['banner'].upper().rstrip('.')
        f = font_per(testo, BEBAS, W - 60, 150)
        d.text((W / 2, bh / 2 + 4), testo, font=f, fill=(255, 255, 255), anchor='mm')
        for k, lab in enumerate((sp.get('labels') or [])[:2]):
            ox, oy = dove(img, lab.replace('Your ', ''))
            fo = ImageFont.truetype(ARCHIVO, 34)
            lw = d.textlength(lab, font=fo) + 36
            lx = 30 if ox > W / 2 else W - lw - 30   # etichetta dal lato opposto all'oggetto, freccia che lo raggiunge
            ly = bh + 30 + k * 90
            d.rounded_rectangle((lx, ly, lx + lw, ly + 60), radius=18, fill=(255, 255, 255), outline=(0, 0, 0), width=3)
            d.text((lx + 18, ly + 30), lab, font=fo, fill=(0, 0, 0), anchor='lm')
            freccia(d, (lx + lw / 2, ly + 62), (ox, oy - 20), (214, 20, 26), 12, .2 if k == 0 else -.2)
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


def main():
    c = json.load(open(os.path.join(OUT, 'copione.json')))
    sp = spec(c['titolo']); R.log('copertina:', sp)
    base = (C.get('stile_copertina_ai') or 'Hyper-realistic, highly detailed, vivid colors, cinematic lighting, YouTube thumbnail photo, 16:9, '
            'no text, no letters, no logos, correct anatomy') + '. ' + sp['scene']
    for v in (1, 2):
        img = klein(base + (' Wide shot.' if v == 1 else ' Closer shot, subject bigger.'))
        componi(img, sp, v).save(os.path.join(OUT, f'copertina_{v}.jpg'), quality=92)
    open(os.path.join(OUT, 'copertina.txt'), 'w').write(json.dumps(sp, ensure_ascii=False, indent=1) + f"\ncosto immagini {R.COSTI.get('fal_$', 0):.3f} $ + Haiku {R.COSTI['claude_haiku_$']:.3f} $\n")


if __name__ == '__main__':
    main()
