#!/usr/bin/env python3
"""MOTORE "GLOAM" (9 nov 2026, primo canale: Billion Ruin). Disastri finanziari raccontati come un'indagine, stile editoriale/dossier
approvato con le prove Gloam v4-v6, + oggetti 3D lucidi (metafore con etichette) come l'originale Gloam. Voce Max. 9-10 minuti.
1) Claude scrive la SCALETTA (capitoli + fatti con numeri e date) dal titolo della riga del file di produzione; un secondo passaggio
   controlla i fatti. Poi scrive le scene capitolo per capitolo usando SOLO i fatti controllati (3-5 s a scena).
2) Immagini: foto e clip Pexels controllate da Claude Haiku come photo editor di un documentario finanziario serio (mai foto stock "stupide"),
   oggetti 3D con FLUX.2 Klein (circa 0,01 $ l'uno), tutto il resto disegnato in codice: schede, numeri che corrono, calendari, classifiche,
   schermo di borsa. In ogni scena succede sempre qualcosa (scritta a macchina, sottolineatura, timbro, cerchio, etichetta che compare).
3) Voce ElevenLabs scena per scena (con il testo prima e dopo, per un parlato continuo), musica dalla libreria, colpi e soffi in codice.
4) Pulsante Iscriviti con i suoni, copertina stile A (figura ROSSA = colpevole, BLU = vittime, oggetto d'oro con il nome), impaginazione
   che cambia da un video all'altro (MANO LIBERA). Caricamento come gli altri motori (strumenti/motore_yt.py).
SECCO=SI: prova a secco GRATIS (copione finto, niente Claude, niente voce, niente immagini AI): controlla montaggio, ritmo e durata.
Colonne usate: channel_name, language, voice_id, voice_model_id, budget_video, coach_budget_video, playlist, carica, privacy,
youtube_category_id, youtube_default_tags, youtube_description_footer, subscribe_overlay_*, scout_filone."""
import io, json, math, multiprocessing as mp, os, random, re, shutil, subprocess, sys, time, urllib.parse
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = os.getcwd()
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI); sys.path.insert(0, os.path.join(QUI, 'strumenti'))
LAV = os.path.join(ROOT, 'lavoro_gloam'); os.makedirs(LAV, exist_ok=True)
os.environ.setdefault('COSTI_FILE', os.path.join(LAV, 'costi_video.jsonl'))
import costi as CO
import iscrizione as ISC
import motore_yt as YT
import prova_gloam3 as G3
import prova_gloam4 as G4
import prova_gloam6 as G6

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}') or {}
RIGA = P.get('riga') or {}
SECCO = str(E('SECCO') or 'NO').upper() == 'SI'
PROVA = SECCO or str(E('PROVA') or P.get('prova') or 'NO').upper() == 'SI'
CARICA = str(E('CARICA') or 'NO').upper() == 'SI'
VOCE = str(E('VOCE') or P.get('voice_id') or 'Gfpl8Yo74Is0W6cPUWWT').strip()   # Max
VOCE_MOD = str(P.get('voice_model_id') or 'eleven_multilingual_v2')
LINGUA = str(P.get('language') or 'en')[:2]
TITOLO = str(E('TEMA') or RIGA.get('titolo_italiano') or RIGA.get('titolo_originale') or P.get('titolo_originale') or '').strip()
W, H, FPS = G6.W, G6.H, G6.FPS
log = YT.log
MODELLO = 'claude-sonnet-5-5'
HAIKU = 'claude-haiku-4-5-20251001'


def num(x, d=0.0):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return d


BUDGET_USD = (num(P.get('coach_budget_video')) or num(P.get('budget_video')) or 1.0) * 1.08   # budget in euro -> dollari
MIN_PAROLE, MAX_PAROLE = 1350, 1500   # 9-10 minuti con la voce Max (circa 150 parole al minuto)


def durata(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())


# ============================================================ CLAUDE
def claude(prompt, modello=MODELLO, sforzo='medium', immagine=None, max_tokens=16000):
    cont = [{'type': 'text', 'text': prompt}]
    if immagine is not None:
        import base64
        b = io.BytesIO(); immagine.convert('RGB').resize((512, max(1, int(512 * immagine.height / immagine.width)))).save(b, 'JPEG', quality=80)
        cont.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}})
    dati = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': cont}]}
    if 'haiku' not in modello:
        dati.update({'thinking': {'type': 'between_tools'}, 'output_config': {'effort': sforzo}})
    for k in range(4):
        try:
            j = YT.http('https://api.anthropic.com/v1/messages', dati, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=900)
            CO.registra('claude', modello, usage=j.get('usage'))
            t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
            if t.strip():
                return t
        except Exception as e:
            log('Claude non risponde, riprovo:', str(e)[:150])
        time.sleep(10 * (k + 1))
    raise RuntimeError('Claude non risponde')


def leggi_json(t):
    m = re.search(r'[\{\[].*[\}\]]', t, re.S).group(0)
    try:
        return json.loads(m)
    except Exception:
        from json_repair import repair_json
        return json.loads(repair_json(m))


# ============================================================ 1) COPIONE
TIPI = """- "foto": full-screen real photo. "etichetta" = "PLACE · DATE"; "titolo" = max 5 words headline on a paper strip; "sotto" = max 8 words detail line (typed).
- "clip": full-screen stock footage of "sfondo" (must be filmable). "cartello" = 2-4 words CAPITALS, first word is the key word (red).
- "dossier": file card. "scheda" (tab, e.g. "COMPANY FILE"), "nome", "persona": true only if the card is about ONE real person, "righe": 3-5 [label, value]
  (short, factual, every value is a real fact: never placeholders like "see next shot", "TBD", "?"), "timbro" (max 2 words or "").
- "dato": huge number. "numero" (e.g. "$440M", "397M", "45 MIN"), "didascalia" (max 8 words), "fonte".
- "calendario": "mese" (3 letters), "giorno", "titolo" (max 4 words), "sotto" (max 10 words), "timbro" (max 3 words or "").
- "classifica": "titolo", "barre": 2-4 [label, NUMBER > 0, value text] (every bar MUST have a real positive number), "timbro", "fonte".
- "oggetto3d": glossy 3D metaphor like the channel Gloam (golden vault cracking, giant stopwatch, collapsing tower of coins, red faceless mannequin = the culprit,
  blue faceless mannequins = the victims). "oggetto" = English description of ONE simple scene (no text, no logos), "etichette": 1-3 labels (max 2 words each, CAPITALS).
- "borsa": live trading screen: "ticker", "da", "a" (real prices). Max 1 time in the whole video, only with the real timing."""


def scaletta():
    f = os.path.join(LAV, 'scaletta.json')
    if os.path.exists(f):
        log('scaletta ripresa'); return json.load(open(f))
    filone = str(P.get('scout_filone') or 'company and finance disasters told like an investigation')
    p = f"""You plan a 9-10 minute English YouTube documentary for the channel "{P.get('channel_name') or 'Billion Ruin'}" (style of the channel Gloam:
company/finance disasters told like an investigation; calm, precise narrator; editorial visuals). Channel topic: {filone}.
Video title (keep it): "{TITOLO}".
Use ONLY well documented facts (SEC filings, court documents, major newspapers) with correct numbers, dates, units (orders vs shares, million vs billion).
If unsure, leave it out. No invented quotes, no invented people.
Plan 8-10 chapters (total {MIN_PAROLE}-{MAX_PAROLE} spoken words). Chapter 1 = cold open with the biggest number and an open question (loop) answered at the end;
then the story in chronological order with tension, the mechanism explained simply, the consequences, the lesson. Last chapter ends with "Subscribe for the next one."
Reply ONLY with JSON: {{"titolo": "{TITOLO}", "descrizione": "2 short paragraphs for the YouTube description (no hashtags)", "tag": ["10-15 English tags"],
"copertina": {{"oggetto": "name on the gold object, 1-2 words CAPITALS (e.g. the company)", "rosso": "culprit role, max 2 words CAPITALS", "blu": "victims role, max 2 words CAPITALS",
"scena_rosso": "what the ONE red figure does", "scena_blu": "what the blue figures do", "scena_oro": "the gold object and what happens to it"}},
"capitoli": [{{"titolo": "max 5 words", "parole": 150, "fatti": ["each fact with its exact number/date"]}}]}}"""
    s = leggi_json(claude(p, sforzo='medium'))
    rev = claude("You are a strict fact-checker for a finance documentary. Check EVERY number, unit, date, time, name and claim in this plan against well documented "
                 "public sources you know. Fix anything wrong or uncertain (rewrite or remove it), keep everything else IDENTICAL. "
                 "Reply ONLY with {\"correzioni\": [\"short note of each fix\"], \"json\": <the full corrected JSON>}.\n\n" + json.dumps(s, ensure_ascii=False), sforzo='medium')
    try:
        r = leggi_json(rev); s = r.get('json') or s; s['_correzioni'] = r.get('correzioni'); log('controllo fatti:', r.get('correzioni'))
    except Exception as e:
        log('controllo fatti non riuscito:', e)
    json.dump(s, open(f, 'w'), ensure_ascii=False, indent=1)
    return s


def scene_capitolo(s, k):
    f = os.path.join(LAV, f'capitolo_{k:02d}.json')
    if os.path.exists(f):
        return json.load(open(f))
    cap = s['capitoli'][k]; n = len(s['capitoli'])
    prec = ' | '.join(c['titolo'] for c in s['capitoli'][:k]) or '(this is the first chapter)'
    p = f"""Write chapter {k + 1} of {n} of the documentary "{s.get('titolo')}" for the YouTube channel {P.get('channel_name') or 'Billion Ruin'} (style of Gloam).
Chapters already told: {prec}. This chapter: "{cap['titolo']}". Use ONLY these verified facts (do not add other numbers or claims): {json.dumps(cap.get('fatti') or [], ensure_ascii=False)}.
About {int(num(cap.get('parole'), 150))} spoken words, split into shots of 8-13 words (3-5 seconds each). Never repeat a sentence of a previous chapter.
{'Shot 1 = hook with the biggest number; open a question the viewer wants answered.' if k == 0 else 'First shot: tipo "foto" with etichetta "CHAPTER ' + str(k + 1) + '" and titolo = the chapter title.'}
{'Close the open question of the cold open, then the last words are: Subscribe for the next one.' if k == n - 1 else 'End with a line that makes the viewer want the next chapter.'}
Each shot: "voce" (spoken text, numbers in words) + ONE "tipo" with its fields + "sfondo" = 2-4 plain English words for a COHERENT, SERIOUS editorial stock image
(buildings, financial district, stock exchange, trading screens, documents, banknotes, servers, newspapers, maps, city skyline) for a PROFESSIONAL finance audience.
NEVER people with emotional faces or gestures, posed models, handshakes, playful images. "chiave" = 1-2 words of the on-screen text to underline in red.
Types:
{TIPI}
Mix: about half "foto"/"clip"; at most 2 "oggetto3d" in this chapter; never two identical types in a row; every shot has something on screen tied to its words.
Reply ONLY with JSON: {{"shots": [{{"voce": "...", "tipo": "...", "sfondo": "...", "chiave": "...", ...}}]}}"""
    c = leggi_json(claude(p, sforzo='low'))
    shots = c['shots'] if isinstance(c, dict) else c
    for sh in shots:   # barre senza valore: via; se ne restano meno di 2 la scena diventa un numero
        if sh.get('tipo') == 'classifica':
            ok = []
            for b in sh.get('barre') or []:
                try:
                    if float(b[1]) > 0:
                        ok.append(b)
                except Exception:
                    pass
            sh['barre'] = ok
            if len(ok) < 2:
                sh.update({'tipo': 'dato', 'numero': str(ok[0][2]) if ok else '?', 'didascalia': sh.get('titolo') or ''})
        if sh.get('tipo') == 'dossier':   # righe senza un fatto vero (es. "See next shot") via
            sh['righe'] = [r for r in (sh.get('righe') or []) if isinstance(r, (list, tuple)) and len(r) >= 2 and str(r[1]).strip()
                           and not re.search(r'next shot|see next|tbd|n/a|unknown|\?\?', str(r[1]), re.I)]
            if len(sh['righe']) < 2:
                sh.update({'tipo': 'foto', 'titolo': sh.get('nome') or '', 'etichetta': str(sh.get('scheda') or '').upper()})
        sh['capitolo'] = cap['titolo']
    json.dump(shots, open(f, 'w'), ensure_ascii=False, indent=1)
    return shots


def copione():
    if SECCO:
        return copione_finto()
    s = scaletta()
    shots = []
    for k in range(len(s['capitoli'])):
        shots += scene_capitolo(s, k)
    # una sola schermata di borsa in tutto il video
    visti = False
    for sh in shots:
        if sh.get('tipo') == 'borsa':
            if visti:
                sh['tipo'] = 'dato'; sh.setdefault('numero', str(sh.get('a') or '')); sh.setdefault('didascalia', str(sh.get('ticker') or ''))
            visti = True
    parole = sum(len(str(x.get('voce') or '').split()) for x in shots)
    log(f'copione: {len(s["capitoli"])} capitoli, {len(shots)} scene, {parole} parole')
    return {**s, 'shots': shots}


def copione_finto():
    """Prova a secco: un copione inventato in codice (gratis) con tutti i tipi di scena, per controllare montaggio e tempi."""
    base = [
        {'tipo': 'foto', 'sfondo': 'stock exchange building', 'etichetta': 'NEW YORK · AUG 1, 2012', 'titolo': 'The morning it broke', 'sotto': '9:30 AM, MARKET OPEN', 'chiave': 'broke'},
        {'tipo': 'clip', 'sfondo': 'trading screens', 'cartello': 'ORDERS EVERYWHERE'},
        {'tipo': 'dato', 'sfondo': 'wall street', 'numero': '$440M', 'didascalia': 'lost in forty five minutes', 'fonte': 'SEC'},
        {'tipo': 'oggetto3d', 'sfondo': 'dark', 'oggetto': 'a giant glossy gold stopwatch cracking', 'etichette': ['45 MINUTES', 'NO STOP']},
        {'tipo': 'dossier', 'sfondo': 'documents desk', 'scheda': 'COMPANY FILE', 'nome': 'Knight Capital', 'righe': [['FOUNDED', '1995'], ['SHARE', '17% of US volume'], ['STAFF', '1,400']], 'timbro': 'TRADING HALTED'},
        {'tipo': 'calendario', 'sfondo': 'city skyline', 'mese': 'AUG', 'giorno': '1', 'titolo': 'Deployment day', 'sotto': 'one server kept old code', 'timbro': 'GLITCH'},
        {'tipo': 'classifica', 'sfondo': 'financial district', 'titolo': 'Loss vs cash', 'barre': [['LOSS', 440, '$440M'], ['CASH', 365, '$365M']], 'timbro': 'BROKE', 'fonte': 'SEC'},
        {'tipo': 'borsa', 'sfondo': 'trading', 'ticker': 'KCG', 'da': 10.33, 'a': 2.58},
    ]
    shots = []
    for k in range(int(E('SCENE_SECCO') or 16)):
        sh = dict(base[k % len(base)]); sh['voce'] = 'This is a test sentence with about ten words for timing.'; sh['capitolo'] = f'Chapter {k // 6 + 1}'
        shots.append(sh)
    return {'titolo': TITOLO or 'Dry run', 'descrizione': 'Dry run.', 'tag': ['test'], 'capitoli': [{'titolo': 'Test'}],
            'copertina': {'oggetto': 'KNIGHT', 'rosso': 'ALGORITHM', 'blu': 'TRADERS', 'scena_rosso': 'typing', 'scena_blu': 'watching', 'scena_oro': 'stopwatch'}, 'shots': shots}


# ============================================================ 2) IMMAGINI (controllate)
CERCHE, N_PEXELS = {}, [0]
USATE, CLIP_USATE = set(), set()


def pexels_cerca(tipo, q):
    """Ricerca Pexels con memoria (la stessa ricerca non si ripete) e tetto di chiamate (Pexels: 200 all'ora)."""
    k = (tipo, q.lower())
    if k in CERCHE:
        return CERCHE[k]
    if N_PEXELS[0] >= 170:
        return {}
    url = ('https://api.pexels.com/v1/search?' if tipo == 'foto' else 'https://api.pexels.com/videos/search?') + urllib.parse.urlencode(
        {'query': q, 'orientation': 'landscape', 'per_page': 15, **({'size': 'medium'} if tipo != 'foto' else {})})
    for t in range(3):
        try:
            N_PEXELS[0] += 1
            CERCHE[k] = YT.http(url, headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'}, timeout=60)
            return CERCHE[k]
        except Exception as e:
            log('pexels:', str(e)[:100]); time.sleep(20 * (t + 1))
    CERCHE[k] = {}
    return {}


def giudice(img, cerca, voce):
    if SECCO:
        return True
    return claude(G6.GIUDICE.format(cerca=cerca, voce=voce), modello=HAIKU, immagine=img, max_tokens=5).strip().upper().startswith('SI')


def scarica_img(url):
    return Image.open(io.BytesIO(YT.http(url, raw=True, headers={'User-Agent': 'Mozilla/5.0'}, timeout=120))).convert('RGB')


def foto(cerca, voce, i):
    for q in [cerca, ' '.join(str(cerca).split()[:2])] + G6.SERI:
        prove = 0
        for p in pexels_cerca('foto', q).get('photos', []):
            if p['id'] in USATE or prove >= 3:
                continue
            prove += 1
            try:
                im = scarica_img(p['src']['large2x'])
            except Exception:
                continue
            USATE.add(p['id'])
            if giudice(im, q, voce):
                return im
            log(f'foto {i}: {p["id"]} scartata (non c\'entra)')
    log(f'foto {i}: nessuna adatta, sfondo scuro')
    return Image.new('RGB', (W, H), (18, 17, 16))


def clip(cerca, voce, i):
    for q in [cerca, ' '.join(str(cerca).split()[:2])]:
        prove = 0
        for v in pexels_cerca('clip', q).get('videos', []):
            if v['id'] in CLIP_USATE or v.get('duration', 0) < 4 or prove >= 3:
                continue
            fs = sorted([x for x in v['video_files'] if (x.get('width') or 0) >= 1280 and x.get('file_type') == 'video/mp4'], key=lambda x: abs((x.get('width') or 0) - 1920))
            if not fs:
                continue
            prove += 1; CLIP_USATE.add(v['id'])
            f = os.path.join(LAV, f'pex_{i:03d}.mp4')
            try:
                open(f, 'wb').write(YT.http(fs[0]['link'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}, timeout=300))
            except Exception:
                continue
            if G3.fondo_verde(f):
                continue
            g = os.path.join(LAV, f'fr_{i:03d}.jpg')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(min(2, v.get('duration', 4) / 2)), '-i', f, '-frames:v', '1', g])
            if os.path.exists(g) and giudice(Image.open(g), q, voce):
                return f, v.get('duration', 8)
            log(f'clip {i}: {v["id"]} scartata')
    return None


STILE3D = ('Glossy stylized 3D render like the YouTube channel Gloam: premium finance documentary, smooth glossy materials, dark charcoal background with soft spotlight '
           'and a few floating gold particles, cinematic rim light, simple bold composition with the subject in the center and empty space around it, '
           'absolutely no text, no letters, no numbers, no logos. Scene: ')


def klein(prompt, w=1280, h=720):   # 1280x720 (circa 0,009 $): poi si ingrandisce, a 1920 costerebbe il doppio
    if SECCO:   # prova a secco: niente immagini a pagamento
        im = Image.new('RGB', (w, h), (30, 26, 22)); d = ImageDraw.Draw(im)
        d.ellipse((w / 2 - 260, h / 2 - 260, w / 2 + 260, h / 2 + 260), fill=(200, 160, 50)); return im
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    for k in range(3):
        try:
            inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': w, 'height': h}, 'num_images': 1, 'output_format': 'jpeg'}, hd, timeout=120)
            for _ in range(120):
                time.sleep(2)
                if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
                    break
            u = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
            CO.registra('fal', 'flux-2-klein-4b', dollari=0.009 * max(1.0, w * h / (1280 * 720)))
            return scarica_img(u)
        except Exception as e:
            log('Klein non riuscito, riprovo:', str(e)[:120]); time.sleep(10)
    return None


# ============================================================ 3) SCENE (disegno)
def s_oggetto3d(s, img, t, d, i):
    """Oggetto 3D a tutto schermo che si avvicina piano; le etichette entrano una alla volta (rettangolo pieno + linea verso l'oggetto)."""
    fr = G6.kb(s['_bg'], t, d, i, 1.10).convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    et = [str(x).upper()[:18] for x in (s.get('etichette') or [])][:3]
    pos = [(.16, .22), (.70, .20), (.18, .70)] if i % 2 else [(.68, .24), (.16, .26), (.66, .70)]
    passo = max(.6, (d - .8) / max(1, len(et)))
    for k, testo in enumerate(et):
        st = .35 + k * passo
        if t < st:
            break
        e = G4.ease((t - st) / .3); fx, fy = pos[k]
        f = G4.F(G4.BOLD, 72); w = f.getlength(testo) + 60; x = fx * W; y = fy * H - (1 - e) * 40
        dd.line((x + w / 2, y + 100, W / 2 + (x + w / 2 - W / 2) * .35, H / 2 + (y + 100 - H / 2) * .35), fill=(245, 240, 230, int(220 * e)), width=4)
        col = G4.ROSSO if k == 0 else ((40, 90, 200) if k == 1 else (200, 150, 40))
        dd.rectangle((x, y, x + w, y + 100), fill=col + (int(255 * e),))
        dd.text((x + 30, y + 12), testo, font=f, fill=(255, 255, 255, int(255 * e)))
    fr.alpha_composite(lay); return fr


DISEGNA = dict(G6.DISEGNA, oggetto3d=s_oggetto3d)
SHOTS = []


def rendi_una(i):
    """Disegna una scena in un file mp4 (lanciata in parallelo: 4 scene alla volta)."""
    s = SHOTS[i]; out = s['_out']; dur = s['_dur']
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return out
    if s.get('_bgf'):
        s['_bg'] = Image.open(s['_bgf']).convert('RGB')
    if s['tipo'] == 'dossier':
        s['_ph'] = Image.open(s['_phf']).convert('RGB') if s.get('_phf') else None
    try:
        if s['tipo'] == 'clip':
            G6.scena_clip(i, s, dur, out)
        elif s['tipo'] == 'borsa':
            G3.borsa(i, s, dur, out)
        else:
            enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
            for k in range(int(dur * FPS) + 1):
                enc.stdin.write(DISEGNA[s['tipo']](s, None, k / FPS, dur, i).convert('RGB').tobytes())
            enc.stdin.close(); enc.wait()
    except Exception as e:   # una scena che non si disegna non ferma il video: diventa una foto con la stessa durata
        log(f'scena {i} ({s["tipo"]}) non riuscita: {str(e)[:120]} -> foto')
        s['tipo'] = 'foto'; s['_bg'] = s.get('_bg') or G6.prepara(Image.new('RGB', (W, H), (20, 18, 16)))
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
        for k in range(int(dur * FPS) + 1):
            enc.stdin.write(G6.s_foto(s, None, k / FPS, dur, i).convert('RGB').tobytes())
        enc.stdin.close(); enc.wait()
    return out


# ============================================================ 4) VOCE
def voce(i, testo, prima, dopo):
    f = os.path.join(LAV, f'voce_{i:03d}.mp3')
    if os.path.exists(f) and os.path.getsize(f) > 500:
        return f
    if SECCO:   # silenzio lungo quanto la frase letta (circa 2,5 parole al secondo)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', f'{max(2.5, len(testo.split()) / 2.5):.2f}', f], check=True)
        return f
    for k in range(4):
        try:
            b = YT.http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
                        {'text': testo, 'model_id': VOCE_MOD, 'previous_text': prima[-400:], 'next_text': dopo[:400],
                         'voice_settings': {'stability': .4, 'similarity_boost': .8, 'style': .25}}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=180, raw=True)
            open(f, 'wb').write(b); CO.registra('elevenlabs', VOCE_MOD, crediti=len(testo))
            return f
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(5 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


# ============================================================ 5) COPERTINA (stile A, MANO LIBERA)
def copertina(c):
    import copertine_gloam as CG
    import copertine_gloam_a as CA
    cp = c.get('copertina') or {}
    n = int(num(P.get('riga_produzione'), 0) or random.randint(0, 99))
    # MANO LIBERA: l'ordine rosso / blu / oro nei tre terzi cambia da un video all'altro
    ordini = [('rosso', 'blu', 'oro'), ('oro', 'blu', 'rosso'), ('blu', 'rosso', 'oro'), ('rosso', 'oro', 'blu'), ('oro', 'rosso', 'blu'), ('blu', 'oro', 'rosso')]
    ordine = ordini[n % len(ordini)]
    terzi = ['LEFT third', 'MIDDLE third', 'RIGHT third']
    desc = {'rosso': f"exactly ONE glossy RED faceless mannequin ({cp.get('scena_rosso') or 'the culprit'}); there is only one red figure in the whole image",
            'blu': f"a few glossy BLUE faceless mannequins ({cp.get('scena_blu') or 'the victims'})",
            'oro': f"a big glossy GOLD object ({cp.get('scena_oro') or 'a vault full of coins'}) with a flat blank plate on its front"}
    prompt = CG.STILE + ' '.join(f'{terzi[k]}: {desc[r]}.' for k, r in enumerate(ordine)) + ' Three groups clearly separated, empty dark space above each.'
    im = None
    for k in range(2):
        im = klein(prompt, 1280, 720)
        if im is None:
            break
        im = im.resize((1280, 720))
        if SECCO or claude('Count the RED mannequin figures in this image. Answer SI if there is exactly one red figure, otherwise NO.', modello=HAIKU, immagine=im, max_tokens=5).strip().upper().startswith('SI'):
            break
        log('copertina: piu\' di una figura rossa, la rifaccio')
    if im is None:
        im = Image.new('RGB', (1280, 720), (20, 20, 24))
    pos = {r: .17 + .33 * k for k, r in enumerate(ordine)}
    for k, (r, col) in enumerate((('rosso', CA.ROSSO), ('blu', CA.BLU))):
        if cp.get(r):
            CA.etichetta_centrata(im, pos[r], 70 + k * 18 + (30 if n % 2 else 0), str(cp[r]).upper()[:16], col)
    CA.targa(im, pos['oro'], .40 + (.08 if n % 3 == 1 else 0), str(cp.get('oggetto') or '').upper()[:14])
    f = os.path.join(ROOT, 'copertina.jpg'); im.convert('RGB').save(f, quality=92)
    return f


# ============================================================ MAIN
def main():
    global SHOTS
    if not TITOLO and not SECCO:
        raise RuntimeError('manca il titolo della riga (titolo_italiano / titolo_originale)')
    c = copione(); SHOTS = c['shots']
    # voce prima di tutto: dalla voce si sa quanto dura ogni scena
    for i, s in enumerate(SHOTS):
        s['voce'] = str(s.get('voce') or '').strip() or '...'
        v = voce(i, s['voce'], ' '.join(x['voce'] for x in SHOTS[max(0, i - 3):i]), ' '.join(str(x.get('voce') or '') for x in SHOTS[i + 1:i + 4]))
        s['_voce'] = v; s['_dur'] = round(durata(v) + .12, 3); s['_out'] = os.path.join(LAV, f'scena_{i:03d}.mp4')
    tot_voce = sum(s['_dur'] for s in SHOTS)
    log(f'voce: {tot_voce / 60:.1f} minuti')
    # immagini: oggetti 3D (a pagamento, sotto il budget), clip e foto controllate
    n3d = 0
    for i, s in enumerate(SHOTS):
        tp = s.get('tipo')
        if tp == 'oggetto3d':
            if CO.totale() + .05 > BUDGET_USD or n3d >= 16:   # budget: l'oggetto 3D diventa una foto con titolo
                s.update({'tipo': 'foto', 'titolo': ' '.join(s.get('etichette') or [])[:40]})
            else:
                im = klein(STILE3D + str(s.get('oggetto') or 'a cracked golden vault'))
                if im is None:
                    s.update({'tipo': 'foto', 'titolo': ' '.join(s.get('etichette') or [])[:40]})
                else:
                    n3d += 1; f = os.path.join(LAV, f'bg_{i:03d}.jpg'); G6.prepara(im).save(f, quality=90); s['_bgf'] = f; continue
        if s.get('tipo') == 'clip':
            r = clip(s.get('sfondo') or 'stock exchange', s['voce'], i)
            if r:
                s['_clip'] = r; continue
            s.update({'tipo': 'foto', 'titolo': s.get('cartello') or '', 'etichetta': ''})
        if s.get('tipo') == 'borsa':
            continue
        if s.get('tipo') not in DISEGNA:
            s['tipo'] = 'foto'
        f = os.path.join(LAV, f'bg_{i:03d}.jpg'); fp = os.path.join(LAV, f'ph_{i:03d}.jpg')
        if not os.path.exists(f):
            im = foto(s.get('sfondo') or 'wall street', s['voce'], i)
            G6.prepara(im, sfoca=(s['tipo'] != 'foto')).save(f, quality=90)
            if s['tipo'] == 'dossier':
                im.save(fp, quality=88)
        s['_bgf'] = f
        if s['tipo'] == 'dossier':   # scheda di una persona: sagoma "No photograph"; di un'azienda o un sistema: la foto del luogo/oggetto
            s['_phf'] = fp if (not s.get('persona') and os.path.exists(fp)) else None
    log('immagini pronte | spesa finora', round(CO.totale(), 3), '$')
    # disegno delle scene in parallelo (4 alla volta)
    with mp.get_context('fork').Pool(max(2, (os.cpu_count() or 4))) as pool:
        parti = pool.map(rendi_una, range(len(SHOTS)))
    # audio: voce + colpi e soffi
    boom, whoosh = G3.suoni()
    audio = []
    for i, s in enumerate(SHOTS):
        a = os.path.join(LAV, f'a_{i:03d}.wav'); tp = s['tipo']; d = s['_dur']
        fx = boom if tp in ('dato', 'borsa', 'oggetto3d') or (tp in ('calendario', 'classifica', 'dossier') and s.get('timbro')) else (whoosh if tp in ('foto', 'clip') else None)
        rit = int(d * {'calendario': .5, 'classifica': .7, 'dossier': .75}.get(tp, 0) * 1000)
        if fx:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', s['_voce'], '-i', fx, '-filter_complex',
                            f'[0:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{d:.3f}[v];[1:a]adelay={rit}|{rit},volume=0.35[f];[v][f]amix=inputs=2:duration=first:normalize=0',
                            '-ar', '44100', '-ac', '2', a], check=True)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', s['_voce'], '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True)
        audio.append(a)
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    video = os.path.join(LAV, 'video.mp4'); vocew = os.path.join(LAV, 'voce.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-c', 'copy', video], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), vocew], check=True)
    tot = durata(vocew)
    brani = sorted(x for x in os.listdir(os.path.join(QUI, 'libreria_musica')) if re.match(r'(mistero|tensione)_\d+\.mp3$', x))
    musica = os.path.join(QUI, 'libreria_musica', brani[int(num(P.get('riga_produzione'), 0)) % len(brani)])
    base = os.path.join(LAV, 'base.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', vocew, '-stream_loop', '-1', '-i', musica,
                    '-filter_complex', f'[2:a]volume=0.09,afade=t=out:st={max(0, tot - 3):.2f}:d=3[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{tot:.2f}', base], check=True)
    finale = os.path.join(ROOT, 'video_gloam.mp4')
    if not ISC.applica(base, finale, dict(P, subscribe_overlay_second=P.get('subscribe_overlay_second') or 95), os.path.join(LAV, 'isc'), short=False, log=log, enc=['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19']):
        shutil.copy(base, finale)
    cop = copertina(c)
    dur_v = durata(finale)
    # capitoli per la descrizione (dove inizia ogni capitolo)
    capitoli, off, visto = [], 0.0, None
    for s in SHOTS:
        if s.get('capitolo') != visto:
            visto = s.get('capitolo'); capitoli.append(f"{int(off // 60):02d}:{int(off % 60):02d} {visto}")
        off += s['_dur']
    if capitoli:
        capitoli[0] = '00:00 ' + capitoli[0][6:]
    titolo = str(c.get('titolo') or TITOLO)[:100]
    descr, tags = YT.testi(P, titolo, c.get('descrizione'), capitoli, c.get('tag'))
    tipi = {}
    for s in SHOTS:
        tipi[s['tipo']] = tipi.get(s['tipo'], 0) + 1
    log('FATTO:', finale, round(dur_v / 60, 1), 'minuti | scene', len(SHOTS), '|', tipi, '|', CO.testo() if hasattr(CO, 'testo') else '', '| Pexels', N_PEXELS[0], 'ricerche')
    YT.chiudi(P, finale, cop, titolo, descr, tags, {'testo_copertina': ' / '.join(str((c.get('copertina') or {}).get(k) or '') for k in ('rosso', 'blu', 'oggetto')),
                                                    'minuti_lavoro': 0}, PROVA, CARICA, dur_v, LINGUA, ROOT)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback; traceback.print_exc()
        YT.esito({'stato': 'ERRORE', 'errore': str(e)[:400]}, ROOT)
        raise
