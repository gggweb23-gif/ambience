#!/usr/bin/env python3
"""
MULTICHANNEL - "Video Storia" (canale storia dei paesi, stile Rome Unscrolled / Genius History).
Dal titolo al video finito, tutto da solo:
  1) copione + regia visiva (Claude)          4) sfondi a cartone (Fal) + kit personaggi (repo kit_storia/)
  2) voce scena per scena (ElevenLabs)         5) montaggio: cambio immagine ogni ~3 s, transizioni a scatto
  3) clip e foto (Pexels)                       6) video_storia.mp4 (+ copione.json, personaggi_mancanti.txt)
Tipi di "pezzo": cartone (sfondo + personaggio che cambia posa), pexels_video, pexels_foto,
carta (frase chiave battuta a macchina su texture), scheda (personaggio + nome), mappa (zoom sul paese).
Variabili: TITOLO, LINGUA, VOCE, MINUTI, MAX_MINUTI, MODELLO_AI, MUSICA_URL, MUSICA_VOL, PROVA (SI = video di ~1 minuto)
Chiavi: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY, FAL_KEY
"""
import base64, json, math, os, random, re, shutil, subprocess, sys, threading, time, traceback, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 24
T_TR = 0.0                                   # nessuna transizione: taglio netto tra le immagini
ROOT = os.getcwd()
LAV = os.path.join(ROOT, 'lavoro_storia')
KIT = os.path.join(ROOT, 'kit_storia')
FONT = os.path.join(ROOT, 'font')
GEO = os.path.join(ROOT, 'geo')
E = os.environ.get
TITOLO = E('TITOLO', 'Tutta la storia dell\'Iran').strip()
LINGUA = E('LINGUA', 'it').strip() or 'it'
VOCE = E('VOCE', 'glnsgBC77wt5zOYU0szz').strip()
MINUTI = float(E('MINUTI', '13') or 13)
MAX_MINUTI = float(E('MAX_MINUTI', '25') or 25)   # oltre questa durata il copione condensa l'originale
PROVA = E('PROVA', 'NO').strip().upper() == 'SI'
MODELLO_AI = E('MODELLO_AI', 'claude-sonnet-5-5').strip()
LINK = E('LINK_COMPETITOR', '').strip()      # video da copiare (titolo, testo e copertina)
INK = (29, 26, 23)
random.seed(TITOLO)


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('comando fallito: ' + ' '.join(map(str, cmd))[:300] + '\n' + r.stderr[-1500:])
    return r.stdout


def durata(p):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]).strip())


def http(url, data=None, headers=None, metodo=None, timeout=180, raw=False):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def scarica(url, path, tentativi=4):
    for k in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'})
            with urllib.request.urlopen(req, timeout=180) as r, open(path, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if os.path.getsize(path) > 2000:
                return path
        except Exception as e:
            log('download fallito', str(e)[:120]); time.sleep(3 * (k + 1))
    raise RuntimeError('impossibile scaricare ' + url)


# ============================================================ 0) VIDEO DEL COMPETITOR
def id_video(link):
    m = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})', link or '')
    return m.group(1) if m else ''


def competitor():
    """Titolo, testo parlato e copertina del video originale. SICUREZZA: senza link valido o senza testo originale il video NON parte."""
    vid = id_video(LINK)
    if not vid:
        raise RuntimeError('STOP: manca il link del video competitor (o non e\' un link YouTube valido). '
                           'Questo canale copia solo i competitor: nessun video creato, nessun costo.')
    c = {'id': vid, 'copertina': f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg'}
    try:
        urllib.request.urlopen(urllib.request.Request(c['copertina'], method='HEAD'), timeout=30)
    except Exception:
        c['copertina'] = f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'
    try:
        c['titolo'] = http('https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=' + vid)['title']
    except Exception as e:
        log('titolo originale non letto:', str(e)[:100])
    chiave_rapid = E('RAPIDAPI_KEY', '')
    if chiave_rapid:   # stesso servizio usato da n8n (youtube-transcript3 su RapidAPI): YouTube non lo blocca
        for k in range(3):
            try:
                j = http('https://youtube-transcript3.p.rapidapi.com/api/transcript?videoId=' + vid,
                         headers={'X-RapidAPI-Key': chiave_rapid, 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com'}, timeout=120)
                righe = j.get('transcript') or []
                testo = ' '.join(str(r.get('text', '')) for r in righe) if isinstance(righe, list) else str(righe)
                testo = re.sub(r'\s+', ' ', testo.replace('[Music]', ' ')).strip()
                if len(testo.split()) > 50:
                    c['testo'] = testo
                    log('testo originale:', len(testo.split()), 'parole (RapidAPI)')
                    return c
                log('RapidAPI: trascrizione vuota', json.dumps(j)[:200])
            except Exception as e:
                log('RapidAPI non riuscito:', str(e)[:150]); time.sleep(5)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            pezzi = YouTubeTranscriptApi().fetch(vid, languages=['en', 'en-US', 'it', 'es', 'fr', 'de'])
            testo = ' '.join(p.text for p in pezzi)
        except AttributeError:
            testo = ' '.join(p['text'] for p in YouTubeTranscriptApi.get_transcript(vid, languages=['en', 'en-US', 'it', 'es']))
        c['testo'] = re.sub(r'\s+', ' ', testo.replace('[Music]', ' ')).strip()
        log('testo originale:', len(c['testo'].split()), 'parole')
    except Exception as e:
        log('testo originale non letto:', str(e)[:150])
    if not c.get('testo'):
        raise RuntimeError('STOP: non riesco a leggere il testo del video competitor (RapidAPI e YouTube). '
                           'Nessun video creato, nessun costo per voce e immagini. Riprova piu\' tardi o con un altro video.')
    return c


# ============================================================ 1) COPIONE
def kit_disponibile():
    if not os.path.isdir(KIT):
        return []
    return sorted({f[:-len('_fermo.png')] for f in os.listdir(KIT) if f.endswith('_fermo.png')})


def copione(comp):
    kit = kit_disponibile()
    orig = comp.get('testo') or ''
    if PROVA and orig:   # prova: si copia solo il primo minuto circa dell'originale
        orig = ' '.join(orig.split()[:170])
    parole = 170 if PROVA else (int(len(orig.split()) * 1.05) if orig else int(MINUTI * 150))
    massimo = int(MAX_MINUTI * 150)
    condensa = parole > massimo
    parole = min(parole, massimo)
    lingua = {'it': 'italiano', 'en': 'English (US)'}.get(LINGUA, LINGUA)
    blocco_originale = ''
    if comp.get('titolo'):
        blocco_originale += f'''
VIDEO ORIGINALE DA COPIARE: "{comp['titolo']}".
- "titolo": e' la TRADUZIONE FEDELE al 100% del titolo originale in {lingua} (stessa struttura, stessi numeri e date, stesse parole in maiuscolo), adattata solo dove serve per suonare naturale.'''
    if orig:
        blocco_originale += f'''
- Il PARLATO deve COPIARE al 100% il testo originale qui sotto: stessi fatti, stesso ordine, stessi ganci, stesse domande, stessi numeri, stessa lunghezza.{' ECCEZIONE: l originale e troppo lungo, quindi CONDENSALO a circa ' + str(parole) + ' parole: stessi fatti principali, stesso ordine, stessi ganci e stesse domande, togli solo dettagli secondari ed esempi ripetuti.' if condensa else ''}
  Traducilo in {lingua} naturale e cambia solo piccole cose per non essere una copia identica (sinonimi, ordine delle parole, qualche frase unita o divisa). NON aggiungere contenuti{' e togli solo il secondario' if condensa else ' e NON toglierne'}.
TESTO ORIGINALE:
{orig[:60000]}
'''
    prompt = f"""Sei lo sceneggiatore e il regista di un canale YouTube di storia a cartone, nello stile di "Genius History" e "Rome Unscrolled".
Scrivi il video: "{TITOLO}". Lingua della voce e delle scritte: {lingua}. Lunghezza totale del parlato: circa {parole} parole.
{blocco_originale}
STILE DEL RACCONTO: dall'inizio della storia del paese fino a oggi, in ordine cronologico, con date precise, fatti veri, nomi veri.
Frasi brevi e concrete, ritmo da documentario coinvolgente, piccole domande e colpi di scena. Prima scena = gancio forte. Ultima scena = chiusura che fa riflettere.

REGIA VISIVA: ogni scena (20-40 parole di voce) ha 2-5 "visivi". RITMO (fondamentale per trattenere lo spettatore):
- primi 10 secondi (prime ~25 parole): ALMENO 5 visivi diversi, uno ogni 4-5 parole, mostrando tutti gli stili del canale (cartone, clip, scritta, mappa...);
- da 10 a 30 secondi: un visivo ogni ~7 parole;
- poi un visivo ogni 8-12 parole, MAI piu' di 12 parole sullo stesso visivo.
Il PRIMO visivo del video e' sempre un "cartone" con un personaggio.
SINCRONIA CON LA VOCE (FONDAMENTALE): ogni visivo ha il campo "frase" = 2-4 parole COPIATE IDENTICHE dal "testo" della scena, nel punto esatto in cui il visivo deve comparire. I visivi sono nello stesso ordine delle loro frasi nel testo, a distanza di almeno 4 parole l'uno dall'altro. Il primo visivo ha come frase le prime parole della scena.
- una "carta" compare quando la voce dice quella frase: il suo "testo" riprende parole DETTE in quella scena e la sua "frase" e' l'inizio di quelle parole nel testo;
- una "scheda" SOLO nella scena in cui quel personaggio viene NOMINATO dalla voce, con frase = il nome cosi' come detto;
- un "cartone" con un personaggio storico reale SOLO quando viene nominato (frase = il nome); quando non si nomina nessuno usa SEMPRE una figura generica della lista (soldato, contadino, nobile...) coerente con cio' che si dice: ogni cartone ha un personaggio;
- un "pexels" deve mostrare cio' che la voce dice in quel momento.
Tipi:
- "cartone": scena disegnata. Campi: "sfondo" (id di uno dei 6 sfondi), "personaggio" (SOLO uno di questa lista, oppure "" per nessuno): {', '.join(kit) or '(nessuno)'}; "reazione": true se a meta' il personaggio cambia posa (momento forte). Nella PRIMA scena il primo visivo e' un cartone con il campo "data" (es. "550 a.C.").
- "pexels_video": clip vera. Campo "q": ricerca Pexels in INGLESE, 2-4 parole concrete che diano immagini SENZA cose moderne: paesaggi naturali, montagne, deserti, rovine, monumenti antichi, oggetti antichi, monete, manoscritti, fuoco, cielo, mare, rievocazioni in costume. MAI persone di oggi, MAI citta' moderne (tranne nelle scene sul presente), MAI nomi di persone o eventi.
- "pexels_foto": foto vera. Campo "q" come sopra.
- DIDASCALIA (facoltativa, su "cartone", "pexels_video" o "pexels_foto"): campo "didascalia" = 2-6 parole chiave DETTE dalla voce in quel momento (es. "Ciro il Grande, 550 a.C.", "Il primo trattato della storia"). Compare su una striscia di carta strappata in basso, battuta a macchina. Usala con misura: circa 1 visivo ogni 6, mai su due visivi di fila.
- "carta": frase chiave scritta su carta. Campo "testo": max 8 parole, la frase piu' forte del momento.
- "scheda": presentazione di un personaggio storico. Campi "personaggio" (dalla lista) e "nome" (nome vero completo).
- "mappa": zoom sulla mappa del paese con titolo e date (usala UNA volta, nella seconda scena).
Proporzioni su tutto il video: circa 35% cartone, 30% pexels_video, 15% pexels_foto, 15% carta, 5% scheda+mappa. Mai due visivi uguali di fila.

FONDI DELLE CARTE: definisci 3 "fondi_carte" per le scritte e le schede: decorazioni a tema del video SOLO ai bordi (rovine, colonne, rami, motivi decorativi, skyline dell'epoca) e CENTRO VUOTO e uniforme. Ogni fondo: "id" (c1..c3) e "prompt_en" (20-35 parole: colori, cosa c'e' ai bordi, colore del centro; varia i colori tra i 3: es. carta antica, toni caldi, toni scuri).
"colori_carte": 2 colori esadecimali scuri ed eleganti coerenti con il tema (es. rosso persiano "#6b1e1e", blu lapislazzuli "#1d3557").
"font_carte": il carattere delle scritte, coerente con l'epoca PRINCIPALE del video: "antico" (Roma, Grecia, Persia, Egitto, antichita'), "medievale" (500-1700), "ottocento" (1700-1900), "macchina" (1900-1960, guerre), "moderno" (dal 1960 a oggi), "classico" (storia lunga di un paese dall'antichita' a oggi, se nessuno prevale).

SFONDI: definisci esattamente 6 sfondi a cartone (luoghi ed epoche chiave del paese, SENZA persone). Ogni sfondo: "id" (s1..s6) e "prompt_en" (descrizione in inglese del luogo e dell'epoca, 20-35 parole).

Rispondi SOLO con un JSON valido, senza testo prima o dopo:
{{"titolo": "...", "titolo_mappa": "nome del paese da scrivere sulla mappa, nella lingua del canale, es. IRAN", "paese_mappa": "nome del paese in inglese come in Natural Earth (es. Iran, India, Egypt, United States of America)",
 "date": "es. 550 a.C. – 2026", "texture": "pergamena|washi|stropicciata|giornale|papiro", "font_carte": "antico|medievale|ottocento|macchina|moderno|classico",
 "fondi_carte": [{{"id": "c1", "prompt_en": "..."}}], "colori_carte": ["#......", "#......"],
 "sfondi": [{{"id": "s1", "prompt_en": "..."}}],
 "scene": [{{"testo": "parlato della scena", "visivi": [{{"tipo": "cartone", "frase": "prime parole della scena", "sfondo": "s1", "personaggio": "...", "reazione": true, "data": "..."}}]}}],
 "copertina": {{"testo": "testo della copertina originale TRADOTTO al 100% (stesse parole, stesse date), MAIUSCOLO", "personaggio": "personaggio della lista che corrisponde alla figura principale della copertina originale, oppure ''"}},
 "personaggi_mancanti": ["figure che sarebbero servite ma non sono nella lista, es. 'Dario I re persiano'"]}}
Scegli la texture piu' coerente (washi per Giappone/Cina/Corea, papiro per Egitto/Mesopotamia, pergamena per antichita'/medioevo, giornale per 1800-1900, stropicciata per storia moderna)."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        raise RuntimeError('manca il secret ANTHROPIC_API_KEY')
    for k in range(3):
        try:
            contenuto = [{'type': 'text', 'text': prompt}]
            if comp.get('copertina'):
                contenuto.insert(0, {'type': 'image', 'source': {'type': 'url', 'url': comp['copertina']}})
                contenuto.insert(1, {'type': 'text', 'text': 'Questa sopra e\' la COPERTINA del video originale.'})
            r = http('https://api.anthropic.com/v1/messages', {
                'model': MODELLO_AI, 'max_tokens': 32000, 'messages': [{'role': 'user', 'content': contenuto}]},
                {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=900)
            testo = ''.join(b.get('text', '') for b in r.get('content', []))
            testo = testo[testo.find('{'): testo.rfind('}') + 1]
            c = json.loads(testo)
            assert c.get('scene') and c.get('sfondi')
            return c
        except Exception as e:
            log('copione non valido, riprovo:', str(e)[:200]); time.sleep(5)
    raise RuntimeError('copione non riuscito')


# ============================================================ 2) VOCE
def voce(i, testo):
    p = os.path.join(LAV, f'voce_{i:03d}.mp3')
    chiave = E('ELEVENLABS_API_KEY', '')
    if not chiave:   # prova senza chiave: silenzio della durata giusta
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', max(1.5, len(testo.split()) * .42), p])
        return p
    for k in range(4):
        try:
            # with-timestamps: stesso prezzo, in piu' restituisce QUANDO viene detta ogni lettera -> immagini a tempo con la voce
            j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_128',
                     {'text': testo, 'model_id': E('VOCE_MODELLO', 'eleven_multilingual_v2'),
                      'voice_settings': {'stability': .5, 'similarity_boost': .75}},
                     {'xi-api-key': chiave})
            open(p, 'wb').write(base64.b64decode(j['audio_base64']))
            json.dump(j.get('alignment') or {}, open(p[:-4] + '.json', 'w'))
            return p
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(4 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


def _norm(t):
    return re.sub(r'[^0-9a-zà-ÿ ]', ' ', (t or '').lower())


def trova(testo, frase, da=0):
    """Posizione (lettera) nel testo della scena dove inizia 'frase'. Prova la frase intera, poi le prime 3, 2 parole, poi la parola piu' lunga."""
    nt = _norm(testo); parole = _norm(frase).split()
    if not parole:
        return None
    prove = [' '.join(parole), ' '.join(parole[:3]), ' '.join(parole[:2])] + sorted([w for w in parole if len(w) > 4], key=len, reverse=True)[:2]
    for pr in prove:
        m = re.search(r'(?<![0-9a-zà-ÿ])' + r'\s+'.join(re.escape(w) for w in pr.split()), nt[da:])
        if m:
            return da + m.start()
    return None


def tempo_lettera(al, idx, testo, D):
    st = (al or {}).get('character_start_times_seconds') or []
    if st and len(st) == len(testo) and idx < len(st):
        return float(st[idx])
    return D * idx / max(1, len(testo))   # riserva: proporzionale


def nominato(testo, nome):
    """Vero se nel testo compare almeno una parola 'importante' del nome (es. Ciro, Dario, Khan)."""
    nt = ' ' + _norm(testo) + ' '
    return any(' ' + w + ' ' in nt for w in _norm(nome).split() if len(w) > 3 and w not in ('grande', 'primo', 'secondo', 'terzo', 'imperatore', 're', 'regina'))


# ============================================================ 3) PEXELS (con memoria: max ~180 ricerche l'ora)
# Ogni clip/foto viene CONTROLLATA da Claude (modello economico) guardando l'anteprima:
# scarta cose moderne, scritte, persone di oggi, cose fuori tema. Mai la stessa clip due volte.
_cache, _conti, _usati, _lock = {}, {'n': 0}, set(), threading.RLock()
VIETATE = ('firefighter', 'fire-fighter', 'jakarta', 'police', 'car', 'cars', 'traffic', 'phone', 'smartphone', 'laptop', 'computer',
           'office', 'selfie', 'tourist', 'tourists', 'christmas', 'birthday', 'party', 'card', 'greeting', 'happy', 'neon', 'logo',
           'text', 'sign', 'shopping', 'mall', 'airport', 'airplane', 'truck', 'bus', 'motorcycle', 'gym', 'fitness', 'model', 'fashion',
           'wedding', 'coffee', 'restaurant', 'supermarket', 'construction', 'vaccine', 'mask', 'covid', 'nowruz', 'football', 'soccer')
MODELLO_CONTROLLO = E('MODELLO_CONTROLLO', 'claude-haiku-4-5-20251001')


def pexels_cerca(tipo, q):
    k = (tipo, q.lower().strip())
    with _lock:
        if k in _cache:
            return _cache[k]
        if _conti['n'] >= 180:
            return []
        _conti['n'] += 1
    chiave = E('PEXELS_API_KEY', '')
    ris = []
    if chiave:
        base = 'https://api.pexels.com/videos/search' if tipo == 'video' else 'https://api.pexels.com/v1/search'
        try:
            j = http(base + '?' + urllib.parse.urlencode({'query': q, 'per_page': 20, 'orientation': 'landscape'}), headers={'Authorization': chiave})
            if tipo == 'video':
                for v in j.get('videos', []):
                    fs = [f for f in v.get('video_files', []) if 'mp4' in (f.get('file_type') or '') and (f.get('height') or 0) <= 1080]
                    fs.sort(key=lambda f: -(f.get('height') or 0))
                    if fs and (v.get('duration') or 0) >= 3:
                        ris.append({'url': fs[0]['link'], 'anteprima': v.get('image') or '', 'desc': (v.get('url') or '').lower()})
            else:
                for ph in j.get('photos', []):
                    ris.append({'url': ph['src'].get('large2x') or ph['src'].get('original'), 'anteprima': ph['src'].get('medium') or '',
                                'desc': ((ph.get('alt') or '') + ' ' + (ph.get('url') or '')).lower()})
        except Exception as e:
            log('Pexels:', q, str(e)[:120])
    ris = [r for r in ris if r['url'] and not any(re.search(r'(^|[^a-z])' + w + r'([^a-z]|$)', r['desc']) for w in VIETATE)]
    with _lock:
        _cache[k] = ris
    return ris


def controlla(candidati, q, contesto):
    """Claude guarda le anteprime e sceglie la prima adatta. -1 = nessuna."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave or not candidati:
        return 0 if candidati else -1
    cont = []
    for i, c in enumerate(candidati):
        cont += [{'type': 'text', 'text': f'Immagine {i}:'}, {'type': 'image', 'source': {'type': 'url', 'url': c['anteprima']}}]
    cont.append({'type': 'text', 'text': f"""Video di storia. La voce in questo momento dice: "{contesto[:400]}". Ricerca usata: "{q}".
Quale immagine e' adatta da mostrare? Deve sembrare coerente con l'epoca e il luogo raccontati.
SCARTA: persone moderne (vestiti di oggi, divise, caschi, occhiali da sole), auto, cellulari, cartelli o scritte leggibili, biglietti di auguri, oggetti di plastica, feste moderne, cose fuori tema.
VANNO BENE: paesaggi, montagne, deserti, rovine, monumenti antichi, musei, oggetti antichi, monete, manoscritti, fuoco, cieli, mare, rievocazioni in costume d'epoca.
Rispondi SOLO con il numero della prima immagine adatta, oppure -1 se nessuna va bene."""})
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_CONTROLLO, 'max_tokens': 10, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        m = re.search(r'-?\d+', ''.join(b.get('text', '') for b in r.get('content', [])))
        n = int(m.group()) if m else 0
        return n if -1 <= n < len(candidati) else 0
    except Exception as e:
        log('controllo Pexels saltato:', str(e)[:150])
        return 0


def pexels(tipo, q, contesto=''):
    for qq in (q, q + ' ancient', 'ancient ruins desert'):
        tutti = pexels_cerca(tipo, qq)   # ricerca FUORI dal lucchetto (prima qui si bloccava tutto)
        with _lock:
            cand = [c for c in tutti if c['url'] not in _usati][:5]
        if not cand:
            continue
        i = controlla(cand, qq, contesto)
        if i >= 0:
            with _lock:
                _usati.add(cand[i]['url'])
            return cand[i]['url']
        log('Pexels scartate tutte per:', qq)
    return None


# ============================================================ 4) SFONDI (Fal)
STILE_SFONDO = ('Wide 2D cartoon illustration for an animated history video, clean thick black outlines, flat warm colours with soft simple shading, '
                'like a modern illustrated history book, rich detail. The scene is EMPTY: absolutely no people, no animals in the foreground. '
                'The lower 30% of the image is open flat ground. No text, no letters, no signs with writing, no logos, no watermark.')


def fal(modello, dati):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/' + modello, dati, h)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], headers=h)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], headers=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('Fal: tempo scaduto')


def sfondo(s):
    p = os.path.join(LAV, 'sfondo_' + s['id'] + '.jpg')
    if os.path.exists(p):
        return p
    if not E('FAL_KEY'):
        Image.new('RGB', (W, H), (200, 180, 140)).save(p); return p
    r = fal('fal-ai/nano-banana-2', {'prompt': s['prompt_en'] + ' ' + STILE_SFONDO, 'aspect_ratio': '16:9',
                                      'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
    scarica(r['images'][0]['url'], p)
    Image.open(p).convert('RGB').resize((W, H), Image.LANCZOS).save(p, quality=92)
    log('sfondo pronto', s['id'])
    return p


# ============================================================ COPERTINA (copia dell'originale con i nostri personaggi)
def carica_fal(path, tipo='image/png'):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    ini = http('https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3', {'content_type': tipo, 'file_name': os.path.basename(path)}, h)
    req = urllib.request.Request(ini['upload_url'], data=open(path, 'rb').read(), method='PUT', headers={'Content-Type': tipo})
    urllib.request.urlopen(req, timeout=300).read()
    return ini['file_url']


def copertina(comp, c):
    if not comp.get('copertina') or not E('FAL_KEY'):
        return None
    cop = c.get('copertina') or {}
    testo = str(cop.get('testo') or c.get('titolo') or '').strip()
    img = [comp['copertina']]
    pg = png_personaggio(cop.get('personaggio') or '', 'fermo')
    if pg:
        try:
            img.append(carica_fal(pg))
        except Exception as e:
            log('personaggio copertina non caricato:', e)
    prompt = ('Recreate the YouTube thumbnail of the FIRST image almost identically: same composition, same layout, same framing, same place '
              'and same kind of scene, same colour palette and same title position and size, redrawn as a high-quality 2D cartoon illustration '
              'with clean black outlines and rich detail. Small differences only: slightly different camera angle, different small details in the background. '
              + ('The main figure is the character of the SECOND image (same face, clothes and style), placed where the main figure is in the first image. ' if len(img) > 1 else '')
              + f'Replace ALL the text with exactly this text, same font style, same colours and same position: "{testo}". No other text, no logos, no watermark.')
    try:
        r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': img, 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
        p = os.path.join(ROOT, 'copertina.jpg'); scarica(r['images'][0]['url'], p)
        Image.open(p).convert('RGB').resize((1280, 720), Image.LANCZOS).save(p, quality=92)
        log('copertina pronta')
        return p
    except Exception as e:
        log('copertina non riuscita:', str(e)[:200])


# ============================================================ texture e font
FONT_EPOCA = {   # sempre leggibili: niente gotico stretto nelle scritte
    'antico': 'Cinzel-Bold.ttf',              # Roma, Grecia, Persia, Egitto, Mesopotamia
    'classico': 'EBGaramond-SemiBold.ttf',    # storia generale, libri
    'medievale': 'IMFellEnglish.ttf',         # 500-1700
    'gotico': 'IMFellEnglish.ttf',
    'ottocento': 'PlayfairDisplay-Bold.ttf',  # 1700-1900, imperi coloniali
    'macchina': 'SpecialElite.ttf',           # 1900-1960, guerre mondiali
    'moderno': 'Oswald-SemiBold.ttf',         # dal 1960 a oggi
    'gara': 'EBGaramond-SemiBold.ttf', 'titolo': 'LuckiestGuy.ttf'}


def font(nome, size):
    f = FONT_EPOCA.get(nome, 'EBGaramond-SemiBold.ttf')
    if not os.path.exists(os.path.join(FONT, f)):
        f = 'EBGaramond-SemiBold.ttf'
    return ImageFont.truetype(os.path.join(FONT, f), size)


# ---------------------------------------------------------------- fondi delle carte (scritte e schede)
STILE_FONDO_CARTA = ('Decorative background plate for text cards in a history documentary. The theme is painted ONLY around the edges: corners, '
                     'side borders and a low skyline or ornaments at the bottom, soft watercolour / engraving look, warm and elegant. '
                     'The CENTRAL 65% of the image is a plain, smooth, uniform, EMPTY area (aged paper or soft solid colour) with absolutely nothing in it, '
                     'ready for big text. No text, no letters, no numbers, no people, no faces, no logo, no watermark.')


def fondo_carta_ai(f):
    p = os.path.join(LAV, 'fondo_' + str(f.get('id', 'c')) + '.jpg')
    if os.path.exists(p):
        return p
    r = fal('fal-ai/nano-banana-2', {'prompt': str(f.get('prompt_en') or '') + ' ' + STILE_FONDO_CARTA, 'aspect_ratio': '16:9',
                                      'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
    scarica(r['images'][0]['url'], p)
    Image.open(p).convert('RGB').resize((W, H), Image.LANCZOS).save(p, quality=92)
    log('fondo carta pronto', f.get('id'))
    return p


def tinta(tex, colore):
    """La stessa carta, ma colorata (rosso scuro, blu notte...): scritte chiare sopra."""
    c = colore.lstrip('#'); rgb = np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], float)
    g = np.asarray(tex.convert('L')).astype(float)[..., None] / 255
    return Image.fromarray(np.clip(rgb * (0.55 + 0.6 * g), 0, 255).astype('uint8'))


def prepara_fondo(im):
    """Sceglie il colore della scritta (scuro o crema) e schiarisce/scurisce piano il centro perche' si legga sempre bene."""
    im = im.convert('RGB').resize((W, H))
    centro = np.asarray(im.crop((W // 4, H // 4, 3 * W // 4, 3 * H // 4))).reshape(-1, 3).mean(0)
    chiaro = centro @ [0.299, 0.587, 0.114] > 128
    alone = Image.new('L', (W, H), 0); ImageDraw.Draw(alone).ellipse((W * .14, H * .2, W * .86, H * .8), fill=150)
    alone = alone.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(Image.new('RGB', (W, H), tuple(int(v) for v in centro)), im, alone)
    return im, (INK if chiaro else (247, 238, 218))


def texture(tipo):
    p = os.path.join(LAV, 'tex_' + tipo + '.jpg')
    if os.path.exists(p):
        return Image.open(p).convert('RGB')
    rng = np.random.default_rng(5)

    def rum(scala, blur):
        n = rng.normal(0, 1, (H // scala + 1, W // scala + 1))
        im = Image.fromarray(((n - n.min()) / (n.max() - n.min()) * 255).astype('uint8')).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
        return np.asarray(im).astype(float) / 255
    yy, xx = np.mgrid[0:H, 0:W]
    vign = np.clip(1 - ((xx - W / 2) / (W * .7)) ** 2 - ((yy - H / 2) / (H * .7)) ** 2, 0, 1)[..., None]
    if tipo in ('stropicciata', 'giornale'):
        h = np.zeros((H, W))
        for _ in range(55):
            x0, y0, an = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, np.pi)
            dist = (xx - x0) * np.sin(an) - (yy - y0) * np.cos(an)
            h += np.clip(1 - np.abs(dist) / rng.uniform(80, 300), 0, 1) * rng.uniform(-1, 1)
        sh = (0.92 + np.clip(np.gradient(h, axis=1) * .9, -.12, .12) + .04 * rum(4, 3))[..., None]
        base = np.array([238, 236, 232]) if tipo == 'stropicciata' else np.array([226, 214, 186])
        col = base * sh * (0.9 + 0.1 * vign)
    elif tipo == 'washi':
        col = np.array([241, 233, 214]) * (0.94 + 0.06 * rum(6, 10)[..., None]) * (0.93 + .07 * vign)
    elif tipo == 'papiro':
        fib = np.repeat(rng.normal(0, 1, (H, 1)), W, 1) * .5 + np.repeat(rng.normal(0, 1, (1, W)), H, 0) * .3
        col = np.array([222, 196, 140]) * (0.9 + 0.05 * np.tanh(fib)[..., None] + .05 * rum(8, 12)[..., None]) * (0.8 + .2 * vign)
    else:   # pergamena
        col = np.array([233, 214, 170]) * (0.85 + 0.15 * rum(8, 18)[..., None]) * (0.6 + .4 * vign) + np.array([150, 110, 60]) * (1 - vign) * .25
    im = Image.fromarray(np.clip(col + rng.normal(0, 4, (H, W, 1)), 0, 255).astype('uint8'))
    if tipo == 'washi':
        d = ImageDraw.Draw(im)
        for _ in range(900):
            x, y, L, an = rng.integers(0, W), rng.integers(0, H), rng.integers(20, 90), rng.uniform(0, np.pi)
            d.line((x, y, x + L * np.cos(an), y + L * np.sin(an)), fill=(222, 210, 184), width=1)
    im.save(p, quality=92)
    return im


# ============================================================ 5) PEZZI (ogni pezzo = un mp4 1920x1080 senza audio)
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', FPS]


def pipe_frames(path, d, disegna):
    n = max(1, int(round(d * FPS)))
    pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           *map(str, ENC), path], stdin=subprocess.PIPE)
    ultimo, img = None, None
    for f in range(n):
        chiave, fn = disegna(f / FPS)
        if chiave != ultimo or img is None:
            img = fn().tobytes(); ultimo = chiave
        pr.stdin.write(img)
    pr.stdin.close(); pr.wait()
    if pr.returncode:
        raise RuntimeError('ffmpeg pipe fallito ' + path)
    return path


def a_capo(testo, f, larg):
    righe, r = [], ''
    for w in testo.split():
        prova = (r + ' ' + w).strip()
        if f.getlength(prova) > larg and r:
            righe.append(r); r = w
        else:
            r = prova
    return righe + ([r] if r else [])


# battitura a macchina: stessi tempi per il disegno e per il suono dei tasti
def battitura(testo, inizio, max_dur):
    tot = max(1, len(testo)); dur = min(max_dur, .05 * tot)
    return inizio, dur


def tasti(testo, inizio, max_dur, d):
    """Secondi (dentro il pezzo) in cui compare ogni lettera: li' suona un tasto."""
    i0, dur = battitura(testo, inizio, max_dur); tot = max(1, len(testo))
    return [i0 + dur * (k + 1) / tot for k, ch in enumerate(testo) if ch.strip() and i0 + dur * (k + 1) / tot < d - .05]


def pezzo_carta(path, d, testo, fondo, nome_font):
    tex, ink = fondo
    sz = 120
    while True:
        f = font(nome_font, sz); righe = a_capo(testo, f, 1450)
        if (len(righe) <= 3 and max(f.getlength(r) for r in righe) <= 1500) or sz <= 74: break
        sz -= 6
    tot = len(testo); i0, dur_batt = battitura(testo, .3, 2.0)

    def disegna(t):
        n = tot if t >= i0 + dur_batt else int(clamp((t - i0) / dur_batt) * tot)

        def fn():
            im = tex.copy(); dr = ImageDraw.Draw(im); resto = n
            y0 = H / 2 - len(righe) * sz * 1.25 / 2
            for k, r in enumerate(righe):
                vis = r[:max(0, resto)]; resto -= len(r) + 1
                x = (W - f.getlength(r)) / 2
                dr.text((x, y0 + k * sz * 1.25), vis, font=f, fill=ink)
            return im
        return n, fn
    return pipe_frames(path, d, disegna)


# ---------------------------------------------------------------- striscia di carta strappata con didascalia (sopra cartoni e clip)
def carta_strappata(alt=250, seme=0):
    rng = np.random.default_rng(seme)
    im = Image.new('RGBA', (W, alt + 60), (0, 0, 0, 0))
    y, bordo = 45.0, []
    for x in range(0, W + 8, 8):   # strappo irregolare: onde larghe + dentini
        y = float(np.clip(y + rng.normal(0, 6), 8, 70)); bordo.append((x, y + rng.uniform(-4, 4)))
    poli = bordo + [(W, alt + 60), (0, alt + 60)]
    ombra = Image.new('L', im.size, 0); ImageDraw.Draw(ombra).polygon([(x, y - 6) for x, y in bordo] + [(W, alt + 60), (0, alt + 60)], fill=110)
    ombra = ombra.filter(ImageFilter.GaussianBlur(9))
    im.paste((0, 0, 0, 255), (0, 0), ombra)
    maschera = Image.new('L', im.size, 0); ImageDraw.Draw(maschera).polygon(poli, fill=255)
    fibra = rng.normal(0, 1, (im.size[1], W)); fibra = (fibra - fibra.min()) / (fibra.max() - fibra.min())
    carta = (np.array([247, 244, 237], float) * (0.95 + 0.05 * fibra[..., None])).astype('uint8')
    im.paste(Image.fromarray(carta), (0, 0), maschera)
    dr = ImageDraw.Draw(im)
    dr.line(bordo, fill=(255, 255, 255, 255), width=4)   # bordo fibroso chiaro dello strappo
    for x, y in bordo[::2]:   # fibre che escono dallo strappo
        if rng.random() < .5:
            dr.line((x, y, x + rng.uniform(-6, 6), y - rng.uniform(2, 9)), fill=(250, 249, 245, 255), width=2)
    return im


def aggiungi_didascalia(path, d, testo, nome_font):
    """Rifa' il pezzo con la striscia di carta che sale dal basso e la scritta battuta a macchina."""
    striscia = carta_strappata(seme=len(testo)); hs = striscia.height
    sz = 76
    while sz > 52 and font(nome_font, sz).getlength(testo) > W - 260:
        sz -= 4
    f = font(nome_font, sz); tot = len(testo); i0, dur = battitura(testo, .45, 1.6)
    tmp = path[:-4] + '_d.mp4'
    lettore = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    scrittore = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                  *map(str, ENC), tmp], stdin=subprocess.PIPE)
    k = 0
    while True:
        b = lettore.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        t = k / FPS; k += 1
        im = Image.frombytes('RGB', (W, H), b)
        sale = ease(clamp(t / .35))
        y = int(H - (hs - 20) * sale)
        im.paste(striscia, (0, y), striscia)
        n = tot if t >= i0 + dur else int(clamp((t - i0) / dur) * tot)
        if n:
            ImageDraw.Draw(im).text(((W - f.getlength(testo)) / 2, y + 60 + (hs - 60 - sz * 1.2) / 2), testo[:n], font=f, fill=INK)
        scrittore.stdin.write(im.tobytes())
    lettore.wait(); scrittore.stdin.close(); scrittore.wait()
    if scrittore.returncode or k == 0:
        raise RuntimeError('didascalia non riuscita')
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- suono della macchina da scrivere
def suono_tasti(eventi, totale, out, sr=44100):
    rng = np.random.default_rng(3)
    a = np.zeros(int((totale + 1) * sr), np.float32)
    for t in eventi:
        n = int(sr * rng.uniform(.018, .03)); i = int(t * sr)
        if i + n >= len(a):
            continue
        rum = np.diff(rng.normal(0, 1, n + 1)).astype(np.float32)         # click secco (rumore filtrato)
        corpo = np.sin(2 * np.pi * rng.uniform(1600, 2600) * np.arange(n) / sr).astype(np.float32) * .35
        a[i:i + n] += (rum + corpo) * np.exp(-np.arange(n) / (n / 5)).astype(np.float32) * rng.uniform(.55, 1.0)
    a = a / (np.abs(a).max() + 1e-6) * .9
    import wave
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((a * 32767).astype('<i2').tobytes())
    return out


def clamp(v, a=0., b=1.):
    return max(a, min(b, v))


def ease(t):
    t = clamp(t)
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def png_personaggio(nome, posa):
    for p in ([posa] if posa == 'fermo' else ['reazione', 'sorpreso', 'indica', 'azione']):
        f = os.path.join(KIT, f'{nome}_{p}.png')
        if os.path.exists(f):
            return f
    return None


def pezzo_scheda(path, d, fondo, nome_pg, nome, nome_font='classico'):
    tex, ink = fondo
    fp = png_personaggio(nome_pg, 'fermo')
    fig = Image.open(fp).convert('RGBA') if fp else None
    if fig:
        fig.thumbnail((900, 690)); ombra = fig.split()[3].filter(ImageFilter.GaussianBlur(10))
    sz = 100
    while sz > 64 and font(nome_font, sz).getlength(nome) > W - 200:
        sz -= 4
    f = font(nome_font, sz); tot = len(nome); i0, dur = battitura(nome, .6, 1.2)

    def disegna(t):
        k = (min(12, int(t * 20)), tot if t >= i0 + dur else int(clamp((t - i0) / dur) * tot))

        def fn():
            im = tex.copy()
            if fig:
                dy = int((1 - ease(min(t, .6) / .6)) * 40)
                x, y = (W - fig.width) // 2, 110 + dy
                im.paste((60, 40, 20), (x + 8, y + 12), ombra.point(lambda v: v * .35))
                im.paste(fig, (x, y), fig)
            n = k[1]; dr = ImageDraw.Draw(im)
            dr.text(((W - f.getlength(nome)) / 2, 850), nome[:n], font=f, fill=ink)
            return im
        return k, fn
    return pipe_frames(path, d, disegna)


def pezzo_cartone(path, d, bg, pg, reazione, data, lato):
    ins = ['-loop', '1', '-framerate', FPS, '-t', d, '-i', bg]
    filtri = [f'[0:v]scale={W * 4}:{H * 4}:flags=lanczos,zoompan=z=\'1+0.08*on/{max(1, int(d * FPS))}\':d=1:'
              f'x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':s={W}x{H}:fps={FPS}[b]']
    cur = 'b'
    f1 = png_personaggio(pg, 'fermo') if pg else None
    if f1:
        f2 = png_personaggio(pg, 'reazione') if reazione else None
        cambio = d * .5
        xb = f'main_w-overlay_w-240' if lato else '240'
        entra = f'if(lt(t,0.6),(0.6-t)/0.6*{"700" if lato else "-700"},0)'
        ins += ['-loop', '1', '-framerate', FPS, '-t', d, '-i', f1]
        filtri.append(f'[1:v]scale=-1:820[p1]')
        en1 = f":enable='lt(t,{cambio:.2f})'" if f2 else ''
        filtri.append(f"[{cur}][p1]overlay=x='{xb}+{entra}':y='main_h-overlay_h-10+6*sin(2.4*t)'{en1}[o1]"); cur = 'o1'
        if f2:
            ins += ['-loop', '1', '-framerate', FPS, '-t', d, '-i', f2]
            filtri.append(f'[2:v]scale=-1:820[p2]')
            filtri.append(f"[{cur}][p2]overlay=x='{xb}':y='main_h-overlay_h-10+6*sin(2.4*t)-30*max(0,1-(t-{cambio:.2f})/0.3)'"
                          f":enable='gte(t,{cambio:.2f})'[o2]"); cur = 'o2'
    if data:
        tf = os.path.join(LAV, 'data.txt'); open(tf, 'w').write(data)
        filtri.append(f"[{cur}]drawtext=fontfile={os.path.join(FONT, 'EBGaramond-SemiBold.ttf')}:textfile={tf}:fontsize=150:fontcolor=0x1d1a17:"
                      f"borderw=8:bordercolor=white@0.75:x=(w-tw)/2:y=60:alpha='min(1,max(0,(t-0.4)/0.5))'[o3]"); cur = 'o3'
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filtri), '-map', f'[{cur}]', '-t', d, *ENC, path])
    return path


def pezzo_video(path, d, src):
    run(['ffmpeg', '-y', '-v', 'error', '-stream_loop', '-1', '-i', src, '-t', d, '-an',
         '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1', *ENC, path])
    return path


def pezzo_foto(path, d, src):
    n = max(1, int(d * FPS))
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', FPS, '-t', d, '-i', src,
         '-vf', f"scale={W * 4}:{H * 4}:force_original_aspect_ratio=increase:flags=lanczos,crop={W * 4}:{H * 4},"
                f"zoompan=z='1+0.07*on/{n}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1",
         '-t', d, *ENC, path])
    return path


# ---------------------------------------------------------------- mappa (PIL, nessun browser)
def carica_geo():
    return json.load(open(os.path.join(GEO, 'mondo.json'))), json.load(open(os.path.join(GEO, 'dettaglio.json')))


def merc(lon, lat):
    lat = max(-85, min(85, lat))
    return (lon + 180) / 360, (1 - math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) / math.pi) / 2


def anelli(geom):
    cs = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    for poly in cs:
        r = poly[0]
        # anelli che attraversano la linea del cambio di data (Russia, Fiji...): si saltano, altrimenti righe orizzontali
        if any(abs(r[i][0] - r[i - 1][0]) > 180 for i in range(1, len(r))):
            continue
        yield r


def pezzo_mappa(path, d, paese, titolo, date):
    mondo, dett = carica_geo()
    bersaglio = next((f for f in dett['features'] if f['properties'].get('name', '').lower() == paese.lower()), None)
    if not bersaglio:
        raise RuntimeError('paese non trovato sulla mappa: ' + paese)
    M0 = [(f, [[merc(*c) for c in a] for a in anelli(f['geometry'])]) for f in mondo['features'] if f['properties'].get('name') != 'Antarctica']
    BT = [[merc(*c) for c in a] for a in anelli(bersaglio['geometry'])]
    xs = [p[0] for a in BT for p in a]; ys = [p[1] for a in BT for p in a]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    # vista iniziale: mondo intero; finale: paese a destra al 45% della larghezza
    v0 = (0.0, .08, 1.0, .92)
    sc = max((x1 - x0) / .42, (y1 - y0) / .62 * W / H)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    v1 = (cx - sc * .64, cy - sc * H / W * .5, cx + sc * .36, cy + sc * H / W * .5)
    ft = font('titolo', 190 if len(titolo) < 10 else 150); fd = font('titolo', 86)

    def vista(z):
        return [lerp(v0[k], v1[k], z) for k in range(4)]

    def disegna(t):
        z = ease((t - .3) / 3); ev = ease((t - 2.6) / 1); tt = clamp((t - 3.2) / .4)
        k = (round(z, 3), round(ev, 2), round(tt, 2))

        def fn():
            a, b, c, dd = vista(z)
            tr = lambda p: ((p[0] - a) / (c - a) * W, (p[1] - b) / (dd - b) * H)
            im = Image.new('RGB', (W, H), (159, 208, 232)); dr = ImageDraw.Draw(im)
            for f, rings in M0:
                for r in rings:
                    pts = [tr(p) for p in r]
                    if len(pts) > 2: dr.polygon(pts, fill=(239, 227, 196), outline=(138, 123, 92))
            col = tuple(int(lerp(x, y, ev)) for x, y in zip((239, 227, 196), (214, 58, 48)))
            for r in BT:
                pts = [tr(p) for p in r]
                if len(pts) > 2: dr.polygon(pts, fill=col, outline=INK, width=3)
            if tt > 0:
                lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
                dl.text((560, 430), titolo.upper(), font=ft, fill=(255, 255, 255, 255), anchor='mm', stroke_width=12, stroke_fill=INK)
                dl.text((560, 560), date, font=fd, fill=(214, 58, 48, 255), anchor='mm', stroke_width=8, stroke_fill=INK)
                lay.putalpha(lay.split()[3].point(lambda v: int(v * tt)))
                im.paste(lay, (0, 0), lay)
            return im
        return k, fn
    return pipe_frames(path, d, disegna)


def lerp(a, b, t):
    return a + (b - a) * t


# ============================================================ 6) UNIONE con transizioni a scatto
def unisci(pezzi, out):
    """pezzi = [(path, durata)]: taglio netto, i pezzi vengono messi uno dopo l'altro senza ricodificare."""
    lista = os.path.join(LAV, 'pezzi.txt')
    open(lista, 'w').write(''.join(f"file '{os.path.abspath(p)}'\n" for p, _ in pezzi))
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', out])
    return durata(out)


# ============================================================ MAIN
PESO = {'cartone': 1.6, 'mappa': 3.0, 'scheda': 1.3, 'carta': 1.2, 'pexels_video': 1.0, 'pexels_foto': 1.0}


def limite(t):
    """Durata massima di un visivo in base a quando compare: primi 10 s = almeno 4 cambi, 10-30 s = 3 ogni 10 s, poi max 5 s."""
    return 2.5 if t < 10 else 3.3 if t < 30 else 5.0


def ritmo(piano, sf_ids):
    """Spezza i visivi troppo lunghi in parti uguali: stesso personaggio su un altro sfondo, un'altra clip della stessa ricerca, ecc."""
    out, t, giro = [], 0.0, 0
    for v in piano:
        d = v['d']; lim = limite(t)
        n = math.ceil(d / lim - .08)
        minimo = 2.7 if v['tipo'] in ('carta', 'scheda') else 3.0 if v['tipo'] == 'mappa' else 1.3   # il tempo di leggere
        if n <= 1 or d / n < 1.3:
            out.append(v); t += d; continue
        primo = max(d / n, min(minimo, d - 1.3 * (n - 1)))
        resto = d - primo; m = n - 1
        while m > 1 and resto / m < 1.3:
            m -= 1
        parti = [dict(v, d=primo)]
        for k in range(1, m + 1):
            giro += 1
            if v['tipo'] in ('pexels_video', 'pexels_foto'):
                nuovo = {'tipo': v['tipo'], 'q': v.get('q'), 'contesto': v.get('contesto')}
            else:
                pg = v.get('personaggio') if v['tipo'] == 'cartone' else v.get('pg_scena')
                altri = [x for x in sf_ids if x != v.get('sfondo')] or sf_ids
                nuovo = {'tipo': 'cartone', 'sfondo': altri[giro % len(altri)], 'personaggio': pg or '', 'reazione': k % 2 == 1,
                         'contesto': v.get('contesto'), 'pg_scena': v.get('pg_scena')}
            parti.append(dict(nuovo, d=resto / m))
        out += parti; t += d
    return out


def pianifica(scene, durs, voci, sf):
    """Divide ogni scena in visivi che compaiono quando la voce dice la loro 'frase'."""
    piano = []
    for i, (s, D) in enumerate(zip(scene, durs)):
        testo = s['testo']
        try:
            al = json.load(open(voci[i][:-4] + '.json'))
        except Exception:
            al = {}
        vis = []
        for v in (s.get('visivi') or []):
            if v.get('tipo') not in PESO:
                continue
            # una scheda (presentazione) solo se quel personaggio viene NOMINATO in questa scena
            if v['tipo'] == 'scheda' and not nominato(testo, v.get('nome') or v.get('personaggio') or ''):
                log('scheda tolta (non nominato nella scena):', v.get('nome')); continue
            vis.append(v)
        vis = vis or [{'tipo': 'cartone', 'sfondo': random.choice(list(sf))}]
        # quando compare ogni visivo: alla parola esatta detta dalla voce
        tot = sum(PESO[v['tipo']] for v in vis); acc = 0; pos = 0; inizi = []
        for j, v in enumerate(vis):
            stima = D * acc / tot; acc += PESO[v['tipo']]
            frase = v.get('frase') or (v.get('testo') if v['tipo'] == 'carta' else '') or (v.get('nome') if v['tipo'] == 'scheda' else '')
            if j == 0 and v['tipo'] not in ('carta', 'scheda'):
                frase = ''   # il primo visivo parte con la scena
            idx = trova(testo, frase, pos) if frase else None
            if idx is not None:
                pos = idx + 1
                t = max(0.0, tempo_lettera(al, idx, testo, D) - 0.15)   # appena prima della parola
            else:
                t = stima if j else 0.0
            inizi.append((t, j, idx is not None))
        inizi.sort()   # in ordine di tempo
        if inizi and not inizi[0][2]:
            inizi[0] = (0.0,) + inizi[0][1:]
        vis = [vis[j] for _, j, _ in inizi]; inizi = [t for t, _, _ in inizi]
        # almeno 1,2 s per visivo: i visivi troppo ravvicinati vengono tolti
        tenuti = []
        for v, t in zip(vis, inizi):
            if tenuti and t < tenuti[-1][1] + 1.2:
                if v['tipo'] in ('carta', 'scheda'):   # la scritta/presentazione ha la precedenza: sostituisce il visivo precedente
                    if len(tenuti) > 1 and t >= tenuti[-2][1] + 1.2:
                        tenuti[-1] = (v, t)
                continue
            tenuti.append((v, t))
        if tenuti and D - tenuti[-1][1] < 1.2 and len(tenuti) > 1:
            tenuti.pop()
        if tenuti and tenuti[0][1] > 0:   # la scena inizia con una scritta detta piu' avanti: fino a li' resta il visivo precedente
            if piano:
                piano[-1]['d'] += tenuti[0][1]
            else:
                tenuti.insert(0, ({'tipo': 'cartone', 'sfondo': random.choice(list(sf))}, 0.0))
        pg_scena = next((v.get('personaggio') for v in (s.get('visivi') or []) if v.get('tipo') == 'cartone' and v.get('personaggio')), '')
        for j, (v, t) in enumerate(tenuti):
            fine = tenuti[j + 1][1] if j + 1 < len(tenuti) else D
            piano.append(dict(v, d=fine - t, contesto=testo, pg_scena=pg_scena))
    return piano




def main():
    os.makedirs(LAV, exist_ok=True)
    comp = competitor()
    c = copione(comp)
    titolo_finale = c.get('titolo') or TITOLO
    json.dump(c, open(os.path.join(ROOT, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
    kit = kit_disponibile()
    mancanti = list(c.get('personaggi_mancanti') or [])
    log('copione:', len(c['scene']), 'scene,', sum(len(s['testo'].split()) for s in c['scene']), 'parole')
    # voce
    with ThreadPoolExecutor(2) as ex:   # ElevenLabs accetta poche richieste insieme (errore 429 con 4)
        voci = list(ex.map(lambda a: voce(*a), enumerate(s['testo'] for s in c['scene'])))
    durs = [durata(v) for v in voci]
    log('voce pronta:', round(sum(durs) / 60, 1), 'minuti')
    # sfondi
    with ThreadPoolExecutor(3) as ex:
        sf = dict(zip([s['id'] for s in c['sfondi']], ex.map(sfondo, c['sfondi'])))
    tex = texture(c.get('texture') or 'pergamena')
    nome_font = c.get('font_carte') if c.get('font_carte') in FONT_EPOCA else 'classico'
    # fondi delle carte: 3 immagini a tema (bordi decorati, centro libero) + la carta dell'epoca + 2 colori a tinta unita
    fondi = [prepara_fondo(tex)]
    for col in (c.get('colori_carte') or ['#6b1e1e', '#1d3557'])[:2]:
        try:
            fondi.append(prepara_fondo(tinta(tex, str(col))))
        except Exception as e:
            log('colore carta saltato:', col, e)
    if E('FAL_KEY') and c.get('fondi_carte'):
        def _fc(f):
            try:
                return fondo_carta_ai(f)
            except Exception as e:
                log('fondo carta non riuscito:', str(e)[:150])
        with ThreadPoolExecutor(3) as ex:
            ai = [prepara_fondo(Image.open(pp)) for pp in ex.map(_fc, c['fondi_carte'][:3]) if pp]
        mix = []   # alterna: tema, carta, tema, colore, tema, colore
        for i in range(max(len(ai), len(fondi))):
            mix += ([ai[i]] if i < len(ai) else []) + ([fondi[i]] if i < len(fondi) else [])
        fondi = mix
    # piano dei pezzi
    piano = pianifica(c['scene'], durs, voci, sf)
    for v in piano:
        if v.get('personaggio') and v['personaggio'] not in kit:
            mancanti.append(v['personaggio']); v['personaggio'] = ''
    # ogni cartone ha sempre un personaggio: quello della scena, altrimenti il piu' usato nel video
    usati = [v.get('personaggio') for v in piano if v.get('tipo') == 'cartone' and v.get('personaggio')]
    pg_video = max(set(usati), key=usati.count) if usati else (kit[0] if kit else '')
    for v in piano:
        if v.get('pg_scena') not in kit:
            v['pg_scena'] = pg_video
        if v['tipo'] == 'cartone' and not v.get('personaggio'):
            v['personaggio'] = v['pg_scena']
    piano = ritmo(piano, list(sf))
    log('visivi:', len(piano), '| primi 10 s:', sum(1 for x in __import__('itertools').accumulate([0] + [v['d'] for v in piano]) if x < 10))
    # durate a fotogrammi interi: video e voce restano allineati fino all'ultimo secondo
    fine_prec, acc = 0, 0.0
    for v in piano:
        acc += v['d']; fine = int(round(acc * FPS))
        v['d'] = max(1, fine - fine_prec) / FPS; fine_prec = fine
    n_carte = 0
    for v in piano:   # ogni carta/scheda su un fondo diverso dalla precedente
        if v['tipo'] in ('carta', 'scheda'):
            v['fondo'] = n_carte % len(fondi); n_carte += 1

    def fai(k):
        v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4'); t = v['tipo']
        try:
            if t in ('pexels_video', 'pexels_foto'):
                u = pexels('video' if t == 'pexels_video' else 'foto', v.get('q') or 'ancient ruins', v.get('contesto') or '')
                if not u:
                    raise RuntimeError('nessun risultato Pexels per ' + str(v.get('q')))
                src = os.path.join(LAV, f'src_{k:04d}' + ('.mp4' if t == 'pexels_video' else '.jpg'))
                scarica(u, src)
                pezzo_video(p, d, src) if t == 'pexels_video' else pezzo_foto(p, d, src)
                return con_didascalia(p, d, v)
            if t == 'carta':
                return pezzo_carta(p, d, v.get('testo') or '', fondi[v.get('fondo', 0)], nome_font)
            if t == 'scheda':
                return pezzo_scheda(p, d, fondi[v.get('fondo', 0)], v.get('personaggio') or '', v.get('nome') or '', nome_font)
            if t == 'mappa':
                return pezzo_mappa(p, d, c.get('paese_mappa') or '', c.get('titolo_mappa') or TITOLO.split()[-1], c.get('date') or '')
            pezzo_cartone(p, d, sf.get(v.get('sfondo')) or list(sf.values())[k % len(sf)], v.get('personaggio') or '',
                          bool(v.get('reazione')), v.get('data') or '', k % 2 == 0)
            return con_didascalia(p, d, v)
        except Exception as e:   # riserva: cartone senza personaggio, il video non si ferma mai
            log('pezzo', k, t, 'sostituito:', str(e)[:200])
            v.pop('didascalia', None); v['tipo'] = 'cartone'
            return pezzo_cartone(p, d, list(sf.values())[k % len(sf)], '', False, '', True)

    def con_didascalia(p, d, v):
        if v.get('didascalia') and d > 2.2:
            try:
                return aggiungi_didascalia(p, d, str(v['didascalia'])[:60], nome_font)
            except Exception as e:
                log('didascalia saltata:', str(e)[:150])
        v.pop('didascalia', None)
        return p
    t0 = time.time()
    with ThreadPoolExecutor(2) as ex:
        paths = list(ex.map(fai, range(len(piano))))
    log('pezzi pronti:', len(paths), 'in', int(time.time() - t0), 's')
    video = os.path.join(LAV, 'muto.mp4')
    unisci([(p, v['d']) for p, v in zip(paths, piano)], video)
    # audio: voce + musica (facoltativa)
    lista = os.path.join(LAV, 'voci.txt'); open(lista, 'w').write(''.join(f"file '{v}'\n" for v in voci))
    voce_tot = os.path.join(LAV, 'voce.m4a')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c:a', 'aac', '-b:a', '192k', voce_tot])
    # tasti della macchina da scrivere, a tempo con le lettere che compaiono
    eventi, t_ini = [], 0.0
    for v in piano:
        d = v['d']
        if v['tipo'] == 'carta':
            eventi += [t_ini + x for x in tasti(v.get('testo') or '', .3, 2.0, d)]
        elif v['tipo'] == 'scheda':
            eventi += [t_ini + x for x in tasti(v.get('nome') or '', .6, 1.2, d)]
        elif v.get('didascalia'):
            eventi += [t_ini + x for x in tasti(str(v['didascalia'])[:60], .45, 1.6, d)]
        t_ini += d - T_TR
    if eventi:
        try:
            wav = suono_tasti(eventi, sum(durs), os.path.join(LAV, 'tasti.wav'))
            con_tasti = os.path.join(LAV, 'voce_tasti.m4a'); vt = float(E('TASTI_VOL', '0.22') or .22)
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-i', wav, '-filter_complex',
                 f'[1:a]volume={vt}[k];[0:a][k]amix=inputs=2:duration=first:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', con_tasti])
            voce_tot = con_tasti
            log('tasti macchina da scrivere:', len(eventi))
        except Exception as e:
            log('suono tasti saltato:', str(e)[:150])
    audio = voce_tot
    if E('MUSICA_URL'):
        try:
            mf = scarica(E('MUSICA_URL'), os.path.join(LAV, 'musica.mp3'))
            audio = os.path.join(LAV, 'audio.m4a'); vol = float(E('MUSICA_VOL', '0.08') or .08)
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-stream_loop', '-1', '-i', mf, '-filter_complex',
                 f'[1:a]volume={vol}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', audio])
        except Exception as e:
            log('musica saltata:', e)
    finale = os.path.join(ROOT, 'video_storia.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'copy', '-shortest', finale])
    copertina(comp, c)
    open(os.path.join(ROOT, 'titolo.txt'), 'w').write(titolo_finale)
    open(os.path.join(ROOT, 'personaggi_mancanti.txt'), 'w').write('\n'.join(sorted(set(m for m in mancanti if m))))
    log('FATTO:', finale, round(durata(finale) / 60, 1), 'minuti')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
