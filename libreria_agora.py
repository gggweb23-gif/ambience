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
         'Strong rim light separating the subject from the dark background, high contrast, readable and striking even on a small phone screen. '
         'Absolutely no text, no letters, no inscriptions, no logo, no watermark, no frame, nothing modern (no phones, cars, electric lights, modern buildings).')

LUCE = {
    'ambra': 'warm amber and golden light, glowing embers, fire and sunset tones',
    'notte': 'cold night blue and teal moonlight, deep shadows',
    'tempesta': 'grey stormy desaturated light, dark clouds, rain or mist',
    'alba': 'soft pale dawn light, gentle mist, calm muted tones',
}

# id, soggetto, emozione, descrizione (inglese, per il prompt e per la scelta nel video)
SOGGETTI = [
    # INQUADRATURE come il competitor: quasi sempre CORPO INTERO o dalle ginocchia in su, a distanze diverse (campo lungo, figura intera, mezza figura),
    # ETA' diverse (giovani, adulti, anziani). Mai solo un volto. Le 7 immagini gia' fatte e approvate restano (stessi id).
    # statue di marmo "vive", corpo intero
    ('statua_luna_colonne', 'statua', 'notte', 'full body marble statue of a muscular philosopher seen from behind between temple columns, full moon in a blue night sky'),
    ('statua_mano_mento', 'statua', 'notte', 'full body marble statue of an old bearded philosopher seated on a stone bench, chin on his hand, moonlit temple behind'),
    ('statua_occhi_chiusi', 'statua', 'alba', 'full body marble statue of an old philosopher with closed eyes standing in a misty olive grove at dawn'),
    ('statua_pioggia', 'statua', 'tempesta', 'full body marble statue of a philosopher standing calm under heavy rain in a street of ruins'),
    ('statua_seduta_trono', 'statua', 'ambra', 'full body marble statue of a philosopher seated on a stone throne inside a dark temple, candles, embers'),
    ('statua_pergamena', 'statua', 'ambra', 'marble statue of a sage seated at a table reading an open scroll, seen from the knees up, oil lamp light'),
    ('statua_spalle_citta', 'statua', 'ambra', 'full body marble statue seen from behind on a balcony overlooking an ancient city at golden sunset'),
    ('statua_giovane_atleta', 'statua', 'alba', 'full body marble statue of a young athletic stoic man standing on a rock above a valley at dawn, calm posture'),
    ('statua_seduta_nuvole', 'statua', 'tempesta', 'marble statue of a muscular man seated on a high ledge above dark storm clouds, seen from the knees up'),
    ('statua_braccia_conserte', 'statua', 'ambra', 'marble statue of a strong middle-aged bearded man with crossed arms, seen from the knees up, fire glow and temple behind'),
    ('statua_camminata', 'statua', 'notte', 'full body marble statue of a philosopher walking forward on a moonlit temple floor, robe in motion'),
    ('statua_inginocchiata', 'statua', 'tempesta', 'full body marble statue of a young man kneeling with head bowed among ruins, rain'),
    ('statua_anziano_bastone', 'statua', 'alba', 'full body marble statue of a very old sage leaning on a staff on a mountain path, morning mist'),
    ('statua_fuoco', 'statua', 'ambra', 'muscular marble statue standing among flames and smoke beside an ancient column, seen from the knees up'),
    # persone antiche reali (cinematografiche, mai volti moderni), corpo intero o mezza figura, eta' diverse
    # PERSONE VERE: figura GRANDE che riempie lo schermo (dalla vita o dalle ginocchia in su), poche a corpo intero, pochissime in campo lungo
    ('imperatore_tenda', 'persona', 'notte', 'middle-aged Roman emperor in simple armor writing on a scroll by an oil lamp inside a military tent at night, seen from the waist up, filling the frame'),
    ('imperatore_campo', 'persona', 'tempesta', 'Roman emperor in a cloak standing alone on a hill above a misty army camp, full body, wide shot'),
    ('senatore_finestra', 'persona', 'alba', 'old Roman senator in a white toga standing at a large stone window looking at the dawn, full body, seen from behind'),
    ('senatore_esilio', 'persona', 'tempesta', 'older man in a worn toga on a windy rocky island shore, seen from the knees up, large in the frame, cloak in the wind, stormy sea behind'),
    ('maestro_allievi', 'persona', 'ambra', 'old teacher with a staff speaking to two young students on stone steps, the teacher large in the foreground from the knees up, golden light'),
    ('allievo_ascolta', 'persona', 'ambra', 'young student in a simple tunic sitting on temple steps listening intently, seen from the waist up, filling the frame, warm light'),
    ('giovane_alba', 'persona', 'alba', 'muscular young man in a tunic training at dawn on a beach, seen from the knees up, large in the frame, calm and disciplined'),
    ('uomo_pioggia', 'persona', 'tempesta', 'man in a dark cloak standing still in the pouring rain in an ancient street, seen from the knees up, large in the frame, others running past blurred'),
    ('vecchio_fuoco', 'persona', 'ambra', 'old bearded sage in ancient robes sitting by a campfire at night, seen from the waist up, large in the frame, fire lighting his face'),
    ('donna_scogliera', 'persona', 'tempesta', 'woman in an ancient stola standing calm on a cliff above a stormy sea, seen from the knees up, large in the frame, cloak in the wind'),
    ('donna_lampada', 'persona', 'notte', 'middle-aged woman in ancient clothes reading a scroll by an oil lamp, seen from the waist up, filling the frame'),
    ('uomo_toga_citta', 'persona', 'ambra', 'man in a toga at an open window above an ancient Greek city at sunset, seen from the knees up, large silhouette in the foreground'),
    ('viandante_sentiero', 'persona', 'alba', 'lone traveler in ancient robes with a staff walking on a stone path in the morning mist, full body filling the frame height'),
    ('figura_mare', 'persona', 'notte', 'man in a cloak sitting on rocks watching a dark sea under the stars, seen from behind from the waist up, large in the foreground'),
    ('figura_scalinata', 'persona', 'tempesta', 'robed man climbing stone steps toward a temple under dark clouds, full body filling the frame height, seen from below'),
    ('schiavo_catene', 'persona', 'ambra', 'muscular man breaking free from iron chains, seen from the knees up, filling the frame, warm dramatic light'),
    ('mercato_calmo', 'persona', 'ambra', 'calm philosopher standing still in a crowded ancient market, seen from the knees up, large in the frame, crowd blurred around him'),
    ('padre_figlio', 'persona', 'alba', 'old father and young son walking together on an ancient road at sunrise, full body filling the frame height'),
    # incappucciati
    ('incappucciato_trono', 'incappucciato', 'ambra', 'hooded robed figure seated on a stone throne in a dark hall, face in shadow, seen from the knees up, filling the frame, torch light'),
    ('incappucciato_corridoio', 'incappucciato', 'notte', 'hooded figure walking toward the camera down a corridor of columns, blue moonlight, full body filling the frame height'),
    ('incappucciato_scogliera', 'incappucciato', 'tempesta', 'hooded figure standing on a cliff above a stormy sea, seen from the knees up, large in the frame, cloak moving in the wind'),
    ('incappucciato_candela', 'incappucciato', 'ambra', 'hooded figure writing by a single candle in a dark stone room, seen from the waist up, filling the frame'),
    # guerrieri
    ('guerriero_elmo', 'guerriero', 'tempesta', 'ancient Greek hoplite with crested helmet and shield, seen from the knees up, large in the frame, battlefield and stormy sky behind'),
    ('guerriero_inginocchiato', 'guerriero', 'notte', 'warrior kneeling with head bowed, sword planted in the ground, full body filling the frame height, moonlight'),
    ('gladiatore_arena', 'guerriero', 'ambra', 'muscular gladiator standing in an ancient arena at sunset, seen from the knees up, large in the frame, dust in the air'),
    ('ercole_fatica', 'guerriero', 'tempesta', 'muscular man carrying a heavy stone on his shoulders up a hill, full body filling the frame height, grey storm light'),
    ('legionario_marcia', 'guerriero', 'alba', 'Roman legionary marching on a road at dawn, seen from the knees up, large in the frame, mist behind'),
    ('spartano_riposo', 'guerriero', 'notte', 'tired warrior sitting on a rock after battle, helmet beside him, seen from the knees up, filling the frame, moonlight'),
    # citta', templi, natura: la figura resta ben visibile in primo piano (niente puntini)
    ('atene_tramonto', 'citta', 'ambra', 'man in a toga in the foreground seen from the waist up, ancient Athens with the Parthenon behind him at golden sunset'),
    ('roma_foro_notte', 'citta', 'notte', 'man with a torch in the foreground seen from the knees up, ancient Roman forum at night behind him'),
    ('roma_alba_nebbia', 'citta', 'alba', 'ancient Rome at dawn seen from a hill, mist between the temples, a man in a toga in the foreground, wide shot'),
    ('tempio_luna', 'tempio', 'notte', 'robed philosopher standing between tall columns of a ruined temple, full body filling the frame height, huge full moon behind'),
    ('tempio_interno_braci', 'tempio', 'ambra', 'figure standing in a beam of light inside a dark ancient temple, seen from the knees up, floating embers around'),
    ('rovine_nebbia', 'rovine', 'tempesta', 'man walking among broken columns and fallen statues in fog, full body filling the frame height'),
    ('anfiteatro_vuoto', 'rovine', 'notte', 'empty ancient amphitheater under the night sky, one figure seated on the stone seats, wide shot'),
    ('mare_tempesta_rocce', 'natura', 'tempesta', 'robed man standing firm on dark rocks as huge waves crash behind him, seen from the knees up, large in the frame'),
    ('montagne_alba', 'natura', 'alba', 'mountain peaks above a sea of clouds at dawn, a lone figure in robes on a summit, wide shot'),
    ('lago_notte_stelle', 'natura', 'notte', 'man sitting on the shore of a still lake reflecting the stars, seen from behind from the waist up, large in the foreground'),
    ('albero_solitario', 'natura', 'tempesta', 'man in a cloak standing beside an old olive tree under a dark sky, full body filling the frame height, wind'),
    ('deserto_sole', 'natura', 'ambra', 'robed traveler walking through desert dunes at sunset, full body filling the frame height'),
    # pochi oggetti simbolici (pause visive): grandi in primo piano
    ('biblioteca_antica', 'oggetti', 'ambra', 'old man reading a scroll in an ancient library, seen from the waist up, candle light, dust floating, shelves of scrolls behind'),
    ('clessidra', 'oggetti', 'notte', 'large hourglass with falling sand filling the frame on a stone table, dark room, a single candle'),
    ('candela_sola', 'oggetti', 'notte', 'single candle burning in darkness, close and large in the frame, smoke rising'),
    ('leone_marmo', 'animali', 'ambra', 'marble lion statue at the entrance of a temple, large in the frame, fire glow'),
    ('aquila_statua', 'animali', 'tempesta', 'bronze eagle with open wings on a column, large in the frame, stormy sky'),
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
                                     'deformed faces/hands/extra limbs, a close-up of only a face or a bust, '
                                     + ('' if 'wide shot' in desc else 'the main subject small in the distance instead of large and filling the frame, ') +
                                     'or clearly does not show the expected subject. Otherwise SI. Answer only SI or NO.'}]}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        return 'NO' not in ''.join(b.get('text', '') for b in r.get('content', [])).upper()
    except Exception as e:
        log('controllo non riuscito, tengo l\'immagine:', str(e)[:100])
        return True


def crea(voce):
    ident, sogg, emo, desc = voce
    dest = os.path.join(CARTELLA, ident + '.jpg')
    if 'wide shot' in desc:
        inq = 'FRAMING: wide epic view, but the person stays clearly visible, never a tiny dot; NEVER a close-up of only a face or a bust.'
    else:
        inq = ('FRAMING: the main subject is LARGE and DOMINANT, filling most of the frame height (from the waist or knees up, or full body filling the height), '
               'heroic and powerful presence; NEVER a close-up of only a face or a bust, never small in the distance.')
    for tent in range(2):
        try:
            r = fal('fal-ai/nano-banana-2', {'prompt': f'{desc}. {LUCE[emo]}. {inq} {STILE}', 'aspect_ratio': '16:9', 'resolution': RISOLUZIONE,
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
