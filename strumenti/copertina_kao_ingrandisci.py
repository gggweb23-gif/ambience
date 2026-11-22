#!/usr/bin/env python3
"""22 nov (Giorgio): scritta della copertina KAO piu' grande, leggibile da mobile (come "NE HANNO PASSATE TROPPE").
Prende la copertina gia' fatta (URL), trova il cartoncino bianco della scritta, lo copre con un cartoncino nuovo piu' grande
nello stesso stile (magenta su bianco, bordo nero, ombra) e la frase al massimo della grandezza possibile.
Mai sopra il personaggio: il cartoncino resta dal suo lato, fino a LIMITE (frazione della larghezza).
Uso: URL=... FRASE="NON E' QUELLO CHE CREDI" OUT=kao_copertine/piatto/ID.jpg LATO=sinistra LIMITE=0.50 python3 strumenti/copertina_kao_ingrandisci.py"""
import io, os, unicodedata, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

E = os.environ.get
MAG = (236, 0, 214)
FONT = '/tmp/Anton.ttf'
if not os.path.exists(FONT):
    open(FONT, 'wb').write(urllib.request.urlopen('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', timeout=60).read())

im = Image.open(io.BytesIO(urllib.request.urlopen(E('URL'), timeout=60).read())).convert('RGB').resize((1280, 720))
W, H = im.size
lato = E('LATO', 'sinistra'); limite = float(E('LIMITE', '0.50'))
a = np.asarray(im).astype(int)
bianco = (a.min(axis=2) > 232)
xs0, xs1 = (0, int(W * .6)) if lato == 'sinistra' else (int(W * .4), W)
m = np.zeros_like(bianco); m[:, xs0:xs1] = bianco[:, xs0:xs1]
cols = np.where(m.sum(axis=0) > H * .18)[0]; rows = np.where(m.sum(axis=1) > W * .10)[0]
vecchio = (cols.min() - 14, rows.min() - 14, cols.max() + 22, rows.max() + 24)   # cartoncino vecchio + bordo e ombra
print('cartoncino vecchio:', vecchio)
if lato == 'sinistra':
    x0, x1 = min(int(W * .025), vecchio[0]), max(int(W * limite), vecchio[2])
else:
    x0, x1 = min(int(W * (1 - limite)), vecchio[0]), max(int(W * .975), vecchio[2])
y0, y1 = min(int(H * .04), vecchio[1]), max(int(H * (.90 if lato == 'sinistra' else .76)), vecchio[3])

F = lambda k: ImageFont.truetype(FONT, k)
ARIA_X, ARIA_Y = .12, .09
pad = int(W * .016); larg, alt = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad


def altezza(f, righe):
    bb = [f.getbbox(r, anchor='ls') for r in righe]; gap = f.size * .16
    return bb, gap, sum(b[3] - b[1] for b in bb) + gap * (len(righe) - 1)


parole = E('FRASE').upper().split(); n = len(parole); best = None
for mk in range(1 << (n - 1)):
    righe, cur = [], [parole[0]]
    for i in range(1, n):
        if mk >> (i - 1) & 1:
            righe.append(' '.join(cur)); cur = [parole[i]]
        else:
            cur.append(parole[i])
    righe.append(' '.join(cur))
    if len(righe) > 4 or (len(righe) > 1 and any(len(r) <= 2 for r in righe)):
        continue
    lo, hi = 20, 320
    while lo < hi:
        k = (lo + hi + 1) // 2
        if max(F(k).getlength(r) for r in righe) + 2 * k * ARIA_X <= larg and altezza(F(k), righe)[2] + 2 * k * ARIA_Y <= alt:
            lo = k
        else:
            hi = k - 1
    if not best or lo > best[0]:
        best = (lo, righe)
k, righe = best
print('carattere', k, 'righe', righe)
senza = lambda r: ''.join(ch for ch in unicodedata.normalize('NFD', r) if unicodedata.category(ch) != 'Mn')
f = F(k); bb, gap, _ = altezza(f, righe)
bn = [f.getbbox(senza(r), anchor='ls') for r in righe]
ext = [max(0, q[1] - b[1]) for q, b in zip(bn, bb)]
hn = sum(q[3] - q[1] for q in bn) + sum(gap + e for e in ext[1:])
vpad = max(pad * .7, ext[0] + max(4, k // 18) + 2) + k * ARIA_Y
wt = max(f.getlength(r) for r in righe)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
box = [cx - wt / 2 - pad - k * ARIA_X, cy - hn / 2 - vpad, cx + wt / 2 + pad + k * ARIA_X, cy + hn / 2 + vpad]
# il cartoncino nuovo deve coprire tutto quello vecchio
box = [min(box[0], vecchio[0]), min(box[1], vecchio[1]), max(box[2], vecchio[2] - 8), max(box[3], vecchio[3] - 10)]
cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
base = im.convert('RGBA')
sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((box[0] + 8, box[1] + 10, box[2] + 8, box[3] + 10), radius=int(pad * 1.4), fill=(0, 0, 0, 110))
base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
dr = ImageDraw.Draw(base)
dr.rounded_rectangle(box, radius=int(pad * 1.4), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=max(4, k // 18))
y = cy - hn / 2
for i, (r, q) in enumerate(zip(righe, bn)):
    if i:
        y += gap + ext[i]
    dr.text((cx, y - q[1]), r, font=f, fill=MAG, anchor='ms')
    y += q[3] - q[1]
os.makedirs(os.path.dirname(E('OUT')), exist_ok=True)
base.convert('RGB').save(E('OUT'), quality=92)
im.save(E('OUT').replace('.jpg', '_prima.jpg'), quality=92)
print('fatto', E('OUT'))
