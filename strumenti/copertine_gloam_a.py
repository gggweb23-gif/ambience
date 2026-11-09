#!/usr/bin/env python3
"""Copertine stile ORIGINALE GLOAM (9 nov, Giorgio) adattate ai prossimi 3 video: Knight Capital, Barings, FTX.
Come Binance: figure 3D lucide senza volto, ROSSO = chi causa il disastro, BLU = chi lo subisce, oggetto d'oro con il nome dell'azienda,
etichette a fumetto sopra ogni figura, fondo scuro con particelle d'oro. Impaginazione diversa per ogni video (MANO LIBERA).
Immagini FLUX.2 Klein 4B (circa 0,01 $ l'una); scritte in codice, mai sovrapposte, leggibili da telefono. Uscita: prove_video/Copertine_Gloam/A1..A3"""
import os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import copertine_gloam as CG

OUT = CG.OUT; W, H = CG.W, CG.H
F = CG.F
ROSSO, BLU, ORO = (220, 30, 40), (30, 90, 230), (245, 196, 50)

VIDEO = [
    {'nome': 'A1_knight_capital', 'oggetto': 'KNIGHT', 'prompt':
     'LEFT third: a glossy RED faceless mannequin furiously typing on a trading terminal, streams of glowing gold coins shooting out of the screen. '
     'MIDDLE third: two glossy BLUE faceless mannequin traders standing behind, hands raised in front of a wall of red falling charts. '
     'RIGHT third: a giant glossy GOLD stopwatch standing on the floor, coins pouring out of it onto the ground. Three groups clearly separated, empty dark space above each.',
     'etichette': [('ALGORITHM', ROSSO, .18), ('TRADERS', BLU, .50)], 'targa': (.83, .40)},
    {'nome': 'A2_barings', 'oggetto': 'BARINGS', 'prompt':
     'LEFT third: a glossy RED faceless mannequin trader sitting at a small desk with a laptop. MIDDLE third: a glossy BLUE faceless mannequin manager standing with arms crossed, '
     'unaware. RIGHT third: a huge glossy GOLD classic bank vault with its door open, gold coins and banknotes flying out toward the red trader. '
     'Three subjects clearly separated, empty dark space above each.',
     'etichette': [('ROGUE TRADER', ROSSO, .17), ('THE BANK', BLU, .47)], 'targa': (.82, .42)},
    {'nome': 'A3_ftx', 'oggetto': 'FTX', 'prompt':
     'RIGHT third: a glossy RED faceless mannequin walking away carrying a big sack overflowing with gold coins. MIDDLE third: a small crowd of glossy BLUE faceless '
     'mannequins looking at an empty space. LEFT third: a glossy GOLD treasure chest, open and completely EMPTY, a few coins on the floor. '
     'Three groups clearly separated, empty dark space above each.',
     'etichette': [('FOUNDER', ROSSO, .82), ('CUSTOMERS', BLU, .50)], 'targa': (.17, .45)},
]


def etichetta_centrata(im, cx, y, testo, col):
    """Etichetta a fumetto centrata su cx; il carattere si rimpicciolisce per stare nel suo terzo (mai sovrapposta alle altre)."""
    size = 66
    while F(size).getlength(testo) + 44 > W * .30 and size > 34:
        size -= 2
    w = F(size).getlength(testo) + 44; x = max(16, min(W - w - 16, cx * W - w / 2))
    CG.etichetta(im, int(x), y, testo, col, size)


def targa(im, cx, cy, testo):
    d = ImageDraw.Draw(im); f = F(54); w = f.getlength(testo) + 50; x = cx * W - w / 2; y = cy * H
    d.rectangle((x, y, x + w, y + 80), fill=ORO, outline=(120, 90, 20), width=4)
    d.text((x + w / 2, y + 40), testo, font=f, fill=(40, 30, 10), anchor='mm')


def main():
    ims = []
    for v in VIDEO:
        im = CG.klein(CG.STILE + v['prompt'])
        for k, (t, col, cx) in enumerate(v['etichette']):
            etichetta_centrata(im, cx, 70 + k * 18, t, col)
        targa(im, *v['targa'], v['oggetto'])
        im.save(os.path.join(OUT, v['nome'] + '.jpg'), quality=92); ims.append(im)
    g = Image.new('RGB', (W, H * 3 + 40), 'white')
    for k, im in enumerate(ims):
        g.paste(im, (0, k * (H + 20)))
    g.resize((W // 2, (H * 3 + 40) // 2)).save(os.path.join(OUT, 'A_prossimi_3.jpg'), quality=90)
    print('FATTO')


if __name__ == '__main__':
    main()
