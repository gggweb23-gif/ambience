#!/usr/bin/env python3
"""
STUDIO COPERTINE MAPPE (canali a mappe, es. Rich Borders): per i video piu' visti del competitor 3 IDEE di copertina diverse dalle loro,
coerenti con il tema "perche' un paese e' ricco e il vicino no":
  1  IL CARTELLINO   - i paesi illuminati come oggetti in vendita, con il cartellino del prezzo (PIL per abitante vero)   (codice, gratis)
  2  LE LUCI DI NOTTE - la Terra di notte vista dal satellite NASA (Black Marble, pubblico dominio): ricco = luce, povero = buio (codice, gratis)
  3  DUE MONDI       - scena vera a terra, divisa dal confine, una persona con un piede di qua e uno di la'                     (fal, 0,04 $)
Ingresso: PAYLOAD = {"nome": "...", "video_ids": ["..."], "titoli": ["..."], "max_spesa": 0.25}
Uscita: prove_angoli/<nome>/ (confronto.jpg, telefono.jpg, <n>_1/2/3.jpg, piano.json)
"""
import base64, io, json, math, os, sys, time
sys.argv = sys.argv[:1]
P0 = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'copertina_presentatore': ''})
sys.path.insert(0, os.getcwd())
import video_mappe as VM
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

W, H = VM.W, VM.H
CART = os.path.join('prove_angoli', P0['nome']); os.makedirs(CART, exist_ok=True)
SPESA = {'tot': 0.0}; MAX_SPESA = float(P0.get('max_spesa', 0.25))
NOTTE = os.path.join(VM.RIS, 'blackmarble.jpg')
Image.MAX_IMAGE_PIXELS = None


def claude(contenuto, max_tokens=2500):
    rr = VM.http('https://api.anthropic.com/v1/messages', {'model': VM.MODELLO_AI, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': contenuto}]},
                 {'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    t = ''.join(b.get('text', '') for b in rr.get('content', []))
    return json.loads(t[t.find('{'): t.rfind('}') + 1])


def fal_immagine(prompt, path):
    if SPESA['tot'] + .04 > MAX_SPESA + 1e-9:
        raise RuntimeError('tetto di spesa raggiunto')
    SPESA['tot'] += .04
    h = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
    inv = VM.http('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': prompt, 'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, h)
    for _ in range(150):
        time.sleep(4); st = VM.http(inv['status_url'], headers=h)
        if st.get('status') == 'COMPLETED':
            r = VM.http(inv['response_url'], headers=h)
            Image.open(io.BytesIO(VM.http(r['images'][0]['url'], raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).save(path, quality=93); return
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('fal: tempo scaduto')


# ---------------------------------------------------------------- geografia comune
def anelli_lonlat(isos):
    R = VM.risorse(); out = []
    for cd in isos:
        rs = R['paesi'].get(str(cd).upper(), [])
        medi = [float(r[:, 0].mean()) for r in rs]
        for r, m in zip(rs, medi):
            if max(medi) > 100 and m < -150:   # isole oltre la linea del cambio di data (es. Russia): fuori dal riquadro
                continue
            if str(cd).upper() == 'USA' and (m < -130):   # Alaska e Hawaii lontane: la vista resta sugli USA continentali
                continue
            out.append(r)
    return out


def vista_per(gruppi, margine=1.35, centro_sposta=0.0):
    """Lo zoom che mostra INTERI e grandi i paesi indicati (proiezione della mappa: gradi uguali in x e y)."""
    pts = np.concatenate([r for g in gruppi for r in anelli_lonlat(g)]) if gruppi else np.array([[0, 20], [10, 30]])
    lo0, lo1, la0, la1 = pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max()
    larg = max((lo1 - lo0) * margine, (la1 - la0) * margine * W / H, 18)
    return {'lon': (lo0 + lo1) / 2 + centro_sposta * larg, 'lat': (la0 + la1) / 2, 'larghezza': larg}


def centro_pixel(polys):
    xs = np.concatenate([np.array(p)[:, 0] for p in polys]); ys = np.concatenate([np.array(p)[:, 1] for p in polys])
    return float(np.median(xs)), float(np.median(ys)), float(ys.min())


# ---------------------------------------------------------------- idea 1: il cartellino del prezzo
def mappa_riflettore(vista, gruppi):
    """Mappa cinematografica: tutto scuro e spento, i paesi in gioco accesi e luminosi (come sotto un riflettore)."""
    v = VM.camera(vista); base, pt = VM.fondo(v, 0.0)
    base = ImageEnhance.Contrast(base).enhance(1.25)
    scuro = ImageEnhance.Brightness(ImageEnhance.Color(base).enhance(.45)).enhance(.42)
    blu = Image.new('RGB', (W, H), (8, 22, 48))
    im = Image.blend(scuro, blu, .35).convert('RGBA')
    vign = Image.radial_gradient('L').resize((W, H)).point(lambda x: int(x * .55))
    im.paste((0, 0, 0, 255), (0, 0), vign)
    tutti = []
    for isos, col in gruppi:
        polys = VM.anelli_visibili(isos, pt); tutti.append(polys)
        g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
        for xy in polys:
            dg.line(xy + [xy[0]], fill=255, width=34)
        im.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, H), c) for c in col] + [g.filter(ImageFilter.GaussianBlur(22)).point(lambda x: int(x * .95))]))
        m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
        for xy in polys:
            dm.polygon(xy, fill=255)
        chiaro = ImageEnhance.Brightness(ImageOps.grayscale(base).convert('RGB')).enhance(1.6)
        tinta = ImageEnhance.Color(ImageChops.multiply(chiaro, Image.new('RGB', (W, H), col))).enhance(1.35)
        im.paste(tinta.convert('RGBA'), (0, 0), m)
        d = ImageDraw.Draw(im)
        for xy in polys:
            d.line(xy + [xy[0]], fill=(255, 255, 255, 230), width=4)
    return im, tutti


def cartellino(im, x_appeso, y_appeso, prezzo, ricco, ang):
    """Cartellino del prezzo appeso a un filo, leggermente ruotato."""
    f = VM.font('Anton-Regular.ttf', 150); tw = ImageDraw.Draw(im).textlength(prezzo, font=f)
    w, h = int(tw + 150), 230
    t = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(t)
    corpo = [(20 + 70, 20), (20 + w, 20), (20 + w, 20 + h), (20 + 70, 20 + h), (20, 20 + h / 2)]
    d.polygon([(x + 10, y + 12) for x, y in corpo], fill=(0, 0, 0, 140))
    d.polygon(corpo, fill=(255, 248, 225), outline=(20, 20, 20), width=8)
    d.ellipse([20 + 34, 20 + h / 2 - 16, 20 + 66, 20 + h / 2 + 16], fill=(20, 20, 20))
    d.text((20 + 80 + tw / 2 + 25, 20 + h / 2), prezzo, font=f, fill=(20, 140, 40) if ricco else (200, 40, 30), anchor='mm')
    t = t.rotate(ang, resample=Image.BICUBIC, expand=True)
    x, y = x_appeso - 30, y_appeso
    dd = ImageDraw.Draw(im); dd.line([(x_appeso, y_appeso - 120), (x + 40, y + t.height / 2)], fill=(250, 250, 250), width=5)
    im.alpha_composite(t, (int(max(10, min(W - t.width - 10, x))), int(max(10, min(H - t.height - 10, y)))))


def idea_cartellino(dati, path):
    luoghi = dati.get('luoghi') or []
    gruppi = [([str(c) for c in l.get('iso') or []], (90, 255, 60) if l.get('ricco') else (235, 80, 30)) for l in luoghi]
    vista = vista_per([g for g, _ in gruppi], 1.45)
    im, tutti = mappa_riflettore(vista, gruppi)
    for k, (l, polys) in enumerate(zip(luoghi, tutti)):
        if not polys:
            continue
        cx, cy, top = centro_pixel(polys)
        cartellino(im, cx, cy - 40, str(l.get('prezzo') or ''), bool(l.get('ricco')), 7 if k % 2 == 0 else -7)
    scritta = str(dati.get('scritta') or '').upper()[:22]
    if scritta:
        fs = 150 if len(scritta) <= 12 else 110
        VM.riquadro(im, W / 2, 120, scritta, fs)
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)


# ---------------------------------------------------------------- idea 2: le luci di notte
def idea_notte(dati, path):
    notte = Image.open(NOTTE).convert('RGB'); Pg = notte.width / 360.0
    lati = [([str(c) for c in l.get('iso') or []]) for l in dati.get('luoghi') or []]
    v = VM.camera(vista_per(lati, 1.4) if any(lati) else dati.get('vista'))
    cx, cy, wd = v; cw = wd * Pg; ch = cw * H / W
    x0, y0 = (cx + 180) * Pg - cw / 2, (90 - cy) * Pg - ch / 2
    im = notte.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255
    lum = a.mean(axis=2, keepdims=True)
    a = np.clip(a * 1.25 + np.power(lum, 1.6) * np.array([1.0, .75, .25]) * 1.4, 0, 1)   # luci dorate che brillano, il buio resta buio
    im = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(radius=2, percent=90))
    bagliore = im.filter(ImageFilter.GaussianBlur(9)); im = ImageChops.screen(im, ImageEnhance.Brightness(bagliore).enhance(.6)).convert('RGBA')
    pt = lambda lon, lat: (((lon + 180) * Pg - x0) * W / cw, ((90 - lat) * Pg - y0) * H / ch)
    d = ImageDraw.Draw(im)
    for k, isos in enumerate(lati):
        for xy in VM.anelli_visibili(isos, pt):
            d.line(xy + [xy[0]], fill=(255, 60, 60, 210) if k else (255, 255, 255, 120), width=3)
    scritta = str(dati.get('scritta') or 'WHY SO DARK?').upper()[:20]
    VM.riquadro(im, W * .5, H * .82, scritta, 150 if len(scritta) <= 12 else 115)
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)


# ---------------------------------------------------------------- idea 3: due mondi a un passo
def idea_mondi(dati, path):
    prompt = (str(dati.get('prompt_en') or '') + ' Photorealistic cinematic photograph, dramatic golden light, high detail, wide 16:9, '
              'the image is split exactly in the middle by the border (a wall or a line), strong contrast between the two sides. '
              'The TOP 25% of the image is simple sky, reserved for a title. No text, no letters, no logos, no flags with writing.')
    fal_immagine(prompt, path)
    im = Image.open(path).convert('RGBA').resize((W, H))
    scritta = str(dati.get('scritta') or '').upper()[:22]
    if scritta:
        VM.riquadro(im, W / 2, 125, scritta, 140 if len(scritta) <= 14 else 105, (255, 214, 0))
    im.convert('RGB').resize((1280, 720), Image.LANCZOS).save(path, quality=93)


DOMANDA = """This is the thumbnail of a very successful YouTube video titled "{t}" (channel about why one country is rich and its neighbour is poor).
We make the same video and test 3 NEW thumbnail ideas. Use only TRUE, well-known public data (World Bank, UN). Answer ONLY JSON:
{{"cartellino": {{"luoghi": [{{"nome": "USA", "iso": ["USA"], "prezzo": "$82,000", "ricco": true}}, {{"nome": "LATIN AMERICA", "iso": ["MEX","GTM","HND","SLV","NIC","CRI","PAN","COL","VEN","ECU","PER","BOL","BRA","PRY","URY","ARG","CHL","GUY","SUR","BLZ","CUB","DOM","HTI"], "prezzo": "$9,000", "ricco": false}}],
  "scritta": "2-3 word hook in CAPS, e.g. SAME CONTINENT?", "fonte": "one line: the data used (GDP per capita, year, source)"}},
 "notte": {{"luoghi": [same places and ISO-3 codes: FIRST the rich/lit one, then the poor/dark one], "scritta": "2-3 word hook in CAPS about light vs darkness, e.g. WHY SO DARK?"}},
 "mondi": {{"prompt_en": "40-70 words: a REAL ground-level place at the border between the two places of the video (a real border town or crossing if one exists), left side rich (what wealth looks like there), right side poor (what poverty looks like there), ONE ordinary person standing right on the border line with one foot on each side, looking at the camera, surprised", "scritta": "max 4 words in CAPS with a true number, e.g. 1 STEP = 9X RICHER"}}}}
Rules: "prezzo" = GDP per capita (current US$, rounded, with $ and comma) unless another true price fits the title better; ISO-3 codes of every country of each place;
for a single country video (e.g. Switzerland) use that country and its richest/poorest relevant neighbour; for a world video use the 4-6 richest countries as ONE rich place."""

righe = []
for n, (vid, tit) in enumerate(zip(P0['video_ids'], P0.get('titoli') or [''] * 99), 1):
    try:
        b = VM.http(f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', raw=True)
        loro = Image.open(io.BytesIO(b)).convert('RGB').resize((1280, 720)); loro.save(os.path.join(CART, f'{n}_loro.jpg'), quality=90)
        buf = io.BytesIO(); loro.resize((960, 540)).save(buf, 'JPEG', quality=88)
        piano = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                        {'type': 'text', 'text': DOMANDA.format(t=tit)}])
    except Exception as e:
        print('piano non riuscito', vid, str(e)[:200], flush=True); continue
    for k, (fn, chiave) in enumerate(((idea_cartellino, 'cartellino'), (idea_notte, 'notte'), (idea_mondi, 'mondi')), 1):
        p = os.path.join(CART, f'{n}_{k}.jpg')
        try:
            fn(piano.get(chiave) or {}, p)
        except Exception as e:
            print('idea', k, 'non riuscita per', vid, str(e)[:200], flush=True)
            Image.new('RGB', (1280, 720), (60, 60, 60)).save(p)
    righe.append((n, vid, tit, piano))
    print('fatto', n, tit, json.dumps(piano, ensure_ascii=False)[:300], flush=True)

F = VM.font('Anton-Regular.ttf', 30); F2 = VM.font('Anton-Regular.ttf', 22)
tw, th = 640, 360
S = Image.new('RGB', (tw * 4, (th + 50) * len(righe) + 50), 'white'); d = ImageDraw.Draw(S)
for j, t in enumerate(['LORO', '1 · IL CARTELLINO', '2 · LE LUCI DI NOTTE', '3 · DUE MONDI']):
    d.text((j * tw + 10, 8), t, font=F, fill='black')
M = Image.new('RGB', (4 * 256 + 10, len(righe) * 148 + 10), (15, 15, 15))
for i, (n, vid, tit, piano) in enumerate(righe):
    y = 50 + i * (th + 50)
    d.text((10, y + 6), f'{tit[:70]}   |   dati: {str((piano.get("cartellino") or {}).get("fonte", ""))[:90]}', font=F2, fill='grey')
    for j, k in enumerate(['loro', '1', '2', '3']):
        im = Image.open(os.path.join(CART, f'{n}_{k}.jpg')).convert('RGB')
        S.paste(im.resize((tw, th)), (j * tw, y + 40)); M.paste(im.resize((246, 138), Image.LANCZOS), (10 + j * 256, 10 + i * 148))
S.save(os.path.join(CART, 'confronto.jpg'), quality=85); M.save(os.path.join(CART, 'telefono.jpg'), quality=90)
json.dump([{'n': n, 'id': v, 'titolo': t, 'piano': p} for n, v, t, p in righe], open(os.path.join(CART, 'piano.json'), 'w'), indent=1, ensure_ascii=False)
open(os.path.join(CART, 'costi.txt'), 'w').write('spesa immagini: %.2f $ + Claude ~0,10 $\n' % SPESA['tot'])
print('FATTO', SPESA, flush=True)
