#!/usr/bin/env python3
"""
PROVA STILE (per tutti i canali): prima di aprire un canale, genera alcune immagini nello stile del canale da copiare,
con il NOSTRO personaggio, per vedere il risultato e il costo prima di produrre i video.
Ingresso: PAYLOAD = {"nome": "roma", "stile": "...", "personaggio": "...", "scene": ["...", ...],
                     "modelli": ["seedream", "nano"], "riferimenti": ["prove_stile/roma/rif_stile_a.jpg", ...]}
Uscita: prove_stile/<nome>/  (personaggio_<modello>.jpg, <modello>_<n>.jpg, foglio.jpg, costi.txt) salvati nel repository.
"""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = P['nome']
CART = os.path.join('prove_stile', NOME)
os.makedirs(CART, exist_ok=True)
REPO = E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
RIF = ['https://raw.githubusercontent.com/%s/main/%s' % (REPO, r) for r in P.get('riferimenti', [])]
PREZZO = {'seedream': 0.04, 'nano': 0.12}
SPESA = {'tot': 0.0}
MAX_SPESA = float(P.get('max_spesa', 0.5))   # tetto di spesa: oltre questo non parte nessuna immagine


def http(url, dati=None, h=None):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode() or '{}')


def fal(modello, dati):
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


def immagine(mod, prompt, refs, path):
    if SPESA['tot'] + PREZZO[mod] > MAX_SPESA + 1e-9:
        raise RuntimeError('tetto di spesa %.2f $ raggiunto' % MAX_SPESA)
    SPESA['tot'] += PREZZO[mod]   # contata subito: fal fa pagare anche se poi qualcosa va storto
    if mod == 'nano':
        r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
    else:
        r = fal('fal-ai/bytedance/seedream/v4.5/edit', {'prompt': prompt, 'image_urls': refs, 'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1})
    url = r['images'][0]['url']
    urllib.request.urlretrieve(url, path)
    im = Image.open(path).convert('RGB'); im.thumbnail((1920, 1080)); im.save(path, quality=90)
    return url


STILE = P['stile']
SENZA_CORNICE = ' Full-bleed illustration filling the whole image: no screen, no monitor, no TV, no frame or border around it.'
REG_STILE = ('The reference image%s show%s ONLY the DRAWING STYLE to copy (line work, colours, shading, level of detail, how people are drawn): '
             'do NOT copy their exact scene, composition or characters, and never add any logo or text. ' % (('s', '') if len(RIF) > 1 else ('', 's')))
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def per_modello(mod):
    pers = os.path.join(CART, 'personaggio_%s.jpg' % mod)
    scheda = P.get('scheda') or ('Draw a character design sheet of OUR main character, full body, three poses (front, walking, surprised), '
                                 'on a plain light background: ')   # 'scheda' nel payload: come disegnare la scheda del personaggio
    u = immagine(mod, REG_STILE + scheda + P['personaggio'] + '. ' + STILE + SENZA_CORNICE, RIF, pers)
    log(mod, 'personaggio pronto')
    out = [pers]
    for i, sc in enumerate(P['scene'], 1):
        p = os.path.join(CART, '%s_%02d.jpg' % (mod, i))
        try:
            immagine(mod, 'The FIRST reference image is OUR main character: when he appears keep him identical (face, hair, clothes, proportions). '
                     + REG_STILE.replace('reference image', 'other reference image') + 'SCENE: ' + sc + '. ' + STILE + SENZA_CORNICE, [u] + RIF, p)
            out.append(p); log(mod, 'scena', i)
        except Exception as e:
            log(mod, 'scena', i, 'non riuscita:', str(e)[:200])
    return mod, out


with ThreadPoolExecutor(2) as ex:
    fatti = dict(ex.map(per_modello, P.get('modelli', ['seedream'])))
# foglio di confronto: una riga per modello
righe = list(fatti.items()); n = max(len(v) for _, v in righe)
tw, th = 480, 270
S = Image.new('RGB', (tw * n, (th + 30) * len(righe)), 'white'); d = ImageDraw.Draw(S)
for r, (mod, fs) in enumerate(righe):
    for c, f in enumerate(fs):
        im = Image.open(f).convert('RGB'); im.thumbnail((tw, th)); S.paste(im, (c * tw, r * (th + 30) + 30))
    d.text((8, r * (th + 30) + 8), '%s  (%.2f $ a immagine)' % (mod, PREZZO[mod]), fill='black')
S.save(os.path.join(CART, 'foglio.jpg'), quality=85)
open(os.path.join(CART, 'costi.txt'), 'w').write('spesa prova: %.2f $\n' % SPESA['tot'] + ''.join('%s: %.2f $ a immagine\n' % (m, PREZZO[m]) for m in fatti))
log('FATTO, spesa %.2f $' % SPESA['tot'])
