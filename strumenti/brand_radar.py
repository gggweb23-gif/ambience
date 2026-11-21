#!/usr/bin/env python3
"""BANNER E AVATAR DEI CANALI RADAR (22 nov 2026): sfondo fotografico FLUX.2 Klein (~0,01-0,02 $), scritte in codice (Anton),
tutto l'importante nella fascia sicura centrale 1546x423 (si vede anche da telefono). Uscita: prove_video/brand/<chiave>/"""
import io, json, os, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('CANALE', 'africaregions')
import prova_radar as R

ROOT = R.ROOT
A = os.path.join(ROOT, 'ctr_test', 'Anton.ttf'); AB = os.path.join(ROOT, 'fonts_costo_vero', 'ArchivoBlack-Regular.ttf')
B = {
 'hidden_america': {'nome': ['HIDDEN AMERICA', 'DOCS'], 'motto': 'THE AMERICA YOU NEVER KNEW', 'col': (200, 30, 40), 'testo2': (255, 255, 255),
   'sfondo': 'Ultra wide cinematic panoramic photograph of iconic American wilderness: a snowy Alaska mountain range on the left, a red desert canyon in the middle, a lonely highway through Monument Valley on the right, golden hour light, epic, sharp, no text',
   'avatar': 'Flat vector icon: the silhouette of the map of the United States in white, a big red location pin on it, dark navy blue background, clean, centered, no text'},
 'lost_decades': {'nome': ['LOST', 'DECADES'], 'motto': 'THE AMERICA WE LEFT BEHIND', 'col': (196, 18, 24), 'testo2': (255, 255, 255),
   'sfondo': 'Ultra wide nostalgic photograph of a 1950s American main street: a chrome diner with neon sign, classic 1950s cars parked, people in 1950s clothes, warm faded Kodachrome colors, film grain, no readable text',
   'avatar': None},
 'dollar_years': {'nome': ['THE DOLLAR', 'YEARS'], 'motto': 'HOW ORDINARY FAMILIES GOT THROUGH', 'col': (120, 84, 30), 'testo2': (255, 236, 200),
   'sfondo': 'Ultra wide vintage sepia photograph of a 1930s Great Depression American small town: a general store, an old farm truck, a family on a dusty road, sepia tones, film grain, documentary photo, no readable text',
   'avatar': None},
}


def klein(prompt, w, h):
    hd = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
    inv = R.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': w, 'height': h}, 'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
    for _ in range(90):
        time.sleep(2)
        if R.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    return Image.open(io.BytesIO(R.http(R.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url'], raw=True))).convert('RGB')


def fit(d, t, path, w, s):
    while s > 20 and d.textlength(t, font=ImageFont.truetype(path, s)) > w:
        s -= 4
    return ImageFont.truetype(path, s)


for k, b in B.items():
    out = os.path.join(ROOT, 'prove_video', 'brand', k); os.makedirs(out, exist_ok=True)
    im = klein(b['sfondo'], 2048, 1152).resize((2560, 1440), Image.LANCZOS)
    sc = Image.new('RGBA', im.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(sc)
    for y in range(1440):
        ds.line((0, y, 2560, y), fill=(0, 0, 0, int(max(0, 150 - abs(y - 720) * .45))))
    im = Image.alpha_composite(im.convert('RGBA'), sc).convert('RGB'); d = ImageDraw.Draw(im)
    cx = 1280
    f1 = fit(d, b['nome'][0], A, 1300, 190)
    d.text((cx, 640), b['nome'][0], font=f1, fill='white', anchor='mm', stroke_width=8, stroke_fill='black')
    f2 = ImageFont.truetype(A, 120); tw = d.textlength(b['nome'][1], font=f2)
    d.rectangle((cx - tw / 2 - 40, 712, cx + tw / 2 + 40, 832), fill=b['col'])
    d.text((cx, 772), b['nome'][1], font=f2, fill=b['testo2'], anchor='mm')
    f3 = ImageFont.truetype(AB, 34)
    d.text((cx, 870), b['motto'], font=f3, fill=(255, 214, 0), anchor='mm', stroke_width=4, stroke_fill='black')
    im.save(os.path.join(out, 'banner.jpg'), quality=93)
    # avatar
    if b['avatar']:
        av = klein(b['avatar'], 1024, 1024).resize((800, 800), Image.LANCZOS)
    else:
        av = im.crop((cx - 380, 330, cx + 380, 1090)).resize((800, 800), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))
        av = Image.blend(av, Image.new('RGB', av.size, (15, 12, 10)), .45); da = ImageDraw.Draw(av)
        da.ellipse((40, 40, 760, 760), outline=b['col'], width=26)
        w1, w2 = b['nome'][0].split()[-1] if len(b['nome'][0].split()) > 1 else b['nome'][0], b['nome'][1]
        da.text((400, 330), w1, font=fit(da, w1, A, 560, 200), fill='white', anchor='mm', stroke_width=6, stroke_fill='black')
        f = ImageFont.truetype(A, 150); tw = da.textlength(w2, font=f)
        da.rectangle((400 - tw / 2 - 30, 420, 400 + tw / 2 + 30, 580), fill=b['col'])
        da.text((400, 500), w2, font=f, fill=b['testo2'], anchor='mm')
    av.save(os.path.join(out, 'avatar.png'))
    print('ok', k)
