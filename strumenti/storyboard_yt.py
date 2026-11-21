#!/usr/bin/env python3
"""STORYBOARD YOUTUBE (gratis, 21 nov 2026): per capire com'e' fatto DAVVERO il video di un competitor (clip vere? immagini AI?
animazioni? mappe? cartone?) scarica le miniature dello storyboard pubblico di YouTube e fa un foglio unico.
Env: VIDEO = id separati da virgola, NOME. Uscita: prove_video/storyboard/<NOME>/<id>.jpg"""
import io, json, os, re, urllib.request
from PIL import Image

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9', 'Cookie': 'CONSENT=YES+1'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()
OUT = os.path.join('prove_video', 'storyboard', os.environ.get('NOME') or 'sb'); os.makedirs(OUT, exist_ok=True)
for vid in [v.strip() for v in os.environ.get('VIDEO', '').split(',') if v.strip()]:
    try:
        html = get('https://www.youtube.com/watch?v=' + vid).decode('utf-8', 'ignore')
        spec = json.loads('"' + re.search(r'"playerStoryboardSpecRenderer":\{"spec":"(.*?)"', html).group(1) + '"')
    except Exception as e:
        print(vid, 'storyboard non trovato', str(e)[:100]); continue
    parti = spec.split('|'); base = parti[0]
    livello = len(parti) - 2   # il livello piu' grande
    w, h, n, cols, rows, _, nome, sigh = parti[livello + 1].split('#')[:8]
    fogli = -(-int(n) // (int(cols) * int(rows)))
    imgs = []
    for m in range(min(fogli, 6)):
        u = base.replace('$L', str(livello)).replace('$N', nome).replace('$M', str(m)) + '&sigh=' + sigh
        try:
            imgs.append(Image.open(io.BytesIO(get(u))).convert('RGB'))
        except Exception as e:
            print(vid, 'foglio', m, str(e)[:80])
    if imgs:
        tot = Image.new('RGB', (imgs[0].width, sum(i.height for i in imgs)))
        y = 0
        for i in imgs:
            tot.paste(i, (0, y)); y += i.height
        tot.save(os.path.join(OUT, vid + '.jpg'), quality=85); print(vid, 'ok', len(imgs), 'fogli')
