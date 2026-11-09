#!/usr/bin/env python3
"""Confronto delle 2 idee di copertina (A = originale Gloam 3D, B = dossier con gancio) sui primi 3 titoli: Knight Capital, Barings, FTX.
Le A sono gia' fatte (copertine_gloam_a.py). Qui si creano le B di Knight e FTX (gratis) e la griglia di confronto. Uscita: prove_video/Copertine_Gloam/confronto_A_B.jpg"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam4 as G4
import copertine_gloam_b as B

OUT = B.OUT; W, H = B.W, B.H


def dossier(foto, numero, scheda, riga1, riga2, sotto=None):
    b = ImageOps.fit(foto, (W, H)).filter(ImageFilter.GaussianBlur(2))
    b = Image.blend(b, Image.new('RGB', (W, H), (10, 10, 12)), .45).convert('RGBA'); d = ImageDraw.Draw(b)
    f = ImageFont.truetype(B.SERIF, 230)
    while f.getlength(numero) > 700:
        f = ImageFont.truetype(B.SERIF, f.size - 10)
    d.text((55, 165), numero, font=f, fill=B.CREMA); d.rectangle((65, 445, 65 + min(700, f.getlength(numero)), 457), fill=B.ROSSO)
    if sotto:
        d.text((65, 480), sotto, font=ImageFont.truetype(B.MONO, 40), fill=(220, 215, 205))
    c = G4.carta(430, 520, 3).convert('RGBA'); cd = ImageDraw.Draw(c)
    cd.text((28, 22), scheda, font=ImageFont.truetype(B.MONO, 30), fill=(90, 80, 65))
    cd.rectangle((28, 70, 228, 330), fill=(55, 57, 62))
    cd.ellipse((78, 105, 178, 205), fill=(22, 22, 25)); cd.rounded_rectangle((48, 200, 208, 340), 60, fill=(22, 22, 25))
    cd.text((128, 150), '?', font=ImageFont.truetype(B.SERIF, 60), fill=(80, 80, 85), anchor='mm')
    for k, (t, col) in enumerate(((riga1, B.INCH), (riga2, B.ROSSO))):
        ff = ImageFont.truetype(B.MB, 62)
        while ff.getlength(t) > 380:
            ff = ImageFont.truetype(B.MB, ff.size - 2)
        cd.text((28, 350 + k * 70), t, font=ff, fill=col)
    G4.ombra_incolla(b, c, 1000, 330, ang=-4)
    return b.convert('RGB')


def main():
    k = dossier(G4.foto_pexels('new york stock exchange night', 1).convert('RGB'), '$440M', 'THE CODE', 'POWER', 'PEG', '45 MINUTES')
    k.save(os.path.join(OUT, 'B_knight.jpg'), quality=92)
    f = dossier(G4.foto_pexels('bahamas night city', 2).convert('RGB'), '$8B', 'SUSPECT', 'SAM', 'BANKMAN-FRIED', 'MISSING')
    f.save(os.path.join(OUT, 'B_ftx.jpg'), quality=92)
    A = [Image.open(os.path.join(OUT, n)) for n in ('A1_knight_capital.jpg', 'A2_barings.jpg', 'A3_ftx.jpg')]
    Bs = [k, Image.open(os.path.join(OUT, 'B1.jpg')), f]
    titoli = ['1. How Knight Capital Lost $440,000,000 in 45 Minutes', '2. How Barings Bank Was Destroyed by One Trader', '3. How FTX Lost $8,000,000,000 in 10 Days']
    w, h = 640, 360; g = Image.new('RGB', (w * 2 + 30, 60 + 3 * (h + 70)), 'white'); d = ImageDraw.Draw(g)
    fh = ImageFont.truetype(B.MB, 30); ft = ImageFont.truetype(B.MB, 24)
    d.text((w // 2, 30), 'A - ORIGINALE GLOAM (3D)', font=fh, fill=(20, 20, 20), anchor='mm')
    d.text((w + 30 + w // 2, 30), 'B - DOSSIER CON GANCIO', font=fh, fill=(20, 20, 20), anchor='mm')
    for i in range(3):
        y = 60 + i * (h + 70)
        d.text((10, y + 8), titoli[i], font=ft, fill=(60, 60, 60))
        g.paste(A[i].resize((w, h)), (0, y + 50)); g.paste(Bs[i].resize((w, h)), (w + 30, y + 50))
    g.save(os.path.join(OUT, 'confronto_A_B.jpg'), quality=90)
    print('FATTO')


if __name__ == '__main__':
    main()
