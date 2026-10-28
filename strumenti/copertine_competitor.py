#!/usr/bin/env python3
"""
COPERTINE COMPETITOR (per tutti i canali, gratis): scarica titoli e copertine degli ultimi video di un canale YouTube (feed RSS pubblico)
e fa un foglio di confronto, per studiare copertine e scritte del competitor.
Ingresso: PAYLOAD = {"nome": "roma", "canale_id": "UC..."}
Uscita: copertine_competitor/<nome>/ (<id>.jpg, foglio.jpg, titoli.txt) salvati nel repository.
"""
import io, json, os, re, urllib.request
from PIL import Image, ImageDraw

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = os.path.join('copertine_competitor', P['nome']); os.makedirs(CART, exist_ok=True)
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read()
xml = get('https://www.youtube.com/feeds/videos.xml?channel_id=' + P['canale_id']).decode()
voci = re.findall(r'<yt:videoId>([\w-]{11})</yt:videoId>.*?<title>(.*?)</title>.*?<media:statistics views="(\d+)"', xml, re.S)
righe, imgs = [], []
for vid, tit, views in voci:
    for q in ('maxresdefault', 'hqdefault'):
        try:
            im = Image.open(io.BytesIO(get(f'https://i.ytimg.com/vi/{vid}/{q}.jpg'))).convert('RGB').resize((1280, 720)); break
        except Exception:
            im = None
    if im is None:
        continue
    im.save(os.path.join(CART, vid + '.jpg'), quality=90); imgs.append((vid, im))
    righe.append(f'{vid} | {int(views):>9,} views | {tit}')
    print(righe[-1], flush=True)
open(os.path.join(CART, 'titoli.txt'), 'w').write('\n'.join(righe) + '\n')
tw, th, col = 480, 270, 4
S = Image.new('RGB', (tw * col, (th + 24) * ((len(imgs) + col - 1) // col)), 'white'); d = ImageDraw.Draw(S)
for i, (vid, im) in enumerate(imgs):
    x, y = (i % col) * tw, (i // col) * (th + 24)
    S.paste(im.resize((tw, th)), (x, y + 24)); d.text((x + 6, y + 6), vid, fill='black')
S.save(os.path.join(CART, 'foglio.jpg'), quality=85)
