#!/usr/bin/env python3
"""COPERTINA "FOTO SIMBOLO" (stile A3a, scelto il 30 ott 2026 per Storia in Minuti; vale per ogni canale con copertina_stile = foto):
pannello blu a sinistra con "TUTTA LA STORIA" (giallo), il NOME del paese enorme (bianco) e gli anni (rosso), a destra la foto
di un luogo SIMBOLO del paese presa da Pexels, ritagliata sul monumento. Ogni foto e' CONTROLLATA da Claude: paese giusto,
simbolo riconoscibile, ben visibile. Le scritte stanno sempre dentro i loro rettangoli. Mai nulla nell'angolo del timer.
Uso: crea(titolo_video, lingua, path, info_extra='') -> path (o None se nessuna foto supera il controllo)."""
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


def piano(titolo, lingua='it', extra=''):
    """Dal titolo del video: nome del paese, anni, ricerche Pexels dei luoghi simbolo."""
    lin = {'it': 'italiano', 'en': 'English'}.get(lingua, lingua)
    return _claude([{'type': 'text', 'text':
        f'Titolo di un video YouTube sulla storia completa di un paese: "{titolo}". {extra}\nRispondi SOLO JSON: '
        f'{{"nome": "nome del paese (o impero) in {lin}, MAIUSCOLO, breve (es. STATI UNITI, IRAN, IMPERO ROMANO)", '
        f'"anni": "il periodo raccontato, corto, in {lin} (es. 3000 a.C. → 2026, 660 a.C. → 2026); se il titolo non lo dice: 5.000 ANNI DI STORIA o simile, solo se vero", '
        '"simboli": ["6 ricerche Pexels in inglese, dalla piu\' famosa: i monumenti e luoghi SIMBOLO del paese che un italiano riconosce subito '
        '(es. Taj Mahal; Giza pyramids; Colosseum Rome; Statue of Liberty New York; Persepolis Iran), con il nome del luogo e del paese; '
        'se del paese ci sono poche foto famose, le ultime 2 ricerche siano paesaggi tipici e inconfondibili con il nome del paese (es. Afghanistan mountains valley, Jerusalem old city walls)"]}'}],
        os.environ.get('MODELLO_COPERTINA', 'claude-sonnet-5-5'))


def _pexels(q):
    url = 'https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'per_page': 6, 'orientation': 'landscape', 'size': 'large'})
    req = urllib.request.Request(url, headers={'Authorization': os.environ.get('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read()).get('photos') or []


def foto_simbolo(nome, simboli, modello='claude-sonnet-5-5'):
    """La foto migliore tra quelle che superano il controllo di Claude. (foto, riquadro del soggetto 0-1) oppure (None, None)."""
    domanda = (f'Questa foto andra\' sulla copertina di un video su TUTTA LA STORIA di: {nome}. Rispondi SOLO JSON: '
               '{"cosa": "cosa mostra esattamente (luogo, citta, paese)", "paese_giusto": true/false (il luogo si trova DAVVERO in quel paese? se non ne sei sicuro: false), '
               '"simbolo": 1-10 (quanto e\' un simbolo famoso e riconoscibile di quel paese per un italiano), "visibile": 1-10 (quanto il soggetto e\' grande, nitido, ben illuminato), '
               '"pulita": true/false (false se davanti o attorno al soggetto ci sono negozi, insegne, auto, cartelli, cantieri, impalcature, cavi o folle che rovinano la foto), '
               '"box": [x0, y0, x1, y1] (riquadro del soggetto principale, frazioni 0-1 della foto)}')
    candidati = []
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
            if g.get('paese_giusto') and g.get('pulita', True) and (g.get('visibile') or 0) >= 7:
                candidati.append(((g.get('simbolo') or 0) + (g.get('visibile') or 0), g.get('simbolo') or 0, im, g.get('box') or [.2, .2, .8, .8]))
        if any(c[1] >= 9 and c[0] >= 17 for c in candidati):
            break
    buoni = [c for c in candidati if c[1] >= 8] or [c for c in candidati if c[1] >= 5]   # prima i simboli famosi, poi almeno il paese giusto
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


def disegna(nome, anni, foto, box, path, testo_alto='TUTTA LA STORIA'):
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
    if anni:
        _box(d, x, y + 14, anni, _adatta(anni, 60, larg), ROSSO, BIANCO)
    im.convert('RGB').save(path, quality=93)
    return path


def crea(titolo, lingua, path, extra=''):
    p = piano(titolo, lingua, extra)
    log('copertina foto:', json.dumps(p, ensure_ascii=False)[:300])
    foto, box = foto_simbolo(p.get('nome') or titolo, p.get('simboli') or [])
    if foto is None:
        log('copertina foto: nessuna foto ha superato il controllo'); return None
    return disegna(str(p.get('nome') or '').upper(), str(p.get('anni') or ''), foto, box, path,
                   'TUTTA LA STORIA' if lingua == 'it' else 'THE WHOLE HISTORY')
