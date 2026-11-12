#!/usr/bin/env python3
"""Billion Ruin: copertina "dei soldi" (stile B dossier, scelta di Giorgio del 12 nov), legata al racconto del video. Gratis (foto Pexels + disegno in codice).
Ingresso (env): CIFRA ("$42B"), SOTTO ("GONE IN 1 DAY"), SCHEDA_SU ("BANK RUN"), SCHEDA_1 ("SILICON"), SCHEDA_2 ("VALLEY BANK"), TIMBRO ("CLOSED"),
FOTO (ricerca Pexels in inglese), OUT (cartella), LATO (sx = cifra a sinistra, dx = cifra a destra: MANO LIBERA, impaginazione diversa da un video all'altro).
Esce OUT/soldi_1.jpg e OUT/soldi_2.jpg (due foto di fondo diverse). Niente scritte nell'angolo in basso a destra (durata del video)."""
import os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam4 as G4

E = os.environ.get
W, H = 1280, 720
SERIF, MONO, MB = G4.SERIF, G4.MONO, 'fonts_gloam/montserrat_black.woff'
CREMA, ROSSO, INCH = (245, 240, 228), (190, 30, 30), (28, 26, 24)
F = ImageFont.truetype


def adatta(path, t, size, maxw):
    while size > 20 and F(path, size).getlength(t) > maxw:
        size -= 4
    return F(path, size)


def crea(foto):
    dx = str(E('LATO') or 'sx').lower() == 'dx'
    b = ImageOps.fit(foto, (W, H)).filter(ImageFilter.GaussianBlur(2))
    b = Image.blend(b, Image.new('RGB', (W, H), (10, 10, 12)), .5).convert('RGBA')
    d = ImageDraw.Draw(b)
    cif, sotto = E('CIFRA', '$42B'), E('SOTTO', '')
    x0 = 660 if dx else 50
    f = adatta(SERIF, cif, 260, 640)
    d.text((x0, 120), cif, font=f, fill=CREMA)
    bb = d.textbbox((x0, 120), cif, font=f)
    d.rectangle((x0 + 8, bb[3] + 30, bb[2], bb[3] + 44), fill=ROSSO)
    if sotto:
        d.text((x0 + 8, bb[3] + 62), sotto, font=adatta(MB, sotto, 64, 600), fill=CREMA)
    # scheda di carta dall'altro lato, alta (lontana dalla durata in basso a destra)
    c = G4.carta(440, 400, 5).convert('RGBA'); dc = ImageDraw.Draw(c)
    dc.text((30, 26), E('SCHEDA_SU', ''), font=F(MONO, 32), fill=(90, 80, 65))
    dc.text((30, 100), E('SCHEDA_1', ''), font=adatta(MB, E('SCHEDA_1', ''), 78, 380), fill=INCH)
    dc.text((30, 195), E('SCHEDA_2', ''), font=adatta(MB, E('SCHEDA_2', ''), 78, 380), fill=ROSSO)
    cx = 320 if dx else 975
    G4.ombra_incolla(b, c, cx, 290, ang=4 if dx else -4)
    if E('TIMBRO'):
        G4.ombra_incolla(b, G4.timbro(E('TIMBRO')), cx - 10, 470, ang=0, sc=.85)
    return b.convert('RGB')


def main():
    out = E('OUT', 'prove_video/Copertine_Gloam/soldi'); os.makedirs(out, exist_ok=True)
    for k in (1, 2):
        crea(G4.foto_pexels(E('FOTO', 'bank building night'), k)).save(os.path.join(out, f'soldi_{k}.jpg'), quality=92)
    print('FATTO', out)


if __name__ == '__main__':
    main()
