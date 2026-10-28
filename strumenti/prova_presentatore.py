#!/usr/bin/env python3
"""
PROVA PRESENTATORE (per tutti i canali): un volto "presentatore" credibile da mettere in copertina.
Genera N ritratti (fal, con tetto di spesa), toglie lo sfondo e li incolla su una copertina gia' uscita, in piu' posizioni,
poi fa un foglio di confronto: copertina attuale | versioni con il presentatore.
Ingresso: PAYLOAD = {"nome": "rich-borders", "video_id": "<id YouTube della nostra copertina>", "competitor_id": "<id facoltativo>",
                     "persone": ["descrizione 1", "descrizione 2"], "posizioni": ["sinistra", "destra"], "max_spesa": 0.08}
Uscita: prove_presentatore/<nome>/ (presentatore_<n>.png, copertina_<n>_<posizione>.jpg, confronto.jpg, costi.txt) salvati nel repository.
"""
import io, json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageFilter

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_presentatore', P['nome'])
os.makedirs(CART, exist_ok=True)
PREZZO = 0.04   # seedream v4.5 a immagine
MAX_SPESA = float(P.get('max_spesa', 0.08))
SPESA = {'tot': 0.0}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def http(url, dati=None, h=None, raw=False):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def fal(modello, dati):
    if SPESA['tot'] + PREZZO > MAX_SPESA + 1e-9:
        raise RuntimeError('tetto di spesa %.2f $ raggiunto' % MAX_SPESA)
    SPESA['tot'] += PREZZO   # contata subito: fal fa pagare anche se poi qualcosa va storto
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/' + modello, dati, h)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], h=h)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], h=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('Fal: tempo scaduto')


def copertina_yt(vid):
    for q in ('maxresdefault', 'hqdefault'):
        try:
            return Image.open(io.BytesIO(http(f'https://i.ytimg.com/vi/{vid}/{q}.jpg', raw=True))).convert('RGB').resize((1280, 720))
        except Exception:
            pass
    raise RuntimeError('copertina non scaricata: ' + vid)


BASE = ('Photorealistic waist-up portrait photo of {p}. He looks straight into the camera with a warm, confident, trustworthy expression, '
        'like a teacher about to explain something fascinating, slight smile, one hand slightly raised as if explaining. '
        'Soft studio lighting, sharp focus, high detail, natural skin. Plain flat light grey background, nothing else in the image, no text.')

from rembg import remove   # toglie lo sfondo (gratis, gira sul computer di GitHub)
remove(Image.new('RGB', (64, 64), 'white'))   # scarica il modello PRIMA di spendere: se fallisce, non si paga niente

nostra = copertina_yt(P['video_id'])
nostra.save(os.path.join(CART, 'copertina_attuale.jpg'), quality=92)
loro = None
if P.get('competitor_id'):
    try:
        loro = copertina_yt(P['competitor_id']); loro.save(os.path.join(CART, 'copertina_competitor.jpg'), quality=92)
    except Exception as e:
        log('competitor:', e)

righe = []
for n, persona in enumerate(P['persone'], 1):
    try:
        r = fal('fal-ai/bytedance/seedream/v4.5/text-to-image', {'prompt': BASE.format(p=persona), 'image_size': {'width': 1536, 'height': 2048}, 'num_images': 1})
    except Exception as e:
        log('presentatore', n, 'non riuscito:', str(e)[:200]); continue
    foto = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB')
    foto.save(os.path.join(CART, 'foto_%d.jpg' % n), quality=90)
    ritaglio = remove(foto)   # RGBA senza sfondo
    bb = ritaglio.getbbox(); ritaglio = ritaglio.crop(bb)
    ritaglio.save(os.path.join(CART, 'presentatore_%d.png' % n))
    log('presentatore', n, 'pronto')
    riga = []
    for pos in P.get('posizioni', ['sinistra', 'destra']):
        im = nostra.copy().convert('RGBA')
        alto = int(720 * .92); pr = ritaglio.resize((int(ritaglio.width * alto / ritaglio.height), alto), Image.LANCZOS)
        # contorno bianco + ombra: stacca il presentatore dalla mappa (come le copertine con persone che fanno CTR alto)
        a = pr.split()[3]
        bordo = a.filter(ImageFilter.MaxFilter(13))
        ombra = Image.new('RGBA', pr.size, (0, 0, 0, 0)); ombra.putalpha(a.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * .6)))
        x = 0 if pos == 'sinistra' else 1280 - pr.width
        x = max(-int(pr.width * .08), min(x, 1280 - pr.width + int(pr.width * .08)))
        y = 720 - alto
        im.alpha_composite(ombra, (x + 10, y + 6))
        bianco = Image.new('RGBA', pr.size, (255, 255, 255, 255)); bianco.putalpha(bordo)
        im.alpha_composite(bianco, (x, y)); im.alpha_composite(pr, (x, y))
        p = os.path.join(CART, 'copertina_%d_%s.jpg' % (n, pos))
        im.convert('RGB').save(p, quality=92); riga.append(p)
    righe.append(riga)

# foglio di confronto: prima riga attuale (+ competitor), poi una riga per presentatore
tw, th = 640, 360
prima = [('attuale', nostra)] + ([('competitor', loro)] if loro else [])
col = max([len(prima)] + [len(r) for r in righe])
S = Image.new('RGB', (tw * col, (th + 34) * (1 + len(righe))), 'white'); d = ImageDraw.Draw(S)
for c, (t, im) in enumerate(prima):
    S.paste(im.resize((tw, th)), (c * tw, 34)); d.text((c * tw + 8, 10), t.upper(), fill='black')
for r, riga in enumerate(righe, 1):
    for c, f in enumerate(riga):
        S.paste(Image.open(f).resize((tw, th)), (c * tw, r * (th + 34) + 34)); d.text((c * tw + 8, r * (th + 34) + 10), os.path.basename(f), fill='black')
S.save(os.path.join(CART, 'confronto.jpg'), quality=88)
open(os.path.join(CART, 'costi.txt'), 'w').write('spesa prova: %.2f $ (%.2f $ a ritratto)\n' % (SPESA['tot'], PREZZO))
log('FATTO, spesa %.2f $' % SPESA['tot'])
