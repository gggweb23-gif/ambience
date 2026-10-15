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
import json, math, os, random, re, shutil, subprocess, sys, threading, time, traceback, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 24
T_TR = 0.2                                   # durata transizione a scatto (xfade hblur)
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

REGIA VISIVA: ogni scena (20-40 parole di voce) ha 2-4 "visivi" che cambiano ogni ~3 secondi. Tipi:
- "cartone": scena disegnata. Campi: "sfondo" (id di uno dei 6 sfondi), "personaggio" (SOLO uno di questa lista, oppure "" per nessuno): {', '.join(kit) or '(nessuno)'}; "reazione": true se a meta' il personaggio cambia posa (momento forte). Nella PRIMA scena il primo visivo e' un cartone con il campo "data" (es. "550 a.C.").
- "pexels_video": clip vera. Campo "q": ricerca Pexels in INGLESE, 2-4 parole concrete che diano immagini SENZA cose moderne: paesaggi naturali, montagne, deserti, rovine, monumenti antichi, oggetti antichi, monete, manoscritti, fuoco, cielo, mare, rievocazioni in costume. MAI persone di oggi, MAI citta' moderne (tranne nelle scene sul presente), MAI nomi di persone o eventi.
- "pexels_foto": foto vera. Campo "q" come sopra.
- "carta": frase chiave scritta su carta. Campo "testo": max 8 parole, la frase piu' forte del momento.
- "scheda": presentazione di un personaggio storico. Campi "personaggio" (dalla lista) e "nome" (nome vero completo).
- "mappa": zoom sulla mappa del paese con titolo e date (usala UNA volta, nella seconda scena).
Proporzioni su tutto il video: circa 35% cartone, 30% pexels_video, 15% pexels_foto, 15% carta, 5% scheda+mappa. Mai due visivi uguali di fila.

SFONDI: definisci esattamente 6 sfondi a cartone (luoghi ed epoche chiave del paese, SENZA persone). Ogni sfondo: "id" (s1..s6) e "prompt_en" (descrizione in inglese del luogo e dell'epoca, 20-35 parole).

Rispondi SOLO con un JSON valido, senza testo prima o dopo:
{{"titolo": "...", "titolo_mappa": "nome del paese da scrivere sulla mappa, nella lingua del canale, es. IRAN", "paese_mappa": "nome del paese in inglese come in Natural Earth (es. Iran, India, Egypt, United States of America)",
 "date": "es. 550 a.C. – 2026", "texture": "pergamena|washi|stropicciata|giornale|papiro", "font_carte": "classico|gotico|macchina",
 "sfondi": [{{"id": "s1", "prompt_en": "..."}}],
 "scene": [{{"testo": "parlato della scena", "visivi": [{{"tipo": "cartone", "sfondo": "s1", "personaggio": "...", "reazione": true, "data": "..."}}]}}],
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
            b = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
                     {'text': testo, 'model_id': E('VOCE_MODELLO', 'eleven_multilingual_v2'),
                      'voice_settings': {'stability': .5, 'similarity_boost': .75}},
                     {'xi-api-key': chiave, 'accept': 'audio/mpeg'}, raw=True)
            open(p, 'wb').write(b)
            return p
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(4 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


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
def font(nome, size):
    f = {'gara': 'EBGaramond-SemiBold.ttf', 'titolo': 'LuckiestGuy.ttf', 'gotico': 'UnifrakturMaguntia.ttf',
         'macchina': 'SpecialElite.ttf', 'classico': 'EBGaramond-SemiBold.ttf'}.get(nome, 'EBGaramond-SemiBold.ttf')
    return ImageFont.truetype(os.path.join(FONT, f), size)


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


def pezzo_carta(path, d, testo, tex, nome_font):
    sz = 96
    while True:
        f = font(nome_font, sz); righe = a_capo(testo, f, 1500)
        if len(righe) <= 3 or sz <= 60: break
        sz -= 6
    tot = len(testo); dur_batt = min(2.0, .045 * tot)

    def disegna(t):
        n = tot if t >= .3 + dur_batt else int(clamp((t - .3) / dur_batt) * tot)

        def fn():
            im = tex.copy(); dr = ImageDraw.Draw(im); resto = n
            y0 = H / 2 - len(righe) * sz * 1.25 / 2
            for k, r in enumerate(righe):
                vis = r[:max(0, resto)]; resto -= len(r) + 1
                x = (W - f.getlength(r)) / 2
                dr.text((x, y0 + k * sz * 1.25), vis, font=f, fill=INK)
            return im
        return n, fn
    return pipe_frames(path, d, disegna)


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


def pezzo_scheda(path, d, tex, nome_pg, nome):
    fp = png_personaggio(nome_pg, 'fermo')
    fig = Image.open(fp).convert('RGBA') if fp else None
    if fig:
        fig.thumbnail((900, 690)); ombra = fig.split()[3].filter(ImageFilter.GaussianBlur(10))
    f = font('gara', 86); tot = len(nome)

    def disegna(t):
        k = (min(12, int(t * 20)), int(clamp((t - .6) / .8) * tot))

        def fn():
            im = tex.copy()
            if fig:
                dy = int((1 - ease(min(t, .6) / .6)) * 40)
                x, y = (W - fig.width) // 2, 110 + dy
                im.paste((60, 40, 20), (x + 8, y + 12), ombra.point(lambda v: v * .35))
                im.paste(fig, (x, y), fig)
            n = k[1]; dr = ImageDraw.Draw(im)
            dr.text(((W - f.getlength(nome)) / 2, 860), nome[:n], font=f, fill=INK)
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
    """pezzi = [(path, durata)], ogni durata include gia' T_TR in piu' (tranne l'ultimo). Catena xfade hblur a blocchi."""
    def catena(lista, dest):
        if len(lista) == 1:
            shutil.copy(lista[0][0], dest); return lista[0][1]
        ins, fl, lun = [], [], lista[0][1]
        for p, _ in lista: ins += ['-i', p]
        prec = '0:v'
        for k in range(1, len(lista)):
            off = lun - T_TR
            fl.append(f'[{prec}][{k}:v]xfade=transition=hblur:duration={T_TR}:offset={off:.3f}[x{k}]')
            prec = f'x{k}'; lun = off + lista[k][1]
        run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', ';'.join(fl), '-map', f'[{prec}]', *ENC, dest])
        return lun
    blocchi, n = [], 0
    for i in range(0, len(pezzi), 14):
        dest = os.path.join(LAV, f'blocco_{n:03d}.mp4'); n += 1
        blocchi.append((dest, catena(pezzi[i:i + 14], dest)))
    log('blocchi uniti:', len(blocchi))
    while len(blocchi) > 1:
        nuovi = []
        for i in range(0, len(blocchi), 10):
            dest = os.path.join(LAV, f'blocco_{n:03d}.mp4'); n += 1
            nuovi.append((dest, catena(blocchi[i:i + 10], dest)))
        blocchi = nuovi
    shutil.copy(blocchi[0][0], out)
    return blocchi[0][1]


# ============================================================ MAIN
PESO = {'cartone': 1.6, 'mappa': 3.0, 'scheda': 1.3, 'carta': 1.2, 'pexels_video': 1.0, 'pexels_foto': 1.0}


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
    nome_font = {'gotico': 'gotico', 'macchina': 'macchina'}.get(c.get('font_carte'), 'gara')
    # piano dei pezzi
    piano = []
    for i, (s, D) in enumerate(zip(c['scene'], durs)):
        vis = [v for v in (s.get('visivi') or []) if v.get('tipo') in PESO] or [{'tipo': 'cartone', 'sfondo': random.choice(list(sf))}]
        tot = sum(PESO[v['tipo']] for v in vis)
        for v in vis:
            piano.append(dict(v, d=D * PESO[v['tipo']] / tot, contesto=s['testo']))
    lati = 0
    for k, v in enumerate(piano):
        v['d'] = v['d'] + (T_TR if k < len(piano) - 1 else 0)
        if v.get('personaggio') and v['personaggio'] not in kit:
            mancanti.append(v['personaggio']); v['personaggio'] = ''

    def fai(k):
        v = piano[k]; d = v['d']; p = os.path.join(LAV, f'pezzo_{k:04d}.mp4'); t = v['tipo']
        try:
            if t in ('pexels_video', 'pexels_foto'):
                u = pexels('video' if t == 'pexels_video' else 'foto', v.get('q') or 'ancient ruins', v.get('contesto') or '')
                if not u:
                    raise RuntimeError('nessun risultato Pexels per ' + str(v.get('q')))
                src = os.path.join(LAV, f'src_{k:04d}' + ('.mp4' if t == 'pexels_video' else '.jpg'))
                scarica(u, src)
                return pezzo_video(p, d, src) if t == 'pexels_video' else pezzo_foto(p, d, src)
            if t == 'carta':
                return pezzo_carta(p, d, v.get('testo') or '', tex, nome_font)
            if t == 'scheda':
                return pezzo_scheda(p, d, tex, v.get('personaggio') or '', v.get('nome') or '')
            if t == 'mappa':
                return pezzo_mappa(p, d, c.get('paese_mappa') or '', c.get('titolo_mappa') or TITOLO.split()[-1], c.get('date') or '')
            return pezzo_cartone(p, d, sf.get(v.get('sfondo')) or list(sf.values())[k % len(sf)], v.get('personaggio') or '',
                                 bool(v.get('reazione')), v.get('data') or '', k % 2 == 0)
        except Exception as e:   # riserva: cartone senza personaggio, il video non si ferma mai
            log('pezzo', k, t, 'sostituito:', str(e)[:200])
            return pezzo_cartone(p, d, list(sf.values())[k % len(sf)], '', False, '', True)
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
