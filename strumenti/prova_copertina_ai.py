#!/usr/bin/env python3
"""PROVE COPERTINA CON AI A PARTIRE DA UNA BOZZA (8 nov 2026, per tutti i canali): fal nano-banana-2/edit (~0,08 $ a immagine).
PAYLOAD = {"cartella": "prove_video/<canale>/copertine_ai", "base": "<percorso immagine nel repository>", "prove": [{"nome": "...", "prompt": "..."}]}
Uscita: <cartella>/<nome>.jpg + confronto.jpg (bozza + prove)."""
import base64, io, json, os, time, urllib.request
from PIL import Image, ImageDraw

P = json.loads(os.environ['PAYLOAD'])
CART = P['cartella']; os.makedirs(CART, exist_ok=True)
H = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', ''), 'Content-Type': 'application/json'}


def http(url, dati=None, raw=False):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None, headers=H)
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
    return b if raw else json.loads(b or b'{}')


def leggi(p):
    im = Image.open(p).convert('RGB'); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=92)
    return im, 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


base, ref0 = leggi(P['base']) if P.get('base') else (None, None)   # una bozza per tutte, oppure "base" dentro ogni prova
fatte, spesa = ([('BOZZA', base)] if base is not None else []), 0.0
for pr in P['prove']:
    ref = leggi(pr['base'])[1] if pr.get('base') else ref0
    try:
        inv = http('https://queue.fal.run/fal-ai/nano-banana-2/edit', {'prompt': pr['prompt'], 'image_urls': [ref], 'aspect_ratio': '16:9',
                                                                        'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
        for _ in range(150):
            time.sleep(4); st = http(inv['status_url'])
            if st.get('status') == 'COMPLETED':
                break
        r = http(inv['response_url']); spesa += 0.08
        im = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB').resize((1280, 720))
        im.save(os.path.join(CART, pr['nome'] + '.jpg'), quality=92); fatte.append((pr['nome'], im)); print('fatta', pr['nome'], flush=True)
    except Exception as e:
        print('NON riuscita', pr['nome'], str(e)[:200], flush=True)
tw, th = 640, 360
S = Image.new('RGB', (tw * 2, (th + 30) * ((len(fatte) + 1) // 2)), 'white'); d = ImageDraw.Draw(S)
for i, (n, im) in enumerate(fatte):
    x, y = (i % 2) * tw, (i // 2) * (th + 30); S.paste(im.resize((tw, th)), (x, y + 30)); d.text((x + 8, y + 8), n, fill='black')
S.save(os.path.join(CART, 'confronto.jpg'), quality=88)
print(f'SPESA: {spesa:.2f} $ ({len(fatte) - 1} immagini)')
