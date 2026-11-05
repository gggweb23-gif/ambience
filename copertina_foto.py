#!/usr/bin/env python3
"""COPERTINA "FOTO SIMBOLO" (stile A3a, scelto il 30 ott 2026 per Storia in Minuti; vale per ogni canale con copertina_stile = foto):
pannello blu a sinistra con "TUTTA LA STORIA" (giallo), il NOME del paese enorme (bianco) e gli anni (rosso), a destra la foto
di un luogo SIMBOLO del paese presa da Pexels, ritagliata sul monumento. Ogni foto e' CONTROLLATA da Claude: paese giusto,
simbolo riconoscibile, ben visibile. Le scritte stanno sempre dentro i loro rettangoli. Mai nulla nell'angolo del timer.
Uso: crea(titolo_video, lingua, path, info_extra='', riserva_max=0) -> path (o None se nessuna foto supera il controllo).
riserva_max = colonna copertina_riserva_max ($ a video): se > 0 e copre il costo, senza foto Pexels valida si fa UNA foto AI dello stesso simbolo."""
import base64, io, json, os, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

W, H = 1280, 720
GIALLO, ROSSO, NERO, BIANCO, BLU = (255, 214, 0), (226, 35, 35), (12, 12, 16), (255, 255, 255), (16, 52, 120)
DIR_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'font')
REGISTRO = []
log = print


def _font_file():
    p = os.path.join(DIR_FONT, 'Anton-Regular.ttf')
    if not os.path.exists(p):
        os.makedirs(DIR_FONT, exist_ok=True)
        b = urllib.request.urlopen('https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf', timeout=60).read()
        open(p, 'wb').write(b)
    return p


def font(s):
    return ImageFont.truetype(_font_file(), int(s))


def _claude(contenuto, modello, max_tokens=400):
    corpo = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': contenuto}]}
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(corpo).encode(),
                                 headers={'x-api-key': os.environ.get('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    t = ''.join(b.get('text', '') for b in json.loads(urllib.request.urlopen(req, timeout=120).read()).get('content', []))
    return json.JSONDecoder().raw_decode(t[t.find('{'):])[0]


def piano(titolo, lingua='it', extra='', nota=''):
    """Dal titolo del video: il SOGGETTO del titolo (paese, impero, citta', regione...), anni, ricerche Pexels dei luoghi simbolo."""
    lin = {'it': 'italiano', 'en': 'English'}.get(lingua, lingua)
    return _claude([{'type': 'text', 'text':
        f'Titolo di un video YouTube sulla storia completa di qualcosa: "{titolo}". {extra}\n{nota}Rispondi SOLO JSON: '
        f'{{"nome": "il SOGGETTO ESATTO del titolo, in {lin}, MAIUSCOLO, breve: quello che il titolo dice (paese, impero, citta\', regione, '
        f'azienda...). Se il titolo parla di una citta\' scrivi la citta\', MAI il paese in cui si trova (es. titolo su Las Vegas -> LAS VEGAS, non STATI UNITI; '
        f'titolo su Venezia -> VENEZIA, non ITALIA). Esempi: STATI UNITI, IRAN, IMPERO ROMANO, LAS VEGAS", '
        f'"anni": "il periodo raccontato, corto, in {lin} (es. 3000 a.C. → 2026, 660 a.C. → 2026); se il titolo non lo dice: 5.000 ANNI DI STORIA o simile, solo se vero", '
        '"simboli": ["6 ricerche Pexels in inglese, dalla piu\' famosa: i monumenti e luoghi SIMBOLO di quel soggetto (non del paese intorno) che un italiano riconosce subito '
        '(es. Taj Mahal; Giza pyramids; Colosseum Rome; Statue of Liberty New York; Las Vegas Strip; Persepolis Iran), con il nome del luogo; '
        'se ci sono poche foto famose, le ultime 2 ricerche siano paesaggi tipici e inconfondibili di quel soggetto (es. Afghanistan mountains valley, Jerusalem old city walls)"]}'}],
        os.environ.get('MODELLO_COPERTINA', 'claude-sonnet-5-5'))


def _norm(t):
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFD', str(t).lower()) if unicodedata.category(ch) != 'Mn')


def nome_nel_titolo(nome, titolo):
    """CONTROLLO: il nome scritto in copertina deve essere il soggetto del titolo (almeno una parola importante del nome nel titolo)."""
    import re
    pt = set(re.findall(r'\w+', _norm(titolo)))
    pn = [w for w in re.findall(r'\w+', _norm(nome)) if len(w) > 2 and w not in ('impero', 'regno', 'repubblica', 'storia', 'della', 'delle', 'the', 'empire', 'kingdom')]
    return bool(pn) and any(w in pt or w.rstrip('aeio') in {x.rstrip('aeio') for x in pt} for w in pn)


def _pexels(q):
    url = 'https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'per_page': 6, 'orientation': 'landscape', 'size': 'large'})
    req = urllib.request.Request(url, headers={'Authorization': os.environ.get('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read()).get('photos') or []


def foto_simbolo(nome, simboli, modello='claude-sonnet-5-5', pulita=True):
    """La foto migliore tra quelle che superano il controllo di Claude. (foto, riquadro del soggetto 0-1) oppure (None, None)."""
    domanda = (f'Questa foto andra\' sulla copertina di un video su TUTTA LA STORIA di: {nome}. Rispondi SOLO JSON: '
               '{"cosa": "cosa mostra esattamente (luogo, citta, paese)", "paese_giusto": true/false (il luogo si trova DAVVERO in/a ' + nome + '? una foto di un altro luogo dello stesso paese = false; se non ne sei sicuro: false), '
               '"simbolo": 1-10 (quanto e\' un simbolo famoso e riconoscibile di ' + nome + ' per un italiano), "visibile": 1-10 (quanto il soggetto e\' grande, nitido, ben illuminato), '
               '"pulita": true/false (false se davanti o attorno al soggetto ci sono negozi, insegne, auto, cartelli, cantieri, impalcature, cavi o folle che rovinano la foto; '
               'ma se le insegne o le luci SONO il simbolo stesso, es. le insegne al neon di Las Vegas, allora e\' pulita), '
               '"box": [x0, y0, x1, y1] (riquadro del soggetto principale, frazioni 0-1 della foto)}')
    candidati, riserva = [], []
    for q in simboli[:8]:
        try:
            foto = _pexels(q)
        except Exception as e:
            log('pexels', q, str(e)[:80]); continue
        for f in foto[:4]:
            try:
                im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(f['src']['large2x'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())).convert('RGB')
                x = im.copy(); x.thumbnail((900, 900)); buf = io.BytesIO(); x.save(buf, 'JPEG', quality=85)
                g = _claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                             {'type': 'text', 'text': domanda}], modello, 300)
            except Exception as e:
                log('controllo foto non riuscito', q, str(e)[:100]); continue
            REGISTRO.append(f"{nome} | {q} | {g.get('cosa')} | paese {g.get('paese_giusto')} | simbolo {g.get('simbolo')} | visibile {g.get('visibile')} | {f['url']}")
            log('foto copertina:', REGISTRO[-1][:200])
            if g.get('paese_giusto') and (g.get('pulita', True) or not pulita) and (g.get('visibile') or 0) >= 7:
                candidati.append(((g.get('simbolo') or 0) + (g.get('visibile') or 0), g.get('simbolo') or 0, im, g.get('box') or [.2, .2, .8, .8]))
            elif g.get('paese_giusto') and (g.get('visibile') or 0) >= 5 and (g.get('simbolo') or 0) >= 6:   # riserva: luogo giusto ma foto meno perfetta
                riserva.append(((g.get('simbolo') or 0) + (g.get('visibile') or 0), g.get('simbolo') or 0, im, g.get('box') or [.2, .2, .8, .8]))
        if any(c[1] >= 9 and c[0] >= 17 for c in candidati):
            break
    buoni = [c for c in candidati if c[1] >= 8] or [c for c in candidati if c[1] >= 5]   # prima i simboli famosi, poi almeno il paese giusto
    if not buoni and riserva:   # 5 nov: meglio una foto giusta un po' meno perfetta che una copertina in uno stile diverso dal canale
        log('copertina foto: uso la foto di riserva (luogo giusto, meno perfetta)')
        buoni = riserva
    if not buoni:
        return None, None
    m = max(buoni, key=lambda c: c[0])
    return m[2], m[3]


def ritaglia_su(im, box, w, h, quota=.78):
    W0, H0 = im.size; x0, y0, x1, y1 = [float(c) for c in box]
    bw, bh = max(.05, x1 - x0) * W0, max(.05, y1 - y0) * H0; cx, cy = (x0 + x1) / 2 * W0, (y0 + y1) / 2 * H0
    sc = min(w * quota / bw, h * quota / bh); sc = max(sc, w / W0, h / H0)
    im2 = im.resize((int(W0 * sc), int(H0 * sc)), Image.LANCZOS)
    left = min(max(0, cx * sc - w / 2), im2.width - w); top = min(max(0, cy * sc - h / 2), im2.height - h)
    return im2.crop((int(left), int(top), int(left) + w, int(top) + h))


def _box(d, x, y, t, s, fondo, col, padx=26, pady=14):
    f = font(s); l, tp, r, b = d.textbbox((0, 0), t, font=f)
    w, h = r - l + 2 * padx, b - tp + 2 * pady
    d.rectangle([x + 8, y + 10, x + w + 8, y + h + 10], fill=(0, 0, 0, 150))
    d.rectangle([x, y, x + w, y + h], fill=fondo)
    d.text((x + padx - l, y + pady - tp), t, font=f, fill=col)
    return h


def _adatta(t, s, larg, padx=26):
    while s > 36 and font(s).getlength(t) + 2 * padx > larg:
        s -= 4
    return s


def _anno(a, lingua='it'):
    a = int(a)
    return (f"{-a:,}".replace(',', '.') + (' a.C.' if lingua == 'it' else ' BC')) if a < 0 else str(a)


def linea_tempo(d, tappe, x0, x1, y, stile='piena', lingua='it'):
    """La stessa linea del tempo del video: tappe equidistanti, tutta gia' percorsa (gialla) fino a oggi, punto finale grande."""
    tappe = sorted(set(int(t) for t in tappe))
    if len(tappe) < 2:
        return
    if len(tappe) > 4:   # in copertina al massimo 4 tappe: prima, due in mezzo, oggi (si leggono da telefono)
        tappe = [tappe[0], tappe[len(tappe) // 3], tappe[2 * len(tappe) // 3], tappe[-1]]
    pos = lambda i: x0 + i * (x1 - x0) / (len(tappe) - 1)
    f = font(30 if stile != 'mini' else 26)
    if stile == 'piena':   # fascia scura con bordi tondi
        d.rounded_rectangle([x0 - 50, y - 46, x1 + 50, y + 60], radius=24, fill=(10, 14, 24, 200))
    d.line([(x0, y), (x1, y)], fill=GIALLO, width=9)
    for i, t in enumerate(tappe):
        x = pos(i); ultimo = i == len(tappe) - 1
        rr = 17 if ultimo else 10
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=GIALLO, outline=BIANCO if ultimo else NERO, width=4)
        tx = _anno(t, lingua); l, tp, r_, b = d.textbbox((0, 0), tx, font=f); w = r_ - l
        xa = min(max(x - w / 2, x0 - 40), x1 + 40 - w)
        sopra = stile == 'mini' and i % 2 == 1   # nel pannello stretto le scritte si alternano sopra e sotto: mai una sull'altra
        ya = y - 24 - (b - tp) if sopra else y + 22
        d.text((xa - l + 3, ya - tp + 3), tx, font=f, fill=(0, 0, 0, 200)); d.text((xa - l, ya - tp), tx, font=f, fill=BIANCO)


def disegna(nome, anni, foto, box, path, testo_alto='TUTTA LA STORIA', tappe=None, linea='', lingua='it'):
    xs = int(W * .42)
    im = Image.new('RGB', (W, H), BLU)
    im.paste(ImageEnhance.Contrast(ImageEnhance.Color(ritaglia_su(foto, box, W - xs, H)).enhance(1.25)).enhance(1.12), (xs, 0))
    im = im.convert('RGBA'); d = ImageDraw.Draw(im)
    d.polygon([(xs - 2, 0), (xs + 60, 0), (xs - 2, H)], fill=BLU)
    larg, x = W * .42 - 60, 40
    y = 70 + _box(d, x, 70, testo_alto, _adatta(testo_alto, 54, larg), GIALLO, NERO) + 30
    parole = nome.split(); s = min(_adatta(p, 190, larg, 0) for p in parole)
    alt = lambda s_: sum(d.textbbox((0, 0), p, font=font(s_))[3] - d.textbbox((0, 0), p, font=font(s_))[1] + 18 for p in parole)
    while s > 60 and y + alt(s) + 110 > H - 30:
        s -= 6
    for p in parole:
        l, tp, r, b = d.textbbox((0, 0), p, font=font(s))
        d.text((x - l + 6, y - tp + 8), p, font=font(s), fill=(0, 0, 0, 160)); d.text((x - l, y - tp), p, font=font(s), fill=BIANCO)
        y += b - tp + 18
    if anni and linea != 'pannello':
        _box(d, x, y + 14, anni, _adatta(anni, 60, larg), ROSSO, BIANCO)
    if tappe and linea == 'pannello':   # al posto della fascia degli anni: la linea del tempo dentro il pannello blu
        linea_tempo(d, tappe, x + 40, x + larg - 50, y + 90, 'mini', lingua)
    elif tappe and linea == 'foto':   # sulla foto, in alto (mai vicino all'angolo del timer in basso a destra)
        linea_tempo(d, tappe, xs + 90, W - 90, 70, 'piena', lingua)
    elif tappe and linea == 'base':   # lungo tutta la copertina, poco sopra il bordo basso ma finisce prima dell'angolo del timer
        linea_tempo(d, tappe, 90, W - 330, H - 120, 'piena', lingua)
    im.convert('RGB').save(path, quality=93)
    return path


COSTO_AI = 0.08   # $ stimati per 1 immagine fal nano-banana-2 a 1K (la parte foto della copertina e' 742x720: basta e avanza)


def _fal_immagine(prompt):
    """Una immagine fal nano-banana-2 (FAL_KEY), 16:9, senza testo. Restituisce PIL.Image."""
    import time
    h = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', ''), 'Content-Type': 'application/json'}
    rq = lambda u, d=None: json.loads(urllib.request.urlopen(urllib.request.Request(u, data=json.dumps(d).encode() if d is not None else None, headers=h), timeout=120).read())
    inv = rq('https://queue.fal.run/fal-ai/nano-banana-2', {'prompt': prompt, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1})
    for _ in range(100):
        time.sleep(4); st = rq(inv['status_url'])
        if st.get('status') == 'COMPLETED':
            url = rq(inv['response_url'])['images'][0]['url']
            return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read())).convert('RGB')
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:200])
    raise RuntimeError('fal: tempo scaduto')


def foto_ai(nome, simboli, riserva_max=0.0):
    """SECONDO TENTATIVO (5 nov, Giorgio): nessuna foto Pexels valida -> UNA foto fotorealistica creata con l'AI del simbolo del soggetto,
    disegnata poi con lo STESSO pannello A3a. Solo se riserva_max (colonna copertina_riserva_max, $ a video) copre il costo stimato."""
    try:
        riserva_max = float(str(riserva_max or 0).replace(',', '.').replace('$', '').replace('€', '').strip() or 0)
    except ValueError:
        riserva_max = 0.0
    if riserva_max <= 0:
        return None, None
    if COSTO_AI > riserva_max + 1e-9 or not os.environ.get('FAL_KEY'):
        log(f'copertina foto: secondo tentativo AI saltato (costo stimato {COSTO_AI:.2f} $ > copertina_riserva_max {riserva_max:.2f} $ o FAL_KEY mancante)')
        return None, None
    soggetto = (simboli or [nome])[0]
    prompt = (f'Photorealistic professional travel photograph of {soggetto} ({nome}), the most famous and recognizable landmark, exactly as it really looks, '
              'shown WHOLE, big and sharp in the centre of the frame, golden hour light, clear sky, vivid natural colours, high contrast. '
              'No people in the foreground, no cars, no signs, no scaffolding. Absolutely NO text, letters, numbers, logos or watermark.')
    log(f'copertina foto: secondo tentativo con foto AI di "{soggetto}" (costo stimato {COSTO_AI:.2f} $, tetto {riserva_max:.2f} $)')
    try:
        im = _fal_immagine(prompt)
    except Exception as e:
        log('copertina foto: foto AI non riuscita:', str(e)[:150]); return None, None
    try:
        import costi as CO
        CO.registra('fal', 'fal-ai/nano-banana-2', dollari=COSTO_AI, nota='copertina foto riserva AI')
    except Exception:
        pass
    return im, [.15, .1, .85, .9]


def crea(titolo, lingua, path, extra='', riserva_max=0.0):
    p = piano(titolo, lingua, extra)
    if not nome_nel_titolo(p.get('nome') or '', titolo):   # CONTROLLO: mai in copertina un soggetto diverso dal titolo (31 ott: Las Vegas -> STATI UNITI)
        log('copertina foto: nome', p.get('nome'), 'non e\' il soggetto del titolo, rifaccio')
        p = piano(titolo, lingua, '', f'ATTENZIONE: "{p.get("nome")}" e\' sbagliato, non e\' il soggetto del titolo. Il nome deve essere scritto nel titolo. ')
        if not nome_nel_titolo(p.get('nome') or '', titolo):
            log('COPERTINA BLOCCATA: il nome', p.get('nome'), 'non corrisponde al titolo', titolo); return None
    log('copertina foto:', json.dumps(p, ensure_ascii=False)[:300])
    foto, box = foto_simbolo(p.get('nome') or titolo, p.get('simboli') or [])
    if foto is None:   # stesso stile del canale: solo la foto cambia origine (AI), mai un'altra grafica
        log('copertina foto: nessuna foto ha superato il controllo')
        foto, box = foto_ai(p.get('nome') or titolo, p.get('simboli') or [], riserva_max)
    if foto is None:
        return None
    return disegna(str(p.get('nome') or '').upper(), str(p.get('anni') or ''), foto, box, path,
                   'TUTTA LA STORIA' if lingua == 'it' else 'THE WHOLE HISTORY')
