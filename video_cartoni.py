#!/usr/bin/env python3
"""MOTORE "CARTONI + GRAFICI" (7 nov 2026, primo canale: Quanto Ti Resta). Tutto disegnato in codice: si paga solo il copione (Claude) e la voce (ElevenLabs).
1) Claude scrive la puntata dal titolo della riga del file di produzione (colonne attivita e lezione): storia con un protagonista,
   esempi sempre diversi, numeri a schermo, e per ogni scena le inquadrature scelte tra i modelli di motore_cartoni/tpl.js.
2) Voce ElevenLabs scena per scena, con i tempi di ogni parola: ogni inquadratura parte quando la voce dice la sua parola.
3) Montaggio con Chromium (motore_cartoni/video.html): un'inquadratura nuova ogni 3-6 secondi, mai la stessa immagine, sottotitoli e capitoli.
4) Musica e suoni dalla libreria del repository, pulsante Iscriviti con i suoni, copertina disegnata in codice.
5) Caricamento: colonna carica = SI -> YouTube (programmato all'ora di uscita); MANUALE -> cartella da_caricare/ e testi nel file di produzione.
Colonne di Channel Configs usate: channel_name, language, niche, narrative_angle, target_audience, voice_id, voice_model_id, voice_speed, voce_ritmo,
durata_min_minuti, durata_max_minuti, slogan, youtube_description_footer, youtube_default_tags, playlist, carica, privacy, subscribe_overlay_*, modello_ai."""
import base64, json, os, re, shutil, subprocess, sys, time, unicodedata, urllib.parse, urllib.request
ROOT = os.getcwd()
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI); sys.path.insert(0, os.path.join(QUI, 'strumenti'))
os.environ.setdefault('COSTI_FILE', os.path.join(ROOT, 'lavoro_cartoni', 'costi_video.jsonl'))
import costi as CO
import descrizione as DESCR
import manuale as MAN
import iscrizione as ISC
try:
    import dichiarazioni_yt as DICH
except Exception:
    DICH = None
E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}') or {}
RIGA = P.get('riga') or {}
LAV = os.path.join(ROOT, 'lavoro_cartoni'); os.makedirs(LAV, exist_ok=True)
MOT = os.path.join(QUI, 'motore_cartoni')
PROVA = str(E('PROVA') or P.get('prova') or 'NO').upper() == 'SI'
CARICA = str(E('CARICA') or 'NO').upper() == 'SI' and not MAN.attivo(P)
MODELLO = str(P.get('modello_ai') or 'claude-sonnet-5-5')
VOCE = str(E('VOCE') or P.get('voice_id') or '').strip()
VOCE_MOD = str(P.get('voice_model_id') or 'eleven_multilingual_v2')
LINGUA = str(P.get('language') or 'it')[:2]
NOME = str(P.get('channel_name') or P.get('channel_id') or 'canale')
MIN_SEC_YT = 480
T0 = time.time()


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def num(x, d=0.0):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return d


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('comando fallito: ' + ' '.join(map(str, cmd))[:300] + '\n' + r.stderr[-1500:])
    return r.stdout


def durata(p):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).strip())


def http(url, data=None, headers=None, timeout=900):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        return json.loads(r.read().decode() or '{}')


def esito(e):
    log('esito:', json.dumps(e, ensure_ascii=False)[:600])
    json.dump(e, open(os.path.join(ROOT, 'esito_video.json'), 'w'), ensure_ascii=False)


# ============================================================ 1) COPIONE
MODELLI = """luogo {luogo, insegna, azione: felice|preoccupato|stupito|lavora|festa, clienti: 0-5, testo} = il protagonista nel suo locale (scena di storia)
prezzo {oggetto, prezzo: "20 €", nuovo_prezzo: "22 €" (facoltativo), nota} = un prodotto grande con il cartellino del prezzo
fette {titolo, totale: 20, totale_testo: "20 €", fette: [{nome, valore, testo: "3,60 €"}], evidenzia: indice della fetta del guadagno} = dove vanno i soldi (ciambella + legenda), max 6 fette, i valori sommano al totale
formula {titolo, a: "3.000 €", op: "÷"|"×"|"−"|"+", b: "9,40 €", risultato: "320 magliette", nota} = un calcolo passo passo
conteggio {oggetto, icone: 1-60, testo: "13 al giorno"} = tanti oggetti che si riempiono + numero grande
pareggio {titolo, fissi: 3000, margine: 9.4, nuovo_margine (facoltativo), unita: "magliette vendute", oggetto, perdita: true/false, guadagno: true/false} = grafico del punto di pareggio (fissi/margine = pareggio)
mesi {titolo, valori: [12 numeri], evidenzia: [numeri dei mesi 1-12], nota} = barre dei 12 mesi
confronto {titolo, a: {titolo, valore, oggetto}, b: {titolo, valore, oggetto}, vincitore: "a"|"b"|""} = due opzioni a confronto (oggetto SEMPRE compilato e coerente con il suo titolo: scarpe per un negozio di scarpe, mai il caffe' per tutto)
lista {titolo, voci: [max 6 frasi brevi]} = foglio con le spunte
costi {voci: [{nome, valore, testo}], totale, periodo: "al mese"} = costi fissi che spuntano intorno al protagonista preoccupato (max 6)
domanda {testo (max 30 caratteri), emozione: stupito|preoccupato|felice|calmo, scuro: true/false} = protagonista grande con fumetto (gancio, colpo di scena)
bilancia {titolo, sinistra, destra, pende: sinistra|destra} = due cose sulla bilancia
calendario {titolo, giorni: 1-31, testo} = mese con i giorni accesi
soldi {centro: "8.000 €", destinazioni: [max 4 nomi]} = i soldi che escono verso chi li riceve
cruscotto {titolo, voci: [{nome, valore: 0-1}]} = indicatori da tenere d'occhio (max 4)
timbro {oggetto, testo: "PERDITA", colore: rosso|verde, nota} = timbro grande
andamento {titolo, valori: [numeri], etichette: [testi], colore: verde|rosso} = linea che sale o scende
persone {n: 1-9, azione: fila|escono|entrano, escono: quanti, testo} = clienti
orologio {ore: 1-16, piene: quante, testo} = ore della giornata piene/vuote
salvadanaio {direzione: riempie|svuota, testo} = risparmi che crescono o calano
leve {titolo, voci: [3-4 nomi], evidenzia: indice} = le leve per migliorare
riepilogo {titolo, voci: [max 4 frasi brevi]} = schede finali da ricordare
prossimo {luogo, insegna, oggetto, testo} = gancio al prossimo episodio"""


def claude(prompt, max_tokens=64000):
    """Streaming + ragionamento ridotto (come video_storia.py): i modelli 5.5 ragionano dentro max_tokens e senza
    streaming la risposta lunga arrivava VUOTA ('Expecting value'). Senza JSON si riprova (max 3 volte)."""
    d = {'model': MODELLO, 'max_tokens': max_tokens, 'stream': True, 'messages': [{'role': 'user', 'content': prompt}]}
    if 'sonnet-5' in MODELLO:
        d.update(thinking={'type': 'between_tools'}, output_config={'effort': 'low'})
    elif re.search(r'(opus|fable|mythos)-5', MODELLO):
        d['output_config'] = {'effort': 'low'}
    for k in range(3):
        try:
            req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(d).encode(),
                                         headers={'content-type': 'application/json', 'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
            pezzi, fine, uso = [], '', {}
            with urllib.request.urlopen(req, timeout=600) as r:
                for riga in r:
                    riga = riga.decode('utf-8', 'ignore').strip()
                    if not riga.startswith('data:'):
                        continue
                    try:
                        ev = json.loads(riga[5:].strip())
                    except Exception:
                        continue
                    t = ev.get('type')
                    if t == 'content_block_delta' and (ev.get('delta') or {}).get('type') == 'text_delta':
                        pezzi.append(ev['delta'].get('text', ''))
                    elif t == 'message_start':
                        uso = dict((ev.get('message') or {}).get('usage') or {})
                    elif t == 'message_delta':
                        fine = (ev.get('delta') or {}).get('stop_reason') or fine
                        uso.update({a: b for a, b in (ev.get('usage') or {}).items() if isinstance(b, int)})
                    elif t == 'error':
                        raise RuntimeError('Claude: ' + json.dumps(ev.get('error'))[:200])
            CO.registra('claude', MODELLO, uso)
            testo = ''.join(pezzi)
            log('Claude:', len(testo), 'caratteri, fine:', fine)
            if '{' in testo:
                return testo
            log('risposta senza JSON, riprovo:', testo[:200])
        except Exception as e:
            log('Claude non risponde, riprovo:', str(e)[:200])
        time.sleep(20 * (k + 1))
    raise RuntimeError('Claude non risponde (nessun copione): niente spesa per la voce')


def json_da(testo):
    m = re.search(r'\{.*\}', testo, re.S)
    s = m.group(0) if m else testo
    try:
        return json.loads(s)
    except Exception:
        from json_repair import repair_json
        return json.loads(repair_json(s))


def copione():
    f = os.path.join(LAV, 'copione.json')
    if os.path.exists(f):
        log('copione ripreso dal giro precedente'); return json.load(open(f))
    titolo = str(RIGA.get('titolo_italiano') or RIGA.get('titolo_originale') or P.get('titolo') or '').strip()
    attivita, lezione = str(RIGA.get('attivita') or '').strip(), str(RIGA.get('lezione') or '').strip()
    dmin, dmax = num(P.get('durata_min_minuti'), 8.5), num(P.get('durata_max_minuti'), 9.5)
    car = int((dmin + dmax) / 2 * 60 * 15.5)   # caratteri di voce per la durata voluta (circa 15,5 caratteri al secondo)
    prompt = f"""Sei l'autore del canale YouTube "{NOME}" ({P.get('niche') or ''}). Pubblico: {P.get('target_audience') or 'titolari di attivita, commercianti, chi vuole aprirne una'}.
Stile: {P.get('narrative_angle') or 'storytelling a cartoni animati: una storia con un protagonista e i suoi numeri veri, spiegati in modo semplice, utile e divertente'}.
Lingua: {'italiano' if LINGUA == 'it' else LINGUA}, dai del tu allo spettatore.

PUNTATA: "{titolo}"
Attivita protagonista: {attivita or 'quella del titolo'}. Concetti da insegnare: {lezione or 'margine, costi fissi, punto di pareggio'}.

Scrivi la puntata completa per un video di {dmin:g}-{dmax:g} minuti: in totale circa {int(car * 1.2)} caratteri di testo parlato (non meno di {car}: conta i caratteri, i testi brevi rendono il video troppo corto).
REGOLE DEL TESTO
- Inizia con un gancio forte nei primi 10 secondi (un problema o un numero che sorprende), niente saluti, niente "in questo video".
- Una storia con UN protagonista (nome italiano) e la sua attivita; ogni concetto spiegato con i suoi numeri, poi con 1-2 esempi DIVERSI di altre attivita (mai ripetere lo stesso esempio).
- Insegna cosa guardare, cosa non guardare e come si calcola, passo passo; fai pensare chi ha un'attivita.
- Numeri realistici e coerenti fra loro (ricontrolla ogni calcolo: totali, divisioni, percentuali). Sono esempi: non presentarli come dati ufficiali.
- Nel testo parlato TUTTI i numeri scritti in lettere (es. "tremila euro", "nove euro e quaranta", "il trenta per cento"), mai cifre.
- Frasi brevi, ritmo vivace, qualche domanda allo spettatore, una battuta ogni tanto. Chiudi con un riassunto e un gancio al prossimo episodio, poi "Iscriviti".
- 32-40 scene, ognuna da 220 a 330 caratteri.
INQUADRATURE (il video e' tutto disegnato: ogni scena ha 2-4 inquadrature, una nuova ogni 4-6 secondi di voce)
- La prima inquadratura di ogni scena ha "parola": "". Le altre hanno "parola": una parola ESATTA del testo della scena (la prima volta che compare) in cui l'inquadratura deve partire.
- Modelli disponibili (tipo e parametri p):
{MODELLI}
- Usa tutti i modelli nel corso del video, alterna storia (luogo, domanda, persone) e grafici; mai due inquadrature uguali di fila; i numeri a schermo con le cifre in formato italiano (1.500 €, 9,40 €).
- I numeri nei grafici devono essere gli STESSI detti dalla voce.
PROTAGONISTA: definiscilo una volta: {{"nome", "capelli": marco|giulia|short|long|curly|bun|bald|cap|chef, "colore_capelli": "#hex", "pelle": chiara|media|scura, "maglia": "#hex", "grembiule": "#hex" o "", "occhiali": true/false}}.
CAPITOLI: in 6-9 scene metti "capitolo": "titolo breve del capitolo" (la prima scena NO, e' il gancio).
COPERTINA: "copertina": {{"righe": [3 righe brevi e grammaticalmente corrette, max 16 caratteri l'una, maiuscole CON gli accenti (CAFFÈ, PERCHÉ), es. "400 MAGLIETTE", "VENDUTE...", "E IN ROSSO"], "emozione": stupito|preoccupato, "oggetto": "...", "prezzo": "20 €", "fondo": scuro|chiaro}}.
COPERTINA AI: "copertina_ai": {{"valore_sx": quanto COSTA (prezzo di costo, es. "0,10 €", "2,40 €", "18 €/ORA"), "valore_dx": a quanto LO VENDI (es. "1,20 €", "8 €", "40 €/MESE"), "oggetto_sx": "in inglese: cosa disegnare dal lato del costo (es. a small heap of pizza ingredients: flour bag, tomato, mozzarella)", "oggetto_dx": "in inglese: cosa disegnare dal lato della vendita (es. a big hot margherita pizza on a wooden peel)", "domanda": ["prima riga, max 18 caratteri, maiuscole con accenti", "seconda riga max 18 caratteri"] (la domanda che fa cliccare, es. ["E ALLORA PERCHÉ", "IL BAR CHIUDE?"])}}. I valori devono essere numeri veri del video.
YOUTUBE: "descrizione" (3-5 frasi che invogliano, senza capitoli), "tag" (12-18 tag in italiano), "oggetto" (l'oggetto simbolo della puntata, es. "caffe", "pizza").

Rispondi SOLO con il JSON:
{{"titolo": "{titolo}", "protagonista": {{...}}, "oggetto": "...", "copertina": {{...}}, "copertina_ai": {{...}}, "descrizione": "...", "tag": [...],
 "scene": [{{"testo": "...", "capitolo": "", "inquadrature": [{{"parola": "", "tipo": "luogo", "p": {{...}}}}, ...]}}, ...]}}"""
    c = json_da(claude(prompt))
    tot = sum(len(s.get('testo', '')) for s in c.get('scene', []))
    log('copione:', len(c.get('scene', [])), 'scene,', tot, 'caratteri')
    if tot < car * .9:   # troppo corto: si chiede di allungare (stesse regole)
        c2 = json_da(claude(prompt + f'\n\nATTENZIONE: una versione precedente era troppo corta ({tot} caratteri). Scrivila di almeno {int(car * 1.2)} caratteri, con piu\' scene ed esempi.'))
        if sum(len(s.get('testo', '')) for s in c2.get('scene', [])) > tot:
            c = c2
    c['titolo'] = titolo or c.get('titolo')
    json.dump(c, open(f, 'w'), ensure_ascii=False, indent=1)
    return c


def pulisci(c):
    """Controlli senza AI: tipi esistenti, prima inquadratura senza parola, numeri in cifre tolti dalla voce, scene vuote via."""
    tipi = set(re.findall(r"^TPL\.(\w+) =", open(os.path.join(MOT, 'tpl.js')).read(), re.M))
    out = []
    for s in c.get('scene', []):
        testo = re.sub(r'\s+', ' ', str(s.get('testo') or '')).strip()
        if not testo:
            continue
        inq = [q for q in (s.get('inquadrature') or []) if isinstance(q, dict)]
        for q in inq:
            if q.get('tipo') not in tipi:
                log('modello sconosciuto', q.get('tipo'), '-> domanda'); q['tipo'] = 'domanda'; q['p'] = {'testo': ''}
        if not inq:
            inq = [{'parola': '', 'tipo': 'domanda', 'p': {}}]
        inq[0]['parola'] = ''
        out.append({'testo': testo, 'capitolo': str(s.get('capitolo') or '').strip(), 'inquadrature': inq})
    c['scene'] = out
    if re.search(r'\d', ' '.join(s['testo'] for s in out)):
        log('ATTENZIONE: cifre nel testo parlato (la voce potrebbe leggerle male):', [s['testo'][:60] for s in out if re.search(r'\d', s['testo'])][:3])
    return c


# ============================================================ 2) VOCE
def voce(i, testo, prima, dopo):
    f = os.path.join(LAV, f'voce_{i:03d}.mp3')
    if os.path.exists(f) and os.path.exists(f[:-4] + '.json'):
        return f
    vel = max(.7, min(1.2, num(P.get('voice_speed'), 1.0) or 1.0))
    for k in range(4):
        try:
            j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_128',
                     {'text': testo, 'model_id': VOCE_MOD, 'previous_text': prima[-400:], 'next_text': dopo[:400],
                      'voice_settings': {'stability': .5, 'similarity_boost': .75, 'speed': vel}}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=180)
            open(f, 'wb').write(base64.b64decode(j['audio_base64'])); json.dump(j.get('alignment') or {}, open(f[:-4] + '.json', 'w'))
            CO.registra('elevenlabs', VOCE_MOD, crediti=len(testo) * (0.5 if ('flash' in VOCE_MOD or 'turbo' in VOCE_MOD) else 1))
            return f
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(5 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


def parole(al, atempo, lead):
    out, cur, a, b = [], '', None, None
    for ch, s, e in zip(al.get('characters', []), al.get('character_start_times_seconds', []), al.get('character_end_times_seconds', [])):
        if ch.isspace():
            if cur: out.append((cur, a, b)); cur = ''
            continue
        if not cur: a = s
        cur += ch; b = e
    if cur: out.append((cur, a, b))
    return [(w, round(lead + a / atempo, 3), round(lead + b / atempo, 3)) for w, a, b in out]


# ============================================================ 3) MONTAGGIO
def copertina_ai(pg, ca, ctx, cop):
    """Bozza disegnata (gratis) -> fal nano-banana-2/edit (~0,08 $) -> controllo delle scritte con Claude (1 riprova) -> banda con targa e domanda.
    Se qualcosa non va resta la copertina disegnata: mai una copertina con scritte sbagliate."""
    bozza = os.path.join(LAV, 'bozza_copertina.jpg')
    alto = __import__('datetime').date.today().toordinal() % 2 == 1   # 8 nov (MANO LIBERA): banda sopra a giorni alterni
    pg.evaluate('c => bozza_ai(c)', dict(ca, oggetto=ctx.get('oggetto'), alto=alto)); pg.wait_for_timeout(300)
    pg.screenshot(path=bozza, type='jpeg', quality=92)
    vs, vd = str(ca.get('valore_sx') or '').strip(), str(ca.get('valore_dx') or '').strip()
    prompt = ('Redesign this rough YouTube thumbnail draft for an Italian channel about how much businesses really earn, as a polished 2D cartoon / flat vector explainer thumbnail: '
              'clean thick dark outlines, bright friendly colours, soft gradients and subtle shadows, very readable on a phone, 16:9. Keep the same layout: red left half, green right half '
              'with a slightly diagonal split, a big glossy yellow-orange arrow from left to right, and a plain dark navy band across the ' + ('TOP' if alto else 'bottom') + ' 30% of the image. '
              f'LEFT (red): {ca.get("oggetto_sx") or "what it costs"}. RIGHT (green): {ca.get("oggetto_dx") or "what it is sold for"}. '
              f'The ONLY texts in the image, spelled EXACTLY like this: "COSTA" at the top left and "LO VENDI" at the top right, both WHITE with a dark outline; '
              f'the values "{vs}" (left) and "{vd}" (right) in bold rounded YELLOW lettering with a dark outline, small sparkles around the right value. '
              'No other words, letters or labels anywhere (no English words, no brand names). The dark bottom band must stay COMPLETELY EMPTY. No logo, no watermark.')
    H = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
    rif = 'data:image/jpeg;base64,' + base64.b64encode(open(bozza, 'rb').read()).decode()
    for tentativo in range(2):
        inv = http('https://queue.fal.run/fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': [rif], 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1}, H)
        CO.registra('fal', 'fal-ai/nano-banana-2/edit', dollari=0.08, nota='copertina AI')
        for _ in range(150):
            time.sleep(4)
            if http(inv['status_url'], headers=H).get('status') == 'COMPLETED':
                break
        url = http(inv['response_url'], headers=H)['images'][0]['url']
        img = os.path.join(LAV, f'copertina_ai_{tentativo}.jpg')
        with urllib.request.urlopen(url, timeout=120) as r:
            open(img, 'wb').write(r.read())
        # controllo scritte (Claude guarda l'immagine): solo COSTA, LO VENDI e i due valori, scritti giusti
        dom = ('Look at this thumbnail image. Answer ONLY with JSON {"ok": true|false, "motivo": "..."}. ok = true ONLY if: the texts "COSTA", "LO VENDI", '
               f'"{vs}" and "{vd}" are present and spelled exactly, there is NO other readable word or label anywhere, and the dark band is empty.')
        j = http('https://api.anthropic.com/v1/messages', {'model': MODELLO, 'max_tokens': 300, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(open(img, 'rb').read()).decode()}},
            {'type': 'text', 'text': dom}]}]}, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        CO.registra('claude', MODELLO, j.get('usage'), nota='controllo copertina AI')
        t = ''.join(b.get('text', '') for b in j.get('content', []) if b.get('type') == 'text')
        esito_c = json_da(t) if '{' in t else {'ok': False, 'motivo': t[:100]}
        log(f'copertina AI tentativo {tentativo + 1}:', 'OK' if esito_c.get('ok') else 'scritte da rifare (' + str(esito_c.get('motivo'))[:120] + ')')
        if esito_c.get('ok'):
            d = (ca.get('domanda') or ['', '']) + ['', '']
            pg.goto('file://' + os.path.join(MOT, 'video.html')); pg.wait_for_timeout(300)
            pg.evaluate('([a, b, c, e]) => finale_ai(a, b, c, e)', ['file://' + img, d[0], d[1], alto]); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(700)
            pg.screenshot(path=cop, type='jpeg', quality=92)
            log('copertina AI pronta (COSTA / LO VENDI + targa)')
            return
    raise RuntimeError('scritte sbagliate anche al secondo tentativo')


def monta(c, order, ctx):
    from playwright.sync_api import sync_playwright
    os.makedirs(os.path.join(LAV, 'scene'), exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={'width': 1920, 'height': 1080})
        msg = []; pg.on('console', lambda m: msg.append(m.text))
        pg.goto('file://' + os.path.join(MOT, 'video.html'))
        tl = pg.evaluate('([o, c]) => init(o, c)', [order, ctx])
        json.dump(tl, open(os.path.join(LAV, 'timeline.json'), 'w'), ensure_ascii=False)
        log('inquadrature:', len(tl), '| media', round(sum(x[4] for x in tl) / max(1, len(tl)), 1), 's')
        pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(300)
        files = []
        for i, o in enumerate(order):
            fin = os.path.join(LAV, 'scene', f's{i:03d}.mp4')
            files.append(fin)
            if os.path.exists(fin):
                continue
            tmp = fin[:-4] + '.tmp.mp4'; n = round(o['dur'] * 30)
            ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-',
                                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', '30', tmp], stdin=subprocess.PIPE)
            for fr in range(n):
                pg.evaluate(f"draw({o['off'] + fr / 30:.4f})")
                ff.stdin.write(pg.screenshot(type='jpeg', quality=90))
            ff.stdin.close()
            if ff.wait():
                raise RuntimeError('montaggio della scena %d non riuscito' % i)
            os.replace(tmp, fin)
            if i % 5 == 0:
                log('scena', i + 1, 'di', len(order))
        cop = os.path.join(ROOT, 'copertina.jpg')
        pg.set_viewport_size({'width': 1280, 'height': 720})
        pg.evaluate('([c, x]) => copertina(c, x)', [c.get('copertina') or {}, ctx]); pg.wait_for_timeout(200)
        pg.screenshot(path=cop, type='jpeg', quality=92)
        if str(P.get('copertina_ai') or '').strip().upper() == 'SI' and c.get('copertina_ai'):   # 8 nov (Giorgio): stile COSTA / LO VENDI rifinito con l'AI
            try:
                copertina_ai(pg, c['copertina_ai'], ctx, cop)
            except Exception as e:
                log('copertina AI non riuscita, resta quella disegnata:', str(e)[:200])
        br.close()
    errori = [m for m in msg if m.startswith('errore')]
    if errori:
        log('inquadrature con errore (sostituite):', errori[:10])
    lista = os.path.join(LAV, 'lista.txt')
    open(lista, 'w').write(''.join(f"file '{f}'\n" for f in files))
    muto = os.path.join(LAV, 'muto.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto])
    return muto, cop, tl


SUONI = {'prezzo': 'cassa', 'fette': 'monete', 'formula': 'cassa', 'conteggio': 'crescita', 'pareggio': 'crescita', 'soldi': 'monete', 'costi': 'monete',
         'timbro': 'calo', 'salvadanaio': 'monete', 'riepilogo': 'campana', 'prossimo': 'campana', 'persone': 'folla', 'orologio': 'tempo'}


def audio(order, tl, atempo, lead, tot):
    ins, fl, n = [], [], 0
    for o in order:
        ins += ['-i', o['voce']]
        fl.append(f"[{n}:a]atempo={atempo:.4f},adelay={int(lead * 1000)}|{int(lead * 1000)},apad,atrim=0:{o['dur']},aformat=sample_rates=44100:channel_layouts=stereo[v{n}]"); n += 1
    fl.append(''.join(f'[v{i}]' for i in range(n)) + f'concat=n={n}:v=0:a=1[voce]')
    mus = [os.path.join(QUI, 'libreria_musica', f) for f in sorted(os.listdir(os.path.join(QUI, 'libreria_musica'))) if f.startswith('curiosita') and f.endswith('.mp3')][:4]
    for m in mus:
        ins += ['-stream_loop', '-1', '-i', m]
    fl.append(''.join(f'[{n + i}:a]' for i in range(len(mus))) + f'concat=n={len(mus)}:v=0:a=1[mm]'); n += len(mus)
    fl.append(f"[mm]atrim=0:{tot},volume={num(P.get('musica_volume'), 0.11) or 0.11},afade=t=in:d=1,afade=t=out:st={tot - 3}:d=3,aformat=sample_rates=44100:channel_layouts=stereo[mus]")
    mix, j, ultimo = ['[voce]', '[mus]'], 0, -9
    for sid, tipo, par, g, d in tl:
        snd = SUONI.get(tipo)
        f = os.path.join(QUI, 'libreria_mappe', 'suoni', f'{snd}.mp3') if snd else ''
        if not snd or not os.path.exists(f) or g - ultimo < 6:
            continue
        ultimo = g; ms = int((g + .5) * 1000)
        ins += ['-i', f]; fl.append(f"[{n}:a]atrim=0:2.5,volume=0.35,adelay={ms}|{ms},aformat=sample_rates=44100:channel_layouts=stereo[e{j}]"); mix.append(f'[e{j}]'); n += 1; j += 1
    fl.append(''.join(mix) + f'amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[a]')
    out = os.path.join(LAV, 'audio.m4a')
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(fl), '-map', '[a]', '-t', f'{tot:.3f}', '-c:a', 'aac', '-b:a', '192k', out])
    return out


# ============================================================ 4) YOUTUBE
def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60).read())['access_token']


def metti_in_playlist(vid, titolo, tok):
    """Colonna playlist:  Nome playlist: parola1, parola2 || Altra playlist  (senza parole = tutti i video). Crea la playlist se manca."""
    regole = [x.strip() for x in str(P.get('playlist') or '').split('||') if x.strip()]
    scelte = [n.strip()[:150] for n, _, p in (r.partition(':') for r in regole)
              if n.strip() and (not p.strip() or any(w.strip().lower() in titolo.lower() for w in p.split(',') if w.strip()))]
    if not scelte:
        return 'nessuna playlist nel foglio (colonna playlist)'
    h = {'Authorization': 'Bearer ' + tok}
    try:
        tutte = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', headers=h).get('items', [])
        esistenti = {it['snippet']['title'].strip().lower(): it['id'] for it in tutte}
        for nome in scelte:
            pid = esistenti.get(nome.lower())
            if not pid:
                pid = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', {'snippet': {'title': nome}, 'status': {'privacyStatus': 'public'}}, h)['id']
                time.sleep(8)
            http('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}}, h)
            log('playlist:', nome)
        return ''
    except Exception as e:
        return 'playlist non aggiornata: ' + str(e)[:150]


def carica_youtube(path, titolo, descr, tags, cop):
    tok = token()
    status = {'privacyStatus': P.get('privacy') or 'public', 'selfDeclaredMadeForKids': False, 'containsSyntheticMedia': False}
    if P.get('pubblica_il') and status['privacyStatus'] == 'public':
        status['privacyStatus'] = 'private'; status['publishAt'] = P['pubblica_il']
    snip = {'title': titolo[:100], 'description': descr, 'tags': tags, 'categoryId': str(P.get('youtube_category_id') or '27'), 'defaultLanguage': LINGUA, 'defaultAudioLanguage': LINGUA}
    hd = {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Length': str(os.path.getsize(path)), 'X-Upload-Content-Type': 'video/mp4'}
    if DICH:   # 8 nov: dichiarazione dentro il caricamento (niente modifica dopo da 50 unita')
        sess = DICH.sessione('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', {'snippet': snip, 'status': status}, hd, 120)
    else:
        with urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                                                           data=json.dumps({'snippet': snip, 'status': status}).encode(), method='POST', headers=hd), timeout=120) as r:
            sess = r.headers['Location']
    for k in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(sess, data=open(path, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'video/mp4'}), timeout=1800) as r:
                ris = json.loads(r.read().decode()); vid = ris['id']
            break
        except Exception as e:
            log('upload, riprovo:', str(e)[:150]); time.sleep(15 * (k + 1)); tok = token()
    else:
        raise RuntimeError('caricamento su YouTube non riuscito')
    if DICH:
        try:
            DICH.nessuna_promozione(vid, tok, ris)
        except Exception:
            pass
    nota = metti_in_playlist(vid, titolo, tok)   # 8 nov (Giorgio): ogni video va in una playlist
    try:
        urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', data=open(cop, 'rb').read(), method='POST',
                                                      headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'image/jpeg'}), timeout=120).read()
    except Exception as e:
        nota = (nota + ' | ' if nota else '') + 'copertina non caricata: ' + str(e)[:150]
    return vid, nota


# ============================================================ MAIN
def main():
    c = pulisci(copione())
    scene = c['scene']
    # voce
    files = []
    for i, s in enumerate(scene):
        files.append(voce(i, s['testo'], ' '.join(x['testo'] for x in scene[:i]), ' '.join(x['testo'] for x in scene[i + 1:])))
    nat = sum(durata(f) for f in files); car = sum(len(s['testo']) for s in scene)
    obiettivo = num(P.get('voce_ritmo'), 16.5) or 16.5   # caratteri al secondo voluti
    atempo = max(1.0, min(1.15, obiettivo / (car / nat)))
    LEAD, TAIL = .3, .5
    order, off = [], 0.0
    for i, (s, f) in enumerate(zip(scene, files)):
        d = round(LEAD + durata(f) / atempo + TAIL, 3)
        W = parole(json.load(open(f[:-4] + '.json')), atempo, LEAD)
        sub, cur = [], []
        for w in W:
            cur.append(w)
            if len(cur) >= 7 or w[0][-1] in '.?!:' or (w[0][-1] == ',' and len(cur) >= 3):
                sub.append({'txt': ' '.join(x[0] for x in cur), 'a': cur[0][1], 'b': cur[-1][2]}); cur = []
        if cur:
            sub.append({'txt': ' '.join(x[0] for x in cur), 'a': cur[0][1], 'b': cur[-1][2]})
        order.append({'id': f's{i}', 'off': round(off, 3), 'dur': d, 'voce': f, 'words': [[w, a] for w, a, b in W], 'sub': sub,
                      'capitolo': s.get('capitolo') or '', 'shots': s['inquadrature']})
        off += d
    tot = round(off, 3)
    log(f'voce: {car} caratteri, {nat:.0f} s naturali, atempo {atempo:.3f}, video {tot / 60:.1f} minuti')
    if tot < MIN_SEC_YT and not PROVA:
        log(f'ATTENZIONE: video di {tot / 60:.1f} minuti, sotto gli 8 minuti')
    ctx = {'protagonista': c.get('protagonista') or {}, 'attivita': str(RIGA.get('attivita') or ''), 'oggetto': c.get('oggetto') or ''}
    muto, cop, tl = monta(c, [{k: v for k, v in o.items() if k != 'voce'} for o in order], ctx)
    aud = audio(order, tl, atempo, LEAD, tot)
    base = os.path.join(LAV, 'base.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', aud, '-map', '0:v', '-map', '1:a', '-c', 'copy', '-shortest', base])
    finale = os.path.join(ROOT, 'video_cartoni.mp4')
    # pulsante iscriviti con i suoni: dentro la prima inquadratura "luogo"/"prezzo" dopo il minuto e mezzo (centro dello schermo piu' libero)
    sec = next((g + 1 for sid, tipo, par, g, d in tl if g > 90 and d >= 5 and tipo in ('prezzo', 'luogo', 'domanda', 'persone')), num(P.get('subscribe_overlay_second'), 100))
    if not ISC.applica(base, finale, dict(P, subscribe_overlay_second=sec), os.path.join(LAV, 'isc'), short=False, log=log, enc=['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19']):
        shutil.copy(base, finale)
    dur_v = durata(finale)
    # descrizione: titolo, testo, capitoli, chiusura
    titolo = str(c.get('titolo') or '')[:100]
    cap, t_ = ['00:00 ' + (str(scene[0]['testo']).split('.')[0][:40] or 'Intro')], 0.0
    for o in order:
        if o['capitolo'] and o['off'] >= 10:
            cap.append(f"{int(o['off'] // 60):02d}:{int(o['off'] % 60):02d} {o['capitolo']}")
    descr = '\n\n'.join(x for x in [titolo, str(c.get('descrizione') or '').strip(), '\n'.join(cap) if len(cap) >= 3 else '',
                                     'I numeri del video sono esempi per spiegare i concetti: ogni attivita\' ha i suoi.', str(P.get('youtube_description_footer') or '').strip()] if x)
    descr = DESCR.con_titolo(titolo, descr)
    tags = DESCR.tag_con_titolo(titolo, [str(x) for x in (c.get('tag') or [])] + [x.strip() for x in str(P.get('youtube_default_tags') or '').split(',') if x.strip()])
    tag_txt = ', '.join(tags) if isinstance(tags, list) else str(tags)
    playlist = str(P.get('playlist') or '').split('||')[0].split(':')[0].strip()
    testo_cop = ' '.join((c.get('copertina') or {}).get('righe') or [])
    log('FATTO:', finale, round(dur_v / 60, 1), 'minuti |', CO.testo() if hasattr(CO, 'testo') else '')
    extra = {'titolo': titolo, 'descrizione': descr, 'tag': tag_txt, 'playlist': playlist, 'testo_copertina': testo_cop,
             'minuti_video': round(dur_v / 60, 1), 'minuti_lavoro': round((time.time() - T0) / 60, 1)}
    if PROVA or dur_v < MIN_SEC_YT:
        esito({'stato': 'PROVA OK', **extra}); return
    if CARICA and E('YT_REFRESH_TOKEN'):
        vid, nota = carica_youtube(finale, titolo, descr, tags if isinstance(tags, list) else tag_txt.split(', '), cop)
        esito({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'pubblica_il': P.get('pubblica_il') or '', 'errore': nota, **extra})
    else:
        if CARICA:
            log('carica = SI ma manca la chiave YouTube del canale: preparo il caricamento a mano')
        MAN.prepara(finale, cop, titolo, ROOT)
        esito({'stato': 'CREATO', **extra})


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback; traceback.print_exc()
        esito({'stato': 'ERRORE', 'errore': str(e)[:400]})
        raise
