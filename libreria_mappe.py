#!/usr/bin/env python3
"""
RICH BORDERS - Libreria di personaggi, oggetti e suoni (si crea UNA volta, poi la usano tutti i video).

Come il competitor: piccoli personaggi e oggetti illustrati (stile gioco di strategia, cartone con un filo di 3D)
che compaiono sulla mappa, e suoni veri (monete, navi, spade, folla...).
- Immagini: Nano Banana 2 su fondo bianco -> scontorno (birefnet) -> PNG trasparente rifilato (libreria_mappe/img/<nome>.png).
- Suoni: ElevenLabs "sound effects" (libreria_mappe/suoni/<nome>.mp3).
- Ripartibile: quello che c'e' gia' non si rifa' (si paga solo quello che manca). MASSIMO = tetto di immagini nuove per giro.
Costo indicativo: ~0,09 $ a immagine, suoni pochi crediti ElevenLabs. Una volta sola.
Uscita anche: libreria_mappe/anteprima.jpg (tutte le immagini in una griglia) e libreria_mappe/indice.json.
Chiavi: FAL_KEY, ELEVENLABS_API_KEY.
"""
import io, json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
BASE = os.path.join(os.getcwd(), 'libreria_mappe')
IMG, SUONI = os.path.join(BASE, 'img'), os.path.join(BASE, 'suoni')
MASSIMO = int(E('MASSIMO', '') or 999)

STILE = ('Single isolated game asset, cute but detailed 2D cartoon illustration with soft 3D shading, like a token on a strategy-game map '
         '(Civilization / Age of Empires icon style): clean bold shapes, warm saturated colours, soft dark outline, gentle highlight on top, '
         'a small soft shadow under it. Seen from the front, slightly from above. The WHOLE subject is visible and centred, with empty margin around it. '
         'Pure plain WHITE background, nothing else. No text, no letters, no numbers, no logo, no frame, no ground scene.')

# nome: (categoria, soggetto). La categoria decide il suono che parte quando compare nel video.
VISIVI = {
    # personaggi (si usano anche in gruppo: "folla")
    'conquistador': ('persona', 'a Spanish conquistador in a steel morion helmet and breastplate holding a halberd'),
    'colonist': ('persona', 'an English colonial farmer in a 1700s brown coat and hat holding a hoe'),
    'native_worker': ('persona', 'an Andean indigenous worker in a woven poncho carrying a heavy basket of ore on his back'),
    'miner': ('persona', 'a tired colonial miner with a pickaxe and a small lamp, dusty clothes'),
    'king': ('persona', 'a European king with a golden crown, red royal robe with ermine and a sceptre'),
    'merchant': ('persona', 'a wealthy 18th-century merchant in a fine coat holding a bag of gold coins'),
    'landowner': ('persona', 'a rich colonial landowner (hacendado) in a wide hat and fine clothes, arms crossed'),
    'soldier': ('persona', 'a 19th-century infantry soldier in a blue uniform with a musket'),
    'worker': ('persona', 'a 1900s factory worker in overalls and a flat cap holding a wrench'),
    'voter': ('persona', 'an ordinary citizen dropping a paper ballot into a wooden ballot box'),
    'student': ('persona', 'a child student with a school book and a small satchel'),
    'sailor': ('persona', 'an 18th-century sailor with a striped shirt and a rope over his shoulder'),
    'politician': ('persona', 'a politician in a dark suit giving a speech behind a small podium'),
    'banker': ('persona', 'a banker in a black suit and top hat holding a stack of banknotes'),
    'family': ('persona', 'a small poor peasant family (father, mother, child) in simple clothes'),
    # oggetti
    'treasure_chest': ('monete', 'an open wooden treasure chest overflowing with gold coins and silver, glowing'),
    'gold_coins': ('monete', 'a big pile of shiny gold coins'),
    'silver_bars': ('monete', 'a stack of shiny silver ingots'),
    'money_bag': ('monete', 'a fat brown money bag tied with rope, a dollar sign stitched on it, coins spilling'),
    'banknotes': ('monete', 'a thick stack of green banknotes'),
    'galleon': ('nave', 'a Spanish treasure galleon with full white sails and red-yellow flags'),
    'cargo_ship': ('nave', 'a modern cargo ship loaded with colourful containers'),
    'steam_train': ('treno', 'an old black steam locomotive with a puff of white smoke'),
    'mine': ('lavoro', 'a mountain mine entrance with wooden beams and a cart full of silver ore'),
    'factory': ('lavoro', 'a red-brick factory with chimneys and smoke'),
    'farm': ('lavoro', 'a small farm plot with green crops and a wooden fence'),
    'hacienda': ('lavoro', 'a big colonial hacienda manor house with a red tile roof'),
    'cabin': ('casa', 'a small wooden log cabin of a pioneer family'),
    'school': ('casa', 'a little red public schoolhouse with a bell tower'),
    'church': ('campana', 'a white colonial baroque church with a bell tower'),
    'parliament': ('legge', 'a classical government building with columns and a dome'),
    'scroll_law': ('legge', 'an old parchment scroll of law with a red wax seal'),
    'ballot_box': ('legge', 'a wooden ballot box with a paper ballot going in'),
    'crown': ('monete', 'a golden royal crown with red jewels'),
    'cannon': ('guerra', 'an old bronze cannon on wooden wheels'),
    'swords': ('guerra', 'two crossed steel swords'),
    'oil_derrick': ('lavoro', 'an oil derrick pump jack with a small black oil puddle'),
    'sugar_cane': ('lavoro', 'a bundle of green sugar cane stalks'),
    'coffee_sack': ('lavoro', 'a jute sack full of coffee beans'),
    'cattle': ('lavoro', 'a brown cow standing'),
    'hourglass': ('tempo', 'an antique wooden hourglass with golden sand'),
    'chart_down': ('calo', 'a red 3D arrow chart going down'),
    'chart_up': ('crescita', 'a green 3D arrow chart going up'),
}

# suoni (ElevenLabs sound effects): nome -> (descrizione, secondi)
SUONI_LISTA = {
    'monete': ('a handful of gold coins clinking and dropping into a pile, crisp and satisfying', 1.5),
    'cassa': ('old mechanical cash register ching sound', 1.2),
    'nave': ('wooden sailing ship creaking with soft ocean waves and a distant seagull', 2.5),
    'treno': ('short steam train whistle and chugging', 2.0),
    'lavoro': ('pickaxe hitting rock twice in a mine', 1.5),
    'casa': ('soft wooden knock and a door creak', 1.2),
    'campana': ('single small church bell ring, warm', 2.0),
    'legge': ('heavy rubber stamp thud on paper, official', 1.0),
    'guerra': ('two swords clashing, short metallic', 1.2),
    'persona': ('soft pop with a short crowd murmur', 1.2),
    'folla': ('medium crowd of people murmuring, historical market', 2.5),
    'tempo': ('clock ticking quickly', 1.5),
    'calo': ('descending cartoon slide whistle, short', 1.2),
    'crescita': ('rising magical chime, positive, short', 1.2),
    'alza': ('deep rumble of stone rising from the ground, short', 1.8),
    'carta': ('paper map unfolding rustle', 1.2),
}


def http(url, data=None, headers=None, timeout=300, raw=False):
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, dict) else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}


def fal(modello, dati):
    inv = http('https://queue.fal.run/' + modello, dati, FAL)
    for _ in range(150):
        time.sleep(3)
        st = http(inv['status_url'], headers=FAL)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], headers=FAL)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')


def visivo(nome):
    cat, sogg = VISIVI[nome]
    out = os.path.join(IMG, nome + '.png')
    for tent in range(2):
        try:
            r = fal('fal-ai/nano-banana-2', {'prompt': f'{sogg.capitalize()}. {STILE}', 'aspect_ratio': '1:1', 'resolution': '1K',
                                            'output_format': 'png', 'num_images': 1})
            url = r['images'][0]['url']
            sc = fal('fal-ai/birefnet', {'image_url': url})
            im = Image.open(io.BytesIO(http((sc.get('image') or {}).get('url') or url, raw=True))).convert('RGBA')
            bb = im.getchannel('A').point(lambda v: 255 if v > 20 else 0).getbbox()
            if bb:
                im = im.crop(bb)
            im.thumbnail((512, 512), Image.LANCZOS)
            im.save(out)
            print('fatta:', nome, im.size, flush=True)
            return nome
        except Exception as e:
            print('non riuscita', nome, str(e)[:150], flush=True)
    return None


def suono(nome):
    testo, sec = SUONI_LISTA[nome]
    out = os.path.join(SUONI, nome + '.mp3')
    try:
        b = http('https://api.elevenlabs.io/v1/sound-generation', {'text': testo, 'duration_seconds': sec, 'prompt_influence': 0.5},
                 {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, raw=True)
        open(out, 'wb').write(b); print('suono:', nome, len(b), 'byte', flush=True)
    except Exception as e:
        print('suono non riuscito', nome, str(e)[:200], flush=True)


def main():
    os.makedirs(IMG, exist_ok=True); os.makedirs(SUONI, exist_ok=True)
    mancano = [n for n in VISIVI if not os.path.exists(os.path.join(IMG, n + '.png'))][:MASSIMO]
    print(f'immagini da fare: {len(mancano)} (circa {len(mancano) * 0.09:.2f} $)', flush=True)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(visivo, mancano))
    for n in SUONI_LISTA:
        if not os.path.exists(os.path.join(SUONI, n + '.mp3')):
            suono(n)
    indice = {'immagini': {n: VISIVI[n][0] for n in VISIVI if os.path.exists(os.path.join(IMG, n + '.png'))},
              'suoni': [n for n in SUONI_LISTA if os.path.exists(os.path.join(SUONI, n + '.mp3'))]}
    json.dump(indice, open(os.path.join(BASE, 'indice.json'), 'w'), indent=1)
    # anteprima: griglia con nome
    nomi = list(indice['immagini']); col = 8; cel = 240
    G = Image.new('RGB', (col * cel, ((len(nomi) + col - 1) // col) * (cel + 30)), (60, 120, 170)); d = ImageDraw.Draw(G)
    for i, n in enumerate(nomi):
        im = Image.open(os.path.join(IMG, n + '.png')); im.thumbnail((cel - 20, cel - 20))
        x, y = (i % col) * cel, (i // col) * (cel + 30)
        G.paste(im, (x + (cel - im.width) // 2, y + (cel - im.height) // 2), im); d.text((x + 8, y + cel + 6), n, fill='white')
    G.save(os.path.join(BASE, 'anteprima.jpg'), quality=88)
    print('libreria:', len(nomi), 'immagini,', len(indice['suoni']), 'suoni', flush=True)


if __name__ == '__main__':
    main()
