#!/usr/bin/env python3
"""COSTO VERO - 3 concetti nuovi di copertina (12 nov 2026, Giorgio: "i video sono interessanti, le copertine no").
Cosa spiega il canale: il PREZZO che vedi e' solo la punta, il COSTO VERO negli anni e' molto di piu'. La copertina deve far vedere
questo scarto in un colpo d'occhio, con il soggetto riconoscibile subito.
  1 ICEBERG:   la piscina e' la punta, sott'acqua un blocco enorme di banconote (il costo nascosto). 35.000 sopra, 60.500 sotto.
  2 SCONTRINO: dalla piscina esce uno scontrino lunghissimo che attraversa il giardino. Totale in rosso.
  3 SOLDI:     la piscina piena di banconote invece che d'acqua. Il costo vero gigante.
Disegno: FLUX.2 Klein (~0,02 $ l'una), scritte in codice (leggibili da telefono, mai in basso a destra sulla durata)."""
import io, os, sys, time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
QUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, QUI); sys.path.insert(0, os.path.dirname(QUI))
import motore_yt as YT
import costi as CO

E = os.environ.get
OUT = E('OUT') or 'prove_video/Costo_Vero/copertine_concetti'; os.makedirs(OUT, exist_ok=True)
FA, FB = 'ctr_test/Anton.ttf', 'fonts_gloam/montserrat_black.woff'
R, Y, INK, BI = (225, 30, 45), (255, 205, 40), (25, 25, 35), (255, 255, 255)
# 12 nov sera (Giorgio): "una prova grafica TOTALMENTE diversa dall'attuale" (niente illustrazione colorata + cartellino + numeri come ora)
CONCETTI = {
    'pennarello': 'Realistic DSLR photograph, natural light, NOT an illustration: a real backyard in-ground swimming pool in an Italian villa garden, '
                  'pool in the RIGHT half of the frame, the LEFT 40% is plain lawn and hedge. Sharp, high detail. NO text, NO letters, NO logos.',
    'noir': 'Cinematic dark photograph: a small perfect scale model of a backyard swimming pool with blue glowing water on a black table, lit by a single '
            'dramatic spotlight from above, deep black background, gold light reflections, luxury product shot, the model is on the RIGHT side. NO text, NO letters.',
    'progetto': 'Technical BLUEPRINT drawing: thin white lines on deep blue blueprint paper with a fine grid, isometric exploded view of a backyard in-ground swimming pool: '
                'the pool basin, the pump, the sand filter, the pipes and the winter cover drawn separately, slightly apart, in the RIGHT 65% of the image. '
                'Blank areas, NO text, NO letters, NO numbers, NO labels.',
}
def fal(ep, dati):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/' + ep, dati, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    return YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']


def F(p, s):
    return ImageFont.truetype(p, int(s))


def etichetta(im, xy, txt, font, size, fg, bg, pad=(26, 14), ang=0, maxw=None):
    while maxw and size > 30 and F(font, size).getlength(txt) > maxw:
        size -= 4
    f = F(font, size); d0 = ImageDraw.Draw(im); b = d0.textbbox((0, 0), txt, font=f)
    w, h = b[2] - b[0] + pad[0] * 2, b[3] - b[1] + pad[1] * 2
    lay = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), 16, fill=bg, outline=INK, width=5)
    d.text((10 + pad[0] - b[0], 10 + pad[1] - b[1]), txt, font=f, fill=fg)
    lay = lay.rotate(ang, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(lay, (int(xy[0]), int(xy[1])))
    return xy[1] + lay.height


def barrato(im, xy, txt, size):
    f = F(FA, size); d = ImageDraw.Draw(im); b = d.textbbox(xy, txt, font=f, stroke_width=6)
    d.text(xy, txt, font=f, fill=BI, stroke_width=6, stroke_fill=INK)
    d.line((b[0] - 6, (b[1] + b[3]) // 2 + 8, b[2] + 6, (b[1] + b[3]) // 2 - 8), fill=R, width=12)
    return b[3]


def tratto(d, pts, col, w):
    """Linea "a mano" (pennarello): due passate leggermente sfalsate."""
    import random
    for k in range(2):
        q = [(x + random.uniform(-2, 2), y + random.uniform(-2, 2)) for x, y in pts]
        d.line(q, fill=col, width=w, joint='curve')


def ellisse_mano(d, b, col, w):
    import math, random
    cx, cy, rx, ry = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
    pts = [(cx + rx * (1 + random.uniform(-.03, .03)) * math.cos(a / 40 * 2 * math.pi + .3), cy + ry * (1 + random.uniform(-.03, .03)) * math.sin(a / 40 * 2 * math.pi + .3)) for a in range(46)]
    tratto(d, pts, col, w)


def main():
    import random
    random.seed(7)
    FM = os.path.join(OUT, 'PermanentMarker.ttf')
    if not os.path.exists(FM):
        open(FM, 'wb').write(YT.http('https://raw.githubusercontent.com/google/fonts/main/apache/permanentmarker/PermanentMarker-Regular.ttf', raw=True, timeout=60))
    FS = 'fonts_gloam/serif.woff'; FMONO = 'fonts_gloam/mono.woff'
    for nome, sc in CONCETTI.items():
        f = os.path.join(OUT, nome + '_base.jpg')
        if not os.path.exists(f):
            u = fal('fal-ai/flux-2/klein/4b', {'prompt': sc, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'})
            CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='copertina concetto costo vero')
            Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').resize((1280, 720), Image.LANCZOS).save(f, quality=95)
        im = Image.open(f).convert('RGBA'); d = ImageDraw.Draw(im)
        if nome == 'pennarello':   # foto vera + annotazioni a pennarello rosso, come uno che ha fatto i conti a mano
            ellisse_mano(d, (730, 230, 1250, 640), (230, 20, 30), 9)
            lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            dl.rectangle((30, 40, 560, 210), fill=(255, 235, 60, 170))   # evidenziatore
            im.alpha_composite(lay); d = ImageDraw.Draw(im)
            d.text((50, 30), '35.000 €', font=F(FM, 120), fill=INK)
            tratto(d, [(45, 150), (540, 90)], (230, 20, 30), 12)
            d.text((40, 250), '60.500 €', font=F(FM, 150), fill=(230, 20, 30), stroke_width=4, stroke_fill=BI)
            d.text((60, 470), 'in 10 anni!', font=F(FM, 70), fill=BI, stroke_width=5, stroke_fill=INK)
        elif nome == 'noir':   # buio, un solo faro, cifra in oro: elegante e "da documentario"
            lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            for k in range(60):
                dl.rectangle((0, 0, 620 - k * 4, 720), fill=(0, 0, 0, 3))
            im.alpha_composite(lay); d = ImageDraw.Draw(im)
            ORO = (232, 190, 95)
            d.text((60, 70), 'IL VERO PREZZO DI', font=F(FMONO, 36), fill=(220, 220, 220))
            d.text((60, 115), 'UNA PISCINA', font=F(FA, 96), fill=BI)
            d.text((52, 270), '60.500€', font=F(FS, 190), fill=ORO)
            d.line((62, 500, 520, 500), fill=ORO, width=3)
            d.text((60, 520), 'NON 35.000', font=F(FMONO, 44), fill=(200, 200, 200))
        else:   # progetto tecnico con le voci di costo come quote del disegno
            AZ = (235, 245, 255)
            voci = [('COPERTURA', '4.000 €', (1000, 200)), ('SCAVO E VASCA', '35.000 €', (820, 320)), ('POMPA E FILTRI', '13.000 €', (980, 430)), ('PRODOTTI', '6.000 €', (860, 520))]
            ys = [150, 250, 350, 450]
            for (n_, v_, p_), y in zip(voci, ys):
                d.line((330, y + 30, p_[0], p_[1]), fill=AZ, width=2); d.ellipse((p_[0] - 7, p_[1] - 7, p_[0] + 7, p_[1] + 7), outline=AZ, width=3)
                d.text((40, y), n_, font=F(FMONO, 26), fill=AZ)
                d.text((40, y + 30), v_, font=F(FA, 50), fill=BI)
            lay = Image.new('RGBA', (560, 170), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            dl.rounded_rectangle((8, 8, 552, 162), 10, outline=(230, 40, 50), width=8)
            dl.text((280, 52), 'COSTO VERO', font=F(FMONO, 34), fill=(230, 40, 50), anchor='mm')
            dl.text((280, 112), '60.500 €', font=F(FA, 80), fill=(230, 40, 50), anchor='mm')
            lay = lay.rotate(8, expand=True, resample=Image.BICUBIC)
            im.alpha_composite(lay, (20, 455))
            d.text((40, 40), 'PISCINA', font=F(FA, 84), fill=BI)
        im.convert('RGB').save(os.path.join(OUT, nome + '.jpg'), quality=94)
        print('FATTO', nome, flush=True)


if __name__ == '__main__':
    main()
