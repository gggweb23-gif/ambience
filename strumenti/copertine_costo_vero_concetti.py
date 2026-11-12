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
STILE = 'Bold glossy 3D-illustration look like a top YouTube thumbnail, saturated colors, sharp details, high contrast. NO text, NO letters, NO numbers, NO logos. '
CONCETTI = {
    'iceberg': 'Cutaway view split by the water line of the sea: ABOVE the water a small pretty backyard swimming pool with blue water and a sun lounger sits like the tip of an iceberg; '
               'BELOW the water line an ENORMOUS iceberg made of tightly stacked green euro banknotes goes deep down into dark blue water. Composition: pool and tip in the upper RIGHT, '
               'the huge underwater mass fills the lower half; the LEFT third of the image is clean sea and sky.',
    'scontrino': 'A sunny backyard with a blue in-ground swimming pool on the RIGHT side; an EXTREMELY long white paper shopping receipt comes out of the pool water and unrolls '
                 'in big curls across the green lawn toward the viewer, blank receipt paper with faint grey lines only. The LEFT third of the image is clear blue sky and lawn.',
    'soldi': 'A backyard in-ground swimming pool on the RIGHT side completely FILLED with green euro banknotes instead of water, banknotes overflowing on the edge, a pool ladder '
             'going into the money, sunny Italian garden, dramatic low angle. The LEFT third of the image is clear sky and hedge.',
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


def main():
    for nome, sc in CONCETTI.items():
        f = os.path.join(OUT, nome + '_base.jpg')
        if not os.path.exists(f):
            u = fal('fal-ai/flux-2/klein/4b', {'prompt': STILE + sc, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'})
            CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='copertina concetto costo vero')
            Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').resize((1280, 720), Image.LANCZOS).save(f, quality=95)
        im = Image.open(f).convert('RGBA'); d = ImageDraw.Draw(im)
        # le scritte stanno nel terzo di SINISTRA (libero per costruzione), mai in basso a destra
        if nome == 'iceberg':
            etichetta(im, (34, 40), 'PREZZO', FB, 40, INK, Y + (255,), ang=0)
            barrato(im, (40, 110), '35.000 €', 120)
            etichetta(im, (34, 300), 'COSTO VERO', FB, 40, BI, R + (255,))
            d.text((40, 370), '60.500 €', font=F(FA, 170), fill=R, stroke_width=9, stroke_fill=BI)
        elif nome == 'scontrino':
            etichetta(im, (34, 40), 'PISCINA', FA, 92, INK, Y + (255,), ang=-3)
            d.text((40, 230), '60.500 €', font=F(FA, 180), fill=R, stroke_width=10, stroke_fill=BI)
            etichetta(im, (44, 470), 'IN 10 ANNI', FB, 52, BI, INK + (255,), ang=2)
        else:
            barrato(im, (40, 50), '35.000 €', 110)
            d.text((40, 200), '60.500 €', font=F(FA, 190), fill=Y, stroke_width=11, stroke_fill=INK)
            etichetta(im, (44, 460), 'IL VERO PREZZO', FB, 50, BI, R + (255,), ang=-2)
        im.convert('RGB').save(os.path.join(OUT, nome + '.jpg'), quality=94)
        print('FATTO', nome, flush=True)


if __name__ == '__main__':
    main()
