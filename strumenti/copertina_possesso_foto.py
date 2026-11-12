#!/usr/bin/env python3
"""COSTO VERO - copertina "FOTO 2C" (scelta di Giorgio del 12 nov 2026, valida per tutti i video nuovi fino a nuove direttive).
Foto VERA (realistica) del soggetto su meta' immagine; sull'altra meta', in colonna, caratteri puliti alti e stretti (Bebas Neue):
  PREZZO / 35.000 EUR barrato (barra rossa sottile, cifre leggibili) / freccia rossa giu' / 60.500 EUR giallo gigante / IN 10 ANNI.
Sempre un CERCHIO rosso a mano sul soggetto (Giorgio: "bene avere sempre un cerchio o una freccia per identificare il soggetto").
MANO LIBERA: il lato si alterna da un video all'altro (soggetto a destra e scritte a sinistra, o il contrario); mai scritte in basso
a destra sulla durata del video. Spesa: una foto FLUX.2 Klein ~0,02 $."""
import io, math, os, random, sys, time
from PIL import Image, ImageDraw, ImageFont, ImageFilter
QUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, QUI); sys.path.insert(0, os.path.dirname(QUI))
import motore_yt as YT
import costi as CO

E = os.environ.get
W, H = 1280, 720
R, Y, INK, BI = (228, 25, 40), (255, 214, 0), (18, 18, 24), (255, 255, 255)
BB = os.path.join(os.path.dirname(QUI), 'fonts_costo_vero', 'BebasNeue-Regular.ttf')
F = lambda s: ImageFont.truetype(BB, int(s))


def eur(v):
    return f'{round(float(v)):,}'.replace(',', '.') + ' €'


def foto(prodotto, sx):
    """Foto realistica: il soggetto nella meta' indicata, l'altra meta' libera (prato, cielo, muro) per le scritte."""
    lato_ogg = 'LEFT' if sx else 'RIGHT'; libero = 'RIGHT' if sx else 'LEFT'
    prompt = (f'Realistic DSLR photograph, natural daylight, NOT an illustration: {prodotto}, in a real ordinary Italian setting. '
              f'The subject is big, sharp and fully visible in the {lato_ogg} HALF of the frame, vertically centered. '
              f'The {libero} 45% of the image is calm, simple background without objects (lawn, wall, sky, road). '
              'High detail, vivid but natural colors. NO text, NO letters, NO numbers, NO logos, NO brand names.')
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    for _ in range(3):
        try:
            inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
            for _ in range(150):
                time.sleep(2)
                if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
                    break
            u = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
            CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='copertina costo vero foto 2c')
            return Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').resize((W, H), Image.LANCZOS)
        except Exception as e:
            print('foto copertina non riuscita, riprovo:', str(e)[:120], flush=True); time.sleep(4)
    raise RuntimeError('foto copertina non riuscita')


def box_soggetto(im, cosa):
    """Dove sta il soggetto nella foto (Claude Haiku, ~0,001 $): il cerchio rosso lo stringe da vicino invece di stare in un punto fisso."""
    import base64, json, re
    try:
        buf = io.BytesIO(); im.convert('RGB').resize((640, 360)).save(buf, 'JPEG', quality=85)
        r = YT.http('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 120, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': f'Image 640x360. Bounding box of the main subject ({cosa or "the main object"}). Answer ONLY {{"box": [x1, y1, x2, y2]}}.'}]}]},
            {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'}, timeout=60)
        CO.registra('claude', 'claude-haiku-4-5-20251001', usage=r.get('usage'), nota='box soggetto copertina')
        b = json.loads(re.search(r'\{.*\}', r['content'][0]['text'], re.S).group(0))['box']
        x1, y1, x2, y2 = [float(v) * 2 for v in b]
        mx, my = (x2 - x1) * .12, (y2 - y1) * .12   # un po' d'aria intorno
        return (max(10, x1 - mx), max(10, y1 - my), min(W - 10, x2 + mx), min(H - 10, y2 + my))
    except Exception as e:
        print('box del soggetto non trovato:', str(e)[:100], flush=True)
        return None


def cerchio(d, box, seme=3):
    random.seed(seme)
    cx, cy, rx, ry = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
    for _ in range(2):
        pts = [(cx + rx * (1 + random.uniform(-.03, .03)) * math.cos(a / 40 * 2 * math.pi + .3),
                cy + ry * (1 + random.uniform(-.03, .03)) * math.sin(a / 40 * 2 * math.pi + .3)) for a in range(46)]
        d.line(pts, fill=R, width=9, joint='curve')


def crea(p):
    """p: prodotto (descrizione in inglese), prezzo, costo_vero, anni, lato ('sx' = scritte a sinistra), immagine (facoltativa, PIL gia' pronta)."""
    scritte_sx = str(p.get('lato') or 'sx') == 'sx'
    im = (p.get('immagine') or foto(p['prodotto'], sx=not scritte_sx)).convert('RGBA')
    d0 = ImageDraw.Draw(im)
    box = p.get('box') or (box_soggetto(im, p.get('prodotto')) if E('ANTHROPIC_API_KEY') else None) or ((730, 230, 1250, 640) if scritte_sx else (40, 200, 560, 610))
    cerchio(d0, box, seme=int(p.get('seme') or 3))   # il cerchio stretto intorno al soggetto
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    prezzo, vero, anni = float(p.get('prezzo') or 0), float(p['costo_vero']), int(p.get('anni') or 0)
    x0 = 44 if scritte_sx else 760

    def riga(y, txt, size, col, ancora='la'):
        x = x0 if ancora == 'la' else 1240
        d.text((x, y), txt, font=F(size), fill=col, stroke_width=max(5, int(size) // 14), stroke_fill=INK, anchor=ancora)
        return d.textbbox((x, y), txt, font=F(size), anchor=ancora)

    an = 'la' if scritte_sx else 'ra'
    y = 26
    if prezzo and vero > prezzo:   # prezzo barrato solo se il costo vero e' piu' alto (regola 10 nov)
        riga(y, 'PREZZO', 64, BI, an)
        b = riga(86, eur(prezzo), 150, BI, an)
        lin = (b[0] - 6, b[3] - 4, b[2] + 6, b[1] + 4)
        d.line(lin, fill=INK, width=15); d.line(lin, fill=R, width=9)
        fx = (b[0] + 136) if scritte_sx else (b[2] - 136)
        d.polygon([(fx - 30, 262), (fx + 30, 262), (fx + 30, 290), (fx + 60, 290), (fx, 338), (fx - 60, 290), (fx - 30, 290)], fill=R, outline=INK)
        y = 340
    else:
        riga(y, 'COSTO VERO', 80, BI, an); y = 120
    size = 200
    while size > 120 and F(size).getlength(eur(vero)) > 470:
        size -= 8
    b = riga(y, eur(vero), size, Y, an)
    riga(min(b[3] + 18, 590), f'IN {anni} ANNI' if anni else 'IL COSTO VERO', 70, BI, an)   # mai sotto i 650 px (durata del video in basso a destra)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 150), (0, 0) + im.size, lay.split()[3])
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (6, 8)); im.alpha_composite(lay)
    return im.convert('RGB')


def prove():
    """Workflow: PAYLOAD {"prove": [{"nome", "prodotto", "prezzo", "costo_vero", "anni", "lato"}]} -> prove_video/Costo_Vero/copertine_foto/<nome>.jpg"""
    import json
    out = 'prove_video/Costo_Vero/copertine_foto'; os.makedirs(out, exist_ok=True)
    for k, p in enumerate(json.loads(E('PAYLOAD') or '{}').get('prove', [])):
        base = foto(p['prodotto'], sx=str(p.get('lato') or 'sx') != 'sx')
        base.save(os.path.join(out, p['nome'] + '_base.jpg'), quality=95)
        crea(dict(p, immagine=base, seme=k + 3)).save(os.path.join(out, p['nome'] + '.jpg'), quality=94)
        print('FATTO', p['nome'], flush=True)


if __name__ == '__main__' and E('PAYLOAD'):
    prove(); sys.exit(0)
if __name__ == '__main__':   # prova veloce (gratis con un'immagine gia' pronta)
    base = Image.open(sys.argv[1]) if len(sys.argv) > 1 else Image.new('RGB', (W, H), (80, 140, 90))
    for lato in ('sx', 'dx'):
        crea({'prodotto': 'test', 'prezzo': 35000, 'costo_vero': 60500, 'anni': 10, 'lato': lato, 'immagine': base}).save(f'/tmp/foto2c_{lato}.jpg', quality=92)
    print('ok')

