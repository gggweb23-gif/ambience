#!/usr/bin/env python3
"""
AGORA OF SAGES - Libreria di immagini AI riutilizzabile (si crea UNA volta, poi la usano tutti i video).

Stile "Stoic Journal": film still fotorealistici, scuri, cinematografici (statue di marmo, figure incappucciate,
guerrieri, citta' antiche al tramonto, luna tra le colonne, tempeste, candele e pergamene...).
- Nano Banana 2 (testo -> immagine), 16:9. Risoluzione: RISOLUZIONE = 1K (~0,08 $) o 2K (~0,12 $).
- Ripartibile: le immagini gia' presenti in libreria_agora/ non si rifanno (si paga solo quello che manca).
- MASSIMO = tetto di immagini nuove per questo giro (es. 10 per una prova).
- Controllo Claude Haiku (facoltativo, CONTROLLO=SI): scarta immagini con scritte, mani/volti deformi, oggetti moderni; una seconda prova.
Uscita: libreria_agora/<id>.jpg (2400x1350, cosi' il movimento lento non perde qualita') + libreria_agora/indice.json
[{file, descrizione, emozione (ambra|notte|tempesta|alba), soggetto}].
Chiavi: FAL_KEY, ANTHROPIC_API_KEY (solo per il controllo).
"""
import base64, io, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

E = os.environ.get
CARTELLA = os.path.join(os.getcwd(), 'libreria_agora')
RISOLUZIONE = (E('RISOLUZIONE', '') or '1K').strip().upper()
MASSIMO = int(E('MASSIMO', '') or 999)
CONTROLLO = (E('CONTROLLO', '') or 'SI').strip().upper() == 'SI'
PREZZO = 0.12 if RISOLUZIONE == '2K' else 0.08

STILE = ('Photorealistic cinematic film still, dark stoic philosophy atmosphere, dramatic chiaroscuro lighting, deep crushed blacks, '
         'low saturation, subtle film grain, epic and contemplative mood, shallow depth of field, 16:9 widescreen composition. '
         'Absolutely no text, no letters, no inscriptions, no logo, no watermark, no frame, nothing modern (no phones, cars, electric lights, modern buildings).')

LUCE = {
    'ambra': 'warm amber and golden light, glowing embers, fire and sunset tones',
    'notte': 'cold night blue and teal moonlight, deep shadows',
    'tempesta': 'grey stormy desaturated light, dark clouds, rain or mist',
    'alba': 'soft pale dawn light, gentle mist, calm muted tones',
}

# id, soggetto, emozione, descrizione (inglese, per il prompt e per la scelta nel video)
SOGGETTI = [
    # statue di filosofi (volti diversi, mai un filosofo preciso: vanno bene per tutti i video)
    ('statua_pensatore_profilo', 'statua', 'ambra', 'side profile of a marble statue of a bearded ancient Greek philosopher, eyes lowered in thought, city at sunset blurred behind'),
    ('statua_mano_mento', 'statua', 'notte', 'marble statue of a bearded philosopher resting his chin on his hand, deep in thought, moonlit temple behind'),
    ('statua_busto_buio', 'statua', 'tempesta', 'close-up of the marble bust of a stern bearded sage, cracks in the marble, dark storm clouds behind'),
    ('statua_occhi_chiusi', 'statua', 'alba', 'marble statue of an old philosopher with closed eyes, serene, morning mist around him'),
    ('statua_seduta_trono', 'statua', 'ambra', 'marble statue of a philosopher seated on a stone throne inside a dark temple, candle light, embers in the air'),
    ('statua_pergamena', 'statua', 'ambra', 'marble statue of a sage holding an open scroll, reading, warm oil lamp light'),
    ('statua_spalle_citta', 'statua', 'ambra', 'marble statue seen from behind on a balcony overlooking an ancient city at golden sunset'),
    ('statua_pioggia', 'statua', 'tempesta', 'marble statue of a philosopher standing calm under heavy rain among ruins, water running on the marble'),
    ('statua_luna_colonne', 'statua', 'notte', 'marble statue of a muscular philosopher seen from behind between temple columns, full moon in a blue night sky'),
    ('statua_volto_crepe', 'statua', 'tempesta', 'extreme close-up of a cracked marble face of an ancient thinker, intense gaze, dust in the air'),
    ('statua_dito_tempia', 'statua', 'notte', 'marble statue of a philosopher touching his temple with one finger, dark background with grey smoke'),
    ('statua_braccia_conserte', 'statua', 'ambra', 'marble statue of a strong bearded philosopher with crossed arms, confident, fire glow behind'),
    # guerrieri e figure forti
    ('guerriero_fuoco', 'guerriero', 'ambra', 'muscular marble warrior statue standing among flames and smoke, ancient column beside him'),
    ('guerriero_elmo', 'guerriero', 'tempesta', 'ancient Greek hoplite statue with crested helmet and shield, standing alone, stormy sky'),
    ('guerriero_inginocchiato', 'guerriero', 'notte', 'marble warrior kneeling with head bowed, sword planted in the ground, moonlight'),
    ('guerriero_schiena', 'guerriero', 'alba', 'muscular marble statue seen from behind looking at a misty valley at dawn'),
    ('gladiatore_arena', 'guerriero', 'ambra', 'lone gladiator statue in an empty ancient arena at sunset, dust in the air'),
    ('ercole_fatica', 'guerriero', 'tempesta', 'marble statue of a herculean man carrying a heavy stone on his shoulders, grey storm light'),
    # figure incappucciate e persone antiche (mai volti moderni)
    ('incappucciato_trono', 'incappucciato', 'ambra', 'hooded robed figure seated on a stone throne in a dark hall, face in shadow, warm torch light'),
    ('incappucciato_corridoio', 'incappucciato', 'notte', 'hooded figure walking alone down a long corridor of columns, blue moonlight, mist on the floor'),
    ('incappucciato_scogliera', 'incappucciato', 'tempesta', 'hooded figure standing on a cliff above a stormy sea, cloak moving in the wind'),
    ('incappucciato_candela', 'incappucciato', 'ambra', 'hooded monk-like figure writing by a single candle in a dark stone room'),
    ('uomo_toga_finestra', 'figura', 'alba', 'man in an ancient toga standing at a large stone window looking at mountains at dawn, seen from behind'),
    ('uomo_toga_citta', 'figura', 'ambra', 'man in a toga standing at an open window above an ancient Greek city at sunset, silhouette'),
    ('vecchio_saggio_fuoco', 'figura', 'ambra', 'old bearded sage in ancient robes sitting by a small fire at night, face lit by the flames'),
    ('figura_sentiero', 'figura', 'alba', 'lone traveler in ancient robes walking on a stone path toward a temple in the morning mist'),
    ('figura_mare', 'figura', 'notte', 'figure in a cloak sitting on rocks watching a dark sea under the stars'),
    ('figura_scalinata', 'figura', 'tempesta', 'robed figure climbing long stone steps toward a temple under dark clouds'),
    # citta' antiche
    ('atene_tramonto', 'citta', 'ambra', 'aerial view of ancient Athens with the Parthenon at golden sunset, smoke and haze'),
    ('roma_foro_notte', 'citta', 'notte', 'ancient Roman forum at night with torches, columns and temples, blue sky with stars'),
    ('roma_alba_nebbia', 'citta', 'alba', 'ancient Rome at dawn seen from a hill, mist between the temples and domes'),
    ('citta_tempesta', 'citta', 'tempesta', 'ancient Greek city under a dramatic storm, lightning over the acropolis'),
    ('porto_antico', 'citta', 'ambra', 'ancient harbor with wooden ships at sunset, stone lighthouse, golden haze'),
    # templi, colonne, luna
    ('tempio_luna', 'tempio', 'notte', 'ruined Greek temple with tall columns under a huge full moon, blue night'),
    ('colonne_nebbia', 'tempio', 'alba', 'row of ancient columns disappearing into thick morning fog'),
    ('tempio_interno_braci', 'tempio', 'ambra', 'dark interior of an ancient temple with marble columns and floating embers, a beam of light'),
    ('rovine_nebbia', 'rovine', 'tempesta', 'ancient ruins in fog, broken columns and fallen statues, grey light'),
    ('testa_statua_terra', 'rovine', 'tempesta', 'broken marble head of a statue lying in the grass among ruins, overcast light'),
    ('arco_alba', 'rovine', 'alba', 'ancient stone arch on a mountain path at sunrise, soft golden light'),
    ('anfiteatro_vuoto', 'rovine', 'notte', 'empty ancient amphitheater under the night sky, stars and moonlight on the stone seats'),
    # natura drammatica
    ('mare_tempesta_rocce', 'natura', 'tempesta', 'huge waves crashing on dark rocks below an ancient temple, stormy sky'),
    ('cielo_tempesta', 'natura', 'tempesta', 'dramatic stormy sky with heavy dark clouds and rays of light breaking through'),
    ('montagne_alba', 'natura', 'alba', 'mountain peaks above a sea of clouds at dawn, calm and vast'),
    ('lago_notte_stelle', 'natura', 'notte', 'still lake at night reflecting the stars and the moon, silhouette of mountains'),
    ('albero_solitario', 'natura', 'tempesta', 'lone old olive tree on a hill under a dark sky, wind'),
    ('deserto_sole', 'natura', 'ambra', 'endless desert dunes at sunset, warm orange light, a single ancient ruin'),
    ('fuoco_braci', 'natura', 'ambra', 'close-up of burning embers and flames in darkness, sparks rising'),
    # candele, libri, pergamene, oggetti simbolici
    ('biblioteca_antica', 'oggetti', 'ambra', 'ancient library with shelves of scrolls, candle light, dust floating in the air'),
    ('pergamene_tavolo', 'oggetti', 'ambra', 'old scrolls, quill and an oil lamp on a wooden table in darkness'),
    ('clessidra', 'oggetti', 'notte', 'hourglass with falling sand on a stone table, dark room, a single candle'),
    ('candela_sola', 'oggetti', 'notte', 'single candle burning in total darkness, smoke rising, close-up'),
    ('specchio_bronzo', 'oggetti', 'notte', 'ancient bronze mirror on a stone wall reflecting a dim candle, mysterious'),
    ('catene_spezzate', 'oggetti', 'ambra', 'broken iron chains on ancient stone steps, warm light, symbol of freedom'),
    ('bilancia_antica', 'oggetti', 'alba', 'ancient bronze balance scale on a marble table, soft morning light'),
    ('elmo_terra', 'oggetti', 'tempesta', 'ancient bronze helmet lying on the ground in the rain, battlefield mist'),
    # animali simbolici
    ('leone_marmo', 'animali', 'ambra', 'marble lion statue roaring at the entrance of a temple, fire glow'),
    ('aquila_statua', 'animali', 'tempesta', 'bronze eagle statue with open wings on a column against a stormy sky'),
    ('lupo_rovine', 'animali', 'notte', 'lone wolf among ancient ruins under the moonlight'),
    ('gufo_colonna', 'animali', 'notte', 'owl perched on a broken marble column at night, symbol of wisdom'),
    ('cavallo_nebbia', 'animali', 'alba', 'marble horse statue emerging from morning fog'),
]


def log(*a):
    print('[libreria]', *a, flush=True)


def http(url, dati=None, headers=None, raw=False, timeout=120):
    h = {'Content-Type': 'application/json'} if isinstance(dati, dict) else {}
    h.update(headers or {})
    body = json.dumps(dati).encode() if isinstance(dati, dict) else dati
    req = urllib.request.Request(url, data=body, headers=dict({'User-Agent': 'Mozilla/5.0'}, **h))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def fal(modello, dati):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/' + modello, dati, h)
    for _ in range(150):
        time.sleep(5)
        st = http(inv['status_url'], headers=h)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], headers=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')


def buona(img_bytes, desc):
    """Claude Haiku: niente scritte, niente oggetti moderni, niente corpi deformi, soggetto giusto."""
    if not CONTROLLO or not E('ANTHROPIC_API_KEY', ''):
        return True
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(img_bytes)).convert('RGB'); im.thumbnail((640, 640))
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=82)
        r = http('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 200, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': f'Expected: {desc}. Answer NO if the image has ANY readable text, letters or inscriptions, a modern object, '
                                     'deformed faces/hands/extra limbs, or clearly does not show the expected subject. Otherwise SI. Answer only SI or NO.'}]}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        return 'NO' not in ''.join(b.get('text', '') for b in r.get('content', [])).upper()
    except Exception as e:
        log('controllo non riuscito, tengo l\'immagine:', str(e)[:100])
        return True


def crea(voce):
    ident, sogg, emo, desc = voce
    dest = os.path.join(CARTELLA, ident + '.jpg')
    for tent in range(2):
        try:
            r = fal('fal-ai/nano-banana-2', {'prompt': f'{desc}. {LUCE[emo]}. {STILE}', 'aspect_ratio': '16:9', 'resolution': RISOLUZIONE,
                                             'output_format': 'jpeg', 'num_images': 1})
            b = http(r['images'][0]['url'], raw=True, timeout=180)
            if not buona(b, desc):
                log(f'{ident}: scartata dal controllo, rifaccio'); continue
            from PIL import Image
            Image.open(io.BytesIO(b)).convert('RGB').resize((2400, 1350), Image.LANCZOS).save(dest, quality=90)
            log(f'{ident}: pronta')
            return ident
        except Exception as e:
            log(f'{ident}: errore', str(e)[:150]); time.sleep(5)
    return None


def main():
    os.makedirs(CARTELLA, exist_ok=True)
    da_fare = [v for v in SOGGETTI if not os.path.exists(os.path.join(CARTELLA, v[0] + '.jpg'))][:MASSIMO]
    log(f'libreria: {len(SOGGETTI) - len([v for v in SOGGETTI if not os.path.exists(os.path.join(CARTELLA, v[0] + ".jpg"))])} gia\' pronte, '
        f'{len(da_fare)} da creare ({RISOLUZIONE}, circa {len(da_fare) * PREZZO:.2f} $)')
    if not E('FAL_KEY', '') and da_fare:
        sys.exit('manca il secret FAL_KEY')
    with ThreadPoolExecutor(4) as ex:
        fatte = [x for x in ex.map(crea, da_fare) if x]
    indice = [{'file': v[0] + '.jpg', 'descrizione': v[3], 'emozione': v[2], 'soggetto': v[1]}
              for v in SOGGETTI if os.path.exists(os.path.join(CARTELLA, v[0] + '.jpg'))]
    json.dump(indice, open(os.path.join(CARTELLA, 'indice.json'), 'w'), ensure_ascii=False, indent=1)
    log(f'FATTO: {len(fatte)} nuove, libreria con {len(indice)} immagini (indice.json aggiornato)')


if __name__ == '__main__':
    main()
