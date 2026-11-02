#!/usr/bin/env python3
"""
VIDEO ARCHIVIO (per tutti i canali fatti con archivi video gratuiti, es. Orbital Days con la NASA) — il video VERO, non la prova.
1) testo del video di riferimento (impronta del competitor, RapidAPI) -> copione NUOVO sul nostro titolo, stessa struttura,
   lunghezza fissata dai minuti del foglio, tutto nella lingua del canale (unita' di misura del pubblico: es. °F per gli USA)
2) montaggio con strumenti/prova_archivio.py (voce con i tempi, clip dalla libreria e dall'archivio, mai la stessa due volte)
3) CONTROLLI prima del caricamento: durata nei minuti del foglio, almeno 80% di video in movimento, inquadrature corte
4) copertina nello stile fisso del canale (stile C: foto del video + ritocco AI, personaggio inventato, niente loghi)
5) caricamento su YouTube (privacy del foglio: per le prime prove 'unlisted') + riga del file di produzione aggiornata
Spesa: copione (Claude) + 1 ritocco copertina, con TETTO sul totale (coach_budget_video del foglio, in euro).
PAYLOAD = riga di Channel Configs + {"titolo": "...", "testo_copertina": "...", "link_competitor": "...", "nome": "..."}
"""
import shutil, base64, io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = re.sub(r'[^a-z0-9_]+', '_', (P.get('nome') or P.get('titolo') or 'video').lower())[:60]
CART = os.path.join('prove_video', 'archivio', NOME); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/va'; os.makedirs(LAV, exist_ok=True)
LINGUA = {'en': 'English (US)', 'it': 'italiano'}.get(str(P.get('language') or 'en')[:2], str(P.get('language')))
def numero(x, base):   # numeri del foglio: 1,08 / 1.08 / "01:08" (cella formattata come ora) -> 1.08
    try:
        return float(re.sub(r'[^0-9.\-]', '', str(x).replace(',', '.').replace(':', '.')) or base) if str(x or '').strip() else float(base)
    except Exception:
        return float(base)


MIN_M = numero(P.get('durata_min_minuti'), 8.5); MAX_M = numero(P.get('durata_max_minuti'), 9)
PAROLE_SEC = 3.3                                     # largo apposta (misurato 3,1-3,23 parole/s a 1.08): il video deve stare SEMPRE sopra la durata minima del foglio (1 nov, Giorgio: mai sotto 8 minuti)
P_MIN, P_MAX = int(MIN_M * 60 * PAROLE_SEC), int(MAX_M * 60 * PAROLE_SEC)
N_SCENE = round((P_MIN + P_MAX) / 2 / 36)   # numero di scene: Sonnet rispetta il numero di scene meglio del numero di parole
P_OK = int(max(P_MIN * .92, MIN_M * 60 * .95 * 3.25))   # minimo accettato: sopra la durata minima del foglio anche con la voce piu' veloce misurata
BUDGET_USD = float(str(P.get('coach_budget_video') or P.get('budget_video') or 1).replace(',', '.').replace('€', '') or 1) * 1.08
SPESA = {'usd': 0.0, 'voci': []}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def _costo_se_fermo():   # anche un giro che si ferma ha speso: va nello storico costi del canale (esito BLOCCATO)
    if SPESA.get('fatto') or not SPESA['usd']:
        return
    f = os.path.join('coach', 'costi', re.sub(r'[^a-z0-9]+', '_', str(P.get('channel_id') or 'canale').lower()).strip('_') + '.tsv')
    os.makedirs('coach/costi', exist_ok=True); nuovo = not os.path.exists(f)
    with open(f, 'a') as o:
        if nuovo:
            o.write('data\tcosto_dollari\tcrediti_voce\tprova\tlink\tdettaglio\tesito\n')
        cr_ = 0   # crediti voce gia' pagati in questo giro fermato (prima venivano segnati 0)
        try:
            if not globals().get('VOCE_RIPRESA') and any(f_.startswith('voce_') for f_ in os.listdir('/tmp/lav')):
                cr_ = len(' '.join(s_['testo'] for s_ in c['scene']))
        except Exception:
            pass
        o.write('\t'.join([time.strftime('%Y-%m-%d %H:%M'), f"{SPESA['usd']:.3f}", str(cr_), 'NO', '', json.dumps(SPESA['voci']), 'BLOCCATO']) + '\n')


def riga_produzione(valori):
    """Aggiorna la riga del file di produzione (se il video e' partito dall'avvio giornaliero)."""
    fid, n = P.get('foglio_produzione'), P.get('riga_produzione')
    if not fid or not n or not E('GOOGLE_SA_KEY'):
        return
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        cr = service_account.Credentials.from_service_account_info(json.loads(E('GOOGLE_SA_KEY')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        cr.refresh(Request()); h_ = {'Authorization': 'Bearer ' + cr.token}
        sch = get(f'https://sheets.googleapis.com/v4/spreadsheets/{fid}?fields=sheets.properties', h=h_)['sheets'][0]['properties']['title']
        intest = get(f'https://sheets.googleapis.com/v4/spreadsheets/{fid}/values/' + urllib.parse.quote(f"'{sch}'!A1:AZ1"), h=h_)['values'][0]
        col = lambda k: ''.join(chr(65 + x) for x in ([intest.index(k) // 26 - 1] if intest.index(k) >= 26 else []) + [intest.index(k) % 26])
        dati = [{'range': f"'{sch}'!{col(k)}{n}", 'values': [[v]]} for k, v in valori.items() if k in intest]
        get(f'https://sheets.googleapis.com/v4/spreadsheets/{fid}/values:batchUpdate', {'valueInputOption': 'RAW', 'data': dati}, h=h_)
        log('file di produzione aggiornato:', ', '.join(valori))
    except Exception as e:
        log('file di produzione non aggiornato:', str(e)[:150])


def _riga_se_fermo():   # video fermato: la riga torna Pronto, riparte al prossimo giro
    if not SPESA.get('fatto'):
        riga_produzione({'status': 'Pronto', 'data_inizio_produzione': ''})


import atexit
atexit.register(_costo_se_fermo)
atexit.register(_riga_se_fermo)


def get(u, dati=None, h=None, raw=False, timeout=300, metodo=None):
    req = urllib.request.Request(u, data=(dati if isinstance(dati, bytes) else json.dumps(dati).encode()) if dati is not None else None,
                                 headers=dict({'User-Agent': 'ambience-video-archivio/1.0', **({'Content-Type': 'application/json'} if dati is not None and not isinstance(dati, bytes) else {})}, **(h or {})),
                                 method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def spendi(voce, usd):
    SPESA['usd'] += usd; SPESA['voci'].append(f'{voce}: {usd:.3f} $')
    if SPESA['usd'] > BUDGET_USD:
        raise RuntimeError(f'VIDEO BLOCCATO (budget): speso {SPESA["usd"]:.2f} $ oltre {BUDGET_USD:.2f} $')


def claude(prompt, modello='claude-sonnet-5-5', max_tokens=24000, immagine=None):
    contenuto = prompt if not immagine else [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(immagine).decode()}},
                                              {'type': 'text', 'text': prompt}]
    corpo = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': contenuto}]}
    if 'sonnet-5' in modello:   # Sonnet 5.5 ragiona prima di rispondere e il ragionamento consumava tutti i token: risposta vuota
        corpo.update(thinking={'type': 'between_tools'}, output_config={'effort': 'medium'})
    r = get('https://api.anthropic.com/v1/messages', corpo,
            {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=600)
    u = r.get('usage', {}); prezzi = (3, 15) if 'sonnet' in modello else (1, 5)
    spendi('claude ' + modello, (u.get('input_tokens', 0) * prezzi[0] + u.get('output_tokens', 0) * prezzi[1]) / 1e6)
    return ''.join(b.get('text', '') for b in r.get('content', []))


# ---------------- 1) impronta del competitor ----------------
riferimento = ''
vid = (re.search(r'(?:v=|youtu\.be/)([\w-]{11})', str(P.get('link_competitor') or '')) or [None, None])[1]
if vid and E('RAPIDAPI_KEY'):
    try:
        j = get('https://youtube-transcript3.p.rapidapi.com/api/transcript?videoId=' + vid,
                h={'X-RapidAPI-Key': E('RAPIDAPI_KEY'), 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com'}, timeout=120)
        righe = j.get('transcript') or []
        riferimento = re.sub(r'\s+', ' ', ' '.join(str(x.get('text', '')) for x in righe) if isinstance(righe, list) else str(righe)).strip()
        log('testo di riferimento:', len(riferimento.split()), 'parole')
    except Exception as e:
        log('testo di riferimento non letto:', str(e)[:120])

# copertina del video competitor (gratis): il testo della NOSTRA copertina parte dalla sua idea (1 nov, Giorgio)
COP_COMP = None
if vid and not str(P.get('testo_copertina') or '').strip():
    for q_ in ('maxresdefault', 'hqdefault'):
        try:
            COP_COMP = get(f'https://i.ytimg.com/vi/{vid}/{q_}.jpg', raw=True, timeout=60); break
        except Exception:
            pass

# ---------------- 2) copione ----------------
regole = f"""You write the narration of a YouTube documentary for the channel "{P.get('channel_name')}".
Title of the video: "{P['titolo']}". Language: {LINGUA} ONLY (every word of the narration, on-screen texts, title, description and tags).
Audience and units: {P.get('cultural_localization') or ''}
Voice style: {P.get('language_register') or ''}
Structure: {P.get('narrative_angle') or ''}
LENGTH: the narration must be between {P_MIN} and {P_MAX} words in total (count them). This is a HARD limit.
FACTS: only documented facts about real space missions and astronauts; never invent names, quotes or numbers. No real astronaut names unless they are famous and the fact is documented.
FOOTAGE: the video is made ONLY of real NASA footage. For EACH scene give the archive search that shows EXACTLY what the narration says:
 - "q": 2-5 English words for the NASA video archive (e.g. "astronaut eating food space station", "spacewalk", "Soyuz landing", "sleeping bag crew quarters")
 - "tag": 2-4 specific lowercase English keywords of what must be visible (e.g. ["food", "eating"], ["spacewalk", "suit"]); NEVER only generic words like space, station, astronaut, earth
 - the first 3 scenes must make it obvious in one second that the video is about astronauts (astronauts in the station or on a spacewalk): add "obbligo": ["astronaut"] to them
 - "scritta" (optional, about 1 scene in 4): 1-3 words in CAPS shown on screen, a number or a strong word said in that scene (US units: -250°F, 17,500 MPH, 250 MILES)
Scenes: EXACTLY {N_SCENE} scenes, each 32-40 words (Sonnet tends to write too little: count the scenes)."""
if riferimento:
    regole += f"""

REFERENCE VIDEO (copy its STRUCTURE, rhythm, hooks and kind of questions — NOT its topic): a successful video about ancient Rome.
{' '.join(riferimento.split()[:6000])}"""
if not str(P.get('testo_copertina') or '').strip():
    regole += """

THUMBNAIL TEXT ("testo_copertina"): 1-3 words in CAPS, built on the TITLE of this video. """ + (
        'The attached image is the thumbnail of the successful competitor video: FIRST try to adapt ITS text idea (same mechanism: a short shock word, a question, a contrast, a number) to our title and topic. Only if it cannot be adapted, invent one in the same style. ' if COP_COMP else
        'No competitor thumbnail for this title: invent one in the style of the channel (examples: NO WEEKENDS, TOO COLD?, NO BED, NO ESCAPE, THE NIGHT SHIFT). ') + """It must complete the title and create curiosity, never repeat it word by word, in the channel language only."""
regole += """

Answer ONLY with valid JSON:
{"scene": [{"testo": "...", "q": "...", "tag": ["..."], "scritta": "", "obbligo": []}],
 "descrizione": "YouTube description, 3 short paragraphs (~120 words) with the words people search, then a line with 4-6 hashtags",
 "tag": ["20-30 YouTube tags"],
 "testo_copertina": "1-3 WORDS (only if asked above, else empty)",
 "copertina_prompt": "one sentence: the scene of the thumbnail, a FICTIONAL astronaut in close-up with a strong readable emotion matching the title, setting and light"}"""
c = None; n = 0; VOCE_RIPRESA = False
# RIPRESA (2 nov, Giorgio: non buttare soldi nei giri falliti): se un giro precedente sullo STESSO titolo si e' fermato dopo aver
# pagato copione e voce, il workflow li ha salvati in lavoro_archivio/: si riusano (stesso testo = stessa voce, zero crediti ElevenLabs)
RIP = 'lavoro_archivio'
try:
    c0 = json.load(open(os.path.join(RIP, 'copione.json')))
    if c0.get('titolo_video') == P['titolo'] and c0.get('scene'):
        c = c0; n = sum(len(s['testo'].split()) for s in c['scene'])
        os.makedirs('/tmp/lav', exist_ok=True)
        for f_ in os.listdir(RIP):
            if f_.startswith('voce_') and f_.endswith('.json'):
                shutil.copy(os.path.join(RIP, f_), os.path.join('/tmp/lav', f_))
        VOCE_RIPRESA = any(f_.startswith('voce_') for f_ in os.listdir(RIP))
        log(f'copione RIPRESO dal giro fallito precedente ({len(c["scene"])} scene, {n} parole): nessuna spesa di copione; voce salvata:',
            any(f_.startswith('voce_') for f_ in os.listdir(RIP)))
except Exception:
    pass
if c is None:
    t = claude(regole, immagine=COP_COMP)
    try:
        c = json.loads(t[t.find('{'): t.rfind('}') + 1])
        n = sum(len(s['testo'].split()) for s in c['scene'])
        log(f'copione: {len(c["scene"])} scene, {n} parole (obiettivo {P_MIN}-{P_MAX}, minimo accettato {P_OK})')
    except Exception as e:
        c = None; n = 0; log('copione non leggibile:', str(e)[:120], '| risposta:', len(t), 'caratteri', repr(t[:200]))
# troppo corto: NON si riscrive tutto (Sonnet tornava sempre a ~1360 parole) ma si AGGIUNGONO scene nel mezzo
for giro in range(2):
    if not c or n >= P_OK:
        break
    manca = (P_MIN + P_MAX) // 2 - n; k_ = max(3, round(manca / 36)); dove = max(1, len(c['scene']) - 3)
    agg = claude(f"""This is the narration of a YouTube documentary titled "{P['titolo']}", in {LINGUA} ONLY, as JSON scenes:
{json.dumps(c['scene'], ensure_ascii=False)}
It is {n} words: too short. Write EXACTLY {k_} NEW scenes (32-40 words each, about {manca} words in total) that go between scene {dove} and scene {dove + 1}:
new documented facts and moments on the same topic, same voice and rules, no repetition of what is already said, smooth with the scenes before and after.
Same fields as the other scenes (testo, q, tag, scritta, obbligo). Answer ONLY with JSON: {{"scene": [...]}}""", max_tokens=12000)
    try:
        nuove = json.loads(agg[agg.find('{'): agg.rfind('}') + 1])['scene']
        c['scene'] = c['scene'][:dove] + nuove + c['scene'][dove:]
        n = sum(len(s['testo'].split()) for s in c['scene'])
        log(f'copione allungato: +{len(nuove)} scene -> {len(c["scene"])} scene, {n} parole')
    except Exception as e:
        log('allungamento non leggibile:', str(e)[:120])
if c and not (P_OK <= n <= P_MAX * 1.15):
    c = None
if not c:
    raise RuntimeError('VIDEO BLOCCATO: copione fuori lunghezza (nessuna spesa per voce e montaggio)')
c['titolo_video'] = P['titolo']
json.dump(c, open(os.path.join(CART, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
os.makedirs(RIP, exist_ok=True); json.dump(c, open(os.path.join(RIP, 'copione.json'), 'w'), ensure_ascii=False)   # salvato per un'eventuale ripresa

# ---------------- 3) montaggio (strumenti/prova_archivio.py) ----------------
mont = {'nome': NOME, 'voce': P.get('voice_id'), 'velocita': numero(P.get('voice_speed'), 1.08),
        'stabilita': numero(P.get('voce_stabilita'), .4), 'stile_voce': numero(P.get('voce_stile'), .25),
        'musica': P.get('musica_file') or 'epico_002.mp3', 'volume_musica': 0.07, 'max_secondi': 3.3, 'solo_video_fino_a': 30,
        'libreria': P.get('libreria') or '', 'scene': [{k: s.get(k) for k in ('testo', 'q', 'tag', 'scritta', 'obbligo') if s.get(k)} for s in c['scene']]}
VIDEO = os.path.join(CART, 'prova.mp4')
MIN_VIDEO = numero(P.get('video_movimento_minimo'), 80)   # colonna del foglio (decide Giorgio): sotto questa quota un video pubblico si blocca


def controlli():
    costi = open(os.path.join(CART, 'costi.txt')).read()
    quota = float((re.search(r'video in movimento: (\d+)', costi) or [0, 0])[1])
    media = float((re.search(r'inquadratura media ([\d.]+)', costi) or [0, 9])[1])
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=duration', '-of', 'csv=p=0', VIDEO], capture_output=True, text=True).stdout or 0)   # durata delle IMMAGINI, non dell'audio
    err = []
    if not (MIN_M * 60 * .95 <= dur <= MAX_M * 60 * 1.12):
        err.append(f'durata {dur / 60:.1f} min fuori da {MIN_M:g}-{MAX_M:g}')
    if quota < MIN_VIDEO:
        err.append(f'solo {quota:.0f}% di video in movimento (minimo {MIN_VIDEO:g}%)')
    if media > 3.6:
        err.append(f'inquadratura media {media:.1f} s (massimo 3,3)')
    log(f'CONTROLLI: durata {dur / 60:.1f} min, video in movimento {quota:.0f}%, inquadratura media {media:.1f} s' + (' | DA RIPARARE: ' + '; '.join(err) if err else ' | OK'))
    return quota, media, dur, err


# RIPARAZIONE AUTOMATICA (31 ott, Giorgio: "i video non si devono bloccare"): se un controllo non passa, si rifa' il montaggio
# con regole piu' strette (clip ovunque, inquadrature piu' corte, altri momenti delle riprese gia' scaricate) invece di fermarsi.
TENTATIVI = [mont, dict(mont, solo_video_fino_a=99999, max_secondi=3.0)]
quota = media = dur = 0; errori = ['montaggio non riuscito']; MONTATO = False; MIGLIORE = None
for t_, m_ in enumerate(TENTATIVI):
    if os.path.exists(VIDEO):
        os.remove(VIDEO)   # mai caricare il video rotto di un tentativo precedente
    r = subprocess.run([sys.executable, 'strumenti/prova_archivio.py'], env=dict(os.environ, PAYLOAD=json.dumps(m_)))
    if r.returncode:
        log('montaggio non riuscito al tentativo', t_ + 1); continue
    MONTATO = True
    quota, media, dur, errori = controlli()
    if not errori:
        break
    if not MIGLIORE or quota > MIGLIORE[0]:   # si tiene la versione migliore (piu' video in movimento) tra quelle fatte
        MIGLIORE = (quota, media, dur, errori); shutil.copy(VIDEO, VIDEO + '.migliore.mp4')
    log('RIPARAZIONE: rifaccio il montaggio con clip ovunque e inquadrature piu\' corte')
# argomenti senza clip in libreria -> la libreria li cerchera' nei prossimi giri (cresce dove serve)
try:
    mancano = [x for x in open(os.path.join(CART, 'mancanti.txt')).read().splitlines() if x.strip()]
    if mancano and P.get('libreria'):
        fm = os.path.join('libreria_clip', P['libreria'], 'ricerche_mancanti.txt'); os.makedirs(os.path.dirname(fm), exist_ok=True)
        gia = set(open(fm).read().splitlines()) if os.path.exists(fm) else set()
        open(fm, 'a').write(''.join(x + '\n' for x in mancano if x not in gia))
        log(len(mancano), 'argomenti senza clip in libreria: aggiunti alle ricerche dei prossimi giri')
except Exception:
    pass
DA_CONTROLLARE = ''
if errori and MIGLIORE and os.path.exists(VIDEO + '.migliore.mp4') and (not os.path.exists(VIDEO) or MIGLIORE[0] > quota):
    os.replace(VIDEO + '.migliore.mp4', VIDEO); quota, media, dur, errori = MIGLIORE
    log(f'si usa la versione migliore: {quota:.0f}% di video in movimento')
if os.path.exists(VIDEO + '.migliore.mp4'):
    os.remove(VIDEO + '.migliore.mp4')
if errori:
    if not MONTATO or not os.path.exists(VIDEO) or (P.get('privacy') or 'unlisted') == 'public':
        raise RuntimeError('VIDEO BLOCCATO (controlli, anche dopo la riparazione): ' + '; '.join(errori))
    DA_CONTROLLARE = '; '.join(errori)   # video non in elenco: si carica comunque e lo si segnala, Giorgio lo vede prima di pubblicare
    log('CARICATO DA CONTROLLARE (non in elenco):', DA_CONTROLLARE)

# ---------------- 5) copertina stile C ----------------
FP = os.path.join(LAV, 'anton.ttf'); open(FP, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
base = os.path.join(LAV, 'base.jpg')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '6', '-i', VIDEO, '-frames:v', '1', base])
im = Image.open(base).convert('RGB').resize((1280, 720))
if E('FAL_KEY') and SPESA['usd'] + 0.04 <= BUDGET_USD:
    spendi('fal seedream (copertina)', 0.04)
    buf = io.BytesIO(); im.save(buf, 'JPEG', quality=90); h = {'Authorization': 'Key ' + E('FAL_KEY')}
    try:
        inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', {
            'prompt': 'Use the reference photo only for the setting. ' + c.get('copertina_prompt', '') +
                      ' The astronaut is a FICTIONAL person who does not resemble any real astronaut. Unbranded suit and clothes: NO NASA logo, no agency insignia, '
                      'no flags, no patches. Photorealistic cinematic film still, dramatic light, high contrast. The astronaut is very big, head and shoulders filling '
                      'the RIGHT 60% of the frame. The LEFT 40% darker and simple. No text, no letters, no logos.',
            'image_urls': ['data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()], 'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, h)
        for _ in range(120):
            time.sleep(4); st = get(inv['status_url'], h=h)
            if st.get('status') == 'COMPLETED':
                im = Image.open(io.BytesIO(get(get(inv['response_url'], h=h)['images'][0]['url'], raw=True))).convert('RGB').resize((1280, 720)); break
            if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
                break
    except Exception as e:
        log('ritocco copertina non riuscito:', str(e)[:150])
g = Image.new('L', (1280, 1))
for x in range(1280):
    g.putpixel((x, 0), int(170 * max(0, ((1 - x / 1280) - .5) / .5)))
im.paste(Image.new('RGB', (1280, 720)), (0, 0), g.resize((1280, 720))); d = ImageDraw.Draw(im)
TESTO_COP = str(P.get('testo_copertina') or '').strip() or str(c.get('testo_copertina') or '').strip() or 'WHY?'
log('testo copertina:', TESTO_COP, '(dal foglio)' if str(P.get('testo_copertina') or '').strip() else '(creato dal titolo e dalla copertina del competitor)')
parole = TESTO_COP.upper().split(); righe = [' '.join(parole[:-1]), parole[-1]] if len(parole) > 1 else parole
y = 110
for i, rr in enumerate(righe):
    s_ = 240
    while s_ > 60 and d.textlength(rr, font=ImageFont.truetype(FP, s_)) > 600:
        s_ -= 4
    d.text((50, y), rr, font=ImageFont.truetype(FP, s_), fill='#4FD2FF' if i == len(righe) - 1 and len(righe) > 1 else 'white', stroke_width=max(8, s_ // 11), stroke_fill=(0, 0, 0))
    y += int(s_ * 1.02)
COP = os.path.join(CART, 'copertina.jpg'); im.save(COP, quality=92)

# ---------------- 6) caricamento su YouTube ----------------
vid_id = ''
if str(P.get('carica') or '').upper() == 'SI' and E('YT_REFRESH_TOKEN'):
    tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
        'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()), timeout=60).read())['access_token']
    pulisci = lambda t: re.sub(r'[<>]', '', str(t)).strip()
    tags, tot = [], 0
    for t in c.get('tag', []):   # YouTube: massimo 500 caratteri di tag in tutto, niente < >
        t = pulisci(t)[:60]
        if t and tot + len(t) + 3 <= 450:
            tags.append(t); tot += len(t) + 3
    meta = {'snippet': {'title': pulisci(P['titolo'])[:100], 'description': pulisci(c.get('descrizione', ''))[:4900], 'tags': tags,
                        'categoryId': str(P.get('youtube_category_id') or 27), 'defaultLanguage': str(P.get('language') or 'en')[:2],
                        'defaultAudioLanguage': str(P.get('language') or 'en')[:2]},
            'status': {'privacyStatus': P.get('privacy') or 'unlisted', 'selfDeclaredMadeForKids': False}}
    # canale pubblico: esce all'ora del foglio (publish_time, ora italiana), oggi se c'e' tempo, altrimenti domani
    ora_pub = re.match(r'(\d{1,2})[:.](\d{2})', str(P.get('publish_time') or ''))
    if meta['status']['privacyStatus'] == 'public' and ora_pub and not DA_CONTROLLARE:
        import datetime as dt_
        from zoneinfo import ZoneInfo
        ora = dt_.datetime.now(ZoneInfo('Europe/Rome'))
        quando = ora.replace(hour=int(ora_pub[1]), minute=int(ora_pub[2]), second=0, microsecond=0)
        if quando < ora + dt_.timedelta(minutes=30):
            quando += dt_.timedelta(days=1)
        meta['status'].update(privacyStatus='private', publishAt=quando.astimezone(dt_.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        log('esce il', quando.strftime('%d/%m alle %H:%M'), '(ora italiana)')
    req = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', data=json.dumps(meta).encode(),
                                 headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json', 'X-Upload-Content-Type': 'video/mp4'})
    up = urllib.request.urlopen(req, timeout=60).headers['Location']
    req = urllib.request.Request(up, data=open(VIDEO, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'video/mp4'})
    vid_id = json.loads(urllib.request.urlopen(req, timeout=3600).read())['id']
    log('caricato su YouTube:', vid_id, '(' + (P.get('privacy') or 'unlisted') + ')')
    try:
        req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}', data=open(COP, 'rb').read(),
                                     headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'image/jpeg'})
        urllib.request.urlopen(req, timeout=120); log('copertina caricata')
    except Exception as e:
        log('copertina non caricata (canale da verificare per le miniature personalizzate?):', str(e)[:150])

# ---------------- 7) costi e riepilogo ----------------
crediti = 0 if VOCE_RIPRESA else len(' '.join(s['testo'] for s in c['scene']))   # voce ripresa da un giro fallito: gia' contata li'
open(os.path.join(CART, 'riepilogo.txt'), 'w').write(f"titolo: {P['titolo']}\nyoutube: {vid_id}\n" + (f"DA CONTROLLARE: {DA_CONTROLLARE}\n" if DA_CONTROLLARE else '') + f"spesa: {SPESA['usd']:.3f} $ ({'; '.join(SPESA['voci'])}) + {crediti} crediti voce\n"
                                                     f"durata: {dur / 60:.1f} min | video in movimento: {quota:.0f}% | inquadratura media: {media:.1f} s\n")
os.makedirs('coach/costi', exist_ok=True)
f = os.path.join('coach', 'costi', re.sub(r'[^a-z0-9]+', '_', str(P.get('channel_id') or 'canale').lower()).strip('_') + '.tsv')
nuovo = not os.path.exists(f)
with open(f, 'a') as o:
    if nuovo:
        o.write('data\tcosto_dollari\tcrediti_voce\tprova\tlink\tdettaglio\tesito\n')
    o.write('\t'.join([time.strftime('%Y-%m-%d %H:%M'), f"{SPESA['usd']:.3f}", str(crediti), 'NO', 'https://www.youtube.com/watch?v=' + vid_id if vid_id else '',
                       json.dumps(SPESA['voci']), 'OK']) + '\n')
SPESA['fatto'] = True
riga_produzione({'status': 'Completato', 'youtube_video_id': vid_id, 'titolo_thumbnail': TESTO_COP, 'descrizione_youtube': c.get('descrizione', ''),
                 'tag_seo': ', '.join(c.get('tag', [])), 'data_pubblicazione': (meta['status'].get('publishAt', '') if vid_id else '') or time.strftime('%Y-%m-%d %H:%M') + (' (non in elenco)' if (P.get('privacy') or 'unlisted') != 'public' else '')})
print('VIDEO_ID=' + vid_id)
log('FATTO', NOME, f"{SPESA['usd']:.3f} $")
