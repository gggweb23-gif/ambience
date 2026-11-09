#!/usr/bin/env python3
"""Copertina stile B (dossier) con un GANCIO di curiosita' (9 nov, Giorgio: "un riferimento a un nome o altro che l'utente voglia saperne di piu'").
3 varianti sul video Barings: 1 = scheda "SUSPECT: NICK LEESON"; 2 = "ACCOUNT 88888" cerchiato; 3 = "THE QUEEN'S BANK" + timbro.
Fondo: foto Pexels di Londra di notte (gratis), tutto il resto disegnato in codice. Uscita: prove_video/Copertine_Gloam/B1..B3 + B_varianti.jpg"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam4 as G4

OUT = 'prove_video/Copertine_Gloam'; os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
SERIF, MONO, MB = G4.SERIF, G4.MONO, 'fonts_gloam/montserrat_black.woff'
CREMA, ROSSO, INCH, CARTA = (245, 240, 228), (190, 30, 30), (28, 26, 24), (232, 224, 203)


def base(foto):
    b = ImageOps.fit(foto, (W, H)).filter(ImageFilter.GaussianBlur(2))
    b = Image.blend(b, Image.new('RGB', (W, H), (10, 10, 12)), .45).convert('RGBA')
    d = ImageDraw.Draw(b)
    d.text((55, 165), '£827M', font=ImageFont.truetype(SERIF, 230), fill=CREMA)
    d.rectangle((65, 445, 740, 457), fill=ROSSO)
    return b


def carta(w, h, ang):
    c = G4.carta(w, h, 7).convert('RGBA')
    return c, ang


def v1(foto):   # scheda sospettato
    b = base(foto)
    c = G4.carta(430, 520, 3).convert('RGBA'); d = ImageDraw.Draw(c)
    d.text((28, 22), 'SUSPECT', font=ImageFont.truetype(MONO, 30), fill=(90, 80, 65))
    d.rectangle((28, 70, 228, 330), fill=(55, 57, 62))
    d.ellipse((78, 105, 178, 205), fill=(22, 22, 25)); d.rounded_rectangle((48, 200, 208, 340), 60, fill=(22, 22, 25))
    d.text((128, 150), '?', font=ImageFont.truetype(SERIF, 60), fill=(80, 80, 85), anchor='mm')
    d.text((28, 350), 'NICK', font=ImageFont.truetype(MB, 62), fill=INCH)
    d.text((28, 420), 'LEESON', font=ImageFont.truetype(MB, 62), fill=ROSSO)
    G4.ombra_incolla(b, c, 1010, 330, ang=-4)
    return b


def v2(foto):   # conto segreto 88888
    b = base(foto)
    c = G4.carta(500, 230, 4).convert('RGBA'); d = ImageDraw.Draw(c)
    d.text((30, 25), 'ERROR ACCOUNT', font=ImageFont.truetype(MONO, 30), fill=(90, 80, 65))
    d.text((30, 75), '88888', font=ImageFont.truetype(MB, 110), fill=INCH)
    G4.ombra_incolla(b, c, 1000, 520, ang=3)
    d = ImageDraw.Draw(b)
    d.ellipse((720, 425, 1270, 625), outline=ROSSO, width=10)
    d.text((780, 110), 'HIDDEN', font=ImageFont.truetype(MB, 92), fill=ROSSO)
    d.text((780, 210), 'FOR 3 YEARS', font=ImageFont.truetype(MB, 62), fill=CREMA)
    return b


def v3(foto):   # la banca della regina
    b = base(foto)
    s = G4.carta(560, 120, 5).convert('RGBA'); d = ImageDraw.Draw(s)
    d.text((280, 60), "THE QUEEN'S BANK", font=ImageFont.truetype(MB, 52), fill=INCH, anchor='mm')
    G4.ombra_incolla(b, s, 960, 140, ang=-3)
    G4.ombra_incolla(b, G4.timbro('COLLAPSED').resize((470, 160)), 960, 560, ang=0)
    return b


def main():
    foto = G4.foto_pexels('london skyline night', 0).convert('RGB')
    ims = []
    for k, f in enumerate((v1, v2, v3), 1):
        im = f(foto).convert('RGB'); im.save(os.path.join(OUT, f'B{k}.jpg'), quality=92); ims.append(im)
    g = Image.new('RGB', (W, H * 3 + 40), 'white')
    for k, im in enumerate(ims):
        g.paste(im, (0, k * (H + 20)))
    g.resize((W // 2, (H * 3 + 40) // 2)).save(os.path.join(OUT, 'B_varianti.jpg'), quality=90)
    print('FATTO')


if __name__ == '__main__':
    main()
