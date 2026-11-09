#!/usr/bin/env python3
"""PROVA STILE GLOAM v6 (9 nov, Giorgio: "niente foto stupide di Pexels, tipo uno con le mani in testa: pubblico professionale, argomento serio,
tutte immagini coerenti col canale"). Foto E clip passano tutte dal controllo di Claude Haiku con criteri da documentario finanziario serio:
scartate pose da stock (emozioni esagerate, mani in testa, risate, strette di mano, modelli in posa) e soggetti non pertinenti.
Base: PROVA STILE GLOAM v5 (9 nov, Giorgio: "se non serve il contorno nero non metterlo; deve sempre succedere qualcosa, una sottolineatura,
una scritta che compare; mai una schermata ferma 3-4 secondi; dinamicita' continua quando non c'e' un pezzo di video").
Rispetto alla v4: foto a TUTTO SCHERMO (niente cornice nera), schede/numeri/calendari/classifiche su FOTO COERENTE sfocata (non sul nero),
un "evento" animato al massimo ogni 1,2-1,5 s (scritta a macchina, sottolineatura rossa che si disegna, evidenziatore, timbro, numero che corre, cerchio),
controllo dei fatti (secondo passaggio di Claude), controllo che ogni foto Pexels c'entri (Claude Haiku guarda la foto), barre senza valore scartate, 60 s.
Uscita: prove_video/Prova_Gloam5/. Non carica niente."""
import base64, io, json, math, os, random, re, subprocess, sys, time, urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3
import prova_gloam4 as G4

E = os.environ.get
OUT = 'prove_video/Prova_Gloam6'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/gloam6'; os.makedirs(LAV, exist_ok=True)
TEMA = E('TEMA') or 'How Knight Capital Lost $440,000,000 in 45 Minutes (August 1, 2012)'
W, H, FPS = 1920, 1080, 30
SERIF, MONO, BOLD = G4.SERIF, G4.MONO, G4.BOLD
CARTA, INCH, ROSSO, CREMA, GIALLO = G4.CARTA, G4.INCH, G4.ROSSO, G4.CREMA, (250, 214, 70)
F, cl, ease, log = G4.F, G4.cl, G4.ease, G3.log
COSTO = G3.COSTO; COSTO['controlli'] = 0.0


def claude(prompt, modello='claude-sonnet-5-5', sforzo='medium', immagine=None, max_tokens=16000):
    cont = [{'type': 'text', 'text': prompt}]
    if immagine is not None:
        b = io.BytesIO(); immagine.convert('RGB').resize((512, int(512 * immagine.height / immagine.width))).save(b, 'JPEG', quality=80)
        cont.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}})
    dati = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': cont}]}
    if 'haiku' not in modello:
        dati.update({'thinking': {'type': 'between_tools'}, 'output_config': {'effort': sforzo}})
    j = G3.http('https://api.anthropic.com/v1/messages', dati, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
    u = j.get('usage') or {}
    p_in, p_out = (1e-6, 5e-6) if 'haiku' in modello else (3e-6, 15e-6)
    COSTO['controlli' if immagine is not None else 'claude'] += u.get('input_tokens', 0) * p_in + u.get('output_tokens', 0) * p_out
    return ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')


def leggi_json(t):
    m = re.search(r'\{.*\}', t, re.S).group(0)
    try:
        return json.loads(m)
    except Exception:
        from json_repair import repair_json
        return json.loads(repair_json(m))


# ---------------------------------------------------------------- copione + controllo dei fatti
def copione():
    fc = os.path.join(OUT, 'copione.json')
    if os.path.exists(fc) and not E('TEMA'):
        c = json.load(open(fc)); log('copione ripreso'); return c
    prompt = f"""You write for a new English YouTube channel copying the style of "Gloam" (company/finance disasters told like an investigation; calm precise narrator; editorial visuals).
Topic: {TEMA}. ONLY well documented facts with correct numbers, dates and units (orders vs shares, millions vs billions). If unsure, leave it out. No invented quotes.
EXACTLY 60 seconds: 125-140 spoken words, 15-18 shots (3-5 s each). Shot 1 = hook with the big number. Open a loop in the first 10 s, answer it in the last 10 s. End with "Subscribe for the next one."
Each shot: "voce" (numbers in words) + ONE "tipo" with its fields. EVERY shot also has "sfondo" = 2-4 plain English words for a COHERENT, SERIOUS editorial stock image (Pexels) used full screen or blurred behind the graphic, for a PROFESSIONAL finance audience:
architecture and places (bank headquarters, financial district, stock exchange building, city skyline, empty trading floor, government building), objects and documents (contracts, ledgers, banknotes, coins, newspapers, servers, trading screens, charts on monitors, phones on a desk), maps, archive-looking photos.
NEVER: people making emotional faces or gestures (hands on head, shocked, crying, laughing, celebrating), posed stock models, handshakes, thumbs up, office parties, cartoonish or playful images. And "chiave" = 1-2 words of the on-screen text to underline in red.
- "foto": full-screen real photo. "etichetta" = "PLACE · DATE"; "titolo" = max 5 words headline shown on a paper strip; "sotto" = max 8 words detail line (typed).
- "clip": full-screen stock footage of "sfondo" (must be filmable). "cartello" = 2-4 words CAPITALS, first word is the key word (red).
- "dossier": file card. "scheda" (tab, e.g. "COMPANY FILE"), "nome", "righe": 3-5 [label, value] (short, factual), "timbro" (max 2 words or "").
- "dato": huge number. "numero" (e.g. "$440M", "397M", "45 MIN"), "didascalia" (max 8 words), "fonte".
- "calendario": "mese" (3 letters), "giorno", "titolo" (max 4 words), "sotto" (max 10 words), "timbro" (max 3 words or "").
- "classifica": "titolo", "barre": 2-4 [label, NUMBER > 0, value text] (every bar MUST have a real positive number), "timbro", "fonte".
- "borsa": live trading screen: "ticker", "da", "a" (real prices). Max 1 time, only with the real timing.
Mix: at least 7 "foto"/"clip". Each graphic type at least once. Never two identical types in a row.
Also "titolo" and "copertina": {{"sfondo": "stock photo words", "scritta": "max 3 words, CAPITALS"}}.
Reply ONLY with JSON: {{"titolo": "...", "copertina": {{...}}, "shots": [{{"voce": "...", "tipo": "foto", "sfondo": "...", "chiave": "...", ...}}]}}"""
    c = leggi_json(claude(prompt))
    # secondo passaggio: controllo dei fatti (numeri, unita', date, orari)
    rev = claude("You are a strict fact-checker for a finance documentary. Check EVERY number, unit (orders vs shares, million vs billion), date, time and claim "
                 "in this JSON (fields voce and all on-screen fields) against well documented public sources you know (e.g. SEC filings, major newspapers). "
                 "Fix anything wrong or uncertain (rewrite or remove the claim, keep word counts similar), keep everything else IDENTICAL. "
                 "Reply ONLY with {\"correzioni\": [\"short note of each fix\"], \"json\": <the full corrected JSON>}.\n\n" + json.dumps(c, ensure_ascii=False))
    try:
        r = leggi_json(rev); c = r.get('json') or c
        log('controllo fatti:', r.get('correzioni'))
        c['_correzioni'] = r.get('correzioni')
    except Exception as e:
        log('controllo fatti non riuscito:', e)
    # barre senza valore: via; se ne restano meno di 2 la scena diventa un numero
    for s in c['shots']:
        if s.get('tipo') == 'classifica':
            ok = []
            for b in s.get('barre') or []:
                try:
                    if float(b[1]) > 0:
                        ok.append(b)
                except Exception:
                    pass
            s['barre'] = ok
            if len(ok) < 2:
                s.update({'tipo': 'dato', 'numero': str(ok[0][2]) if ok else '?', 'didascalia': s.get('titolo') or ''})
    json.dump(c, open(fc, 'w'), ensure_ascii=False, indent=1)
    log('copione:', c['titolo'], len(c['shots']), 'scene', sum(len(s['voce'].split()) for s in c['shots']), 'parole')
    return c


# ---------------------------------------------------------------- foto Pexels controllate (Haiku guarda se c'entrano)
USATE = set()
GIUDICE = ('You are the photo editor of a SERIOUS finance documentary for a professional audience (like the Financial Times or Bloomberg). '
           'Search words: "{cerca}". Narration of this shot: "{voce}". Reject (NO) if the image is: a posed stock model, a person with an exaggerated emotion or gesture '
           '(hands on head, shocked, crying, laughing, celebrating, thumbs up, handshake), playful or cartoonish, clearly unrelated to finance/business/the story, '
           'or shows a big visible brand logo. Accept (SI) sober, credible, editorial images coherent with the topic (buildings, places, documents, screens, money, '
           'people working naturally seen from a distance). Answer only SI or NO.')
SERI = ['financial district buildings', 'stock exchange building', 'trading screens dark', 'bank building facade', 'documents desk', 'city skyline night']


def foto(cerca, voce, i):
    for q in [cerca, ' '.join(str(cerca).split()[:2])]:
        try:
            j = G3.http('https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 12}),
                        headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
        except Exception as e:
            log('pexels foto:', e); continue
        prove = 0
        for p in j.get('photos', []):
            if p['id'] in USATE or prove >= 4:
                continue
            prove += 1
            im = Image.open(io.BytesIO(G3.http(p['src']['large2x'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}))).convert('RGB')
            r = claude(GIUDICE.format(cerca=cerca, voce=voce),
                       modello='claude-haiku-4-5-20251001', immagine=im, max_tokens=5)
            if r.strip().upper().startswith('SI'):
                USATE.add(p['id']); log(f'foto {i}: "{q}" -> {p["id"]} ok'); return im
            log(f'foto {i}: {p["id"]} scartata (non c\'entra)')
    for q in SERI:   # niente foto a caso: si ripiega su soggetti seri, sempre controllati
        try:
            j = G3.http('https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 8}),
                        headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
        except Exception:
            continue
        for p in j.get('photos', [])[:3]:
            if p['id'] in USATE:
                continue
            im = Image.open(io.BytesIO(G3.http(p['src']['large2x'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}))).convert('RGB')
            if claude(GIUDICE.format(cerca=q, voce=voce), modello='claude-haiku-4-5-20251001', immagine=im, max_tokens=5).strip().upper().startswith('SI'):
                USATE.add(p['id']); log(f'foto {i}: ripiego serio "{q}" -> {p["id"]}'); return im
    log(f'foto {i}: nessuna adatta'); return G4.foto_pexels('financial district', i)


CLIP_USATE = set()


def clip_seria(cerca, voce, i):
    """Clip Pexels controllata come le foto (un fotogramma guardato da Haiku). Se nessuna va bene -> None (la scena diventa una foto controllata)."""
    for q in [cerca, ' '.join(str(cerca).split()[:2])]:
        try:
            j = G3.http('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 10, 'size': 'medium'}),
                        headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
        except Exception as e:
            log('pexels clip:', e); continue
        prove = 0
        for v in j.get('videos', []):
            if v['id'] in CLIP_USATE or v.get('duration', 0) < 4 or prove >= 4:
                continue
            fs = sorted([f for f in v['video_files'] if (f.get('width') or 0) >= 1280 and f.get('file_type') == 'video/mp4'], key=lambda f: abs((f.get('width') or 0) - 1920))
            if not fs:
                continue
            prove += 1; CLIP_USATE.add(v['id'])
            f = os.path.join(LAV, f'pex_{i:02d}.mp4'); open(f, 'wb').write(G3.http(fs[0]['link'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}))
            if G3.fondo_verde(f):
                continue
            g = os.path.join(LAV, 'fr.jpg'); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(min(2, v.get('duration', 4) / 2)), '-i', f, '-frames:v', '1', g])
            if os.path.exists(g) and claude(GIUDICE.format(cerca=cerca, voce=voce), modello='claude-haiku-4-5-20251001', immagine=Image.open(g), max_tokens=5).strip().upper().startswith('SI'):
                log(f'clip {i}: "{q}" -> {v["id"]} ok'); return f, v.get('duration', 8)
            log(f'clip {i}: {v["id"]} scartata (non seria o fuori tema)')
    return None


# ---------------------------------------------------------------- animazioni (sempre qualcosa che succede)
def scrivi_a_macchina(t, inizio, testo, cps=32):
    n = int(max(0.0, t - inizio) * cps)
    return testo[:n]


def sottolinea(d, x0, x1, y, t, inizio, col=ROSSO, spess=8, dur=.35):
    k = ease((t - inizio) / dur)
    if k > 0:
        d.line((x0, y, x0 + (x1 - x0) * k, y), fill=col, width=spess)


def evidenzia(lay, box, t, inizio, dur=.35):
    k = ease((t - inizio) / dur)
    if k > 0:
        x0, y0, x1, y1 = box
        ImageDraw.Draw(lay).rectangle((x0, y0, x0 + (x1 - x0) * k, y1), fill=GIALLO + (150,))


def cerchio(d, box, t, inizio, dur=.5, col=ROSSO):
    k = ease((t - inizio) / dur)
    if k > 0:
        d.arc(box, -100, -100 + 370 * k, fill=col, width=9)


def kb(img, t, d, i, scala=1.12):
    """Movimento continuo della foto a tutto schermo (spinta + deriva alternata)."""
    z = 1 + (scala - 1) * (t / max(d, .1)); w, h = int(W / z), int(H / z)
    big = img if img.size == (int(W * scala) + 2, int(H * scala) + 2) else img
    x0 = int((big.width - w) * (.5 + (.3 if i % 2 else -.3) * (t / max(d, .1) - .5))); y0 = (big.height - h) // 2
    return big.crop((x0, y0, x0 + w, y0 + h)).resize((W, H), Image.BILINEAR)


def prepara(img, sfoca=False):
    b = ImageOps.fit(img, (int(W * 1.12) + 2, int(H * 1.12) + 2), Image.BILINEAR)
    if sfoca:
        b = b.filter(ImageFilter.GaussianBlur(14))
        b = Image.blend(b, Image.new('RGB', b.size, (12, 11, 10)), .55)
    return b


def ombra(lay, box, r=0):
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle((box[0] + 14, box[1] + 20, box[2] + 14, box[3] + 20), fill=(0, 0, 0, 130))
    lay.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16)))


def chiave_x(f, testo, chiave):
    """Posizione (inizio, fine) della parola chiave dentro il testo, per sottolinearla."""
    k = str(chiave or '').strip()
    i = testo.upper().find(k.upper()) if k else -1
    if i < 0:
        return 0, f.getlength(testo)
    return f.getlength(testo[:i]), f.getlength(testo[:i + len(k)])


def s_foto(s, img, t, d, i):
    fr = kb(s['_bg'], t, d, i).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    # sfumatura in basso per leggere
    gr = Image.linear_gradient('L').resize((W, 520)).point(lambda v: int(v * .8))
    lay.paste((0, 0, 0, 255), (0, H - 520, W, H), gr)
    et = str(s.get('etichetta') or '').upper()
    if et:
        txt = scrivi_a_macchina(t, .15, et)
        dd.rectangle((60, 40, 60 + 74 + sum(F(MONO, 32).getlength(ch) + 4 for ch in et), 100), fill=(0, 0, 0, 150))
        dd.rectangle((78, 63, 90, 75), fill=(230, 160, 40)); G4.scrivi(dd, (104, 50), txt, F(MONO, 32), (235, 230, 220), spaz=4)
    tit = str(s.get('titolo') or '')
    if tit and t > .7:
        k = ease((t - .7) / .35); f = G4.adatta(SERIF, tit, 104, 1500)
        w = f.getlength(tit) + 80; x = 70 - (1 - k) * 600
        ombra(lay, (x, H - 330, x + w, H - 190))
        dd.rectangle((x, H - 330, x + w, H - 190), fill=CARTA + (255,))
        dd.text((x + 40, H - 318), tit, font=f, fill=INCH)
        a, b = chiave_x(f, tit, s.get('chiave'))
        sottolinea(dd, x + 40 + a, x + 40 + b, H - 205, t, 1.25)
    sot = str(s.get('sotto') or '').upper()
    if sot:
        G4.scrivi(dd, (110, H - 150), scrivi_a_macchina(t, 1.7, sot, 38), F(MONO, 34), (235, 230, 220), spaz=4)
    fr.alpha_composite(lay); return fr


def s_dossier(s, img, t, d, i):
    fr = kb(s['_bg'], t, d, i, 1.06).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    e = ease(t / .4); y0 = 150 + (1 - e) * 120
    ombra(lay, (160, y0, 1760, y0 + 800))
    c = G4.carta(1600, 800, 1); lay.paste(c, (160, int(y0)))
    dd.rectangle((220, y0 - 60, 620, y0 + 4), fill=CARTA + (255,)); G4.scrivi(dd, (250, y0 - 46), str(s.get('scheda') or 'FILE').upper()[:16], F(MONO, 34), (80, 75, 65), spaz=3)
    if s.get('_ph') is not None:
        ph = ImageOps.fit(s['_ph'], (420, 520)).convert('L').convert('RGB')
    else:   # sagoma "No photograph"
        ph = Image.new('RGB', (420, 520), (60, 62, 66)); pd = ImageDraw.Draw(ph)
        pd.ellipse((130, 100, 290, 270), fill=(25, 25, 28)); pd.rounded_rectangle((70, 260, 350, 560), 90, fill=(25, 25, 28))
        pd.text((210, 185), '?', font=F(SERIF, 80), fill=(80, 80, 85), anchor='mm')
        dd.text((440, y0 + 680), 'No photograph', font=F(MONO, 26), fill=(110, 100, 85), anchor='mm')
    lay.paste(ph, (230, int(y0 + 120)))
    nome = str(s.get('nome') or ''); fn = G4.adatta(SERIF, nome, 120, 1000)
    dd.text((720, y0 + 90), scrivi_a_macchina(t, .35, nome, 26), font=fn, fill=INCH)
    righe = (s.get('righe') or [])[:5]; passo = max(.45, (d * .6) / max(1, len(righe)))
    for k, (a, b) in enumerate(righe):
        st = .9 + k * passo; y = y0 + 280 + k * 92
        if t < st:
            break
        G4.scrivi(dd, (720, y + 12), str(a).upper()[:14], F(MONO, 28), (110, 100, 85), spaz=3)
        dd.text((990, y), scrivi_a_macchina(t, st + .1, str(b)[:30], 40), font=G4.adatta(MONO, str(b)[:30], 46, 700), fill=INCH)
        if k == len(righe) - 1:   # ultima riga: sottolineata
            sottolinea(dd, 990, 990 + G4.adatta(MONO, str(b)[:30], 46, 700).getlength(str(b)[:30]), y + 64, t, st + .7)
    fr.alpha_composite(lay)
    if s.get('timbro') and t > d * .75:
        k = cl((t - d * .75) / .18); G4.ombra_incolla(fr, G4.timbro(str(s['timbro']).upper()[:18]), 1480, y0 + 690, sc=1.6 - .6 * ease(k), alpha=k)
    return fr


def s_dato(s, img, t, d, i):
    fr = kb(s['_bg'], t, d, i, 1.08).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    num = str(s.get('numero') or ''); m = re.match(r'^([^\d]*)([\d.,]+)(.*)$', num); vis = num
    if m:
        v = float(m.group(2).replace(',', '')); k = ease((t - .1) / max(.8, min(1.6, d * .4)))
        dec = len(m.group(2).split('.')[1]) if '.' in m.group(2) else 0
        vis = m.group(1) + f'{v * k:,.{dec}f}' + m.group(3)
    f = G4.adatta(SERIF, num, 320, 1500)
    pulse = 1 + .015 * math.sin(t * 4)
    dd.text((W / 2, 440), vis, font=F(SERIF, int(f.size * pulse)), fill=CREMA, anchor='mm')
    wn = f.getlength(num)
    sottolinea(dd, W / 2 - wn / 2, W / 2 + wn / 2, 610, t, max(1.0, min(1.8, d * .4) + .1), ROSSO, 12)
    did = str(s.get('didascalia') or '').upper()
    fd = G4.adatta(MONO, did, 40, 1300 / 1.4); tw = sum(fd.getlength(ch) + 6 for ch in did)
    G4.scrivi(dd, (W / 2 - tw / 2, 670), scrivi_a_macchina(t, 1.3, did, 40), fd, (230, 225, 215), spaz=6)
    if s.get('fonte') and t > 1.3 + len(did) / 40:
        G4.scrivi(dd, (W / 2, 750), ('SOURCE: ' + str(s['fonte'])).upper()[:50], F(MONO, 24), (170, 165, 155), spaz=5, anc='ma')
    fr.alpha_composite(lay); return fr


def s_calendario(s, img, t, d, i):
    fr = kb(s['_bg'], t, d, i, 1.08).convert('RGBA')
    e = ease(t / .45)
    pag = Image.new('RGBA', (440, 480), CREMA + (255,)); pd = ImageDraw.Draw(pag)
    pd.rectangle((0, 0, 440, 84), fill=ROSSO); G4.scrivi(pd, (220, 20), str(s.get('mese') or '').upper()[:3], F(MONO, 40), (245, 240, 230), spaz=10, anc='ma')
    pd.text((220, 290), str(s.get('giorno') or ''), font=F(SERIF, 270), fill=INCH, anchor='mm')
    G4.ombra_incolla(fr, pag, 400, 540 - 300 * (1 - e), ang=-3 * (1 - e))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    tit = str(s.get('titolo') or ''); ft = G4.adatta(SERIF, tit, 118, 1100)
    dd.text((720, 360), scrivi_a_macchina(t, .5, tit, 24), font=ft, fill=CREMA)
    a, b = chiave_x(ft, tit, s.get('chiave')); sottolinea(dd, 720 + a, 720 + b, 510, t, .55 + len(tit) / 24)
    sot = str(s.get('sotto') or '').upper(); fs = G4.adatta(MONO, sot, 34, 1080 / 1.45)
    G4.scrivi(dd, (725, 550), scrivi_a_macchina(t, 1.0 + len(tit) / 24, sot, 40), fs, (220, 215, 205), spaz=5)
    fr.alpha_composite(lay)
    if s.get('timbro'):
        st = min(d - .6, 1.4 + len(tit) / 24 + len(sot) / 40)
        if t > st:
            k = cl((t - st) / .18); G4.ombra_incolla(fr, G4.timbro(str(s['timbro']).upper()[:20]), 1500, 190, sc=1.6 - .6 * ease(k), alpha=k)
    return fr


def s_classifica(s, img, t, d, i):
    fr = kb(s['_bg'], t, d, i, 1.06).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    e = ease(t / .4); y0 = 170 + (1 - e) * 100
    ombra(lay, (190, y0, 1730, y0 + 740)); lay.paste(G4.carta(1540, 740, 2), (190, int(y0)))
    G4.scrivi(dd, (260, y0 + 60), scrivi_a_macchina(t, .3, str(s.get('titolo') or '').upper()[:48], 40), F(MONO, 38), (60, 56, 50), spaz=4)
    dd.line((260, y0 + 125, 1660, y0 + 125), fill=(120, 110, 95), width=2)
    B = (s.get('barre') or [])[:4]; mx = max([float(b[1]) for b in B] + [1]); passo = max(.5, d * .45 / max(1, len(B)))
    for k, b in enumerate(B):
        y = y0 + 170 + k * (430 // max(1, len(B))); st = .7 + k * passo
        G4.scrivi(dd, (260, y), str(b[0]).upper()[:40], F(MONO, 30), (60, 56, 50), spaz=3)
        lv = F(SERIF, 74).getlength(str(b[2])); g = ease((t - st) / .6); w = int(min(1000, 1360 - lv - 60) * float(b[1]) / mx * g)
        dd.rectangle((260, y + 50, 260 + max(w, 3), y + 125), fill=ROSSO if k == 0 else (55, 60, 72))
        if g > .6:
            dd.text((290 + w, y + 44), str(b[2]), font=F(SERIF, 74), fill=INCH)
        if k == 0:
            cerchio(dd, (240 + w, y + 20, 520 + w + 60, y + 160), t, st + .8)
    if s.get('fonte'):
        G4.scrivi(dd, (260, y0 + 680), ('SOURCES: ' + str(s['fonte'])).upper()[:60], F(MONO, 24), (110, 100, 85), spaz=3)
    fr.alpha_composite(lay)
    if s.get('timbro') and t > d * .7:
        k = cl((t - d * .7) / .18); G4.ombra_incolla(fr, G4.timbro(str(s['timbro']).upper()[:22]), 1450, y0 + 600, sc=1.6 - .6 * ease(k), alpha=k)
    return fr


DISEGNA = {'foto': s_foto, 'dossier': s_dossier, 'dato': s_dato, 'calendario': s_calendario, 'classifica': s_classifica}


def rendi(i, s, dur, out):
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for k in range(int(dur * FPS) + 1):
        enc.stdin.write(DISEGNA[s['tipo']](s, None, k / FPS, dur, i).convert('RGB').tobytes())
    enc.stdin.close(); enc.wait()


def scena_clip(i, s, dur, out):
    """Clip a tutto schermo; il cartello entra parola per parola (ogni parola un piccolo colpo)."""
    f, d0 = s['_clip']; ss = max(0.0, random.uniform(0, max(0.0, d0 - dur - .5)))
    base = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,eq=saturation=0.85:contrast=1.06'
    parole = str(s.get('cartello') or '').upper().split()
    if not parole:
        vf = f"[0:v]{base},format=yuv420p[o]"; inp = []
    else:
        inp, vf, last = [], f"[0:v]{base}[b0]", 'b0'
        for k in range(len(parole)):
            lab = os.path.join(LAV, f'cart_{i}_{k}.png'); G4.cartello_png(' '.join(parole[:k + 1]), lab)
            inp += ['-loop', '1', '-t', f'{dur:.3f}', '-i', lab]
            t0 = .4 + k * .35; t1 = .4 + (k + 1) * .35 if k < len(parole) - 1 else dur + 1
            vf += f";[{k + 1}:v]format=rgba[l{k}];[{last}][l{k}]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})'[b{k + 1}]"; last = f'b{k + 1}'
        vf += f";[{last}]format=yuv420p[o]"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{ss:.2f}', '-stream_loop', '-1', '-i', f, *inp, '-filter_complex', vf, '-map', '[o]',
                    '-t', f'{dur:.3f}', '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', out], check=True)


def main():
    c = copione(); shots = c['shots']
    for i, s in enumerate(shots):
        tp = s.get('tipo')
        if tp == 'clip':
            s['_clip'] = clip_seria(s.get('sfondo') or 'stock exchange', s['voce'], i)
            if s['_clip'] is None:   # nessuna clip seria: la scena diventa una foto controllata con titolo
                s.update({'tipo': 'foto', 'titolo': s.get('cartello') or '', 'etichetta': ''}); s['_bg'] = prepara(foto(s.get('sfondo') or 'stock exchange', s['voce'], i))
        elif tp in DISEGNA:
            s['_bg'] = prepara(foto(s.get('sfondo') or 'wall street', s['voce'], i), sfoca=(tp != 'foto'))
            if tp == 'dossier':
                s['_ph'] = None
    boom, whoosh = G3.suoni()
    parti, audio = [], []
    for i, s in enumerate(shots):
        v = G3.voce(i, s['voce']); d = G3.durata(v) + .12
        out = os.path.join(LAV, f'scena_{i:02d}.mp4'); tp = s.get('tipo')
        if tp == 'clip':
            scena_clip(i, s, d, out)
        elif tp == 'borsa':
            G3.borsa(i, s, d, out)
        else:
            if tp not in DISEGNA:
                s['tipo'] = tp = 'foto'; s['_bg'] = prepara(foto(s.get('sfondo') or 'wall street', s['voce'], i))
            rendi(i, s, d, out)
        parti.append(out)
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        fx = boom if tp in ('dato', 'borsa') or (tp in ('calendario', 'classifica', 'dossier') and s.get('timbro')) else (whoosh if tp in ('foto', 'clip') else None)
        rit = int(d * {'calendario': .5, 'classifica': .7, 'dossier': .75}.get(tp, 0) * 1000) if tp in ('calendario', 'classifica', 'dossier') else 0
        if fx:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-i', fx, '-filter_complex',
                            f'[0:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{d:.3f}[v];[1:a]adelay={rit}|{rit},volume=0.4[f];[v][f]amix=inputs=2:duration=first:normalize=0',
                            '-ar', '44100', '-ac', '2', a], check=True)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True)
        audio.append(a); log('scena', i + 1, tp, f'{d:.1f} s')
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-c', 'copy', os.path.join(LAV, 'video.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), os.path.join(LAV, 'voce.wav')], check=True)
    tot = G3.durata(os.path.join(LAV, 'voce.wav'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(LAV, 'video.mp4'), '-i', os.path.join(LAV, 'voce.wav'), '-stream_loop', '-1', '-i', 'libreria_musica/mistero_003.mp3',
                    '-filter_complex', f'[2:a]volume=0.10,afade=t=out:st={max(0, tot - 2):.2f}:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', f'{tot:.2f}', os.path.join(OUT, 'video_prova.mp4')], check=True)
    cp = c.get('copertina') or {}
    bg = prepara(foto(cp.get('sfondo') or 'wall street', c.get('titolo', ''), 99))
    fr = kb(bg, 1, 2, 0).convert('RGBA'); lab = os.path.join(LAV, 'cart_cop.png'); G4.cartello_png(str(cp.get('scritta') or 'GONE')[:24], lab)
    fr.alpha_composite(Image.open(lab)); fr.convert('RGB').resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, 'copertina.jpg'), quality=92)
    tv = G3.durata(os.path.join(OUT, 'video_prova.mp4'))
    for k in range(1, 9):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{tv * (k - .5) / 8:.2f}', '-i', os.path.join(OUT, 'video_prova.mp4'), '-frames:v', '1', '-vf', 'scale=960:-1',
                        os.path.join(OUT, f'fotogramma_{k}.jpg')], check=True)
    costo = (f"durata {tv:.0f} s | scene {len(shots)} | Claude copione+controllo fatti {COSTO['claude']:.3f} $ | controllo foto {COSTO['controlli']:.3f} $ | "
             f"immagini AI 0 | voce {COSTO['voce_caratteri']} crediti")
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
