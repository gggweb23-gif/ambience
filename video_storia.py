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
import base64, hashlib, io, json, math, os, random, re, shutil, subprocess, sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 24
T_TR = 0.0                                   # nessuna transizione: taglio netto tra le immagini
ROOT = os.getcwd()
LAV = os.path.join(ROOT, 'lavoro_storia')
KIT = os.path.join(ROOT, 'kit_storia')
FONT = os.path.join(ROOT, 'font')
GEO = os.path.join(ROOT, 'geo')
E = os.environ.get
try:   # n8n (MULTICHANNEL - Storia Video) passa tutto in un unico JSON: vince sui campi del modulo
    P = json.loads(E('PAYLOAD') or '{}') or {}
except Exception:
    P = {}
TITOLO = E('TITOLO', 'Tutta la storia dell\'Iran').strip()
LINGUA = E('LINGUA', 'it').strip() or 'it'
VOCE = str(P.get('voce') or E('VOCE', '') or 'glnsgBC77wt5zOYU0szz').strip()
MINUTI = float(E('MINUTI', '13') or 13)
MAX_MINUTI = float(P.get('max_minuti') or E('MAX_MINUTI', '25') or 25)   # oltre questa durata il copione condensa l'originale
PROVA = str(P.get('prova') or E('PROVA', 'NO')).strip().upper() == 'SI'
CARICA = str(P.get('carica') or E('CARICA', 'NO')).strip().upper() == 'SI' and not PROVA   # SI = carica su YouTube
VOCE_VELOCITA = max(.8, min(1.2, float(str(P.get('voce_velocita') or E('VOCE_VELOCITA', '') or 1.06).replace(',', '.'))))   # uguale per tutte le scene
MUSICA_URL = str(P.get('musica_url') or E('MUSICA_URL', '')).strip()
def _perc(v, d=100):
    try:
        return max(0, min(100, int(float(str(v).replace('%', '').replace(',', '.')) * (100 if 0 < float(str(v).replace('%', '').replace(',', '.')) <= 1 else 1))))
    except Exception:
        return d
COP_COPIA = _perc(P.get('copertina_copia') or E('COPERTINA_COPIA', ''), 100)    # % della copertina competitor da tenere uguale
TIT_COPIA = _perc(P.get('titolo_copia') or E('TITOLO_COPIA', ''), 100)          # % del titolo competitor da tenere uguale
COP_STILE = str(P.get('copertina_stile') or E('COPERTINA_STILE', '') or 'cartone').strip().lower()   # cartone | realistico
RIFERIMENTI = [u for u in (P.get('riferimenti_copertine') or []) if u][:8]      # copertine top della nicchia (dallo Scout)
MODELLO_AI = E('MODELLO_AI', 'claude-sonnet-5-5').strip()
LINK = str(P.get('link') or E('LINK_COMPETITOR', '')).strip()
CARTE_MINUTO = int(float(str(P.get('carte_minuto') or E('CARTE_MINUTO', '') or 2)))   # scritte su texture: max N al minuto
PERSONAGGIO_MINUTO = int(float(str(P.get('personaggio_minuto') or E('PERSONAGGIO_MINUTO', '') or 2)))   # stesso personaggio max N volte al minuto
EFFETTI = str(P.get('effetti') or E('EFFETTI', '')).strip().upper() == 'SI'                  # effetti sonori da film (spade, cavalli, vento...)
EFFETTI_MINUTO = float(str(P.get('effetti_minuto') or E('EFFETTI_MINUTO', '') or 1.5).replace(',', '.'))   # quanti al massimo per minuto
def _num_lista(v, d):
    try:
        x = [float(t.replace(',', '.')) for t in re.split(r'[;/| ]+', str(v).strip()) if t.strip()]
        return (x + d[len(x):])[:3] if x else d
    except Exception:
        return d
RITMO = _num_lista(P.get('ritmo') or E('RITMO', ''), [4.0, 4.0, 4.0])   # secondi max per immagine: primi 10 s / 10-30 s / dopo
QUOTA_CARTONI = _perc(P.get('quota_cartoni') or E('QUOTA_CARTONI', ''), 80)
BUDGET = float(str(P.get('budget_video') or E('BUDGET_VIDEO', '') or 3).replace(',', '.').replace('€', '').strip() or 0)   # euro massimi a video (0 = nessun tetto)
PREZZO_DISEGNO = 0.12   # $ per disegno Nano Banana 2 a 2K (con i rifatti si conta +25%)
SPESA = {'fal': 0.0, 'disegni': 0}
CORNICE = str(P.get('cornice') or E('CORNICE', '') or 'SI').strip().upper() == 'SI'   # cornice a tema del paese intorno a tutto il video
RISERVA_PX = []   # ricerche Pexels generiche del paese, per quando una ricerca precisa non trova niente   # % del video a cartone (Nano Banana), il resto Pexels
SFONDI_MAX = int(float(str(P.get('sfondi_max') or E('SFONDI_MAX', '') or 60)))
SEC_IMMAGINE = float(str(P.get('secondi_per_immagine') or E('SECONDI_PER_IMMAGINE', '') or 12))   # ogni disegno copre ~16 s: 4 inquadrature diverse da 4 s (meno immagini, stesso ritmo)   # tetto immagini a cartone generate per video (costo)
SUONI_CAMBIO = str(P.get('suoni_cambio') or E('SUONI_CAMBIO', '') or 'NO').strip().upper() == 'SI'   # click/swoosh a ogni cambio immagine
SUONI_CAMBIO_URL = [u.strip() for u in re.split(r'\|\||\n', str(P.get('suoni_cambio_url') or E('SUONI_CAMBIO_URL', ''))) if u.strip().startswith('http')]
SUONI_CAMBIO_VOL = float(str(P.get('suoni_cambio_vol') or E('SUONI_CAMBIO_VOL', '') or .45).replace(',', '.'))
INTEGRATO = str(P.get('cartone_integrato') or E('CARTONE_INTEGRATO', '') or 'SI').strip().upper() == 'SI'   # personaggi DENTRO l'immagine Nano Banana (come PRODUCTION)
SF_META = {}   # id immagine a cartone -> personaggi del kit disegnati dentro
DISTANZA_IMMAGINI = float(str(P.get('distanza_immagini') or E('DISTANZA_IMMAGINI', '') or 120).replace(',', '.'))   # stesso disegno: mai prima di N secondi
TEXTURE = str(P.get('texture') or E('TEXTURE', '') or 'NO').strip().upper() == 'SI'   # NO = niente carte, schede e strisce di carta: solo disegni
TASTI = str(P.get('suoni_tasti') or E('SUONI_TASTI', '') or 'SI').strip().upper() == 'SI'   # rumore macchina da scrivere sulle scritte
REGIA = str(P.get('regia') or E('REGIA', '') or 'NO').strip().upper() == 'SI'   # prova 18/10 bocciata: resta spenta   # solo cartoni, un'immagine per ogni frase
IMMAGINI_MODELLO = str(P.get('immagini_modello') or E('IMMAGINI_MODELLO', '') or 'seedream').strip().lower()   # seedream (0,04 $) | nano-banana-2 (0,12 $ a 2K)
NUOVE_QUOTA = float(str(P.get('immagini_nuove') or E('IMMAGINI_NUOVE', '') or .55).replace(',', '.').replace('%', ''))
NUOVE_QUOTA = NUOVE_QUOTA / 100 if NUOVE_QUOTA > 1 else NUOVE_QUOTA   # quota di inquadrature con un'immagine nuova (le altre: dettaglio della precedente)
IMMAGINI_MAX = int(float(str(P.get('immagini_max') or E('IMMAGINI_MAX', '') or 200)))   # tetto immagini per video (costo)
VERIFICA = str(P.get('verifica_immagini') or E('VERIFICA_IMMAGINI', '') or 'SI').strip().upper() == 'SI'   # Claude controlla ogni immagine
GRANA = str(P.get('grana') or E('GRANA', '') or 'SI').strip().upper() == 'SI'   # grana da pellicola + vignetta leggera
PEXELS_MAX = int(float(str(P.get('pexels_max') or E('PEXELS_MAX', '') or 190)))   # ricerche Pexels per video (limite Pexels: 200 l'ora)
NARRATORE = str(P.get('narratore') or E('NARRATORE', '') or 'anziano_narratore').strip()   # avatar del canale: MAI nei video
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


def senza_ragionamento(data):
    """I modelli Claude 5.5 'ragionano' prima di rispondere e il ragionamento consuma max_tokens: con copioni lunghi
    (o risposte brevi come 'SCELTA: 2') finiva tutto nel ragionamento e la risposta arrivava VUOTA. Qui lo si spegne."""
    m = str(data.get('model') or '')
    if 'thinking' in data or not re.search(r'(sonnet|opus|haiku|fable|mythos)-5', m):
        return data
    d = dict(data)
    if 'sonnet-5-5' in m:
        d['thinking'] = {'type': 'between_tools'}                 # Sonnet 5.5: 'disabled' non e' accettato
        d['output_config'] = {'effort': 'medium'}
    elif 'opus-5-5' in m or 'fable' in m or 'mythos' in m:
        d['output_config'] = {'effort': 'low'}                     # non si puo' spegnere: si riduce al minimo
    else:
        d['thinking'] = {'type': 'disabled'}
        d['output_config'] = {'effort': 'medium'}
    return d


def http(url, data=None, headers=None, metodo=None, timeout=180, raw=False):
    if isinstance(data, dict) and 'api.anthropic.com' in url:
        data = senza_ragionamento(data)
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


def dati_yt(c):
    """Tag e categoria del video competitor (YouTube Data API con il token del canale); se non riesce usa quelli scritti dallo Scout nel foglio."""
    tag, cat = [], ''
    if E('YT_REFRESH_TOKEN'):
        try:
            req = urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=snippet&id=' + c['id'],
                                         headers={'Authorization': 'Bearer ' + token()})
            with urllib.request.urlopen(req, timeout=60) as r:
                sn = (json.loads(r.read().decode()).get('items') or [{}])[0].get('snippet') or {}
            tag, cat = list(sn.get('tags') or []), str(sn.get('categoryId') or '')
        except Exception as e:
            log('tag/categoria del competitor non letti da YouTube:', str(e)[:120])
    if not tag:
        tag = [t.strip() for t in re.split(r'[,|]', str(P.get('tag_originali') or '')) if t.strip()]
    cat = cat or str(P.get('categoria_originale') or '').strip()
    c['tag_originali'], c['categoria'] = tag, cat
    log('competitor: categoria', cat or '-', ',', len(tag), 'tag')


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
    dati_yt(c)
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
    """Personaggi del kit, SENZA il narratore (avatar del canale): nei video non compare mai."""
    if not os.path.isdir(KIT):
        return []
    return sorted({f[:-len('_fermo.png')] for f in os.listdir(KIT) if f.endswith('_fermo.png')} - {NARRATORE})


# come sono disegnati i personaggi generici (il nome da solo inganna: "re_antico" e' un re europeo con l'ermellino)
KIT_DESCR = {
    'uomo_moderno': 'uomo moderno in giacca e cravatta: SOLO uomini d\'affari o politici di oggi (MAI archeologi, scienziati, esploratori, turisti, persone del passato)',
    'donna_moderna': 'donna moderna in felpa e jeans (SOLO persone di oggi)',
    'turista': 'turista moderno con camicia hawaiana e macchina fotografica (SOLO turismo di oggi)',
    'industriale': 'industriale dell\'Ottocento in cilindro', 'operaio': 'operaio europeo del Novecento',
    're_antico': 're europeo medievale, corona e mantello di ermellino (SOLO Europa)',
    'regina': 'regina europea medievale, abito blu (SOLO Europa)',
    'nobile': 'nobile europeo del Settecento con parrucca (SOLO Europa 1700-1800)',
    'cavaliere': 'cavaliere crociato europeo con armatura e croce (SOLO Europa/crociate)',
    'crociato': 'crociato europeo (SOLO crociate)',
    'generale': 'generale in divisa della prima guerra mondiale (SOLO 1900-1950)',
    'politico': 'politico moderno in giacca e cravatta (SOLO dal 1900 a oggi)',
    'esploratore': 'esploratore europeo del Cinquecento',
    'soldato_moschetto': 'soldato europeo del Settecento con moschetto',
    'sacerdote': 'sacerdote antico del Medio Oriente, tunica bianca e incenso',
    'contadino_antico': 'contadino asiatico con cappello di paglia a cono',
    'contadina_antica': 'contadina antica con velo, Medio Oriente/Mediterraneo',
    'mercante': 'mercante mediorientale con turbante',
    'guerriero_barbaro': 'guerriero barbaro nordico con pelliccia e ascia',
    'legionario': 'legionario romano', 'senatore': 'senatore romano in toga',
}


def lista_kit(kit):
    return ', '.join(k + (f' ({KIT_DESCR[k]})' if k in KIT_DESCR else '') for k in kit) or '(nessuno)'


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
    # sfondi a cartone: tanti quanti servono per non ripetere (ognuno usato al massimo 2 volte), con un tetto di costo
    sec = parole / 2.5   # ~150 parole al minuto
    pezzi = min(sec, 10) / RITMO[0] + max(0, min(sec, 30) - 10) / RITMO[1] + max(0, sec - 30) / RITMO[2]
    usi = 1 if sec < 240 else 2   # video corti: ogni disegno UNA volta sola; lunghi: max 2 volte, a distanza
    n_sf = max(6, min(SFONDI_MAX, math.ceil(pezzi * QUOTA_CARTONI / 100 / usi) + 2))
    if INTEGRATO:   # un disegno ogni ~7 s di cartone: il ritmo da 3 s lo fanno zoom e inquadrature diverse della STESSA immagine
        n_sf = max(6, min(SFONDI_MAX, math.ceil(sec * QUOTA_CARTONI / 100 / SEC_IMMAGINE) + 2))
    if BUDGET > 0:   # tetto di spesa: pochi disegni (solo dove ci sono persone + gancio iniziale), il ritmo lo fa Pexels (gratis)
        dollari = BUDGET * 1.08
        fissi = 0.35 + 0.15 + 0.05 + (sec / 5) * 0.005   # copione + copertina + controlli disegni + controlli Pexels (Haiku)
        n_budget = max(2, int((dollari - fissi) / (PREZZO_DISEGNO * 1.25)))
        n_sf = max(2, min(SFONDI_MAX, n_budget, 3 + math.ceil(max(0.0, sec - 30) / 45)))
        globals()['QUOTA_CARTONI'] = max(5, min(60, round(n_sf * 8 / max(sec, 1) * 100)))
        globals()['RITMO'] = [4.0, 5.0, 6.0]
        log(f'budget {BUDGET:.2f} EUR: {n_sf} disegni (circa {n_sf * PREZZO_DISEGNO:.2f} $), cartone ~{QUOTA_CARTONI}% del video, il resto Pexels')
    w = [round(RITMO[0] * 2.5), round(RITMO[1] * 2.5), round(RITMO[2] * 2.5)]   # parole per visivo (circa 2,5 parole al secondo)
    if INTEGRATO and BUDGET <= 0:   # ogni visivo ha la SUA immagine scritta sulla sua frase; i tagli da 3 s li fa il montaggio (zoom sulla stessa immagine)
        w = [12, 24, round(SEC_IMMAGINE * 2.5)]   # un visivo = un disegno; i tagli ogni 4 s li fa il montaggio
    regola_pg = ("il personaggio deve essere uno di quelli DISEGNATI DENTRO quell'immagine (campo personaggi dell'immagine), oppure \"\"" if INTEGRATO
                 else '"reazione": true se a meta\' il personaggio cambia posa (momento forte)')
    if INTEGRATO:
        blocco_sfondi = (f"IMMAGINI A CARTONE (campo \"sfondi\"): definisci esattamente {n_sf} immagini disegnate, nell'ORDINE del racconto (s1 = inizio, s{n_sf} = fine), "
            "TUTTE DIVERSE tra loro: scene VIVE con persone che fanno qualcosa (re sul trono, soldati in marcia, mercanti al mercato, contadini nei campi, "
            "una battaglia, una nave che parte, una folla in piazza, un dettaglio ravvicinato di mani, volti, oggetti), di giorno, al tramonto, di notte, campi larghi e primi piani. "
            "Ogni immagine: \"id\" (s1..), \"prompt_en\" (in inglese, 25-45 parole: luogo, epoca, chi c'e', cosa fa, emozione, inquadratura; vestiti e oggetti SEMPRE corretti per l'epoca e il popolo, mai nulla di moderno) "
            "e \"personaggi\": lista (0-2) di personaggi della lista del kit che compaiono DENTRO l'immagine (verranno disegnati identici al kit). "
            "Un personaggio storico con NOME compare solo nelle immagini usate mentre la voce parla di lui; le persone generiche senza personaggio nel kit descrivile nel prompt_en (popolo, epoca, vestiti). "
            "Le persone hanno SEMPRE l'aspetto, il colore della pelle e i vestiti del POPOLO del paese raccontato in quell'epoca (es. indiani in India, persiani in Iran): mai europei o asiatici dell'est se non sono loro i protagonisti. "
            "OGNI IMMAGINE E' PENSATA PER UNA SOLA FRASE: il visivo 'cartone' che la usa ha come frase esattamente cio' che l'immagine mostra (se la frase dice verde dal mare al mare, l'immagine mostra campi verdi dal mare al mare). "
            "Ogni immagine si usa UNA sola volta in tutto il video.")
    else:
        blocco_sfondi = (f"SFONDI: definisci esattamente {n_sf} sfondi a cartone (luoghi ed epoche del paese nell'ordine del racconto, SENZA persone), TUTTI DIVERSI tra loro: "
            "citta', palazzi, interni, campi di battaglia vuoti, porti, deserti, montagne, templi, mercati vuoti, strade, di giorno, al tramonto, di notte, campi larghi e scorci ravvicinati. "
            f"Ogni sfondo: \"id\" (s1..s{n_sf}) e \"prompt_en\" (descrizione in inglese del luogo e dell'epoca, 20-35 parole).")
    blocco_originale = ''
    if comp.get('titolo'):
        blocco_originale += f'''
VIDEO ORIGINALE DA COPIARE: "{comp['titolo']}".
- "titolo": ''' + (f"e' la TRADUZIONE FEDELE al 100% del titolo originale in {lingua} (stessa struttura, stessi numeri e date, stesse parole in maiuscolo), adattata solo dove serve per suonare naturale." if TIT_COPIA >= 100 else
       f"tieni il {TIT_COPIA}% del titolo originale tradotto in {lingua} (stessa struttura, stesso argomento, stessi numeri e date) e cambia il restante {100 - TIT_COPIA}% per renderlo piu' forte e diverso: un'altra parola d'impatto, una promessa o un dettaglio di curiosita'. Mai un titolo identico all'originale.")
    if comp.get('tag_originali'):
        blocco_originale += f'''
TAG DEL COMPETITOR (da tradurre in {lingua} e mettere per primi nel campo "tag"): {', '.join(comp['tag_originali'])[:1500]}'''
    if orig:
        blocco_originale += f'''
- Il PARLATO deve COPIARE al 100% il testo originale qui sotto: stessi fatti, stesso ordine, stessi ganci, stesse domande, stessi numeri, stessa lunghezza.{' ECCEZIONE: l originale e troppo lungo, quindi CONDENSALO a circa ' + str(parole) + ' parole: stessi fatti principali, stesso ordine, stessi ganci e stesse domande, togli solo dettagli secondari ed esempi ripetuti.' if condensa else ''}
  Traducilo in {lingua} naturale e cambia solo piccole cose per non essere una copia identica (sinonimi, ordine delle parole, qualche frase unita o divisa). NON aggiungere contenuti{' e togli solo il secondario' if condensa else ' e NON toglierne'}.
  UNITA' DI MISURA: il pubblico e' {'italiano' if LINGUA == 'it' else 'del canale'}: {'converti SEMPRE le unita americane in quelle europee con numeri arrotondati (gradi Fahrenheit -> gradi Celsius, es. 120 gradi F = circa 50 gradi; miglia -> chilometri; piedi -> metri; pollici -> centimetri; libbre -> chili; galloni -> litri; acri -> ettari). Mai lasciare 120 gradi se erano Fahrenheit.' if LINGUA == 'it' else 'keep the units of the original.'}
TESTO ORIGINALE:
{orig[:60000]}
'''
    prompt = f"""Sei lo sceneggiatore e il regista di un canale YouTube di storia a cartone, nello stile di "Genius History" e "Rome Unscrolled".
Scrivi il video: "{TITOLO}". Lingua della voce e delle scritte: {lingua}. Lunghezza totale del parlato: circa {parole} parole.
{blocco_originale}
STILE DEL RACCONTO: dall'inizio della storia del paese fino a oggi, in ordine cronologico, con date precise, fatti veri, nomi veri.
Frasi brevi e concrete, ritmo da documentario coinvolgente, piccole domande e colpi di scena. Prima scena = gancio forte. Ultima scena = chiusura che fa riflettere.

REGIA VISIVA: ogni scena (20-40 parole di voce) ha 2-5 "visivi". RITMO (fondamentale per trattenere lo spettatore):
- primi 10 secondi (prime ~25 parole): un visivo nuovo ogni ~{w[0]} parole, alternando cartone e immagini vere;
- da 10 a 30 secondi: un visivo ogni ~{w[1]} parole;
- poi un visivo ogni ~{w[2]} parole, MAI piu' di {w[2] + 2} parole sullo stesso visivo.
SORPRESA: lo spettatore deve sempre voler vedere cosa viene dopo: ogni visivo e' DIVERSO dal precedente (luogo, inquadratura, campo largo / dettaglio, giorno / notte, dentro / fuori); mai la stessa immagine due volte vicine.
Il PRIMO visivo del video e' sempre un "cartone" con un personaggio.
SINCRONIA CON LA VOCE (FONDAMENTALE): ogni visivo ha il campo "frase" = 2-4 parole COPIATE IDENTICHE dal "testo" della scena, nel punto esatto in cui il visivo deve comparire. I visivi sono nello stesso ordine delle loro frasi nel testo, a distanza di almeno 4 parole l'uno dall'altro. Il primo visivo ha come frase le prime parole della scena.
- una "carta" compare quando la voce dice quella frase: il suo "testo" riprende parole DETTE in quella scena e la sua "frase" e' l'inizio di quelle parole nel testo;
- una "scheda" SOLO nella scena in cui quel personaggio viene NOMINATO dalla voce, con frase = il nome cosi' come detto;
- un "cartone" con un personaggio storico reale SOLO quando viene nominato (frase = il nome); quando non si nomina nessuno usa SEMPRE una figura generica della lista (soldato, contadino, nobile...) coerente con cio' che si dice: ogni cartone ha un personaggio; se nella lista NON c'e' un personaggio coerente con cio' che la voce dice in quel momento, NON mettere un personaggio sbagliato: usa un "pexels_video", un "pexels_foto" o una "carta" (e segna la figura in "personaggi_mancanti"); il personaggio deve essere SEMPRE della stessa EPOCA e dello stesso popolo di cio' che si racconta (mai un generale in divisa moderna per l'antichita', mai un cavaliere medievale europeo per la Persia antica);
- un "pexels" deve mostrare cio' che la voce dice in quel momento, nel LUOGO giusto (paesaggi del paese raccontato: deserto, altopiano, montagne, mari di QUEL paese; mai colline verdi europee per un paese desertico). Le PERSONE si mostrano SOLO con i cartoni: nelle ricerche Pexels mai persone, soldati, guerrieri, cavalieri, eserciti, folle o rievocazioni (su Pexels sono sempre persone di oggi).
Tipi:
- "cartone": scena disegnata. Campi: "sfondo" (id di una delle immagini a cartone; ognuna al massimo 2 volte in tutto il video e mai in due scene vicine), "personaggio" (SOLO uno di questa lista, oppure "" per nessuno): {lista_kit(kit)}; {regola_pg}. Nella PRIMA scena il primo visivo e' un cartone con il campo "data" (es. "550 a.C.").
- "pexels_video": clip vera. Campo "q": ricerca Pexels in INGLESE, 2-4 parole concrete che diano immagini SENZA cose moderne: paesaggi naturali, montagne, deserti, rovine, monumenti antichi, oggetti antichi, monete, manoscritti, armi antiche in museo, fuoco, cielo, mare. MAI persone (nemmeno in costume), MAI citta' moderne (tranne nelle scene sul presente), MAI nomi di persone o eventi.
- "pexels_foto": foto vera. Campo "q" come sopra.
- SUONO (facoltativo, su qualsiasi visivo): campo "suono" = effetto sonoro da film IN INGLESE, 3-8 parole, coerente con cio' che si vede e si racconta (es. "swords clashing, distant battle shouts", "horses galloping on dry ground", "desert wind howling", "heavy rain and thunder", "wooden ship creaking, waves", "crackling fire", "crowd murmuring in ancient market", "propeller planes flying over", "old telephone ringing", "police sirens, city traffic"). Usalo con misura, solo nei momenti forti: circa 1-2 per minuto, mai due visivi di fila.
- DIDASCALIA (facoltativa, su "cartone", "pexels_video" o "pexels_foto"): campo "didascalia" = 2-6 parole chiave DETTE dalla voce in quel momento (es. "Ciro il Grande, 550 a.C.", "Il primo trattato della storia"). Compare su una striscia di carta strappata in basso, battuta a macchina. Usala spesso per dare ritmo: circa 1 visivo ogni 4-5, mai su due visivi di fila; mai su visivi piu' corti di 2 secondi di parlato.
- "carta": frase chiave scritta su carta. Campo "testo": max 8 parole, la frase piu' forte del momento.
- "scheda": presentazione di un personaggio storico. Campi "personaggio" (dalla lista) e "nome" (nome vero completo).
- "mappa": zoom sulla mappa del paese con titolo e date (usala UNA volta, nella seconda scena).
Proporzioni su tutto il video: circa {QUOTA_CARTONI}% cartone e {100 - QUOTA_CARTONI}% immagini vere ({(100 - QUOTA_CARTONI) // 2}% pexels_video, {(100 - QUOTA_CARTONI) - (100 - QUOTA_CARTONI) // 2}% pexels_foto); carte, schede e mappa sono in piu' e rare. Alterna cartone e immagini vere: mai due visivi uguali di fila.
CAPITOLI YOUTUBE: dividi il video in 6-10 capitoli seguendo le grandi fasi della storia (epoche, imperi, svolte); la PRIMA scena ha sempre il campo "capitolo".
CARTE: al massimo 2 al minuto di parlato (circa 1 visivo "carta" ogni 15 visivi): solo le frasi piu' forti.
IDENTITA' DEI PERSONAGGI: un personaggio della lista usato per una persona con NOME (es. cavaliere_mongolo = Gengis Khan, re_antico = Dario I) resta quella persona per TUTTO il video: non usarlo mai per un'altra persona o come figura generica. Per persone diverse senza personaggio adatto usa pexels o carta.

FONDI DELLE CARTE: definisci 3 "fondi_carte" per le scritte e le schede: decorazioni a tema del video SOLO ai bordi (rovine, colonne, rami, motivi decorativi, skyline dell'epoca) e CENTRO VUOTO e uniforme. Ogni fondo: "id" (c1..c3) e "prompt_en" (20-35 parole: colori, cosa c'e' ai bordi, colore del centro; varia i colori tra i 3: es. carta antica, toni caldi, toni scuri).
"colori_carte": 2 colori esadecimali scuri ed eleganti coerenti con il tema (es. rosso persiano "#6b1e1e", blu lapislazzuli "#1d3557").
"font_carte": il carattere delle scritte, coerente con l'epoca PRINCIPALE del video: "antico" (Roma, Grecia, Persia, Egitto, antichita'), "medievale" (500-1700), "ottocento" (1700-1900), "macchina" (1900-1960, guerre), "moderno" (dal 1960 a oggi), "classico" (storia lunga di un paese dall'antichita' a oggi, se nessuno prevale).

{blocco_sfondi}

Rispondi SOLO con un JSON valido, senza testo prima o dopo:
{{"titolo": "...", "titolo_mappa": "nome del paese da scrivere sulla mappa, nella lingua del canale, es. IRAN", "paese_mappa": "nome del paese in inglese come in Natural Earth (es. Iran, India, Egypt, United States of America)",
 "date": "es. 550 a.C. – 2026", "texture": "pergamena|washi|stropicciata|giornale|papiro", "font_carte": "antico|medievale|ottocento|macchina|moderno|classico",
 "fondi_carte": [{{"id": "c1", "prompt_en": "..."}}], "colori_carte": ["#......", "#......"],
 "sfondi": [{{"id": "s1", "prompt_en": "...", "personaggi": []}}],
 "scene": [{{"capitolo": "SOLO nella prima scena di ogni capitolo: titolo breve del capitolo in {lingua} (2-5 parole, es. 'Le origini', 'L'impero di Ciro'); nelle altre scene ometti il campo", "testo": "parlato della scena", "visivi": [{{"tipo": "cartone", "frase": "prime parole della scena", "sfondo": "s1", "personaggio": "...", "reazione": true, "data": "...", "suono": "..."}}]}}],
 "copertina": {{"testo": "testo della copertina originale TRADOTTO al 100% (stesse parole, stesse date), MAIUSCOLO", "personaggio": "SOLO se nella lista c'e' la STESSA figura della copertina originale o una dello stesso popolo, epoca e aspetto (es. re persiano antico -> ciro_il_grande; MAI un re europeo per la Persia). Se non c'e' una corrispondenza sicura: '' (la figura originale verra' ridisegnata a cartone)"}},
 "descrizione": "descrizione YouTube in {lingua}: 3 paragrafi brevi (circa 120 parole) che riassumono il video con le parole che la gente cerca, poi una riga con 4-6 hashtag",
 "tag": ["25-35 tag YouTube in {lingua}: PRIMA tutti i TAG DEL COMPETITOR (se ci sono) tradotti in {lingua} nello stesso ordine (nomi propri invariati, togli solo nomi di altri canali), POI aggiungi i nostri tag validi: paese, impero, epoche, personaggi, 'storia di ...', 'storia completa'"],
 "personaggi_mancanti": ["figure che sarebbero servite ma non sono nella lista, es. 'Dario I re persiano'"]}}
Scegli la texture piu' coerente (washi per Giappone/Cina/Corea, papiro per Egitto/Mesopotamia, pergamena per antichita'/medioevo, giornale per 1800-1900, stropicciata per storia moderna)."""
    prompt += regole_finali(n_sf)
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        raise RuntimeError('manca il secret ANTHROPIC_API_KEY')
    for k in range(3):
        try:
            contenuto = [{'type': 'text', 'text': prompt}]
            if comp.get('copertina'):
                contenuto.insert(0, {'type': 'image', 'source': {'type': 'url', 'url': comp['copertina']}})
                contenuto.insert(1, {'type': 'text', 'text': 'Questa sopra e\' la COPERTINA del video originale.'})
            richiesta = {'model': MODELLO_AI if k < 2 else MODELLO_RISERVA, 'max_tokens': 64000, 'messages': [{'role': 'user', 'content': contenuto}]}
            if 'sonnet-5' in richiesta['model']:   # poco ragionamento: i token servono al copione lungo (prima finivano a meta')
                richiesta.update(thinking={'type': 'between_tools'}, output_config={'effort': 'low'})
            testo, fine = claude_stream(richiesta, chiave)
            if '{' not in testo:
                raise ValueError(f'risposta senza JSON (stop: {fine}, {len(testo)} caratteri): {testo[:200]!r}')
            testo = testo[testo.find('{'): testo.rfind('}') + 1]
            c = json.loads(testo)
            assert c.get('scene') and c.get('sfondi')
            return c
        except Exception as e:
            log('copione non valido, riprovo:', str(e)[:200]); time.sleep(5)
    raise RuntimeError('copione non riuscito')


MODELLO_RISERVA = E('MODELLO_RISERVA', 'claude-opus-5-5')


def claude_stream(payload, chiave, timeout=600):
    """Chiamata a Claude in streaming: per le risposte lunghe (copione di 15-25 minuti) la connessione non resta mai ferma,
    cosi' non viene chiusa a meta' (prima arrivava una risposta vuota -> 'Expecting value')."""
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(dict(senza_ragionamento(payload), stream=True)).encode(),
                                 headers={'content-type': 'application/json', 'x-api-key': chiave, 'anthropic-version': '2023-06-01'})
    pezzi, fine, pensiero = [], '', [0]
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for riga in r:
            riga = riga.decode('utf-8', 'ignore').strip()
            if not riga.startswith('data:'):
                continue
            try:
                ev = json.loads(riga[5:].strip())
            except Exception:
                continue
            if ev.get('type') == 'content_block_delta' and (ev.get('delta') or {}).get('type') == 'text_delta':
                pezzi.append(ev['delta'].get('text', ''))
            elif ev.get('type') == 'content_block_delta' and (ev.get('delta') or {}).get('type') == 'thinking_delta':
                pensiero[0] += 1
            elif ev.get('type') == 'message_delta':
                fine = (ev.get('delta') or {}).get('stop_reason') or fine
            elif ev.get('type') == 'error':
                raise RuntimeError('Claude: ' + json.dumps(ev.get('error'))[:200])
    testo = ''.join(pezzi)
    log('copione ricevuto:', len(testo), 'caratteri, fine:', fine, '| blocchi di ragionamento:', pensiero[0])
    return testo, fine


# ============================================================ 2) VOCE
def voce(i, testo, prima='', dopo='', velocita=None):
    p = os.path.join(LAV, f'voce_{i:03d}.mp3')
    if velocita is None and os.path.exists(p) and os.path.getsize(p) > 1000 and os.path.exists(p[:-4] + '.json'):
        return p   # ripresa: voce gia' pagata
    chiave = E('ELEVENLABS_API_KEY', '')
    if not chiave:   # prova senza chiave: silenzio della durata giusta
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', max(1.5, len(testo.split()) * .42), p])
        return p
    for k in range(4):
        try:
            # with-timestamps: stesso prezzo, in piu' restituisce QUANDO viene detta ogni lettera -> immagini a tempo con la voce
            j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_128',
                     {'text': testo, 'model_id': E('VOCE_MODELLO', 'eleven_multilingual_v2'),
                      'previous_text': prima[-400:], 'next_text': dopo[:400],   # stessa intonazione tra una scena e l'altra
                      'voice_settings': dict({'stability': .5, 'similarity_boost': .75}, speed=velocita or VOCE_VELOCITA)},
                     {'xi-api-key': chiave})
            open(p, 'wb').write(base64.b64decode(j['audio_base64']))
            json.dump(j.get('alignment') or {}, open(p[:-4] + '.json', 'w'))
            return p
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(4 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


_U = ['zero', 'uno', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette', 'otto', 'nove', 'dieci', 'undici', 'dodici', 'tredici',
      'quattordici', 'quindici', 'sedici', 'diciassette', 'diciotto', 'diciannove']
_D = ['', '', 'venti', 'trenta', 'quaranta', 'cinquanta', 'sessanta', 'settanta', 'ottanta', 'novanta']
_ORD = ['', 'primo', 'secondo', 'terzo', 'quarto', 'quinto', 'sesto', 'settimo', 'ottavo', 'nono', 'decimo', 'undicesimo', 'dodicesimo',
        'tredicesimo', 'quattordicesimo', 'quindicesimo', 'sedicesimo', 'diciassettesimo', 'diciottesimo', 'diciannovesimo', 'ventesimo', 'ventunesimo']


def num_it(n):
    """Numero intero in lettere, in italiano corretto (2500 -> duemilacinquecento, 1945 -> millenovecentoquarantacinque)."""
    n = int(n)
    if n < 20:
        return _U[n]
    if n < 100:
        d, u = divmod(n, 10); t = _D[d]
        if u in (1, 8):
            t = t[:-1]
        return t + ('' if u == 0 else ('tre' if u == 3 else _U[u]))
    if n < 1000:
        c, r = divmod(n, 100); t = 'cento' if c == 1 else _U[c] + 'cento'
        if r and (r // 10 == 8 or r == 8):
            t = t[:-1]
        return t + (num_it(r) if r else '')
    if n < 1000000:
        m, r = divmod(n, 1000)
        return ('mille' if m == 1 else num_it(m) + 'mila') + (num_it(r) if r else '')
    if n < 1000000000:
        m, r = divmod(n, 1000000)
        return ('un milione' if m == 1 else num_it(m) + ' milioni') + ((' ' + ('e ' if r < 1000 else '') + num_it(r)) if r else '')
    m, r = divmod(n, 1000000000)
    return ('un miliardo' if m == 1 else num_it(m) + ' miliardi') + ((' ' + num_it(r)) if r else '')


def parlato(t):
    """Testo per la VOCE: numeri, date e sigle scritti come si dicono (sullo schermo restano le cifre)."""
    if LINGUA != 'it' or not t:
        return t
    t = re.sub(r'\b([IVX]{1,5})\s+(secolo|sec\.)', lambda m: (_ORD[roman(m.group(1))] if 0 < roman(m.group(1)) < len(_ORD) else m.group(1)) + ' secolo', t)
    t = re.sub(r'\b([A-Z][a-zà-ÿ]+) (II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI)\b', lambda m: m.group(1) + ' ' + _ORD[roman(m.group(2))], t)
    t = re.sub(r'\ba\.\s?C\.', 'avanti Cristo', t); t = re.sub(r'\bd\.\s?C\.', 'dopo Cristo', t)
    t = re.sub(r'(\d)\s*%', r'\1 per cento', t)
    t = re.sub(r'(\d)\s*°\s*C\b', r'\1 gradi', t); t = re.sub(r'(\d)\s*°', r'\1 gradi', t)
    t = re.sub(r'(\d)\s*km\b', r'\1 chilometri', t); t = re.sub(r'(\d)\s*kg\b', r'\1 chili', t)
    t = re.sub(r'\b\d{1,3}(?:[.\u202f ]\d{3})+\b', lambda m: re.sub(r'\D', '', m.group()), t)   # 2.500 -> 2500
    t = re.sub(r'\b(\d+),(\d+)\b', lambda m: num_it(int(m.group(1))) + ' virgola ' + (num_it(int(m.group(2))) if not m.group(2).startswith('0') else ' '.join(_U[int(x)] for x in m.group(2))), t)
    t = re.sub(r'\b\d+\b', lambda m: num_it(int(m.group())) if len(m.group()) <= 12 else m.group(), t)
    t = re.sub(r'\buno (milion|miliard)', r'un \1', t)
    return t


def roman(r):
    v = {'I': 1, 'V': 5, 'X': 10}; tot = 0
    for i, ch in enumerate(r):
        x = v.get(ch, 0); tot += -x if i + 1 < len(r) and v.get(r[i + 1], 0) > x else x
    return tot


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
_riserva = {}
VIETATE = ('firefighter', 'fire-fighter', 'jakarta', 'police', 'car', 'cars', 'traffic', 'phone', 'smartphone', 'laptop', 'computer',
           'office', 'selfie', 'tourist', 'tourists', 'christmas', 'birthday', 'party', 'card', 'greeting', 'happy', 'neon', 'logo',
           'text', 'sign', 'shopping', 'mall', 'airport', 'airplane', 'truck', 'bus', 'motorcycle', 'gym', 'fitness', 'model', 'fashion',
           'wedding', 'coffee', 'restaurant', 'supermarket', 'construction', 'vaccine', 'mask', 'covid', 'nowruz', 'football', 'soccer',
           # persone di oggi: nelle clip di storia non devono comparire (restano le rievocazioni in costume, controllate da Claude)
           'man', 'men', 'woman', 'women', 'person', 'people', 'girl', 'girls', 'boy', 'boys', 'guy', 'lady', 'child', 'children', 'kid',
           'kids', 'couple', 'family', 'friends', 'portrait', 'hiker', 'hiking', 'traveler', 'travelers', 'backpacker', 'photographer',
           'soldier', 'soldiers', 'knight', 'knights', 'warrior', 'warriors', 'reenactment', 'costume', 'parade', 'festival', 'army', 'crowd')
PAESE = {'nome': ''}
MODELLO_CONTROLLO = E('MODELLO_CONTROLLO', 'claude-haiku-4-5-20251001')


def pexels_cerca(tipo, q):
    k = (tipo, q.lower().strip())
    with _lock:
        if k in _cache:
            return _cache[k]
        if _conti['n'] >= PEXELS_MAX:
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
                        pics = [x.get('picture') for x in (v.get('video_pictures') or []) if x.get('picture')]
                        viste = [pics[int(i * (len(pics) - 1) / 3)] for i in range(4)] if len(pics) > 3 else [v.get('image') or ''] + pics
                        ris.append({'url': fs[0]['link'], 'anteprima': v.get('image') or '', 'viste': [x for x in viste if x],
                                    'desc': (v.get('url') or '').lower()})
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
    def b64(u):   # scarichiamo noi l'anteprima (Pexels blocca i download fatti da altri server) e la mandiamo come immagine
        try:
            im = Image.open(io.BytesIO(http(u, raw=True, timeout=30))).convert('RGB'); im.thumbnail((384, 384))
            buf = io.BytesIO(); im.save(buf, 'JPEG', quality=80)
            return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}
        except Exception:
            return None
    cont, validi = [], 0
    for i, c in enumerate(candidati):   # per le clip: inizio, meta' e fine (una persona puo' entrare dopo)
        with ThreadPoolExecutor(3) as ex:
            imgs = [x for x in ex.map(b64, (c.get('viste') or [c['anteprima']])[:3]) if x]
        if imgs:
            validi += 1
        cont += [{'type': 'text', 'text': f'Immagine {i}:' + ('' if imgs else ' (anteprima non disponibile: SCARTALA)')}] + imgs
    if not validi:
        log('Pexels: nessuna anteprima scaricabile per', q); return -1
    cont.append({'type': 'text', 'text': f"""Video di storia sul paese: {PAESE.get('nome') or 'vedi testo'}. La voce in questo momento dice: "{contesto[:400]}". Ricerca usata: "{q}".
Quale immagine e' adatta da mostrare? Deve sembrare coerente con l'epoca e il luogo raccontati.
Se un'immagine ha piu' fotogrammi (stessa clip), giudicali TUTTI: basta un fotogramma sbagliato per scartarla.
COERENZA: se la voce parla di un popolo o di un luogo preciso (es. gli arabi, l'Iran, il deserto), l'immagine deve essere di QUEL luogo/popolo; paesaggi di un altro continente o clima vanno SCARTATI.
SCARTA SEMPRE: qualsiasi persona (anche in costume medievale o storico), citta' moderne, palazzi moderni, lampioni, cavi elettrici, cartelli, folle; qualsiasi persona di oggi, anche piccola, lontana, di spalle o in mezzo a rovine (giacche, felpe, jeans, scarpe da ginnastica, zaini, turisti); auto, cellulari, cartelli o scritte leggibili, biglietti di auguri, oggetti di plastica, feste moderne, cose fuori tema.
VANNO BENE: paesaggi, montagne, deserti, rovine, monumenti antichi, musei, oggetti antichi, monete, manoscritti, fuoco, cieli, mare, armi antiche in museo. NESSUNA persona: le persone nel video sono solo disegnate.
Per il LUOGO basta che sia plausibile per quel paese (montagne, deserti, rovine, cieli vanno bene se il clima e' simile); scarta solo cio' che e' chiaramente di un altro mondo (es. colline verdi alpine per un deserto, palme tropicali, citta' europee).
Ragiona in breve (max 2 righe) e poi chiudi con una riga ESATTAMENTE cosi': SCELTA: <numero della prima immagine adatta, oppure -1 se nessuna va bene>"""})
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_PEXELS', '') or MODELLO_CONTROLLO, 'max_tokens': 300, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        txt = ''.join(b.get('text', '') for b in r.get('content', []))
        m = re.search(r'SCELTA:\s*(-?\d+)', txt) or re.search(r'(-?\d+)\s*$', txt.strip())
        n = int(m.group(1)) if m else -1
        if not m:
            log('Pexels: risposta non chiara:', txt[-150:])
        log('Pexels', repr(q), '->', 'scartate tutte' if n < 0 else f'scelta {n}')
        return n if -1 <= n < len(candidati) else -1
    except Exception as e:   # senza controllo NON si usa nessuna immagine (meglio un cartone che una persona di oggi)
        log('controllo Pexels non riuscito, immagine NON usata:', str(e)[:200])
        return -1


def pexels(tipo, q, contesto=''):
    for qq in (q, q + ' ancient'):   # niente ricerche generiche di riserva: se non c'e' un'immagine giusta si usa un cartone
        tutti = pexels_cerca(tipo, qq)   # ricerca FUORI dal lucchetto (prima qui si bloccava tutto)
        with _lock:
            cand = [c for c in tutti if c['url'] not in _usati][:4]
        if not cand:
            continue
        i = controlla(cand, qq, contesto)
        if i >= 0:
            with _lock:
                _usati.add(cand[i]['url'])
            return cand[i]['url']
        log('Pexels scartate tutte per:', qq)
    return None


def regole_finali(n_sf):
    """Regole che prevalgono su tutto il resto del prompt (canale Storia: solo disegni, nessuna texture)."""
    r = ["\n\nREGOLE FINALI (PREVALGONO su tutto quello scritto sopra):",
         "- PERSONE: in ogni immagine compaiono SOLO persone del popolo e dell'epoca di cui parla la voce in quel momento. "
         "Quando la voce cita studiosi, geologi, scienziati, archeologi o scoperte moderne, NON disegnare loro: mostra la cosa (la grotta, la stalagmite, il reperto, la rovina) "
         "oppure le persone ANTICHE di cui si parla. Abiti moderni o dell'800 (giacca, cravatta, panciotto) SOLO se la scena e' ambientata esplicitamente in quell'epoca.",
         f"- IMMAGINI MAI RIPETUTE: ogni visivo \"cartone\" usa un'immagine DIVERSA (s1, s2, s3... in ordine, ognuna UNA sola volta). I visivi cartone sono quindi al massimo {n_sf}: "
         "se la scena e' lunga, il visivo dura di piu' (gli stacchi li fa il montaggio). Mai la stessa immagine in due visivi."]
    if BUDGET > 0:
        r.append(f"- DISEGNI CONTATI: esattamente {n_sf} visivi \"cartone\" in tutto il video, ognuno con la SUA immagine (s1..s{n_sf}, in ordine, mai ripetute). "
                 "Mettine 3 nei primi 30 secondi (il gancio); gli altri SOLO dove la voce parla di PERSONE (re, battaglie, popolo, mercati, eventi), distribuiti su tutto il video. "
                 "Un cartone dura 6-9 secondi di voce (15-22 parole).")
        r.append("- TUTTO IL RESTO e' Pexels: preferisci \"pexels_video\" (clip), \"pexels_foto\" solo se serve un oggetto preciso. Un visivo pexels ogni 10-14 parole. "
                 "Campo \"q\": 3-5 parole in INGLESE con il LUOGO del paese + la COSA CONCRETA che la voce dice in quel momento "
                 "(es. voce 'i monsoni portano la pioggia' -> 'monsoon rain India fields'; 'il fiume Gange' -> 'Ganges river Varanasi'; 'templi di pietra' -> 'ancient stone temple India'). "
                 "Mai persone, soldati, folle, feste, citta' moderne (tranne quando la voce parla di oggi). Visivi vicini = cose diverse (fiume, poi montagna, poi rovina, poi cielo).")
        r.append("- Aggiungi in cima al JSON il campo \"riserva_pexels\": 8 ricerche Pexels generiche ma tipiche del paese (paesaggi, fiumi, montagne, monumenti antichi, cielo), per quando una ricerca non trova niente.")
    elif QUOTA_CARTONI >= 100:
        r.append("- SOLO DISEGNI: usa solo \"cartone\" e una \"mappa\". Niente pexels_video e pexels_foto.")
    if not TEXTURE:
        r.append("- NIENTE SCRITTE SU CARTA: non usare i tipi \"carta\" e \"scheda\". \"fondi_carte\" = [].")
        r.append("- SOVRIMPRESSIONE (campo \"didascalia\"): SOLO su visivi pexels_video / pexels_foto e SOLO quando la voce in quel momento dice un NUMERO, una DATA o una misura "
                 "(es. '70% delle piogge in 4 mesi', 'Oltre 50 gradi', '4.200 anni fa', '1,5 miliardi di persone'). 2-6 parole, UNA sola informazione, con il numero scritto in cifre. "
                 "Al massimo 1 ogni 4 visivi pexels, mai su due visivi di fila, mai sui cartoni. Se non c'e' un numero, niente didascalia.")
    return '\n'.join(r)


def togli_texture(piano):
    """Canale senza texture: carte e schede diventano il disegno della stessa scena (quello prima o dopo), via le strisce di carta."""
    if TEXTURE:
        return
    n, t, ultima = 0, 0.0, -1e9
    for i, v in enumerate(piano):
        did = str(v.get('didascalia') or '').strip()
        tiene = (did and v['tipo'] in ('pexels_video', 'pexels_foto') and re.search(r'\d', did) and len(did.split()) <= 7
                 and v.get('d', 0) >= 2.5 and t - ultima >= 12)
        if tiene:
            ultima = t
        else:
            v.pop('didascalia', None)
        t += v.get('d', 0)
        if v['tipo'] in ('carta', 'scheda'):
            vicino = next((x for x in list(reversed(piano[:i])) + piano[i + 1:] if x['tipo'] == 'cartone' and x.get('sfondo')
                           and x.get('contesto') == v.get('contesto')), None) or \
                next((x for x in reversed(piano[:i]) if x['tipo'] == 'cartone' and x.get('sfondo')), None)
            for k_ in ('testo', 'nome', 'fondo'):
                v.pop(k_, None)
            if vicino:
                v.update({'tipo': 'cartone', 'sfondo': vicino['sfondo'], 'personaggio': vicino.get('personaggio') or ''})
            else:
                v.update({'tipo': 'cartone', 'personaggio': ''})
            n += 1
    log(f'senza texture: {n} carte/schede diventate disegni, strisce di carta tolte')


BORDO = int(float(str(P.get('cornice_bordo') or E('CORNICE_BORDO', '') or 0.055).replace(',', '.')) * H)   # spessore uguale sui 4 lati (5,5% dell'altezza)


def crea_cornice(paese, epoca=''):
    """Cornice come quella di un quadro: STESSO spessore sui 4 lati, decorata con i motivi tipici del paese.
    Nano Banana disegna solo il MOTIVO (a tutta pagina); la cornice la ritaglia lo script: cosi' non puo' uscire bianca o storta."""
    p = os.path.join(LAV, 'cornice.png')
    if os.path.exists(p) and os.path.exists(p + '.json'):
        return p, tuple(json.load(open(p + '.json')))
    b = BORDO
    for tentativo in range(2):
        prompt = (f"Dense decorative ornamental pattern typical of the traditional art and architecture of {paese}{(' (' + epoca + ')') if epoca else ''}: "
                  f"the motifs, carvings, colours and materials of that culture, like a richly carved and painted picture-frame moulding. "
                  "The pattern FILLS THE WHOLE IMAGE edge to edge, rich saturated colours (no white, no plain areas, no empty background), "
                  "flat front view, high detail. No text, no letters, no logo, no watermark."
                  + (" Use deep, warm, strong colours." if tentativo else ''))
        r = fal('fal-ai/nano-banana-2', {'prompt': prompt, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'png', 'num_images': 1})
        grezza = os.path.join(LAV, 'cornice_motivo.png')
        scarica(r['images'][0]['url'], grezza)
        im = Image.open(grezza).convert('RGB').resize((W, H), Image.LANCZOS)
        a = np.asarray(im).astype(float)
        fascia = np.concatenate([a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)])
        luce, varia = fascia.mean(), fascia.std()
        if 35 < luce < 200 and varia > 22:   # colorata e decorata: niente bianco, niente tinta unita
            break
        log(f'motivo cornice scartato (luce {luce:.0f}, varieta {varia:.0f}), lo rifaccio')
    alfa = np.full((H, W), 255, np.uint8); alfa[b:H - b, b:W - b] = 0
    out = Image.fromarray(np.dstack([np.asarray(im), alfa]).astype(np.uint8), 'RGBA')
    d = ImageDraw.Draw(out)   # profili come un quadro: filo scuro esterno, filo oro e ombra sul bordo interno
    d.rectangle([0, 0, W - 1, H - 1], outline=(25, 18, 10, 255), width=4)
    d.rectangle([b - 6, b - 6, W - b + 5, H - b + 5], outline=(25, 18, 10, 255), width=3)
    d.rectangle([b - 3, b - 3, W - b + 2, H - b + 2], outline=(212, 175, 55, 255), width=3)
    out.save(p); json.dump([b, b], open(p + '.json', 'w'))
    log(f'cornice di {paese} pronta: bordo {b} px su tutti i lati')
    return p, (b, b)


def applica_cornice(video, c):
    """Il video dentro la cornice: bordo uguale sui 4 lati. Il video si rimpicciolisce e si rifila appena sopra e sotto (~3%)."""
    if not CORNICE or not E('FAL_KEY'):
        return video
    try:
        png, (bx, by) = crea_cornice(c.get('paese_mappa') or PAESE.get('nome') or TITOLO, c.get('date') or '')
        out = video[:-4] + '_cornice.mp4'
        iw, ih = W - 2 * bx, H - 2 * by
        iw -= iw % 2; ih -= ih % 2
        run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-loop', '1', '-framerate', FPS, '-i', png, '-filter_complex',
             f'color=c=black:s={W}x{H}:r={FPS}[n];[0:v]scale={iw}:{ih}:force_original_aspect_ratio=increase,crop={iw}:{ih},setsar=1[v];'
             f'[n][v]overlay=x={(W - iw) // 2}:y={(H - ih) // 2}:shortest=1[b];'
             f'[b][1:v]overlay=0:0:shortest=1,format=yuv420p[o]', '-map', '[o]', '-an', *ENC, out])
        return out
    except Exception as e:
        log('cornice saltata:', str(e)[:200]); return video


# ============================================================ 4) SFONDI (Fal)
STILE_SCENA = ('Wide 2D cartoon illustration for an animated history video, clean thick black outlines, flat warm colours with soft simple shading, '
               'like a modern illustrated history book, rich detail, cinematic composition. All people are drawn in the SAME cartoon style, with expressive faces, '
               'clothes, hair, weapons and objects historically correct for the era and the people described: nothing modern. '
               'Never people in suits, jackets, ties, waistcoats, lab coats or 19th/20th-century clothes (no scientists, scholars, explorers, tourists) unless the scene is explicitly set in that period. '
               'People look like the local population of the country being told (skin tone, faces, clothes), never Europeans unless stated. '
               'No text, no letters, no signs with writing, no logos, no watermark, no frame, no border.')
_ref_url = {}


def ref_personaggio(pg):
    with _lock:
        if pg in _ref_url:
            return _ref_url[pg]
    f = png_personaggio(pg, 'fermo')
    if not f:
        return None
    im = Image.open(f).convert('RGBA'); bg = Image.new('RGB', im.size, 'white'); bg.paste(im, (0, 0), im)   # fondo bianco: Nano Banana lo legge meglio
    j = os.path.join(LAV, f'ref_{pg}.jpg'); bg.save(j, quality=92)
    u = carica_fal(j, 'image/jpeg')
    with _lock:
        _ref_url[pg] = u
    return u


STILE_SFONDO = ('Wide 2D cartoon illustration for an animated history video, clean thick black outlines, flat warm colours with soft simple shading, '
                'like a modern illustrated history book, rich detail. The scene is EMPTY: absolutely no people, no animals in the foreground. '
                'The lower 30% of the image is open flat ground. No text, no letters, no signs with writing, no logos, no watermark.')


def fal(modello, dati):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    with _lock:
        SPESA['fal'] += (PREZZO_DISEGNO if str(dati.get('resolution')) == '2K' else 0.08) if 'nano-banana' in modello else 0.04
        SPESA['disegni'] += 1
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
    dati = {'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1}
    if INTEGRATO:   # come PRODUCTION: i personaggi sono DENTRO la scena (stessa luce, stessa azione), identici al kit
        refs = []
        for pg in (SF_META.get(s['id']) or [])[:2]:
            try:
                u = ref_personaggio(pg)
                if u:
                    refs.append(u)
            except Exception as e:
                log('riferimento personaggio non caricato:', pg, str(e)[:100])
        prompt = s['prompt_en'] + '. ' + STILE_SCENA
        if refs:
            prompt = ('The character' + ('s' if len(refs) > 1 else '') + ' of the reference image' + ('s' if len(refs) > 1 else '') +
                      ' must appear INSIDE this scene, kept IDENTICAL (same face, same body, same clothes, same drawing style), acting naturally in the scene. '
                      'Do not copy the white background of the reference. Scene: ' + prompt)
            r = fal('fal-ai/nano-banana-2/edit', dict(dati, prompt=prompt, image_urls=refs))
        else:
            r = fal('fal-ai/nano-banana-2', dict(dati, prompt=prompt))
    else:
        r = fal('fal-ai/nano-banana-2', dict(dati, prompt=s['prompt_en'] + ' ' + STILE_SFONDO))
    scarica(r['images'][0]['url'], p)
    shutil.copy(p, p[:-4] + '_full.jpg')   # originale 2K: serve per gli zoom (vista a sinistra / a destra) senza sgranare
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


STILE_COP = {
    'cartone': 'redrawn as a high-quality 2D cartoon illustration with clean black outlines and rich detail',
    'realistico': 'recreated as a photorealistic cinematic photograph, like a still from a big-budget historical film: real skin, real materials, dramatic light, no cartoon, no illustration',
}


LINGUA_NOME = {'it': 'italiano', 'en': 'English (US)'}.get(LINGUA, LINGUA)


def date_lingua(t):
    """In italiano: BC/BCE -> a.C., AD/CE -> d.C. (copertina e testi a schermo)."""
    if LINGUA != 'it' or not t:
        return t
    t = re.sub(r'\b(B\.?\s?C\.?\s?E\.?|B\.?\s?C\.?)(?![A-Za-z])', 'a.C.', t)
    t = re.sub(r'(?<=\d)\s*(A\.?\s?D\.?|C\.?\s?E\.?)(?![A-Za-z])', ' d.C.', t)
    return t


def analizza_copertina(comp, testo):
    """Copia al COP_COPIA%: Claude guarda la copertina del competitor e le migliori della nicchia e decide il cambio (pattern forte)."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave or COP_COPIA >= 100:
        return ''
    cont = [{'type': 'text', 'text': 'IMMAGINE 0 = copertina del video che copiamo.'}, {'type': 'image', 'source': {'type': 'url', 'url': comp['copertina']}}]
    for i, u in enumerate(RIFERIMENTI, 1):
        cont += [{'type': 'text', 'text': f'IMMAGINE {i} = copertina di successo della stessa nicchia.'}, {'type': 'image', 'source': {'type': 'url', 'url': u}}]
    cont.append({'type': 'text', 'text': f"""Dobbiamo rifare la copertina 0 per il nostro canale tenendo il {COP_COPIA}% IDENTICO (composizione, soggetto principale, colori, posizione e stile del testo) e cambiando il {100 - COP_COPIA}%.
Il cambio NON e' casuale: guarda le copertine 1-{len(RIFERIMENTI)} e trova i PATTERN che le rendono forti (es. un personaggio con emozione esagerata, una freccia o un cerchio rosso, un contrasto piu' forte, un oggetto simbolo in primo piano, una data o un numero evidenziato, un volto storico riconoscibile, fuoco/esplosione, mappa).
Scegli UNO o DUE di questi pattern che mancano nella copertina 0 e aggiungili al posto di elementi secondari, cosi' la copertina diventa piu' forte e abbastanza diversa da non essere una copia.
Il testo della copertina sara': "{testo}".
Se il cambio aggiunge o modifica una scritta (date, numeri, parole), deve essere nella lingua del canale ({LINGUA_NOME}): in italiano le date si scrivono "a.C." e "d.C." (es. "5000 a.C. → 2026"), MAI "BC", "AD", "BCE", "CE".
Rispondi SOLO con JSON: {{"tieni": "cosa resta uguale, in inglese, 1 frase", "cambia": "il cambio preciso da fare, in inglese, 1-2 frasi concrete per un generatore di immagini", "pattern": "nome breve del pattern usato, in italiano"}}"""})
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_AI, 'max_tokens': 600, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=300)
        t = ''.join(b.get('text', '') for b in r.get('content', []))
        j = json.loads(t[t.find('{'): t.rfind('}') + 1])
        open(os.path.join(ROOT, 'copertina_analisi.txt'), 'w').write(json.dumps(j, ensure_ascii=False, indent=1))
        log('copertina: pattern scelto ->', j.get('pattern'), '|', j.get('cambia'))
        return f"KEEP: {j.get('tieni', '')} CHANGE (about {100 - COP_COPIA}% of the image): {date_lingua(j.get('cambia', ''))} "
    except Exception as e:
        log('analisi copertina saltata:', str(e)[:200])
        return f'Change about {100 - COP_COPIA}% of the secondary elements (background details, small objects, camera angle) while keeping the main subject and layout. '


def copertina(comp, c):
    if not comp.get('copertina') or not E('FAL_KEY'):
        return None
    cop = c.get('copertina') or {}
    testo = date_lingua(str(cop.get('testo') or c.get('titolo') or '').strip())
    img = [comp['copertina']]
    pg = None   # MAI una persona grande in copertina: al suo posto il bollino del canale
    if pg:
        try:
            img.append(carica_fal(pg))
        except Exception as e:
            log('personaggio copertina non caricato:', e)
    stile = STILE_COP.get(COP_STILE, STILE_COP['cartone'])
    cambio = analizza_copertina(comp, testo)
    if COP_COPIA >= 100:
        base = ('Recreate the YouTube thumbnail of the FIRST image almost identically: same composition, same layout, same framing, same place '
                f'and same kind of scene, same colour palette and same title position and size, {stile}. '
                'Small differences only: slightly different camera angle, different small details in the background. ')
    else:
        base = (f'Recreate the YouTube thumbnail of the FIRST image keeping about {COP_COPIA}% of it: same main composition, same layout, same colour palette '
                f'and same title position and size, {stile}. ' + cambio)
    prompt = (base + ('The main figure is the character of the SECOND image (same face, clothes and style), placed where the main figure is in the first image. ' if len(img) > 1 else '')
              + 'NO big person or character in the foreground: if the first image has a large figure, REMOVE it and fill that area with the landscape, '
              'monuments and scenery of the place (people may appear only tiny and far away). Keep the TOP-LEFT corner (about 28% of the width and 40% of the height) '
              'free of text and of important elements, only sky or background, because the channel logo will be placed there; if the title was there, move it to the right side. '
              + 'Keep the BOTTOM-RIGHT corner (last 30% of the width and last 28% of the height) free of any text: YouTube shows the video duration there. '
              + f'Replace ALL the text with exactly this text, same font style, same colours and same position (but never in the bottom-right corner): "{testo}". '
              + (f'Every word, number and date written on the image must be in {LINGUA_NOME}' + (' (dates as "a.C." / "d.C." written EXACTLY like this with lowercase a and d, even if the rest of the title is uppercase; never BC, AD or A.C.)' if LINGUA == 'it' else '') + '. '
              + 'No other text, no logos, no watermark.'))
    try:
        r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': img, 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
        p = os.path.join(ROOT, 'copertina.jpg'); scarica(r['images'][0]['url'], p)
        Image.open(p).convert('RGB').resize((1280, 720), Image.LANCZOS).save(p, quality=92)
        if BOLLINO:
            aggiungi_bollino(p)
        log('copertina pronta (copia', str(COP_COPIA) + '%, stile', COP_STILE + ')')
        return p
    except Exception as e:
        log('copertina non riuscita:', str(e)[:200])


# ============================================================ BOLLINO "VIDEO ORIGINALE - STORIA IN MINUTI" (sempre uguale su ogni copertina)
RED, YEL, WHITE, INK_B = (226, 20, 30, 255), (255, 214, 0, 255), (255, 255, 255, 255), (22, 18, 20, 255)
BOLLINO = str(P.get('bollino') or E('BOLLINO', '') or 'SI').strip().upper() == 'SI'
BOLLINO_URL = str(P.get('bollino_url') or E('BOLLINO_URL', '')).strip()   # facoltativo: un PNG trasparente al posto di quello disegnato qui
BOLLINO_LARGHEZZA = 260   # pixel su copertina 1280x720: stessa grandezza su tutte (bollino tondo come l'avatar)


def _font_bollino():
    f = os.path.join(FONT, 'PermanentMarker.ttf')
    if not os.path.exists(f):
        os.makedirs(FONT, exist_ok=True)
        scarica('https://github.com/google/fonts/raw/main/apache/permanentmarker/PermanentMarker-Regular.ttf', f)
    return f


def ellisse_ruvida(d, cx, cy, rx, ry, rot, fill=None, outline=None, width=1, jit=0.02, n=180, seed=1):
    r = random.Random(seed); pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        f = 1 + r.uniform(-jit, jit)
        x, y = rx * math.cos(a) * f, ry * math.sin(a) * f
        c, s = math.cos(rot), math.sin(rot)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    if fill:
        d.polygon(pts, fill=fill)
    if outline:
        d.line(pts + [pts[0]], fill=outline, width=width, joint='curve')


def pennellata(w, h, colore, seed, sfrangia=True):
    """Striscia di pennarello/pennello con bordi irregolari."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); r = random.Random(seed)
    top = [(x, r.uniform(0, h * .07)) for x in range(0, w + 1, 45)]
    bot = [(x, h - r.uniform(0, h * .07)) for x in range(w, -1, -45)]
    d.polygon(top + bot, fill=colore)
    if sfrangia:
        for _ in range(40):   # setole alle estremita'
            y = r.uniform(h * .1, h * .9); l = r.uniform(20, 90)
            x0 = r.choice([0, w]); d.line((x0, y, x0 + (l if x0 == 0 else -l) * -1, y + r.uniform(-4, 4)), fill=colore, width=r.randint(3, 9))
        for _ in range(25):   # vuoti della pennellata
            x = r.uniform(0, w); y = r.choice([r.uniform(0, h * .15), r.uniform(h * .85, h)])
            d.line((x, y, x + r.uniform(30, 120), y), fill=(0, 0, 0, 0), width=r.randint(2, 5))
    return im


def testo_ruotato(base, xy, testo, font, colore, ang, stroke=0, sc=None):
    w, h = int(font.getlength(testo)) + 60, int(font.size * 1.6)
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((30, h / 2), testo, font=font, fill=colore, anchor='lm', stroke_width=stroke, stroke_fill=sc)
    t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(t, (int(xy[0] - t.width / 2), int(xy[1] - t.height / 2)))


def disegna_bollino(S=1400):
    """Bollino tondo: TUTTO dentro l'anello bianco, scritte centrate e misurate sulla larghezza disponibile."""
    MK = lambda n: ImageFont.truetype(_font_bollino(), n)
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    cx = cy = S / 2
    R_ROSSO, R_ANELLO = S * .48, S * .435
    R_DENTRO = R_ANELLO - S * .025   # area utile per scritte e strisce
    d.ellipse((cx - R_ROSSO, cy - R_ROSSO, cx + R_ROSSO, cy + R_ROSSO), fill=RED)
    w_an = int(S * .012)
    d.ellipse((cx - R_ANELLO, cy - R_ANELLO, cx + R_ANELLO, cy + R_ANELLO), outline=WHITE, width=w_an)
    corda = lambda y, marg=.86: 2 * math.sqrt(max(0, R_DENTRO ** 2 - (y - cy) ** 2)) * marg   # larghezza libera a quell'altezza

    def scrivi(y, testo, colore, alt_max):
        k = int(alt_max)
        while k > 20 and MK(k).getlength(testo) > corda(y):
            k -= 2
        d.text((cx, y), testo, font=MK(k), fill=colore, anchor='mm')
        return k
    # tasto play
    py, ps = S * .23, S * .065
    tri = [(cx - ps * .7, py - ps * .85), (cx - ps * .7, py + ps * .85), (cx + ps, py)]
    d.polygon(tri, fill=WHITE); d.line(tri + [tri[0]], fill=WHITE, width=int(S * .014), joint='curve')
    # VIDEO / ORIGINALE
    k_or = scrivi(S * .49, 'ORIGINALE', WHITE, S * .11)   # stessa grandezza per le due righe: ordinato
    d.text((cx, S * .49 - k_or * 1.08), 'VIDEO', font=MK(k_or), fill=WHITE, anchor='mm')
    # striscia gialla e linee: ritagliate dentro l'anello bianco (niente esce dal cerchio)
    gialli = Image.new('RGBA', (S, S), (0, 0, 0, 0)); g = ImageDraw.Draw(gialli); r = random.Random(5)
    ys, hs = S * .625, S * .13
    top = [(x, ys - hs / 2 + r.uniform(-S * .006, S * .006)) for x in range(0, S + 1, int(S * .03))]
    bot = [(x, ys + hs / 2 + r.uniform(-S * .006, S * .006)) for x in range(S, -1, -int(S * .03))]
    g.polygon(top + bot, fill=YEL)
    for y, l in ((S * .76, .42), (S * .815, .28)):
        g.rounded_rectangle((cx - S * l / 2, y - S * .011, cx + S * l / 2, y + S * .011), radius=int(S * .011), fill=YEL)
    maschera = Image.new('L', (S, S), 0)
    ImageDraw.Draw(maschera).ellipse((cx - R_ANELLO + w_an * 1.5, cy - R_ANELLO + w_an * 1.5, cx + R_ANELLO - w_an * 1.5, cy + R_ANELLO - w_an * 1.5), fill=255)
    im.paste(gialli, (0, 0), Image.composite(gialli.split()[3], Image.new('L', (S, S), 0), maschera))
    d = ImageDraw.Draw(im)
    k = int(S * .085)
    while k > 20 and MK(k).getlength('STORIA IN MINUTI') > corda(ys, .84):
        k -= 2
    d.text((cx, ys), 'STORIA IN MINUTI', font=MK(k), fill=INK_B, anchor='mm')
    return im


def immagine_bollino():
    p = os.path.join(LAV, 'bollino.png')
    if not os.path.exists(p):
        if BOLLINO_URL:
            scarica(BOLLINO_URL, p)
        else:
            b = disegna_bollino(); b.crop(b.getbbox()).save(p)
    return Image.open(p).convert('RGBA')


def angolo_libero(p):
    """Claude guarda la copertina e sceglie l'angolo dove il bollino non copre scritte, volti o il soggetto principale."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        return 'alto_sinistra'
    im = Image.open(p).convert('RGB'); im.thumbnail((768, 768)); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85)
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_AI, 'max_tokens': 200, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': "In questa copertina YouTube va messo un bollino rotondo largo circa un quarto dell'immagine. In quale angolo NON copre "
                                     "scritte, numeri, date, volti o il soggetto principale? Preferisci alto_sinistra se e' libero. "
                                     "Rispondi solo: ANGOLO: alto_sinistra | alto_destra | basso_sinistra (mai basso_destra: li' c'e' la durata del video)"}]}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        m = re.search(r'(alto|basso)_(sinistra|destra)', ''.join(b.get('text', '') for b in r.get('content', [])))
        ang = m.group(0) if m else 'alto_sinistra'
        return 'alto_destra' if ang == 'basso_destra' else ang   # in basso a destra c'e' la durata del video: mai li'
    except Exception as e:
        log('angolo bollino non scelto:', str(e)[:100]); return 'alto_sinistra'


def aggiungi_bollino(p):
    try:
        cop = Image.open(p).convert('RGBA'); b = immagine_bollino()
        b = b.resize((BOLLINO_LARGHEZZA, int(b.height * BOLLINO_LARGHEZZA / b.width)), Image.LANCZOS)
        ang = angolo_libero(p); m = 16
        x = m if ang.endswith('sinistra') else cop.width - b.width - m
        y = m if ang.startswith('alto') else cop.height - b.height - m
        cop.alpha_composite(b, (x, y)); cop.convert('RGB').save(p, quality=92)
        log('bollino in copertina:', ang)
    except Exception as e:
        log('bollino non aggiunto:', str(e)[:150])


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
def dur_carta(d):
    """Battitura delle carte: la frase e' sempre completa almeno 1 secondo prima del cambio immagine."""
    return min(2.0, max(.4, d - 1.3))


def dur_scheda(d):
    return min(1.2, max(.3, d - 1.6))


def dur_did(d):
    """Durata della battitura di una didascalia: si adatta al pezzo, cosi' la scritta finisce sempre prima del cambio."""
    return min(1.6, max(.5, d - 1.1))


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
        f = font(nome_font, sz); righe = a_capo(testo, f, 1150)   # dentro il centro libero del fondo, mai sopra le decorazioni
        if (len(righe) <= 3 and max(f.getlength(r) for r in righe) <= 1200) or sz <= 70: break
        sz -= 6
    tot = len(testo); i0, dur_batt = battitura(testo, .3, dur_carta(d))

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


ORO = (255, 201, 74)


def aggiungi_sovrimpressione(path, d, testo, nome_font=''):
    """Un solo dato in sovrimpressione (canale senza texture): scritta grande bianca, i NUMERI in oro, su un'ombra scura sfumata in basso.
    Compare con una dissolvenza, le lettere battute a macchina, poi resta ferma fino alla fine dell'immagine."""
    f = None
    for sz in range(104, 54, -6):
        f = ImageFont.truetype(os.path.join(FONT, 'Oswald-SemiBold.ttf'), sz) if os.path.exists(os.path.join(FONT, 'Oswald-SemiBold.ttf')) else font('classico', sz)
        if f.getlength(testo) <= W - 240:
            break
    ombra = Image.new('L', (1, 380))
    for y in range(380):
        ombra.putpixel((0, y), int(185 * (y / 379) ** 1.6))
    ombra = Image.merge('RGBA', [Image.new('L', (W, 380), 0)] * 3 + [ombra.resize((W, 380))])
    tot = len(testo); i0, dur = battitura(testo, .35, dur_did(d))
    x0 = (W - f.getlength(testo)) / 2; y0 = H - 120 - f.size
    oro = [bool(re.match(r'[\d.,%°]', ch)) or (ch in '+-' and k + 1 < tot and testo[k + 1].isdigit()) for k, ch in enumerate(testo)]
    tmp = path[:-4] + '_s.mp4'
    lettore = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    scrittore = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                  *map(str, ENC), tmp], stdin=subprocess.PIPE)
    k = 0
    while True:
        b = lettore.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        t = k / FPS; k += 1
        im = Image.frombytes('RGB', (W, H), b).convert('RGBA')
        a = ease(clamp(t / .4))
        if a > 0:
            o = ombra.copy(); o.putalpha(o.getchannel('A').point(lambda v: int(v * a)))
            im.alpha_composite(o, (0, H - 380))
        n = tot if t >= i0 + dur else int(clamp((t - i0) / dur) * tot)
        if n:
            dr = ImageDraw.Draw(im); x = x0
            for j, ch in enumerate(testo[:n]):
                dr.text((x + 3, y0 + 4), ch, font=f, fill=(0, 0, 0, 150))
                dr.text((x, y0), ch, font=f, fill=ORO if oro[j] else (255, 255, 255))
                x += f.getlength(ch)
        scrittore.stdin.write(im.convert('RGB').tobytes())
    lettore.wait(); scrittore.stdin.close(); scrittore.wait()
    if scrittore.returncode or k == 0:
        raise RuntimeError('sovrimpressione non riuscita')
    os.replace(tmp, path)
    return path


def aggiungi_didascalia(path, d, testo, nome_font):
    if not TEXTURE:   # canale senza texture: niente striscia di carta, solo la scritta pulita
        return aggiungi_sovrimpressione(path, d, testo, nome_font)
    """Rifa' il pezzo con la striscia di carta che sale dal basso e la scritta battuta a macchina."""
    striscia = carta_strappata(seme=len(testo)); hs = striscia.height
    sz = 76
    while sz > 52 and font(nome_font, sz).getlength(testo) > W - 260:
        sz -= 4
    f = font(nome_font, sz); tot = len(testo); i0, dur = battitura(testo, .45, dur_did(d))
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
def effetto(desc, dur, k):
    """Effetto sonoro da film generato con ElevenLabs (stessa chiave della voce). Uguali = generato una volta sola."""
    chiave = E('ELEVENLABS_API_KEY', '')
    p = os.path.join(LAV, 'fx_' + hashlib.md5(f'{desc}|{dur:.1f}'.encode()).hexdigest()[:10] + '.mp3')
    if os.path.exists(p):
        return p
    b = http('https://api.elevenlabs.io/v1/sound-generation', {'text': desc, 'duration_seconds': round(max(1.0, min(dur, 6.0)), 1),
             'prompt_influence': 0.5}, {'xi-api-key': chiave, 'Accept': 'audio/mpeg'}, timeout=120, raw=True)
    open(p, 'wb').write(b)
    return p


def pista_effetti(piano, totale):
    """Sceglie al massimo EFFETTI_MINUTO effetti al minuto (distanziati), li genera e li mette a tempo con le immagini."""
    if not EFFETTI or not E('ELEVENLABS_API_KEY'):
        return None
    tetto = max(1, int(round(totale / 60 * EFFETTI_MINUTO)))
    passo = 60 / max(.1, EFFETTI_MINUTO) * .7
    scelti, t, ultimo = [], 0.0, -1e9
    for v in piano:
        desc = str(v.get('suono') or '').strip()
        if desc and t - ultimo >= passo and len(scelti) < tetto and v['d'] >= 1.5:
            scelti.append((t, min(v['d'], 5.0), desc)); ultimo = t
        t += v['d'] - T_TR
    if not scelti:
        return None
    ins, filt, ok = [], [], 0
    for i, (t0, d, desc) in enumerate(scelti):
        try:
            f = effetto(desc, d, i)
        except Exception as e:
            log('effetto saltato:', desc, str(e)[:100]); continue
        ins += ['-i', f]; ms = int(t0 * 1000)
        filt.append(f'[{ok}:a]atrim=0:{d:.2f},afade=t=in:d=0.25,afade=t=out:st={max(0, d - 0.8):.2f}:d=0.8,adelay={ms}|{ms}[e{ok}]'); ok += 1
    if not ok:
        return None
    out = os.path.join(LAV, 'effetti.wav')
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filt) + ';' + ''.join(f'[e{i}]' for i in range(ok))
         + f'amix=inputs={ok}:normalize=0,apad=whole_dur={totale:.2f}[a]', '-map', '[a]', '-ac', '2', '-ar', '44100', out])
    log('effetti sonori:', ok, 'su', len(scelti), '(tetto', tetto, ')', '; '.join(x[2] for x in scelti)[:300])
    return out


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


SUONI_CAMBIO_DESCR = [   # libreria generata con ElevenLabs (stessa chiave della voce): suoni veri, tutti diversi
    ('fast cinematic whoosh transition', 0.8), ('soft airy swish, quick camera pan', 0.6), ('deep whoosh with a soft low boom', 1.0),
    ('paper page turning quickly', 0.6), ('short wooden tap, warm and soft', 0.5), ('soft bubble pop, cartoon', 0.5),
    ('short cinematic impact hit, deep', 0.8), ('quick swoosh with a light magical shimmer', 0.8), ('reverse whoosh riser, short', 0.8),
    ('soft cloth flutter, flag in the wind, short', 0.6), ('light glass ding, gentle', 0.6), ('drum hit with short reverb, epic', 0.7)]


def _carica_suono(f, sr):
    w = f + '.raw'
    run(['ffmpeg', '-y', '-v', 'error', '-i', f, '-t', '1.6', '-ac', '1', '-ar', str(sr), '-f', 's16le', w])
    x = np.frombuffer(open(w, 'rb').read(), '<i2').astype(np.float32) / 32768
    sopra = np.nonzero(np.abs(x) > max(.02, np.abs(x).max() * .08))[0] if len(x) else []
    return x[max(0, sopra[0] - int(sr * .01)):] if len(sopra) else x   # niente silenzio iniziale: il suono parte col taglio


def _stesso_volume(a, rms=.16):
    """Tutti i suoni allo stesso volume PERCEPITO (non allo stesso picco: prima i click secchi coprivano gli swoosh)."""
    a = a - a.mean()
    r = float(np.sqrt(np.mean(a[np.abs(a) > 1e-4] ** 2))) if np.any(np.abs(a) > 1e-4) else 0
    if r <= 0:
        return a
    return np.clip(a * (rms / r), -1, 1)


def _libreria_cambio(sr=44100):
    """Suoni per il cambio immagine: 1) link nel foglio (suoni_cambio_url); 2) generati con ElevenLabs (12 suoni veri);
    3) di riserva, generati qui."""
    lib = []
    for i, u in enumerate(SUONI_CAMBIO_URL[:40]):
        try:
            a = _carica_suono(scarica(u, os.path.join(LAV, f'cambio_{i}.src')), sr)
            if len(a) > 100:
                lib.append(_stesso_volume(a))
        except Exception as e:
            log('suono cambio non scaricato:', u[-40:], str(e)[:80])
    if lib:
        return lib, 'dal foglio'
    if E('ELEVENLABS_API_KEY'):
        def gen(x):
            i, (desc, dur) = x
            try:
                return _stesso_volume(_carica_suono(effetto(desc, dur, i), sr)[:int(sr * 1.4)])
            except Exception as e:
                log('suono cambio non generato:', desc, str(e)[:80])
        with ThreadPoolExecutor(3) as ex:
            lib = [a for a in ex.map(gen, enumerate(SUONI_CAMBIO_DESCR)) if a is not None and len(a) > 100]
        if len(lib) >= 4:
            return lib, 'ElevenLabs'
    rng = np.random.default_rng(11)

    def env(n, att, dec):
        t = np.arange(n) / sr
        return np.minimum(1, t / max(1e-4, att)) * np.exp(-np.maximum(0, t - att) / dec)

    def rumore(n, liscio):
        return np.convolve(rng.normal(0, 1, n), np.ones(liscio) / liscio, 'same')

    def swoosh(dur, liscio, picco):
        n = int(sr * dur); t = np.arange(n) / sr
        return rumore(n, liscio) * np.sin(np.pi * np.clip(t / dur, 0, 1)) ** picco

    def tono(f0, f1, dur, dec):
        n = int(sr * dur); t = np.arange(n) / sr
        f = f1 + (f0 - f1) * np.exp(-t * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, .002, dec)
    lib = [swoosh(.42, 18, 2), swoosh(.28, 6, 3), swoosh(.55, 40, 1.5), tono(900, 380, .18, .05),
           tono(140, 55, .45, .12) + rumore(int(sr * .45), 60) * env(int(sr * .45), .001, .05) * .4,
           tono(1250, 1250, .12, .03) + tono(2500, 2500, .12, .02) * .3,
           np.concatenate([rumore(int(sr * .07), 3) * env(int(sr * .07), .002, .02), np.zeros(int(sr * .04)),
                           rumore(int(sr * .09), 4) * env(int(sr * .09), .002, .03)]),
           swoosh(.35, 10, 1) * np.linspace(.2, 1, int(sr * .35))]
    return [_stesso_volume(a) for a in lib], 'generati'


def pista_cambi(piano, totale, out, sr=44100):
    """Un suono a ogni cambio immagine, a rotazione: mai uno dei 3 suoni appena usati."""
    lib, fonte = _libreria_cambio(sr)
    a = np.zeros(int((totale + 2) * sr), np.float32)
    rng = random.Random(str(P.get('id') or TITOLO)); ultimi, t, n = [], 0.0, 0
    for k, v in enumerate(piano):
        if k:
            scelta = [x for x in range(len(lib)) if x not in ultimi] or list(range(len(lib)))
            i = rng.choice(scelta); ultimi = (ultimi + [i])[-min(3, len(lib) - 1):]
            s_ = lib[i] * rng.uniform(.85, 1.0); j = max(0, int((t - .05) * sr))   # appena prima del taglio: il suono "porta" l'immagine
            s_ = s_[:max(0, len(a) - j)]; a[j:j + len(s_)] += s_.astype(np.float32); n += 1
        t += v['d'] - T_TR
    a = np.clip(a, -1, 1)
    import wave
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((a * 32767).astype('<i2').tobytes())
    log('suoni di cambio immagine:', n, '| libreria:', len(lib), 'suoni', f'({fonte})')
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
        fig.thumbnail((900, 620)); ombra = fig.split()[3].filter(ImageFilter.GaussianBlur(10))
    sz = 100
    while sz > 64 and font(nome_font, sz).getlength(nome) > W - 200:
        sz -= 4
    f = font(nome_font, sz); tot = len(nome); i0, dur = battitura(nome, .6, dur_scheda(d))

    def disegna(t):
        k = (min(12, int(t * 20)), tot if t >= i0 + dur else int(clamp((t - i0) / dur) * tot))

        def fn():
            im = tex.copy()
            if fig:
                dy = int((1 - ease(min(t, .6) / .6)) * 40)
                x, y = (W - fig.width) // 2, 700 - fig.height + 20 + dy
                im.paste((60, 40, 20), (x + 8, y + 12), ombra.point(lambda v: v * .35))
                im.paste(fig, (x, y), fig)
            n = k[1]
            # nome sempre leggibile: su una fascia di carta chiara al centro, mai sopra le decorazioni del bordo
            lw, yb = f.getlength(nome) + 140, 700
            fascia = Image.new('RGBA', (W, H), (0, 0, 0, 0)); df = ImageDraw.Draw(fascia)
            df.rounded_rectangle(((W - lw) / 2, yb, (W + lw) / 2, yb + sz * 1.55), radius=26, fill=(247, 238, 218, 240),
                                 outline=(120, 90, 50, 200), width=4)
            im = Image.alpha_composite(im.convert('RGBA'), fascia).convert('RGB')
            ImageDraw.Draw(im).text(((W - f.getlength(nome)) / 2, yb + sz * .2), nome[:n], font=f, fill=INK)
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
        xb = f'(main_w-520-overlay_w/2)' if lato else '(520-overlay_w/2)'   # centrato sul personaggio: le due pose restano allineate
        entra = f'if(lt(t,0.6),(0.6-t)/0.6*{"700" if lato else "-700"},0)'
        ins += ['-loop', '1', '-framerate', FPS, '-t', d, '-i', f1]
        # cambio posa in dissolvenza (0,3 s): prima era uno scambio secco che sembrava uno 'scatto'
        filtri.append(f'[1:v]scale=-1:820,format=rgba' + (f',fade=t=out:st={cambio:.2f}:d=0.3:alpha=1' if f2 else '') + '[p1]')
        en1 = f":enable='lt(t,{cambio + .3:.2f})'" if f2 else ''
        filtri.append(f"[{cur}][p1]overlay=x='{xb}+{entra}':y='main_h-overlay_h-10+6*sin(2.4*t)'{en1}[o1]"); cur = 'o1'
        if f2:
            ins += ['-loop', '1', '-framerate', FPS, '-t', d, '-i', f2]
            filtri.append(f'[2:v]scale=-1:820,format=rgba,fade=t=in:st={cambio:.2f}:d=0.3:alpha=1[p2]')
            filtri.append(f"[{cur}][p2]overlay=x='{xb}':y='main_h-overlay_h-10+6*sin(2.4*t)'"
                          f":enable='gte(t,{cambio:.2f})'[o2]"); cur = 'o2'
    if data:
        tf = os.path.join(LAV, 'data.txt'); open(tf, 'w').write(data)
        filtri.append(f"[{cur}]drawtext=fontfile={os.path.join(FONT, 'EBGaramond-SemiBold.ttf')}:textfile={tf}:fontsize=150:fontcolor=0x1d1a17:"
                      f"borderw=8:bordercolor=white@0.75:x=(w-tw)/2:y=60:alpha='min(1,max(0,(t-0.4)/0.5))'[o3]"); cur = 'o3'
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(filtri), '-map', f'[{cur}]', '-t', d, *ENC, path])
    return path


def pezzo_video(path, d, src):
    """Clip piu' corta del suo spazio: prima si rallenta un po' (fino al 70%), poi si ferma sull'ultimo fotogramma.
    MAI ripartire da capo (si vedeva lo 'scatto' con l'immagine che ricominciava)."""
    try:
        ds = durata(src)
    except Exception:
        ds = 0
    lento = ''
    if 0 < ds < d:
        f = max(.7, ds / d)
        lento = f'setpts=PTS/{f:.3f},'
        if ds / f < d:
            lento += f'tpad=stop_mode=clone:stop_duration={d - ds / f + .5:.2f},'
    run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-t', d, '-an',
         '-vf', f'{lento}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1', *ENC, path])
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


# ============================================================ REGIA: solo cartoni, un'inquadratura ogni ~3 s scritta sulle parole esatte della voce
ZOOM_BOX = {'': (0.0, 0.0, 1.0), 'centro': (.2, .2, .6), 'sinistra': (.0, .22, .6), 'destra': (.4, .22, .6),
            'alto': (.2, .0, .6), 'basso': (.2, .4, .6), 'volto': (.3, .12, .4)}
CAMERE = ('push_in', 'pull_out', 'pan_left', 'pan_right', 'tilt_up', 'tilt_down')
CONNETTIVI = {'e', 'ed', 'ma', 'poi', 'quando', 'mentre', 'che', 'perche', 'perché', 'cosi', 'così', 'allora', 'dopo', 'prima', 'invece',
              'infatti', 'pero', 'però', 'anche', 'oppure', 'o', 'finche', 'finché', 'and', 'but', 'then', 'when', 'while', 'so', 'after', 'before'}


def taglia_inquadrature(scene, durs, voci):
    """Divide la voce in inquadrature di ~RITMO secondi, tagliando SEMPRE tra una parola e l'altra (tempi veri di ElevenLabs)."""
    out, glob = [], 0.0
    for i, (s, D) in enumerate(zip(scene, durs)):
        testo = s.get('testo_voce') or s['testo']
        try:
            al = json.load(open(voci[i][:-4] + '.json'))
        except Exception:
            al = {}
        st = (al or {}).get('character_start_times_seconds') or []
        if len(st) != len(testo):
            st = None
        parole = [(m.start(), m.group()) for m in re.finditer(r'\S+', testo)]
        tempo = (lambda ci: min(D, max(0.0, st[ci]))) if st else (lambda ci: D * ci / max(1, len(testo)))
        tagli, primi = [0.0], [0]

        def punti(k):   # quanto e' "naturale" tagliare prima della parola k
            prima, w = parole[k - 1][1], parole[k][1].lower().strip('«"(')
            if re.search(r'[.!?]["»)]?$', prima):
                return 3.0
            if re.search(r'[;:]["»)]?$', prima):
                return 2.5
            if prima.endswith(','):
                return 2.0
            return 1.2 if w in CONNETTIVI else 0.0
        while True:   # si sceglie il taglio migliore vicino al ritmo, dove la frase "respira" (punto, virgola, "e / ma / poi...")
            t_ini = tagli[-1]; lim = limite(glob + t_ini)
            cand = [k for k in range(primi[-1] + 1, len(parole))
                    if 1.6 <= tempo(parole[k][0]) - t_ini <= lim + 1.3 and D - tempo(parole[k][0]) >= 1.4]
            if not cand:
                break
            k = max(cand, key=lambda k: punti(k) - abs(tempo(parole[k][0]) - t_ini - lim) * .7)
            tagli.append(tempo(parole[k][0])); primi.append(k)
        for j, t0 in enumerate(tagli):
            t1 = tagli[j + 1] if j + 1 < len(tagli) else D
            ws = parole[primi[j]: primi[j + 1] if j + 1 < len(primi) else len(parole)]
            out.append({'scena': i, 'd': t1 - t0, 'testo': ' '.join(w for _, w in ws), 'capitolo': (s.get('capitolo') or '') if j == 0 else ''})
        glob += D
    return out


def piano_regia(c, shots, kit):
    """Claude fa il regista: per OGNI inquadratura decide l'immagine sulle parole esatte della voce."""
    chiave = E('ANTHROPIC_API_KEY', '')
    lotto, ris, memoria = 60, {}, ''
    for b0 in range(0, len(shots), lotto):
        parte = shots[b0:b0 + lotto]
        elenco = '\n'.join(f'{b0 + k}: {s["testo"]}' + (f'   [INIZIA IL CAPITOLO: {s["capitolo"]}]' if s.get('capitolo') else '') for k, s in enumerate(parte))
        prompt = f"""Sei il regista di un video di storia a cartone di altissimo livello: "{c.get('titolo') or TITOLO}" (paese: {PAESE.get('nome') or ''}).
Ogni riga qui sotto e' un'inquadratura di circa {RITMO[0]:.0f} secondi con le PAROLE che la voce dice in quel momento. Per OGNI riga decidi cosa si vede.
{('Ultime immagini decise (per continuita di epoca, luoghi e personaggi): ' + memoria) if memoria else ''}

REGOLE:
1. COERENZA ASSOLUTA: l'immagine mostra ESATTAMENTE quello che dicono quelle parole. Se dice sole: sole e luce calda; se dice pioggia o inverno: pioggia o neve; se dice deserto: deserto; se nomina una persona: quella persona; se parla di numeri o idee astratte: una scena concreta che li rappresenta. MAI qualcosa che contraddice le parole.
2. "nuova": true = immagine nuova; false = DETTAGLIO dell'ultima immagine nuova (la stessa scena vista piu' da vicino), SOLO se le parole parlano ancora della stessa cosa e quel dettaglio e' gia' nell'immagine. Mai piu' di 2 dettagli di fila. Circa {round(NUOVE_QUOTA * 100)}% di immagini nuove.
3. "prompt_en" (solo per le nuove): in inglese, 30-60 parole: chi c'e' e cosa fa, luogo, epoca, tempo atmosferico e luce, emozione, e l'INQUADRATURA (varia sempre: epic wide establishing shot, aerial view, medium shot, dramatic close-up, low angle, over-the-shoulder, silhouette against the sky...). Se le righe dopo saranno dettagli, descrivi anche quegli elementi e dove sono (left / right / center).
4. "personaggi": 0-2 id del kit SOLO se sono proprio loro (la persona con nome che la voce nomina, o una figura generica coerente con epoca e popolo). Kit: {lista_kit(kit)}. Le altre persone descrivile nel prompt (popolo, epoca, vestiti corretti).
5. "zoom" (solo per i dettagli): uno tra sinistra, destra, centro, alto, basso, volto.
6. "camera": push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down. Variala, mai uguale due volte di fila; nei momenti forti push_in.
7. "didascalia" (facoltativa, circa 1 riga ogni 6, mai due di fila): 2-6 parole chiave DETTE in quella riga (nomi, date, luoghi).
8. "mappa": true UNA sola volta in tutto il video, quando la voce presenta il territorio o i confini del paese (senza prompt).
9. EMOZIONE E SORPRESA: alterna campi lunghissimi epici e primi piani emotivi, giorno e notte, folle e solitudine, interni ed esterni; mai lo stesso soggetto due volte di fila; ogni immagine deve far venire voglia di vedere la successiva.
10. Mai scritte, lettere o numeri dentro le immagini; niente di moderno se l'epoca e' antica.

INQUADRATURE:
{elenco}

Rispondi SOLO con un array JSON, un oggetto per riga, con lo stesso numero "n":
[{{"n": {b0}, "nuova": true, "prompt_en": "...", "personaggi": [], "camera": "push_in", "didascalia": ""}}, {{"n": {b0 + 1}, "nuova": false, "zoom": "volto", "camera": "pan_left"}}]"""
        for k in range(3):
            try:
                testo, _ = claude_stream({'model': MODELLO_AI if k < 2 else MODELLO_RISERVA, 'max_tokens': 32000,
                                          'messages': [{'role': 'user', 'content': prompt}]}, chiave)
                arr = json.loads(testo[testo.find('['): testo.rfind(']') + 1])
                for x in arr:
                    if isinstance(x, dict) and str(x.get('n', '')).lstrip('-').isdigit():
                        ris[int(x['n'])] = x
                break
            except Exception as e:
                log('regia non valida, riprovo:', str(e)[:150]); time.sleep(5)
        ultime = [ris[n].get('prompt_en') for n in range(b0, b0 + len(parte)) if n in ris and ris[n].get('prompt_en')][-3:]
        memoria = ' | '.join(u[:220] for u in ultime)
    # regole fisse sopra le scelte di Claude
    mappa_fatta, dettagli, ultima_cam, out = False, 0, '', []
    for n, s in enumerate(shots):
        r = dict(ris.get(n) or {})
        if r.get('mappa') and not mappa_fatta and c.get('paese_mappa'):
            mappa_fatta = True; out.append(dict(s, tipo='mappa')); dettagli = 0; continue
        r['mappa'] = False
        nuova = bool(r.get('nuova', True)) or not out or dettagli >= 2 or not any(x.get('img') is not None for x in out)
        if nuova and not str(r.get('prompt_en') or '').strip():
            if out and dettagli < 2 and any(x.get('img') is not None for x in out):
                nuova = False
            else:
                r['prompt_en'] = 'Historical scene illustrating: ' + s['testo']
        cam = r.get('camera') if r.get('camera') in CAMERE else random.choice(CAMERE)
        if cam == ultima_cam:
            cam = random.choice([x for x in CAMERE if x != cam])
        ultima_cam = cam
        v = dict(s, tipo='cartone', camera=cam, didascalia=str(r.get('didascalia') or '').strip()[:60])
        if nuova:
            v.update(img=n, prompt=str(r['prompt_en']).strip(), personaggi=[x for x in (r.get('personaggi') or []) if x in kit and x != NARRATORE][:2], zoom='')
            dettagli = 0
        else:
            v.update(img=next(x['img'] for x in reversed(out) if x.get('img') is not None), zoom=r.get('zoom') if r.get('zoom') in ZOOM_BOX else 'centro')
            dettagli += 1
        out.append(v)
    nuove = [v for v in out if v.get('prompt')]
    if len(nuove) > IMMAGINI_MAX:   # tetto di costo: alcune nuove diventano dettagli della precedente (mai la prima del capitolo)
        togli = len(nuove) - IMMAGINI_MAX
        for i in range(1, len(out)):
            if togli <= 0:
                break
            v, p = out[i], out[i - 1]
            if v.get('prompt') and not v.get('capitolo') and p.get('img') is not None and i % 2:
                v.update(img=p['img'], zoom='centro'); v.pop('prompt', None); togli -= 1
    for v in out:   # i dettagli puntano all'immagine giusta
        if v.get('tipo') == 'cartone' and not v.get('prompt') and v.get('img') is not None and out[v['img']].get('tipo') != 'cartone':
            v['img'] = next(x['img'] for x in reversed(out[:out.index(v)]) if x.get('prompt'))
    log(f"regia: {len(out)} inquadrature, {sum(1 for v in out if v.get('prompt'))} immagini nuove, "
        f"{sum(1 for v in out if v.get('tipo') == 'cartone' and not v.get('prompt'))} dettagli, mappa: {'si' if mappa_fatta else 'no'}")
    return out


def _immagine_fal(prompt, refs, p):
    if IMMAGINI_MODELLO.startswith('nano'):
        dati = {'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1}
        r = fal('fal-ai/nano-banana-2/edit', dict(dati, prompt=prompt, image_urls=refs)) if refs else fal('fal-ai/nano-banana-2', dict(dati, prompt=prompt))
    else:
        dati = {'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}
        r = fal('fal-ai/bytedance/seedream/v4.5/edit', dict(dati, prompt=prompt, image_urls=refs)) if refs else \
            fal('fal-ai/bytedance/seedream/v4.5/text-to-image', dict(dati, prompt=prompt))
    scarica(r['images'][0]['url'], p)
    im = Image.open(p).convert('RGB')
    ImageOps.fit(im, (2560, 1440), Image.LANCZOS).save(p, quality=92)


def verifica_immagine(p, testi, prompt):
    """Claude guarda l'immagine e la confronta con le parole della voce. None = ok, altrimenti cosa correggere."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        return None
    im = Image.open(p).convert('RGB'); im.thumbnail((768, 768)); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85)
    domanda = f"""Video di storia sul paese: {PAESE.get('nome') or '-'}. Questa immagine accompagna queste parole della voce: "{testi[:500]}".
Controlla SOLO errori evidenti che uno spettatore noterebbe:
1) contraddice le parole? (es. dice sole e c'e' pioggia, dice deserto e c'e' una foresta, dice una battaglia e c'e' una festa, nomina un re e non c'e')
2) vestiti, edifici o oggetti moderni in un'epoca antica? persone in giacca, cravatta, panciotto o abiti dell'800/900 (scienziati, studiosi) quando la voce parla di un'epoca antica o di un luogo?
3) scritte, lettere o numeri nell'immagine?
4) errori di anatomia: 3 braccia, 2 teste, corpi fusi, mani deformi molto evidenti?
5) persone di un altro popolo rispetto al paese e all'epoca raccontati (es. europei o asiatici dell'est in una scena dell'India antica)?
Rispondi in 1 riga e chiudi con: ESITO: OK  oppure  ESITO: RIFAI - <cosa correggere, in inglese, max 20 parole>"""
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_CONTROLLO, 'max_tokens': 300, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': domanda}]}]}, {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        txt = ''.join(b.get('text', '') for b in r.get('content', []))
        m = re.search(r'ESITO:\s*(OK|RIFAI\s*-?\s*(.*))', txt)
        return None if not m or m.group(1).startswith('OK') else (m.group(2) or 'match the narration').strip()[:200]
    except Exception as e:
        log('verifica immagine non riuscita:', str(e)[:120]); return None


def genera_regia(v, testi):
    p = os.path.join(LAV, f'img_{v["img"]:04d}.jpg')
    if os.path.exists(p):
        return p
    refs = []
    for pg in v.get('personaggi') or []:
        try:
            u = ref_personaggio(pg)
            if u:
                refs.append(u)
        except Exception as e:
            log('riferimento personaggio non caricato:', pg, str(e)[:100])
    base = v['prompt'] + '. ' + STILE_SCENA
    if refs:
        base = ('The character' + ('s' if len(refs) > 1 else '') + ' of the reference image' + ('s' if len(refs) > 1 else '') +
                ' must appear INSIDE this scene, kept IDENTICAL (same face, body, clothes and drawing style), acting naturally. '
                'Do not copy the white background of the reference. Scene: ' + base)
    if not E('FAL_KEY'):
        Image.new('RGB', (2560, 1440), (200, 180, 140)).save(p); return p
    try:
        _immagine_fal(base, refs, p)
    except Exception as e:   # modello non disponibile o immagine rifiutata: si prova con l'altro modello
        log('immagine', v['img'], 'riprovo con Nano Banana:', str(e)[:150])
        dati = {'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1}
        r = fal('fal-ai/nano-banana-2/edit', dict(dati, prompt=base, image_urls=refs)) if refs else fal('fal-ai/nano-banana-2', dict(dati, prompt=base))
        scarica(r['images'][0]['url'], p); ImageOps.fit(Image.open(p).convert('RGB'), (2560, 1440), Image.LANCZOS).save(p, quality=92)
    if VERIFICA:
        motivo = verifica_immagine(p, testi, v['prompt'])
        if motivo:
            log(f'immagine {v["img"]} rifatta: {motivo}')
            try:
                _immagine_fal(base + ' IMPORTANT: ' + motivo, refs, p)
            except Exception as e:
                log('rifacimento non riuscito:', str(e)[:120])
    return p


def pezzo_regia(path, d, img, zoom, camera, titolo='', nome_font='classico'):
    x0, y0, w0 = ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])
    w0 = min(w0, .86) if camera in ('pan_left', 'pan_right', 'tilt_up', 'tilt_down') else w0
    cx, cy = x0 + ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])[2] / 2, y0 + ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])[2] / 2
    a = (max(0, min(1 - w0, cx - w0 / 2)), max(0, min(1 - w0, cy - w0 / 2)), w0)
    sp = (1 - w0) * .9   # quanto ci si puo' spostare
    if camera == 'push_in':
        w1 = a[2] * .84; b = (a[0] + (a[2] - w1) / 2, a[1] + (a[2] - w1) / 2, w1)
    elif camera == 'pull_out':
        w1 = a[2] * .84; b = a; a = (a[0] + (a[2] - w1) / 2, a[1] + (a[2] - w1) / 2, w1)
    elif camera in ('pan_left', 'pan_right'):
        l, r = max(0, a[0] - sp / 2), min(1 - w0, a[0] + sp / 2)
        a, b = ((r, a[1], w0), (l, a[1], w0)) if camera == 'pan_left' else ((l, a[1], w0), (r, a[1], w0))
    else:
        t_, b_ = max(0, a[1] - sp / 2), min(1 - w0, a[1] + sp / 2)
        a, b = ((a[0], b_, w0), (a[0], t_, w0)) if camera == 'tilt_up' else ((a[0], t_, w0), (a[0], b_, w0))
    n1 = max(1, int(d * FPS) - 1)
    e = lambda p_, q: f'({p_:.4f}+({q:.4f}-{p_:.4f})*(3*pow(on/{n1},2)-2*pow(on/{n1},3)))'
    vf = (f"scale=3840:2160:flags=lanczos,zoompan=z='1/{e(a[2], b[2])}':x='iw*{e(a[0], b[0])}':y='ih*{e(a[1], b[1])}':d=1:s={W}x{H}:fps={FPS}")
    if GRANA:
        vf += ',noise=alls=4:allf=t,vignette=angle=PI/6'
    if titolo:   # inizio capitolo: titolo grande che appare e scompare
        tf = path[:-4] + '_t.txt'; open(tf, 'w').write(titolo.upper())
        ff = os.path.join(FONT, FONT_EPOCA.get(nome_font, 'EBGaramond-SemiBold.ttf'))
        vf += (f",drawtext=fontfile={ff}:textfile={tf}:fontsize=150:fontcolor=white:borderw=6:bordercolor=black@0.7:"
               f"box=1:boxcolor=black@0.35:boxborderw=40:x=(w-tw)/2:y=(h-th)/2:"
               f"alpha='if(lt(t,0.3),t/0.3,if(lt(t,{max(.6, d - .5):.2f}),1,max(0,({d:.2f}-t)/0.5)))'")
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', FPS, '-t', d, '-i', img, '-vf', vf + ',setsar=1', '-t', d, *ENC, path])
    return path


def video_regia(c, durs, voci, kit):
    nome_font = c.get('font_carte') if c.get('font_carte') in FONT_EPOCA else 'classico'
    shots = taglia_inquadrature(c['scene'], durs, voci)
    piano = piano_regia(c, shots, kit)
    fine_prec, acc = 0, 0.0   # durate a fotogrammi interi: video e voce restano allineati
    for v in piano:
        acc += v['d']; fine = int(round(acc * FPS)); v['d'] = max(1, fine - fine_prec) / FPS; fine_prec = fine
    nuove = [v for v in piano if v.get('prompt')]
    testi = {v['img']: ' '.join(x['testo'] for x in piano if x.get('img') == v['img']) for v in nuove}
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        immagini = dict(zip([v['img'] for v in nuove], ex.map(lambda v: genera_regia(v, testi[v['img']]), nuove)))
    log('immagini pronte:', len(immagini), 'in', int(time.time() - t0), 's')

    def fai(k):
        v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4')
        try:
            if v['tipo'] == 'mappa':
                return pezzo_mappa(p, d, c.get('paese_mappa') or '', c.get('titolo_mappa') or TITOLO.split()[-1], c.get('date') or '')
            pezzo_regia(p, d, immagini[v['img']], v.get('zoom'), v.get('camera'), v.get('capitolo') or '', nome_font)
        except Exception as e:
            log('inquadratura', k, 'di riserva:', str(e)[:200])
            prec = next((immagini[x['img']] for x in reversed(piano[:k]) if x.get('img') in immagini), None) or next(iter(immagini.values()))
            v.pop('didascalia', None)
            return pezzo_regia(p, d, prec, 'centro', 'push_in')
        if v.get('didascalia') and d > 1.7:
            try:
                aggiungi_didascalia(p, d, v['didascalia'], nome_font)
            except Exception as e:
                log('didascalia saltata:', str(e)[:120]); v.pop('didascalia', None)
        else:
            v.pop('didascalia', None)
        return p
    with ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(fai, range(len(piano))))
    log('inquadrature pronte:', len(paths), 'in', int(time.time() - t0), 's')
    return piano, paths


# ============================================================ MAIN
PESO = {'cartone': 1.6, 'mappa': 3.0, 'scheda': 1.3, 'carta': 1.2, 'pexels_video': 1.0, 'pexels_foto': 1.0}


def blocca_identita(piano):
    """Un personaggio presentato con un NOME (scheda) e' quella persona per tutto il video: altrove compare solo quando
    la voce parla di lei; negli altri punti si toglie (al suo posto un'immagine vera della scena o lo sfondo)."""
    nomi = {}
    for v in piano:
        if v['tipo'] == 'scheda' and v.get('personaggio') and v.get('nome'):
            nomi.setdefault(v['personaggio'], v['nome'])
    for v in piano:
        pg = v.get('personaggio')
        if v['tipo'] != 'cartone' or pg not in nomi:
            continue
        if nominato(v.get('contesto') or '', nomi[pg]):
            continue
        qs = v.get('alt_q') or []
        log(f'personaggio {pg} e\' {nomi[pg]}: tolto dove la voce parla d\'altro')
        if qs:
            for k_ in ('personaggio', 'sfondo', 'reazione', 'data'):
                v.pop(k_, None)
            v.update({'tipo': 'pexels_foto', 'q': qs[0], 'alt_q': qs[1:]})
        else:
            v['personaggio'] = ''


def limita_carte(piano, massimo=CARTE_MINUTO):
    """Al massimo N carte (scritte su texture) ogni 60 secondi: le altre diventano immagini vere della scena."""
    t, tempi = 0.0, []
    for v in piano:
        if v['tipo'] == 'carta':
            if len([x for x in tempi if t - x < 60]) >= massimo:
                qs = query_vicine(piano, v)
                if qs:
                    tq, q = qs[0]
                    v.update({'tipo': tq, 'q': q, 'alt_q': [x[1] for x in qs[1:]]}); v.pop('testo', None)
                else:
                    v.update({'tipo': 'cartone', 'personaggio': ''}); v.pop('testo', None)
                log(f'carta al secondo {t:.0f}: troppe in 60 s, diventa {v["tipo"]}')
            else:
                tempi.append(t)
        t += v['d']


def query_vicine(piano, v):
    stessa = [(x['tipo'], x['q']) for x in piano if x is not v and x.get('contesto') == v.get('contesto')
              and x['tipo'] in ('pexels_video', 'pexels_foto') and x.get('q')]
    return stessa


def limita_personaggi(piano, massimo=PERSONAGGIO_MINUTO):
    if INTEGRATO:   # i personaggi sono dentro disegni unici, ognuno scritto per la sua frase: sostituirli porta immagini incoerenti
        return
    """Lo stesso personaggio al massimo N volte in 60 secondi (stanca lo spettatore). Le apparizioni in piu' diventano:
    un altro personaggio gia' usato nella stessa parte di video, oppure una clip Pexels vicina, oppure lo sfondo senza nessuno."""
    tempi, t = [], 0.0
    for v in piano:
        tempi.append(t); t += v['d']
    visti = {}
    for i, v in enumerate(piano):
        pg = v.get('personaggio') if v['tipo'] in ('cartone', 'scheda') else ''
        if not pg:
            continue
        prima = [x for x in visti.get(pg, []) if tempi[i] - x < 60]
        if len(prima) < massimo or v['tipo'] == 'scheda':   # la scheda (presentazione col nome) resta sempre
            visti.setdefault(pg, []).append(tempi[i]); continue
        vicini = [piano[j] for j in range(max(0, i - 5), min(len(piano), i + 6)) if j != i]
        gia = [piano[j] for j in range(max(0, i - 5), i) if piano[j].get('contesto') == v.get('contesto')]   # gia' visti, stessa scena
        altri = [x.get('personaggio') for x in gia if x['tipo'] == 'cartone' and x.get('personaggio') not in ('', None, pg)]
        altri = [a for a in altri if len([x for x in visti.get(a, []) if tempi[i] - x < 60]) < massimo]
        clip = next((x for x in vicini if x['tipo'] in ('pexels_video', 'pexels_foto') and x.get('q')), None)
        if altri:
            v['personaggio'] = altri[0]; visti.setdefault(altri[0], []).append(tempi[i])
        elif clip:
            for k in ('personaggio', 'sfondo', 'reazione', 'data'):
                v.pop(k, None)
            v.update({'tipo': clip['tipo'], 'q': clip['q']})
        else:
            v['personaggio'] = ''
        log(f'personaggio {pg}: troppe apparizioni in 60 s, al secondo {tempi[i]:.0f} sostituito')


def limite(t):
    """Durata massima di un visivo in base a quando compare (colonna ritmo, es. 3;4;5): primi 10 s / da 10 a 30 s / poi."""
    return RITMO[0] if t < 10 else RITMO[1] if t < 30 else RITMO[2]


def ritmo(piano, sf_ids):
    query_scena = {}
    for x in piano:
        if x['tipo'] in ('pexels_video', 'pexels_foto') and x.get('q'):
            query_scena.setdefault(x.get('contesto'), []).append((x['tipo'], x['q']))
    for x in piano:   # se una ricerca non trova niente si provano le altre della stessa scena prima del cartone
        if x['tipo'] in ('pexels_video', 'pexels_foto'):
            x['alt_q'] = [q for _, q in query_scena.get(x.get('contesto'), []) if q != x.get('q')]
    out = _ritmo(piano, sf_ids, query_scena)
    return out


def _ritmo(piano, sf_ids, query_scena):
    """Spezza i visivi troppo lunghi. Ogni pezzo nuovo e' un'immagine DIVERSA: si sceglie tra cartone e immagine vera
    per restare vicini alla quota del foglio (quota_cartoni) e, per i cartoni, lo sfondo meno usato finora."""
    uso = {x: 0 for x in sf_ids}
    for v in piano:
        if v['tipo'] == 'cartone' and v.get('sfondo') in uso:
            uso[v['sfondo']] += 1
    sec = {'c': 0.0, 'p': 0.0}
    out, t, giro = [], 0.0, 0

    def conta(x):
        if x['tipo'] == 'cartone':
            sec['c'] += x['d']
        elif x['tipo'] in ('pexels_video', 'pexels_foto'):
            sec['p'] += x['d']

    def sfondo_libero(evita, ancora=None, ammessi=()):
        if not sf_ids:
            return None
        sc = scegli_immagine(sf_ids, uso, evita, ancora, ammessi)
        uso[sc] = uso.get(sc, 0) + 1
        return sc
    for v in piano:
        d = v['d']; lim = limite(t)
        if BUDGET > 0 and v['tipo'] == 'cartone':
            lim = max(lim, 9.0)   # un disegno = una sola inquadratura che si muove piano
        n = max(1, round(d / lim))   # pezzi lunghi circa quanto il ritmo del foglio (non molto piu' corti)
        if d / n > lim * 1.15:
            n += 1
        minimo = 2.7 if v['tipo'] in ('carta', 'scheda') else 3.0 if v['tipo'] == 'mappa' else 1.3   # il tempo di leggere
        if v.get('didascalia') and d < 3.8:   # la didascalia ha bisogno di tempo per essere letta: questo visivo non si spezza
            n = 1
        if n <= 1 or d / n < 1.3:
            out.append(v); conta(v); t += d; continue
        primo = max(d / n, min(minimo, d - 1.3 * (n - 1)))
        resto = d - primo; m = n - 1
        while m > 1 and resto / m < 1.3:
            m -= 1
        parti = [dict(v, d=primo)]; conta(parti[0])
        for k in range(1, m + 1):
            giro += 1
            qs = query_scena.get(v.get('contesto'), [])
            prec = parti[-1]
            tot = sec['c'] + sec['p']
            serve_cartone = (sec['c'] / tot * 100 if tot else 0) < QUOTA_CARTONI
            if prec['tipo'] == 'cartone' and qs:   # alternanza: dopo un cartone un'immagine vera
                serve_cartone = False
            elif prec['tipo'] in ('pexels_video', 'pexels_foto') and sf_ids:
                serve_cartone = True
            if BUDGET > 0:   # mai un disegno in piu' (costano e non devono ripetersi): la clip successiva della stessa scena
                serve_cartone = not qs
            if INTEGRATO and v['tipo'] == 'cartone' and v.get('sfondo') and not (BUDGET > 0 and qs):   # stessa immagine (coerente con la frase), inquadratura diversa
                nuovo = {k_: v[k_] for k_ in ('tipo', 'sfondo', 'personaggio', 'contesto', 'pg_scena', 'frase') if k_ in v}
                nuovo['vista_fissa'] = k % 3 + 1
            elif qs and not serve_cartone:   # un'altra immagine vera della stessa scena (mai la stessa clip: Pexels esclude le gia' usate)
                tq, q = qs[giro % len(qs)]
                nuovo = {'tipo': tq, 'q': q, 'contesto': v.get('contesto'), 'alt_q': [x[1] for x in qs if x[1] != q]}
            else:   # un altro luogo disegnato: lo sfondo meno usato, con il personaggio della scena
                vicini = {x.get('sfondo') for x in out[-8:] + parti if x.get('sfondo')}
                ancora = next((x.get('sfondo') for x in reversed(out + parti) if x['tipo'] == 'cartone' and x.get('sfondo')), None)
                sc = sfondo_libero(vicini, ancora, SF_META.get(v.get('sfondo')) or [])
                pg = v.get('personaggio') if v['tipo'] == 'cartone' else v.get('pg_scena')
                if INTEGRATO:
                    pg = (SF_META.get(sc) or [''])[0]
                nuovo = {'tipo': 'cartone', 'sfondo': sc, 'personaggio': pg or '', 'reazione': k % 2 == 1,
                         'contesto': v.get('contesto'), 'pg_scena': v.get('pg_scena')}
            parti.append(dict(nuovo, d=resto / m)); conta(parti[-1])
        out += parti; t += d
    log(f"ritmo: {len(out)} immagini | cartone {sec['c'] / max(1, sec['c'] + sec['p']) * 100:.0f}% (quota {QUOTA_CARTONI}%) | "
        f"sfondi usati: {sum(1 for x in uso.values() if x)}/{len(uso)}, max {max(uso.values()) if uso else 0} volte")
    return out


def _num(x):
    m = re.search(r'\d+', str(x or ''))
    return int(m.group()) if m else 0


def scegli_immagine(ids, uso, evita=(), ancora=None, ammessi=()):
    """L'immagine a cartone da usare per un pezzo nuovo: VICINA nel racconto (stessa epoca: gli id s1..sN seguono la storia),
    poco usata, non appena vista, e senza personaggi diversi da quelli gia' in scena (un re non compare quando si parla d'altro)."""
    a = _num(ancora) if ancora else None
    for raggio in (3, 6, 10, 10 ** 6):
        cand = [x for x in ids if (a is None or abs(_num(x) - a) <= raggio)
                and (not SF_META.get(x) or set(SF_META.get(x)) <= set(ammessi or []))]
        if cand:
            break
    else:
        cand = list(ids)
    return sorted(cand, key=lambda x: (uso.get(x, 0), x in evita, abs(_num(x) - a) if a else 0, random.random()))[0]


def coerenza_immagini(piano):
    """Dopo i controlli su identita' e ripetizioni: se a un cartone e' stato tolto o cambiato il personaggio ma l'immagine lo contiene
    (personaggi DENTRO l'immagine), si cambia immagine con una vicina senza personaggi, o con un'immagine vera della stessa scena."""
    if not INTEGRATO:
        return
    for v in piano:   # l'immagine resta quella scritta per la frase: il personaggio e' quello disegnato dentro
        dentro = (SF_META.get(v.get('sfondo')) or []) if v['tipo'] == 'cartone' else []
        if dentro and v.get('personaggio') not in dentro:
            v['personaggio'] = dentro[0]
    return
    uso = {}
    for v in piano:
        if v['tipo'] == 'cartone' and v.get('sfondo'):
            uso[v['sfondo']] = uso.get(v['sfondo'], 0) + 1
    ids = list(SF_META)
    for i, v in enumerate(piano):
        dentro = (SF_META.get(v.get('sfondo')) or []) if v['tipo'] == 'cartone' else []
        if not dentro or v.get('personaggio') in dentro:
            continue
        liberi = [x for x in ids if not SF_META.get(x)]
        qs = query_vicine(piano, v)
        if qs and (not liberi or i % 2):
            tq, q = qs[0]
            for k_ in ('personaggio', 'sfondo', 'reazione'):
                v.pop(k_, None)
            v.update({'tipo': tq, 'q': q, 'alt_q': [x[1] for x in qs[1:]]})
        elif liberi:
            vicini = {x.get('sfondo') for x in piano[max(0, i - 6): i + 6] if x.get('sfondo')}
            sc = scegli_immagine(liberi, uso, vicini, v.get('sfondo'))
            uso[sc] = uso.get(sc, 0) + 1
            v.update({'sfondo': sc, 'personaggio': ''})
        log(f'immagine {i}: il personaggio disegnato non va bene qui, diventa {v["tipo"]} {v.get("sfondo") or v.get("q")}')


def distanzia_immagini(piano, sf_ids):
    """Lo stesso disegno non torna prima di DISTANZA_IMMAGINI secondi (lo spettatore se ne accorge: 'scena gia' vista').
    Al suo posto: un disegno mai usato o usato da piu' tempo (vicino nel racconto); se non c'e', un'immagine vera della stessa scena;
    solo come ultima scelta resta lo stesso disegno (zoomato o specchiato)."""
    if INTEGRATO:   # ogni disegno e' fatto per la SUA frase: scambiarlo con un altro porta immagini che non c'entrano (es. grotta mentre si parla dell'Egitto)
        log('disegni ripetuti: nessuno scambio (ogni immagine resta sulla sua frase)'); return
    ultimo, uso, t, cambiati = {}, {}, 0.0, 0
    for v in piano:
        if v['tipo'] == 'cartone' and v.get('sfondo'):
            uso[v['sfondo']] = uso.get(v['sfondo'], 0) + 1
    for i, v in enumerate(piano):
        sc = v.get('sfondo') if v['tipo'] == 'cartone' else None
        di_fila = i > 0 and piano[i - 1].get('tipo') == 'cartone' and piano[i - 1].get('sfondo') == sc   # stessa immagine, altra inquadratura: va bene
        if sc and not di_fila and t - ultimo.get(sc, -1e9) < DISTANZA_IMMAGINI:
            liberi = [x for x in sf_ids if t - ultimo.get(x, -1e9) >= DISTANZA_IMMAGINI
                      and (not INTEGRATO or not SF_META.get(x) or v.get('personaggio') in SF_META.get(x))]
            nuovo = scegli_immagine(liberi, uso, (), sc, SF_META.get(sc) or []) if liberi else None
            if nuovo and (not INTEGRATO or not SF_META.get(nuovo) or set(SF_META[nuovo]) <= set(SF_META.get(sc) or [])):
                uso[nuovo] = uso.get(nuovo, 0) + 1
                v['sfondo'] = nuovo
                if INTEGRATO:
                    v['personaggio'] = (SF_META.get(nuovo) or [''])[0]
                cambiati += 1
            else:
                qs = query_vicine(piano, v)
                if qs:
                    tq, q = qs[i % len(qs)]
                    for k_ in ('personaggio', 'sfondo', 'reazione'):
                        v.pop(k_, None)
                    v.update({'tipo': tq, 'q': q, 'alt_q': [x[1] for x in qs if x[1] != q]}); cambiati += 1
            sc = v.get('sfondo') if v['tipo'] == 'cartone' else None
        if sc:
            ultimo[sc] = t
        t += v['d']
    log(f'disegni ripetuti entro {DISTANZA_IMMAGINI:.0f} s sostituiti: {cambiati}')


def verifica_sfondi(piano, sf, c):
    """Claude guarda ogni immagine a cartone e la confronta con le frasi della voce in cui compare: se non c'entra
    (es. grotta quando si dice 'verde dal mare al mare') o ha persone del popolo sbagliato, la fa rifare una volta."""
    frasi = {}
    for v in piano:
        if v['tipo'] == 'cartone' and v.get('sfondo') in sf:
            f = str(v.get('frase') or '').strip() or str(v.get('contesto') or '')[:160]
            if f and f not in frasi.setdefault(v['sfondo'], []):
                frasi[v['sfondo']].append(f)
    per_id = {s_['id']: s_ for s_ in c.get('sfondi') or []}

    def uno(i):
        motivo = verifica_immagine(sf[i], ' / '.join(frasi[i])[:500], per_id.get(i, {}).get('prompt_en', ''))
        if not motivo or i not in per_id:
            return 0
        if BUDGET > 0 and SPESA['fal'] + PREZZO_DISEGNO > BUDGET * 1.08 - 0.6:
            log(f'immagine {i} da rifare ({motivo}) ma il tetto di spesa e\' raggiunto: resta'); return 0
        log(f'immagine {i} rifatta: {motivo}')
        vecchie = []
        for x in (sf[i], sf[i][:-4] + '_full.jpg'):
            if os.path.exists(x):
                os.replace(x, x + '.old'); vecchie.append(x)
        try:
            sfondo(dict(per_id[i], prompt_en=per_id[i]['prompt_en'] + '. IMPORTANT: ' + motivo))
            for x in vecchie:
                os.remove(x + '.old')
            for f in os.listdir(LAV):   # inquadrature della vecchia immagine
                if f.startswith(os.path.basename(sf[i])[:-4] + '_v'):
                    os.remove(os.path.join(LAV, f))
            return 1
        except Exception as e:
            for x in vecchie:
                os.replace(x + '.old', x)
            log('immagine non rifatta, tengo la prima:', str(e)[:120]); return 0
    with ThreadPoolExecutor(4) as ex:
        n = sum(ex.map(uno, list(frasi)))
    log(f'controllo immagini: {len(frasi)} guardate, {n} rifatte')


def viste_sfondi(piano):
    """Lo stesso sfondo usato piu' volte non deve sembrare la stessa immagine: 2a volta zoom a sinistra, 3a a destra, 4a specchiato."""
    n, prec = {}, None
    for v in piano:
        if v['tipo'] == 'cartone' and v.get('sfondo'):
            if v.get('vista_fissa'):
                v['vista'] = v['vista_fissa']
            else:
                v['vista'] = n.get(v['sfondo'], 0) % 4
                if prec and prec.get('sfondo') == v['sfondo'] and prec.get('vista') == v['vista']:
                    v['vista'] = (v['vista'] + 1) % 4
            n[v['sfondo']] = n.get(v['sfondo'], 0) + 1
        prec = v


def vista_sfondo(bg, vista):
    if not vista:
        return bg
    out = bg[:-4] + f'_v{vista}.jpg'
    if not os.path.exists(out):
        full = bg[:-4] + '_full.jpg'
        im = Image.open(full if os.path.exists(full) else bg).convert('RGB'); w, h = im.size
        if INTEGRATO:   # personaggi dentro l'immagine: inquadrature diverse (centro / sinistra / destra), MAI specchiate
            z = {1: 1.35, 2: 1.6, 3: 1.6}[vista]
            cw, ch = int(w / z), int(h / z)
            x = {1: (w - cw) // 2, 2: int(w * 0.04), 3: w - cw - int(w * 0.04)}[vista]
            im = im.crop((x, (h - ch) // 3, x + cw, (h - ch) // 3 + ch))
        elif vista == 3:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        else:
            cw, ch = int(w / 1.45), int(h / 1.45); x = 0 if vista == 1 else w - cw
            im = im.crop((x, h - ch, x + cw, h))   # tiene il terreno in basso: il personaggio resta appoggiato
        im.resize((W, H), Image.LANCZOS).save(out, quality=92)
    return out


def pianifica(scene, durs, voci, sf):
    """Divide ogni scena in visivi che compaiono quando la voce dice la loro 'frase'."""
    piano = []
    for i, (s, D) in enumerate(zip(scene, durs)):
        testo = s.get('testo_voce') or s['testo']   # le lettere della voce corrispondono a questo testo
        try:
            al = json.load(open(voci[i][:-4] + '.json'))
        except Exception:
            al = {}
        n_al = len((al or {}).get('character_start_times_seconds') or [])
        if n_al and n_al != len(testo):
            log(f'scena {i}: tempi della voce non allineati al testo ({n_al} lettere contro {len(testo)}): uso la stima')
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
            idx = trova(testo, parlato(frase), pos) if frase else None
            if idx is not None:
                pos = idx + 1
                t = max(0.0, tempo_lettera(al, idx, testo, D) - 0.15)   # appena prima della parola
            elif j and frase and (v.get('personaggio') or v['tipo'] in ('carta', 'scheda')):
                log('visivo tolto (parole non trovate nella voce):', v['tipo'], v.get('personaggio') or v.get('testo') or '', '|', frase[:40])
                continue   # un personaggio o una scritta non deve MAI comparire prima che la voce ne parli
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
                if v['tipo'] in ('carta', 'scheda'):   # la scritta/presentazione ha la precedenza: non sparisce mai
                    if len(tenuti) > 1 and t >= tenuti[-2][1] + 1.2:
                        tenuti[-1] = (v, t)
                    elif tenuti[-1][1] + 1.2 < D - 1.5:
                        tenuti.append((v, tenuti[-1][1] + 1.2))   # entra poco dopo, mentre la voce la sta dicendo
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




def norm_paese(t):
    t = re.sub(r'[^a-z ]', ' ', str(t).lower())
    t = re.sub(r'\b(the|ancient|empire|of|history|entire|kingdom|republic)\b', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return {'roman': 'rome', 'persia': 'iran', 'persian': 'iran', 'usa': 'united states', 'america': 'united states'}.get(t, t)


def paese_video(comp):
    """Il paese (o impero) raccontato dal video competitor, in inglese: serve a non fare mai due video sullo stesso paese."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        return ''
    testo = f"Titolo: {comp.get('titolo', '')}\nInizio del parlato: {' '.join((comp.get('testo') or '').split()[:250])}"
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_CONTROLLO, 'max_tokens': 30, 'messages': [{'role': 'user', 'content':
                 testo + "\n\nDi quale paese racconta la storia questo video? Rispondi SOLO con il nome del paese di oggi in inglese "
                 "(es. Persia -> Iran, Prussia -> Germany). Se e' un impero senza paese di oggi (es. Roman Empire, Mongol Empire) scrivi il nome dell'impero in inglese. "
                 "Correggi eventuali errori di battitura del titolo (es. 'History of Iron' che parla dell'Iran -> Iran)."}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=60)
        p = ''.join(b.get('text', '') for b in r.get('content', [])).strip().split('\n')[0].strip(' ."\'')
        log('paese del video:', p)
        return p[:60]
    except Exception as e:
        log('paese non riconosciuto:', str(e)[:120])
        return ''


def capitoli(scene, durs):
    """Capitoli YouTube con i tempi VERI della voce: '0:00 Titolo' (almeno 3, distanti almeno 10 s, il primo a 0:00)."""
    righe, t, ultimo = [], 0.0, -100
    for i, (s, d) in enumerate(zip(scene, durs)):
        tit = re.sub(r'\s+', ' ', str(s.get('capitolo') or '')).strip()
        if tit and (i == 0 or t - ultimo >= 10):
            tt = 0 if not righe else int(t)
            righe.append((f'{tt // 3600}:{tt % 3600 // 60:02d}:{tt % 60:02d}' if tt >= 3600 else f'{tt // 60}:{tt % 60:02d}') + ' ' + tit[:60])
            ultimo = t
        t += d
    if righe and not righe[0].startswith('0:00'):
        righe[0] = '0:00 ' + righe[0].split(' ', 1)[1]
    if len(righe) < 3:
        log('capitoli: meno di 3, non inseriti'); return ''
    log('capitoli:', len(righe))
    return 'Capitoli:\n' + '\n'.join(righe)


def minuti_giusti(testo, n):
    """'in 11 Minuti' -> 'in 13 Minuti' (stesso maiuscolo/minuscolo, singolare se 1). Vale anche per 'minutes' e 'min'."""
    def sost(m):
        parola = m.group(3); base = parola.lower()
        if base.startswith('minut') and base[-1] in 'oi':        # italiano
            nuova = 'minuto' if n == 1 else 'minuti'
        elif base.startswith('minute'):                            # inglese
            nuova = 'minute' if n == 1 else 'minutes'
        else:
            nuova = base
        nuova = nuova.upper() if parola.isupper() else nuova.capitalize() if parola[0].isupper() else nuova
        return str(n) + m.group(2) + nuova
    nuovo = re.sub(r'(?<![\d.,])(\d{1,3})(\s*)(minut[oi]|minutes?|min)\b', sost, testo, flags=re.I)
    if nuovo != testo:
        log('minuti nel titolo/copertina aggiornati:', testo, '->', nuovo)
    return nuovo


def main():
    os.makedirs(LAV, exist_ok=True)
    comp = competitor()
    # stesso paese gia' fatto? stop prima di spendere (voce, immagini): la riga va in DOPPIONE e al giro dopo parte il paese successivo
    paese = paese_video(comp)
    INFO_COMP['paese'] = paese; PAESE['nome'] = paese
    fatti = {norm_paese(str(x).split(' = ')[0]): x for x in (P.get('paesi_fatti') or []) if str(x).strip()}   # "Iran = STO-001"
    if paese and norm_paese(paese) in fatti:
        msg = f'DOPPIONE: {paese} e\' gia\' stato fatto (' + str(fatti[norm_paese(paese)]) + '). Video NON prodotto, nessun costo.'
        log(msg)
        avvisa({'stato': 'DOPPIONE', 'errore': msg, 'paese': paese, 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1)})
        sys.exit(0)
    INFO_COMP.update({'categoria_originale': comp.get('categoria') or '', 'tag_originali': ', '.join(comp.get('tag_originali') or [])[:2000]})
    salvato = os.path.join(LAV, 'copione_lavoro.json')
    if os.path.exists(salvato):   # ripresa dopo un errore: stesso copione, niente nuova spesa
        c = json.load(open(salvato))
        n_v = len([f for f in os.listdir(LAV) if f.startswith('voce_') and f.endswith('.mp3')])
        n_d = len([f for f in os.listdir(LAV) if re.match(r'sfondo_s\d+\.jpg$', f)])
        log(f'RIPRESA: copione salvato, {n_v} voci e {n_d} disegni gia\' pronti (non si ripagano)')
    else:
        c = copione(comp)
        json.dump(c, open(salvato, 'w'), ensure_ascii=False)
    c['categoria_originale'] = comp.get('categoria') or ''
    titolo_finale = c.get('titolo') or TITOLO
    json.dump(c, open(os.path.join(ROOT, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
    kit = kit_disponibile()
    mancanti = list(c.get('personaggi_mancanti') or [])
    for s_ in c.get('sfondi') or []:   # personaggi del kit disegnati DENTRO ogni immagine a cartone
        SF_META[s_['id']] = [x for x in (s_.get('personaggi') or []) if x in kit and x != NARRATORE][:2]
    log('copione:', len(c['scene']), 'scene,', sum(len(s['testo'].split()) for s in c['scene']), 'parole')
    # voce
    with ThreadPoolExecutor(2) as ex:   # ElevenLabs accetta poche richieste insieme (errore 429 con 4)
        testi = [parlato(s['testo']) for s in c['scene']]   # numeri e sigle scritti per esteso: la voce li legge bene
        for s_, t_ in zip(c['scene'], testi):
            s_['testo_voce'] = t_
        voci = list(ex.map(lambda i: voce(i, testi[i], ' '.join(testi[:i])[-400:], ' '.join(testi[i + 1:])[:400]), range(len(testi))))
    durs = [durata(v) for v in voci]
    # ritmo della voce uguale dall'inizio alla fine: una scena letta piu' lenta delle altre (succede spesso alla prima) si rifa' un po' piu' veloce
    ritmi = [len(t.split()) / max(.5, d) for t, d in zip(testi, durs)]
    medio = sorted(ritmi)[len(ritmi) // 2] if ritmi else 0
    for i, r in enumerate(ritmi):
        if False and medio and r < medio * .93 and len(testi[i].split()) >= 8:   # disattivato: il cambio di velocita' si sentiva
            vel = round(min(1.15, medio / r), 2)
            log(f'voce scena {i}: {r:.2f} parole/s contro {medio:.2f} di media -> rifatta a velocita {vel}')
            try:
                voci[i] = voce(i, testi[i], ' '.join(testi[:i])[-400:], ' '.join(testi[i + 1:])[:400], vel)
                durs[i] = durata(voci[i])
            except Exception as e:
                log('voce non rifatta:', str(e)[:120])
    # titolo e copertina copiati al 100%: se citano i minuti del video originale, si mettono i minuti VERI del nostro video
    minuti_veri = max(1, int(round(sum(durs) / 60)))
    titolo_finale = minuti_giusti(titolo_finale, minuti_veri)
    if isinstance(c.get('copertina'), dict) and c['copertina'].get('testo'):
        c['copertina']['testo'] = minuti_giusti(str(c['copertina']['testo']), minuti_veri)
    c['titolo'] = titolo_finale
    c['capitoli_testo'] = capitoli(c['scene'], durs)
    if c.get('descrizione'):
        c['descrizione'] = minuti_giusti(str(c['descrizione']), minuti_veri)
    log('voce pronta:', round(sum(durs) / 60, 1), 'minuti')
    if REGIA:   # solo cartoni: un'immagine scritta su ogni frase della voce
        piano, paths = video_regia(c, durs, voci, kit)
    else:
        # sfondi
        RISERVA_PX[:] = [str(x).strip() for x in (c.get('riserva_pexels') or []) if str(x).strip()][:10] or \
            [f"{c.get('paese_mappa') or 'ancient'} {x}" for x in ('landscape', 'river', 'mountains', 'ancient ruins', 'sky clouds', 'temple')]
        if BUDGET > 0:   # rete di sicurezza: mai piu' disegni di quanti ne paga il budget, anche se il copione ne chiede di piu'
            sec_v = sum(durs)
            massimo = max(2, int((BUDGET * 1.08 - (0.35 + 0.15 + 0.05 + sec_v / 5 * 0.005)) / (PREZZO_DISEGNO * 1.25)))
            if len(c['sfondi']) > massimo:
                tenuti = {x['id'] for x in c['sfondi'][:massimo]}
                log(f"budget: il copione chiede {len(c['sfondi'])} disegni, se ne fanno {massimo}; gli altri diventano clip Pexels")
                c['sfondi'] = c['sfondi'][:massimo]
                for sc_ in c['scene']:
                    for v in sc_.get('visivi') or []:
                        if v.get('tipo') == 'cartone' and v.get('sfondo') not in tenuti:
                            q = str(v.get('q') or '') or (RISERVA_PX[0] if RISERVA_PX else (c.get('paese_mappa') or 'ancient') + ' landscape')
                            v.update({'tipo': 'pexels_video', 'q': q}); v.pop('sfondo', None); v.pop('personaggio', None)
        with ThreadPoolExecutor(3) as ex:
            sf = dict(zip([s['id'] for s in c['sfondi']], ex.map(sfondo, c['sfondi'])))
        tex = texture(c.get('texture') or 'pergamena') if TEXTURE else Image.new('RGB', (W, H), (240, 232, 214))
        nome_font = c.get('font_carte') if c.get('font_carte') in FONT_EPOCA else 'classico'
        # fondi delle carte: 3 immagini a tema (bordi decorati, centro libero) + la carta dell'epoca + 2 colori a tinta unita
        fondi = [prepara_fondo(tex)]
        fondi_ai = []
        for col in (c.get('colori_carte') or ['#6b1e1e', '#1d3557'])[:2]:
            try:
                fondi.append(prepara_fondo(tinta(tex, str(col))))
            except Exception as e:
                log('colore carta saltato:', col, e)
        if E('FAL_KEY') and c.get('fondi_carte') and TEXTURE:
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
            fondi = ai or mix; fondi_ai = ai   # gli spettatori vogliono immagini a tema: niente fondi neutri se ci sono quelli a tema
        # piano dei pezzi
        piano = pianifica(c['scene'], durs, voci, sf)
        for v in piano:
            if v.get('personaggio') and v['personaggio'] not in kit:
                mancanti.append(v['personaggio']); v['personaggio'] = ''
        # un cartone ha il personaggio della SUA scena; se la scena non ne ha uno coerente nel kit, nessuno (meglio vuoto che fuori contesto)
        usati = [v.get('personaggio') for v in piano if v.get('tipo') == 'cartone' and v.get('personaggio') and v['personaggio'] != NARRATORE]
        pg_video = max(set(usati), key=usati.count) if usati else (kit[0] if kit else '')
        for v in piano:
            if v.get('pg_scena') not in kit:
                v['pg_scena'] = ''
            if INTEGRATO and v['tipo'] == 'cartone':   # il personaggio e' quello disegnato dentro l'immagine
                dentro = SF_META.get(v.get('sfondo')) or []
                v['personaggio'] = v.get('personaggio') if v.get('personaggio') in dentro else (dentro[0] if dentro else '')
            elif v['tipo'] == 'cartone' and not v.get('personaggio'):
                v['personaggio'] = v['pg_scena']
        togli_texture(piano)
        piano = ritmo(piano, list(sf))
        for v in piano:   # il narratore (avatar del canale) non compare MAI nei video
            if v.get('personaggio') == NARRATORE:
                v['personaggio'] = ''
        blocca_identita(piano)
        limita_carte(piano)
        limita_personaggi(piano)
        coerenza_immagini(piano)
        distanzia_immagini(piano, list(sf))
        togli_texture(piano)
        viste_sfondi(piano)
        if VERIFICA and E('FAL_KEY'):
            verifica_sfondi(piano, sf, c)
        log('visivi:', len(piano), '| primi 10 s:', sum(1 for x in __import__('itertools').accumulate([0] + [v['d'] for v in piano]) if x < 10))
        # durate a fotogrammi interi: video e voce restano allineati fino all'ultimo secondo
        fine_prec, acc = 0, 0.0
        for v in piano:
            acc += v['d']; fine = int(round(acc * FPS))
            v['d'] = max(1, fine - fine_prec) / FPS; fine_prec = fine
        n_carte, n_schede, ultimo_sfondo = 0, 0, (list(sf)[0] if sf else None)
        decorati = [i for i, f in enumerate(fondi) if any(f is a for a in fondi_ai)] or list(range(len(fondi)))
        for v in piano:   # carte: fondi a rotazione; schede dei personaggi: SEMPRE su un fondo decorato a tema
            if v['tipo'] == 'carta':
                v['fondo'] = n_carte % len(fondi); n_carte += 1
            elif v['tipo'] == 'scheda':
                v['fondo'] = decorati[n_schede % len(decorati)]; n_schede += 1
                v['sfondo_scheda'] = ultimo_sfondo
            if v['tipo'] == 'cartone' and v.get('sfondo'):
                ultimo_sfondo = v['sfondo']
            v['sfondo_ultimo'] = ultimo_sfondo

        def fai(k):
            v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4'); t = v['tipo']
            try:
                if t in ('pexels_video', 'pexels_foto'):
                    u = None
                    for qq in [v.get('q') or 'ancient ruins'] + list(v.get('alt_q') or [])[:2] + random.sample(RISERVA_PX, min(3, len(RISERVA_PX))):
                        u = pexels('video' if t == 'pexels_video' else 'foto', qq, v.get('contesto') or '')
                        if u:
                            break
                    if not u:
                        raise RuntimeError('nessun risultato Pexels per ' + str(v.get('q')))
                    src = os.path.join(LAV, f'src_{k:04d}' + ('.mp4' if t == 'pexels_video' else '.jpg'))
                    scarica(u, src)
                    pezzo_video(p, d, src) if t == 'pexels_video' else pezzo_foto(p, d, src)
                    return con_didascalia(p, d, v)
                if t == 'carta':
                    return pezzo_carta(p, d, v.get('testo') or '', fondi[v.get('fondo', 0)], nome_font)
                if t == 'scheda':   # il personaggio si presenta dentro un luogo della storia (sfondo a cartone del video), mai su fondo neutro
                    bg = sf.get(v.get('sfondo_scheda')) or list(sf.values())[k % len(sf)]
                    return pezzo_scheda(p, d, (Image.open(bg).convert('RGB').resize((W, H), Image.LANCZOS), INK), v.get('personaggio') or '', v.get('nome') or '', nome_font)
                if t == 'mappa':
                    return pezzo_mappa(p, d, c.get('paese_mappa') or '', c.get('titolo_mappa') or TITOLO.split()[-1], c.get('date') or '')
                pezzo_cartone(p, d, vista_sfondo(sf.get(v.get('sfondo')) or list(sf.values())[k % len(sf)], v.get('vista', 0)),
                              '' if INTEGRATO else (v.get('personaggio') or ''),
                              bool(v.get('reazione')), v.get('data') or '', k % 2 == 0)
                return con_didascalia(p, d, v)
            except Exception as e:   # riserva: cartone senza personaggio su uno sfondo poco usato (mai la stessa immagine di prima)
                log('pezzo', k, t, 'non riuscito:', str(e)[:200])
                if BUDGET > 0 or not TEXTURE:   # mai un'immagine a caso: si continua l'immagine precedente (vedi sotto)
                    v.pop('didascalia', None); v['continua'] = True
                    return None
                v.pop('didascalia', None); v['tipo'] = 'cartone'
                with _lock:
                    liberi = [x for x in sf if not (INTEGRATO and SF_META.get(x))] or list(sf)   # mai un personaggio a caso
                    ids = sorted(liberi, key=lambda x: (_riserva.get(x, 0), x == v.get('sfondo_ultimo'), abs(_num(x) - _num(v.get('sfondo_ultimo'))), random.random()))
                    sc = ids[0]; _riserva[sc] = _riserva.get(sc, 0) + 1
                return pezzo_cartone(p, d, vista_sfondo(sf[sc], 1 + (_riserva[sc] + k) % 3), '', False, '', True)

        def con_didascalia(p, d, v):
            if v.get('didascalia') and d > 1.7:
                try:
                    return aggiungi_didascalia(p, d, str(v['didascalia'])[:60], nome_font)
                except Exception as e:
                    log('didascalia saltata:', str(e)[:150])
            v.pop('didascalia', None)
            return p
        t0 = time.time()
        with ThreadPoolExecutor(2) as ex:
            paths = list(ex.map(fai, range(len(piano))))
        for k, pth in enumerate(paths):   # pezzo senza immagine giusta: continua l'immagine precedente (ultimo fotogramma, zoom lento)
            if pth:
                continue
            prec = next((paths[j] for j in range(k - 1, -1, -1) if paths[j]), None) or next((x for x in paths if x), None)
            fermo = os.path.join(LAV, f'fermo_{k:04d}.jpg')
            try:
                run(['ffmpeg', '-y', '-v', 'error', '-sseof', '-0.2', '-i', prec, '-frames:v', '1', fermo])
            except Exception:
                run(['ffmpeg', '-y', '-v', 'error', '-i', prec, '-frames:v', '1', fermo])
            paths[k] = pezzo_foto(os.path.join(LAV, f'pezzo_{k:04d}.mp4'), piano[k]['d'], fermo)
            log(f'pezzo {k}: continua l\'immagine precedente (nessuna immagine coerente trovata)')
        log('pezzi pronti:', len(paths), 'in', int(time.time() - t0), 's')
        log(f"SPESA immagini: {SPESA['disegni']} immagini, circa {SPESA['fal']:.2f} $" + (f' (tetto {BUDGET:.2f} EUR a video)' if BUDGET else ''))
    video = os.path.join(LAV, 'muto.mp4')
    unisci([(p, v['d']) for p, v in zip(paths, piano)], video)
    video = applica_cornice(video, c)
    # audio: voce + musica (facoltativa)
    lista = os.path.join(LAV, 'voci.txt'); open(lista, 'w').write(''.join(f"file '{v}'\n" for v in voci))
    voce_tot = os.path.join(LAV, 'voce.m4a')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c:a', 'aac', '-b:a', '192k', voce_tot])
    # tasti della macchina da scrivere, a tempo con le lettere che compaiono
    eventi, t_ini = [], 0.0
    for v in piano:
        d = v['d']
        if v['tipo'] == 'carta':
            eventi += [t_ini + x for x in tasti(v.get('testo') or '', .3, dur_carta(d), d)]
        elif v['tipo'] == 'scheda':
            eventi += [t_ini + x for x in tasti(v.get('nome') or '', .6, dur_scheda(d), d)]
        elif v.get('didascalia'):
            eventi += [t_ini + x for x in tasti(str(v['didascalia'])[:60], .45, dur_did(d), d)]
        t_ini += d - T_TR
    if eventi and TASTI:
        try:
            wav = suono_tasti(eventi, sum(durs), os.path.join(LAV, 'tasti.wav'))
            con_tasti = os.path.join(LAV, 'voce_tasti.m4a'); vt = float(E('TASTI_VOL', '0.22') or .22)
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-i', wav, '-filter_complex',
                 f'[1:a]volume={vt}[k];[0:a][k]amix=inputs=2:duration=first:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', con_tasti])
            voce_tot = con_tasti
            log('tasti macchina da scrivere:', len(eventi))
        except Exception as e:
            log('suono tasti saltato:', str(e)[:150])
    if SUONI_CAMBIO:   # click / swoosh / pop a ogni cambio immagine: danno ritmo
        try:
            wav = pista_cambi(piano, sum(durs), os.path.join(LAV, 'cambi.wav'))
            con_c = os.path.join(LAV, 'voce_cambi.m4a')
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-i', wav, '-filter_complex',
                 f'[1:a]volume={SUONI_CAMBIO_VOL}[k];[0:a][k]amix=inputs=2:duration=first:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', con_c])
            voce_tot = con_c
        except Exception as e:
            log('suoni di cambio saltati:', str(e)[:150])
    try:   # effetti da film sotto la voce: si abbassano da soli quando la voce parla (come nei film)
        fx = pista_effetti(piano, sum(durs))
        if fx:
            con_fx = os.path.join(LAV, 'voce_fx.m4a'); vf = float(str(P.get('effetti_volume') or E('EFFETTI_VOL', '') or .7).replace(',', '.'))
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-i', fx, '-filter_complex',
                 f'[0:a]asplit=2[v][sc];[1:a]volume={vf}[f];[f][sc]sidechaincompress=threshold=0.08:ratio=2:attack=40:release=300[fd];'
                 f'[v][fd]amix=inputs=2:duration=first:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', con_fx])
            voce_tot = con_fx
    except Exception as e:
        log('effetti sonori saltati:', str(e)[:150])
    audio = voce_tot
    brani = [u.strip() for u in re.split(r'\|\||\n', MUSICA_URL) if u.strip()]
    if brani:   # piu' brani separati da || : uno per video, a rotazione
        try:
            url = brani[int(hashlib.md5(str(P.get('id') or TITOLO).encode()).hexdigest(), 16) % len(brani)]
            mf = scarica(url, os.path.join(LAV, 'musica.mp3'))
            audio = os.path.join(LAV, 'audio.m4a'); vol = float(str(P.get('musica_vol') or E('MUSICA_VOL', '') or .06).replace(',', '.').replace('%', ''))
            vol = vol / 100 if vol > 1 else vol   # 6 o 6% = 0.06
            tot = durata(voce_tot)
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-stream_loop', '-1', '-i', mf, '-filter_complex',
                 f'[1:a]volume={vol},afade=t=in:d=2,afade=t=out:st={max(0, tot - 4):.2f}:d=4[m];'
                 f'[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', audio])
            log('musica:', url[-40:], 'volume', vol)
        except Exception as e:
            log('musica saltata:', e)
    finale = os.path.join(ROOT, 'video_storia.mp4')
    if not iscrizione(video, audio, finale):
        run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'copy', '-shortest', finale])
    cop = copertina(comp, c)
    open(os.path.join(ROOT, 'titolo.txt'), 'w').write(titolo_finale)
    if CARICA:
        t0c = time.time()
        vid = carica_youtube(finale, c, titolo_finale)
        note = [x for x in (carica_copertina(vid, cop), playlist_video(vid, titolo_finale)) if x]
        avvisa({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'titolo': titolo_finale,
                'testo_copertina': str((c.get('copertina') or {}).get('testo') or ''), 'pubblica_il': P.get('pubblica_il') or '',
                'minuti_video': round(durata(finale) / 60, 1), 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1),
                'errore': '; '.join(note)})
    elif P.get('id'):
        avvisa({'stato': 'PROVA OK' if PROVA else 'CREATO', 'minuti_video': round(durata(finale) / 60, 1),
                'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1), 'titolo': titolo_finale})
    open(os.path.join(ROOT, 'personaggi_mancanti.txt'), 'w').write('\n'.join(sorted(set(m for m in mancanti if m))))
    log('FATTO:', finale, round(durata(finale) / 60, 1), 'minuti')


# ============================================================ INVITO ISCRIZIONE (colonne subscribe_overlay_* di Channel Configs)
def iscrizione(video, audio, finale):
    """Immagine "ISCRIVITI / SUBSCRIBE" nella lingua del canale al secondo N per 4 s + clic + campanella (come json2video).
    Restituisce False se non c'e' nulla da fare o se qualcosa va storto (il video esce comunque, senza invito)."""
    isc = P.get('iscrizione') or {}
    img = str(isc.get('img') or '').strip()
    if not img:
        return False
    try:
        num = lambda v, d: float(str(v).replace(',', '.')) if str(v if v is not None else '').strip() != '' else d
        sec = num(isc.get('sec'), 10.0); clic = num(isc.get('clic_ritardo'), 0.6)
        png = scarica(img, os.path.join(LAV, 'iscriviti.png'))
        ins = ['-i', video, '-i', audio, '-loop', '1', '-t', '%.3f' % durata(video), '-i', png]
        fl = (f"[2:v]scale=900:-1,format=rgba,fade=t=in:st={sec}:d=0.3:alpha=1,fade=t=out:st={sec + 3.6}:d=0.4:alpha=1[isc];"
              f"[0:v][isc]overlay=x=(W-w)/2:y=640:enable='between(t,{sec},{sec + 4})'[v]")
        suoni, k = [], 3
        for url, quando, nome in ((isc.get('clic'), sec + clic, 'clic'), (isc.get('campana'), sec + clic + num(isc.get('campana_ritardo'), 1.0), 'campana')):
            if not str(url or '').strip():
                continue
            try:
                f = scarica(str(url).strip(), os.path.join(LAV, nome + '.mp3'))
            except Exception as e:
                log(nome, 'non disponibile:', str(e)[:80]); continue
            ins += ['-i', f]; ms = int(quando * 1000)
            fl += f";[{k}:a]adelay={ms}|{ms},volume=0.5[s{k}]"; suoni.append(f'[s{k}]'); k += 1
        amap = '1:a'
        if suoni:
            fl += f";[1:a]{''.join(suoni)}amix=inputs={len(suoni) + 1}:duration=first:normalize=0[a]"; amap = '[a]'
        run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', fl, '-map', '[v]', '-map', amap, *ENC, '-c:a', 'aac', '-b:a', '192k', '-shortest', finale])
        log(f'invito iscrizione al secondo {sec} con {len(suoni)} suoni')
        return True
    except Exception as e:
        log('invito iscrizione saltato:', str(e)[:200])
        return False


# ============================================================ YOUTUBE (caricamento sul canale + avviso a n8n)
T_INIZIO = time.time()
INFO_COMP = {}   # categoria e tag del competitor: tornano nel foglio di produzione con l'esito


def token():
    data = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                   'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=data), timeout=60) as r:
        return json.loads(r.read().decode())['access_token']


def lista_tag(titolo, tag):
    out, lung = [], 0
    for t in [titolo] + [str(x) for x in (tag or [])]:
        t = re.sub(r'\s+', ' ', re.sub(r'[<>,]', ' ', t)).strip()
        if not t or any(x.lower() == t.lower() for x in out):
            continue
        costo = len(t) + (2 if ' ' in t else 0) + (1 if out else 0)
        if lung + costo > 480:
            continue
        out.append(t); lung += costo
    return out


def carica_youtube(path, c, titolo):
    if not E('YT_REFRESH_TOKEN'):
        raise RuntimeError('manca il secret YT_REFRESH_TOKEN_STORIA su GitHub: video creato ma non caricato')
    tok = token()
    descr = '\n\n'.join(x for x in [titolo, str(c.get('descrizione') or '').strip(), str(c.get('capitoli_testo') or '').strip(),
                                     str(P.get('descrizione_base') or '').strip()] if x)
    snippet = {'title': titolo[:100], 'description': descr[:4900], 'tags': lista_tag(titolo, c.get('tag')),
               'categoryId': str(c.get('categoria_originale') or P.get('categoria') or '27'), 'defaultLanguage': LINGUA, 'defaultAudioLanguage': LINGUA}
    status = {'privacyStatus': P.get('privacy') or 'public', 'selfDeclaredMadeForKids': False}
    if P.get('pubblica_il'):
        status['privacyStatus'] = 'private'; status['publishAt'] = P['pubblica_il']
    size = os.path.getsize(path)
    req = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                                 data=json.dumps({'snippet': snippet, 'status': status}).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8',
                                          'X-Upload-Content-Length': str(size), 'X-Upload-Content-Type': 'video/mp4'})
    with urllib.request.urlopen(req, timeout=120) as r:
        sessione = r.headers['Location']
    log(f'upload di {size / 1e6:.0f} MB')
    for tentativo in range(6):
        try:
            put = urllib.request.Request(sessione, data=open(path, 'rb').read(), method='PUT',
                                         headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'video/mp4'})
            with urllib.request.urlopen(put, timeout=1800) as r:
                vid = json.loads(r.read().decode())['id']
                log('caricato su YouTube:', vid)
                return vid
        except urllib.error.HTTPError as e:
            if e.code == 401:
                tok = token()
            elif e.code not in (500, 502, 503, 504):
                raise RuntimeError('YouTube ha rifiutato il caricamento: ' + str(e.code) + ' ' + e.read().decode()[:400])
            log('upload, riprovo:', e.code)
        except Exception as e:
            log('upload, errore di rete, riprovo:', str(e)[:150])
        time.sleep(15 * (tentativo + 1))
    raise RuntimeError('caricamento su YouTube non riuscito')


def carica_copertina(video_id, img):
    if not img:
        return 'copertina non creata'
    try:
        req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}',
                                     data=open(img, 'rb').read(), method='POST', headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'image/jpeg'})
        urllib.request.urlopen(req, timeout=120).read()
        return ''
    except Exception as e:
        return 'copertina non caricata: ' + str(e)[:200]


def playlist_video(video_id, titolo):
    """Impostazioni -> playlist:  Nome playlist: parola1, parola2 || Altra playlist   (senza parole = tutti i video)"""
    regole = [x.strip() for x in str(P.get('playlist') or '').split('||') if x.strip()]
    scelte = []
    for r in regole:
        nome, _, parole = r.partition(':')
        lista = [w.strip().lower() for w in parole.split(',') if w.strip()]
        if nome.strip() and (not lista or any(w in titolo.lower() for w in lista)):
            scelte.append(nome.strip()[:150])
    if not scelte:
        return ''
    try:
        h = {'Authorization': 'Bearer ' + token()}
        esistenti = {it['snippet']['title'].strip().lower(): it['id'] for it in
                     http('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', headers=h).get('items', [])}
        for nome in scelte:
            pid = esistenti.get(nome.lower())
            if not pid:
                pid = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status',
                           {'snippet': {'title': nome}, 'status': {'privacyStatus': 'public'}}, h)['id']
                time.sleep(8)
            http('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet',
                 {'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': video_id}}}, h)
        return ''
    except Exception as e:
        return 'playlist non aggiornata: ' + str(e)[:150]


def avvisa(esito):
    for k, v in INFO_COMP.items():
        if v and k not in esito:
            esito[k] = v
    log('esito:', json.dumps(esito, ensure_ascii=False)[:500])
    if not P.get('callback_url'):
        return
    for k in range(3):
        try:
            http(P['callback_url'], {'id': P.get('id'), 'foglio': P.get('foglio', ''), **esito}); return
        except Exception as e:
            log('avviso a n8n non riuscito:', str(e)[:150]); time.sleep(10)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        if P.get('id'):
            avvisa({'stato': 'ERRORE', 'errore': str(e)[:400], 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1)})
        sys.exit(1)
