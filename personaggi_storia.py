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
  # ===== RUOLI GENERICI (valgono per tutti i paesi) =====
  'contadino_antico': 'an ancient farmer in a simple beige tunic and straw hat, holding a hoe',
  'contadina_antica': 'an ancient farmer woman in a long simple dress and headscarf, carrying a basket of grain',
  're_antico': 'an ancient king with a golden crown, red royal robe with fur trim and a sceptre, proud expression',
  'regina': 'a queen with a golden crown, an elegant long blue gown and a necklace, dignified expression',
  'sacerdote': 'an ancient priest in long white robes holding a smoking incense bowl, calm expression',
  'mercante': 'a travelling merchant with a turban, colourful robes and a bag of coins, cunning smile',
  'guerriero_barbaro': 'a wild northern barbarian warrior with fur cloak, braided beard and an axe, fierce expression',
  'cavaliere': 'a medieval knight in shining plate armour with a sword and a shield with a simple cross, brave expression',
  'crociato': 'a crusader knight with a white tunic with a red cross over chain mail, a great helm under the arm',
  'esploratore': 'a 1500s explorer captain with a feathered hat, cape, boots and a telescope, adventurous expression',
  'soldato_moschetto': 'an 1700s British redcoat soldier with white cross belts, tall hat and a musket',
  'nobile': 'an 1700s nobleman with a white powdered wig, embroidered coat and a lace collar, arrogant expression',
  'industriale': 'a Victorian industrialist with a black top hat, frock coat, waistcoat with a pocket watch and a cane, smug smile',
  'operaio': 'a 1900s factory worker with a flat cap, rolled-up sleeves, suspenders and a hammer, tired but proud',
  'soldato_ww1': 'a 1915 soldier with a round helmet, khaki uniform and a rifle, worried expression',
  'soldato_ww2': 'a 1940s soldier with a green helmet, field uniform and a backpack, determined expression',
  'soldato_moderno': 'a modern soldier in camouflage uniform with a helmet and a rifle, alert expression',
  'generale': 'a 1900s general with a peaked cap, uniform covered in medals and a moustache, stern expression',
  'politico': 'a 1950s politician in a dark suit and tie giving a speech with one raised hand, confident smile',
  'manifestante': 'a young protester holding a blank cardboard sign with no writing, shouting, raised fist',
  'rifugiato': 'a tired refugee mother carrying a bundle and holding a child by the hand, worried expression',
  'turista': 'a modern tourist with a sun hat, flower shirt, shorts, camera around the neck, amazed expression',
  'uomo_moderno': 'a modern man in a smart suit holding a smartphone, busy expression',
  'donna_moderna': 'a modern young woman in casual clothes with a backpack, curious smile',
  'anziano_narratore': 'a friendly old storyteller with a white beard, round glasses, a cardigan and a book, warm smile',
  # ===== IRAN / PERSIA =====
  'ciro_il_grande': 'Cyrus the Great, ancient Persian king with a tall crenellated golden crown, long curled black beard, purple and gold royal robes',
  'immortale_persiano': 'a Persian Immortal soldier with a long patterned robe, wicker shield, spear and quiver, curled beard',
  'sacerdote_zoroastriano': 'a Zoroastrian priest in white robes with a white mouth veil, tending a small sacred fire',
  'scia_reza_pahlavi': 'Mohammad Reza Shah Pahlavi, the last Shah of Iran, in a white military dress uniform with medals and sash, slicked dark hair',
  'khomeini': 'Ayatollah Ruhollah Khomeini, elderly Iranian cleric with a long white beard, black turban and dark robe, stern expression',
  # ===== AFGHANISTAN =====
  'guerriero_pashtun': 'an Afghan Pashtun tribal warrior with a turban, long shirt, waistcoat, shawl and an old long rifle (jezail)',
  'alessandro_magno': 'Alexander the Great, young Macedonian king with wavy golden hair, bronze cuirass, red cloak and a sword',
  'cavaliere_mongolo': 'a Mongol horse archer with a fur-trimmed hat, padded coat, composite bow and quiver',
  'mujahid_anni80': 'a 1980s Afghan mujahideen fighter with a pakol wool hat, patterned scarf, long shirt and a rifle',
  'soldato_sovietico': 'a Soviet soldier of the 1980s in a khaki uniform, telnyashka striped shirt and a panama hat, with a rifle',
  # ===== INDIA =====
  'contadino_indiano': 'an Indian village farmer with a white dhoti, turban and a wooden plough, tired smile',
  'imperatore_moghul': 'a Mughal emperor in rich silk robes with a jewelled turban and pearl necklaces, holding a rose',
  'maharaja': 'an Indian maharaja with a jewelled turban with a feather, golden embroidered coat and a curved sword',
  'soldato_cipay': 'an 1850s Indian sepoy soldier in a red British-style coat, white turban and a musket',
  'gandhi': 'Mahatma Gandhi, thin elderly man with round glasses, bald head, white homespun shawl and a walking stick, gentle smile',
  'nehru': 'Jawaharlal Nehru, Indian statesman with a white Gandhi cap and a long Nehru jacket with a red rose',
  'regina_vittoria': 'Queen Victoria, short elderly British queen in a black mourning dress with a small crown and white veil, unamused expression',
  # ===== EGITTO =====
  'faraone': 'an Egyptian pharaoh with the striped nemes headdress, golden collar and a crook, serious expression',
  'ramses_ii': 'Ramesses II, mighty Egyptian pharaoh with the blue khepresh war crown, golden collar, bow and kilt',
  'cleopatra': 'Cleopatra VII, Egyptian queen with black braided hair, golden vulture headdress, white dress and gold jewellery',
  'scriba_egizio': 'an ancient Egyptian scribe sitting cross-legged with a papyrus scroll and a reed pen, shaved head',
  'contadino_egizio': 'an ancient Egyptian farmer with a white linen kilt, carrying water jars on a shoulder pole',
  'nasser': 'Gamal Abdel Nasser, Egyptian president of the 1950s with combed-back dark hair and a dark suit, confident pose',
  # ===== ROMA =====
  'legionario': 'a Roman legionary with a red-crested helmet, segmented armour, red tunic, shield and short sword',
  'senatore': 'a Roman senator in a white toga with a purple stripe, holding a scroll, thoughtful expression',
  'giulio_cesare': 'Julius Caesar with a laurel wreath, thin face, receding hair, red general cloak over armour',
  'augusto': 'Emperor Augustus, young Roman emperor with neat short hair, armour with a decorated breastplate and a raised arm',
  # ===== ISRAELE =====
  're_davide': 'King David of ancient Israel with a golden crown, a harp and a purple robe, curly beard',
  'antico_ebreo': 'an ancient Hebrew shepherd with a striped robe, head cloth and a wooden staff',
  'netanyahu': 'Benjamin Netanyahu, Israeli prime minister with grey hair, dark suit and blue tie, serious expression',
  'ben_gurion': 'David Ben-Gurion, Israeli founding leader with wild white hair on the sides of a bald head, open-collar shirt',
  'combattente_palestinese': 'a Palestinian man with a black-and-white keffiyeh scarf around the neck, simple clothes, defiant expression',
  # ===== IMPERO BRITANNICO =====
  'churchill': 'Winston Churchill with a bowler hat, three-piece suit, bow tie and a cigar, bulldog expression',
  'ufficiale_coloniale': 'a British colonial officer with a white pith helmet, khaki uniform and a swagger stick, moustache',
  'marinaio_britannico': 'an 1800s Royal Navy sailor with a striped shirt, flat hat and a rope coil',
  # ===== UCRAINA / RUSSIA =====
  'cosacco': 'a Ukrainian Cossack with a long scalp lock (oseledets), long moustache, wide red trousers and a sabre',
  'zar_russo': 'a Russian tsar with a fur-trimmed golden crown, heavy embroidered robe and a sceptre, bearded',
  'zelensky': 'Volodymyr Zelensky, Ukrainian president with short dark hair and short beard, olive green military-style t-shirt',
  'putin': 'Vladimir Putin, Russian president with thinning short hair, dark suit and tie, cold expression',
  'stalin': 'Joseph Stalin with a thick moustache, combed-back hair and a grey military tunic',
  # ===== LAS VEGAS / USA =====
  'cowboy': 'an American cowboy with a wide brown hat, bandana, leather vest and boots, relaxed grin',
  'nativo_paiute': 'a Paiute Native American man with simple woven and leather clothes and a basket, calm expression',
  'operaio_diga': 'a 1930s construction worker with a yellow hard hat, overalls and a shovel, hard-working expression',
  'gangster_anni50': 'a 1950s casino gangster with a fedora hat, pinstripe suit and a cigar, smug grin',
  'showgirl': 'a 1950s Las Vegas showgirl with a feathered headdress and a sparkly costume, big smile',
  'elvis': 'Elvis Presley in a white rhinestone jumpsuit with a high collar and black pompadour hair, singing pose',
  'bugsy_siegel': 'Bugsy Siegel, 1940s mobster with slicked-back hair, double-breasted suit and a confident smirk',
  # ===== CAPO VERDE =====
  'navigatore_portoghese': 'a 1460s Portuguese navigator with a beret, puffed sleeves, a cape and an astrolabe',
  'pescatore_capoverde': 'a Cape Verdean fisherman with a straw hat, rolled-up trousers and a fishing net, warm smile',
  'cantante_morna': 'a Cape Verdean morna singer, barefoot woman in a simple elegant dress singing with closed eyes',
  'amilcar_cabral': 'Amilcar Cabral, African independence leader with a knitted cap (sumbia), glasses and a short beard',
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

POSE = {   # 2 pose: fermo + reazione (la reazione piu' adatta al ruolo la sceglie l'AI)
  'reazione': ('a strong reaction that fits this character: a ruler or leader points forward giving an order; a warrior raises his weapon '
               'ready to fight; ordinary people look shocked with hands near the face and mouth open; a performer strikes a show pose'),
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
