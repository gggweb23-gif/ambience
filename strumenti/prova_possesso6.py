#!/usr/bin/env python3
"""PROVA "POSSESSO" v6 (9 nov, correzioni della v5): stile SEMPRE illustrazione dipinta (mai foto); il SUV compare SOLO nelle immagini col protagonista
(fatte partendo dalla prima, quindi sempre lo stesso SUV), sempre di lato o di tre quarti da dietro (niente calandra = niente logo);
le immagini senza persone mostrano solo oggetti e luoghi, MAI un'auto (cosi' niente auto in casa e niente SUV diversi).
Base: PROVA "POSSESSO" v5 (9 nov, Giorgio: "un SUV medio da circa 45.000 euro; un'immagine nuova a ogni cambio di grafica ma col modello piu' base;
mai l'auto davanti alla cucina; mai la testa dietro la grafica; massima resa, minimo costo").
Immagini FLUX.2 Klein 4B a 1280x720 (circa 0,009 $ l'una senza persone, circa 0,017 $ con il protagonista tenuto uguale dalla prima immagine).
Base: PROVA "POSSESSO" v3 (9 nov, Giorgio: "sempre macchine, case ecc. della classe media; ogni volta che cambia la grafica deve cambiare anche l'immagine;
l'utente deve capire ma mai annoiarsi"): ogni passo della grafica ha il suo sfondo (dissolvenza), oggetti da classe media, sottolineature ed evidenziatori continui.
Base: PROVA "POSSESSO" LIVELLO 2 (9 nov, Giorgio: "crea video da 1 minuto con la nuova idea... alzare il livello").
Sfondo illustrato AI (stesso protagonista e stessa cosa in tutte le scene: la prima immagine fa da riferimento alle altre)
+ grafica che spiega disegnata in codice e animata sopra (cartellino, scontrini che si sommano, barre del valore, calcolo del costo vero, consigli).
I numeri a schermo li calcola il codice (mai incoerenti): totale = somma delle voci, costo vero = totale - rivendita.
Uscita: prove_video/Prova_Possesso2/ (video_prova.mp4, copertina.jpg, fotogrammi, copione.json, costo.txt). Non carica niente."""
import io, json, math, os, re, subprocess, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

E = os.environ.get
OUT = 'prove_video/Prova_Possesso6'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/possesso6'; os.makedirs(LAV, exist_ok=True)
VOCE = E('VOCE') or 'glnsgBC77wt5zOYU0szz'
COSA = E('COSA') or "un SUV medio nuovo da 45.000 euro comprato a rate"
W, H, FPS = 1920, 1080, 30
FONT = 'ctr_test/Anton.ttf'
COSTO = {'claude': 0.0, 'immagini': 0, 'voce': 0}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
STILE = ('DIGITAL PAINTED ILLUSTRATION, NOT a photograph: warm editorial illustration style with soft painted shading, consistent in every image. '
         'Everything is ORDINARY ITALIAN MIDDLE CLASS. The car is a generic mid-size family SUV, always seen from the SIDE or from the REAR three-quarter view '
         '(front grille never visible), no badge, no logo, no brand. '
         'Cars are ALWAYS outdoors, in a showroom, a parking lot, a street, a petrol station or a garage: NEVER inside a house or in front of a kitchen. '
         'modest apartments and kitchens, ordinary neighbourhoods, normal clothes. '
         'Premium editorial illustration for an Italian personal-finance YouTube explainer, semi-realistic 2.5D style with soft shading, warm cinematic light, '
         'Italian setting. Keep the LEFT 50% of the frame calm and uncluttered (soft background only) because graphics go there; main subject on the RIGHT half. '
         'Absolutely no text, no letters, no numbers, no logos, no brand badges, no shop signs, no license plates: every car is a generic unbranded model. ')
INK, Y, R, G, BL, BIANCO, GRIGIO = (30, 34, 53), (255, 201, 60), (232, 57, 70), (43, 182, 115), (90, 140, 235), (255, 255, 255), (95, 100, 120)


def http(url, data=None, headers=None, raw=False, timeout=300):
    body = json.dumps(data).encode() if data is not None else None
    h = {'Content-Type': 'application/json'} if data is not None else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def eur(v):
    return f'{round(v):,}'.replace(',', '.') + ' €'


# ---------------------------------------------------------------- copione
def copione():
    fc = os.path.join(OUT, 'copione.json')
    if os.path.exists(fc) and not E('COSA'):
        c = json.load(open(fc)); log('copione ripreso'); return c
    prompt = f"""Scrivi il copione di un video YouTube italiano di 60 secondi (circa 150 parole parlate in tutto) per il canale "Quanto costa DAVVERO possedere qualcosa".
Cosa: {COSA}. Numeri realistici italiani 2026, arrotondati. Un protagonista con nome italiano.
Struttura FISSA di 6 scene (non cambiarla). Per ogni scena: "voce" (testo parlato, numeri scritti in lettere, frasi brevi e incisive), "sfondi" (lista in INGLESE: UNA immagine diversa per OGNI passo della grafica, nell'ordine in cui la voce ne parla; sempre lo stesso protagonista e la stessa cosa; tutto da classe media italiana) e i dati della grafica.
Ogni elemento di "sfondi" e' {{"persone": true/false, "descr": "..."}}: persone=true solo se nella scena c'e' il protagonista (stesso viso e vestiti), persone=false per oggetti e luoghi SENZA nessuna persona e SENZA nessuna automobile (es. pistola della pompa di benzina da vicino col display dei litri, polizza e chiavi su un tavolo, attrezzi e gomme in officina, bollettino del bollo e penna, parchimetro, salvadanaio, calcolatrice). Il SUV compare SOLO nelle immagini con persone=true, sempre all'aperto o in salone/officina, mai in casa.
Numero di "sfondi" per scena = numero di passi della grafica: cartellino 2, scontrini = una per OGNI voce di spesa (4-6), valore 2 (SUV nuovo lucido, SUV dopo anni), calcolo 3 (conti al tavolo, faccia stupita, portafoglio/calendario), consigli 3 (uno per consiglio), prossimo 1 (un cane). Almeno meta' degli sfondi con persone=false.
Voci di spesa REALISTICHE per un italiano medio (es. carburante per 12.000 km l'anno, assicurazione media italiana): mai cifre troppo basse.
1. "cartellino": gancio forte. dati {{"prezzo": <prezzo della cosa>, "domanda": "MA QUANTO COSTA DAVVERO?"}}
2. "scontrini": tutto quello che paga in N anni. dati {{"anni": 5, "voci": [["Rate + interessi", <numero>], ["Assicurazione", <numero>], ...]}} (le rate con interessi di un acquisto a rate sono SEMPRE piu' del prezzo) (4-6 voci; NON mettere la svalutazione: e' nella scena 3)
3. "valore": quanto vale la cosa anno per anno. dati {{"valori": [<prezzo>, <valore dopo 1 anno>, ...]}} (da oggi all'ultimo anno; l'ultimo e' la rivendita)
4. "calcolo": costo vero = totale pagato meno rivendita; poi al mese e al giorno. dati {{}} (i numeri li calcola il programma: nella voce usa ESATTAMENTE totale = somma delle voci della scena 2, rivendita = ultimo valore della scena 3, costo vero = differenza, al mese = costo vero / mesi, al giorno = costo vero / giorni, tutti arrotondati all'euro intero)
5. "consigli": 3 trucchi concreti per spendere meno. dati {{"voci": ["...", "...", "..."]}} (max 5 parole ciascuno)
6. "prossimo": gancio alla prossima puntata (un'altra cosa da possedere, es. il cane). dati {{"testo": "PROSSIMA PUNTATA: IL CANE"}}
Fai TUTTI i conti prima di scrivere e ricontrollali. Mai correzioni a voce.
Aggiungi "titolo" e "copertina": {{"scritta": "max 3 parole MAIUSCOLE", "sfondo": "in inglese"}} e "protagonista": descrizione fisica in inglese (eta', capelli, vestiti) da ripetere in ogni immagine.
Rispondi SOLO con JSON: {{"titolo": "...", "protagonista": "...", "copertina": {{...}}, "scene": [{{"tipo": "cartellino", "voce": "...", "sfondi": [{{"persone": true, "descr": "..."}}], "dati": {{...}}}}, ...]}}"""
    errore = ''
    for tentativo in range(3):
      for k in range(3):
        j = http('https://api.anthropic.com/v1/messages', {'model': 'claude-sonnet-5-5', 'max_tokens': 16000, 'thinking': {'type': 'between_tools'},
                                                            'output_config': {'effort': 'medium'}, 'messages': [{'role': 'user', 'content': prompt + errore}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        u = j.get('usage') or {}
        COSTO['claude'] += u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6
        t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
        if '{' in t:
            break
      m = re.search(r'\{.*\}', t, re.S).group(0)
      try:
          c = json.loads(m)
      except Exception:
          from json_repair import repair_json
          c = json.loads(repair_json(m))
      # controllo dei numeri PRIMA di spendere in immagini e voce
      try:
          S_ = {x['tipo']: x.get('dati') or {} for x in c['scene']}
          prezzo = float(S_['cartellino'].get('prezzo') or 0); val = [float(v) for v in S_['valore']['valori']]
          voci = [(str(a).lower(), float(b)) for a, b in S_['scontrini']['voci']]; tot = sum(b for _, b in voci)
          rate = sum(b for a, b in voci if 'rat' in a or 'finanz' in a)
          prob = []
          if abs(prezzo - val[0]) > 1:
              prob.append(f'il prezzo del cartellino ({prezzo:.0f}) deve essere uguale al primo valore ({val[0]:.0f})')
          if rate and rate < prezzo:
              prob.append(f'rate + interessi ({rate:.0f}) non possono essere meno del prezzo ({prezzo:.0f})')
          if tot - val[-1] < prezzo * .3:
              prob.append(f'costo vero ({tot - val[-1]:.0f}) irrealistico rispetto al prezzo ({prezzo:.0f})')
      except Exception as e:
          prob = [f'struttura dati non valida: {e}']
      if not prob:
          break
      log('copione scartato:', prob); errore = '\n\nATTENZIONE, il tentativo precedente era sbagliato: ' + '; '.join(prob) + '. Rifai tutti i conti.'
    json.dump(c, open(fc, 'w'), ensure_ascii=False, indent=1)
    log('copione:', c['titolo'], sum(len(s['voce'].split()) for s in c['scene']), 'parole')
    return c


# ---------------------------------------------------------------- immagini (stesso protagonista: la prima fa da riferimento)
def fal(endpoint, dati):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/' + endpoint, dati, hd)
    for _ in range(150):
        time.sleep(3)
        if http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    return http(inv['response_url'], headers=hd)['images'][0]['url']


STILE_OGGETTI = ('DIGITAL PAINTED ILLUSTRATION, NOT a photograph: warm editorial illustration style with soft painted shading. Ordinary Italian middle-class setting. '
                 'A close, simple still-life of the objects described: NO people, NO cars, NO vehicles anywhere in the image. '
                 'Keep the LEFT 50% of the frame calm and uncluttered; main objects on the RIGHT half. No text, no letters, no numbers, no logos. ')
KLEIN_T2I, KLEIN_EDIT = 'fal-ai/flux-2/klein/4b', 'fal-ai/flux-2/klein/4b/edit'
PREZZO = {'t2i': 0.009, 'edit': 0.017}


def immagini(c):
    """Prima immagine: protagonista + SUV (riferimento). Poi: con persone -> edit col riferimento (stessa faccia); senza persone -> testo-immagine (costa la meta')."""
    prot = c.get('protagonista') or ''
    voci = [x for s in c['scene'] for x in (s.get('sfondi') or [])]
    out, rif = [], None
    for i, x in enumerate(voci):
        d = x.get('descr') if isinstance(x, dict) else str(x); con = bool(x.get('persone')) if isinstance(x, dict) else True
        f = os.path.join(LAV, f'sfondo_{i}.jpg')
        p = (STILE + f'Main character (always the same person): {prot}. Scene: {d}') if con else (STILE_OGGETTI + f'Scene (objects and place only): {d}')
        for k in range(3):
            try:
                if rif is None:
                    url = fal(KLEIN_T2I, {'prompt': STILE + f'Main character: {prot}. Scene: the main character standing next to his new mid-size family SUV seen from the side, in a bright car showroom.',
                                          'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'}); rif = url; COSTO['t2i'] = COSTO.get('t2i', 0) + 1
                if con:
                    url = fal(KLEIN_EDIT, {'prompt': 'Same illustration style, SAME man (same face, hair, clothes) and SAME SUV as in the reference image. ' + p,
                                           'image_urls': [rif], 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'}); COSTO['edit'] = COSTO.get('edit', 0) + 1
                else:
                    url = fal(KLEIN_T2I, {'prompt': p, 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'}); COSTO['t2i'] = COSTO.get('t2i', 0) + 1
                Image.open(io.BytesIO(http(url, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).save(f, quality=94)
                COSTO['immagini'] += 1; break
            except Exception as e:
                log('immagine non riuscita, riprovo:', str(e)[:200]); time.sleep(4)
        out.append(f)
    return out


def immagini_vecchie(c):
    prot = c.get('protagonista') or ''
    out, rif = [], None
    descr = [x for s in c['scene'] for x in (s.get('sfondi') or [s.get('sfondo') or ''])] + [c['copertina'].get('sfondo') or (c['scene'][0].get('sfondi') or [''])[0]]
    for i, d in enumerate(descr):
        f = os.path.join(LAV, f'sfondo_{i}.jpg')
        p = STILE + f'Main character (always the same person): {prot}. Scene: {d}'
        for k in range(3):
            try:
                if rif is None:
                    url = fal('fal-ai/nano-banana-2', {'prompt': p, 'aspect_ratio': '16:9', 'output_format': 'jpeg', 'num_images': 1}); rif = url
                else:
                    url = fal('fal-ai/nano-banana-2/edit', {'prompt': 'Same illustration style, SAME man (same face, hair and clothes) and, if present, the SAME object as in the reference image. New scene: ' + p,
                                                            'image_urls': [rif], 'aspect_ratio': '16:9', 'output_format': 'jpeg', 'num_images': 1})
                Image.open(io.BytesIO(http(url, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).save(f, quality=94)
                COSTO['immagini'] += 1; break
            except Exception as e:
                log('immagine non riuscita, riprovo:', str(e)[:150]); time.sleep(4)
        out.append(f)
    return out


# ---------------------------------------------------------------- grafica animata
_F = {}
F = lambda s: _F.setdefault(s, ImageFont.truetype(FONT, s))
cl = lambda x: max(0.0, min(1.0, x))
ease = lambda x: 1 - (1 - cl(x)) ** 3
def pop(x):
    x = cl(x); return 1 + 2.7 * (x - 1) ** 3 + 1.7 * (x - 1) ** 2 if x > 0 else 0


def pannello(im, box, fill, r=28, alpha=1.0):
    if alpha <= 0:
        return
    x0, y0, x1, y1 = box
    sh = Image.new('RGBA', (int(x1 - x0) + 80, int(y1 - y0) + 80), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((40, 40, 40 + x1 - x0, 40 + y1 - y0), r, fill=(0, 0, 0, int(110 * alpha)))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)), (int(x0 - 30), int(y0 - 26)))
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(box, r, fill=fill[:3] + (int((fill[3] if len(fill) > 3 else 255) * alpha),))
    im.alpha_composite(lay)


def scritta(im, xy, t, size, col, anc='la', alpha=1.0, maxw=None):
    if maxw:
        while F(size).getlength(t) > maxw and size > 24:
            size -= 2
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(xy, t, font=F(size), fill=col + (int(255 * alpha),), anchor=anc)
    im.alpha_composite(lay)


def grafica(im, sc, t, d, dati):
    tipo = sc['tipo']; dd = sc.get('dati') or {}
    sl = lambda a: int(-700 * (1 - ease((t - a) / .45)))    # entrata da sinistra
    if tipo == 'cartellino':
        x = sl(.2)
        pannello(im, (110 + x, 250, 780 + x, 580), (255, 255, 255, 245))
        scritta(im, (150 + x, 285), 'PREZZO SUL CARTELLINO', 46, GRIGIO)
        scritta(im, (150 + x, 350), eur(dati['prezzo'] * ease((t - .4) / 1.0)), 150, INK, maxw=600)
        q = pop((t - d * .45) / .4)
        if q:
            w = 900 * q
            pannello(im, (110, 640, 110 + w, 800), R + (255,))
            if q > .9:
                scritta(im, (150, 672), str(dd.get('domanda') or 'MA QUANTO COSTA DAVVERO?').upper(), 76, BIANCO, maxw=820)
    elif tipo == 'scontrini':
        V = dati['voci']; n = len(V); x = sl(0)
        pannello(im, (100 + x, 110, 900 + x, 250 + 92 * n), (255, 250, 236, 248))
        scritta(im, (140 + x, 140), f"IN {dati['anni']} ANNI PAGHI", 60, INK)
        passo = d * .75 / n; tot = 0
        for i, (nome, v) in enumerate(V):
            a = cl((t - .4 - i * passo) / .3)
            if a <= 0:
                continue
            y = 240 + i * 92 + int(20 * (1 - a))
            ev = cl(1 - (t - .4 - i * passo - .3) / .9)   # evidenziatore giallo sulla riga appena arrivata, poi sfuma
            if ev > 0:
                lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).rectangle((125 + x, y - 6, 125 + x + 750 * ease(min(1, (t - .4 - i * passo) / .25)), y + 66), fill=(255, 214, 70, int(120 * ev))); im.alpha_composite(lay)
            scritta(im, (140 + x, y), nome, 52, (60, 64, 85), alpha=a, maxw=480)
            scritta(im, (860 + x, y), eur(v), 56, R, 'ra', alpha=a)
            tot += v * a
        yb = 290 + 92 * n
        pannello(im, (100, yb, 900, yb + 160), INK + (255,))
        scritta(im, (140, yb + 48), 'TOTALE', 60, Y)
        scritta(im, (860, yb + 20), eur(tot), 100, Y, 'ra')
    elif tipo == 'valore':
        V = dati['valori']; n = len(V); x = sl(0)
        pannello(im, (90 + x, 110, 1000 + x, 230 + 70 * n), (255, 255, 255, 245))
        scritta(im, (130 + x, 140), 'QUANTO VALE ANNO DOPO ANNO', 56, INK, maxw=820)
        passo = d * .7 / n
        for i, v in enumerate(V):
            a = ease((t - .4 - i * passo) / .5)
            if a <= 0:
                continue
            y = 240 + i * 70; w = int(500 * v / V[0] * a)
            scritta(im, (130 + x, y), 'oggi' if i == 0 else f'anno {i}', 42, GRIGIO)
            ImageDraw.Draw(im).rounded_rectangle((300 + x, y + 6, 300 + x + max(w, 12), y + 52), 12, fill=G if i == 0 else (R if i == n - 1 else BL))
            scritta(im, (316 + x + w, y + 4), eur(v), 42, INK, alpha=a)
        if t > d * .8:
            persi = V[0] - V[-1]
            pannello(im, (90, 290 + 70 * n, 1000, 420 + 70 * n), R + (255,), alpha=cl((t - d * .8) / .3))
            scritta(im, (130, 318 + 70 * n), f'VALORE PERSO: {eur(persi)}', 70, BIANCO, alpha=cl((t - d * .8) / .3), maxw=820)
            u = ease((t - d * .8 - .3) / .35)
            if u > 0:
                ImageDraw.Draw(im).line((130, 400 + 70 * n, 130 + 820 * u, 400 + 70 * n), fill=Y, width=7)
    elif tipo == 'calcolo':
        x = sl(0)
        pannello(im, (90 + x, 130, 1010 + x, 520), (255, 255, 255, 245))
        righe = [('Pagato in totale', eur(dati['totale']), INK), ('Rivendita', '- ' + eur(dati['rivendita']), G)]
        for i, (a_, b_, c_) in enumerate(righe):
            a = cl((t - .3 - i * d * .15) / .3)
            scritta(im, (130 + x, 170 + i * 110), a_, 58, GRIGIO, alpha=a); scritta(im, (970 + x, 160 + i * 110), b_, 74, c_, 'ra', alpha=a)
        ImageDraw.Draw(im).line((130 + x, 390, 970 + x, 390), fill=INK, width=6)
        k = ease((t - d * .35) / 1.0)
        scritta(im, (130 + x, 405), 'COSTO VERO', 58, R, alpha=cl(k * 3))
        scritta(im, (970 + x, 395), eur(dati['costo_vero'] * k), 90, R, 'ra', alpha=cl(k * 3))
        u = ease((t - d * .35 - 1.0) / .4)
        if u > 0:
            ImageDraw.Draw(im).line((130 + x, 512, 130 + x + 840 * u, 512), fill=R, width=6)
        q = pop((t - d * .6) / .4)
        if q:
            pannello(im, (90, 580, 90 + 920 * q, 760), INK + (255,))
            if q > .9:
                scritta(im, (130, 610), f"{eur(dati['mese'])} AL MESE", 96, Y, maxw=840)
            if t > d * .78:
                pannello(im, (90, 800, 700, 940), Y + (255,), alpha=cl((t - d * .78) / .25))
                scritta(im, (130, 822), f"{eur(dati['giorno'])} AL GIORNO", 80, INK, alpha=cl((t - d * .78) / .25), maxw=540)
    elif tipo == 'consigli':
        V = (dd.get('voci') or [])[:3]; x = sl(0)
        pannello(im, (90 + x, 150, 1000 + x, 330 + 120 * len(V)), (255, 255, 255, 245))
        scritta(im, (130 + x, 180), 'COME SPENDERE MENO', 64, INK)
        for i, v in enumerate(V):
            a = pop((t - .5 - i * d * .22) / .35)
            if not a:
                continue
            y = 290 + i * 120
            ImageDraw.Draw(im).ellipse((130 + x, y + 8, 190 + x, y + 68), fill=G)
            ImageDraw.Draw(im).line((145 + x, y + 38, 157 + x, y + 52, 177 + x, y + 24), fill=BIANCO, width=8)
            scritta(im, (215 + x, y + 6), str(v), 58, INK, alpha=cl(a), maxw=740)
    elif tipo == 'prossimo':
        q = pop((t - .3) / .45)
        if q:
            pannello(im, (110, 400, 110 + 1000 * q, 580), R + (255,))
            if q > .9:
                scritta(im, (150, 432), str(dd.get('testo') or 'PROSSIMA PUNTATA').upper(), 90, BIANCO, maxw=920)


def sfondo_passi(bgs, t, d, i):
    """Uno sfondo per ogni passo della grafica: cambia a intervalli uguali con dissolvenza di 0,3 s; ognuno con la sua spinta lenta."""
    n = len(bgs); p = d / n; k = min(n - 1, int(t / p)); tl = t - k * p
    fr = sfondo_frame(bgs[k], tl, p, i + k)
    if k > 0 and tl < .3:
        fr = Image.blend(sfondo_frame(bgs[k - 1], p, p, i + k - 1), fr, tl / .3)
    return fr


def sfondo_frame(bg, t, d, i):
    """Movimento lento dello sfondo (spinta 1.00 -> 1.05, verso destra o sinistra a scene alterne)."""
    z = 1 + .05 * (t / max(d, .1)); w, h = int(W / z), int(H / z)
    x0 = int((W - w) * (.5 + (.25 if i % 2 else -.25) * t / max(d, .1))); y0 = (H - h) // 2
    return bg.crop((x0, y0, x0 + w, y0 + h)).resize((W, H), Image.BILINEAR).convert('RGBA')


def durata(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())


def main():
    c = copione(); S = c['scene']
    # numeri sempre coerenti: li calcola il programma
    sc2 = next(s for s in S if s['tipo'] == 'scontrini')['dati']; sc3 = next(s for s in S if s['tipo'] == 'valore')['dati']
    voci = [(str(a), float(b)) for a, b in sc2['voci']]; anni = int(sc2.get('anni') or 5); valori = [float(v) for v in sc3['valori']]
    tot = sum(v for _, v in voci); cv = tot - valori[-1]
    dati = {'prezzo': float(next(s for s in S if s['tipo'] == 'cartellino')['dati'].get('prezzo') or valori[0]), 'voci': voci, 'anni': anni, 'valori': valori,
            'totale': tot, 'rivendita': valori[-1], 'costo_vero': cv, 'mese': cv / (anni * 12), 'giorno': cv / (anni * 365)}
    log('numeri:', {k: v for k, v in dati.items() if k != 'voci'})
    imgs = immagini(c)
    tutte = [Image.open(f) for f in imgs]; bgs, j = [], 0
    for s in S:
        n = max(1, len(s.get('sfondi') or [1])); bgs.append(tutte[j:j + n] or [tutte[-1]]); j += n
    bgs.append([tutte[0]])
    voci_f, durs = [], []
    for i, s in enumerate(S):
        f = os.path.join(LAV, f'voce_{i}.mp3')
        open(f, 'wb').write(http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
                                 {'text': s['voce'], 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': .45, 'similarity_boost': .8, 'style': .2}},
                                 {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, raw=True))
        COSTO['voce'] += len(s['voce']); voci_f.append(f); durs.append(durata(f) + .35)
    # audio: voci in fila + musica bassa
    parti = []
    for i, f in enumerate(voci_f):
        a = os.path.join(LAV, f'a_{i}.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f, '-af', f'adelay=150|150,apad,atrim=0:{durs[i]:.3f}', '-ar', '44100', '-ac', '2', a], check=True); parti.append(a)
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), os.path.join(LAV, 'voce.wav')], check=True)
    # video: fotogrammi disegnati e passati a ffmpeg (dissolvenza breve tra le scene)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', os.path.join(LAV, 'video.mp4')], stdin=subprocess.PIPE)
    prec = None
    for i, s in enumerate(S):
        n = int(round(durs[i] * FPS)); ultimo = None
        for k in range(n):
            t = k / FPS
            fr = sfondo_passi(bgs[i], t, durs[i], i)
            grafica(fr, s, t, durs[i], dati)
            fr = fr.convert('RGB')
            if prec is not None and k < 9:
                fr = Image.blend(prec, fr, (k + 1) / 10)
            enc.stdin.write(fr.tobytes()); ultimo = fr
        prec = ultimo
        log('scena', i + 1, s['tipo'], f'{durs[i]:.1f} s')
    enc.stdin.close(); enc.wait()
    tot_s = durata(os.path.join(LAV, 'voce.wav'))
    mus = 'libreria_musica/epico_001.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(LAV, 'video.mp4'), '-i', os.path.join(LAV, 'voce.wav'), '-stream_loop', '-1', '-i', mus,
                    '-filter_complex', f'[2:a]volume=0.10,afade=t=out:st={max(0, tot_s - 2):.2f}:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', os.path.join(OUT, 'video_prova.mp4')], check=True)
    # copertina: sfondo dedicato + cartellino e scritta (stile del canale)
    cop = tutte[0].convert('RGBA')
    pannello(cop, (90, 300, 820, 560), (255, 255, 255, 245)); scritta(cop, (130, 330), eur(dati['prezzo']), 170, INK, maxw=650)
    pannello(cop, (90, 620, 1000, 820), R + (255,)); scritta(cop, (130, 650), str(c['copertina'].get('scritta') or 'COSTO VERO?').upper(), 110, BIANCO, maxw=840)
    cop.convert('RGB').resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, 'copertina.jpg'), quality=92)
    tv = durata(os.path.join(OUT, 'video_prova.mp4'))
    for k in range(1, 9):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{tv * (k - .5) / 8:.2f}', '-i', os.path.join(OUT, 'video_prova.mp4'), '-frames:v', '1', '-vf', 'scale=960:-1',
                        os.path.join(OUT, f'fotogramma_{k}.jpg')], check=True)
    costo = f"durata {tv:.0f} s | Claude {COSTO['claude']:.3f} $ | immagini Klein {COSTO['immagini']} (senza persone {COSTO.get('t2i', 0)}, con protagonista {COSTO.get('edit', 0)}: circa {COSTO.get('t2i', 0) * PREZZO['t2i'] + COSTO.get('edit', 0) * PREZZO['edit']:.2f} $) | voce {COSTO['voce']} crediti"
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
