#!/usr/bin/env python3
"""11 nov sera (Giorgio, Costo Vero: "deve vedersi meglio il prodotto, cambia completamente stile"): copertina PRODOTTO.
Il prodotto ENORME e nitido sulla meta' sinistra (o destra) su fondo pieno colorato, sull'altra meta' un CARTELLINO del prezzo
appeso: prezzo di cartellino barrato -> costo vero enorme in rosso -> "IN N ANNI". Niente persone: il prodotto e' il protagonista.
FLUX.2 Klein 4B testo-immagine 1920x1080 (circa 0,02 $). Non carica: salva in prove_video/Costo_Vero/prodotto/<nome>.jpg.
PAYLOAD: {"prove": [{"nome", "prodotto" (inglese), "prezzo", "costo_vero", "anni", "stile": "disegno|foto", "fondo": "#hex", "lato": "sx|dx"}]}"""
import io, json, os, sys, time
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3
import copertine_possesso as CP
E = os.environ.get
Q = json.loads(E('PAYLOAD') or '{}')
OUT = 'prove_video/Costo_Vero/prodotto'
W, H = 1280, 720


def eur(v):
    return f"{int(round(float(v))):,}".replace(',', '.') + ' €'


def klein(p):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = G3.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': p, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'}, hd)
    for _ in range(120):
        time.sleep(2)
        if G3.http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = G3.http(inv['response_url'], headers=hd)['images'][0]['url']
    try:
        import costi as CO; CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='copertina prodotto')
    except Exception:
        pass
    return Image.open(io.BytesIO(G3.http(u, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))


def sistema(im, sx):
    """L'AI non rispetta sempre "meta' sinistra": trovo il prodotto (diverso dal colore del fondo) e, se serve, lo rimpicciolisco e lo
    sposto sul suo lato, su fondo dello stesso colore, cosi' il cartellino non lo copre mai."""
    import numpy as np
    a = np.asarray(im).astype(int)
    bordo = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    fondo = np.median(bordo, axis=0)
    m = np.abs(a - fondo).sum(2) > 90
    ys, xs = np.where(m)
    if len(xs) < 500:
        return im
    bx0, bx1 = np.percentile(xs, 1), np.percentile(xs, 99); by0, by1 = np.percentile(ys, 1), np.percentile(ys, 99)
    serve = 620   # spazio del cartellino
    s = min(1.0, (W - serve - 40) / max(1, bx1 - bx0), (H - 30) / max(1, by1 - by0))
    nuovo = Image.new('RGB', (W, H), tuple(int(v) for v in fondo))
    pic = im.resize((int(W * s), int(H * s)), Image.LANCZOS)
    dx = (20 - bx0 * s) if sx else (W - 20 - bx1 * s)
    dy = (H - (by0 + by1) * s) / 2
    if not sx:   # 11 nov: sul lato destro il prodotto sta piu' in alto, lontano dalla durata del video
        dy = min(dy, H - 110 - by1 * s)
    maschera = Image.new('L', pic.size, 0); ImageDraw.Draw(maschera).rectangle((40, 40, pic.width - 40, pic.height - 40), fill=255)
    nuovo.paste(pic, (int(dx), int(dy)), maschera.filter(ImageFilter.GaussianBlur(30)))
    return nuovo


def crea(p):
    """p: prodotto (inglese), prezzo, costo_vero, anni, stile foto|disegno, fondo #hex, lato sx|dx -> immagine RGB 1280x720."""
    sx = p.get('lato', 'sx') == 'sx'
    lato = 'LEFT' if sx else 'RIGHT'
    stile = ('Ultra realistic commercial PRODUCT PHOTOGRAPHY, studio light, crisp reflections, razor sharp. ' if p.get('stile') == 'foto'
             else 'Bold DIGITAL PAINTED ILLUSTRATION, clean outlines, vivid colours, high contrast, razor sharp. ')
    prompt = (stile + f"{p['prodotto']}, HUGE and clearly recognizable, three-quarter view, filling the {lato} HALF of the frame from top to bottom, "
              f"slightly tilted, dramatic but clean. Solid plain background colour {p.get('fondo', '#1E5BFF')} everywhere, the other half of the image is "
              "COMPLETELY EMPTY plain background. No people, no hands, no text, no letters, no numbers, no logos, no brand names.")
    im = sistema(klein(prompt), sx).convert('RGBA')
    # cartellino del prezzo appeso (sull'altra meta', mai nell'angolo in basso a destra della durata)
    x0 = 700 if sx else 70; cw, ch = 520, 470; y0 = 60
    card = Image.new('RGBA', (cw + 40, ch + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    d.rounded_rectangle((20, 20, cw + 20, ch + 20), 34, fill=CP.BIANCO, outline=CP.NERO, width=9)
    d.ellipse((cw // 2 - 4, 38, cw // 2 + 36, 78), fill=(230, 230, 230), outline=CP.NERO, width=6)   # buco del cartellino
    prezzo, vero, tag = eur(p['prezzo']), eur(p['costo_vero']), f"IN {int(p['anni'])} ANNI"
    sp = CP.adatta(prezzo, 96, cw - 120); wp = CP.F(sp).getlength(prezzo)
    xp = 20 + (cw - wp) / 2; d.text((xp, 100), prezzo, font=CP.F(sp), fill=CP.NERO)
    if float(p['costo_vero']) > float(p['prezzo']):
        d.line((xp - 14, 100 + sp * .66, xp + wp + 14, 100 + sp * .30), fill=CP.ROSSO, width=12)
    sv = CP.adatta(vero, 150, cw - 60); wv = CP.F(sv).getlength(vero)
    d.text((20 + (cw - wv) / 2, 225), vero, font=CP.F(sv), fill=CP.ROSSO, stroke_width=4, stroke_fill=CP.NERO)
    st = CP.adatta(tag, 70, cw - 160); wt = CP.F(st).getlength(tag); yt = 225 + sv + 30
    d.rounded_rectangle((20 + (cw - wt) / 2 - 22, yt - 10, 20 + (cw + wt) / 2 + 22, yt + st * 1.18), 18, fill=CP.GIALLO, outline=CP.NERO, width=5)
    d.text((20 + (cw - wt) / 2, yt), tag, font=CP.F(st), fill=CP.NERO)
    card = card.rotate(4 if sx else -4, expand=True, resample=Image.BICUBIC)
    ombra = Image.new('RGBA', card.size, (0, 0, 0, 0)); ombra.paste((0, 0, 0, 110), (0, 0), card.split()[-1])
    x0 = (W - card.width - 45) if sx else 45
    im.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(14)), (x0 + 14, y0 + 18))
    im.alpha_composite(card, (x0, y0))
    assert y0 + card.height < H - 20
    return im.convert('RGB')


FONDI = ['#1E5BFF', '#FFC21A', '#12B76A', '#7B3FF2', '#FF5A36', '#00A3C4']


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for p in Q.get('prove', []):
        f = os.path.join(OUT, p['nome'] + '.jpg'); crea(p).save(f, quality=93); print('pronta', f)
