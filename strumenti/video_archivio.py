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
sys.path.insert(0, os.path.join(os.getcwd(), 'coach'))
sys.path.insert(0, os.path.join(os.getcwd(), 'strumenti'))
import manuale as MAN   # colonna carica = MANUALE: tutto pronto ma il video lo carica Giorgio
import ricetta as _RIC   # coach automatico: parametri della versione attiva della ricetta del canale (coach_auto = SI)
P = _RIC.applica(P)
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
PAROLE_SEC = numero(P.get('parole_al_secondo'), 3.3)                                     # largo apposta (misurato 3,1-3,23 parole/s a 1.08): il video deve stare SEMPRE sopra la durata minima del foglio (1 nov, Giorgio: mai sotto 8 minuti)
P_MIN, P_MAX = int(MIN_M * 60 * PAROLE_SEC), int(MAX_M * 60 * PAROLE_SEC)
N_SCENE = round((P_MIN + P_MAX) / 2 / 36)   # numero di scene: Sonnet rispetta il numero di scene meglio del numero di parole
P_OK = int(max(P_MIN * .92, MIN_M * 60 * .95 * PAROLE_SEC * .985))   # minimo accettato: sopra la durata minima del foglio anche con la voce piu' veloce misurata
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
        for k in [k for k, v in valori.items() if k == 'playlist' and str(v or '').strip() and k not in intest]:   # colonna nuova in fondo
            get(f'https://sheets.googleapis.com/v4/spreadsheets/{fid}/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!" + ''.join(chr(65 + x) for x in ([len(intest) // 26 - 1] if len(intest) >= 26 else []) + [len(intest) % 26]) + '1', 'values': [[k]]}]}, h=h_)
            intest.append(k)
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


def json_sicuro(t):
    """JSON della risposta di Claude; se ha un errore di sintassi (es. virgolette non chiuse) lo ripara GRATIS invece di
    rifare il copione (2 nov: un errore di una virgola a Rich Borders = copione rifatto da capo, +0,30 $)."""
    t = t[t.find('{'): t.rfind('}') + 1]
    try:
        return json.loads(t)
    except Exception as e:
        try:
            from json_repair import repair_json
            c = json.loads(repair_json(t))
            log('JSON del copione riparato gratis (errore era:', str(e)[:80] + ')')
            return c
        except ImportError:
            raise e


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

# ---------------- 1b) canali in inglese che copiano un competitor in inglese (11 nov, Giorgio) ----------------
# Stessa lingua e stesso pubblico: YouTube vede i nostri video come doppioni (Agora e WWII quasi senza impression, Orbital con l'IMPRONTA si').
# Si prende SOLO gancio, struttura e argomento; il TITOLO e il testo si riscrivono da zero. KAO e i canali che traducono da un'altra lingua non cambiano.
TITOLO_COMP = P['titolo']
STRUTT = str(P.get('language') or '').strip().lower().startswith('en') and str(P.get('metodo') or 'impronta').strip().lower() == 'copia'
if STRUTT:
    try:
        _c0 = json.load(open(os.path.join('lavoro_archivio', 'copione.json')))
        if _c0.get('titolo_competitor') == TITOLO_COMP and _c0.get('titolo_video'):
            P['titolo'] = _c0['titolo_video']; log('titolo nostro RIPRESO dal giro precedente:', P['titolo'])
    except Exception:
        pass
    if P['titolo'] == TITOLO_COMP:
        try:
            _t = claude(f"""Successful YouTube title of a competitor channel (same language, same audience as ours): "{TITOLO_COMP}".
Our channel: "{P.get('channel_name')}". Write OUR title for a video on the same subject: SAME pattern (same kind of promise and twist, a number if it has one,
same separators like - | : and the same rhythm) but with DIFFERENT words and a different angle on the same documented facts, so that nobody searching
on YouTube would see the two titles as the same. Never reuse its distinctive phrase (e.g. "He Named One City" -> say it another way).
Correct {P.get('language') or 'en'} spelling, max 90 characters, no emoji. Answer ONLY the title.""", modello='claude-sonnet-5-5', max_tokens=4000)
            _t = _t.strip().strip('"').strip()
            if 15 < len(_t) <= 100:
                P['titolo'] = _t; log('titolo NOSTRO (struttura del competitor, parole nuove):', TITOLO_COMP, '->', P['titolo'])
        except Exception as e:
            log('titolo nuovo non riuscito, resta quello della riga:', str(e)[:100])

# ---------------- 2) copione ----------------
# regole del canale dal foglio (colonne regole_fatti, footage_descrizione, footage_esempi_q, footage_esempi_tag, obbligo_apertura):
# vuote = quelle di Orbital Days (NASA)
R_FATTI = P.get('regole_fatti') or 'only documented facts about real space missions and astronauts; never invent names, quotes or numbers. No real astronaut names unless they are famous and the fact is documented.'
R_FOOTAGE = P.get('footage_descrizione') or 'the video is made ONLY of real NASA footage.'
R_Q = P.get('footage_esempi_q') or '"astronaut eating food space station", "spacewalk", "Soyuz landing", "sleeping bag crew quarters"'
R_TAG = P.get('footage_esempi_tag') or '["food", "eating"], ["spacewalk", "suit"]; never only space, station, astronaut, earth'
_ob = str(P.get('obbligo_apertura') or 'astronaut').strip()
R_OBBLIGO = '' if _ob.upper() == 'NO' else f' - the first 3 scenes must make it obvious in one second what the video is about: add "obbligo": ["{_ob}"] to them\n'
regole = f"""You write the narration of a YouTube documentary for the channel "{P.get('channel_name')}".
Title of the video: "{P['titolo']}". Language: {LINGUA} ONLY (every word of the narration, on-screen texts, title, description and tags).
Audience and units: {P.get('cultural_localization') or ''}
Voice style: {P.get('language_register') or ''}
Structure: {P.get('narrative_angle') or ''}
LENGTH: the narration must be between {P_MIN} and {P_MAX} words in total (count them). This is a HARD limit.
FACTS: {R_FATTI}
FOOTAGE: {R_FOOTAGE} For EACH scene give the archive search that shows EXACTLY what the narration says:
 - "q": 2-5 English words for the video archive (e.g. {R_Q})
 - "tag": 2-4 specific lowercase English keywords of what must be visible (e.g. {R_TAG}); NEVER only generic words
{R_OBBLIGO} - "anno" (only for history videos): the year the scene talks about (e.g. 1944), so the archive footage is from the right year; 0 if the scene has no precise year
 - "capitolo" (YouTube chapters): on the FIRST scene and then on the scene that opens each new part of the story, about one every 60-90 seconds (6-9 in total): a chapter title of 2-5 words in the channel language; every other scene "capitolo": ""
 - "scritta" (optional, about 1 scene in 4): 1-3 words in CAPS shown on screen, a number or a strong word said in that scene (US units: -250°F, 17,500 MPH, 250 MILES)
Scenes: EXACTLY {N_SCENE} scenes, each 32-40 words (Sonnet tends to write too little: count the scenes).
OPENING (the first 3 scenes, about 30 seconds: this decides if the viewer stays): scene 1 gives the PAYOFF of the title at once, the most surprising
answer, fact or number (say the end first, then explain how we get there); no greetings, no "in this video", no slow scene-setting, no generic intro.
Scenes 2-3 open one concrete question the viewer wants answered and promise what is coming ("but the real danger is not the fire. It is what comes next").
After that, a new small reveal or surprising detail about every 60-90 seconds, so there is always a reason to keep watching."""   # 11 nov (Giorgio): gancio forte, ritenzione a 30 s bassa su Orbital Days
METODO = str(P.get('metodo') or 'impronta').strip().lower()   # copia (stesso argomento del competitor) | impronta (stessa struttura, altro argomento)
if riferimento and METODO == 'copia' and STRUTT:
    regole += f"""

REFERENCE VIDEO (a successful video of a competitor in the SAME language: copying it makes ours a duplicate). Take ONLY its opening hook
(the mechanism, not the words), its STRUCTURE (order of the parts, rhythm, kind of questions and reveals) and its subject. Write the narration
FROM SCRATCH: never its sentences, examples, metaphors, anecdotes, lists or turns of phrase, not even reworded with synonyms. Facts only from
documented history; quotes only if real and documented. Make it BETTER than the original, not just different: clearer explanations, one extra surprising and documented fact or comparison, a stronger hook.
{' '.join(riferimento.split()[:6000])}"""
elif riferimento and METODO == 'copia':
    PCT = int(numero(P.get('copia_percentuale'), 80))
    regole += f"""

REFERENCE VIDEO (same topic, a successful video of the channel we copy): keep about {PCT}% of its content (the same story, facts, order, hooks,
questions and reveals), rewritten in your own words, never copying sentences word by word. The other {100 - PCT}% is new, documented material
that fits the same pattern and makes the video better. Make it BETTER than the original, not just different: clearer explanations, one extra surprising and documented fact or comparison, a stronger hook. Never add facts, quotes, dates or numbers that are not in the reference or in documented history.
{' '.join(riferimento.split()[:6000])}"""
elif riferimento:
    regole += f"""

REFERENCE VIDEO (copy its STRUCTURE, rhythm, hooks and kind of questions — NOT its topic): {P.get('riferimento_descrizione') or 'a successful video about ancient Rome.'}
{' '.join(riferimento.split()[:6000])}"""
if not str(P.get('testo_copertina') or '').strip():
    regole += """

THUMBNAIL TEXT ("testo_copertina"): 1-3 words in CAPS, built on the TITLE of this video. """ + (
        'The attached image is the thumbnail of the successful competitor video: FIRST try to adapt ITS text idea (same mechanism: a short shock word, a question, a contrast, a number) to our title and topic. Only if it cannot be adapted, invent one in the same style. ' if COP_COMP else
        'No competitor thumbnail for this title: invent one in the style of the channel (examples: NO WEEKENDS, TOO COLD?, NO BED, NO ESCAPE, THE NIGHT SHIFT). ') + """It must complete the title and create curiosity, never repeat it word by word, in the channel language only."""
regole += """

Answer ONLY with valid JSON:
{"scene": [{"testo": "...", "q": "...", "tag": ["..."], "scritta": "", "obbligo": [], "capitolo": "", "anno": 0}],
 "descrizione": "YouTube description, 3 short paragraphs (~120 words) with the words people search, then a line with 4-6 hashtags",
 "tag": ["20-30 YouTube tags"],
 "testo_copertina": "1-3 WORDS (only if asked above, else empty)",
 "copertina_prompt": "one sentence: the scene of the thumbnail, """ + (P.get('copertina_soggetto') or 'a FICTIONAL astronaut') + """ with a strong readable emotion matching the title: setting, action, key object and light (the framing is decided later)"}"""
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
        c = json_sicuro(t)
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
Same fields as the other scenes (testo, q, tag, scritta, obbligo, capitolo, anno). Answer ONLY with JSON: {{"scene": [...]}}""", max_tokens=12000)
    try:
        nuove = json_sicuro(agg)['scene']
        c['scene'] = c['scene'][:dove] + nuove + c['scene'][dove:]
        n = sum(len(s['testo'].split()) for s in c['scene'])
        log(f'copione allungato: +{len(nuove)} scene -> {len(c["scene"])} scene, {n} parole')
    except Exception as e:
        log('allungamento non leggibile:', str(e)[:120])
if c and not (P_OK <= n <= P_MAX * 1.15):
    c = None
if not c:
    raise RuntimeError('VIDEO BLOCCATO: copione fuori lunghezza (nessuna spesa per voce e montaggio)')
c['titolo_video'] = P['titolo']; c['titolo_competitor'] = TITOLO_COMP
json.dump(c, open(os.path.join(CART, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
os.makedirs(RIP, exist_ok=True); json.dump(c, open(os.path.join(RIP, 'copione.json'), 'w'), ensure_ascii=False)   # salvato per un'eventuale ripresa

# ---------------- 3) montaggio (strumenti/prova_archivio.py) ----------------
mont = {'nome': NOME, 'voce': P.get('voice_id'), 'velocita': numero(P.get('voice_speed'), 1.08),
        'stabilita': numero(P.get('voce_stabilita'), .4), 'stile_voce': numero(P.get('voce_stile'), .25),
        'musica': P.get('musica_file') or 'epico_002.mp3', 'volume_musica': 0.07, 'volume_voce': numero(P.get('volume_voce'), 1.0),   # 9 nov: colonna volume_voce (WWII: voce piu' alta) 'max_secondi': 3.3, 'solo_video_fino_a': 30,
        'movimenti_camera': P.get('movimenti_camera') or 'NO', 'suono_foto': P.get('suono_foto') or 'NO',
        'libreria': P.get('libreria') or '', 'archivio': str(P.get('libreria_archivio') or 'nasa').strip().lower(),
        'foto_riserva': [x.strip() for x in str(P.get('foto_riserva') or '').split(';') if x.strip()] or None, 'scene': [{k: s.get(k) for k in ('testo', 'q', 'tag', 'scritta', 'obbligo', 'anno') if s.get(k)} for s in c['scene']]}
VIDEO = os.path.join(CART, 'prova.mp4')
MIN_VIDEO = numero(P.get('video_movimento_minimo'), 80)   # colonna del foglio (decide Giorgio): OBIETTIVO di video in movimento (le riparazioni puntano qui)
BLOCCO_VIDEO = numero(P.get('video_movimento_blocco'), MIN_VIDEO)   # 5 nov (Giorgio): sotto questa quota si blocca; tra blocco e obiettivo si pubblica lo stesso (es. 50)


def archivio_sbagliato():
    if mont['archivio'] == 'nasa':
        return ''
    try:
        f_ = open(os.path.join(CART, 'fonti.txt')).read()
    except Exception:
        return ''
    import re as _re
    n_ = len(_re.findall(r'\b(iss\d{3}|jsc\d|ksc|nasa|expedition|astronaut|space station)', f_, _re.I))
    return f'{n_} inquadrature da archivio NASA/spazio in un canale storico' if n_ else ''


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
    if archivio_sbagliato():
        err.append(archivio_sbagliato())
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
# ---------------- REVISIONE DELLE INQUADRATURE (2 nov, Giorgio: "aumenta i controlli, deve uscire un video fatto bene") ----------------
# Haiku guarda OGNI inquadratura con la frase che la voce dice in quel momento e boccia quelle sbagliate (epoca, spazio/NASA, cartoni,
# cartelli con scritte, svastiche in primo piano, scena che non c'entra). Le bocciate si tolgono e il montaggio si rifa' (voce gia' pagata).
def revisione():
    try:
        inq = json.load(open('/tmp/lav/inquadrature.json'))
    except Exception as e:
        log('revisione: elenco inquadrature non letto', str(e)[:80]); return []
    argomento = P.get('niche') or P.get('channel_name') or ''
    bocciate = []
    for k in range(0, len(inq), 20):
        g_ = inq[k:k + 20]; cont = []
        for x in g_:
            try:
                b_ = open(x['frame'], 'rb').read()
            except Exception:
                continue
            cont.append({'type': 'text', 'text': f"Shot {x['i']} ({x.get('tipo')}). Narration: \"{x.get('testo', '')[:600]}\"" + (f" (our own on-screen text was cut out of this image: only the top part is shown)." if x.get('scritta') else '')})
            cont.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(b_).decode()}})
        cont.append({'type': 'text', 'text': f'These are shots of a YouTube documentary about: {argomento}. For each shot decide if it is WRONG for this video. '
                     'A shot is WRONG if: ' + ('it shows a different era (modern/after 1950 vehicles, clothes, colour TV look) or space/astronauts/NASA; '
                     if str(P.get('libreria_archivio') or '').strip().lower() == 'storico' else '') + 'it is a cartoon, '
                     'animation, map graphic or drawing; it is a title card, intertitle or has burned-in text/subtitles/timecode; a swastika flag or Nazi banner is '
                     'the main subject; it is black/empty; or it clearly belongs to ANOTHER subject (e.g. a horse show or a reindeer in a war video, a car on Earth in a space video). '
                     'Footage that fits the channel topic and period is fine even if generic or not literally what the sentence says (archival black-and-white footage, '
                     'space/station/mission control footage for a space video). Text we added on purpose (listed per shot) is fine. Judge ONLY the image: the narration is given just as context and may be cut, never reject a shot because of the narration text. Answer ONLY JSON: {"sbagliate": [{"i": <shot number>, "motivo": "short reason"}]} (empty list if all are fine).'})
        try:
            corpo = {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1200, 'messages': [{'role': 'user', 'content': cont}]}
            r_ = get('https://api.anthropic.com/v1/messages', corpo, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
            u_ = r_.get('usage', {}); spendi('claude haiku (revisione inquadrature)', (u_.get('input_tokens', 0) * 1 + u_.get('output_tokens', 0) * 5) / 1e6)
            t_ = ''.join(b.get('text', '') for b in r_.get('content', []))
            for b in json_sicuro(t_).get('sbagliate', []):
                x = next((y for y in g_ if y['i'] == int(b.get('i', -1))), None)
                if x:
                    bocciate.append(dict(x, motivo=b.get('motivo', '')))
        except RuntimeError:
            raise
        except Exception as e:
            log('revisione: gruppo non controllato', str(e)[:100])
    log(f'REVISIONE: {len(bocciate)} inquadrature bocciate su {len(inq)}' + (': ' + '; '.join(f"{x['i']} {x['motivo']}" for x in bocciate[:12]) if bocciate else ''))
    return bocciate


def segna_in_libreria(bocciate):   # gli spezzoni bocciati non tornano piu' nei video (la libreria impara); file a parte: niente conflitti con il giro notturno
    if not P.get('libreria'):
        return
    f_ = os.path.join('libreria_clip', P['libreria'], 'bocciati.json')
    try:
        vecchi = json.load(open(f_)) if os.path.exists(f_) else []
        nuovi = [{'n': x['lib_n'], 'fonte': x.get('fonte'), 'motivo': x.get('motivo', '')} for x in bocciate if x.get('lib_n') is not None]
        nuovi += [{'foto': x['fonte'], 'motivo': x.get('motivo', '')} for x in bocciate if x.get('lib_n') is None and x.get('tipo') == 'foto' and x.get('fonte')]
        nuovi += [{'clip': x['fonte'], 'motivo': x.get('motivo', '')} for x in bocciate if x.get('lib_n') is None and x.get('tipo') == 'clip' and x.get('fonte')]   # 11 nov: clip prese dall'archivio (non dalla libreria)
        json.dump(vecchi + nuovi, open(f_, 'w'), ensure_ascii=False, indent=1); log(len(nuovi), 'spezzoni tolti per sempre dalla libreria (bocciati.json)')
    except Exception as e:
        log('bocciati non salvati', str(e)[:80])


if MONTATO and os.path.exists(VIDEO) and str(P.get('revisione_inquadrature') or 'SI').upper() != 'NO':
    # 5 nov: con UN solo rimontaggio Orbital Days e WWII venivano bloccati 3 volte al giorno (9-21 inquadrature ancora sbagliate):
    # ogni giro toglie le nuove bocciate e rimonta, fino a 3 giri (voce gia' pagata). La soglia resta il 4% (min 3).
    soglia = max(3, len(json.load(open('/tmp/lav/inquadrature.json'))) * .04)
    bocc = revisione(); giri = 0; via_lib, via_foto, via_clip = [], [], []
    while bocc and len(bocc) > (soglia if giri else 0) and giri < int(float(str(P.get('giri_revisione') or 3))):
        giri += 1
        segna_in_libreria(bocc)
        via_lib += [x['lib_n'] for x in bocc if x.get('lib_n') is not None]
        via_foto += [x['fonte'] for x in bocc if x.get('tipo') == 'foto']
        # 11 nov: anche le clip prese direttamente dall'archivio (non dalla libreria) si tolgono: prima tornavano sempre uguali
        # (Orbital Days bloccato con le stesse 3 clip di un lancio di razzo dopo 3 rimontaggi)
        via_clip += [x['fonte'] for x in bocc if x.get('tipo') == 'clip' and x.get('lib_n') is None and x.get('fonte')]
        m_ = dict(mont, escludi_lib=via_lib, escludi_foto=via_foto, escludi=list(mont.get('escludi') or []) + via_clip)
        shutil.copy(VIDEO, VIDEO + '.prima_revisione.mp4')
        log(f'RIMONTAGGIO {giri}: tolte {len(via_lib) + len(via_clip)} clip e {len(via_foto)} foto bocciate')
        r = subprocess.run([sys.executable, 'strumenti/prova_archivio.py'], env=dict(os.environ, PAYLOAD=json.dumps(m_)))
        if r.returncode != 0 or not os.path.exists(VIDEO):
            os.replace(VIDEO + '.prima_revisione.mp4', VIDEO); errori = errori + ['revisione: rimontaggio non riuscito']; bocc = []
            break
        os.remove(VIDEO + '.prima_revisione.mp4')
        quota, media, dur, errori = controlli()
        bocc = revisione()
    if giri and bocc:
        segna_in_libreria(bocc)   # anche le bocciate dell'ultimo giro non tornano piu'
    toll = max(soglia, len(json.load(open('/tmp/lav/inquadrature.json'))) * numero(P.get('revisione_tolleranza'), 4) / 100)   # 5 nov (Giorgio): blocco solo oltre la tolleranza del canale
    if len(bocc) > toll:
        errori = errori + [f'ancora {len(bocc)} inquadrature sbagliate dopo {giri} rimontaggi']

if MONTATO and archivio_sbagliato():   # materiale di un altro argomento: mai caricato, nemmeno non in elenco
    raise RuntimeError('VIDEO BLOCCATO: ' + archivio_sbagliato())
if errori and quota >= BLOCCO_VIDEO:   # movimento sotto l'obiettivo ma sopra la soglia di blocco: non si butta il video
    sotto = [e for e in errori if 'di video in movimento' in e]
    if sotto:
        log(f'MOVIMENTO {quota:.0f}%: sotto l\'obiettivo {MIN_VIDEO:g}% ma sopra la soglia di blocco {BLOCCO_VIDEO:g}%: si pubblica')
        errori = [e for e in errori if e not in sotto]
if errori:
    if not MONTATO or not os.path.exists(VIDEO) or (P.get('privacy') or 'unlisted') == 'public':
        raise RuntimeError('VIDEO BLOCCATO (controlli, anche dopo la riparazione): ' + '; '.join(errori))
    DA_CONTROLLARE = '; '.join(errori)   # video non in elenco: si carica comunque e lo si segnala, Giorgio lo vede prima di pubblicare
    log('CARICATO DA CONTROLLARE (non in elenco):', DA_CONTROLLARE)

# ---------------- 4b) pulsante Mi piace/Iscriviti + campanella con i suoni (6 nov, Giorgio: su tutti i video di tutti i canali) ----------------
if MONTATO and os.path.exists(VIDEO):
    sys.path.insert(0, 'strumenti'); import iscrizione as ISC
    if ISC.applica(VIDEO, VIDEO + '.isc.mp4', P, LAV, log=log, enc=['-c:v', 'libx264', '-preset', 'medium', '-crf', '18']):
        os.replace(VIDEO + '.isc.mp4', VIDEO)
    # 10 nov (Giorgio: "su tutti i canali in massima qualita'"): video finale a 1440p, YouTube gli da' la codifica migliore
    import motore_yt as _YT
    if _YT.nitido(VIDEO, VIDEO + '.1440.mp4') == VIDEO + '.1440.mp4':
        os.replace(VIDEO + '.1440.mp4', VIDEO)

# ---------------- 5) copertina stile C ----------------
FP = os.path.join(LAV, 'anton.ttf'); open(FP, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
base = os.path.join(LAV, 'base.jpg')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', '6', '-i', VIDEO, '-frames:v', '1', base])
im = Image.open(base).convert('RGB').resize((1280, 720))
STILE_COP = str(P.get('copertina_stile') or 'C').strip().lower()   # C = Orbital Days | etichetta_rossa = WWII Testimony (B dello studio copertine)
# 8 nov (Giorgio): copertine MAI tutte uguali (YouTube penalizza quelle fatte in serie): stile e colori fissi, ma a rotazione
# cambiano il lato del volto e la posizione della scritta. 0 = volto a destra, scritta in alto a sinistra (come prima);
# 1 = volto a sinistra, scritta in alto a destra; 2 = volto a destra, scritta in basso a sinistra (in basso a destra mai: c'e' la durata del video)
_VAR = int(str(P.get('copertina_variante') or __import__('datetime').date.today().toordinal() % 3)) % 3
VOLTO_SX = _VAR == 1
TESTO_BASSO = _VAR == 2
LATO_V, LATO_T = ('LEFT', 'RIGHT') if VOLTO_SX else ('RIGHT', 'LEFT')
log('impaginazione copertina:', _VAR, '| volto', LATO_V, '| scritta', 'in basso' if TESTO_BASSO else 'in alto', 'a', LATO_T)
# 8 nov (Giorgio, MANO LIBERA): non sempre il viso grande. Cambia anche l'inquadratura, su un giro di 4 giorni diverso da quello del lato (3):
# le combinazioni si ripetono solo ogni 12 video e la copertina non e' mai uguale alla precedente.
INQ = int(str(P.get('copertina_inquadratura') or __import__('datetime').date.today().toordinal() % 4)) % 4
INQUADRATURE = [
    ('primo piano', 'The face is big and sharp, head and shoulders filling the {V} 60% of the frame, strong readable emotion'),
    ('mezzo busto', 'Medium shot from the waist up: the person is doing something meaningful for the story (hands and objects visible), filling the {V} 55% of the frame, readable emotion'),
    ('scena larga', 'Wide shot: the whole person is small-medium in a dramatic environment that tells the story (the place dominates), placed in the {V} 60% of the frame'),
    ('dettaglio', 'Close-up of the key object or action of the story (hands, a tool, a document, a visor or a window) with the person partly visible behind, filling the {V} 60% of the frame'),
]
INQ_NOME, INQ_TXT = INQUADRATURE[INQ][0], INQUADRATURE[INQ][1].format(V=LATO_V) + f'. NOBODY else in the {LATO_T} 40% (that side is kept empty for the title: no faces, no heads there)'
log('inquadratura copertina:', INQ_NOME)
if STILE_COP == 'etichetta_rossa':
    PROMPT_COP = ('Use the reference photo only for the setting and the era. ' + c.get('copertina_prompt', '') +
                  ' Black and white 1940s archival photograph look, real film grain, documentary realism. The person is FICTIONAL and does not resemble any real '
                  'historical figure. No swastikas, no Nazi flags or armbands, no insignia, no text, no letters, no logos. '
                  f'{INQ_TXT}; the {LATO_T} 40% simpler and darker.')
else:
    PROMPT_COP = ('Use the reference photo only for the setting. ' + c.get('copertina_prompt', '') +
                  ' The astronaut is a FICTIONAL person who does not resemble any real astronaut. Unbranded suit and clothes: NO NASA logo, no agency insignia, '
                  'no flags, no patches. Photorealistic cinematic film still, dramatic light, high contrast. '
                  f'{INQ_TXT}. The {LATO_T} 40% darker and simple. No text, no letters, no logos.')
def senza_bordi_neri(img):   # bande nere ai lati del fotogramma (pellicole d'epoca): via prima del ritocco
    g_ = img.convert('L'); w_, h_ = g_.size; px = g_.load()
    col = lambda x: sum(px[x, y] for y in range(0, h_, 8)) / len(range(0, h_, 8))
    sx, dx = 0, w_ - 1
    while sx < w_ * .2 and col(sx) < 22:
        sx += 1
    while dx > w_ * .8 and col(dx) < 22:
        dx -= 1
    if sx > 4 or dx < w_ - 5:
        c_ = img.crop((sx, 0, dx + 1, h_)); nh_ = int(c_.width * 9 / 16)
        c_ = c_.crop((0, (c_.height - nh_) // 2, c_.width, (c_.height - nh_) // 2 + nh_)) if c_.height > nh_ else c_
        log('copertina: tolte le bande nere del fotogramma'); return c_.resize((1280, 720))
    return img


def ritocca(img, prompt):
    if not E('FAL_KEY') or SPESA['usd'] + 0.04 > BUDGET_USD:
        return None
    spendi('fal seedream (copertina)', 0.04)
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=90); h = {'Authorization': 'Key ' + E('FAL_KEY')}
    try:
        inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', {
            'prompt': prompt, 'image_urls': ['data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()],
            'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, h)
        for _ in range(120):
            time.sleep(4); st = get(inv['status_url'], h=h)
            if st.get('status') == 'COMPLETED':
                return Image.open(io.BytesIO(get(get(inv['response_url'], h=h)['images'][0]['url'], raw=True))).convert('RGB').resize((1280, 720))
            if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
                break
    except Exception as e:
        log('ritocco copertina non riuscito:', str(e)[:150])
    return None


def ha_svastica(img):   # CONTROLLO (2 nov, Giorgio): mai simboli nazisti in copertina (l'AI a volte li disegna lo stesso)
    try:
        buf = io.BytesIO(); x_ = img.copy(); x_.thumbnail((900, 900)); x_.save(buf, 'JPEG', quality=85)
        t_ = claude('Is a swastika (or any Nazi symbol: swastika armband, Nazi flag, SS runes) visible ANYWHERE in this image, even small or in the background? '
                    'Answer ONLY {"svastica": true} or {"svastica": false}.', modello='claude-haiku-4-5-20251001', max_tokens=30, immagine=buf.getvalue())
        return bool(json_sicuro(t_).get('svastica'))
    except Exception as e:
        log('controllo simboli non riuscito:', str(e)[:100]); return True   # nel dubbio: niente immagine ritoccata


if STILE_COP == 'etichetta_rossa':
    im = senza_bordi_neri(im)
r_im = ritocca(im, PROMPT_COP)
if r_im is not None and STILE_COP == 'etichetta_rossa' and ha_svastica(r_im):
    log('copertina: il ritocco ha disegnato una svastica, rifaccio')
    r_im = ritocca(im, PROMPT_COP + ' ABSOLUTELY NO swastika or Nazi symbol anywhere: plain uniforms with no armbands.')
    if r_im is not None and ha_svastica(r_im):
        log('copertina: ancora simboli nazisti, uso il fotogramma vero senza ritocco'); r_im = None
if r_im is not None:
    im = r_im
elif STILE_COP == 'etichetta_rossa':   # senza ritocco: anche il fotogramma vero non deve avere simboli nazisti
    for sec_ in (25, 45, 70):
        if not ha_svastica(im):
            break
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(sec_), '-i', VIDEO, '-frames:v', '1', base])
        im = senza_bordi_neri(Image.open(base).convert('RGB').resize((1280, 720)))
TESTO_COP = str(P.get('testo_copertina') or '').strip() or str(c.get('testo_copertina') or '').strip() or 'WHY?'
TESTO_COP = TESTO_COP.rstrip(' .')   # 10 nov (Giorgio): nelle copertine MAI il punto finale
if STILE_COP == 'etichetta_rossa':
    # STILE B (2 nov, Giorgio): bianco e nero d'archivio, fascia rossa con la frase in bianco. Leggibile da telefono:
    # al massimo 2 righe, lettere alte almeno 80 px su 720 (ad anteprima piccola restano leggibili)
    from PIL import ImageOps as _IO, ImageEnhance as _IE
    im = _IE.Contrast(_IO.grayscale(im).convert('RGB')).enhance(1.25)
    d = ImageDraw.Draw(im); parole = TESTO_COP.upper().split()
    # 8 nov (Giorgio): scritte PIU' GRANDI, fondamentale per leggerle da telefono
    alto_ = VOLTO_SX or _VAR == 0   # fascia in alto (a destra mai in basso: c'e' la durata del video)
    if alto_:   # nel 40% libero accanto al volto: una parola per riga (max 3 righe), lettere grandi
        righe = parole if len(parole) <= 3 else [' '.join(parole[:(len(parole) + 1) // 2]), ' '.join(parole[(len(parole) + 1) // 2:])]
        s_, larg_max = 180, 1280 * .48 - 44   # 10 nov (Giorgio): lettere grandi come la copertina di Guderian (la migliore), circa 175 px
    else:
        righe = [' '.join(parole)] if len(parole) <= 2 else [' '.join(parole[:(len(parole) + 1) // 2]), ' '.join(parole[(len(parole) + 1) // 2:])]
        s_, larg_max = 165, 760
    def _alt(sz):   # altezza totale delle fasce rosse con lettere di grandezza sz
        f_ = ImageFont.truetype(FP, sz); b_ = d.textbbox((0, 0), 'ABC', font=f_); return len(righe) * ((b_[3] - b_[1]) + 38)
    # 10 nov (Giorgio, regola per tutti i canali): mai scritte dietro la durata del video (angolo in basso a destra, ultimi 150 px)
    while s_ > 100 and (max(d.textlength(r_, font=ImageFont.truetype(FP, s_)) for r_ in righe) > larg_max or (alto_ and 40 + _alt(s_) > 720 - 150)):
        s_ -= 4
    fnt = ImageFont.truetype(FP, s_); hb = d.textbbox((0, 0), 'ABC', font=fnt)
    y = 40 if alto_ else 720 - 50 - ((hb[3] - hb[1]) + 38) * len(righe)
    for r_ in righe:
        l_, t_, rr_, b_ = d.textbbox((0, 0), r_, font=fnt)
        x_ = (1280 - 40 - ((rr_ - l_) + 44)) if VOLTO_SX else 40
        d.rectangle((x_, y, x_ + (rr_ - l_) + 44, y + (b_ - t_) + 30), fill=(200, 22, 22))
        d.text((x_ + 22 - l_, y + 15 - t_), r_, font=fnt, fill='white')
        y += (b_ - t_) + 30 + 8
    log('testo copertina:', TESTO_COP, '| altezza lettere', s_, 'px')
else:
    # 10 nov (Giorgio, Orbital Days): la scritta NON deve mai coprire la persona ne' il soggetto, e mai dietro la durata (in basso a destra).
    # MANO LIBERA resta: stile fisso (bianco + ultima parola azzurra, contorno nero), posto e grandezza cambiano. Haiku dice dov'e' il soggetto
    # (~0,001 $), poi si prova ogni posto libero (colonna del lato vuoto, in alto o in basso) e si sceglie quello con le lettere piu' grandi.
    im.save(os.path.join(CART, 'copertina_base.jpg'), quality=92)   # base senza scritta: si riscrive gratis
    sog = (0, 0, 0, 0)
    try:
        buf = io.BytesIO(); x_ = im.copy(); x_.save(buf, 'JPEG', quality=85)
        t_ = claude('This is a 1280x720 thumbnail. Give the bounding boxes (pixels) of EVERY person (whole visible body, helmet included) and of the key object '
                    'they interact with. Answer ONLY {"box": [[x1, y1, x2, y2], ...]}.', modello='claude-haiku-4-5-20251001', max_tokens=300, immagine=buf.getvalue())
        bx = [[int(float(v)) for v in b_[:4]] for b_ in json_sicuro(t_)['box'] if len(b_) >= 4]
        sog = (min(b_[0] for b_ in bx), min(b_[1] for b_ in bx), max(b_[2] for b_ in bx), max(b_[3] for b_ in bx))   # tutte le persone insieme
        log('copertina: soggetto in', sog)
    except Exception as e:
        log('posizione soggetto non trovata, uso il lato libero previsto:', str(e)[:100])
        sog = (0, 0, 640, 720) if VOLTO_SX else (640, 0, 1280, 720)
    d = ImageDraw.Draw(im)
    parole = TESTO_COP.upper().split(); righe = [' '.join(parole[:-1]), parole[-1]] if len(parole) > 1 else parole
    def _misure(larg, alt):
        s0 = 230
        while s0 > 70:
            ms = [s0] * len(righe)
            ms = [min(s0, max(60, int(s0 * larg / max(1, d.textlength(r_, font=ImageFont.truetype(FP, s0)))))) for r_ in righe]
            if sum(int(m * 1.02) for m in ms) <= alt:
                return ms
            s0 -= 6
        return None
    candidati = []
    for lato in ('sx', 'dx'):
        for vert in ('alto', 'basso'):
            if lato == 'dx' and vert == 'basso':
                continue   # mai dietro la durata del video
            # zona libera: dal bordo fino al soggetto (con aria), oppure sopra/sotto il soggetto
            x0, x1 = (45, sog[0] - 30) if lato == 'sx' else (sog[2] + 30, 1280 - 45)
            if x1 - x0 < 240:   # accanto non c'e' spazio: proviamo sopra o sotto il soggetto, su tutta la meta' del lato
                x0, x1 = (45, 640) if lato == 'sx' else (640, 1280 - 45)
                y0, y1 = (35, sog[1] - 25) if vert == 'alto' else (sog[3] + 25, 720 - 40)
            else:
                y0, y1 = (35, 720 - 40) if lato == 'sx' else (35, 720 - 175)
            if lato == 'dx':
                y1 = min(y1, 720 - 175)
            if x1 - x0 < 240 or y1 - y0 < 150:
                continue
            ms = _misure(min(x1 - x0, 600), y1 - y0)
            if ms:
                candidati.append((min(ms), lato, vert, x0, x1, y0, y1, ms))
    # MANO LIBERA: tra i posti buoni (lettere almeno l'85% del migliore) si alterna in base al giorno
    if candidati:
        top = max(c_[0] for c_ in candidati)
        buoni = sorted([c_ for c_ in candidati if c_[0] >= top * .85], key=lambda c_: (c_[1], c_[2]))
        _, lato, vert, x0, x1, y0, y1, misure = buoni[_VAR % len(buoni)]
    else:   # nessun posto libero: il lato con piu' spazio accanto al soggetto, in alto, lettere piu' piccole
        lato = 'sx' if sog[0] >= 1280 - sog[2] else 'dx'; vert = 'alto'
        x0, x1, y0, y1 = (45, max(200, sog[0] - 25), 35, 680) if lato == 'sx' else (min(1080, sog[2] + 25), 1235, 35, 545)
        misure = _misure(x1 - x0, y1 - y0) or [80] * len(righe)
    log('copertina: scritta', lato, vert, '| lettere', misure)
    # ombra solo sotto la scritta (non piu' meta' immagine scurita): l'immagine resta limpida
    alt_tot = sum(int(m * 1.02) for m in misure)
    y = y0 if vert == 'alto' else y1 - alt_tot
    ombra = Image.new('L', (1280, 720), 0); do = ImageDraw.Draw(ombra)
    do.rectangle((x0 - 40, y - 30, x1 + 40, y + alt_tot + 30), fill=120)
    from PIL import ImageFilter as _IF
    im.paste(Image.new('RGB', (1280, 720)), (0, 0), ombra.filter(_IF.GaussianBlur(45))); d = ImageDraw.Draw(im)
    for i, (rr, s_) in enumerate(zip(righe, misure)):
        f_ = ImageFont.truetype(FP, s_)
        x_ = (x1 - d.textlength(rr, font=f_)) if lato == 'dx' else x0
        d.text((x_, y), rr, font=f_, fill='#4FD2FF' if i == len(righe) - 1 and len(righe) > 1 else 'white', stroke_width=max(8, s_ // 11), stroke_fill=(0, 0, 0))
        y += int(s_ * 1.02)
COP = os.path.join(CART, 'copertina.jpg'); im.save(COP, quality=92)

# ---------------- capitoli (tempi VERI della voce, come Storia in Minuti e Rich Borders) ----------------
def capitoli():
    try:
        tempi = json.load(open(os.path.join(CART, 'tempi_scene.json')))
    except Exception:
        return ''
    righe, ultimo = [], -100
    for i, (s_, (a, b)) in enumerate(zip(c['scene'], tempi)):
        tit = re.sub(r'\s+', ' ', str(s_.get('capitolo') or '')).strip()
        if tit and (not righe or a - ultimo >= 15):
            tt = 0 if not righe else int(a)
            righe.append(f'{tt // 60}:{tt % 60:02d} ' + tit[:60]); ultimo = a
    if len(righe) > 10:   # troppi capitoli confondono: se ne tengono 10 distribuiti (il primo a 0:00 resta)
        passo = (len(righe) - 1) / 9
        righe = [righe[0]] + [righe[round(1 + i * passo)] for i in range(9)]
    if len(righe) < 3:
        log('capitoli: meno di 3, non inseriti'); return ''
    log('capitoli:', len(righe))
    return ('Capitoli:' if str(P.get('language') or 'en')[:2] == 'it' else 'Chapters:') + '\n' + '\n'.join(righe)


CAPITOLI = capitoli()
if CAPITOLI:
    c['descrizione'] = str(c.get('descrizione') or '').strip() + '\n\n' + CAPITOLI
import descrizione as DESCR
c['descrizione'] = DESCR.con_titolo(P['titolo'], c.get('descrizione'))   # 6 nov (Giorgio): la prima frase della descrizione e' sempre il titolo
c['tag'] = DESCR.tag_con_titolo(P['titolo'], c.get('tag', []))   # 6 nov (Giorgio): il titolo e' anche uno dei tag


def playlist(vid_id_, tk_):
    """Come gli altri canali: playlist per argomento (colonna playlist_topics se compilata), creata se non esiste. Scelta con Haiku."""
    try:
        H_ = {'Authorization': 'Bearer ' + tk_, 'Content-Type': 'application/json'}
        try:
            esistenti = {x['snippet']['title'].strip(): x['id'] for x in get('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', h=H_).get('items', [])}
        except Exception as e_:   # 7 nov: con la quota YouTube finita la playlist restava vuota; si sceglie lo stesso tra quelle gia' usate nel foglio
            log('elenco playlist non letto:', str(e_)[:80]); esistenti = {x: '' for x in P.get('playlist_usate') or []}
            if vid_id_ is not None:
                raise
        lista = [x.strip() for x in re.split(r'[,;|\n]', str(P.get('playlist_topics') or '')) if x.strip()]
        domanda = (f'YouTube channel "{P.get("channel_name")}". Video title: "{P["titolo"]}".\nExisting playlists: {json.dumps(list(esistenti), ensure_ascii=False)}\n'
                   + (f'Allowed playlist names (choose EXACTLY one, same spelling): {json.dumps(lista, ensure_ascii=False)}\n' if lista else
                      f'If an existing playlist fits, answer with its exact name. Otherwise propose ONE new playlist name, 2-4 words in {LINGUA}, broad enough for 10+ future videos (a theme), never the video title.\n')
                   + 'Answer ONLY with the playlist name.')
        nome = claude(domanda, modello='claude-haiku-4-5-20251001', max_tokens=60).strip().strip('"').strip()[:140]
        if not nome:
            return ''
        if vid_id_ is None:   # caricamento a mano: solo il nome (se non esiste, Giorgio la crea in YouTube Studio)
            return nome + ('' if nome in esistenti else ' (nuova: da creare)')
        pid = esistenti.get(nome)
        if not pid:
            pid = get('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': nome}, 'status': {'privacyStatus': 'public'}}, h=H_)['id']
            log('playlist creata:', nome)
        for k_ in range(4):   # playlist appena creata: per qualche secondo YouTube risponde 409
            try:
                get('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid_id_}}}, h=H_)
                break
            except Exception:
                if k_ == 3:
                    raise
                time.sleep(10 * (k_ + 1))
        log('video aggiunto alla playlist:', nome); return nome
    except Exception as e:
        log('playlist non riuscita:', str(e)[:200]); return ''


# ---------------- 6) caricamento su YouTube ----------------
vid_id = ''
if str(P.get('carica') or '').upper() == 'SI' and E('YT_REFRESH_TOKEN'):
    tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
        'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()), timeout=60).read())['access_token']
    pulisci = lambda t: re.sub(r'[<>]', '', str(t)).strip()
    tags, tot = [], 0
    for t in c.get('tag', []):   # YouTube: massimo 500 caratteri di tag in tutto, niente < >
        t = pulisci(t)[:100]   # il primo tag e' il titolo intero
        if t and tot + len(t) + 3 <= 450:
            tags.append(t); tot += len(t) + 3
    meta = {'snippet': {'title': pulisci(P['titolo'])[:100], 'description': pulisci(c.get('descrizione', ''))[:4900], 'tags': tags,
                        'categoryId': str(P.get('youtube_category_id') or 27), 'defaultLanguage': str(P.get('language') or 'en')[:2],
                        'defaultAudioLanguage': str(P.get('language') or 'en')[:2]},
            'status': {'privacyStatus': P.get('privacy') or 'unlisted', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}}
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
    import dichiarazioni_yt as DICH   # 8 nov: dichiarazione dentro il caricamento (niente modifica dopo da 50 unita')
    up = DICH.sessione('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', meta,
                       {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json', 'X-Upload-Content-Type': 'video/mp4'}, 60)
    req = urllib.request.Request(up, data=open(VIDEO, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'video/mp4'})
    ris = json.loads(urllib.request.urlopen(req, timeout=3600).read()); vid_id = ris['id']
    log('caricato su YouTube:', vid_id, '(' + (P.get('privacy') or 'unlisted') + ')')
    DICH.nessuna_promozione(vid_id, tk, ris)
    try:
        req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid_id}', data=open(COP, 'rb').read(),
                                     headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'image/jpeg'})
        urllib.request.urlopen(req, timeout=120); log('copertina caricata')
    except Exception as e:
        log('copertina non caricata (canale da verificare per le miniature personalizzate?):', str(e)[:150])
    playlist(vid_id, tk)
NOME_PLAYLIST = ''
if MAN.attivo(P):   # caricamento a mano: video + copertina in da_caricare/ (artifact da scaricare), testi nel file di produzione
    try:
        tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
            'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()), timeout=60).read())['access_token']
        NOME_PLAYLIST = playlist(None, tk)
    except Exception as e:
        log('playlist per il caricamento a mano non scelta:', str(e)[:150])
    MAN.prepara(VIDEO, COP, P['titolo'], os.getcwd())

try:   # file del video per gli Short (artifact shorts-<canale>-riga<N>): solo questo video, non le vecchie prove nel repository
    os.makedirs('per_shorts', exist_ok=True); shutil.copy(VIDEO, os.path.join('per_shorts', 'video.mp4'))
except Exception as e:
    log('file per gli Short non preparato:', str(e)[:120])

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
if MAN.attivo(P) and not vid_id:
    riga_produzione({'status': MAN.STATO, 'titolo_italiano': P['titolo'], 'titolo_thumbnail': TESTO_COP, 'descrizione_youtube': c.get('descrizione', ''),
                     'tag_seo': ', '.join(c.get('tag', [])), 'playlist': NOME_PLAYLIST, 'data_pubblicazione': MAN.orario(P)})
else:
  riga_produzione({'status': 'Completato', 'youtube_video_id': vid_id, 'titolo_thumbnail': TESTO_COP, 'descrizione_youtube': c.get('descrizione', ''),
                 'tag_seo': ', '.join(c.get('tag', [])), 'data_pubblicazione': (meta['status'].get('publishAt', '') if vid_id else '') or time.strftime('%Y-%m-%d %H:%M') + (' (non in elenco)' if (P.get('privacy') or 'unlisted') != 'public' else '')})
print('VIDEO_ID=' + vid_id)
log('FATTO', NOME, f"{SPESA['usd']:.3f} $")
