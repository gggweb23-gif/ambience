#!/usr/bin/env python3
"""BANNER E AVATAR DI UN CANALE nello stile dei video notizie (16 nov 2026, War Room Explained).
Stesso motore delle notizie: caricature vere (libreria caricature/, si pagano una volta), scena a cartone Seedream, scritte Anton.
Banner 2560x1440 con tutto l'importante nella fascia sicura centrale (1546x423: e' l'unica parte che si vede da telefono e in alto su computer),
avatar 800x800 tondo. Env: BRAND (json in brand/), FAL_KEY, ANTHROPIC_API_KEY. Uscita: prove_video/brand/<nome>/ (~0,10-0,30 $)."""
import os, sys
os.environ['NOTIZIA'] = os.environ.get('BRAND') or 'brand/war_room.json'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import video_notizie as V
from PIL import Image, ImageDraw

B = V.N; OUT = os.path.join(V.ROOT, 'prove_video', 'brand', B['nome']); os.makedirs(OUT, exist_ok=True)
SX0, SY0, SX1, SY1 = (2560 - 1546) // 2, (1440 - 423) // 2, (2560 + 1546) // 2, (1440 + 423) // 2   # fascia sicura


def busto(chi, posa, alt):
    png = V.posa(chi, posa)
    p = Image.open(png).convert('RGBA')
    p = p.crop((0, 0, p.width, int(p.height * .42)))   # mezzo busto: testa e spalle
    return p.resize((int(p.width * alt / p.height), alt), Image.LANCZOS)


def banner():
    b = B['banner']
    B.setdefault('sets', {})['banner'] = {'descr': b['sfondo']}
    im = Image.open(V.sfondo('banner')).convert('RGBA').resize((2560, 1440), Image.LANCZOS)
    scuro = Image.new('RGBA', im.size, (8, 12, 24, 0)); d = ImageDraw.Draw(scuro)
    for y in range(1440):   # fascia centrale un po' piu' scura: le scritte si leggono sempre
        a = max(0, 150 - abs(y - 720) * .35); d.line((0, y, 2560, y), fill=(8, 12, 24, int(a)))
    im.alpha_composite(scuro)
    alt = SY1 - SY0 - 10
    sx = busto(*b['sinistra'], alt); im.alpha_composite(sx, (SX0 + 20, SY1 - alt))
    dx = [busto(c, p, alt if i == 0 else int(alt * .9)) for i, (c, p) in enumerate(b['destra'])]
    x_primo = SX1 - 20 - dx[0].width; x = x_primo
    for p in dx[1:]:   # gli altri dietro, un po' a sinistra
        x -= int(p.width * .62); im.alpha_composite(p, (x, SY1 - p.height))
    im.alpha_composite(dx[0], (x_primo, SY1 - dx[0].height))
    # nome del canale al centro, su due righe (la seconda nel riquadro rosso) + motto
    d = ImageDraw.Draw(im); r1, r2 = B['nome_canale']; xl, xr = SX0 + 20 + sx.width + 30, x - 30; cx = (xl + xr) // 2; larg = xr - xl
    f1 = V.font(V.F_TITOLI, 200)
    while max(f1.getbbox(r1)[2], f1.getbbox(r2)[2] + 50) > larg and f1.size > 60:
        f1 = V.font(V.F_TITOLI, f1.size - 4)
    f2 = V.font(V.F_TESTI, 46)
    while f2.getbbox(B['motto'])[2] > larg and f2.size > 24:
        f2 = V.font(V.F_TESTI, f2.size - 2)
    h1 = f1.size * 1.02; tot = h1 * 2 + 30 + f2.size; y = (SY0 + SY1) / 2 - tot / 2 + h1 / 2
    V.testo_box(d, (cx, y), r1, f1, V.BIANCO, stroke=10, sfill=V.NERO, anchor='mm')
    y += h1 + 8; bb = f1.getbbox(r2, anchor='mm')
    d.rectangle((cx + bb[0] - 26, y + bb[1] - 14, cx + bb[2] + 26, y + bb[3] + 14), fill=V.ROSSO + (255,))
    V.testo_box(d, (cx, y), r2, f1, V.BIANCO, anchor='mm')
    V.testo_box(d, (cx, y + h1 / 2 + 30 + f2.size / 2), B['motto'], f2, V.GIALLO, stroke=5, sfill=V.NERO, anchor='mm')
    im.convert('RGB').save(os.path.join(OUT, 'banner.jpg'), quality=94)
    prova = im.copy(); dp = ImageDraw.Draw(prova); dp.rectangle((SX0, SY0, SX1, SY1), outline=(0, 255, 0, 255), width=6)
    prova.convert('RGB').resize((1280, 720)).save(os.path.join(OUT, 'banner_zona_sicura.jpg'), quality=88)
    im.crop((SX0, SY0, SX1, SY1)).convert('RGB').save(os.path.join(OUT, 'banner_come_da_telefono.jpg'), quality=90)


def avatar():
    for k in range(3):
        r = V.fal('fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': V.STILE + B['avatar'] + '. ' + V.NO_TESTO, 'image_size': {'width': 2048, 'height': 2048}, 'num_images': 1}, 0.04)
        im = Image.open(V.io.BytesIO(V.http(r['images'][0]['url'], raw=True, timeout=180))).convert('RGB')
        if k < 2 and V.haiku_immagine(im, 'Answer SI if this logo icon has any readable text, letters or deformed shapes, otherwise NO.').startswith('SI'):
            continue
        break
    im = im.resize((800, 800), Image.LANCZOS)
    m = Image.new('L', (800, 800), 0); ImageDraw.Draw(m).ellipse((0, 0, 799, 799), fill=255)
    im.save(os.path.join(OUT, 'avatar.png'))
    tondo = Image.new('RGBA', (800, 800), (0, 0, 0, 0)); tondo.paste(im, (0, 0), m); tondo.save(os.path.join(OUT, 'avatar_tondo_anteprima.png'))


if __name__ == '__main__':
    if (os.environ.get('SOLO_AVATAR') or 'NO') != 'SI':
        banner()
    if (os.environ.get('SOLO_BANNER') or 'NO') != 'SI':
        avatar()
    V.log(f'banner e avatar pronti in {OUT}, spesa {V.CO.totale():.3f} $')
