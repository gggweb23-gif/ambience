#!/usr/bin/env python3
"""3 STILI DI COPERTINA per il canale "Quanto costa DAVVERO" (9 nov, Giorgio: colpire, immagini grandi, scritte ben visibili da telefono, MANO LIBERA).
Sui primi 3 titoli: SUV da 45.000 EUR, cane in 12 anni, casa da 200.000 EUR col mutuo. Numeri di esempio (nel video vero arrivano dal copione).
Stile 1 CARTELLINO: oggetto enorme + cartellino col prezzo barrato e il costo vero.
Stile 2 FACCIA: protagonista stupito in primo piano + cifra enorme.
Stile 3 SCONTRINO: scontrino lungo che esce dall'immagine con il TOTALE in rosso.
MANO LIBERA: lato del soggetto, colori e posizione delle scritte cambiano da una copertina all'altra.
Immagini FLUX.2 Klein 4B illustrate (circa 0,01 $ l'una, 6 immagini). Uscita: prove_video/Copertine_Possesso/"""
import io, os, sys, time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3

E = os.environ.get
OUT = 'prove_video/Copertine_Possesso'; os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
MB = 'fonts_gloam/montserrat_black.woff'
F = lambda s: ImageFont.truetype(MB, s)
ROSSO, GIALLO, BIANCO, NERO, VERDE = (225, 35, 45), (255, 210, 40), (255, 255, 255), (20, 20, 25), (30, 170, 90)
STILE = ('DIGITAL PAINTED ILLUSTRATION, warm editorial style, bold and bright, high contrast, ordinary Italian middle class, '
         'no text, no letters, no numbers, no logos, no brand. ')
TITOLI = [
    {'t': 'SUV', 'prezzo': '45.000 €', 'vero': '52.300 €', 'mese': '872 €/MESE',
     'oggetto': 'a big shiny new mid-size family SUV seen from the side, generic and unbranded, filling the frame, simple warm gradient background',
     'faccia': 'close-up portrait of a shocked Italian man in his 30s with wide eyes and open mouth, holding car keys, simple warm background'},
    {'t': 'CANE', 'prezzo': '800 €', 'vero': '18.000 €', 'mese': '125 €/MESE',
     'oggetto': 'a big adorable golden retriever dog sitting and looking at the viewer, filling the frame, simple warm gradient background',
     'faccia': 'close-up portrait of a shocked Italian woman in her 30s with wide eyes, hugging a golden retriever puppy, simple warm background'},
    {'t': 'CASA', 'prezzo': '200.000 €', 'vero': '318.000 €', 'mese': '880 €/MESE',
     'oggetto': 'a nice ordinary Italian two-storey house with a small garden, filling the frame, sunny sky, simple composition',
     'faccia': 'close-up portrait of a shocked Italian couple in their 30s holding house keys, wide eyes, simple warm background'},
]


def klein(p):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = G3.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': STILE + p, 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'}, hd)
    for _ in range(100):
        time.sleep(2)
        if G3.http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = G3.http(inv['response_url'], headers=hd)['images'][0]['url']
    return Image.open(io.BytesIO(G3.http(u, raw=True))).convert('RGB').resize((W, H))


def scritta_bordo(d, xy, t, size, fill, bordo=NERO, sw=10, anchor='la'):
    d.text(xy, t, font=F(size), fill=fill, stroke_width=sw, stroke_fill=bordo, anchor=anchor)


def adatta(t, size, maxw):
    while F(size).getlength(t) > maxw and size > 30:
        size -= 4
    return size


def stile_cartellino(img, v, k):
    im = img.copy(); d = ImageDraw.Draw(im)
    sx = k % 2 == 0   # MANO LIBERA: cartellino a sinistra o a destra
    x0 = 40 if sx else W - 560
    d.rounded_rectangle((x0, 60, x0 + 520, 300), 30, fill=BIANCO, outline=NERO, width=8)
    s = adatta(v['prezzo'], 110, 440); d.text((x0 + 260, 180), v['prezzo'], font=F(s), fill=NERO, anchor='mm')
    d.line((x0 + 30, 220, x0 + 490, 140), fill=ROSSO, width=16)
    s = adatta(v['vero'], 150, 600)
    scritta_bordo(d, (x0 + (0 if sx else -80), 330), v['vero'], s, GIALLO)
    scritta_bordo(d, (x0 + (0 if sx else -80), 330 + s + 20), 'DAVVERO?', 90, BIANCO)
    return im


def stile_faccia(img, v, k):
    im = img.copy(); d = ImageDraw.Draw(im)
    alto = k % 2 == 1   # MANO LIBERA: cifra in alto o in basso
    s = adatta(v['mese'], 140, 700)
    y = 50 if alto else H - s - 70
    box = (30, y - 10, 30 + F(s).getlength(v['mese']) + 50, y + s + 30)
    d.rectangle(box, fill=ROSSO)
    d.text((55, y), v['mese'], font=F(s), fill=BIANCO)
    scritta_bordo(d, (55, (y + s + 50) if alto else (y - 110)), 'IL ' + v['t'] + '?' if v['t'] != 'CASA' else 'LA CASA?', 80, GIALLO)
    return im


def stile_scontrino(img, v, k):
    im = img.copy().convert('RGBA')
    dx = k % 2 == 1   # MANO LIBERA: scontrino a destra o a sinistra
    sc = Image.new('RGBA', (420, 760), (250, 248, 240, 255)); d = ImageDraw.Draw(sc)
    for i in range(0, 420, 20):   # bordo strappato in alto
        d.polygon([(i, 0), (i + 10, 14), (i + 20, 0)], fill=(0, 0, 0, 0))
    d.text((210, 70), 'SCONTRINO', font=F(44), fill=NERO, anchor='mm')
    for j in range(5):
        d.line((40, 140 + j * 70, 380, 140 + j * 70), fill=(200, 200, 200), width=4)
        d.rectangle((40, 115 + j * 70, 40 + 120 + (j * 37) % 120, 130 + j * 70), fill=(150, 150, 150))
    d.text((210, 520), 'TOTALE', font=F(54), fill=NERO, anchor='mm')
    s = adatta(v['vero'], 90, 380); d.text((210, 610), v['vero'], font=F(s), fill=ROSSO, anchor='mm')
    sc = sc.rotate(-6 if dx else 6, expand=True, resample=Image.BICUBIC)
    ombra = Image.new('RGBA', sc.size, (0, 0, 0, 0)); ombra.putalpha(sc.split()[3].point(lambda a: int(a * .5)))
    x = W - sc.width + 30 if dx else -30
    im.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(14)), (x + 14, 10)); im.alpha_composite(sc, (x, -10))
    d = ImageDraw.Draw(im)
    tx = 60 if dx else W - 60
    scritta_bordo(d, (tx, H - 230), 'QUANTO', 96, BIANCO, anchor='la' if dx else 'ra')
    scritta_bordo(d, (tx, H - 130), 'COSTA?', 96, GIALLO, anchor='la' if dx else 'ra')
    return im.convert('RGB')


def main():
    righe = []
    for k, v in enumerate(TITOLI):
        ogg = klein(v['oggetto']); fac = klein(v['faccia'])
        a, b, c = stile_cartellino(ogg, v, k), stile_faccia(fac, v, k), stile_scontrino(ogg, v, k)
        for n, im in zip('123', (a, b, c)):
            im.save(os.path.join(OUT, f'{v["t"].lower()}_stile{n}.jpg'), quality=92)
        righe.append((a, b, c))
    w, h = 560, 315; g = Image.new('RGB', (w * 3 + 40, 70 + 3 * (h + 60)), 'white'); d = ImageDraw.Draw(g)
    for j, t in enumerate(['1 - CARTELLINO', '2 - FACCIA + CIFRA', '3 - SCONTRINO']):
        d.text((j * (w + 20) + w // 2, 35), t, font=F(30), fill=NERO, anchor='mm')
    nomi = ['Quanto costa DAVVERO un SUV da 45.000 €?', 'Quanto costa DAVVERO un cane in 12 anni?', 'Quanto costa DAVVERO una casa da 200.000 € con il mutuo?']
    for i, r in enumerate(righe):
        y = 70 + i * (h + 60); d.text((10, y + 8), nomi[i], font=F(24), fill=(60, 60, 60))
        for j, im in enumerate(r):
            g.paste(im.resize((w, h)), (j * (w + 20), y + 45))
    g.save(os.path.join(OUT, 'confronto_3_stili.jpg'), quality=90)
    print('FATTO')


if __name__ == '__main__':
    main()
