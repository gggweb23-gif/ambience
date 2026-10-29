#!/usr/bin/env python3
"""
PROVA TAVOLA (per tutti i canali): UNA immagine generata = tavola 2x2 con 4 inquadrature diverse della stessa scena,
tagliata in 4 immagini separate (4 immagini al prezzo di una). Serve a verificare la qualita' prima di usarla nei video.
Ingresso: PAYLOAD = {"nome": "...", "scene": ["..."], "stile": "...", "riferimenti": ["percorso/repo.jpg"], "max_spesa": 0.08}
Uscita: prove_tavola/<nome>/ (tavola_<n>.jpg, <n>_1..4.jpg, foglio.jpg, costi.txt)
"""
import base64, io, json, os, time, urllib.request
from PIL import Image, ImageDraw

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_tavola', P['nome']); os.makedirs(CART, exist_ok=True)
PREZZO, MAX = 0.04, float(P.get('max_spesa', 0.08)); SPESA = {'tot': 0.0}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read(); return b if raw else json.loads(b.decode() or '{}')


def fal(dati):
    if SPESA['tot'] + PREZZO > MAX + 1e-9:
        raise RuntimeError('tetto di spesa raggiunto')
    SPESA['tot'] += PREZZO
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', dati, h)
    for _ in range(150):
        time.sleep(4); st = get(inv['status_url'], h=h)
        if st.get('status') == 'COMPLETED':
            return get(inv['response_url'], h=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')


refs = ['data:image/jpeg;base64,' + base64.b64encode(open(r, 'rb').read()).decode() for r in P.get('riferimenti', [])]
TAVOLA = ('A 2x2 STORYBOARD SHEET: the image is divided into FOUR equal panels (top-left, top-right, bottom-left, bottom-right) separated by thin straight white lines, '
          'each panel a complete 16:9 frame of the SAME moment with the SAME characters, clothes and place, but a DIFFERENT shot: '
          'panel 1 wide establishing shot of the whole scene; panel 2 close-up of the main character face with a strong emotion; '
          'panel 3 detail close-up of hands or the key object; panel 4 a different character reacting, or the scene from another angle. '
          'The reference images show ONLY the drawing style to copy. No text, no letters, no numbers, no panel borders other than the thin white dividing lines. ')
fatti = []
for n, sc in enumerate(P['scene'], 1):
    try:
        r = fal({'prompt': TAVOLA + 'SCENE: ' + sc + ' STYLE: ' + P.get('stile', ''), 'image_urls': refs, 'image_size': {'width': 3840, 'height': 2160}, 'num_images': 1})
        im = Image.open(io.BytesIO(get(r['images'][0]['url'], raw=True))).convert('RGB')
        log('tavola', n, im.size)
        im.resize((1920, 1080)).save(os.path.join(CART, 'tavola_%d.jpg' % n), quality=88)
        W, H = im.size; m = int(W * .006)   # taglio con un piccolo margine per togliere le linee bianche
        for k, (x, y) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)], 1):
            q = im.crop((x * W // 2 + m, y * H // 2 + m, (x + 1) * W // 2 - m, (y + 1) * H // 2 - m)).resize((1920, 1080), Image.LANCZOS)
            p = os.path.join(CART, '%d_%d.jpg' % (n, k)); q.save(p, quality=90); fatti.append(p)
    except Exception as e:
        log('tavola', n, 'non riuscita:', str(e)[:200])
S = Image.new('RGB', (960 * 4, 540 * max(1, len(fatti) // 4)), 'white')
for i, f in enumerate(fatti):
    S.paste(Image.open(f).resize((960, 540)), ((i % 4) * 960, (i // 4) * 540))
S.save(os.path.join(CART, 'foglio.jpg'), quality=85)
open(os.path.join(CART, 'costi.txt'), 'w').write('spesa: %.2f $ (%d tavole, %d immagini)\n' % (SPESA['tot'], len(fatti) // 4, len(fatti)))
log('FATTO %.2f $' % SPESA['tot'])
