#!/usr/bin/env python3
"""
MULTICHANNEL - Kit personaggi per il canale Storia dei Paesi.
1) crea un personaggio "modello" che fissa lo stile (stesso stile degli sfondi);
2) crea tutti gli altri partendo dal modello (stesso tratto, stesse proporzioni, stessi colori);
3) scontorna (sfondo trasparente) e salva PNG in kit_storia/ + un foglio di anteprima.
"""
import json, os, time, urllib.request
from PIL import Image, ImageDraw

OUT = os.path.join(os.getcwd(), 'kit_storia')
STILE = ('High-quality 2D cartoon character for an animated history video, same style as a modern illustrated history book: '
         'clean confident black ink outlines of medium thickness, flat warm colours with soft cel shading, slightly exaggerated '
         'friendly proportions (big head about one third of the body, expressive eyes and eyebrows), clear readable silhouette. '
         'Full body from head to feet, standing on nothing, centered, three-quarter view facing the viewer. '
         'Plain pure white background, no ground, no shadow on the floor, no other objects, no text, no letters, no logo.')
MODELLO = 'A medieval European peasant man in his thirties with a brown tunic, rope belt and leather shoes, friendly smile.'
PERSONAGGI = {
  # --- antichità
  'contadino_antico': 'an ancient farmer in a simple beige tunic and straw hat, holding a hoe',
  'contadina_antica': 'an ancient farmer woman in a long simple dress and headscarf, carrying a basket of grain',
  're_antico': 'an ancient king with a golden crown, red royal robe with fur trim and a sceptre, proud expression',
  'regina': 'a queen with a golden crown, an elegant long blue gown and a necklace, dignified expression',
  'faraone': 'an Egyptian pharaoh with the striped nemes headdress, golden collar and a crook, serious expression',
  'sacerdote': 'an ancient priest in long white robes holding a smoking incense bowl, calm expression',
  'legionario': 'a Roman legionary with a red-crested helmet, segmented armour, red tunic, shield and short sword',
  'senatore': 'a Roman senator in a white toga with a purple stripe, holding a scroll, thoughtful expression',
  'guerriero_barbaro': 'a wild northern barbarian warrior with fur cloak, braided beard and an axe, fierce expression',
  'mercante': 'a travelling merchant with a turban, colourful robes and a bag of coins, cunning smile',
  # --- medioevo / età moderna
  'cavaliere': 'a medieval knight in shining plate armour with a sword and a shield with a simple cross, brave expression',
  'samurai': 'a Japanese samurai in lacquered armour with a horned helmet and a katana, fierce expression',
  'shogun': 'a Japanese shogun in rich silk robes and a black court hat, stern expression, arms crossed',
  'imperatore_cinese': 'a Chinese emperor in a yellow dragon robe and a flat imperial crown with beads, solemn expression',
  'monaco': 'a Buddhist monk with a shaved head and orange robes, holding prayer beads, serene expression',
  'esploratore': 'a 1500s explorer captain with a feathered hat, cape, boots and a telescope, adventurous expression',
  'pirata': 'a pirate with a tricorn hat, eye patch, striped shirt and a cutlass, mischievous grin',
  'soldato_moschetto': 'an 1700s soldier with a red coat, white cross belts, tall hat and a musket',
  'nobile': 'an 1700s nobleman with a white powdered wig, embroidered coat and a lace collar, arrogant expression',
  # --- 1800-1900
  'industriale': 'a Victorian industrialist with a black top hat, frock coat, waistcoat with a pocket watch and a cane, smug smile',
  'operaio': 'a 1900s factory worker with a flat cap, rolled-up sleeves, suspenders and a hammer, tired but proud',
  'cowboy': 'an American cowboy with a wide brown hat, bandana, leather vest and boots, relaxed grin',
  'nativo_americano': 'a Native American man with a feather in his hair, fringed leather clothes and a bow, calm proud expression',
  'cercatore_oro': 'a gold prospector with a scruffy beard, battered hat, pickaxe and a pan with gold nuggets, excited expression',
  'soldato_ww1': 'a 1915 soldier with a round helmet, khaki uniform and a rifle, worried expression',
  'soldato_ww2': 'a 1940s soldier with a green helmet, field uniform and a backpack, determined expression',
  'generale': 'a 1900s general with a peaked cap, uniform covered in medals and a moustache, stern expression',
  'politico': 'a 1950s politician in a dark suit and tie giving a speech with one raised hand, confident smile',
  'operaio_diga': 'a 1930s construction worker with a yellow hard hat, overalls and a shovel, hard-working expression',
  # --- oggi e generici
  'turista': 'a modern tourist with a sun hat, flower shirt, shorts, camera around the neck, amazed expression',
  'uomo_moderno': 'a modern businessman in a smart suit holding a smartphone, busy expression',
  'donna_moderna': 'a modern young woman in casual clothes with a backpack, curious smile',
  'bambino': 'a small child in simple clothes, big curious eyes, pointing at something',
  'anziano_narratore': 'a friendly old storyteller with a white beard, round glasses, a cardigan and a book, warm smile',
  'folla_contadini': 'a small group of three poor peasants in ragged clothes standing together, angry and protesting with raised fists',
  'esercito': 'a tight group of five soldiers in matching uniforms marching in a line, side view',
}

def http_json(url, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    h = {'Content-Type': 'application/json'} if data is not None else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=120) as r:
        return json.loads(r.read().decode() or '{}')

def fal(modello, dati):
    h = {'Authorization': 'Key ' + os.environ['FAL_KEY']}
    inv = http_json('https://queue.fal.run/' + modello, dati, h)
    for _ in range(120):
        time.sleep(5)
        st = http_json(inv['status_url'], headers=h)
        if st.get('status') == 'COMPLETED':
            return http_json(inv['response_url'], headers=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')

def scarica(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120) as r, open(path, 'wb') as f:
        f.write(r.read())

def scontorna(url, nome):
    sc = fal('fal-ai/birefnet', {'image_url': url})
    p = os.path.join(OUT, nome + '.png')
    scarica((sc.get('image') or {}).get('url') or url, p)
    im = Image.open(p).convert('RGBA'); bb = im.getbbox()
    if bb: im = im.crop(bb)
    im.save(p)
    print('fatto', nome, im.size, flush=True)
    return p

POSE = {
  'indica': 'explaining something: one arm raised, pointing with the index finger to the side, mouth open as if talking',
  'sorpreso': 'shocked and surprised: both hands up near the face, eyes wide open, mouth wide open, leaning slightly back',
  'azione': 'in action, doing what this character typically does (walking, fighting, working or carrying something), dynamic pose',
}
from concurrent.futures import ThreadPoolExecutor
RIS = '1K'

def personaggio(nome, desc):
    try:
        if os.path.exists(os.path.join(OUT, nome + '_fermo.png')):
            print('gia fatto', nome, flush=True); return
        r = fal('fal-ai/nano-banana-2/edit', {
            'prompt': ('Draw a NEW character in EXACTLY the same drawing style as the attached image: same line thickness, same colouring and '
                       'shading, same head-to-body proportions, same eye style. The new character is ' + desc + ', standing relaxed. ' + STILE),
            'image_urls': [URL_BASE], 'aspect_ratio': '3:4', 'resolution': RIS, 'output_format': 'png', 'num_images': 1})
        url = r['images'][0]['url']
        scontorna(url, nome + '_fermo')
        for p, dp in POSE.items():
            try:
                q = fal('fal-ai/nano-banana-2/edit', {
                    'prompt': ('The SAME character as in the attached image: keep exactly the same face, hair, body, clothes, colours, accessories '
                               'and drawing style. Only change the pose: ' + dp + '. ' + STILE),
                    'image_urls': [url], 'aspect_ratio': '3:4', 'resolution': RIS, 'output_format': 'png', 'num_images': 1})
                scontorna(q['images'][0]['url'], nome + '_' + p)
            except Exception as e:
                print('NON riuscita posa', nome, p, e, flush=True)
    except Exception as e:
        print('NON riuscito', nome, e, flush=True)

os.makedirs(OUT, exist_ok=True)
base = fal('fal-ai/nano-banana-2', {'prompt': MODELLO + ' ' + STILE, 'aspect_ratio': '3:4', 'resolution': RIS, 'output_format': 'png', 'num_images': 1})
URL_BASE = base['images'][0]['url']
scontorna(URL_BASE, '00_modello')
SOLO = [x.strip() for x in os.environ.get('SOLO', '').split(',') if x.strip()]   # prova: solo questi personaggi
scelti = {k: v for k, v in PERSONAGGI.items() if not SOLO or k in SOLO}
print('personaggi da fare:', list(scelti), flush=True)
with ThreadPoolExecutor(max_workers=5) as ex:
    list(ex.map(lambda kv: personaggio(*kv), scelti.items()))

# foglio di anteprima su scacchiera
files = sorted(f for f in os.listdir(OUT) if f.endswith('.png'))
cols, cw, ch = 12, 220, 300
S = Image.new('RGB', (cols * cw, ((len(files) + cols - 1) // cols) * ch), 'white')
d = ImageDraw.Draw(S)
for i, f in enumerate(files):
    x, y = (i % cols) * cw, (i // cols) * ch
    for a in range(0, cw, 20):
        for b in range(0, ch - 30, 20):
            if (a // 20 + b // 20) % 2: d.rectangle((x + a, y + b, x + a + 19, y + b + 19), fill=(232, 232, 232))
    im = Image.open(os.path.join(OUT, f)); im.thumbnail((cw - 20, ch - 50))
    S.paste(im, (x + (cw - im.width) // 2, y + (ch - 30 - im.height) // 2), im)
    d.text((x + 8, y + ch - 24), f[:-4], fill='black')
S.save(os.path.join(OUT, '_anteprima.jpg'), quality=85)
print(len(files), 'personaggi')
