#!/usr/bin/env python3
"""BANNER: soggetti dentro la FASCIA visibile (9 nov, Giorgio: "abbassa le immagini, vanno fuori dal banner").
Su computer YouTube mostra solo la fascia centrale alta 423 px (y 508-931 su 2560x1440); su telefono solo il centro 1546x423.
Gratis, senza nuove immagini AI: ritaglia i soggetti dai banner gia' generati da kit_canali.py, li rimpicciolisce dentro la fascia
(ai lati, fuori dalle scritte) su uno sfondo disegnato in codice, e riscrive le scritte al centro.
Uso: python3 strumenti/kit_fascia.py <costo_vero_banner_originale.jpg> <en_banner_originale.jpg>"""
import os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = 'prove_video/Kit_Canali'
MB, SERIF, MONO = 'fonts_gloam/montserrat_black.woff', 'fonts_gloam/serif.woff', 'fonts_gloam/mono.woff'
F = lambda f, s: ImageFont.truetype(f, s)
Y0, Y1 = 508, 931           # fascia visibile su computer
NOME_EN = (os.environ.get('NOME_EN') or 'Billion Ruin').upper()


def sfumato(w, h, bordo):
    """maschera con i bordi sfumati, per incollare il ritaglio senza stacchi"""
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rectangle((bordo, bordo, w - bordo, h - bordo), fill=255)
    return m.filter(ImageFilter.GaussianBlur(bordo / 2))


def incolla(im, sorg, box, alt, cx, base_y, bordo=18):
    """ritaglia box da sorg, lo porta all'altezza alt e lo appoggia con la base a base_y, centrato su cx"""
    r = sorg.crop(box); k = alt / r.height; r = r.resize((int(r.width * k), alt), Image.LANCZOS)
    im.paste(r, (int(cx - r.width / 2), base_y - alt), sfumato(r.width, r.height, bordo))


def gradiente(c1, c2):
    g = Image.new('RGB', (1, 1440))
    for y in range(1440):
        t = y / 1439; g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    return g.resize((2560, 1440))


def costo_vero(src):
    """SUV e barca dell'immagine originale sono gia' dentro la fascia: si copre la parte centrale (casa e moto finivano
    dietro le scritte) con un pannello pieno dai bordi sfumati, e si riscrivono le scritte."""
    im = Image.open(src).convert('RGB')
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).rounded_rectangle((498, 500, 2128, 940), 40, fill=255)
    im.paste(Image.new('RGB', im.size, (255, 148, 34)), (0, 0), m.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(im)
    d.text((1280, 625), 'COSTO VERO', font=F(MB, 170), fill=(255, 255, 255), anchor='mm', stroke_width=12, stroke_fill=(20, 20, 25))
    d.text((1280, 785), 'QUANTO COSTA DAVVERO POSSEDERE LE COSE?', font=F(MB, 54), fill=(20, 20, 25), anchor='mm')
    d.text((1280, 870), 'AUTO · CASA · CANE · BARCA · NUOVO VIDEO OGNI GIORNO', font=F(MB, 36), fill=(255, 255, 255), anchor='mm')
    im.save(os.path.join(OUT, 'costo_vero_banner.jpg'), quality=92)


def inglese(src):
    s = Image.open(src).convert('RGB')
    im = Image.new('RGB', (2560, 1440), (10, 10, 12)); v = Image.new('L', (2560, 1440), 0)
    ImageDraw.Draw(v).ellipse((-300, 200, 2860, 1240), fill=255); v = v.filter(ImageFilter.GaussianBlur(220))
    im.paste(Image.new('RGB', (2560, 1440), (36, 36, 41)), (0, 0), v)
    d = ImageDraw.Draw(im); random.seed(7)
    for _ in range(140):   # pulviscolo d'oro come nell'originale
        x, y, r = random.randint(0, 2560), random.randint(470, 970), random.choice((2, 3, 4, 5))
        if 560 < x < 2000 and random.random() < .7:
            continue
        d.ellipse((x - r, y - r, x + r, y + r), fill=(232, 182, 60))
    incolla(im, s, (0, 380, 655, 1195), 405, 330, 925, 26)      # caveau d'oro a sinistra
    incolla(im, s, (1900, 215, 2430, 1200), 405, 2230, 925, 26)  # figura rossa a destra
    d = ImageDraw.Draw(im)
    d.text((1280, 650), NOME_EN, font=F(SERIF, 180), fill=(245, 238, 222), anchor='mm')
    w = F(SERIF, 180).getlength(NOME_EN); d.rectangle((1280 - w / 2, 752, 1280 + w / 2, 764), fill=(225, 35, 45))
    d.text((1280, 835), 'HOW BILLIONS DISAPPEAR · ONE COLLAPSE AT A TIME', font=F(MONO, 38), fill=(220, 214, 200), anchor='mm')
    im.save(os.path.join(OUT, 'en_banner.jpg'), quality=92)


if __name__ == '__main__':
    costo_vero(sys.argv[1]); inglese(sys.argv[2]); print('FATTO')
