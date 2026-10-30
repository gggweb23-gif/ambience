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
import glob as _glob
import base64, hashlib, io, json, math, os, random, re, shutil, subprocess, sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 24
T_TR = 0.0                                   # nessuna transizione: taglio netto tra le immagini
ROOT = os.getcwd()
LAV = os.path.join(ROOT, 'lavoro_storia')
os.makedirs(LAV, exist_ok=True)
os.environ.setdefault('COSTI_FILE', os.path.join(LAV, 'costi_video.jsonl'))   # resta nel lavoro salvato: una ripresa somma i costi
import costi as CO
KIT = os.path.join(ROOT, 'kit_storia')
FONT = os.path.join(ROOT, 'font')
GEO = os.path.join(ROOT, 'geo')
E = os.environ.get
try:   # n8n (MULTICHANNEL - Storia Video) passa tutto in un unico JSON: vince sui campi del modulo
    P = json.loads(E('PAYLOAD') or '{}') or {}
except Exception:
    P = {}
sys.path.insert(0, os.path.join(os.getcwd(), 'coach'))
import ricetta as _RIC   # coach automatico: parametri della versione attiva della ricetta del canale (coach_auto = SI)
P = _RIC.applica(P)
TITOLO = E('TITOLO', 'Tutta la storia dell\'Iran').strip()
LINGUA = (str(P.get('language') or '').strip().lower()[:2] or E('LINGUA', 'it').strip() or 'it')   # language del canale (Channel Configs) vince
VOCE = str(P.get('voce') or E('VOCE', '') or 'glnsgBC77wt5zOYU0szz').strip()
MINUTI = float(E('MINUTI', '13') or 13)
# durata dal foglio (colonne durata_min_minuti / durata_max_minuti): l'originale piu' lungo si condensa, piu' corto si espande
MAX_MINUTI = float(str(P.get('durata_max_minuti') or P.get('max_minuti') or E('MAX_MINUTI', '25') or 25).replace(',', '.'))
MIN_MINUTI = float(str(P.get('durata_min_minuti') or P.get('min_minuti') or E('MIN_MINUTI', '0') or 0).replace(',', '.'))
PROVA = str(P.get('prova') or E('PROVA', 'NO')).strip().upper() == 'SI'
CARICA = str(P.get('carica') or E('CARICA', 'NO')).strip().upper() == 'SI' and not PROVA   # SI = carica su YouTube
MIN_SEC_YT = 480   # video piu' corti di 8 minuti (le prove) non vanno mai su YouTube
VOCE_VELOCITA = max(.8, min(1.2, float(str(P.get('voce_velocita') or E('VOCE_VELOCITA', '') or 1.06).replace(',', '.'))))   # uguale per tutte le scene
MUSICA_URL = str(P.get('musica_url') or E('MUSICA_URL', '')).strip()
# 30 ott: ElevenLabs solo per la VOCE. Musica e suoni NUOVI generati con ElevenLabs spenti (consumano crediti): si usano solo quelli gia' in libreria
# e la musica dei link nel foglio. Colonna elevenlabs_musica_suoni = SI per riaccendere la generazione.
ELEVEN_EXTRA = str(P.get('elevenlabs_musica_suoni') or E('ELEVENLABS_MUSICA_SUONI', '') or 'NO').strip().upper() == 'SI'
def _perc(v, d=100):
    try:
        return max(0, min(100, int(float(str(v).replace('%', '').replace(',', '.')) * (100 if 0 < float(str(v).replace('%', '').replace(',', '.')) <= 1 else 1))))
    except Exception:
        return d
COP_COPIA = _perc(P.get('copertina_copia') or E('COPERTINA_COPIA', ''), 100)
TESTO_COPIA = _perc(P.get('copia_copione') or E('COPIA_COPIONE', ''), 100)       # % del copione competitor da tenere uguale (il resto: pattern vincenti)
STILE_RACCONTO = str(P.get('stile_racconto') or E('STILE_RACCONTO', '')).strip()   # vuoto = storia del paese in ordine cronologico
STILE_IMMAGINI = str(P.get('stile_immagini') or E('STILE_IMMAGINI', '')).strip()   # vuoto = stile cartone di Storia in Minuti
MAPPA_SI = str(P.get('mappa') or E('MAPPA', '') or 'SI').strip().upper() != 'NO'    # % della copertina competitor da tenere uguale
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
_bud = str(P.get('budget_video') if P.get('budget_video') is not None else E('BUDGET_VIDEO', '')).replace(',', '.').replace('€', '').strip()
try:
    _bud_n = float(_bud) if _bud else 3.0
except ValueError:
    _bud_n = 3.0
if _bud.upper() in ('NO', '-1', 'LIBERO'):   # budget_video = NO: solo disegni (niente Pexels), il costo lo limita immagini_max
    _bud, _bud_n = '', 0.0
SOLO_PEXELS = bool(_bud) and _bud_n == 0   # budget 0 = nessun disegno Nano Banana nel video: solo clip e foto Pexels (+ mappa)
BUDGET = _bud_n   # euro massimi a video per i disegni
PREZZO_DISEGNO = 0.12   # $ per disegno Nano Banana 2 a 2K (con i rifatti si conta +25%)
SPESA = {'fal': 0.0, 'disegni': 0}
COP_VIDEO = str(P.get('copertina_video') or E('COPERTINA_VIDEO', '') or 'NO').strip().upper() == 'SI'
RISERVA_COP = 0.15 if COP_VIDEO else 0.55   # $ tenuti da parte nel budget per le copertine: 1a (fino a 3 tentativi) + la 2a se servira'
LINEA_TEMPO = str(P.get('linea_tempo') or E('LINEA_TEMPO', '') or 'NO').strip().lower()   # colonna linea_tempo: alto | basso | NO (vuota) = linea del tempo sempre visibile
LINEA_TEMPO = 'alto' if LINEA_TEMPO in ('si', 'alto', 'sopra') else 'basso' if LINEA_TEMPO in ('basso', 'sotto') else ''
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


def _soldi(v):
    """'1,10' / '1.10' / '1:10' (cella letta come ora) / 1.1 -> 1.1 ; vuoto o non valido -> None"""
    t = str(v if v is not None else '').strip().replace('€', '').replace('$', '')
    if not t:
        return None
    m = re.match(r'^(\d+)[:.,](\d+)', t)
    try:
        return float(f'{m.group(1)}.{m.group(2)}') if m else float(t)
    except ValueError:
        return None


# LUCCHETTO DI SPESA (30 ott 2026, Giorgio): mai disegni senza tetto. budget_video numero = euro massimi di immagini a video;
# budget_video NO / vuoto = vale max_spesa_immagini, e se manca anche quella 1 $. Il tetto vale per qualunque tipo di disegno.
TETTO_IMMAGINI = BUDGET if BUDGET > 0 else (_soldi(P.get('max_spesa_immagini')) or 1.0)
if _soldi(P.get('coach_budget_video')):   # il budget del coach (deciso da Giorgio) e' il tetto massimo: le immagini non lo superano mai
    TETTO_IMMAGINI = min(TETTO_IMMAGINI, max(0.0, _soldi(P.get('coach_budget_video')) - 0.3 - (0.15 if COP_VIDEO else 0.55)))
TAVOLE = str(P.get('tavole') or E('TAVOLE', '') or 'NO').strip().upper() == 'SI'   # regia: ogni immagine generata = tavola 2x2 con 4 inquadrature diverse (mai la stessa immagine due volte)
if TAVOLE and not (P.get('immagini_nuove') or E('IMMAGINI_NUOVE', '')):
    NUOVE_QUOTA = .3   # una tavola ogni ~4 inquadrature: le altre 3 sono gli altri pannelli
COMING_UP = float(str(P.get('coming_up_secondi') or E('COMING_UP_SECONDI', '') or 0).replace(',', '.'))   # scene: anteprima iniziale "COMING UP..." (0 = spenta)
ALTA_RIS = str(P.get('risoluzione') or E('RISOLUZIONE', '') or '').strip() == '1440'   # video finale a 2560x1440 (YouTube lo comprime meglio)
PEXELS_DA = float(str(P.get('pexels_da_secondi') or E('PEXELS_DA_SECONDI', '') or 60).replace(',', '.'))   # regia: prima di questo secondo solo cartoni
REGIA_PEXELS = _perc(P.get('regia_pexels') or E('REGIA_PEXELS', ''), 0)   # regia: % di inquadrature Pexels (clip e foto d'epoca) dopo PEXELS_DA
ATMOSFERA = str(P.get('atmosfera') or E('ATMOSFERA', '') or ('SI' if TAVOLE else 'NO')).strip().upper() == 'SI'   # pioggia, neve, polvere, braci, nebbia animate sopra l'immagine quando la scena le ha
VERIFICA = str(P.get('verifica_immagini') or E('VERIFICA_IMMAGINI', '') or 'SI').strip().upper() == 'SI'   # Claude controlla ogni immagine
GRANA = str(P.get('grana') or E('GRANA', '') or 'SI').strip().upper() == 'SI'   # grana da pellicola + vignetta leggera
PEXELS_MAX = int(float(str(P.get('pexels_max') or E('PEXELS_MAX', '') or 190)))   # ricerche Pexels per ORA (limite Pexels: 200 l'ora)
PEXELS_ATTESA_MAX = float(str(P.get('pexels_attesa_max') or E('PEXELS_ATTESA_MAX', '') or 80)) * 60   # minuti massimi di attesa per il limite orario
_orari_px = []
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
        if raw:
            return b
        j = json.loads(b.decode() or '{}')
        if isinstance(data, dict) and isinstance(j, dict) and j.get('usage'):   # costo del video (costi.py)
            if 'api.anthropic.com' in url:
                CO.registra('claude', data.get('model'), j['usage'])
            elif 'api.openai.com' in url:
                CO.registra('openai', data.get('model'), j['usage'])
        return j


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
    massimo = int(MAX_MINUTI * 150); minimo = 0 if PROVA else int(MIN_MINUTI * 150)
    condensa = parole > massimo
    espandi = parole < minimo
    parole = max(min(parole, massimo), minimo)
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
        fissi = 0.35 + RISERVA_COP + 0.05 + (sec / 5) * 0.005   # copione + copertine (1 + eventuale 2) + controlli disegni + controlli Pexels (Haiku)
        n_budget = max(2, int((dollari - fissi) / (PREZZO_DISEGNO * 1.25)))
        n_sf = max(2, min(SFONDI_MAX, n_budget, 3 + math.ceil(max(0.0, sec - 30) / 45)))
        globals()['QUOTA_CARTONI'] = max(5, min(60, round(n_sf * 8 / max(sec, 1) * 100)))
        globals()['RITMO'] = [4.0, 5.0, 6.0]
        log(f'budget {BUDGET:.2f} EUR: {n_sf} disegni (circa {n_sf * PREZZO_DISEGNO:.2f} $), cartone ~{QUOTA_CARTONI}% del video, il resto Pexels')
    if SOLO_PEXELS:   # budget 0: nessun disegno, tutto Pexels super coerente (+ mappa)
        n_sf = 0
        globals()['QUOTA_CARTONI'] = 0
        globals()['RITMO'] = [4.0, 5.0, 5.0]   # mai piu' di 5 secondi sulla stessa immagine
        log('budget 0 EUR: nessun disegno, solo clip e foto Pexels controllate (+ mappa)')
    w = [round(RITMO[0] * 2.5), round(RITMO[1] * 2.5), round(RITMO[2] * 2.5)]   # parole per visivo (circa 2,5 parole al secondo)
    if INTEGRATO and BUDGET <= 0 and not SOLO_PEXELS:   # ogni visivo ha la SUA immagine scritta sulla sua frase; i tagli da 3 s li fa il montaggio (zoom sulla stessa immagine)
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
- Il PARLATO deve COPIARE al {TESTO_COPIA}% il testo originale qui sotto: stessi fatti, stesso ordine, stessi ganci, stesse domande, stessi numeri, stessa lunghezza.{(' Il restante ' + str(100 - TESTO_COPIA) + '% riscrivilo seguendo i pattern vincenti dell originale (stesso tipo di ganci, domande allo spettatore, dettagli concreti e sorprendenti, stesso tono): mai parti a caso.') if TESTO_COPIA < 100 else ''}{' ECCEZIONE: l originale e troppo lungo, quindi CONDENSALO a circa ' + str(parole) + ' parole: stessi fatti principali, stesso ordine, stessi ganci e stesse domande, togli solo dettagli secondari ed esempi ripetuti.' if condensa else ''}{' ECCEZIONE: l originale e troppo corto, quindi ESPANDILO a circa ' + str(parole) + ' parole: stesso ordine e stessi ganci, aggiungi dettagli veri e concreti, esempi e curiosita coerenti con quelli dell originale (mai riempitivi).' if espandi else ''}
  Traducilo in {lingua} naturale e cambia solo piccole cose per non essere una copia identica (sinonimi, ordine delle parole, qualche frase unita o divisa). {'Aggiungi solo dettagli veri e coerenti' if espandi else 'NON aggiungere contenuti'}{' e togli solo il secondario' if condensa else ' e NON toglierne'}.
  UNITA' DI MISURA: il pubblico e' {'italiano' if LINGUA == 'it' else 'del canale'}: {'converti SEMPRE le unita americane in quelle europee con numeri arrotondati (gradi Fahrenheit -> gradi Celsius, es. 120 gradi F = circa 50 gradi; miglia -> chilometri; piedi -> metri; pollici -> centimetri; libbre -> chili; galloni -> litri; acri -> ettari). Mai lasciare 120 gradi se erano Fahrenheit.' if LINGUA == 'it' else 'keep the units of the original.'}
TESTO ORIGINALE:
{orig[:60000]}
'''
    prompt = f"""Sei lo sceneggiatore e il regista di un canale YouTube di storia a cartone, nello stile di "Genius History" e "Rome Unscrolled".
Scrivi il video: "{TITOLO}". Lingua della voce e delle scritte: {lingua}. Lunghezza totale del parlato: circa {parole} parole.
{blocco_originale}
STILE DEL RACCONTO: {STILE_RACCONTO or "dall'inizio della storia del paese fino a oggi, in ordine cronologico, con date precise, fatti veri, nomi veri."}
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
 "scene": [{{"capitolo": "SOLO nella prima scena di ogni capitolo: titolo breve del capitolo in {lingua} (2-5 parole, es. 'Le origini', 'L'impero di Ciro'); nelle altre scene ometti il campo", "testo": "parlato della scena", "anno": "l'anno (numero intero) del momento storico di cui parla la scena: negativo = avanti Cristo (es. -3000, -550, 1492, 1948, 2026); le scene su oggi = 2026", "visivi": [{{"tipo": "cartone", "frase": "prime parole della scena", "sfondo": "s1", "personaggio": "...", "reazione": true, "data": "...", "suono": "..."}}]}}],
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
            if not c.get('scene'):
                raise ValueError('copione senza scene')
            if not c.get('sfondi') and not SOLO_PEXELS:
                raise ValueError('copione senza sfondi a cartone')
            c['sfondi'] = c.get('sfondi') or []   # budget 0: nessun disegno, e' giusto che non ci siano sfondi
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
    pezzi, fine, pensiero, uso = [], '', [0], {}
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
            elif ev.get('type') == 'message_start':
                uso = dict((ev.get('message') or {}).get('usage') or {})
            elif ev.get('type') == 'message_delta':
                fine = (ev.get('delta') or {}).get('stop_reason') or fine
                uso.update({k: v for k, v in (ev.get('usage') or {}).items() if isinstance(v, int)})
            elif ev.get('type') == 'error':
                raise RuntimeError('Claude: ' + json.dumps(ev.get('error'))[:200])
    testo = ''.join(pezzi)
    CO.registra('claude', payload.get('model'), uso, nota='copione')
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
            mv = E('VOCE_MODELLO', 'eleven_multilingual_v2')
            CO.registra('elevenlabs', mv, crediti=len(testo) * (0.5 if ('flash' in mv or 'turbo' in mv) else 1))
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
VIETATE_SCENE = tuple(w.strip().lower() for w in re.split(r'[,;]', str(P.get('stock_exclude_words') or '')) if w.strip()) + (
    'cafe', 'coffee', 'shop', 'store', 'donut', 'donuts', 'restaurant', 'supermarket', 'people', 'woman', 'girl', 'tourist', 'tourists',
    'crowd', 'modern', 'apartment', 'shopping', 'bakery', 'pastry', 'neon', 'skyline', 'highway')   # scene: mai luoghi o persone di oggi


def pexels_cerca(tipo, q):
    k = (tipo, q.lower().strip())
    with _lock:
        if k in _cache:
            return _cache[k]
    # limite Pexels: PEXELS_MAX ricerche all'ora. Arrivati al limite si ASPETTA che l'ora si liberi (prima le ricerche finivano
    # e meta' video restava senza clip). Solo dopo PEXELS_ATTESA_MAX minuti di attesa totale si rinuncia (e si riusano clip).
    while True:
        with _lock:
            if k in _cache:
                return _cache[k]
            ora = time.time()
            _orari_px[:] = [t for t in _orari_px if ora - t < 3600]
            if len(_orari_px) < PEXELS_MAX:
                _orari_px.append(ora); _conti['n'] += 1
                break
            if _conti.get('attesa', 0) >= PEXELS_ATTESA_MAX:
                if not _conti.get('avvisato'):
                    _conti['avvisato'] = True
                    log(f'ATTENZIONE: ricerche Pexels FINITE ({_conti["n"]} fatte, attesa massima raggiunta): da qui si riusano clip gia\' scaricate')
                return []
            pausa = min(60.0, 3600 - (ora - _orari_px[0]) + 2)
            if not _conti.get('in_attesa'):
                _conti['in_attesa'] = True
                log(f'Pexels: raggiunto il limite di {PEXELS_MAX} ricerche l\'ora ({_conti["n"]} fatte): aspetto che si liberi (circa {int(3600 - (ora - _orari_px[0])) // 60 + 1} min)')
            _conti['attesa'] = _conti.get('attesa', 0) + pausa
        time.sleep(pausa)
    if _conti.pop('in_attesa', None):
        log(f'Pexels: ricerche di nuovo disponibili, riparto ({int(_conti.get("attesa", 0)) // 60} min di attesa finora)')
    chiave = E('PEXELS_API_KEY', '')
    ris = []
    if chiave:
        base = 'https://api.pexels.com/videos/search' if tipo == 'video' else 'https://api.pexels.com/v1/search'
        try:
            j = http(base + '?' + urllib.parse.urlencode({'query': q, 'per_page': 40, 'orientation': 'landscape'}), headers={'Authorization': chiave})
            if tipo == 'video':
                for v in j.get('videos', []):
                    fs = [f for f in v.get('video_files', []) if 'mp4' in (f.get('file_type') or '') and (f.get('height') or 0) <= 1080]
                    fs.sort(key=lambda f: -(f.get('height') or 0))
                    if fs and (v.get('duration') or 0) >= 3:
                        pics = [x.get('picture') for x in (v.get('video_pictures') or []) if x.get('picture')]
                        viste = [pics[int(i * (len(pics) - 1) / 3)] for i in range(4)] if len(pics) > 3 else [v.get('image') or ''] + pics
                        ris.append({'url': fs[0]['link'], 'anteprima': v.get('image') or '', 'viste': [x for x in viste if x],
                                    'desc': (v.get('url') or '').lower(), 'autore': str((v.get('user') or {}).get('id') or '')})
            else:
                for ph in j.get('photos', []):
                    ris.append({'url': ph['src'].get('large2x') or ph['src'].get('original'), 'anteprima': ph['src'].get('medium') or '',
                                'desc': ((ph.get('alt') or '') + ' ' + (ph.get('url') or '')).lower(), 'autore': str(ph.get('photographer_id') or '')})
        except Exception as e:
            log('Pexels:', q, str(e)[:120])
    vietate = VIETATE + (VIETATE_SCENE if TAVOLE else ())
    ris = [r for r in ris if r['url'] and not any(re.search(r'(^|[^a-z])' + re.escape(w) + r'([^a-z]|$)', r['desc']) for w in vietate)]
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
            im = Image.open(io.BytesIO(http(u, raw=True, timeout=30))).convert('RGB'); im.thumbnail((512, 512))
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
SCARTA SEMPRE (guarda bene anche i bordi e lo sfondo, persone minuscole comprese): qualsiasi persona (anche in costume medievale o storico), transenne, recinzioni, ponteggi, strutture o ponti di metallo, tralicci, cartelli, auto parcheggiate, palazzi moderni dietro le rovine, citta' moderne, palazzi moderni, lampioni, cavi elettrici, cartelli, folle; qualsiasi persona di oggi, anche piccola, lontana, di spalle o in mezzo a rovine (giacche, felpe, jeans, scarpe da ginnastica, zaini, turisti); auto, cellulari, cartelli o scritte leggibili, biglietti di auguri, oggetti di plastica, feste moderne, cose fuori tema.
VANNO BENE: paesaggi, montagne, deserti, rovine, monumenti antichi, musei, oggetti antichi, monete, manoscritti, fuoco, cieli, mare, armi antiche in museo. NESSUNA persona: le persone nel video sono solo disegnate.
Per il LUOGO basta che sia plausibile per quel paese (montagne, deserti, rovine, cieli vanno bene se il clima e' simile); scarta solo cio' che e' chiaramente di un altro mondo (es. colline verdi alpine per un deserto, palme tropicali, citta' europee).
Rispondi con UNA SOLA riga, esattamente cosi' e nient'altro: SCELTA: <numero della prima immagine adatta, oppure -1 se nessuna va bene>"""})
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': str(P.get('modello_pexels') or E('MODELLO_PEXELS', '') or MODELLO_CONTROLLO), 'max_tokens': 400, 'messages': [{'role': 'user', 'content': cont}]},
                 {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        txt = ''.join(b.get('text', '') for b in r.get('content', []))
        m = (re.search(r'SCELTA:\s*\**\s*(-?\d+)', txt) or re.search(r'(-?\d+)\s*$', txt.strip())
             or re.search(r"(?:scelgo|scelta|adatta[^.]{0,40}e')\s*(?:l')?\s*immagine\s*(\d+)", txt, re.I)
             or re.search(r'immagine\s*(\d+)[^.]{0,60}(?:adatta|rappresentativa|coerente|evocativa|plausibile)', txt, re.I))
        n = int(m.group(1)) if m else -1
        if not m:
            log('Pexels: risposta non chiara:', txt[-150:])
        log('Pexels', repr(q), '->', 'scartate tutte' if n < 0 else f'scelta {n}')
        return n if -1 <= n < len(candidati) else -1
    except Exception as e:   # senza controllo NON si usa nessuna immagine (meglio un cartone che una persona di oggi)
        log('controllo Pexels non riuscito, immagine NON usata:', str(e)[:200])
        return -1


LUOGHI = []   # parole dei luoghi del paese (es. iran, persia, tehran, isfahan, zagros...): i paesaggi Pexels devono essere DAVVERO di quel paese
PAESAGGIO = re.compile(r'(mountain|desert|river|valley|canyon|lake|coast|sea|beach|city|town|village|landscape|aerial|plateau|forest|hill|field|street|market|skyline|drone)', re.I)


def del_paese(c):
    """La clip di un paesaggio e' accettata solo se la sua descrizione su Pexels nomina il paese o un suo luogo (niente montagne di altri paesi)."""
    d = c.get('desc', '').replace('-', ' ')
    return any(re.search(r'(^|[^a-z])' + re.escape(k) + r'([^a-z]|$)', d) for k in LUOGHI)


_scelte = []   # clip/foto gia' usate: (autore, parole del titolo, impronta dell'immagine)
_impronte = {}


def impronta(u):
    """Impronta a colori 4x4 dell'anteprima: due riprese dello stesso posto (anche da un'altra angolazione) hanno gli stessi colori negli stessi punti."""
    if u in _impronte:
        return _impronte[u]
    try:
        im = Image.open(io.BytesIO(http(u, raw=True, timeout=30))).convert('RGB').resize((4, 4), Image.BOX)
        h = [x for px in im.getdata() for x in px]
    except Exception:
        h = None
    _impronte[u] = h
    return h


def parole_titolo(c):
    d = re.sub(r'https?://[^/]+/(video|photo)/', '', c.get('desc', '')).replace('-', ' ')
    return {w for w in re.findall(r'[a-z]{4,}', d) if w not in ('view', 'aerial', 'drone', 'footage', 'shot', 'video', 'photo', 'free', 'stock')}


def stessa_ripresa(c):
    """Vero se e' la stessa ripresa (o quasi) di una gia' usata: stesso autore con titolo simile, oppure immagine quasi uguale."""
    h = impronta(c.get('anteprima') or '') if c.get('anteprima') else None
    pt = parole_titolo(c)
    for autore, pu, hu in _scelte:
        if autore and autore == c.get('autore') and pt and pu and len(pt & pu) / max(1, min(len(pt), len(pu))) >= 0.5:
            return True
        if h and hu and sum(abs(x - y) for x, y in zip(h, hu)) / len(h) <= 14:   # stessi colori negli stessi punti = stessa ripresa
            return True
    return False


def pexels(tipo, q, contesto=''):
    for qq in (q, q + ' ancient'):   # niente ricerche generiche di riserva: se non c'e' un'immagine giusta si usa un cartone
        tutti = pexels_cerca(tipo, qq)   # ricerca FUORI dal lucchetto (prima qui si bloccava tutto)
        if LUOGHI and PAESAGGIO.search(qq):   # paesaggi: solo clip girate davvero nel paese
            prima_n = len(tutti); tutti = [c for c in tutti if del_paese(c)]
            if prima_n and not tutti:
                log('Pexels', repr(qq), '-> nessuna clip girata nel paese, scartate', prima_n)
        with _lock:
            liberi = [c for c in tutti if c['url'] not in _usati]
        cand, scartate = [], 0
        for c in liberi:   # niente seconda ripresa dello stesso posto (es. due voli di drone sul Nilo dello stesso autore)
            if len(cand) >= 4:
                break
            with _lock:
                doppia = stessa_ripresa(c)
            if doppia:
                scartate += 1
            else:
                cand.append(c)
        if scartate:
            log('Pexels', repr(qq), '-> scartate', scartate, 'riprese quasi uguali a una gia\' usata')
        if not cand:
            continue
        i = controlla(cand, qq, contesto)
        if i >= 0:
            with _lock:
                if cand[i]['url'] in _usati or stessa_ripresa(cand[i]):   # un'altra ricerca in parallelo l'ha appena presa
                    continue
                _usati.add(cand[i]['url'])
                _scelte.append((cand[i].get('autore') or '', parole_titolo(cand[i]), impronta(cand[i].get('anteprima') or '') if cand[i].get('anteprima') else None))
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
    if SOLO_PEXELS:
        r.append("- NIENTE DISEGNI: NESSUN visivo \"cartone\" e \"sfondi\" = []. Il video e' fatto SOLO di \"pexels_video\" (preferiti), \"pexels_foto\" e UNA \"mappa\" all'inizio.")
    if BUDGET > 0 or SOLO_PEXELS:
        if not SOLO_PEXELS:
            r.append(f"- DISEGNI CONTATI: esattamente {n_sf} visivi \"cartone\" in tutto il video, ognuno con la SUA immagine (s1..s{n_sf}, in ordine, mai ripetute). "
                     "Mettine 3 nei primi 30 secondi (il gancio); gli altri SOLO dove la voce parla di PERSONE (re, battaglie, popolo, mercati, eventi), distribuiti su tutto il video. "
                     "Un cartone dura 6-9 secondi di voce (15-22 parole).")
        r.append("- TUTTO IL RESTO e' Pexels: preferisci \"pexels_video\" (clip), \"pexels_foto\" solo se serve un oggetto preciso. Un visivo pexels ogni 10-14 parole. "
                 "Campo \"q\": 3-5 parole in INGLESE con il LUOGO del paese + la COSA CONCRETA che la voce dice in quel momento "
                 "(es. voce 'i monsoni portano la pioggia' -> 'monsoon rain India fields'; 'il fiume Gange' -> 'Ganges river Varanasi'; 'templi di pietra' -> 'ancient stone temple India'). "
                 "Mai persone, soldati, folle, feste, citta' moderne (tranne quando la voce parla di oggi). Visivi vicini = cose diverse (fiume, poi montagna, poi rovina, poi cielo).")
        r.append("- Aggiungi in cima al JSON il campo \"riserva_pexels\": 8 ricerche Pexels generiche ma tipiche del paese (paesaggi, fiumi, montagne, monumenti antichi, cielo), per quando una ricerca non trova niente. "
                 "Nelle ricerche di paesaggi metti SEMPRE il nome del paese o di una sua citta'/luogo famoso (es. 'Isfahan mosque dome', 'Iran desert dunes', 'Zagros mountains Iran').")
        r.append("- Aggiungi in cima al JSON il campo \"luoghi_paese\": 20-30 parole in inglese minuscolo con cui su Pexels si descrivono le riprese fatte in quel paese: nome del paese, nomi antichi, aggettivi (es. iran, iranian, persia, persian), "
                 "citta', regioni, monti, deserti, fiumi e monumenti famosi (es. tehran, isfahan, shiraz, yazd, kashan, persepolis, zagros, alborz, damavand, lut, qeshm).")
    elif QUOTA_CARTONI >= 100:
        r.append("- SOLO DISEGNI: usa solo \"cartone\"" + (" e una \"mappa\"" if MAPPA_SI else " (niente mappa)") + ". Niente pexels_video e pexels_foto.")
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


def _anno_txt(a):
    a = int(a)
    if a < 0:
        return f"{-a:,}".replace(',', '.') + (' a.C.' if LINGUA == 'it' else ' BC')
    return str(a)


def linea_del_tempo(video, scene, durs):
    """LINEA DEL TEMPO sempre visibile (in alto o in basso): le tappe del racconto in ordine, la parte gia' raccontata si colora
    e un segnale con l'anno corre da una tappa all'altra quando il racconto cambia epoca. Fa capire a chi guarda dove siamo nel tempo."""
    try:
        anni, prec = [], None
        for sc in scene:
            try:
                a = int(float(str(sc.get('anno')).replace('.', '').replace(',', '').strip()))
            except Exception:
                a = prec
            anni.append(a); prec = a
        if not any(a is not None for a in anni):
            log('linea del tempo saltata: il copione non ha gli anni'); return video
        primo = next(a for a in anni if a is not None)
        anni = [a if a is not None else primo for a in anni]
        # INTRODUZIONE: il racconto apre spesso col presente ("Oggi...") e poi torna all'inizio. Le scene prima della
        # data piu' antica sono l'introduzione: la barra mostra tutto l'arco senza cursore. Da li' il cursore va solo avanti.
        k0 = anni.index(min(anni))
        for i in range(k0 + 1, len(anni)):
            anni[i] = max(anni[i], anni[i - 1])
        inizi, t = [], 0.0
        for d in durs:
            inizi.append(t); t += d
        totale = durata(video)
        intro_fine = inizi[k0] if k0 else None
        tappe = sorted(set(anni[k0:]) | {max(anni)})
        if len(tappe) > 9:   # al massimo 9 tappe scritte: le altre restano solo come posizione
            passo = (len(tappe) - 1) / 8
            scritte = {tappe[round(i * passo)] for i in range(9)}
        else:
            scritte = set(tappe)
        x0, x1, hb = 110, W - 110, 132
        def pos(a):   # tappe equidistanti (5.000 anni di antichita' non schiacciano il Novecento), tra due tappe in proporzione
            if len(tappe) == 1:
                return (x0 + x1) / 2
            for i in range(len(tappe) - 1):
                if tappe[i] <= a <= tappe[i + 1]:
                    f = (a - tappe[i]) / max(1, tappe[i + 1] - tappe[i])
                    return x0 + (i + f) * (x1 - x0) / (len(tappe) - 1)
            return x0 if a < tappe[0] else x1
        def anno_a(tt):   # l'anno mostrato al tempo tt: corre verso quello della scena nuova in 1,2 s
            k = max(0, sum(1 for s_ in inizi if s_ <= tt) - 1)
            a_ora, a_prima = anni[k], anni[k - 1] if k > k0 else anni[k]
            f = min(1, (tt - inizi[k]) / 1.2); f = f * f * (3 - 2 * f)
            return a_prima + (a_ora - a_prima) * f
        cart = os.path.join(LAV, 'linea'); shutil.rmtree(cart, ignore_errors=True); os.makedirs(cart, exist_ok=True)
        fps_l = 8; n = int(totale * fps_l) + 1
        fnt = None
        for cand in (os.path.join(FONT, 'Oswald-SemiBold.ttf'), '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
            if os.path.exists(cand):
                fnt = cand; break
        F1, F2 = ImageFont.truetype(fnt, 24), ImageFont.truetype(fnt, 34)
        base = Image.new('RGBA', (W, hb), (0, 0, 0, 0)); db = ImageDraw.Draw(base)
        db.rounded_rectangle([40, 8, W - 40, hb - 8], radius=22, fill=(10, 14, 24, 165))
        yl = 80
        db.line([(x0, yl), (x1, yl)], fill=(255, 255, 255, 110), width=6)
        for a in tappe:
            x = pos(a); db.ellipse([x - 6, yl - 6, x + 6, yl + 6], fill=(255, 255, 255, 170))
            if a in scritte:
                db.text((x, yl + 26), _anno_txt(a), font=F1, fill=(255, 255, 255, 200), anchor='mm')
        ultimo = None
        for i in range(n):
            tt = i / fps_l
            p = os.path.join(cart, f'l_{i:06d}.png')
            if intro_fine is not None and tt < intro_fine:   # introduzione: solo l'arco intero, senza cursore
                chiave = 'intro'
            else:
                a = anno_a(tt); x = pos(a); chiave = (round(x), round(a))
            if chiave == ultimo and i:
                os.link(os.path.join(cart, f'l_{i - 1:06d}.png'), p); continue
            ultimo = chiave
            if chiave == 'intro':
                base.save(p); continue
            im = base.copy(); d = ImageDraw.Draw(im)
            d.line([(x0, yl), (x, yl)], fill=(255, 200, 40, 255), width=8)   # la parte gia' raccontata
            d.ellipse([x - 15, yl - 15, x + 15, yl + 15], fill=(255, 200, 40, 255), outline=(255, 255, 255, 255), width=4)
            tx = _anno_txt(round(a))
            w_ = d.textlength(tx, font=F2) + 34; xc = min(max(x, 40 + w_ / 2), W - 40 - w_ / 2)
            d.rounded_rectangle([xc - w_ / 2, yl - 58, xc + w_ / 2, yl - 18], radius=12, fill=(255, 200, 40, 255))
            d.text((xc, yl - 38), tx, font=F2, fill=(15, 15, 20, 255), anchor='mm')
            im.save(p)
        y = 18 if LINEA_TEMPO == 'alto' else H - hb - 14
        out = video[:-4] + '_tempo.mp4'
        run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-framerate', str(fps_l), '-i', os.path.join(cart, 'l_%06d.png'),
             '-filter_complex', f'[1:v]fps={FPS}[l];[0:v][l]overlay=0:{y}:shortest=1[v]', '-map', '[v]', '-map', '0:a?',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', out])
        log(f'linea del tempo ({LINEA_TEMPO}): {len(tappe)} tappe, da {_anno_txt(tappe[0])} a {_anno_txt(tappe[-1])}')
        return out
    except Exception as e:
        log('linea del tempo saltata:', str(e)[:200]); return video


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
if STILE_IMMAGINI:   # stile del canale (es. Faces of Rome: personaggi in primo piano a fuoco)
    STILE_SCENA = STILE_IMMAGINI
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


_CTX = threading.local()   # _CTX.scena = True mentre si disegnano le scene (tetto di spesa)


def fal(modello, dati):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    with _lock:
        costo = (PREZZO_DISEGNO if str(dati.get('resolution')) == '2K' else 0.08) if 'nano-banana' in modello else 0.04
        tetto = TETTO_IMMAGINI
        if getattr(_CTX, 'scena', False):
            SPESA['scene'] = SPESA.get('scene', 0) + costo
        if getattr(_CTX, 'scena', False) and SPESA['scene'] > tetto + 1e-9:   # il tetto vale per le immagini delle scene
            SPESA['scene'] -= costo
            raise RuntimeError(f'tetto di spesa immagini {tetto:.2f} $ raggiunto')
        if SPESA['fal'] + costo > tetto + RISERVA_COP + 1e-9:   # LUCCHETTO DI SPESA: il totale immagini del video (scene + copertine) non si supera MAI
            if getattr(_CTX, 'scena', False):
                SPESA['scene'] -= costo
            raise RuntimeError(f'tetto di spesa totale immagini {tetto + RISERVA_COP:.2f} $ raggiunto')
        SPESA['fal'] += costo
        SPESA['disegni'] += 1
        CO.registra('fal', modello, dollari=costo)
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


def copertina_primo_piano(comp, c):
    """Copertina "primo piano a fuoco" (angolo A dello Studio Angoli, es. Faces of Rome): stessa storia e stessa scritta della copertina
    del competitor, ma UN personaggio enorme e nitido con reazione esagerata, sfondo semplice e sfocato; scritta gialla su UNA riga in alto."""
    if not comp.get('copertina') or not E('FAL_KEY') or not E('ANTHROPIC_API_KEY'):
        return None
    try:
        b = http(comp['copertina'], raw=True); im0 = Image.open(io.BytesIO(b)).convert('RGB').resize((1280, 720)); buf = io.BytesIO(); im0.save(buf, 'JPEG', quality=88)
        dom = ('This is the thumbnail of a successful YouTube video titled "' + str(comp.get('titolo') or '') + '". Our channel uses the same topics and the same drawing style '
               'but always a FOCUSED CLOSE-UP framing. Answer ONLY JSON: {"testo": "the words written on the thumbnail, translated to ' + LINGUA_NOME + ', CAPS, max 3 short words, same meaning", '
               '"scena": "in English, the SAME story as ONE single character VERY BIG in the foreground (from the waist up, about 60% of the image) with the exact exaggerated emotion, '
               'holding or near the key object, and the place behind him SIMPLE and softly BLURRED with only 2-3 recognizable elements; 2 sentences"}')
        r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_AI, 'max_tokens': 800, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}, {'type': 'text', 'text': dom}]}]},
            {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'}, timeout=300)
        t = ''.join(x.get('text', '') for x in r.get('content', [])); j = json.loads(t[t.find('{'): t.rfind('}') + 1])
        prompt = ('The reference image shows ONLY the drawing style to copy (lines, colours, faces): do NOT copy its composition. YouTube thumbnail, FOCUSED CLOSE-UP: '
                  + str(j.get('scena') or '') + ' ' + STILE_SCENA + ' The TOP 25% of the image stays simple (a big title will go there), no face there.'
                  + ' Everything historically accurate for the era: no modern symbols or signs (no $ or currency signs on bags or coins), no modern objects, no text.')
        p = os.path.join(ROOT, 'copertina.jpg')
        _immagine_fal(prompt, [comp['copertina']], p)
        im = Image.open(p).convert('RGB').resize((1280, 720), Image.LANCZOS)
        fp = os.path.join(LAV, 'cinzel.ttf')
        if not os.path.exists(fp):
            open(fp, 'wb').write(http('https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf', raw=True))
        def F(k):
            f = ImageFont.truetype(fp, k)
            try:
                f.set_variation_by_name('Black')
            except Exception:
                pass
            return f
        testo = str(j.get('testo') or c.get('titolo') or '').upper().strip()
        d = ImageDraw.Draw(im); k = 150; f = F(k)
        while d.textlength(testo, font=f) > 1180 and k > 60:   # sempre UNA riga: non copre mai le teste
            k -= 4; f = F(k)
        d.text((640, 18), testo, font=f, fill=(255, 220, 0), stroke_width=max(7, int(k * .1)), stroke_fill=(10, 10, 10), anchor='ma')
        im.save(p, quality=93)
        log('copertina primo piano pronta:', testo)
        return p
    except Exception as e:
        log('copertina primo piano non riuscita:', str(e)[:200])
        return None


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
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', '-r', FPS]


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
    for sz in range(104, 28, -6):
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
    lib = os.path.join(ROOT, 'libreria_suoni'); os.makedirs(lib, exist_ok=True)   # libreria comune: ogni suono generato resta e non si paga piu'
    p = os.path.join(lib, 'fx_' + hashlib.md5(f'{desc}|{dur:.1f}'.encode()).hexdigest()[:10] + '.mp3')
    if os.path.exists(p) and os.path.getsize(p) > 500:
        return p
    if not ELEVEN_EXTRA:
        raise RuntimeError('suono non in libreria (generazione ElevenLabs spenta)')
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
    ('short cinematic impact hit, deep', 0.8), ('soft low whoosh, warm and muffled', 0.8), ('reverse whoosh riser, short', 0.8),
    ('soft cloth flutter, flag in the wind, short', 0.6), ('soft muffled thump, low and warm', 0.5), ('drum hit with short reverb, epic', 0.7)]


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
    scatto = colpo = None
    if any(v.get('scritta') for v in piano):
        try:
            colpo = _stesso_volume(_carica_suono(effetto('short punchy cinematic impact hit, deep boom', 1.0, 0), sr)[:int(sr * .8)], .18)
        except Exception as e:
            log('suono delle scritte non generato:', str(e)[:100])
    if any(v.get('tipo') == 'pexels_foto' for v in piano):
        try:
            scatto = _stesso_volume(_carica_suono(effetto('single camera shutter click, vintage camera, crisp', 1.0, 0), sr)[:int(sr * .6)], .2)
        except Exception as e:
            log('suono di scatto non generato:', str(e)[:100])
    for k, v in enumerate(piano):
        if v.get('scritta') and colpo is not None:   # scritta che entra a scatto: colpo secco
            j = max(0, int((t + .08) * sr)); s_ = colpo[:max(0, len(a) - j)]; a[j:j + len(s_)] += s_.astype(np.float32) * .8
        if k and v.get('tipo') == 'pexels_foto' and scatto is not None:   # foto: scatto della macchina fotografica
            j = max(0, int((t - .03) * sr)); s_ = scatto[:max(0, len(a) - j)]; a[j:j + len(s_)] += s_.astype(np.float32); n += 1
        elif k and SUONI_CAMBIO and (not TAVOLE or v.get('prompt') or v.get('tipo') != 'cartone'):
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


def pezzo_video(path, d, src, inizio=0.0, specchio=False):
    """Clip piu' corta del suo spazio: si rallenta un po' (fino al 70%) e, se non basta, va avanti e poi all'indietro.
    MAI un fotogramma fermo e MAI ripartire da capo (si vedeva lo 'scatto')."""
    try:
        ds = durata(src)
    except Exception:
        ds = 0
    inizio = max(0.0, min(inizio, ds - 1.0)) if ds > 1.0 else 0.0
    resto = ds - inizio if ds else 0
    filtro = ''
    if 0 < resto < d:
        if resto / .7 < d:   # anche rallentata non basta: avanti + indietro (niente fermo immagine)
            filtro = 'split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,'
            resto *= 2
        if resto < d:
            filtro += f'setpts=PTS/{max(.5, resto / d):.3f},'
    filtro += 'hflip,' if specchio else ''
    run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{inizio:.2f}', '-t', f'{min(ds - inizio, d + 1) if ds else d:.2f}', '-i', src, '-t', d, '-an',
         '-vf', f'{filtro}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1', *ENC, path])
    return path


def pezzo_foto(path, d, src, flash=False):
    n = max(1, int(d * FPS))
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', FPS, '-t', d, '-i', src,
         '-vf', f"scale={W * 4}:{H * 4}:force_original_aspect_ratio=increase:flags=lanczos,crop={W * 4}:{H * 4},"
                f"zoompan=z='1+0.07*on/{n}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1"
                + (',fade=t=in:st=0:d=0.22:color=white' if flash else ''),
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
                    if 1.6 <= tempo(parole[k][0]) - t_ini <= lim + (0 if TAVOLE else 1.3) and D - tempo(parole[k][0]) >= 1.4]
            if not cand and TAVOLE and D - t_ini > lim:   # tetto rigido: si taglia comunque tra due parole
                cand = [k for k in range(primi[-1] + 1, len(parole)) if 1.0 <= tempo(parole[k][0]) - t_ini <= lim and D - tempo(parole[k][0]) >= 1.0]
                if not cand:   # ultima risorsa: la parola piu' vicina al ritmo (mai un'inquadratura lunghissima)
                    cand = sorted([k for k in range(primi[-1] + 1, len(parole)) if .6 <= tempo(parole[k][0]) - t_ini and D - tempo(parole[k][0]) >= .6],
                                  key=lambda k: abs(tempo(parole[k][0]) - t_ini - lim))[:1]
            if not cand:
                break
            k = max(cand, key=lambda k: punti(k) - abs(tempo(parole[k][0]) - t_ini - lim) * .7)
            tagli.append(tempo(parole[k][0])); primi.append(k)
        for j, t0 in enumerate(tagli):
            t1 = tagli[j + 1] if j + 1 < len(tagli) else D
            ws = parole[primi[j]: primi[j + 1] if j + 1 < len(primi) else len(parole)]
            out.append({'scena': i, 'd': t1 - t0, 't': glob + t0, 'testo': ' '.join(w for _, w in ws), 'capitolo': (s.get('capitolo') or '') if j == 0 else ''})
        glob += D
    return out


REGOLE_DETTAGLI = """2. "nuova": true = immagine nuova; false = DETTAGLIO dell'ultima immagine nuova (la stessa scena vista piu' da vicino), SOLO se le parole parlano ancora della stessa cosa e quel dettaglio e' gia' nell'immagine. Mai piu' di 2 dettagli di fila. Circa {q}% di immagini nuove.
3. "prompt_en" (solo per le nuove): in inglese, 30-60 parole: chi c'e' e cosa fa, luogo, epoca, tempo atmosferico e luce, emozione, e l'INQUADRATURA (varia sempre: epic wide establishing shot, aerial view, medium shot, dramatic close-up, low angle, over-the-shoulder, silhouette against the sky...). Se le righe dopo saranno dettagli, descrivi anche quegli elementi e dove sono (left / right / center)."""
REGOLE_PEXELS = """13. IMMAGINI VERE (solo righe segnate [PEXELS SI]): circa il {q}% di quelle righe diventa "tipo": "pexels_video" (preferito) o "pexels_foto" invece del cartone: rovine, monumenti, statue, mosaici, monete, oggetti antichi nei musei, strade romane, acquedotti, fuoco, cielo, mare, campagna. Mai due di fila e mai a meta' di una tavola (dopo un pexels la riga seguente e' "nuova": true). Per OGNI riga segnata [PEXELS SI], anche se resta cartone, scrivi "q": ricerca Pexels in inglese di 3-5 parole MOLTO precisa: il luogo o l'oggetto antico esatto + cosa si vede (es. "Colosseum arches ruins Rome", "Roman Forum columns sunset", "ancient Roman coins museum", "Roman marble bust museum", "Appian Way ancient stones", "Roman mosaic floor detail", "ancient oil lamp flame"), e "alt_q": 2 alternative altrettanto precise. Mai persone, soldati in costume, citta' moderne, turisti: solo cose d'epoca. Preferisci inquadrature STRETTE e di dettaglio (un arco, pietre, colonne, un mosaico, una statua, monete, una lucerna) ai panorami larghi delle rovine, dove compaiono turisti, transenne e palazzi moderni."""
REGOLE_TAVOLE = """2. MONTAGGIO DA FILM: "nuova": true = un MOMENTO nuovo, che viene disegnato come TAVOLA di 4 inquadrature diverse dello stesso momento (stessi personaggi, vestiti e luogo). Le righe dopo con "nuova": false mostrano, in ordine, gli altri pannelli della stessa tavola: massimo 3 di fila, e solo se le parole parlano ancora di quel momento. Lo spettatore non vede MAI la stessa immagine due volte. Circa una riga nuova ogni 3-4.
3. "prompt_en" (solo per le nuove): in inglese, 30-50 parole: il momento (chi c'e', cosa fa, luogo, epoca, tempo atmosferico e luce, emozione). "pannelli" (solo per le nuove): 4 descrizioni in inglese di 10-25 parole, una per pannello, ognuna coerente con le parole della riga in cui si vedra' (pannello 1 = questa riga, 2/3/4 = le righe "nuova": false che seguono). Ordine da film, SEMPRE: 1 campo LARGO che mostra tutto l'ambiente; 2 primo piano del volto del protagonista con un'emozione forte; 3 dettaglio di mani o dell'oggetto chiave (MAI un volto); 4 campo MEDIO di un altro personaggio o della scena da un'angolazione opposta (dall'alto, dal basso, di spalle), MAI un primo piano. Quattro soggetti chiaramente diversi.
   Ogni pannello mostra un'AZIONE in corso (un gesto, un movimento, qualcosa che succede), mai pose ferme: lo spettatore deve voler vedere cosa succede dopo.
   Due tavole di fila MAI con lo stesso soggetto o oggetto (se una tavola ha il dettaglio della porta, la successiva mostra altro); i personaggi ricorrenti hanno sempre gli stessi vestiti."""
REGOLE_EXTRA = """11. "atmosfera" (solo per le nuove, di solito ""): pioggia, neve, polvere, braci o nebbia SOLO se la scena li ha davvero (temporale, inverno, strada o battaglia polverosa, fuoco o citta' in fiamme, alba nebbiosa o fumo). Vale per tutta la tavola.
12. "suono" (facoltativo, circa uno ogni 15-20 secondi, nei momenti forti): un effetto sonoro in inglese, 3-8 parole, che corrisponde a cio' che si vede (es. "swords clashing in battle", "horses galloping on stone", "roaring crowd in the arena", "heavy rain and thunder"). Mai musica, mai voci che parlano."""


def piano_regia(c, shots, kit):
    """Claude fa il regista: per OGNI inquadratura decide l'immagine sulle parole esatte della voce."""
    chiave = E('ANTHROPIC_API_KEY', '')
    lotto, ris, memoria = 60, {}, ''
    for b0 in range(0, len(shots), lotto):
        parte = shots[b0:b0 + lotto]
        elenco = '\n'.join(f'{b0 + k}: {s["testo"]}' + (f'   [INIZIA IL CAPITOLO: {s["capitolo"]}]' if s.get('capitolo') else '')
                           + ('   [PEXELS SI]' if REGIA_PEXELS and s.get('t', 0) >= PEXELS_DA else '') for k, s in enumerate(parte))
        prompt = f"""Sei il regista di un video di storia a cartone di altissimo livello: "{c.get('titolo') or TITOLO}" (paese: {PAESE.get('nome') or ''}).
Ogni riga qui sotto e' un'inquadratura di circa {RITMO[0]:.0f} secondi con le PAROLE che la voce dice in quel momento. Per OGNI riga decidi cosa si vede.
{('Ultime immagini decise (per continuita di epoca, luoghi e personaggi): ' + memoria) if memoria else ''}

REGOLE:
1. COERENZA ASSOLUTA: l'immagine mostra ESATTAMENTE quello che dicono quelle parole. Se dice sole: sole e luce calda; se dice pioggia o inverno: pioggia o neve; se dice deserto: deserto; se nomina una persona: quella persona; se parla di numeri o idee astratte: una scena concreta che li rappresenta. MAI qualcosa che contraddice le parole.
{REGOLE_TAVOLE if TAVOLE else REGOLE_DETTAGLI.format(q=round(NUOVE_QUOTA * 100))}
4. "personaggi": 0-2 id del kit SOLO se sono proprio loro (la persona con nome che la voce nomina, o una figura generica coerente con epoca e popolo). Kit: {lista_kit(kit)}. Le altre persone descrivile nel prompt (popolo, epoca, vestiti corretti).
5. "zoom" (solo per i dettagli): uno tra sinistra, destra, centro, alto, basso, volto.
6. "camera": push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down. Variala, mai uguale due volte di fila; nei momenti forti push_in.
7. "didascalia" (facoltativa, circa 1 riga ogni 6, mai due di fila): 2-6 parole chiave DETTE in quella riga (nomi, date, luoghi).
8. "mappa": true UNA sola volta in tutto il video, quando la voce presenta il territorio o i confini del paese (senza prompt).
9. EMOZIONE E SORPRESA: alterna campi lunghissimi epici e primi piani emotivi, giorno e notte, folle e solitudine, interni ed esterni; mai lo stesso soggetto due volte di fila; ogni immagine deve far venire voglia di vedere la successiva.
10. Mai scritte, lettere o numeri dentro le immagini; niente di moderno se l'epoca e' antica.
{REGOLE_EXTRA if (TAVOLE or EFFETTI or ATMOSFERA) else ''}
{REGOLE_PEXELS.format(q=REGIA_PEXELS) if REGIA_PEXELS else ''}

INQUADRATURE:
{elenco}

Rispondi SOLO con un array JSON, un oggetto per riga, con lo stesso numero "n":
[{{"n": {b0}, "nuova": true, "prompt_en": "...",{' "pannelli": ["...", "...", "...", "..."], "atmosfera": "",' if TAVOLE else ''} "personaggi": [], "camera": "push_in", "didascalia": "", "suono": ""}}, {{"n": {b0 + 1}, "nuova": false,{'' if TAVOLE else ' "zoom": "volto",'} "camera": "pan_left", "suono": ""}}]"""
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
        q_px = str(r.get('q') or '').strip()
        if q_px:
            s = dict(s, q=q_px, alt_q=[str(x).strip() for x in (r.get('alt_q') or []) if str(x).strip()][:2])
        if REGIA_PEXELS and s.get('t', 0) >= PEXELS_DA and r.get('tipo') in ('pexels_video', 'pexels_foto') and q_px \
                and out and out[-1].get('tipo') == 'cartone':   # immagine vera d'epoca (mai due di fila, mai nel primo minuto)
            out.append(dict(s, tipo=r['tipo'], contesto=s['testo'], camera='', didascalia=str(r.get('didascalia') or '').strip()[:60],
                            suono=str(r.get('suono') or '').strip()[:80]))
            dettagli = 3 if TAVOLE else dettagli   # dopo un'immagine vera riparte una tavola nuova
            continue
        max_det = 3 if TAVOLE else 2
        nuova = bool(r.get('nuova', True)) or not out or dettagli >= max_det or not any(x.get('img') is not None for x in out)
        if nuova and not str(r.get('prompt_en') or '').strip():
            if out and dettagli < max_det and any(x.get('img') is not None for x in out):
                nuova = False
            else:
                r['prompt_en'] = 'Historical scene illustrating: ' + s['testo']
        cam = r.get('camera') if r.get('camera') in CAMERE else random.choice(CAMERE)
        if cam == ultima_cam:
            cam = random.choice([x for x in CAMERE if x != cam])
        ultima_cam = cam
        v = dict(s, tipo='cartone', camera=cam, didascalia=str(r.get('didascalia') or '').strip()[:60], suono=str(r.get('suono') or '').strip()[:80])
        if nuova:
            v.update(img=n, prompt=str(r['prompt_en']).strip(), personaggi=[x for x in (r.get('personaggi') or []) if x in kit and x != NARRATORE][:2], zoom='',
                     pannelli=[str(x).strip() for x in (r.get('pannelli') or []) if str(x).strip()][:4],
                     atmo=str(r.get('atmosfera') or '').strip().lower() if str(r.get('atmosfera') or '').strip().lower() in ATMO_TIPI else '')
            dettagli = 0
        else:
            v.update(img=next(x['img'] for x in reversed(out) if x.get('img') is not None), zoom=r.get('zoom') if r.get('zoom') in ZOOM_BOX else 'centro')
            dettagli += 1
        out.append(v)
    nuove = [v for v in out if v.get('prompt')]
    if TAVOLE and REGIA_PEXELS and len(nuove) > IMMAGINI_MAX:   # tetto di costo: intere tavole (dopo il primo minuto) diventano clip e foto d'epoca
        gruppi = []
        for i, v in enumerate(out):
            if v.get('prompt'):
                gruppi.append([i])
            elif gruppi and v.get('tipo') == 'cartone' and v.get('img') == out[gruppi[-1][0]]['img']:
                gruppi[-1].append(i)
        adatti = [g for g in gruppi if out[g[0]].get('t', 0) >= PEXELS_DA and not out[g[0]].get('capitolo') and all(out[i].get('q') for i in g)]
        togli = min(len(nuove) - IMMAGINI_MAX, len(adatti))
        for g in [adatti[int(j * len(adatti) / max(1, togli))] for j in range(togli)]:   # distribuite su tutto il video
            for n_, i in enumerate(g):
                out[i].update(tipo='pexels_video' if n_ % 2 == 0 else 'pexels_foto', contesto=out[i]['testo'], camera='')
                for k_ in ('prompt', 'img', 'pannelli', 'zoom', 'personaggi'):
                    out[i].pop(k_, None)
        log(f'tetto di {IMMAGINI_MAX} tavole: {togli} tavole diventano immagini Pexels')
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
    if TAVOLE:   # ogni inquadratura della stessa tavola prende il pannello dopo: 1 campo largo, 2 volto, 3 dettaglio, 4 reazione
        uso, atmo = {}, {v['img']: v.get('atmo', '') for v in out if v.get('prompt')}
        for v in out:
            if v.get('tipo') != 'cartone' or v.get('img') is None:
                continue
            i = uso.get(v['img'], 0); uso[v['img']] = i + 1
            v.update(pannello=i % 4, zoom='' if i < 4 else 'centro', atmo=atmo.get(v['img'], ''))   # oltre 4 (solo col tetto di costo): dettaglio del pannello
    log(f"regia: {len(out)} inquadrature, {sum(1 for v in out if v.get('prompt'))} immagini nuove, "
        f"{sum(1 for v in out if v.get('tipo') == 'cartone' and not v.get('prompt'))} dettagli, "
        f"{sum(1 for v in out if v.get('tipo') in ('pexels_video', 'pexels_foto'))} Pexels, mappa: {'si' if mappa_fatta else 'no'}")
    return out


def _immagine_fal(prompt, refs, p, size=(2560, 1440)):
    if IMMAGINI_MODELLO.startswith('nano'):
        dati = {'aspect_ratio': '16:9', 'resolution': '4K' if size[0] > 2560 else '2K', 'output_format': 'jpeg', 'num_images': 1}
        r = fal('fal-ai/nano-banana-2/edit', dict(dati, prompt=prompt, image_urls=refs)) if refs else fal('fal-ai/nano-banana-2', dict(dati, prompt=prompt))
    else:
        dati = {'image_size': {'width': size[0], 'height': size[1]}, 'num_images': 1}
        r = fal('fal-ai/bytedance/seedream/v4.5/edit', dict(dati, prompt=prompt, image_urls=refs)) if refs else \
            fal('fal-ai/bytedance/seedream/v4.5/text-to-image', dict(dati, prompt=prompt))
    scarica(r['images'][0]['url'], p)
    im = Image.open(p).convert('RGB')
    ImageOps.fit(im, size, Image.LANCZOS).save(p, quality=92)


# ============================================================ TAVOLE 2x2: 4 inquadrature diverse al prezzo di un'immagine
TAVOLA_PROMPT = ('A 2x2 STORYBOARD SHEET: the image is divided into FOUR EQUAL panels (top-left, top-right, bottom-left, bottom-right) separated by thin straight '
                 'white lines that cross exactly in the centre; each panel is a complete 16:9 frame of the SAME moment with the SAME characters, clothes, light and place, '
                 'but a clearly DIFFERENT shot and subject; every panel shows an ACTION happening, never a static pose. '
                 'Places are shown exactly as they were IN THAT ERA, never as they look today (no later monuments, no modern palazzi, no church crosses, no iron railings). '
                 'Everything is historically accurate for the era of the story: no modern buildings, no factory chimneys or smokestacks, no glass windows, '
                 'no electric lights, no modern clothes or objects. ')
TAVOLA_STD = ['wide establishing shot of the whole scene', 'close-up of the main character face with a strong emotion',
              'detail close-up of the hands or the key object (no face)', 'medium shot of another character reacting, or the scene from the opposite angle (not a close-up)']
TAVOLA_RIF = {}   # 'url': la prima tavola del video, riferimento di stile e personaggi per tutte le altre


def _bordo(a):   # righe (n, L, 3): e' una linea di separazione (quasi tutta bianca) o un contorno (quasi tutto nero)?
    mn, mx = a.min(axis=2), a.max(axis=2)
    bi = (mn > 205).mean(axis=1); ne = (mx < 70).mean(axis=1)
    return (bi > .8) | (ne > .8), bi > .8


def _linea(prof, lo, hi):   # la fascia bianca piu' vicina al centro tra lo e hi
    best, i, mid = None, lo, (lo + hi) / 2
    while i < hi:
        if prof[i]:
            j = i
            while j < hi and prof[j]:
                j += 1
            if best is None or abs((i + j) / 2 - mid) < abs(sum(best) / 2 - mid):
                best = (i, j)
            i = j
        else:
            i += 1
    return best


def _rifila(q):   # toglie dai 4 lati le righe/colonne di linea bianca o di contorno nero rimaste attaccate al pannello
    a = np.asarray(q, dtype=np.int16); h, w = a.shape[:2]
    rig, _ = _bordo(a); col, _ = _bordo(a.transpose(1, 0, 2))

    def conta(seq, lim):
        n = 0
        while n < lim and seq[n]:
            n += 1
        return n
    t, b = conta(rig, int(h * .06)), conta(rig[::-1], int(h * .06))
    l, r = conta(col, int(w * .06)), conta(col[::-1], int(w * .06))
    e = max(3, int(w * .006))   # margine per l'antialias della linea
    return q.crop((l + e, t + e, w - r - e, h - b - e))


def taglia_tavola(im, size=(2560, 1440)):
    """Tavola 2x2 -> 4 pannelli 16:9 senza linee bianche: trova da sola le linee divisorie (anche se i pannelli non sono uguali).
    ok=False se una linea non si trova o un pannello e' troppo lontano dal 16:9 (tavola da rifare)."""
    im = im.convert('RGB'); W_, H_ = im.size; k = 2; trovate = []
    a = np.asarray(im.resize((W_ // k, H_ // k)), dtype=np.int16); h2, w2 = a.shape[:2]

    def oriz(c0, c1):
        z = _linea(_bordo(a[:, c0:c1])[1], int(h2 * .3), int(h2 * .7)); trovate.append(bool(z))
        return (z[0] * k, z[1] * k) if z else (H_ // 2, H_ // 2)

    def vert(r0, r1):
        z = _linea(_bordo(a[r0:r1].transpose(1, 0, 2))[1], int(w2 * .3), int(w2 * .7)); trovate.append(bool(z))
        return (z[0] * k, z[1] * k) if z else (W_ // 2, W_ // 2)
    ys = oriz(int(w2 * .05), int(w2 * .3)), oriz(int(w2 * .7), int(w2 * .95))   # linea orizzontale a sinistra e a destra
    vt = vert(int(h2 * .05), int(min(ys[0][0], ys[1][0]) / k * .9))
    vb = vert(int(max(ys[0][1], ys[1][1]) / k + (h2 - max(ys[0][1], ys[1][1]) / k) * .1), int(h2 * .95))
    boxes = [(0, 0, vt[0], ys[0][0]), (vt[1], 0, W_, ys[1][0]), (0, ys[0][1], vb[0], H_), (vb[1], ys[1][1], W_, H_)]
    pannelli = [_rifila(im.crop(bx)) for bx in boxes]
    ok = all(trovate) and all(1.35 < q.size[0] / max(1, q.size[1]) < 2.3 for q in pannelli)
    return [ImageOps.fit(q, size, Image.LANCZOS) for q in pannelli], ok


def verifica_immagine(p, testi, prompt, nota=''):
    """Claude guarda l'immagine e la confronta con le parole della voce. None = ok, altrimenti cosa correggere."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave:
        return None
    im = Image.open(p).convert('RGB'); im.thumbnail((1568, 1568) if nota else (768, 768)); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85)
    domanda = nota + f"""Video di storia sul paese: {PAESE.get('nome') or '-'}. Questa immagine accompagna queste parole della voce: "{testi[:500]}".
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
    if TAVOLE:
        return genera_tavola(v, testi, refs, p)
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


TAVOLE_KO = set()   # tavole non tagliabili: si usa l'immagine intera con inquadrature diverse (zoom)


def genera_tavola(v, testi, refs, p):
    """Una tavola 2x2 a 4K -> 4 pannelli diversi. Lista di 4 percorsi (pannello 1..4)."""
    out = [p[:-4] + f'_p{i}.jpg' for i in range(4)]
    if all(os.path.exists(x) for x in out):
        return out
    pan = (v.get('pannelli') or []) + TAVOLA_STD[len(v.get('pannelli') or []):]
    prompt = (TAVOLA_PROMPT + ' '.join(f'PANEL {i + 1}: {x}.' for i, x in enumerate(pan[:4])) + ' MOMENT: ' + v['prompt'] + '. STYLE (the shot of each panel above wins over any framing written here): ' + STILE_SCENA +
              ' No text, no letters, no numbers, no captions, no speech bubbles, no borders other than the thin white dividing lines.')
    if refs:
        prompt = ('The character' + ('s' if len(refs) > 1 else '') + ' of the reference image' + ('s' if len(refs) > 1 else '') +
                  ' must appear in the panels kept IDENTICAL (same face, body, clothes and drawing style). Do not copy the white background of the reference. ' + prompt)
    if TAVOLA_RIF.get('url'):   # stesso disegno e stessi personaggi in tutto il video
        refs = list(refs) + [TAVOLA_RIF['url']]
        prompt = ('The LAST reference image is an earlier storyboard sheet of this same video: copy EXACTLY its drawing style, line thickness, colours and light, '
                  'and when the same characters appear keep their faces, hair and clothes identical; do NOT copy its scenes or compositions. ' + prompt)
    tav = p[:-4] + '_tavola.jpg'
    if not E('FAL_KEY'):
        Image.new('RGB', (3840, 2160), (200, 180, 140)).save(tav)
    pannelli, ok, motivo = None, False, None
    for tentativo in range(2):   # una sola ripetizione se la tavola non si taglia bene o non corrisponde alle parole
        try:
            if E('FAL_KEY'):
                _immagine_fal(prompt + (' IMPORTANT: ' + motivo if tentativo and motivo else ''), refs, tav, (3840, 2160))
            pannelli, ok = taglia_tavola(Image.open(tav))
        except Exception as e:
            log('tavola', v['img'], 'non riuscita:', str(e)[:150]); ok = False
        motivo = None
        if ok and VERIFICA and E('FAL_KEY'):
            motivo = verifica_immagine(tav, testi, v['prompt'], 'E\' una TAVOLA di 4 inquadrature dello stesso momento separate da linee bianche: le linee vanno bene, '
                                                              'controlla il contenuto dei 4 pannelli. Conta come errore anche ogni edificio moderno, '
                                                              'ciminiera di fabbrica, finestra a vetri, ringhiera di ferro, croce su una chiesa, monumento costruito dopo l\'epoca raccontata '
                                                              '(la citta\' deve essere com\'era ALLORA, mai com\'e\' oggi). Guarda bene anche lo sfondo di ogni pannello. ')
            if motivo:
                log(f'tavola {v["img"]} da rifare: {motivo}'); ok = False
        if ok:
            break
        motivo = motivo or 'four EQUAL panels separated by thin straight white lines crossing exactly in the centre'
    if pannelli is None:   # mai senza immagine: tavola non riuscita due volte -> immagine singola
        _immagine_fal(v['prompt'] + '. ' + STILE_SCENA, refs, p); TAVOLE_KO.add(v['img'])
        return [p] * 4
    if not ok and pannelli:
        log('tavola', v['img'], 'tagliata male due volte: uso dei pannelli comunque')
    for q, x in zip(pannelli, out):
        q.save(x, quality=92)
    log('tavola pronta', v['img'])
    return out


# ============================================================ ATMOSFERA: particelle animate sopra l'immagine (gratis, generate qui)
ATMO_TIPI = ('pioggia', 'neve', 'polvere', 'braci', 'nebbia')


def atmosfera_clip(tipo):
    """Clip in loop (trasparente) con pioggia / neve / polvere / braci / nebbia: generata una volta per video."""
    with _atmo_lock:   # piu' inquadrature in parallelo: la clip si genera una volta sola
        return _atmosfera_clip(tipo)


_atmo_lock = threading.Lock()


def _atmosfera_clip(tipo):
    out = os.path.join(LAV, f'atmo_{tipo}.mov')
    if os.path.exists(out):
        return out
    w, h = 960, 540; T = {'pioggia': 2.0, 'neve': 6.0, 'polvere': 6.0, 'braci': 6.0, 'nebbia': 8.0}[tipo]; n = int(T * FPS)
    rng = np.random.default_rng(7); cart = os.path.join(LAV, f'atmo_{tipo}'); os.makedirs(cart, exist_ok=True)
    if tipo == 'nebbia':   # rumore morbido periodico (si ripete senza cuciture) che scorre in orizzontale
        def strato(scala):
            f = np.zeros((h, w), complex)
            for ky in range(-scala, scala + 1):
                for kx in range(-scala, scala + 1):
                    if kx or ky:
                        f[ky % h, kx % w] = rng.normal() / (kx * kx + ky * ky) * np.exp(2j * np.pi * rng.random())
            z = np.real(np.fft.ifft2(f)); return (z - z.min()) / (z.max() - z.min() + 1e-9)
        s1, s2 = strato(4), strato(7)
    else:
        m = {'pioggia': 260, 'neve': 170, 'polvere': 160, 'braci': 70}[tipo]
        x0, y0 = rng.random(m) * w, rng.random(m) * h
        dim, fase, freq = rng.uniform(.5, 1.0, m), rng.random(m) * 6.283, rng.integers(1, 3, m)
        giri = rng.integers(1, 3, m) if tipo != 'pioggia' else rng.integers(3, 5, m)   # quante volte attraversa lo schermo in un loop (intero = loop perfetto)
    for i in range(n):
        t = i / n
        if tipo == 'nebbia':
            z = .6 * np.roll(s1, int(w * t), axis=1) + .4 * np.roll(s2, -int(w * t), axis=1)
            al = (np.clip((z - .35) / .65, 0, 1) * 120).astype(np.uint8)
            fr = np.dstack([np.full((h, w), 225, np.uint8)] * 3 + [al]); Image.fromarray(fr, 'RGBA').save(os.path.join(cart, f'{i:04d}.png')); continue
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for j in range(m):
            if tipo == 'pioggia':
                y = (y0[j] + giri[j] * h * t) % h; x = (x0[j] - .25 * (y - y0[j])) % w; L = 14 + 18 * dim[j]
                d.line((x, y, x - .25 * L, y - L), fill=(215, 225, 240, int(110 + 90 * dim[j])), width=1)
            elif tipo == 'neve':
                y = (y0[j] + giri[j] * h * t) % h; x = (x0[j] + 12 * math.sin(6.283 * freq[j] * t + fase[j])) % w; r = .8 + 2.2 * dim[j]
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(150 + 100 * dim[j])))
            elif tipo == 'polvere':
                x = (x0[j] + 18 * math.sin(6.283 * freq[j] * t + fase[j])) % w; y = (y0[j] + 10 * math.cos(6.283 * freq[j] * t + fase[j])) % h; r = .6 + 1.6 * dim[j]
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 232, 190, int(70 + 170 * (.5 + .5 * math.sin(6.283 * freq[j] * t + fase[j] * 2)) * dim[j])))
            else:   # braci: salgono ondeggiando e brillano
                y = (y0[j] - giri[j] * h * t) % h; x = (x0[j] + 15 * math.sin(6.283 * freq[j] * t + fase[j])) % w; r = 1 + 1.8 * dim[j]
                d.ellipse((x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2), fill=(255, 120, 30, 60))
                d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 200, 90, int(160 + 90 * (.5 + .5 * math.sin(6.283 * 2 * t + fase[j])))))
        if tipo in ('neve', 'braci', 'polvere'):
            im = im.filter(ImageFilter.GaussianBlur(.6))
        im.save(os.path.join(cart, f'{i:04d}.png'))
    run(['ffmpeg', '-y', '-v', 'error', '-framerate', FPS, '-i', os.path.join(cart, '%04d.png'), '-c:v', 'qtrle', '-pix_fmt', 'argb', out])
    shutil.rmtree(cart, ignore_errors=True)
    return out


def pezzo_regia(path, d, img, zoom, camera, titolo='', nome_font='classico', atmo='', flash=False):
    x0, y0, w0 = ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])
    w0 = min(w0, .86) if camera in ('pan_left', 'pan_right', 'tilt_up', 'tilt_down') else w0
    cx, cy = x0 + ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])[2] / 2, y0 + ZOOM_BOX.get(zoom or '', ZOOM_BOX[''])[2] / 2
    a = (max(0, min(1 - w0, cx - w0 / 2)), max(0, min(1 - w0, cy - w0 / 2)), w0)
    sp = (1 - w0) * .9   # quanto ci si puo' spostare
    if camera in ('push_in', 'punch'):
        w1 = a[2] * (.72 if camera == 'punch' else .84); b = (a[0] + (a[2] - w1) / 2, a[1] + (a[2] - w1) / 2, w1)
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
    if camera == 'punch':   # zoom secco nei primi 0,2 s, poi quasi fermo: il "colpo" dei video ad alto ritmo
        k5 = max(2, int(FPS * .2))
        e = lambda p_, q: f'({p_:.4f}+({q:.4f}-{p_:.4f})*(0.85*(1-pow(1-min(on/{k5},1),3))+0.15*on/{n1}))'
    vf = (f"scale=3840:2160:flags=lanczos,zoompan=z='1/{e(a[2], b[2])}':x='iw*{e(a[0], b[0])}':y='ih*{e(a[1], b[1])}':d=1:s={W}x{H}:fps={FPS}")
    ov = None
    if ATMOSFERA and atmo in ATMO_TIPI:
        try:
            ov = atmosfera_clip(atmo)
        except Exception as e_:
            log('atmosfera saltata:', atmo, str(e_)[:120])
    if ov:   # particelle sopra il disegno; grana e titolo vengono dopo
        vf += f"[b];[1:v]scale={W}:{H},format=rgba[o];[b][o]overlay=0:0:shortest=1"
    if flash:
        vf += ',fade=t=in:st=0:d=0.15:color=white'
    if GRANA:
        vf += ',noise=alls=4:allf=t,vignette=angle=PI/6'
    if titolo:   # inizio capitolo: titolo grande che appare e scompare
        tf = path[:-4] + '_t.txt'; open(tf, 'w').write(titolo.upper())
        ff = os.path.join(FONT, FONT_EPOCA.get(nome_font, 'EBGaramond-SemiBold.ttf'))
        fs = 150
        try:   # la scritta sta sempre dentro lo schermo (margine 100 px per lato, box compreso)
            while fs > 50 and ImageFont.truetype(ff, fs).getlength(titolo.upper()) > W - 280:
                fs -= 6
        except Exception:
            fs = 100
        vf += (f",drawtext=fontfile={ff}:textfile={tf}:fontsize={fs}:fontcolor=white:borderw=6:bordercolor=black@0.7:"
               f"box=1:boxcolor=black@0.35:boxborderw=40:x=(w-tw)/2:y=(h-th)/2:"
               f"alpha='if(lt(t,0.3),t/0.3,if(lt(t,{max(.6, d - .5):.2f}),1,max(0,({d:.2f}-t)/0.5)))'")
    if ov:
        run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', FPS, '-t', d, '-i', img, '-stream_loop', '-1', '-i', ov,
             '-filter_complex', '[0:v]' + vf + ',setsar=1[v]', '-map', '[v]', '-t', d, *ENC, path])
    else:
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
    immagini = {}
    if TAVOLE and nuove and E('FAL_KEY'):   # la prima tavola fa da riferimento (stile e personaggi) a tutte le altre
        immagini[nuove[0]['img']] = genera_regia(nuove[0], testi[nuove[0]['img']])
        try:
            rif = os.path.join(LAV, 'tavola_rif.jpg')
            Image.open(immagini[nuove[0]['img']][0][:-7] + '_tavola.jpg').convert('RGB').resize((1920, 1080), Image.LANCZOS).save(rif, quality=88)
            TAVOLA_RIF['url'] = carica_fal(rif, 'image/jpeg')
        except Exception as e:
            log('riferimento tavola non caricato:', str(e)[:150])
    with ThreadPoolExecutor(4) as ex:
        resto = [v for v in nuove if v['img'] not in immagini]
        immagini.update(zip([v['img'] for v in resto], ex.map(lambda v: genera_regia(v, testi[v['img']]), resto)))
    log('immagini pronte:', len(immagini), 'in', int(time.time() - t0), 's')

    def fai(k):
        v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4')
        try:
            if v['tipo'] == 'mappa':
                return pezzo_mappa(p, d, c.get('paese_mappa') or '', c.get('titolo_mappa') or TITOLO.split()[-1], c.get('date') or '')
            if v['tipo'] in ('pexels_video', 'pexels_foto'):   # clip o foto d'epoca, scelta e controllata da Claude (niente persone, niente moderno)
                u, tipo = None, v['tipo']
                for tipo in (v['tipo'], 'pexels_foto' if v['tipo'] == 'pexels_video' else 'pexels_video'):
                    for qq in [v.get('q')] + list(v.get('alt_q') or []):
                        if qq:
                            u = pexels('video' if tipo == 'pexels_video' else 'foto', qq, v.get('contesto') or v['testo'])
                        if u:
                            break
                    if u:
                        break
                if not u:
                    raise RuntimeError('nessuna immagine Pexels adatta per ' + str(v.get('q')))
                v['tipo'] = tipo
                src = os.path.join(LAV, f'src_{k:04d}' + ('.mp4' if tipo == 'pexels_video' else '.jpg'))
                scarica(u, src)
                pezzo_video(p, d, src) if tipo == 'pexels_video' else pezzo_foto(p, d, src, flash=True)
            else:
                src = immagini[v['img']]
                zoom = v.get('zoom')
                if isinstance(src, list):   # tavola: il pannello di questa inquadratura
                    src = src[v.get('pannello', 0) % len(src)]
                    if v['img'] in TAVOLE_KO and not zoom:
                        zoom = ('', 'volto', 'basso', 'destra')[v.get('pannello', 0) % 4]
                pezzo_regia(p, d, src, zoom, v.get('camera'), v.get('capitolo') or '', nome_font, v.get('atmo') or '')
        except Exception as e:
            log('inquadratura', k, 'di riserva:', str(e)[:200])
            prec = next((immagini[x['img']] for x in reversed(piano[:k]) if x.get('img') in immagini), None) or next(iter(immagini.values()))
            prec = prec[-1] if isinstance(prec, list) else prec
            v.pop('didascalia', None); v['tipo'] = 'cartone'
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


# ============================================================ SCENE (colonna tavole=SI): ogni inquadratura e' una SCENA DIVERSA, mai ripetuta
# Ritmo da "film" (metodo MrBeast): taglio ogni 2-3 s, anteprima COMING UP, scritte a scatto, etichetta fissa, battute, zoom secchi, suoni.
# Ogni immagine generata e' un foglio 2x2 a 4K con 4 scene DIVERSE in sequenza (4 immagini Full HD al prezzo di una).
CAMERE_SCENE = CAMERE + ('punch',)
REGOLE_PEXELS_SCENE = REGOLE_PEXELS.replace('Mai due di fila e mai a meta\' di una tavola (dopo un pexels la riga seguente e\' "nuova": true). ', 'Mai due di fila. ')
SCENA_FOGLIO = ('A 2x2 STORYBOARD SHEET: the image is divided into FOUR EQUAL panels (top-left, top-right, bottom-left, bottom-right) separated by thin straight '
                'white lines that cross exactly in the centre. Each panel is a complete 16:9 frame showing a DIFFERENT scene of the same story, in this order: ')
SCENA_FINE = (' Every panel shows an ACTION happening, never a static pose; vary the framing between panels (wide, medium, close-up, detail, from above, from below). '
              'Recurring characters keep the same face and clothes. Places are shown exactly as they were IN THAT ERA, never as they look today. '
              'Everything is historically accurate for the era of the story: no modern buildings, no later monuments, no factory chimneys, no glass windows, '
              'no electric lights, no iron railings, no church crosses, no modern clothes or objects. '
              'No text, no letters, no numbers, no captions, no speech bubbles, no borders other than the thin white dividing lines.')


def piano_scene(c, shots, kit):
    """Claude fa il regista: per OGNI inquadratura una scena diversa, piu' scritte, etichette, battute e suoni."""
    chiave = E('ANTHROPIC_API_KEY', '')
    lotto, ris, gia = 50, {}, []
    for b0 in range(0, len(shots), lotto):
        parte = shots[b0:b0 + lotto]
        elenco = '\n'.join(f'{b0 + k}: {s["testo"]}' + ('   [COMING UP]' if s.get('t', 0) < COMING_UP else '')
                           + (f'   [CAPITOLO: {s["capitolo"]}]' if s.get('capitolo') else '')
                           + ('   [PEXELS SI]' if REGIA_PEXELS and s.get('t', 0) >= PEXELS_DA else '') for k, s in enumerate(parte))
        prompt = f"""Sei il regista di un video YouTube di storia a cartone che deve tenere incollati come un film (ritmo da MrBeast): "{c.get('titolo') or TITOLO}".
Ogni riga e' un'inquadratura di 2-3 secondi con le PAROLE che la voce dice in quel momento. Per OGNI riga decidi cosa si vede.
{('Scene GIA usate (non ripeterle MAI, nemmeno simili): ' + ' | '.join(gia[-40:])) if gia else ''}

REGOLE:
1. OGNI RIGA E' UNA SCENA DIVERSA: un'altra azione, un altro soggetto o un altro luogo. MAI la stessa scena due volte, nemmeno da un'altra angolazione o piu' da vicino. Lo spettatore deve vedere sempre qualcosa di nuovo che succede.
2. COERENZA: la scena mostra ESATTAMENTE quello che dicono le parole di quella riga (persone, luogo, ora del giorno, tempo atmosferico, emozione). Se le parole sono astratte, una scena concreta che le rappresenta.
3. OGGETTI DELL'EPOCA: disegna solo cose che esistevano allora. Se la voce nomina una cosa moderna per contrasto ("niente sveglia, niente caffe'"), mostra l'equivalente antico (un gallo che canta, una lucerna, una meridiana), MAI l'oggetto moderno: niente orologi meccanici, ingranaggi, vetrate, carta stampata, occhiali.
3b. "prompt_en" (SEMPRE; sulle righe con "tipo" pexels bastano 10-15 parole, servono solo di riserva): in inglese, 25-45 parole: chi c'e', cosa sta FACENDO (un'azione in corso), dove, luce, emozione forte e leggibile, e l'inquadratura. Alterna di continuo campo largo, campo medio, primo piano, dettaglio, dall'alto, dal basso: mai la stessa inquadratura due volte di fila. Vestiti, armi, edifici e oggetti esatti dell'epoca raccontata; luoghi come erano ALLORA. Mai scritte nelle immagini.
4. "personaggi": 0-2 id del kit solo se sono proprio loro. Kit: {lista_kit(kit)}. I personaggi ricorrenti hanno sempre gli stessi vestiti: descrivili uguali ogni volta.
5. "camera": push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down, punch (zoom secco: solo nei momenti forti, 1 riga ogni 5-6). Mai uguale due volte di fila.
6. [COMING UP]: queste righe sono l'ANTEPRIMA del video, come nei video di MrBeast: mostrano i momenti piu' spettacolari, sorprendenti o drammatici di TUTTA la storia (anche se la voce qui dice altro), ognuno una scena diversa. Nel resto del video non disegnare MAI di nuovo una scena gia' mostrata nell'anteprima.
7. "scritta" (circa 1 riga ogni 4, mai due di fila): 1-4 parole IN MAIUSCOLO che la voce dice in quella riga e che colpiscono (numeri, cifre, orari, nomi, parole forti: "5:00 AM", "300 SESTERCES", "NO WATER", "CAESAR"). Nella lingua del video.
8. "etichetta": SOLO quando nel racconto cambia il TEMPO (ora del giorno, giorno, anno): una etichetta breve che resta fissa nell'angolo finche' non cambia (es. "5:00 AM", "NOON", "SUNSET", "DAY 1", "64 AD"). Mai concetti o temi ("MYTH", "REALITY", "THE PATRON"): per quelli c'e' la scritta. Al massimo 1 nuova etichetta ogni 30 secondi. Altrimenti "".
9. "battuta" (1-2 al minuto, solo nei momenti ironici o sorprendenti): commento breve e divertente in basso, max 6 parole, nella lingua del video (es. "OUCH...", "NOT IDEAL", "HE WAS NOT OKAY").
10. "flash": true solo nei colpi di scena (max 1 ogni 20 secondi).
11. "atmosfera" (di solito ""): pioggia, neve, polvere, braci o nebbia SOLO se la scena li ha davvero.
11b. "musica": l'UMORE della musica, SOLO dove cambia (un tratto dura almeno 15-20 secondi): uno tra mistero, tensione, epico, azione, curiosita, quotidiano, malinconia, trionfo. Segui il racconto come in un film: mistero o curiosita' all'inizio, tensione quando arriva il problema, epico nelle battaglie, malinconia nei momenti tristi, trionfo nelle conquiste. La prima riga ha sempre un umore. Altrimenti "".
11c. "stacco": true sulla riga di una RIVELAZIONE o di un colpo di scena (max 1 ogni 30 secondi): la musica si ferma un attimo prima e riparte.
12. "suono" (circa una riga ogni 4): effetto sonoro in inglese, 3-8 parole, coerente con quello che si vede (passi, porta, folla, spade, cavalli, fuoco, pioggia, monete). Mai musica, mai voci.
{REGOLE_PEXELS_SCENE.format(q=REGIA_PEXELS) if REGIA_PEXELS else ''}

INQUADRATURE:
{elenco}

Rispondi SOLO con un array JSON, un oggetto per riga, con lo stesso numero "n":
[{{"n": {b0}, "prompt_en": "...", "personaggi": [], "camera": "push_in", "scritta": "", "etichetta": "", "battuta": "", "flash": false, "atmosfera": "", "suono": "", "musica": "mistero", "stacco": false{', "tipo": "cartone", "q": "", "alt_q": []' if REGIA_PEXELS else ''}}}]"""
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
                log('regia scene non valida, riprovo:', str(e)[:150]); time.sleep(5)
        gia += [str(ris[n].get('prompt_en') or '')[:90] for n in range(b0, b0 + len(parte)) if n in ris and ris[n].get('prompt_en')]
    out, ultima_cam, etichetta, ultimo_px, ultima_scritta = [], '', '', False, -9
    for n, s in enumerate(shots):
        r = dict(ris.get(n) or {})
        cam = r.get('camera') if r.get('camera') in CAMERE_SCENE else random.choice(CAMERE)
        if cam == ultima_cam:
            cam = random.choice([x for x in CAMERE if x != cam])
        ultima_cam = cam
        if str(r.get('etichetta') or '').strip():
            etichetta = str(r['etichetta']).strip().upper()[:18]
        scritta = str(r.get('scritta') or '').strip().upper()[:28]
        if scritta and n - ultima_scritta < 2:
            scritta = ''
        if scritta:
            ultima_scritta = n
        v = dict(s, tipo='cartone', camera=cam, prompt=str(r.get('prompt_en') or '').strip() or ('Historical scene, action in progress, illustrating: ' + s['testo']),
                 personaggi=[x for x in (r.get('personaggi') or []) if x in kit and x != NARRATORE][:2], scritta=scritta, etichetta=etichetta,
                 battuta=str(r.get('battuta') or '').strip().upper()[:40], flash=bool(r.get('flash')),
                 atmo=str(r.get('atmosfera') or '').strip().lower() if str(r.get('atmosfera') or '').strip().lower() in ATMO_TIPI else '',
                 suono=str(r.get('suono') or '').strip()[:80], didascalia='', coming_up=s.get('t', 0) < COMING_UP,
                 musica=str(r.get('musica') or '').strip().lower().replace("'", '').replace('à', 'a'), stacco=bool(r.get('stacco')))
        q_px = str(r.get('q') or '').strip()
        if q_px:
            v.update(q=q_px, alt_q=[str(x).strip() for x in (r.get('alt_q') or []) if str(x).strip()][:2])
        if REGIA_PEXELS and s.get('t', 0) >= PEXELS_DA and r.get('tipo') in ('pexels_video', 'pexels_foto') and q_px and not ultimo_px:
            v.update(tipo=r['tipo'], contesto=s['testo'], camera='')
        ultimo_px = v['tipo'] != 'cartone'
        out.append(v)
    # tetto di costo: piu' scene a cartone di quelle pagate dal tetto -> immagini Pexels d'epoca (dopo il primo minuto, mai due di fila)
    cartoni = [i for i, v in enumerate(out) if v['tipo'] == 'cartone']
    troppe = len(cartoni) - IMMAGINI_MAX * 4
    if troppe > 0 and REGIA_PEXELS:
        adatti = [i for i in cartoni if out[i].get('q') and out[i].get('t', 0) >= PEXELS_DA and not out[i].get('capitolo')
                  and (i == 0 or out[i - 1]['tipo'] == 'cartone') and (i + 1 >= len(out) or out[i + 1]['tipo'] == 'cartone')]
        scelti = [adatti[int(j * len(adatti) / troppe)] for j in range(min(troppe, len(adatti)))] if adatti else []
        for i in scelti:
            if (i == 0 or out[i - 1]['tipo'] == 'cartone') and (i + 1 >= len(out) or out[i + 1]['tipo'] == 'cartone'):
                out[i].update(tipo='pexels_video' if i % 2 else 'pexels_foto', contesto=out[i]['testo'], camera='')
        log(f'tetto di {IMMAGINI_MAX} fogli: {sum(1 for i in scelti if out[i]["tipo"] != "cartone")} scene a cartone diventano Pexels')
        resto = sum(1 for v in out if v['tipo'] == 'cartone') - IMMAGINI_MAX * 4
        if resto > 0:   # il tetto non si supera mai: se serve anche due immagini vere di fila
            altri = [i for i, v in enumerate(out) if v['tipo'] == 'cartone' and v.get('q') and v.get('t', 0) >= PEXELS_DA and not v.get('capitolo')]
            for i in [altri[int(j * len(altri) / resto)] for j in range(min(resto, len(altri)))] if altri else []:
                out[i].update(tipo='pexels_video' if i % 2 else 'pexels_foto', contesto=out[i]['testo'], camera='')
    log('inquadrature (secondo, durata, tipo):', ' '.join(f"{v['t']:.1f}/{v['d']:.1f}/{v['tipo'][:3]}" for v in out)[:3000])
    log(f"regia scene: {len(out)} inquadrature, {sum(1 for v in out if v['tipo'] == 'cartone')} cartoni, "
        f"{sum(1 for v in out if v['tipo'] != 'cartone')} Pexels, {sum(1 for v in out if v.get('scritta'))} scritte, "
        f"{sum(1 for v in out if v.get('battuta'))} battute, anteprima {sum(1 for v in out if v.get('coming_up'))} scene")
    return out


def _sottopannelli(q):
    """Vero se dentro un pannello c'e' un'altra linea divisoria (il modello ha disegnato piu' di 4 riquadri)."""
    a = np.asarray(q.resize((q.width // 4, q.height // 4)), dtype=np.int16)
    h, w = a.shape[:2]
    return bool(_linea(_bordo(a)[1], int(h * .2), int(h * .8)) or _linea(_bordo(a.transpose(1, 0, 2))[1], int(w * .2), int(w * .8)))


def verifica_foglio(tav, testi, descr):
    """Claude guarda il foglio e dice QUALI pannelli sono sbagliati (epoca, scritte, anatomia, scena ripetuta). Ritorna l'insieme (0-3)."""
    chiave = E('ANTHROPIC_API_KEY', '')
    if not chiave or not VERIFICA:
        return set()
    im = Image.open(tav).convert('RGB'); im.thumbnail((1568, 1568)); buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85)
    domanda = (f"Foglio con 4 pannelli (1 in alto a sinistra, 2 in alto a destra, 3 in basso a sinistra, 4 in basso a destra) per un video di storia: "
               f"{PAESE.get('nome') or ''}. Le parole della voce: \"{testi[:600]}\". Le scene previste: {' | '.join(descr)[:1200]}.\n"
               "Per OGNI pannello controlla SOLO errori evidenti: edifici moderni o costruiti dopo l'epoca, ciminiere, vetrate, ringhiere di ferro, croci, "
               "orologi meccanici, ingranaggi, vestiti o oggetti non dell'epoca, scritte o lettere, anatomia sbagliata (3 braccia, volti deformi), "
               "sacchi di plastica, piazze o palazzi della citta' di oggi (facciate colorate moderne, obelischi in piazze moderne), "
               "pannello diviso in due immagini affiancate, pannello che ripete la stessa scena di un altro, pannello vuoto o tagliato.\n"
               "Prima, per OGNI pannello, scrivi una riga: 'Pannello N: <cosa si vede sullo SFONDO e sui bordi> -> <eventuali elementi non antichi>'. "
               "Poi chiudi con UNA riga: SBAGLIATI: <numeri dei pannelli sbagliati separati da virgola, oppure nessuno>")
    try:
        r = http('https://api.anthropic.com/v1/messages', {'model': str(P.get('modello_controllo_scene') or MODELLO_CONTROLLO), 'max_tokens': 700,
                 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': domanda}]}]}, {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=120)
        txt = ''.join(b.get('text', '') for b in r.get('content', []))
        m = re.search(r'SBAGLIATI:\s*(.*)', txt)
        return {int(x) - 1 for x in re.findall(r'[1-4]', m.group(1))} if m else set()
    except Exception as e:
        log('controllo foglio non riuscito:', str(e)[:120]); return set()


def _pannello_buono(q):
    return 1.35 < q.width / max(1, q.height) < 2.3 and not _sottopannelli(q)


def genera_foglio(g, scene, testi):
    _CTX.scena = True
    try:
        return _genera_foglio(g, scene, testi)
    finally:
        _CTX.scena = False


def _genera_foglio(g, scene, testi):
    """Un foglio 2x2 a 4K con 4 scene diverse -> {indice: immagine Full HD} dei soli pannelli BUONI.
    Spesa prevedibile: UNA generazione per foglio; una seconda solo se il foglio e' inutilizzabile (meno di 2 pannelli buoni).
    I pannelli sbagliati non si rifanno: la loro inquadratura prende un'immagine di riserva (mai una ripetuta)."""
    base = os.path.join(LAV, f'foglio_{g:03d}')
    out = [f'{base}_p{i}.jpg' for i in range(4)]
    pronti = {i: x for i, x in enumerate(out[:len(scene)]) if os.path.exists(x)}
    if os.path.exists(base + '_fatto') and pronti:
        return pronti
    refs = []
    for pg in list(dict.fromkeys(x for v in scene for x in (v.get('personaggi') or [])))[:3]:
        try:
            u = ref_personaggio(pg)
            if u:
                refs.append(u)
        except Exception as e:
            log('riferimento personaggio non caricato:', pg, str(e)[:100])
    descr = [v['prompt'] for v in scene] + [scene[-1]['prompt'] + ' (another moment, different action)'] * (4 - len(scene))
    prompt = SCENA_FOGLIO + ' '.join(f'PANEL {i + 1}: {x}' + ('' if x.endswith('.') else '.') for i, x in enumerate(descr)) + ' STYLE: ' + STILE_SCENA + SCENA_FINE
    if refs:
        prompt = ('The character' + ('s' if len(refs) > 1 else '') + ' of the reference image' + ('s' if len(refs) > 1 else '') +
                  ' must appear kept IDENTICAL (same face, body, clothes and drawing style) when the panels talk about them. Do not copy the white background of the reference. ' + prompt)
    if TAVOLA_RIF.get('url'):
        refs = refs + [TAVOLA_RIF['url']]
        prompt = ('The LAST reference image is an earlier storyboard sheet of this same video: copy EXACTLY its drawing style, line thickness, colours and light, '
                  'and keep recurring characters identical; do NOT copy its scenes or compositions. ' + prompt)
    if not E('FAL_KEY'):
        for x in out[:len(scene)]:
            Image.new('RGB', (1920, 1080), (200, 180, 140)).save(x)
        open(base + '_fatto', 'w').write('1')
        return {i: x for i, x in enumerate(out[:len(scene)])}
    tav = base + '_tavola.jpg'
    for tentativo in range(2):
        try:
            _immagine_fal(prompt + (' IMPORTANT: exactly FOUR EQUAL panels in a 2x2 grid, separated by thin straight white lines crossing exactly in the centre.' if tentativo else ''),
                          refs, tav, (3840, 2160))
        except Exception as e:
            log('foglio', g, 'non generato:', str(e)[:150]); continue
        pannelli, _ = taglia_tavola(Image.open(tav), (1920, 1080))
        crudi = taglia_tavola_crudi(Image.open(tav))
        buoni = {i for i in range(len(scene)) if _pannello_buono(crudi[i])}
        if len(buoni) < 2 and tentativo == 0:
            log(f'foglio {g} inutilizzabile ({len(buoni)} pannelli buoni): rifatto una volta'); continue
        sbagliati = verifica_foglio(tav, testi, descr[:len(scene)]) if buoni else set()
        buoni -= sbagliati
        for i in buoni:
            pannelli[i].save(out[i], quality=93)
        open(base + '_fatto', 'w').write('1')
        log(f'foglio {g}: {len(buoni)}/{len(scene)} pannelli buoni' + (f' (scartati dal controllo: {sorted(x + 1 for x in sbagliati)})' if sbagliati else ''))
        return {i: out[i] for i in sorted(buoni)}
    return {}


def taglia_tavola_crudi(im):
    """I 4 pannelli come escono dal foglio (senza adattarli al 16:9): servono a capire se sono buoni."""
    W_, H_ = im.size
    k = 2
    a = np.asarray(im.convert('RGB').resize((W_ // k, H_ // k)), dtype=np.int16); h2, w2 = a.shape[:2]

    def oriz(c0, c1):
        z = _linea(_bordo(a[:, c0:c1])[1], int(h2 * .3), int(h2 * .7))
        return (z[0] * k, z[1] * k) if z else (H_ // 2, H_ // 2)

    def vert(r0, r1):
        z = _linea(_bordo(a[r0:r1].transpose(1, 0, 2))[1], int(w2 * .3), int(w2 * .7))
        return (z[0] * k, z[1] * k) if z else (W_ // 2, W_ // 2)
    ys = oriz(int(w2 * .05), int(w2 * .3)), oriz(int(w2 * .7), int(w2 * .95))
    vt = vert(int(h2 * .05), int(min(ys[0][0], ys[1][0]) / k * .9))
    vb = vert(int(max(ys[0][1], ys[1][1]) / k + (h2 - max(ys[0][1], ys[1][1]) / k) * .1), int(h2 * .95))
    boxes = [(0, 0, vt[0], ys[0][0]), (vt[1], 0, W_, ys[1][0]), (0, ys[0][1], vb[0], H_), (vb[1], ys[1][1], W_, H_)]
    return [_rifila(im.convert('RGB').crop(bx)) for bx in boxes]


def _font_scene(sz):
    for nome in ('LuckiestGuy.ttf', 'Oswald-SemiBold.ttf', 'EBGaramond-SemiBold.ttf'):
        p = os.path.join(FONT, nome)
        if os.path.exists(p):
            return ImageFont.truetype(p, sz), p
    return ImageFont.load_default(), ''


def aggiungi_scritta(path, d, testo):
    """Scritta che ENTRA A SCATTO (grande, rimbalza e si ferma), gialla con bordo nero, nel terzo alto. Mai fuori dallo schermo."""
    sz = 150
    f, _ = _font_scene(sz)
    while sz > 50 and f.getlength(testo) > W - 260:
        sz -= 8; f, _ = _font_scene(sz)
    base = Image.new('RGBA', (int(f.getlength(testo)) + 60, int(sz * 1.5)), (0, 0, 0, 0))
    ImageDraw.Draw(base).text((30, sz * .2), testo, font=f, fill=(255, 214, 0), stroke_width=max(6, sz // 12), stroke_fill=(0, 0, 0))
    tmp = path[:-4] + '_w.mp4'
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
        t0 = t - .08
        if t0 >= 0:
            s_ = 1.0 if t0 > .3 else (1.6 - 2.4 * t0 if t0 < .25 else 1.0 + .2 * (1 - (t0 - .25) / .05))   # entra grande, rimbalza, si ferma
            s_ = max(1.0, s_) if t0 > .25 else s_
            w_, h_ = int(base.width * s_), int(base.height * s_)
            q = base.resize((w_, h_), Image.BILINEAR)
            if d - t < .2:
                q.putalpha(q.getchannel('A').point(lambda x: int(x * max(0, (d - t) / .2))))
            im.alpha_composite(q, ((W - w_) // 2, max(10, int(H * .2) - h_ // 2)))
        scrittore.stdin.write(im.convert('RGB').tobytes())
    lettore.wait(); scrittore.stdin.close(); scrittore.wait()
    if scrittore.returncode or k == 0:
        raise RuntimeError('scritta non riuscita')
    os.replace(tmp, path)


def riserva_scene():
    """Immagini vere d'epoca di riserva, dalla colonna stock_fallback_query del canale ("ricerca: parole chiave, ..."): si cercano solo se servono."""
    voci = []
    for pezzo in re.split(r',\s*(?=[^,:]+:)', str(P.get('stock_fallback_query') or '')):
        if ':' in pezzo:
            q, chiavi = pezzo.split(':', 1)
            voci.append((q.strip(), {w.strip().lower() for w in chiavi.split() if len(w.strip()) > 2}))
    return voci


def video_scene(c, durs, voci, kit):
    shots = taglia_inquadrature(c['scene'], durs, voci)
    piano = piano_scene(c, shots, kit)
    fine_prec, acc = 0, 0.0   # durate a fotogrammi interi: video e voce restano allineati
    for v in piano:
        acc += v['d']; fine = int(round(acc * FPS)); v['d'] = max(1, fine - fine_prec) / FPS; fine_prec = fine
    t0 = time.time()

    def prendi(v, k, tipi, query):   # un'immagine vera adatta e mai usata (Claude la guarda prima)
        for tipo in tipi:
            for qq in query:
                u = pexels('video' if tipo == 'pexels_video' else 'foto', qq, v.get('contesto') or v['testo']) if qq else None
                if u:
                    src = os.path.join(LAV, f'src_{k:04d}' + ('.mp4' if tipo == 'pexels_video' else '.jpg'))
                    try:
                        scarica(u, src); return tipo, src
                    except Exception as e:
                        log('download Pexels non riuscito:', str(e)[:100])
        return None, None

    def trova(k):   # 1) immagini vere: quelle che non si trovano diventano scene a cartone
        v = piano[k]
        tipo, src = prendi(v, k, (v['tipo'], 'pexels_foto' if v['tipo'] == 'pexels_video' else 'pexels_video'), [v.get('q')] + list(v.get('alt_q') or []))
        if tipo:
            v.update(tipo=tipo, src=src)
        else:
            log('Pexels: niente di adatto per', repr(v.get('q')), '-> scena a cartone'); v['tipo'] = 'cartone'
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(trova, [k for k, v in enumerate(piano) if v['tipo'] != 'cartone']))
    # 2) fogli: 4 scene a cartone consecutive per foglio (una generazione a foglio: spesa prevedibile)
    cart = [k for k, v in enumerate(piano) if v['tipo'] == 'cartone']
    gruppi = [cart[i:i + 4] for i in range(0, len(cart), 4)]
    for g, ks in enumerate(gruppi):
        for j, k in enumerate(ks):
            piano[k].update(foglio=g, pannello=j)
    testo_g = [' / '.join(piano[k]['testo'] for k in ks) for ks in gruppi]

    def foglio_sicuro(g):
        try:
            return genera_foglio(g, [piano[k] for k in gruppi[g]], testo_g[g])
        except Exception as e:
            log('foglio', g, 'NON riuscito:', str(e)[:200]); return {}
    def foglio_sicuro_rec(g, ks):
        try:
            return genera_foglio(g, [piano[k] for k in ks], ' / '.join(piano[k]['testo'] for k in ks))
        except Exception as e:
            log('foglio di recupero', g, 'NON riuscito:', str(e)[:200]); return {}
    fogli = {}
    if gruppi:
        fogli[0] = foglio_sicuro(0)
        try:   # il primo foglio fa da riferimento di stile e personaggi a tutti gli altri
            src0 = os.path.join(LAV, 'foglio_000_tavola.jpg')
            if os.path.exists(src0) and E('FAL_KEY'):
                rif = os.path.join(LAV, 'tavola_rif.jpg')
                Image.open(src0).convert('RGB').resize((1920, 1080), Image.LANCZOS).save(rif, quality=88)
                TAVOLA_RIF['url'] = carica_fal(rif, 'image/jpeg')
        except Exception as e:
            log('riferimento foglio non caricato:', str(e)[:150])
    with ThreadPoolExecutor(4) as ex:
        resto = list(range(1, len(gruppi)))
        fogli.update(zip(resto, ex.map(foglio_sicuro, resto)))
    for v in piano:
        if v['tipo'] == 'cartone':
            v['img'] = (fogli.get(v['foglio']) or {}).get(v['pannello'])
    mancanti = [k for k, v in enumerate(piano) if v['tipo'] == 'cartone' and not v.get('img')]
    log('fogli pronti:', len(fogli), '| scene a cartone:', len(cart), '| senza immagine:', len(mancanti), '| in', int(time.time() - t0), 's')
    if mancanti:   # un giro di recupero: le scene rimaste senza disegno, ridisegnate insieme in fogli nuovi (4 per foglio)
        rec = [mancanti[i:i + 4] for i in range(0, len(mancanti), 4)]
        with ThreadPoolExecutor(4) as ex:
            esiti = list(ex.map(lambda gi: (gi, foglio_sicuro_rec(100 + gi, rec[gi])), range(len(rec))))
        for gi, ris in esiti:
            for j, k in enumerate(rec[gi]):
                if ris.get(j):
                    piano[k]['img'] = ris[j]
        mancanti = [k for k in mancanti if not piano[k].get('img')]
        log('dopo il recupero, scene senza disegno:', len(mancanti))
    # 3) ogni scena senza immagine prende un'immagine vera d'epoca di riserva, scelta sulle parole della voce (mai una ripetuta)
    riserva = riserva_scene()

    def ripara(k):
        v = piano[k]
        parole = set(re.findall(r'[a-zàèéìòù]{3,}', v['testo'].lower()))
        ordine = sorted(riserva, key=lambda x: -len(x[1] & parole))
        query = [v.get('q')] + list(v.get('alt_q') or []) + [q for q, _ in ordine[:6]]
        tipo, src = prendi(v, k, ('pexels_video', 'pexels_foto'), [q for q in query if q])
        if tipo:
            v.update(tipo=tipo, src=src, contesto=v['testo']); return True
        return False
    dopo = [k for k in mancanti if piano[k].get('t', 0) >= PEXELS_DA]   # nel primo minuto solo cartoni: niente immagini vere di riserva
    with ThreadPoolExecutor(3) as ex:
        riparate = list(ex.map(ripara, dopo))
    ancora = [k for k in mancanti if k not in dopo] + [k for k, ok in zip(dopo, riparate) if not ok]
    # 4) ultima rete: la durata della scena mancante va ai vicini, senza superare il ritmo massimo (MAI 10 secondi ferma)
    massimo = max(RITMO) + .5
    buona = lambda j: piano[j]['tipo'] != 'cartone' or bool(piano[j].get('img'))
    for k in sorted(ancora):
        v = piano[k]
        sx = next((j for j in range(k - 1, -1, -1) if buona(j) and not piano[j].get('salta')), None)
        dx = next((j for j in range(k + 1, len(piano)) if buona(j)), None)
        vicini = [j for j in (sx, dx) if j is not None]
        if not vicini:
            continue
        quota = v['d'] / len(vicini)
        for j in vicini:
            piano[j]['d'] += quota
        v['salta'] = True
        if any(piano[j]['d'] > massimo for j in vicini):
            log(f'ATTENZIONE: inquadratura vicina a {k} supera {massimo:.1f} s')
    piano = [v for v in piano if not v.get('salta')]
    log(f'immagini: {len(mancanti)} scene senza disegno -> {sum(riparate)} immagini vere di riserva, {len(ancora)} assorbite dai vicini')
    nome_font = c.get('font_carte') if c.get('font_carte') in FONT_EPOCA else 'classico'

    def fai(k):
        try:
            return _fai(k)
        except Exception as e:
            log('inquadratura', k, piano[k]['tipo'], 'NON riuscita:', str(e)[:300]); return None

    def _fai(k):
        v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4')
        if v['tipo'] == 'cartone':
            pezzo_regia(p, d, v['img'], '', v.get('camera'), '' if v.get('coming_up') else (v.get('capitolo') or ''),
                        nome_font, v.get('atmo') or '', v.get('flash'))
        elif v['tipo'] == 'pexels_video':
            pezzo_video(p, d, v['src'])
        else:
            pezzo_foto(p, d, v['src'], flash=True)
        if v.get('scritta') and d > 1.0:
            try:
                aggiungi_scritta(p, d, v['scritta'])
            except Exception as e:
                log('scritta saltata:', str(e)[:120]); v['scritta'] = ''
        return p
    with ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(fai, range(len(piano))))
    buoni_p, buoni_v = [], []
    for p_, v in zip(paths, piano):
        if p_:
            buoni_p.append(p_); buoni_v.append(v)
        elif buoni_v:   # errore di montaggio (raro): la precedente dura di piu'
            buoni_v[-1] = dict(buoni_v[-1], d=buoni_v[-1]['d'] + v['d'])
            try:
                pv = buoni_p[-1][:-4] + '_l.mp4'
                run(['ffmpeg', '-y', '-v', 'error', '-i', buoni_p[-1], '-vf', f'tpad=stop_mode=clone:stop_duration={v["d"]:.3f}', *ENC, pv])
                buoni_p[-1] = pv
            except Exception as e:
                log('allungamento non riuscito:', str(e)[:120])
    if not buoni_p:
        raise RuntimeError('nessuna inquadratura riuscita')
    ds = [v['d'] for v in buoni_v]
    log(f'CONTROLLO RITMO: {len(buoni_p)} inquadrature, durata media {sum(ds) / len(ds):.1f} s, massima {max(ds):.1f} s, '
        f'oltre {massimo:.1f} s: {sum(1 for x in ds if x > massimo)} | in {int(time.time() - t0)} s')
    return buoni_v, buoni_p


def ritocchi_scene(video, piano):
    """Un solo passaggio sul video muto: COMING UP iniziale, etichetta fissa nell'angolo, battute in basso."""
    _, ff = _font_scene(60)
    if not ff:
        return video
    filtri, t, cartella = [], 0.0, os.path.join(LAV, 'testi_scene'); os.makedirs(cartella, exist_ok=True)

    def testo(nome, s_):
        p = os.path.join(cartella, nome + '.txt'); open(p, 'w').write(s_); return p
    if COMING_UP > 0:
        fine = min(COMING_UP, sum(v['d'] for v in piano if v.get('coming_up')) or COMING_UP)
        filtri.append(f"drawtext=fontfile={ff}:textfile={testo('cu', 'COMING UP...')}:fontsize=78:fontcolor=0xFFD600:borderw=6:bordercolor=black:"
                      f"x=60:y=h-th-70:enable='between(t,0,{fine:.2f})':alpha='if(lt(mod(t,1),0.75),1,0.55)'")
    tratti, ini, cur = [], 0.0, ''
    for v in piano:
        if v.get('etichetta', '') != cur:
            if cur:
                tratti.append((ini, t, cur))
            cur, ini = v.get('etichetta', ''), t
        if v.get('battuta') and v['d'] > 1.2:
            filtri.append(f"drawtext=fontfile={ff}:textfile={testo(f'b{len(filtri)}', v['battuta'])}:fontsize=64:fontcolor=white:borderw=5:bordercolor=black:"
                          f"x=w-tw-70:y=h-th-80:enable='between(t,{t + .15:.2f},{t + v['d']:.2f})'")
        t += v['d']
    if cur:
        tratti.append((ini, t, cur))
    for i, (a, b, et) in enumerate(tratti):
        if a < COMING_UP:   # durante l'anteprima niente etichetta
            a = COMING_UP
        if b - a < 1:
            continue
        filtri.append(f"drawtext=fontfile={ff}:textfile={testo(f'e{i}', et)}:fontsize=58:fontcolor=white:borderw=5:bordercolor=black:"
                      f"box=1:boxcolor=black@0.35:boxborderw=18:x=50:y=45:enable='between(t,{a:.2f},{b:.2f})'")
    if not filtri:
        return video
    out = video[:-4] + '_r.mp4'
    try:
        run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-vf', ','.join(filtri), *ENC, out])
        log('ritocchi scene: anteprima', 'si' if COMING_UP else 'no', '|', len(tratti), 'etichette |', sum(1 for v in piano if v.get('battuta')), 'battute')
        return out
    except Exception as e:
        log('ritocchi scene saltati:', str(e)[:200])
        return video


# ============================================================ MUSICA DA FILM (colonna musica_regia=SI, modo scene)
# Il regista segna l'UMORE di ogni tratto del racconto; la musica viene da una LIBRERIA comune a tutti i canali (cartella libreria_musica/),
# creata con Eleven Music (musica unica, nessun reclamo Content ID) e che cresce da sola: un brano si genera solo se manca.
MUSICA_REGIA = str(P.get('musica_regia') or E('MUSICA_REGIA', '') or 'NO').strip().upper() == 'SI'
UMORI = {
    'mistero': 'mysterious, curious and suspenseful, soft pulsing low strings, light plucks, slow build',
    'tensione': 'tense and urgent, ticking rhythm, deep drums and staccato strings, rising suspense',
    'epico': 'epic and grand, big war drums, brass and choir-like pads, powerful and heroic',
    'azione': 'fast action, driving percussion, aggressive strings, high energy chase',
    'curiosita': 'playful and light, quirky pizzicato strings and light percussion, curious and fun',
    'quotidiano': 'warm and lively daily life, gentle rhythm, plucked strings and soft flutes, relaxed',
    'malinconia': 'melancholic and emotional, slow solo instrument over soft strings, sad and reflective',
    'trionfo': 'triumphant and uplifting, bright brass and strings, celebratory climax',
}
LIB_MUSICA = os.path.join(ROOT, 'libreria_musica')


def _brano_umore(umore, evita):
    """Un brano della libreria per questo umore, mai uno di quelli in 'evita' (gia' usati di recente dal canale). Se manca, lo crea."""
    os.makedirs(LIB_MUSICA, exist_ok=True)
    stile = str(P.get('musica_stile') or '').strip()
    gia = sorted(_glob.glob(os.path.join(LIB_MUSICA, f'{umore}_*.mp3')))
    liberi = [f for f in gia if os.path.basename(f) not in evita]
    if liberi:
        return random.choice(liberi)
    chiave = E('ELEVENLABS_API_KEY', '') if ELEVEN_EXTRA else ''   # niente brani nuovi: si riusa la libreria
    if not chiave:
        return random.choice(gia) if gia else None
    prompt = (f'Instrumental cinematic background score for a documentary-style YouTube video, {UMORI[umore]}. '
              + (f'Colour: {stile}. ' if stile else '') + 'No vocals, no lyrics, clean mix, steady loopable feel, no fade-out at the end.')
    b = http('https://api.elevenlabs.io/v1/music', {'prompt': prompt, 'music_length_ms': 90000, 'model_id': 'music_v1', 'force_instrumental': True},
             {'xi-api-key': chiave, 'Accept': 'audio/mpeg'}, timeout=600, raw=True)
    n = 1 + max([int(re.search(r'_(\d+)\.mp3$', f).group(1)) for f in gia] or [0])
    p = os.path.join(LIB_MUSICA, f'{umore}_{n:03d}.mp3')
    open(p, 'wb').write(b)
    log('musica nuova in libreria:', os.path.basename(p), f'({len(b) // 1024} KB)')
    return p


def musica_scene(piano, voce_tot, totale):
    """Colonna sonora a tratti: un brano per umore, cambi in dissolvenza, silenzio di un attimo prima delle rivelazioni, sotto la voce."""
    tratti, t, cur, ini, stacchi = [], 0.0, None, 0.0, []
    for v in piano:
        u = v.get('musica') if v.get('musica') in UMORI else cur or 'mistero'
        if u != cur:
            if cur:
                tratti.append([ini, t, cur])
            cur, ini = u, t
        if v.get('stacco') and t > 3:
            stacchi.append(t)
        t += v['d'] - T_TR
    tratti.append([ini, totale, cur or 'mistero'])
    pulito = []   # tratti troppo corti (meno di 8 s) si uniscono al precedente
    for a, b, u in tratti:
        if pulito and (b - a < 8 or pulito[-1][2] == u):
            pulito[-1][1] = b
        else:
            pulito.append([a, b, u])
    usati_f = os.path.join(LIB_MUSICA, 'usati_' + re.sub(r'\W', '_', str(P.get('canale') or 'canale')) + '.json')
    try:
        recenti = json.load(open(usati_f))
    except Exception:
        recenti = []
    pezzi, scelti, X = [], [], 1.5
    for i, (a, b, u) in enumerate(pulito):
        f = _brano_umore(u, set(recenti[-12:]) | set(scelti))
        if not f:
            continue
        scelti.append(os.path.basename(f))
        lung = b - a + (X if i < len(pulito) - 1 else 0)
        dur_f = durata(f)
        off = random.uniform(0, max(0, dur_f - lung - 1)) if dur_f > lung + 1 else 0
        out = os.path.join(LAV, f'mus_{i:02d}.wav')
        filtro = f'atrim=0:{lung:.2f},asetpts=PTS-STARTPTS,afade=t=in:d={.8 if i else 2}'
        giro = ['-stream_loop', '-1'] if dur_f < lung else []   # brano piu' corto del tratto: si ripete
        run(['ffmpeg', '-y', '-v', 'error', *giro, '-ss', f'{off:.2f}', '-i', f, '-af', filtro, '-ar', '44100', '-ac', '2', out])
        pezzi.append(out)
    if not pezzi:
        return None
    mus = os.path.join(LAV, 'musica_scene.wav')
    if len(pezzi) == 1:
        shutil.copy(pezzi[0], mus)
    else:
        fl, prev = [], '[0:a]'
        for n in range(1, len(pezzi)):
            o = f'[m{n}]' if n < len(pezzi) - 1 else '[mm]'
            fl.append(f'{prev}[{n}:a]acrossfade=d={X}:c1=tri:c2=tri{o}'); prev = o
        run(['ffmpeg', '-y', '-v', 'error', *sum((['-i', p] for p in pezzi), []), '-filter_complex', ';'.join(fl), '-map', '[mm]', mus])
    vol = float(str(P.get('musica_volume') or .22).replace(',', '.').replace('%', ''))
    vol = vol / 100 if vol > 1 else vol
    buchi = '+'.join(f'between(t,{s - .9:.2f},{s:.2f})' for s in stacchi[:30])
    vol_expr = f"volume='{vol}*(1-0.95*({buchi}))':eval=frame" if buchi else f'volume={vol}'
    out = os.path.join(LAV, 'voce_musica.m4a')
    run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-i', mus, '-filter_complex',
         f"[1:a]{vol_expr},afade=t=out:st={max(0, totale - 3):.2f}:d=3,apad=whole_dur={totale:.2f}[m];"
         f'[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.05:ratio=4:attack=30:release=400[md];'
         f'[v][md]amix=inputs=2:duration=first:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', out])
    json.dump((recenti + scelti)[-40:], open(usati_f, 'w'))
    log('musica: ' + ' | '.join(f'{a:.0f}-{b:.0f}s {u}' for a, b, u in pulito), '| stacchi:', len(stacchi), '| brani:', ', '.join(scelti))
    return out


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
        if not vis:   # scena senza visivi: un disegno se ci sono, altrimenti (budget 0) una clip Pexels della riserva del paese
            vis = [{'tipo': 'cartone', 'sfondo': random.choice(list(sf))}] if sf else [{'tipo': 'pexels_video', 'q': (RISERVA_PX[i % len(RISERVA_PX)] if RISERVA_PX else 'ancient ruins landscape')}]
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
    global TITOLO
    os.makedirs(LAV, exist_ok=True)
    comp = competitor()
    # il titolo di riserva (es. "Tutta la storia dell'Iran") NON deve mai entrare nel copione se c'e' il video da copiare
    if comp.get('titolo'):
        TITOLO = comp['titolo'].strip()
    else:
        TITOLO = 'la storia completa del paese raccontato nel TESTO ORIGINALE qui sotto'
    log('VIDEO DA COPIARE:', comp.get('id'), '-', comp.get('titolo') or '(titolo non letto)', '| titolo usato:', TITOLO)
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
    if os.path.exists(salvato) and not PROVA:   # copione salvato fuori dalla durata del foglio (es. lanciato senza durata): si rifa' da zero
        try:
            n_par = sum(len(str(s_.get('testo', '')).split()) for s_ in json.load(open(salvato)).get('scene', []))
        except Exception:
            n_par = 0
        if n_par and (n_par > MAX_MINUTI * 150 * 1.10 or n_par < MIN_MINUTI * 150 * 0.90):
            log(f'RIPRESA SCARTATA: il copione salvato ({n_par} parole, ~{n_par / 150:.1f} min) e\' fuori da {MIN_MINUTI:g}-{MAX_MINUTI:g} minuti: si riparte da zero')
            for f_ in os.listdir(LAV):
                fp_ = os.path.join(LAV, f_)
                if os.path.isfile(fp_):
                    os.remove(fp_)
    if os.path.exists(salvato):   # ripresa dopo un errore: stesso copione, niente nuova spesa
        c = json.load(open(salvato))
        n_v = len([f for f in os.listdir(LAV) if f.startswith('voce_') and f.endswith('.mp3')])
        n_d = len([f for f in os.listdir(LAV) if re.match(r'sfondo_s\d+\.jpg$', f)])
        log(f'RIPRESA: copione salvato, {n_v} voci e {n_d} disegni gia\' pronti (non si ripagano)')
    else:
        c = copione(comp)
        if not MAPPA_SI:   # canale senza mappa (es. Faces of Rome)
            c['paese_mappa'] = ''
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
    if REGIA and TAVOLE:   # scene sempre diverse, ritmo da film (colonna tavole=SI)
        piano, paths = video_scene(c, durs, voci, kit)
    elif REGIA:   # solo cartoni: un'immagine scritta su ogni frase della voce
        piano, paths = video_regia(c, durs, voci, kit)
    else:
        # sfondi
        LUOGHI[:] = [str(x).strip().lower() for x in (c.get('luoghi_paese') or []) if len(str(x).strip()) >= 3][:40]
        log('luoghi del paese per i paesaggi Pexels:', ', '.join(LUOGHI) or '(nessuno: controllo solo visivo)')
        RISERVA_PX[:] = [str(x).strip() for x in (c.get('riserva_pexels') or []) if str(x).strip()][:10] or \
            [f"{c.get('paese_mappa') or 'ancient'} {x}" for x in ('landscape', 'river', 'mountains', 'ancient ruins', 'sky clouds', 'temple')]
        if BUDGET > 0 or SOLO_PEXELS:   # rete di sicurezza: mai piu' disegni di quanti ne paga il budget, anche se il copione ne chiede di piu'
            sec_v = sum(durs)
            massimo = 0 if SOLO_PEXELS else max(2, int((BUDGET * 1.08 - (0.35 + RISERVA_COP + 0.05 + sec_v / 5 * 0.005)) / (PREZZO_DISEGNO * 1.25)))
            c['sfondi'] = c.get('sfondi') or []
            if len(c['sfondi']) > massimo or (SOLO_PEXELS and any(v.get('tipo') == 'cartone' for sc_ in c['scene'] for v in sc_.get('visivi') or [])):
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
                if BUDGET > 0 or SOLO_PEXELS or not TEXTURE:   # mai un'immagine a caso: si continua l'immagine precedente (vedi sotto)
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
        # pezzo senza immagine giusta: MAI fermo immagine. Si riusa una clip Pexels gia' scaricata, lontana nel video,
        # presa in un altro tratto e specchiata (sembra un'altra inquadratura).
        riusi = {}
        fonti = sorted(_glob.glob(os.path.join(LAV, 'src_*.mp4')))
        for k, pth in enumerate(paths):
            if pth:
                continue
            p_k = os.path.join(LAV, f'pezzo_{k:04d}.mp4')
            def num(f): return int(re.search(r'src_(\d+)', f).group(1))
            cand = [f for f in fonti if abs(num(f) - k) >= 6] or fonti
            if cand:
                f = sorted(cand, key=lambda f: (riusi.get(f, 0), -abs(num(f) - k)))[0]
                riusi[f] = riusi.get(f, 0) + 1
                try:
                    ds = durata(f)
                except Exception:
                    ds = 0
                inizio = (ds * (0.5 if riusi[f] % 2 else 0.25)) if ds > piano[k]['d'] + 1 else 0.0
                try:
                    paths[k] = pezzo_video(p_k, piano[k]['d'], f, inizio, specchio=riusi[f] % 2 == 1)
                    log(f'pezzo {k}: nessuna clip coerente, riuso la clip {num(f)} (altro tratto, specchiata)')
                    continue
                except Exception as e:
                    log(f'pezzo {k}: riuso non riuscito', str(e)[:120])
            # ultima riserva (nessuna clip scaricata): il pezzo precedente, specchiato, non fermo
            prec = next((paths[j] for j in range(k - 1, -1, -1) if paths[j]), None) or next((x for x in paths if x), None)
            paths[k] = pezzo_video(p_k, piano[k]['d'], prec, 0.0, specchio=True)
            log(f'pezzo {k}: ATTENZIONE nessuna clip da riusare, ripeto il pezzo precedente specchiato')
        log(f"ricerche Pexels usate: {_conti['n']} (limite {PEXELS_MAX} l'ora, attesa {int(_conti.get('attesa', 0)) // 60} min); pezzi con clip riusata: {sum(riusi.values())}")
        log('pezzi pronti:', len(paths), 'in', int(time.time() - t0), 's')
        log(f"SPESA immagini: {SPESA['disegni']} immagini, circa {SPESA['fal']:.2f} $" + (f' (tetto {BUDGET:.2f} EUR a video)' if BUDGET else ''))
    video = os.path.join(LAV, 'muto.mp4')
    unisci([(p, v['d']) for p, v in zip(paths, piano)], video)
    video = applica_cornice(video, c)
    if LINEA_TEMPO:
        video = linea_del_tempo(video, c['scene'], durs)
    if REGIA and TAVOLE:
        video = ritocchi_scene(video, piano)
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
    if SUONI_CAMBIO or any(v.get('tipo') == 'pexels_foto' or v.get('scritta') for v in piano):   # click / swoosh / pop a ogni cambio immagine; scatto sulle foto
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
    if REGIA and TAVOLE and MUSICA_REGIA:   # musica da film scelta scena per scena (libreria comune)
        try:
            m_ = musica_scene(piano, voce_tot, durata(voce_tot))
            if m_:
                audio = m_; brani = []
        except Exception as e:
            log('musica da film non riuscita:', str(e)[:200])
    if brani:   # il PRIMO brano apre sempre il video, poi gli altri si alternano (2, 3, 4, 5, 2, 3...) fino alla fine, con dissolvenze
        try:
            tot = durata(voce_tot)
            vol = float(str(P.get('musica_volume') or P.get('musica_vol') or E('MUSICA_VOL', '') or .04).replace(',', '.').replace('%', ''))
            vol = vol / 100 if vol > 1 else vol   # 4 o 4% = 0.04
            file_b = []
            for n_, u_ in enumerate(brani):
                try:
                    f_ = scarica(u_, os.path.join(LAV, f'musica_{n_}.mp3'))
                    if durata(f_) > 20:
                        file_b.append(f_)
                except Exception as e:
                    log('brano saltato:', u_[-40:], str(e)[:80])
            if not file_b:
                raise RuntimeError('nessun brano scaricato')
            seq, somma, k_ = [file_b[0]], durata(file_b[0]), 0
            altri = file_b[1:] or file_b
            while somma < tot + 5 and len(seq) < 60:
                f_ = altri[k_ % len(altri)]; k_ += 1
                seq.append(f_); somma += durata(f_) - 3
            mf = os.path.join(LAV, 'musica_unita.m4a')
            if len(seq) == 1:
                run(['ffmpeg', '-y', '-v', 'error', '-i', seq[0], '-c:a', 'aac', '-b:a', '192k', mf])
            else:
                ins_ = sum((['-i', f_] for f_ in seq), [])
                fl_, prev = [], '[0:a]'
                for n_ in range(1, len(seq)):
                    out_ = f'[m{n_}]' if n_ < len(seq) - 1 else '[mus]'
                    fl_.append(f'{prev}[{n_}:a]acrossfade=d=3:c1=tri:c2=tri{out_}'); prev = out_
                run(['ffmpeg', '-y', '-v', 'error', *ins_, '-filter_complex', ';'.join(fl_), '-map', '[mus]', '-c:a', 'aac', '-b:a', '192k', mf])
            audio = os.path.join(LAV, 'audio.m4a')
            run(['ffmpeg', '-y', '-v', 'error', '-i', voce_tot, '-stream_loop', '-1', '-i', mf, '-filter_complex',
                 f'[1:a]volume={vol},afade=t=in:d=2,afade=t=out:st={max(0, tot - 4):.2f}:d=4[m];'
                 f'[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]', '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', audio])
            log(f'musica: apertura + {len(seq) - 1} brani a rotazione ({len(file_b)} brani diversi), volume {vol}')
        except Exception as e:
            log('musica saltata:', e)
    finale = os.path.join(ROOT, 'video_storia.mp4')
    if not iscrizione(video, audio, finale):
        run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'copy', '-shortest', finale])
    if ALTA_RIS:   # 2560x1440: YouTube usa una compressione migliore e il video si vede piu' nitido a tutti
        try:
            alto = finale[:-4] + '_1440.mp4'
            run(['ffmpeg', '-y', '-v', 'error', '-i', finale, '-vf', 'scale=2560:1440:flags=lanczos', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17',
                 '-pix_fmt', 'yuv420p', '-c:a', 'copy', alto])
            os.replace(alto, finale); log('video finale a 1440p')
        except Exception as e:
            log('1440p non riuscito, resta 1080p:', str(e)[:150])
    cop = copertina(comp, c) if COP_VIDEO else None
    if COP_STILE == 'foto':   # copertina_stile = foto: pannello con il nome del paese + foto SIMBOLO da Pexels controllata da Claude (stile A3a, 30 ott)
        try:
            import copertina_foto as CF
            CF.log = log
            cop = CF.crea(titolo_finale, LINGUA, os.path.join(ROOT, 'copertina.jpg'),
                          f"Periodo raccontato: {c.get('date') or ''}. Paese: {c.get('titolo_mappa') or c.get('paese_mappa') or ''}.")
            if cop:
                log('copertina foto pronta: copertina.jpg')
        except Exception as e:
            log('copertina foto non riuscita:', str(e)[:200]); cop = None
    if COP_STILE == 'foto' and cop:
        pass
    elif str(P.get('copertina_formato') or '').strip().lower() == 'primo_piano':   # stile Faces of Rome
        cop = copertina_primo_piano(comp, c)
    elif not COP_VIDEO:   # copertina UFFICIALE (bandiera + figura): fatta qui, prima del caricamento, e caricata insieme al video
        try:
            dir_cop = os.path.join(ROOT, 'copertine_storia')
            env = dict(os.environ, TITOLO_PROVA=titolo_finale, COPERTINA_FORMATO=str(P.get('copertina_formato') or 'coppia'))
            subprocess.run([sys.executable, os.path.join(ROOT, 'copertine_storia.py')], env=env, cwd=ROOT, timeout=900)
            src_ = os.path.join(dir_cop, 'prova_1.jpg')
            if os.path.exists(src_):
                cop = os.path.join(ROOT, 'copertina.jpg'); shutil.copy(src_, cop)
                log('copertina ufficiale pronta: copertina.jpg')
            else:
                log('copertina ufficiale NON creata: la fara\' Copertine Storia al prossimo giro')
        except Exception as e:
            log('copertina ufficiale non riuscita:', str(e)[:150])
    open(os.path.join(ROOT, 'titolo.txt'), 'w').write(titolo_finale)
    prepara_extra(c, titolo_finale, finale, cop)
    corto = durata(finale) < MIN_SEC_YT   # video di prova (1 minuto): MAI su YouTube, resta solo su Drive
    if CARICA and corto:
        log(f'video di {durata(finale):.0f} secondi (sotto {MIN_SEC_YT} s): e\' una prova, NON lo carico su YouTube')
    if CARICA and not corto:
        t0c = time.time()
        vid = carica_youtube(finale, c, titolo_finale)
        note = [x for x in (carica_copertina(vid, cop), playlist_video(vid, titolo_finale)) if x]
        if cop and not COP_VIDEO:   # la copertina diventa quella del video: il Rotatore CTR la trova, Copertine Storia non la rifa'
            try:
                import csv as _csv
                dir_cop = os.path.join(ROOT, 'copertine_storia')
                shutil.copy(cop, os.path.join(dir_cop, f'{vid}_1.jpg'))
                inf_p = os.path.join(dir_cop, 'prova_info.json')
                tipi = ['uomo', 'donna']
                if os.path.exists(inf_p):
                    shutil.copy(inf_p, os.path.join(dir_cop, f'{vid}_info.json'))
                    tipi = (json.load(open(inf_p)).get('tipi') or tipi)
                reg = os.path.join(dir_cop, 'registro_copertine.csv'); nuovo = not os.path.exists(reg)
                with open(reg, 'a', newline='', encoding='utf-8') as f_:
                    w_ = _csv.writer(f_)
                    if nuovo:
                        w_.writerow(['data', 'video', 'tipo_1', 'tipo_2'])
                    w_.writerow([time.strftime('%Y-%m-%d'), vid, tipi[0], tipi[1]])
                for x in ('prova_1.jpg', 'prova_info.json'):
                    if os.path.exists(os.path.join(dir_cop, x)):
                        os.remove(os.path.join(dir_cop, x))
                log('copertina ufficiale', 'CARICATA' if not any('copertina' in n for n in note) else 'NON caricata', 'e registrata:', f'copertine_storia/{vid}_1.jpg', '| parte con:', tipi[0])
            except Exception as e:
                log('registro copertina non riuscito:', str(e)[:150])
        avvisa({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'titolo': titolo_finale,
                'testo_copertina': str((c.get('copertina') or {}).get('testo') or ''), 'pubblica_il': P.get('pubblica_il') or '',
                'minuti_video': round(durata(finale) / 60, 1), 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1),
                'errore': '; '.join(note)})
    elif P.get('id'):
        avvisa({'stato': 'PROVA OK' if (PROVA or corto) else 'CREATO', 'minuti_video': round(durata(finale) / 60, 1),
                'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1), 'titolo': titolo_finale})
    open(os.path.join(ROOT, 'personaggi_mancanti.txt'), 'w').write('\n'.join(sorted(set(m for m in mancanti if m))))
    log('FATTO:', finale, round(durata(finale) / 60, 1), 'minuti')
    try:
        log(CO.testo())
    except Exception:
        pass


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
        run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', fl, '-map', '[v]', '-map', amap, *ENC, '-s', '2560x1440', '-sws_flags', 'lanczos', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-shortest', finale])
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
    descr, tags_ = dati_youtube(c, titolo)
    snippet = {'title': titolo[:100], 'description': descr, 'tags': tags_,
               'categoryId': str(c.get('categoria_originale') or P.get('categoria') or '27'), 'defaultLanguage': LINGUA, 'defaultAudioLanguage': LINGUA}
    status = {'privacyStatus': P.get('privacy') or 'public', 'selfDeclaredMadeForKids': False}
    if P.get('pubblica_il') and str(P.get('privacy') or 'public').strip().lower() == 'public':   # private o unlisted: niente programmazione   # privacy private = resta privato, si pubblica a mano
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
    try:
        h = {'Authorization': 'Bearer ' + token()}
        tutte = http('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50', headers=h).get('items', [])
        esistenti = {it['snippet']['title'].strip().lower(): it['id'] for it in tutte}
        if not scelte:
            argomenti = [x.strip() for x in re.split(r'[,;|\n]', str(P.get('playlist_topics') or '')) if x.strip()]
            chiave = E('ANTHROPIC_API_KEY', '')
            if not argomenti or not chiave:
                return ''
            r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO_CONTROLLO, 'max_tokens': 60, 'messages': [{'role': 'user', 'content':
                     f'Video title: "{titolo}".\nAllowed playlist names: {json.dumps(argomenti, ensure_ascii=False)}\n'
                     'Answer ONLY with the ONE playlist name from the list that best fits the video, exactly as written.'}]},
                     {'x-api-key': chiave, 'anthropic-version': '2023-06-01'}, timeout=60)
            nome = ''.join(b.get('text', '') for b in r.get('content', [])).strip().split('\n')[0].strip(' ."\'')
            nome = next((a for a in argomenti if a.lower() == nome.lower()), argomenti[0])
            scelte = [nome[:150]]
            log('playlist scelta:', nome)
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


EXTRA = {}   # descrizione, tag, playlist, link a video e copertina: per il foglio (caricamento a mano possibile)


def carica_fal(path, tipo='video/mp4'):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    dim = os.path.getsize(path)
    base = 'https://rest.alpha.fal.ai/storage/upload/'
    corpo = {'content_type': tipo, 'file_name': os.path.basename(path)}
    if dim <= 90 * 1024 * 1024:
        ini = http(base + 'initiate?storage_type=fal-cdn-v3', corpo, h)
        with open(path, 'rb') as f:
            req = urllib.request.Request(ini['upload_url'], data=f.read(), method='PUT', headers={'Content-Type': tipo})
        with urllib.request.urlopen(req, timeout=1800):
            pass
        return ini['file_url']
    ini = http(base + 'initiate-multipart?storage_type=fal-cdn-v3', corpo, h)
    u = urllib.parse.urlsplit(ini['upload_url'])
    radice, coda = f'{u.scheme}://{u.netloc}{u.path}', ('?' + u.query) if u.query else ''
    pezzo, parti = 10 * 1024 * 1024, []
    with open(path, 'rb') as f:
        n = 0
        while True:
            dati = f.read(pezzo)
            if not dati:
                break
            n += 1
            for tent in range(4):
                try:
                    req = urllib.request.Request(f'{radice}/{n}{coda}', data=dati, method='PUT')
                    with urllib.request.urlopen(req, timeout=600) as r:
                        testo = r.read().decode() or '{}'
                        try:
                            etag = json.loads(testo).get('etag')
                        except Exception:
                            etag = None
                        etag = etag or r.headers.get('ETag') or r.headers.get('etag')
                    if not etag:
                        raise RuntimeError('nessun etag')
                    parti.append({'partNumber': n, 'etag': etag}); break
                except Exception as e:
                    if tent == 3:
                        raise
                    log(f'pezzo {n} non caricato ({str(e)[:80]}), riprovo'); time.sleep(5 * (tent + 1))
    http(f'{radice}/complete{coda}', {'parts': parti})
    return ini['file_url']



def dati_youtube(c, titolo):
    descr = '\n\n'.join(x for x in [titolo, str(c.get('descrizione') or '').strip(), str(c.get('capitoli_testo') or '').strip(),
                                     str(P.get('descrizione_base') or '').strip()] if x)
    return descr[:4900], lista_tag(titolo, c.get('tag'))


def nomi_playlist(titolo):
    scelte = []
    for r in [x.strip() for x in str(P.get('playlist') or '').split('||') if x.strip()]:
        nome, _, parole = r.partition(':')
        lista = [w.strip().lower() for w in parole.split(',') if w.strip()]
        if nome.strip() and (not lista or any(w in titolo.lower() for w in lista)):
            scelte.append(nome.strip()[:150])
    return scelte


def prepara_extra(c, titolo, video, cop):
    """Riempie EXTRA: testi per il caricamento a mano + video e copertina su fal (n8n li salva nelle cartelle Drive del canale)."""
    try:
        descr, tags = dati_youtube(c, titolo)
        EXTRA.update(descrizione=descr, tag=', '.join(tags), playlist=' || '.join(nomi_playlist(titolo)),
                     cartella_video=str(P.get('cartella_video') or ''), cartella_copertine=str(P.get('cartella_copertine') or ''))
    except Exception as e:
        log('testi per il foglio non pronti:', str(e)[:150])
    if not E('FAL_KEY'):
        return
    for chiave, path, tipo in (('video_url', video, 'video/mp4'), ('copertina_url', cop, 'image/jpeg')):
        try:
            if path and os.path.exists(path):
                EXTRA[chiave] = carica_fal(path, tipo); log(chiave, 'pronto per Drive')
        except Exception as e:
            log(chiave, 'non caricato su fal:', str(e)[:150])


def avvisa(esito):
    if esito.get('stato') in ('PUBBLICATO', 'CREATO', 'PROVA OK'):
        for k_, v_ in EXTRA.items():
            esito.setdefault(k_, v_)
    for k, v in INFO_COMP.items():
        if v and k not in esito:
            esito[k] = v
    log('esito:', json.dumps(esito, ensure_ascii=False)[:500])
    if not P.get('callback_url'):
        return
    for k in range(3):
        try:
            http(P['callback_url'], {'id': P.get('id'), 'foglio': P.get('foglio', ''), 'gid': P.get('gid', ''), **esito}); return
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
