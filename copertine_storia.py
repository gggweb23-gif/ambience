#!/usr/bin/env python3
"""
STORIA IN MINUTI - copertine "BANDIERA + SOVRANO": stile del canale, niente copiato dal competitor (dal competitor si prende solo il tipo di figura).
  meta' sinistra: la bandiera del paese, vera stoffa al vento;   meta' destra: un sovrano dell'epoca FOTOREALISTICO, persona nuova;
  dietro: un monumento reale e riconoscibile del paese, cielo vero e colori veri;   in alto al centro: NOME DEL PAESE grande + date (scritti dallo script).
  3 copertine per video: 1 va online, 2 e 3 sono pronte per il cambio se il CTR resta basso (altro monumento, altra figura, altra inquadratura).
Uscita: copertine_storia/<video>_1.jpg, _2.jpg, _3.jpg (+ _base senza scritte) + confronto.jpg. APPLICA=SI carica la 1 su YouTube.
STILE "ILLUSTRATO" (predefinito dal 23/10, COPERTINA_FORMATO=illustrato), come Genius History / History in Minutes:
  illustrazione dipinta; a sinistra un personaggio simbolo del paese a mezzo busto che guarda lo spettatore; dietro il paese che passa
  dall'antico (sinistra) al moderno (destra); in alto a destra il NOME enorme in nero con grazie spesse + bandiera, sotto "2600 a.C. -> 2026" con freccia rossa.
STILE "PRIMA_DOPO" (COPERTINA_FORMATO=prima_dopo, COPERTINA_FORMATO=prima_dopo; "bandiera" = stile vecchio qui sopra), ispirato a CityEons:
  vista aerea 3D fotorealistica divisa in diagonale: a sinistra la citta' antica del paese, a destra lo stesso paese oggi col suo monumento simbolo;
  in alto "2600 a.C. -> 2026" (freccia arancio zafferano, anno finale oro); in basso il NOME DEL PAESE enorme e spaziato con la bandierina. Nessuna persona.
Env: VIDEO = "nostroID:competitorID,..." (al posto del nostro ID va bene una parola del titolo, es. "India:p9IIGdg91fE")
"""
import base64, io, json, os, re, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageOps

E = os.environ.get
APPLICA = str(E('APPLICA', '') or 'NO').strip().upper() == 'SI'
LIVELLI = [int(x) for x in (E('LIVELLI', '') or '40,50,60').split(',') if x.strip()]
COPPIE = [(x.strip().split(':', 1) + [''])[:2] for x in (E('VIDEO', '') or '').split(',') if x.strip()]   # 'id:competitor' oppure solo id / parola del titolo
OUT = os.path.join(os.getcwd(), 'copertine_storia'); os.makedirs(OUT, exist_ok=True)
FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
BOLLINO = os.path.join(os.getcwd(), 'bollino_storia_in_minuti.png')
FORMATO = str(E('COPERTINA_FORMATO', '') or 'illustrato').strip().lower()   # illustrato (come i competitor: personaggio + nome nero con grazie) | prima_dopo (aerea antico -> oggi) | bandiera


def log(*a):
    print(*a, flush=True)


def http(url, dati=None, headers=None, raw=False, metodo=None, timeout=180):
    h = {'User-Agent': 'Mozilla/5.0'}
    if isinstance(dati, (dict, list)):
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    body = json.dumps(dati).encode() if isinstance(dati, (dict, list)) else dati
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=metodo), timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60) as r:
        return json.loads(r.read().decode())['access_token']


AUTH = {'Authorization': 'Bearer ' + token()}


def video_canale():
    ch = http('https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true', headers=AUTH)['items'][0]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    r = http('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode({'part': 'snippet', 'playlistId': up, 'maxResults': 50}), headers=AUTH)
    return [(x['snippet']['resourceId']['videoId'], x['snippet']['title']) for x in r.get('items', [])]


def copertina_yt(v):
    for q in ('maxresdefault', 'hqdefault'):
        try:
            im = Image.open(io.BytesIO(http(f'https://i.ytimg.com/vi/{v}/{q}.jpg', raw=True))).convert('RGB')
            if im.width >= 400:
                return ImageOps.fit(im, (1280, 720), Image.LANCZOS)
        except Exception:
            pass
    return None


def jpg64(im, w=1024):
    x = io.BytesIO(); im.convert('RGB').resize((w, w * 9 // 16)).save(x, 'JPEG', quality=88)
    return base64.b64encode(x.getvalue()).decode()


def fal(modello, dati):
    inv = http('https://queue.fal.run/' + modello, dati, FAL)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], headers=FAL)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], headers=FAL)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')


def claude(cont, max_tokens=3000):
    r = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': max_tokens,
             'messages': [{'role': 'user', 'content': cont}]}, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    return ''.join(b.get('text', '') for b in r.get('content', []))


DOMANDA = """Copertina YouTube di un video sulla storia completa di un paese (competitor). Titolo del video originale: "{titolo}".
Rispondi SOLO JSON:
{{"paese": "nome del paese in ITALIANO, MAIUSCOLO (es. INDIA, IRAN, AFGHANISTAN, GIAPPONE)",
 "bandiera": "nome del paese in inglese per la bandiera ufficiale (es. India)",
 "date": "le date della copertina o del titolo nel formato '2600 a.C. – 2026' (a e d minuscole); se non ci sono, l'arco della storia del paese",
 "uomo": "in inglese: la figura maschile dello stesso tipo della figura principale della copertina, con abiti e gioielli storici del paese (es. 'an ancient Indian king with a golden crown and white and red silk'); se la copertina non ha una figura: il personaggio storico piu' simbolico e riconoscibile del paese, descritto con abiti tipici (es. 'an Indian maharaja with a golden jewelled turban and cream and gold clothes')",
 "donna": "in inglese: la figura femminile corrispondente dello stesso rango ed epoca (es. 'an ancient Indian queen with a golden crown and a red silk sari')",
 "popolo": "in inglese: i tratti del viso REALI e tipici della popolazione storica di quel paese (es. 'authentic native Afghan (Pashtun) facial features: olive skin, strong nose, dark deep-set eyes'), mai tratti di altri popoli",
 "monumento": "in inglese: UN monumento reale e famoso del paese, il piu' riconoscibile (es. 'the Great Stupa of Sanchi')",
 "antico": "in inglese, per una vista AEREA dall'alto: la citta' o il sito piu' antico e famoso del paese com'era all'epoca della PRIMA data, ricostruito intatto e vivo (es. 'the ancient Indus Valley city of Mohenjo-daro in 2600 BC: mud-brick houses, the Great Bath, the river, dusty ochre tones')",
 "moderno": "in inglese, per una vista AEREA dall'alto: il paese OGGI, con il suo monumento piu' famoso in primo piano e la grande citta' moderna dietro (es. 'modern India today with the Taj Mahal and its gardens in the foreground and a dense modern city skyline behind it')",
 "antico2": "come antico ma un ALTRO sito antico famoso del paese, diverso",
 "moderno2": "come moderno ma un ALTRO luogo simbolo di oggi del paese, diverso"}}"""


def prompt_con_testo(bandiera, figura, monumento, var, paese, date):
    inquadratura = 'waist-up, looking at the viewer'   # stessa inquadratura: la 2 cambia solo uomo/donna
    anno = (re.findall(r'\d{3,4}', date) or [''])[-1]
    return ('Create a YouTube thumbnail, 16:9, 1280x720, premium, cinematic and eye-catching, readable on a phone. PHOTOREALISTIC, like a still from a big-budget '
            'historical film: real skin, real fabrics, real metal and jewellery, natural light. No cartoon, no illustration. '
            f'LEFT HALF: the official national flag of {bandiera}, large, real silk fabric waving in the wind with deep natural folds, accurate vivid colours, lit by the sun. '
            f'RIGHT HALF: {figura}, a photorealistic NEW, original person, {inquadratura}. {POPOLO.get("tratti", "")} Real human face with natural skin texture, calm, dignified and confident expression, '
            'warm sunlight on the face and a soft golden rim light on the outline. '
            f'BACKGROUND (between and behind them): {monumento}, real and recognisable, slightly out of focus, with a real blue sky with natural clouds and true natural colours '
            '(no orange filter, no sunset, no fantasy colours). '
            'TEXT, two lines only, spelled exactly: '
            f'Line 1: {paese} - the country name, the BIGGEST element of the thumbnail, very clear bold serif capital letters like a documentary title, white with a thick dark outline '
            'and a strong drop shadow, perfectly readable at a glance. '
            f'Line 2, under it, smaller: {date} (lowercase "a" in "a.C."), bold condensed font, white with black outline' + (f', the year {anno} in bright yellow. ' if anno else '. ') +
            'Place the text in the upper part, across the centre, without covering the flag\'s emblem or the person\'s face. '
            'Keep the bottom-right corner (last 30% of width, last 28% of height) empty of text: the video duration is shown there. '
            'No logo, no badge, no other text, no watermark.')


POPOLO = {}


def date_freccia(date):
    """'2600 a.C. – 2026' -> ('2600 a.C.', '2026')"""
    parti = [x.strip() for x in re.split(r'\s+[–—-]+\s+|\s*→\s*|\s*–\s*|\s*—\s*', str(date)) if x.strip()]
    return (parti[0], parti[-1]) if len(parti) >= 2 else (str(date).strip(), '2026')


def prompt_pd(antico, moderno, paese, bandiera, date):
    da, a = date_freccia(date)
    return ('YouTube thumbnail, 16:9, photorealistic 3D aerial view in bright full daylight at midday, under a beautiful deep clear sky-blue sky with a few small white clouds (vivid azure blue, never orange, never hazy, never sunset), true natural colours, high contrast, very sharp, readable on a phone, no people in the foreground. '
            'The image is split by a soft diagonal blend from bottom-left to top-right: '
            f'the LEFT half shows {antico}; the RIGHT half shows {moderno}. '
            'The two eras melt into each other in the middle like a time-lapse. '
            'TEXT, spelled exactly, nothing else: '
            f'at the top centre, huge, white, condensed bold sans-serif font with wide letter spacing and a soft dark shadow: "{da}" (lowercase "a" in "a.C."), '
            f'then a long thick saffron-orange arrow pointing right, then "{a}" in saffron-gold. '
            f'At the bottom centre, enormous white condensed bold letters with very wide letter spacing and a dark shadow: "{paese}", '
            f'with a small waving national flag of {bandiera} just to the left of the word. '
            'Keep the bottom-right corner (last 25% of width, last 25% of height) free of text: the video duration is shown there. '
            'No other text, no logo, no badge, no watermark.')


def prompt_ill(figura, antico, moderno, paese, bandiera, date):
    da, a = date_freccia(date)
    return ('YouTube thumbnail, 16:9, detailed hand-painted digital illustration in the style of a history documentary thumbnail, rich vivid colours, '
            'very high contrast, very sharp, readable on a phone, slightly darker vignette on the edges. '
            f'LEFT 40%: {figura}, waist-up, close to the camera, looking straight into the viewer\'s eyes with an INTENSE, serious, determined gaze, '
            f'strong warm golden light on the face and a golden rim light on the outline. {POPOLO.get("tratti", "")} '
            f'BACKGROUND behind and to the right: on the left side {antico} under a warm golden sky, blending towards the right into {moderno} '
            'with city lights turning on, under a dramatic sunset sky with orange and deep blue clouds, like a journey through thousands of years. '
            f'TEXT at the top right: "{paese}" enormous, VERY THICK heavy black classical Roman serif font (like Cinzel Black) with a thin white outline, '
            f'the biggest element of the image, with a waving national flag of {bandiera} next to it about half the height of the letters. '
            f'Under it, BIG and bold (about 60% of the height of the word {paese}): "{da}" in black with a thin white outline (lowercase "a" in "a.C."), '
            f'a thick RED arrow pointing right, and "{a}" in bright GOLD with a black outline. '
            'Keep the bottom-right corner free of text. No other text, no logo, no watermark.')


def prompt_scena_ill(figura, antico, moderno):
    return ('YouTube thumbnail background, 16:9, detailed hand-painted digital illustration in the style of a history documentary thumbnail, rich vivid colours, '
            'very high contrast, very sharp, slightly darker vignette on the edges. '
            f'LEFT 40%: {figura}, waist-up, close to the camera, looking straight into the viewer\'s eyes with an INTENSE, serious, determined gaze, '
            f'strong warm golden light on the face and a golden rim light on the outline. {POPOLO.get("tratti", "")} '
            f'BACKGROUND behind and to the right: on the left side {antico} under a warm golden sky, blending towards the right into {moderno} '
            'with city lights turning on, under a dramatic sunset sky with orange and deep blue clouds. '
            'The upper right area (top 45%, right 55%) is open sky: a big title will be added there. Absolutely NO text, letters, numbers, logos or watermark anywhere.')


def titolo_ill(im, paese, date):
    """Riserva: PAESE enorme nero con grazie spesse in alto a destra, date sotto con freccia rossa."""
    W, H = im.size
    da, a = date_freccia(date)
    d = ImageDraw.Draw(im)
    x0, x1 = int(W * .45), int(W * .97)
    k = 230
    while k > 60:
        f1 = ImageFont.truetype(font('slab'), k)
        if f1.getlength(paese) <= x1 - x0:
            break
        k -= 6
    k2 = max(40, int(k * .6))
    while k2 > 30:
        f2 = ImageFont.truetype(font('slab'), k2)
        if f2.getlength(da) + f2.getlength(a) + k2 * 1.3 + 30 <= x1 - x0:
            break
        k2 -= 4
    cx = (x0 + x1) / 2; y = int(H * .05)
    d.text((cx, y), paese, font=f1, fill=(15, 15, 15), anchor='mt', stroke_width=3, stroke_fill=(255, 255, 255))
    y2 = y + k * 1.08; fr = int(f2.size * 1.3)
    tot = f2.getlength(da) + fr + 30 + f2.getlength(a); xs = cx - tot / 2
    d.text((xs, y2), da, font=f2, fill=(15, 15, 15), anchor='lt')
    ya = y2 + f2.size * .55; xa = xs + f2.getlength(da) + 15
    d.rectangle([xa, ya - 5, xa + fr - 22, ya + 5], fill=(220, 30, 30)); d.polygon([(xa + fr - 26, ya - 18), (xa + fr, ya), (xa + fr - 26, ya + 18)], fill=(220, 30, 30))
    d.text((xa + fr + 15, y2), a, font=f2, fill=(232, 182, 40), anchor='lt', stroke_width=3, stroke_fill=(10, 10, 10))
    return im


def crea_ill(figura, antico, moderno, paese, bandiera, date):
    for tentativo in range(3):
        r = fal('fal-ai/nano-banana-2', {'prompt': prompt_ill(figura, antico, moderno, paese, bandiera, date), 'aspect_ratio': '16:9', 'resolution': '2K',
                                         'output_format': 'jpeg', 'num_images': 1})
        prova = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
        if testo_ok(prova, paese, ' '.join(date_freccia(date))):
            return prova
    log('    3 tentativi con scritta sbagliata: scena senza scritte + titolo scritto dallo script')
    r = fal('fal-ai/nano-banana-2', {'prompt': prompt_scena_ill(figura, antico, moderno), 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
    return titolo_ill(ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS), paese, date)


def prompt_scena_pd(antico, moderno):
    return ('YouTube thumbnail background, 16:9, photorealistic 3D aerial view in bright full daylight at midday, under a beautiful deep clear sky-blue sky with a few small white clouds (vivid azure blue, never orange, never hazy, never sunset), true natural colours, high contrast, very sharp, no people in the foreground. '
            'The image is split by a soft diagonal blend from bottom-left to top-right: '
            f'the LEFT half shows {antico}; the RIGHT half shows {moderno}. The two eras melt into each other in the middle like a time-lapse. '
            'The top 22% is calm, clear, vivid azure-blue sky (a title will be added there). Absolutely NO text, letters, numbers, logos or watermark anywhere.')


def titolo_pd(im, paese, date):
    """Riserva senza scritte AI: date in alto con freccia (anno finale oro), PAESE enorme e spaziato in basso."""
    from PIL import ImageFilter
    W, H = im.size
    da, a = date_freccia(date)
    base = im.convert('RGBA'); om = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(om)
    f1 = ImageFont.truetype(font('anton'), 120); fr = 150
    l1, l2 = f1.getlength(da), f1.getlength(a)
    tot = l1 + fr + 60 + l2
    if tot > W * .86:
        k = int(120 * W * .86 / tot); f1 = ImageFont.truetype(font('anton'), k); l1, l2 = f1.getlength(da), f1.getlength(a); fr = int(fr * k / 120); tot = l1 + fr + 60 + l2
    x, y = (W - tot) / 2, 28
    k2 = 230
    while k2 > 80:
        f2 = ImageFont.truetype(font('anton'), k2); sp = int(k2 * .1)   # spaziatura lettere del paese
        larg = sum(f2.getlength(ch) for ch in paese) + sp * (len(paese) - 1)
        if larg <= W * .62:
            break
        k2 -= 6
    xp, yp = (W - larg) / 2, H - k2 * 1.32
    for dx, dy in ((6, 8),):
        do.text((x + dx, y + dy), da, font=f1, fill=(0, 0, 0, 190)); do.text((x + l1 + fr + 60 + dx, y + dy), a, font=f1, fill=(0, 0, 0, 190))
        xx = xp
        for ch in paese:
            do.text((xx + dx, yp + dy), ch, font=f2, fill=(0, 0, 0, 200)); xx += f2.getlength(ch) + sp
    base.alpha_composite(om.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(base)
    d.text((x, y), da, font=f1, fill=BIANCO)
    ya = y + f1.size * .62; xa = x + l1 + 30
    d.rectangle([xa, ya - 9, xa + fr - 38, ya + 9], fill=(232, 120, 40))
    d.polygon([(xa + fr - 50, ya - 34), (xa + fr, ya), (xa + fr - 50, ya + 34)], fill=(232, 120, 40))
    d.text((x + l1 + fr + 60, y), a, font=f1, fill=(226, 174, 68))
    xx = xp
    for ch in paese:
        d.text((xx, yp), ch, font=f2, fill=BIANCO); xx += f2.getlength(ch) + sp
    return base.convert('RGB')


def crea_pd(antico, moderno, paese, bandiera, date):
    """Copertina PRIMA_DOPO: scritta disegnata dall'AI e controllata lettera per lettera (3 tentativi), poi riserva con scritte dello script."""
    for tentativo in range(3):
        r = fal('fal-ai/nano-banana-2', {'prompt': prompt_pd(antico, moderno, paese, bandiera, date), 'aspect_ratio': '16:9', 'resolution': '2K',
                                         'output_format': 'jpeg', 'num_images': 1})
        prova = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
        if testo_ok(prova, paese, ' '.join(date_freccia(date))):
            return prova
    log('    3 tentativi con scritta sbagliata: scena senza scritte + titolo scritto dallo script')
    r = fal('fal-ai/nano-banana-2', {'prompt': prompt_scena_pd(antico, moderno), 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
    return titolo_pd(ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS), paese, date)


def norm(t):
    return re.sub(r'[^A-Z0-9]', '', str(t).upper())


def testo_ok(im, paese, date):
    """Claude legge la copertina: ci devono essere ESATTAMENTE il paese e le date, nient'altro."""
    try:
        t = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(im, 1024)}},
                    {'type': 'text', 'text': 'Trascrivi ESATTAMENTE tutto il testo scritto in questa immagine, lettera per lettera, senza correggere errori. Solo il testo, su una riga.'}], 300)
        ok = norm(t) in (norm(paese + date), norm(date + paese))   # prima_dopo: le date sono in alto, il paese in basso
        if not ok:
            log(f'    scritta sbagliata: "{t.strip()[:80]}"')
        return ok
    except Exception as e:
        log('    controllo scritta non riuscito:', str(e)[:100]); return True


def prompt_scena(bandiera, figura, monumento, var):
    inquadratura = ['waist-up, looking at the viewer', 'chest-up, slightly closer, looking at the viewer', 'waist-up, seen from a slightly low angle, looking at the viewer'][var % 3]
    return ('YouTube thumbnail background, 16:9, PHOTOREALISTIC, like a still from a big-budget historical film: real skin, real fabrics, real metal and jewellery, natural sunlight. '
            'No cartoon, no illustration. '
            f'LEFT 45%: the official national flag of {bandiera}, large, real fabric waving in the wind with deep natural folds, accurate vivid colours, lit by the sun. '
            f'RIGHT 35%: {figura}, a photorealistic original person, {inquadratura}, real human face with natural skin texture, calm, dignified and confident expression, '
            'warm sunlight on the face and a soft golden rim light on the outline. '
            f'BACKGROUND in the centre, between them: {monumento}, real and recognisable, slightly out of focus, under a real blue sky with natural white clouds, true natural colours '
            '(no orange filter, no sunset, no fantasy colours). '
            'The upper central area (top 40% of the image, between the flag and the person) must be calm open sky with nothing important: a big title will be added there. '
            'Absolutely NO text, letters, numbers, logos or watermark anywhere.')


FONT_DIR = os.path.join(os.getcwd(), 'font_copertine'); os.makedirs(FONT_DIR, exist_ok=True)


def font(nome):
    p = os.path.join(FONT_DIR, nome + '.ttf')
    if not os.path.exists(p):
        u = {'slab': 'https://github.com/google/fonts/raw/main/ofl/alfaslabone/AlfaSlabOne-Regular.ttf',
             'anton': 'https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf'}[nome]
        open(p, 'wb').write(http(u, raw=True))
    return p


GIALLO, BIANCO, NERO = (255, 214, 0), (255, 255, 255), (0, 0, 0)


def zona_titolo(im):
    """Claude indica il rettangolo di cielo libero in alto tra bandiera e persona (mai sul volto, mai in basso a destra)."""
    dom = ('YouTube thumbnail without text: flag on the left, a person on the right. We must add a big 2-line title in the UPPER CENTRE. '
           'Give the LARGEST rectangle in the upper part that does NOT cover the person\'s face or head and does not cover the flag\'s central emblem. '
           'It may overlap the top of the flag fabric and the sky. Answer ONLY JSON with percentages: {"x0": 0, "y0": 0, "x1": 0, "y1": 0}')
    try:
        t = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(im, 768)}}, {'type': 'text', 'text': dom}], 1500)
        z = json.loads(t[t.find('{'): t.rfind('}') + 1]); z = [max(0.0, min(100.0, float(z[k]))) / 100 for k in ('x0', 'y0', 'x1', 'y1')]
        if z[2] - z[0] >= .30 and z[3] - z[1] >= .20:
            return z
    except Exception as e:
        log('    zona titolo non trovata:', str(e)[:100])
    return [.20, .02, .74, .42]


def titolo(im, paese, date, z):
    """NOME DEL PAESE grande (serif pesante bianco, contorno scuro, ombra) + date sotto (condensato bianco, anno finale giallo)."""
    W, H = im.size
    x0, y0, x1, y1 = int(W * z[0]), int(H * z[1]) + 6, int(W * z[2]), min(int(H * z[3]), int(H * .60))
    larg, alt = x1 - x0, y1 - y0
    best = None
    for k in range(300, 60, -4):
        k2 = int(k * .52)
        f1, f2 = ImageFont.truetype(font('slab'), k), ImageFont.truetype(font('anton'), k2)
        h = k * 1.05 + k2 * 1.15
        if f1.getlength(paese) <= larg and f2.getlength(date) <= larg and h <= alt:
            best = (k, k2); break
    k, k2 = best or (90, 47)
    f1, f2 = ImageFont.truetype(font('slab'), k), ImageFont.truetype(font('anton'), k2)
    cx = (x0 + x1) / 2; y = y0 + (alt - (k * 1.05 + k2 * 1.15)) / 2
    base = im.convert('RGBA')
    om = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(om)
    do.text((cx + 8, y + 10), paese, font=f1, fill=(0, 0, 0, 200), anchor='mt', stroke_width=max(6, k // 14), stroke_fill=(0, 0, 0, 200))
    do.text((cx + 6, y + k * 1.05 + 8), date, font=f2, fill=(0, 0, 0, 200), anchor='mt', stroke_width=max(5, k2 // 10), stroke_fill=(0, 0, 0, 200))
    from PIL import ImageFilter
    base.alpha_composite(om.filter(ImageFilter.GaussianBlur(9)))
    d = ImageDraw.Draw(base)
    d.text((cx, y), paese, font=f1, fill=BIANCO, anchor='mt', stroke_width=max(6, k // 14), stroke_fill=(20, 20, 20))
    # date: tutto bianco tranne l'ultimo anno (giallo)
    yd = y + k * 1.05
    m = re.match(r'^(.*?)(\d{3,4})\s*$', date)
    pre, anno = (m.group(1), m.group(2)) if m else (date, '')
    tot = f2.getlength(date); xs = cx - tot / 2
    sw = max(5, k2 // 10)
    d.text((xs, yd), pre, font=f2, fill=BIANCO, anchor='lt', stroke_width=sw, stroke_fill=NERO)
    if anno:
        d.text((xs + f2.getlength(pre), yd), anno, font=f2, fill=GIALLO, anchor='lt', stroke_width=sw, stroke_fill=NERO)
    return base.convert('RGB')


REG = os.path.join(OUT, 'registro_copertine.csv')


def registro():
    import csv as _c
    return list(_c.DictReader(open(REG, encoding='utf-8'))) if os.path.exists(REG) else []


def registra(vid, t1, t2):
    import csv as _c
    nuovo = not os.path.exists(REG)
    with open(REG, 'a', newline='', encoding='utf-8') as f:
        w = _c.writer(f)
        if nuovo:
            w.writerow(['data', 'video', 'tipo_1', 'tipo_2'])
        w.writerow([time.strftime('%Y-%m-%d'), vid, t1, t2])


righe, testo_log = [], []
canale = None
TITOLO_PROVA = str(E('TITOLO_PROVA', '') or '').strip()   # prova del video (da video_storia): copertine dal titolo, niente YouTube, niente registro
if TITOLO_PROVA:
    COPPIE = [['prova', '']]
    APPLICA = False
if not COPPIE:   # modo automatico (ogni 3 ore): i video nuovi del canale senza copertine del nuovo stile
    DAL = str(E('DAL', '') or '2026-10-20')
    ch = http('https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true', headers=AUTH)['items'][0]
    r_ = http('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode({'part': 'snippet,contentDetails', 'playlistId': ch['contentDetails']['relatedPlaylists']['uploads'], 'maxResults': 20}), headers=AUTH)
    for it in r_.get('items', []):
        v_ = it['contentDetails']['videoId']
        if str(it['contentDetails'].get('videoPublishedAt') or it['snippet'].get('publishedAt') or '')[:10] >= DAL and not os.path.exists(os.path.join(OUT, f'{v_}_1.jpg')):
            COPPIE.append([v_, ''])
    log(f'video nuovi senza copertine: {len(COPPIE)}')
VARIANTE = str(E('VARIANTE', '') or '').strip()   # "2" = crea SOLO la copertina 2 di un video (la chiede il Rotatore CTR quando serve)
for nostro, comp in COPPIE:
    nostro, comp = nostro.strip(), comp.strip()
    info_p = os.path.join(OUT, f'{nostro}_info.json')
    if VARIANTE:   # copertine alternative di un video gia' online (2 = stessa copertina con l'altra persona, 3 = stessa impostazione con 1-2 elementi diversi)
        canale = canale or video_canale()
        if not re.fullmatch(r'[\w-]{11}', nostro):
            trovato = next((v for v, t in canale if nostro.lower() in t.lower()), None)
            if not trovato:
                log('video non trovato sul canale:', nostro); continue
            log(f'"{nostro}" -> {trovato}'); nostro = trovato
        info_p = os.path.join(OUT, f'{nostro}_info.json')
        tit = next((t for v, t in canale if v == nostro), '')
        if os.path.exists(info_p):
            inf = json.load(open(info_p))
        else:   # video fatto prima del sistema nuovo: i dati si ricavano dal titolo
            try:
                txt = claude([{'type': 'text', 'text': DOMANDA.format(titolo=tit) + " (Nessuna immagine: ricava tutto dal titolo e da cio' che sai della storia del paese.)"}])
                an = json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
            except Exception as e:
                log('analisi non riuscita', nostro, str(e)[:150]); continue
            reg = next((x for x in registro() if x.get('video') == nostro), None)
            primo = (reg or {}).get('tipo_1') or 'uomo'
            fig = [an.get('uomo') or 'an ancient king', an.get('donna') or 'an ancient queen']
            inf = {'paese': str(an.get('paese') or '').upper().strip(), 'date': str(an.get('date') or '').strip(), 'bandiera': str(an.get('bandiera') or '').strip(),
                   'figure': fig if primo == 'uomo' else fig[::-1], 'monumento': an.get('monumento') or 'a famous ancient monument of the country',
                   'tratti': ('The person must look like a REAL native of ' + str(an.get('bandiera') or '') + ': ' + str(an.get('popolo') or '') + '. Never features of other peoples.') if an.get('popolo') else '',
                   'tipi': [primo, 'donna' if primo == 'uomo' else 'uomo'],
                   'antico': an.get('antico') or '', 'moderno': an.get('moderno') or '', 'antico2': an.get('antico2') or '', 'moderno2': an.get('moderno2') or ''}
            json.dump(inf, open(info_p, 'w'), ensure_ascii=False)
        POPOLO['tratti'] = inf.get('tratti', '')
        celle = [('ATTUALE', copertina_yt(nostro))]
        if FORMATO in ('prima_dopo', 'illustrato'):
            if not inf.get('antico'):
                try:
                    txt = claude([{'type': 'text', 'text': DOMANDA.format(titolo=tit) + " (Nessuna immagine: ricava tutto dal titolo e da cio' che sai della storia del paese.)"}])
                    an = json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
                    inf.update({k: an.get(k) or '' for k in ('antico', 'moderno', 'antico2', 'moderno2')})
                    json.dump(inf, open(info_p, 'w'), ensure_ascii=False)
                except Exception as e:
                    log('analisi prima/dopo non riuscita', nostro, str(e)[:150]); continue
            for n_ in [x.strip() for x in VARIANTE.split(',') if x.strip() in ('2', '3')]:
                # 2 = altro sito antico e altro luogo di oggi; 3 = stessi luoghi visti da un'altra angolazione, piu' dall'alto
                ant, mod = ((inf.get('antico2') or inf['antico'], inf.get('moderno2') or inf['moderno']) if n_ == '2'
                            else (inf['antico'] + ', seen from a different, higher angle', inf['moderno'] + ', seen from a different, higher angle'))
                try:
                    if FORMATO == 'illustrato':   # 2 = l'altra figura (donna/uomo) e altri luoghi; 3 = stessa figura, altri luoghi
                        fig_ = (inf.get('figure') or ['a historical leader of the country'] * 2)[1 if n_ == '2' else 0]
                        im = crea_ill(fig_, ant, mod, inf['paese'], inf['bandiera'], inf['date'])
                    else:
                        im = crea_pd(ant, mod, inf['paese'], inf['bandiera'], inf['date'])
                except Exception as e:
                    log(f'{nostro}: copertina {n_} non riuscita:', str(e)[:150]); continue
                im.save(os.path.join(OUT, f'{nostro}_{n_}.jpg'), quality=92)
                celle.append((f'copertina {n_}', im))
                log(f'{nostro}: copertina {n_} creata (prima/dopo): {ant[:60]} | {mod[:60]}')
            righe.append((nostro, celle))
            continue
        for n_ in [x.strip() for x in VARIANTE.split(',') if x.strip() in ('2', '3')]:
            fig, mon = (inf['figure'][1], inf['monumento']) if n_ == '2' else (inf['figure'][0], inf['monumento'])
            if n_ == '3':   # stessa impostazione (bandiera + persona + monumento + scritte), cambiano 1-2 elementi forti
                try:
                    t3 = claude([{'type': 'text', 'text': f'Paese: {inf["paese"]} ({inf["bandiera"]}). Monumento gia\' usato: {inf["monumento"]}. Persona gia\' usata: {inf["figure"][0]}. '
                                  'Rispondi SOLO JSON in inglese: {"monumento": "un ALTRO monumento reale, famosissimo e diverso del paese", '
                                  '"oggetto": "un oggetto storico simbolico che la persona tiene in mano (es. a golden ankh, a papyrus scroll)"}'}], 300)
                    j3 = json.loads(t3[t3.find('{'): t3.rfind('}') + 1])
                    mon = j3.get('monumento') or mon
                    fig = fig + ', holding ' + (j3.get('oggetto') or 'a historical symbolic object') + ' at chest height, slightly more intense and determined expression'
                except Exception as e:
                    log('variante 3: cambi non trovati, cambio solo il monumento:', str(e)[:100]); mon = mon + ' seen from a different angle'
            im = None
            for tentativo in range(3):
                r = fal('fal-ai/nano-banana-2', {'prompt': prompt_con_testo(inf['bandiera'], fig, mon, 1, inf['paese'], inf['date']),
                                                 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
                prova = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
                if testo_ok(prova, inf['paese'], inf['date']):
                    im = prova; break
            if im is None:
                r = fal('fal-ai/nano-banana-2', {'prompt': prompt_scena(inf['bandiera'], fig, mon, 1), 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
                im = titolo(ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS), inf['paese'], inf['date'], [.20, .02, .74, .42])
            im.save(os.path.join(OUT, f'{nostro}_{n_}.jpg'), quality=92)
            celle.append((f'copertina {n_}', im))
            log(f'{nostro}: copertina {n_} creata ({"altra persona" if n_ == "2" else "monumento e oggetto diversi"}): {fig[:70]} | {mon[:50]}')
        righe.append((nostro, celle))
        continue
    if TITOLO_PROVA:
        canale = [('prova', TITOLO_PROVA)]
    canale = canale or video_canale()
    if not TITOLO_PROVA and not re.fullmatch(r'[\w-]{11}', nostro):   # parola del titolo -> ID del nostro video
        trovato = next((v for v, t in canale if nostro.lower() in t.lower()), None)
        if not trovato:
            log('video non trovato sul canale:', nostro); continue
        log(f'"{nostro}" -> {trovato}'); nostro = trovato
    tit = next((t for v, t in canale if v == nostro), '')
    gia = os.path.join(OUT, f'{nostro}_1.jpg')
    if APPLICA and os.path.exists(gia) and str(E('RIFAI', '') or 'NO').upper() != 'SI':   # copertina gia' approvata in prova: si carica quella, non se ne fa una nuova
        try:
            http(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={nostro}', open(gia, 'rb').read(),
                 dict(AUTH, **{'Content-Type': 'image/jpeg'}), metodo='POST')
            log(f'{nostro}: copertina 1 approvata CARICATA su YouTube'); testo_log.append(f'{nostro}: copertina 1 approvata caricata')
            if not any(x.get('video') == nostro for x in registro()):
                registra(nostro, 'uomo', 'donna')
        except Exception as e:
            dett = ''
            try:
                dett = e.read().decode()[:200]
            except Exception:
                pass
            log(f'{nostro}: NON caricata ({str(e)[:60]} {dett})' + (' -> caricala a mano da YouTube Studio: copertine_storia/' + nostro + '_1.jpg' if getattr(e, 'code', 0) == 403 else ''))
        continue
    orig = copertina_yt(comp) if comp else None   # senza competitor (modo automatico) basta il titolo del nostro video
    if comp and orig is None:
        log('copertina del competitor non trovata:', comp)
    try:
        cont = ([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(orig, 768)}}] if orig is not None else [])
        txt = claude(cont + [{'type': 'text', 'text': DOMANDA.format(titolo=tit) + ('' if orig is not None else ' (Nessuna immagine: ricava tutto dal titolo e da cio\' che sai della storia del paese.)')}])
        an = json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
    except Exception as e:
        log('analisi non riuscita', nostro, str(e)[:200]); continue
    paese, date, band = str(an.get('paese') or '').upper().strip(), str(an.get('date') or '').strip(), str(an.get('bandiera') or '').strip()
    # 1 = la figura come stabilito (uomo); 2 = stessa copertina con la donna al posto dell'uomo (solo se la 1 non funziona)
    figure = [an.get('uomo') or 'an ancient king', an.get('donna') or 'an ancient queen']
    # ALTERNANZA tra i video: uno parte con l'uomo, il successivo con la donna (confronto giusto: stessa fase di lancio)
    primo = 'uomo' if len(registro()) % 2 == 0 else 'donna'
    if primo == 'donna':
        figure = figure[::-1]
    tipi_ = [primo, 'donna' if primo == 'uomo' else 'uomo']
    monum = [an.get('monumento') or 'a famous ancient monument of the country'] * 2
    POPOLO['tratti'] = ('The person must look like a REAL native of ' + band + ': ' + str(an.get('popolo') or '') + '. Never features of other peoples.') if an.get('popolo') else ''
    log(f'{nostro} <- {comp} | {paese} / {date} | uomo: {figure[0]} | donna: {figure[1]} | {monum[0]} | {an.get("popolo")}')
    testo_log.append(f'=== {nostro} (originale {comp})\n{paese} / {date}')

    def fai(k):
        if FORMATO == 'illustrato':
            ant = an.get('antico') or f'ancient {band} with its most famous ancient monument'
            mod = an.get('moderno') or f'{band} today with its most famous landmark and a modern city skyline'
            fig = figure[0]
            try:
                im = crea_ill(fig, ant, mod, paese, band, date)
                im.save(os.path.join(OUT, f'{nostro}_{k}.jpg'), quality=92)
                log(f'  copertina {k} (illustrata): {fig[:60]} | {ant[:50]} | {mod[:50]}')
                return k, 0, im, [fig, ant, mod]
            except Exception as e:
                log(f'  copertina {k} non riuscita:', str(e)[:200]); return k, 0, None, [fig, ant, mod]
        if FORMATO == 'prima_dopo':
            ant, mod = an.get('antico') or f'the most ancient famous city of {band} as it was at the time of {date_freccia(date)[0]}', an.get('moderno') or f'{band} today with its most famous landmark and a modern city'
            try:
                im = crea_pd(ant, mod, paese, band, date)
                im.save(os.path.join(OUT, f'{nostro}_{k}.jpg'), quality=92)
                log(f'  copertina {k} (prima/dopo): {ant[:70]} | {mod[:70]}')
                return k, 0, im, [ant, mod]
            except Exception as e:
                log(f'  copertina {k} non riuscita:', str(e)[:200]); return k, 0, None, [ant, mod]
        fig, mon = figure[(k - 1) % len(figure)], monum[(k - 1) % len(monum)]
        try:
            im = None
            for tentativo in range(3):   # come le prove fatte con Gemini: scritta disegnata nella copertina, controllata lettera per lettera
                r = fal('fal-ai/nano-banana-2', {'prompt': prompt_con_testo(band, fig, mon, k - 1, paese, date), 'aspect_ratio': '16:9', 'resolution': '2K',
                                                 'output_format': 'jpeg', 'num_images': 1})
                prova = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
                if testo_ok(prova, paese, date):
                    im = prova; break
            if im is None:   # riserva: scena senza scritte + titolo scritto dallo script (mai una scritta sbagliata online)
                log('    3 tentativi con scritta sbagliata: uso la scena senza scritte e scrivo il titolo io')
                r = fal('fal-ai/nano-banana-2', {'prompt': prompt_scena(band, fig, mon, k - 1), 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
                im = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
                im = titolo(im, paese, date, zona_titolo(im))
            im.save(os.path.join(OUT, f'{nostro}_{k}.jpg'), quality=92)
            log(f'  copertina {k}: {fig} | {mon}')
            return k, 0, im, [fig, mon]
        except Exception as e:
            log(f'  copertina {k} non riuscita:', str(e)[:200]); return k, 0, None, [fig, mon]
    json.dump({'paese': paese, 'date': date, 'bandiera': band, 'figure': figure, 'monumento': monum[0], 'tratti': POPOLO.get('tratti', ''), 'tipi': tipi_,
               'formato': FORMATO, 'antico': an.get('antico') or '', 'moderno': an.get('moderno') or '', 'antico2': an.get('antico2') or '', 'moderno2': an.get('moderno2') or ''},
              open(info_p, 'w'), ensure_ascii=False)
    quante = [1]   # SEMPRE e solo la copertina 1 (anche in prova): la 2 si crea solo se la chiede il Rotatore CTR
    with ThreadPoolExecutor(3) as ex:
        fatte = list(ex.map(fai, quante))
    for k, perc, im, cambi in fatte:
        testo_log.append(f'{k} = ' + ' | '.join(cambi))
    stato = 'solo anteprima'
    prima = next((im for k, perc, im, c in fatte if k == 1 and im is not None), None)
    if APPLICA and prima is not None:
        try:
            b = io.BytesIO(); prima.save(b, 'JPEG', quality=90)
            http(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={nostro}', b.getvalue(),
                 dict(AUTH, **{'Content-Type': 'image/jpeg'}), metodo='POST')
            stato = 'copertina 1 CARICATA su YouTube'
        except Exception as e:
            dett = ''
            try:
                dett = e.read().decode()[:200]
            except Exception:
                pass
            stato = 'NON caricata (' + str(e)[:60] + ' ' + dett + ')' + (' -> caricala a mano da YouTube Studio: copertine_storia/' + nostro + '_1.jpg' if getattr(e, 'code', 0) == 403 else '')
    log('  ' + stato + f' | parte con: {tipi_[0]}')
    testo_log.append(stato + f' | parte con: {tipi_[0]}\n')
    if APPLICA and prima is not None:
        registra(nostro, tipi_[0], tipi_[1])
    righe.append((nostro, [('ORIGINALE', orig)] + [(f'copertina {k}', im) for k, perc, im, c in fatte]))

open(os.path.join(OUT, 'copertine.txt'), 'a', encoding='utf-8').write(time.strftime('%Y-%m-%d %H:%M') + '\n' + '\n'.join(testo_log) + '\n')
if righe:
    tw, th = 400, 225
    S = Image.new('RGB', (tw * 4 + 40, (th + 40) * len(righe) + 10), 'white'); d = ImageDraw.Draw(S)
    try:
        fe = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    except Exception:
        fe = ImageFont.load_default()
    for i, (vid, celle) in enumerate(righe):
        y = i * (th + 40) + 5
        for j, (nome, im) in enumerate(celle):
            if im is not None:
                S.paste(im.resize((tw, th)), (j * (tw + 10), y + 30))
            d.text((j * (tw + 10) + 4, y + 4), f'{vid}  {nome}' if j == 0 else nome, font=fe, fill='black')
    S.save(os.path.join(OUT, 'confronto.jpg'), quality=88)
log('FATTO | APPLICA =', APPLICA)
