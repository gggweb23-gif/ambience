#!/usr/bin/env python3
"""
STUDIO ANGOLI (per tutti i canali) — da fare PRIMA di aprire un canale e quando un canale ha il CTR basso.
1) prende i video piu' visti del canale da copiare (feed pubblico YouTube) e le loro copertine
2) Claude guarda ogni copertina: scritta, scena, personaggio, reazione, e la riscrive nei 3 ANGOLI d'attacco
   (stesso argomento e stesso stile del canale, inquadratura diversa)
3) genera le immagini (fal seedream, con tetto di spesa) e ci mette sopra la scritta del competitor
4) foglio di confronto: LORO | A | B | C  + griglia come da telefono
Ingresso: PAYLOAD = {"nome": "roma", "canale_id": "UC...", "n": 5, "max_spesa": 0.60, "stile": "<facoltativo>", "font": "cinzel|anton|lilita",
                     "angoli": {"A": "...", "B": "...", "C": "..."} (facoltativo: se manca valgono i 3 angoli standard)}
Uscita: prove_angoli/<nome>/ (loro_<n>.jpg, <n>_A.jpg ..., confronto.jpg, telefono.jpg, piano.json, costi.txt) salvati nel repository.
"""
import base64, io, json, os, re, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_angoli', P['nome']); os.makedirs(CART, exist_ok=True)
N = int(P.get('n') or 5)
MAX_SPESA = float(P.get('max_spesa', 0.60))
PREZZO = 0.04
SPESA = {'tot': 0.0}
MODELLO = E('MODELLO_AI', '') or 'claude-sonnet-5-5'
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)

ANGOLI = P.get('angoli') or {
    'A': 'FOCUSED CLOSE-UP: ONE single character VERY BIG in the foreground, from the waist up, sharp and detailed, filling about 60% of the image, '
         'with an EXAGGERATED readable reaction; the background is the same place but SIMPLE and softly BLURRED (shallow depth of field), only 2-3 recognizable elements.',
    'B': 'FIRST-PERSON POINT OF VIEW: we see through the eyes of the protagonist; HIS OWN hands and forearms are big in the foreground at the bottom, '
         'holding the key object of the story; the scene opens in front of us, immersive and dramatic.',
    'C': 'FACE TO FACE: TWO characters big in the foreground, from the chest up, facing each other with strongly CONTRASTING expressions that tell the story; '
         'plain flat VIVID single-colour background (no scenery), strong rim light.'}
NOMI = {'A': 'A · PRIMO PIANO A FUOCO', 'B': 'B · TU SEI LI\'', 'C': 'C · FACCIA A FACCIA'}


def get(u, dati=None, h=None, raw=False, timeout=300):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def fal(dati):
    if SPESA['tot'] + PREZZO > MAX_SPESA + 1e-9:
        raise RuntimeError('tetto di spesa %.2f $ raggiunto' % MAX_SPESA)
    SPESA['tot'] += PREZZO   # contata subito: fal fa pagare anche se poi qualcosa va storto
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', dati, h)
    for _ in range(150):
        time.sleep(4)
        st = get(inv['status_url'], h=h)
        if st.get('status') == 'COMPLETED':
            return get(inv['response_url'], h=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('Fal: tempo scaduto')


def claude(img_bytes, testo):
    rr = get('https://api.anthropic.com/v1/messages', {'model': MODELLO, 'max_tokens': 2500, 'messages': [{'role': 'user', 'content': [
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(img_bytes).decode()}},
        {'type': 'text', 'text': testo}]}]}, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
    t = ''.join(b.get('text', '') for b in rr.get('content', []))
    return json.loads(t[t.find('{'): t.rfind('}') + 1])


# 1) video piu' visti del canale (feed pubblico: ultimi 15)
xml = get('https://www.youtube.com/feeds/videos.xml?channel_id=' + P['canale_id'], raw=True).decode()
voci = re.findall(r'<yt:videoId>([\w-]{11})</yt:videoId>.*?<title>(.*?)</title>.*?<media:statistics views="(\d+)"', xml, re.S)
voci = sorted(voci, key=lambda v: -int(v[2]))[:N]
log('video scelti:', [(v[1][:40], v[2]) for v in voci])

# 2) copertine + piano di Claude
piano = []
for k, (vid, tit, views) in enumerate(voci, 1):
    img = None
    for q in ('maxresdefault', 'hqdefault'):
        try:
            img = Image.open(io.BytesIO(get(f'https://i.ytimg.com/vi/{vid}/{q}.jpg', raw=True))).convert('RGB').resize((1280, 720)); break
        except Exception:
            pass
    if img is None:
        continue
    p_loro = os.path.join(CART, 'loro_%d.jpg' % k); img.save(p_loro, quality=90)
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=88)
    domanda = ('This is the thumbnail of a very successful YouTube video titled "' + tit + '". We make a channel on the SAME topics and in the SAME visual style, '
               'but with a recognizable different framing. Read it and answer ONLY JSON: {"testo": "the EXACT words written on the thumbnail, in CAPS", '
               '"stile": "the drawing style in English (lines, colours, light, level of detail), one sentence", '
               + ', '.join('"%s": "the SAME story of this thumbnail rewritten for this framing: %s Describe in English who is there, the exact emotion, the key objects and the place, one or two sentences"' % (a, d)
                           for a, d in ANGOLI.items()) + '}')
    try:
        x = claude(buf.getvalue(), domanda)
    except Exception as e:
        log('piano non riuscito per', vid, str(e)[:150]); continue
    x.update(id=vid, titolo=tit, views=int(views), loro=p_loro)
    piano.append(x); log('piano', k, x.get('testo'))
json.dump(piano, open(os.path.join(CART, 'piano.json'), 'w'), ensure_ascii=False, indent=1)

# 3) immagini dei 3 angoli (la copertina del competitor come riferimento di STILE)
REPO = E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
for k, x in enumerate(piano, 1):
    rif = 'data:image/jpeg;base64,' + base64.b64encode(open(x['loro'], 'rb').read()).decode()
    stile = P.get('stile') or x.get('stile') or ''
    for a in ANGOLI:
        prompt = ('The reference image shows ONLY the drawing style to copy (lines, colours, faces, level of detail): do NOT copy its composition. '
                  'YouTube thumbnail. ' + ANGOLI[a] + ' SCENE: ' + str(x.get(a, '')) + ' STYLE: ' + stile +
                  ' The TOP 25% of the image stays simple (a big title will go there), no faces there. No text, no letters, no numbers, no logos, no watermark.')
        try:
            r = fal({'prompt': prompt, 'image_urls': [rif], 'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1})
            im = Image.open(io.BytesIO(get(r['images'][0]['url'], raw=True))).convert('RGB').resize((1280, 720))
            im.save(os.path.join(CART, '%d_%s_base.jpg' % (k, a)), quality=90); log('immagine', k, a)
        except Exception as e:
            log('immagine', k, a, 'non riuscita:', str(e)[:150])

# 4) scritta + fogli di confronto
FONTI = {'cinzel': ('https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf', 'Black'),
         'anton': ('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', None),
         'lilita': ('https://github.com/google/fonts/raw/main/ofl/lilitaone/LilitaOne-Regular.ttf', None)}
fu, var = FONTI.get(str(P.get('font') or 'cinzel').lower(), FONTI['cinzel'])
FP = os.path.join(CART, '_font.ttf'); open(FP, 'wb').write(get(fu, raw=True))


def F(s):
    f = ImageFont.truetype(FP, s)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


def scritta(im, testo):
    d = ImageDraw.Draw(im); s = 150; f = F(s)
    while d.textlength(testo, font=f) > 1180 and s > 60:   # sempre una riga sola: non copre mai le teste
        s -= 4; f = F(s)
    d.text((640, 18), testo, font=f, fill=(255, 220, 0), stroke_width=max(7, int(s * .1)), stroke_fill=(10, 10, 10), anchor='ma')
    return im


tw, th = 640, 360; col = 1 + len(ANGOLI)
LB = F(26)
S = Image.new('RGB', (tw * col, (th + 40) * len(piano) + 46), 'white'); d = ImageDraw.Draw(S)
M = Image.new('RGB', (246 * col + 10 * (col + 1), (138 + 10) * len(piano) + 10), (15, 15, 15))
for j, t in enumerate(['LORO'] + [NOMI.get(a, a) for a in ANGOLI]):
    d.text((j * tw + 10, 8), t, font=LB, fill='black')
for k, x in enumerate(piano, 1):
    y = 46 + (k - 1) * (th + 40)
    ims = [Image.open(x['loro'])]
    for a in ANGOLI:
        b = os.path.join(CART, '%d_%s_base.jpg' % (k, a))
        im = scritta(Image.open(b).convert('RGB'), str(x.get('testo') or '').upper()) if os.path.exists(b) else Image.new('RGB', (1280, 720), 'grey')
        im.save(os.path.join(CART, '%d_%s.jpg' % (k, a)), quality=92); ims.append(im)
    d.text((10, y + 4), '{:,}'.format(x['views']).replace(',', '.') + ' visualizzazioni', font=LB, fill='grey')
    for j, im in enumerate(ims):
        S.paste(im.resize((tw, th)), (j * tw, y + 36)); M.paste(im.resize((246, 138), Image.LANCZOS), (10 + j * 256, 10 + (k - 1) * 148))
S.save(os.path.join(CART, 'confronto.jpg'), quality=85); M.save(os.path.join(CART, 'telefono.jpg'), quality=90)
os.remove(FP)
open(os.path.join(CART, 'costi.txt'), 'w').write('spesa immagini: %.2f $ (%.2f $ a immagine) + Claude ~0,05 $\n' % (SPESA['tot'], PREZZO))
log('FATTO, spesa immagini %.2f $' % SPESA['tot'])
