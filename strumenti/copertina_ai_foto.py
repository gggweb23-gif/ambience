#!/usr/bin/env python3
"""11 nov: copertina in stile FOTO generata con l'AI quando Pexels non ha foto valide (es. Agora, filone natura: Congo).
FLUX.2 Klein 4B testo-immagine a 1920x1080 (circa 0,02 $ l'una) + scritta grande con bordo (MANO LIBERA: lato a scelta, mai in basso a destra).
Non carica: salva in CARTELLA/<nome>.jpg, si carica dopo il controllo con carica_copertina.yml.
Ingresso (env PAYLOAD): {"cartella", "prove": [{"nome", "prompt", "testo", "lato": "sx"|"dx"}]}"""
import io, json, os, sys, time
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3
import copertine_possesso as CP
E = os.environ.get
Q = json.loads(E('PAYLOAD') or '{}')
OUT = Q.get('cartella', 'prove_video/copertine_ai'); os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
REGOLA = (' Photorealistic documentary nature photograph, National Geographic style, razor sharp, high detail, dramatic natural light, rich colours. '
          'No text, no letters, no logos, no watermark, no frame.')


def klein(p):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = G3.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': p + REGOLA, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'}, hd)
    for _ in range(120):
        time.sleep(2)
        if G3.http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = G3.http(inv['response_url'], headers=hd)['images'][0]['url']
    return Image.open(io.BytesIO(G3.http(u, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


FONT = {}


def font(url):
    """11 nov (Giorgio: font piu' da avventura per il filone natura): font Google scaricato al volo, sempre ben leggibile."""
    if not url:
        return None
    if url not in FONT:
        f = os.path.join('/tmp', os.path.basename(url)); open(f, 'wb').write(G3.http(url, raw=True)); FONT[url] = f
    return FONT[url]


BASI = {}
for p in Q.get('prove', []):
    if p.get('base') and os.path.exists(p['base']):
        im = Image.open(p['base']).convert('RGBA')
    elif p.get('stessa') in BASI:
        im = BASI[p['stessa']].copy()
    else:
        im = klein(p['prompt']).convert('RGBA')
        im.convert('RGB').save(os.path.join(OUT, p['nome'] + '_base.jpg'), quality=95)   # base senza scritta: si riusa per cambiare solo la scritta
    BASI[p['nome']] = im.copy()
    ff = font(p.get('font'))
    if ff:
        from PIL import ImageFont
        CP.F = lambda s, ff=ff: ImageFont.truetype(ff, s)
    righe = str(p['testo']).upper().rstrip('.').split('|')
    sx = p.get('lato', 'sx') == 'sx'
    x = 60 if sx else W - 60
    larg = W * .52
    size = min(CP.adatta(r, 170, larg) for r in righe)
    # ombra morbida solo dietro la scritta, per staccarla dalla foto
    ombra = Image.new('RGBA', im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ombra)
    y = 70
    for r in righe:
        w = CP.F(size).getlength(r); x0 = x if sx else x - w
        do.rounded_rectangle((x0 - 30, y - 20, x0 + w + 30, y + size + 25), 30, fill=(0, 0, 0, 120)); y += int(size * 1.08)
    im.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(im); y = 70
    for i, r in enumerate(righe):
        CP.scritta_bordo(d, (x, y), r, size, CP.GIALLO if i == len(righe) - 1 else CP.BIANCO, sw=max(8, size // 14), anchor='la' if sx else 'ra')
        y += int(size * 1.08)
    assert y < H - 140, 'scritta troppo lunga'
    f = os.path.join(OUT, p['nome'] + '.jpg'); im.convert('RGB').save(f, quality=93); print('pronta', f)
