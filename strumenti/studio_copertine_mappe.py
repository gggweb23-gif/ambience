#!/usr/bin/env python3
"""
STUDIO COPERTINE MAPPE (canali a mappe, es. Rich Borders): per i video piu' visti del competitor rifa' la copertina nel NOSTRO motore a mappe
(80% uguale: stessi paesi, stessa divisione, stessi colori, stessa scritta) in 3 varianti con il nostro tocco:
  A  PIN CHE REAGISCE  - la mascotte Pin grande sulla linea rossa, stupita (un personaggio che reagisce alza il CTR)
  B  IL NUMERO         - come A + un numero vero e forte nel riquadro giallo (8X RICHER, $3 TRILLION...)
  C  LA RICCHEZZA SI SPOSTA - come A + una grande freccia d'oro dal paese che perde a quello che vince
Disegnato in codice (gratis): si paga solo Claude che legge le 5 copertine (~0,05 $).
Ingresso: PAYLOAD = {"nome": "...", "video_ids": ["..."], "titoli": ["..."]}
Uscita: prove_angoli/<nome>/ (confronto.jpg, telefono.jpg, <n>_A/B/C.jpg)
"""
import io, json, math, os, sys
sys.argv = sys.argv[:1]
P0 = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'copertina_presentatore': ''})
sys.path.insert(0, os.getcwd())
import video_mappe as VM
from PIL import Image, ImageDraw, ImageFont

CART = os.path.join('prove_angoli', P0['nome']); os.makedirs(CART, exist_ok=True)
VM.P['copertina_presentatore'] = ''


def numero_vero(titolo, cp):
    """Un confronto vero e forte (max 12 caratteri) per la variante B: Claude lo sceglie da dati pubblici noti."""
    rr = VM.http('https://api.anthropic.com/v1/messages', {'model': VM.MODELLO_AI, 'max_tokens': 300, 'messages': [{'role': 'user', 'content':
        f'YouTube video "{titolo}". Give ONE short, TRUE and striking comparison number for its thumbnail, max 12 characters, in CAPS, '
        'based on well-known public data (World Bank GDP per capita, population, area...), e.g. "8X RICHER", "$3 TRILLION", "1 VS 18". '
        'Answer ONLY JSON: {"numero": "...", "fonte": "one short line with the data used"}'}]},
        {'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=120)
    t = ''.join(b.get('text', '') for b in rr.get('content', []))
    return json.loads(t[t.find('{'): t.rfind('}') + 1])


def freccia(im, x0, y0, x1, y1):
    """Grande freccia curva d'oro con bordo nero (la ricchezza che si sposta)."""
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(41):
        t = i / 40; mx, my = (x0 + x1) / 2, min(y0, y1) - abs(x1 - x0) * .35
        pts.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t ** 2 * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t ** 2 * y1))
    d.line(pts[:-3], fill=(0, 0, 0), width=58, joint='curve'); d.line(pts[:-3], fill=(255, 205, 0), width=40, joint='curve')
    (ax, ay), (bx, by) = pts[-6], pts[-1]
    ang = math.atan2(by - ay, bx - ax); L = 95
    tri = [(bx, by), (bx - L * math.cos(ang - .5), by - L * math.sin(ang - .5)), (bx - L * math.cos(ang + .5), by - L * math.sin(ang + .5))]
    d.polygon(tri, fill=(255, 205, 0), outline=(0, 0, 0), width=8)


righe = []
for n, (vid, tit) in enumerate(zip(P0['video_ids'], P0.get('titoli') or [''] * 99), 1):
    comp = {'id': vid, 'titolo': tit}
    try:
        cp = VM.piano_copertina(comp, {})
    except Exception as e:
        print('piano non riuscito', vid, e, flush=True); continue
    loro = Image.open(io.BytesIO(VM.http(f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', raw=True))).convert('RGB').resize((1280, 720))
    loro.save(os.path.join(CART, f'{n}_loro.jpg'), quality=90)
    cp['pin_scala'] = 5.5   # Pin grande: e' lui che reagisce
    base = dict(cp, extra='')
    pa = os.path.join(CART, f'{n}_A.jpg'); VM.copertina_nuova(base, pa)
    try:
        num = numero_vero(tit, cp)
    except Exception:
        num = {'numero': '', 'fonte': ''}
    pb = os.path.join(CART, f'{n}_B.jpg'); VM.copertina_nuova(dict(cp, extra=str(num.get('numero') or '')), pb)
    pc = os.path.join(CART, f'{n}_C.jpg'); VM.copertina_nuova(base, pc)
    im = Image.open(pc).convert('RGBA').resize((VM.W, VM.H))
    sx, dx = cp.get('sinistra'), cp.get('destra')
    vince_sx = bool(sx and (sx.get('colori') or {}).get('lime'))
    if sx and dx:   # dal lato che perde a quello che vince
        a, b = (VM.W * .72, VM.H * .55), (VM.W * .28, VM.H * .55)
        if not vince_sx:
            a, b = b, a
        freccia(im, a[0], a[1], b[0], b[1])
    else:
        freccia(im, VM.W * .80, VM.H * .70, VM.W * .52, VM.H * .55)
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(pc, quality=93)
    righe.append((n, vid, tit, num))
    print('fatto', n, tit, num, flush=True)

# fogli di confronto
F = ImageFont.truetype(os.path.join(VM.RIS, 'Anton-Regular.ttf'), 30)
tw, th = 640, 360
S = Image.new('RGB', (tw * 4, (th + 50) * len(righe) + 50), 'white'); d = ImageDraw.Draw(S)
for j, t in enumerate(['LORO', 'A · PIN CHE REAGISCE', 'B · IL NUMERO', 'C · LA RICCHEZZA SI SPOSTA']):
    d.text((j * tw + 10, 8), t, font=F, fill='black')
M = Image.new('RGB', (4 * 256 + 10, len(righe) * 148 + 10), (15, 15, 15))
for i, (n, vid, tit, num) in enumerate(righe):
    y = 50 + i * (th + 50)
    d.text((10, y + 6), f'{tit[:70]}   |   B: {num.get("fonte", "")[:60]}', font=ImageFont.truetype(os.path.join(VM.RIS, 'Anton-Regular.ttf'), 22), fill='grey')
    for j, k in enumerate(['loro', 'A', 'B', 'C']):
        im = Image.open(os.path.join(CART, f'{n}_{k}.jpg')).convert('RGB')
        S.paste(im.resize((tw, th)), (j * tw, y + 40)); M.paste(im.resize((246, 138), Image.LANCZOS), (10 + j * 256, 10 + i * 148))
S.save(os.path.join(CART, 'confronto.jpg'), quality=85); M.save(os.path.join(CART, 'telefono.jpg'), quality=90)
json.dump([{'n': n, 'id': v, 'titolo': t, 'numero': u} for n, v, t, u in righe], open(os.path.join(CART, 'piano.json'), 'w'), indent=1)
print('FATTO', flush=True)
