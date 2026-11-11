#!/usr/bin/env python3
"""LIBRERIA DI UN PERSONAGGIO A CARTONE (11 nov 2026, KAO a cartone): partendo dal riferimento del personaggio crea, UNA VOLTA SOLA,
le sue pose ed espressioni e i personaggi secondari nello stesso stile, su sfondo trasparente, per i video a cartone.
FLUX.2 Klein edit (circa 0,017 $ a immagine) con il riferimento; sfondo bianco tolto dal programma (riempimento dai bordi, gratis).
Uso: PERSONAGGIO=kao (cartella personaggi/kao con identikit.png e pose.json). SOLO=nome1,nome2 per rifarne solo alcune.
Scrive personaggi/<nome>/pose/<posa>.png, secondari/<nome>.png e un foglio di anteprima anteprima.jpg."""
import io, json, os, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import motore_yt as YT
import costi as CO
E = os.environ.get
NOME = E('PERSONAGGIO', 'kao').strip()
CART = os.path.join('personaggi', NOME)
CFG = json.load(open(os.path.join(CART, 'pose.json')))
REF = f"https://raw.githubusercontent.com/{E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')}/main/{CART}/identikit.png"
SOLO = {x.strip() for x in E('SOLO', '').split(',') if x.strip()}
SPESA = [0.0]


def fal(dati):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b/edit', dati, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    url = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
    SPESA[0] += 0.017; CO.registra('fal', 'flux-2-klein-4b-edit', dollari=0.017, nota='libreria personaggio ' + NOME)
    return Image.open(io.BytesIO(YT.http(url, raw=True, timeout=120))).convert('RGB')


def scontorna(im):
    """Sfondo bianco -> trasparente: riempimento dai bordi (il personaggio ha il contorno nero, quindi il bianco interno resta)."""
    im = im.convert('RGBA'); w, h = im.size
    m = Image.new('L', (w + 2, h + 2), 0)
    base = Image.new('RGB', (w + 2, h + 2), (255, 255, 255)); base.paste(im.convert('RGB'), (1, 1))
    ImageDraw.floodfill(base, (0, 0), (255, 0, 255), thresh=40)
    px = base.load(); mp = m.load()
    for y in range(h + 2):
        for x in range(w + 2):
            if px[x, y] != (255, 0, 255):
                mp[x, y] = 255
    a = m.crop((1, 1, w + 1, h + 1)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(.8))
    im.putalpha(a)
    return im.crop(im.getbbox() or (0, 0, w, h))


def fai(tipo, nome, descr):
    out = os.path.join(CART, tipo, nome + '.png')
    if os.path.exists(out) and nome not in SOLO:
        return out
    if SOLO and nome not in SOLO:
        return out if os.path.exists(out) else None
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if tipo == 'pose':
        p = f"{CFG['descrizione']}, now {descr}. Full body visible from head to shoes, centered, plain pure white background, no floor, no shadow, no text, no other people."
    else:
        p = (f"A NEW secondary character in EXACTLY the same flat 2D cartoon style as the reference (same round bald-head proportions style, thick black outlines, "
             f"flat colors): {descr}. NOT the magenta shirt. Full body from head to shoes, centered, plain pure white background, no floor, no shadow, no text.")
    for k in range(2):
        try:
            im = fal({'prompt': p, 'image_urls': [REF], 'image_size': {'width': 768, 'height': 1152}, 'num_images': 1, 'output_format': 'png'})
            scontorna(im).save(out); print(tipo, nome, 'ok'); return out
        except Exception as e:
            print(tipo, nome, 'riprovo:', str(e)[:120])
    return None


fatti = [fai('pose', n, d) for n, d in CFG.get('pose', {}).items()] + [fai('secondari', n, d) for n, d in CFG.get('secondari', {}).items()]
fatti = [f for f in fatti if f and os.path.exists(f)]
# anteprima: tutte le figure su fondo grigio chiaro, con il nome sotto
cel = 220; col = 8; righe = (len(fatti) + col - 1) // col
fo = Image.new('RGB', (col * cel, righe * (cel + 30)), (232, 232, 232)); d = ImageDraw.Draw(fo)
for i, f in enumerate(fatti):
    im = Image.open(f); im.thumbnail((cel - 20, cel - 20))
    x, y = (i % col) * cel, (i // col) * (cel + 30)
    fo.paste(im, (x + (cel - im.width) // 2, y + (cel - im.height) // 2), im)
    d.text((x + 8, y + cel + 6), os.path.basename(f)[:-4], fill=(0, 0, 0))
fo.save(os.path.join(CART, 'anteprima.jpg'), quality=88)
print(f'LIBRERIA {NOME}: {len(fatti)} figure, spesa {SPESA[0]:.2f} $')
