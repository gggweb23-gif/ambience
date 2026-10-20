#!/usr/bin/env python3
"""
STORIA IN MINUTI - copertine "BANDIERA + SOVRANO": stile del canale, niente copiato dal competitor (dal competitor si prende solo il tipo di figura).
  meta' sinistra: la bandiera del paese, vera stoffa al vento;   meta' destra: un sovrano dell'epoca FOTOREALISTICO, persona nuova;
  dietro: un monumento reale e riconoscibile del paese, cielo vero e colori veri;   in alto al centro: NOME DEL PAESE grande + date (scritti dallo script).
  3 copertine per video: 1 va online, 2 e 3 sono pronte per il cambio se il CTR resta basso (altro monumento, altra figura, altra inquadratura).
Uscita: copertine_storia/<video>_1.jpg, _2.jpg, _3.jpg (+ _base senza scritte) + confronto.jpg. APPLICA=SI carica la 1 su YouTube.
Env: VIDEO = "nostroID:competitorID,..." (al posto del nostro ID va bene una parola del titolo, es. "India:p9IIGdg91fE")
"""
import base64, io, json, os, re, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageOps

E = os.environ.get
APPLICA = str(E('APPLICA', '') or 'NO').strip().upper() == 'SI'
LIVELLI = [int(x) for x in (E('LIVELLI', '') or '40,50,60').split(',') if x.strip()]
COPPIE = [x.strip().split(':', 1) for x in (E('VIDEO', '') or '').split(',') if ':' in x]
OUT = os.path.join(os.getcwd(), 'copertine_storia'); os.makedirs(OUT, exist_ok=True)
FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
BOLLINO = os.path.join(os.getcwd(), 'bollino_storia_in_minuti.png')


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
 "uomo": "in inglese: la figura maschile dello stesso tipo della figura principale della copertina, con abiti e gioielli storici del paese (es. 'an ancient Indian king with a golden crown and white and red silk')",
 "donna": "in inglese: la figura femminile corrispondente dello stesso rango ed epoca (es. 'an ancient Indian queen with a golden crown and a red silk sari')",
 "popolo": "in inglese: i tratti del viso REALI e tipici della popolazione storica di quel paese (es. 'authentic native Afghan (Pashtun) facial features: olive skin, strong nose, dark deep-set eyes'), mai tratti di altri popoli",
 "monumento": "in inglese: UN monumento reale e famoso del paese, il piu' riconoscibile (es. 'the Great Stupa of Sanchi')"}}"""


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


def norm(t):
    return re.sub(r'[^A-Z0-9]', '', str(t).upper())


def testo_ok(im, paese, date):
    """Claude legge la copertina: ci devono essere ESATTAMENTE il paese e le date, nient'altro."""
    try:
        t = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(im, 1024)}},
                    {'type': 'text', 'text': 'Trascrivi ESATTAMENTE tutto il testo scritto in questa immagine, lettera per lettera, senza correggere errori. Solo il testo, su una riga.'}], 300)
        ok = norm(t) == norm(paese + date)
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
    if VARIANTE == '2':
        if not os.path.exists(info_p):
            log(nostro, ': mancano i dati della copertina 1, copertina 2 non creata'); continue
        inf = json.load(open(info_p))
        POPOLO['tratti'] = inf.get('tratti', '')
        k = 2
        im = None
        for tentativo in range(3):
            r = fal('fal-ai/nano-banana-2', {'prompt': prompt_con_testo(inf['bandiera'], inf['figure'][1], inf['monumento'], 1, inf['paese'], inf['date']),
                                             'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
            prova = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
            if testo_ok(prova, inf['paese'], inf['date']):
                im = prova; break
        if im is None:
            r = fal('fal-ai/nano-banana-2', {'prompt': prompt_scena(inf['bandiera'], inf['figure'][1], inf['monumento'], 1), 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
            im = titolo(ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS), inf['paese'], inf['date'], [.20, .02, .74, .42])
        im.save(os.path.join(OUT, f'{nostro}_2.jpg'), quality=92)
        log(f'{nostro}: copertina 2 creata ({inf["tipi"][1]}), la mettera\' online il Rotatore CTR')
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
    json.dump({'paese': paese, 'date': date, 'bandiera': band, 'figure': figure, 'monumento': monum[0], 'tratti': POPOLO.get('tratti', ''), 'tipi': tipi_},
              open(info_p, 'w'), ensure_ascii=False)
    quante = [1, 2] if not APPLICA else [1]   # in prova si vedono tutte e due; online va solo la 1 (risparmio: la 2 solo se serve)
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
