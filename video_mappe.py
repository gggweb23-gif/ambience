#!/usr/bin/env python3
"""
MULTICHANNEL - "Video Mappe" (canale RICH BORDERS, stile Fortune of Nations / Ziro History).
Dal link del video competitor al video finito, tutto in codice (nessuna immagine AI):
  1) testo originale del competitor (RapidAPI)       4) mappa in rilievo Natural Earth + paesi colorati + icone + Pin
  2) copione nuovo + regia mappa (Claude, in inglese)  5) suoni: whoosh morbidi, pop sulle icone, tappeto bassissimo
  3) voce scena per scena (ElevenLabs, con i tempi)    6) copertina in codice + caricamento su YouTube (facoltativo)
Variabili: LINK_COMPETITOR, PROVA (SI = ~1 minuto), CARICA, VOCE, MIN_MINUTI, MAX_MINUTI, MODELLO_AI, MUSICA_URL, PAYLOAD (da n8n)
Chiavi: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, RAPIDAPI_KEY (+ YT_* per caricare)
Stile RICH BORDERS (fisso, uguale in tutti i video): oro = paese ricco, blu-verde = l'altro; cartellini blu notte con linea rossa;
Pin (puntina rossa con gli occhi) che salta sulla mappa; "numero del video" all'inizio e alla fine; tre note di firma;
nuvole SOLO nei cambi d'epoca (oggi <-> carta antica), senza whoosh.
"""
import base64, io, json, math, os, re, shutil, subprocess, sys, time, traceback, urllib.error, urllib.parse, urllib.request, wave
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 24
ROOT = os.getcwd()
LAV = os.path.join(ROOT, 'lavoro_mappe')
RIS = os.path.join(ROOT, 'risorse_mappe')          # mappa, confini, font e icone (scaricati dal workflow)
E = os.environ.get
try:
    P = json.loads(E('PAYLOAD') or '{}') or {}
except Exception:
    P = {}
LINK = str(P.get('link') or E('LINK_COMPETITOR', '')).strip()
PROVA = str(P.get('prova') or E('PROVA', 'NO')).strip().upper() == 'SI'
CARICA = str(P.get('carica') or E('CARICA', 'NO')).strip().upper() == 'SI' and not PROVA
VOCE = str(P.get('voce') or E('VOCE', '') or 'pNInz6obpgDQGcFmaJgB').strip()
VOCE_VELOCITA = max(.8, min(1.2, float(str(P.get('voce_velocita') or E('VOCE_VELOCITA', '') or 1.0).replace(',', '.'))))
MIN_MINUTI = float(str(P.get('min_minuti') or E('MIN_MINUTI', '') or 10).replace(',', '.'))
MAX_MINUTI = float(str(P.get('max_minuti') or E('MAX_MINUTI', '') or 14).replace(',', '.'))
MODELLO_AI = str(P.get('modello_ai') or E('MODELLO_AI', '') or 'claude-sonnet-5-5').strip()
MUSICA_URL = str(P.get('musica_url') or E('MUSICA_URL', '')).strip()
MUSICA_VOL = float(str(P.get('musica_volume') or E('MUSICA_VOL', '') or .04).replace(',', '.'))
SLOGAN = str(P.get('slogan') or E('SLOGAN', '') or 'EVERY BORDER HAS A PRICE.').strip()
NOME_CANALE = str(P.get('canale_nome') or E('NOME_CANALE', '') or 'RICH BORDERS').strip().upper()
MIN_SEC_YT = 480                                    # sotto gli 8 minuti (le prove) mai su YouTube
PPM = 150                                           # parole al minuto della voce inglese (stima per la lunghezza del copione)

NAVY, ROSSO, CREMA, ORO, VERDE = (16, 30, 62), (222, 44, 52), (250, 242, 222), (246, 196, 44), (40, 160, 170)
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
T_INIZIO = time.time()


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
    """I modelli 5.x ragionano e il ragionamento consuma max_tokens: qui si limita (stessa regola di video_storia.py)."""
    m = str(data.get('model') or '')
    if 'thinking' in data or not re.search(r'(sonnet|opus|haiku|fable|mythos)-5', m):
        return data
    d = dict(data)
    if 'sonnet-5-5' in m:
        d['thinking'] = {'type': 'between_tools'}; d['output_config'] = {'effort': 'medium'}
    elif 'opus-5-5' in m or 'fable' in m or 'mythos' in m:
        d['output_config'] = {'effort': 'low'}
    else:
        d['thinking'] = {'type': 'disabled'}; d['output_config'] = {'effort': 'medium'}
    return d


def http(url, data=None, headers=None, metodo=None, timeout=180, raw=False):
    if isinstance(data, dict) and 'api.anthropic.com' in url:
        data = senza_ragionamento(data)
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=metodo), timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def scarica(url, path, tentativi=4):
    for k in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=180) as r, open(path, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if os.path.getsize(path) > 200:
                return path
        except Exception as e:
            log('download fallito', str(e)[:120]); time.sleep(3 * (k + 1))
    raise RuntimeError('impossibile scaricare ' + url)


# ============================================================ 0) VIDEO DEL COMPETITOR
def id_video(link):
    m = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})', link or '')
    return m.group(1) if m else ''


def competitor():
    vid = id_video(LINK)
    if not vid:
        raise RuntimeError('STOP: manca il link del video competitor. Nessun video creato, nessun costo.')
    c = {'id': vid, 'copertina': f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'}
    try:
        c['titolo'] = http('https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=' + vid)['title']
    except Exception as e:
        log('titolo originale non letto:', str(e)[:100])
    chiave = E('RAPIDAPI_KEY', '')
    for k in range(3 if chiave else 0):
        try:
            j = http('https://youtube-transcript3.p.rapidapi.com/api/transcript?videoId=' + vid,
                     headers={'X-RapidAPI-Key': chiave, 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com'}, timeout=120)
            righe = j.get('transcript') or []
            testo = ' '.join(str(r.get('text', '')) for r in righe) if isinstance(righe, list) else str(righe)
            testo = re.sub(r'\s+', ' ', re.sub(r'\[(?:Music|Applause)\]', ' ', testo)).strip()
            if len(testo.split()) > 50:
                c['testo'] = testo; log('testo originale:', len(testo.split()), 'parole (RapidAPI)')
                return c
            log('RapidAPI: trascrizione vuota', json.dumps(j)[:200])
        except Exception as e:
            log('RapidAPI non riuscito:', str(e)[:150]); time.sleep(5)
    raise RuntimeError('STOP: testo del video competitor non leggibile (RapidAPI). Nessun video creato, nessun costo per la voce.')


# ============================================================ 1) COPIONE + REGIA (Claude)
ICONE = {'bell': '1f514',    # nome usato da Claude -> codice Twemoji (icone gratuite CC-BY; in futuro: libreria 3D fatta una volta)
    'gold': '1fa99', 'coin': '1fa99', 'silver': '1fa99', 'money': '1f4b0', 'cash': '1f4b5', 'bank': '1f3e6', 'ship': '1f6a2', 'sailboat': '26f5',
    'crown': '1f451', 'chains': '26d3', 'mine': '26cf', 'farm': '1f33e', 'house': '1f3e0', 'factory': '1f3ed', 'oil': '1f6e2', 'train': '1f686',
    'car': '1f697', 'plane': '2708', 'chart_up': '1f4c8', 'chart_down': '1f4c9', 'people': '1f465', 'soldier': '1f482', 'sword': '2694',
    'gun': '1f52b', 'bomb': '1f4a3', 'fire': '1f525', 'skull': '1f480', 'church': '26ea', 'school': '1f3eb', 'hospital': '1f3e5',
    'city': '1f3d9', 'mountain': '26f0', 'volcano': '1f30b', 'desert': '1f3dc', 'island': '1f3dd', 'river': '1f30a', 'tree': '1f333',
    'sugar': '1f36c', 'coffee': '2615', 'banana': '1f34c', 'corn': '1f33d', 'cotton': '2601', 'tobacco': '1f6ac', 'fish': '1f41f',
    'cow': '1f404', 'horse': '1f40e', 'diamond': '1f48e', 'computer': '1f4bb', 'phone': '1f4f1', 'container': '1f4e6', 'scroll': '1f4dc',
    'law': '2696', 'vote': '1f5f3', 'handshake': '1f91d', 'question': '2753', 'warning': '26a0', 'clock': '23f0', 'lightbulb': '1f4a1',
    'pyramid': '1f53a', 'temple': '1f6d5', 'castle': '1f3f0', 'tent': '26fa', 'dollar': '1f4b2', 'euro': '1f4b6', 'tax': '1f9fe',
}


def bandiera(iso2):
    iso2 = str(iso2 or '').strip().upper()
    if not re.match(r'^[A-Z]{2}$', iso2):
        return ''
    return '-'.join('%x' % (0x1F1E6 + ord(ch) - 65) for ch in iso2)


def claude(prompt, max_tokens=32000):
    chiave = E('ANTHROPIC_API_KEY', '')
    req = urllib.request.Request('https://api.anthropic.com/v1/messages',
                                 data=json.dumps(dict(senza_ragionamento({'model': MODELLO_AI, 'max_tokens': max_tokens,
                                                                          'messages': [{'role': 'user', 'content': prompt}]}), stream=True)).encode(),
                                 headers={'content-type': 'application/json', 'x-api-key': chiave, 'anthropic-version': '2023-06-01'})
    pezzi = []
    with urllib.request.urlopen(req, timeout=900) as r:
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
            elif ev.get('type') == 'error':
                raise RuntimeError('Claude: ' + json.dumps(ev.get('error'))[:200])
    return ''.join(pezzi)


def copione(comp):
    orig = comp['testo']
    if PROVA:
        orig = ' '.join(orig.split()[:200])
    parole = 170 if PROVA else int(min(MAX_MINUTI * PPM, max(MIN_MINUTI * PPM, len(orig.split()) * 1.0)))
    n_scene = max(8, round(parole / 20))
    icone = ', '.join(sorted(ICONE))
    prompt = f"""You write videos for the YouTube channel RICH BORDERS ("Every border has a price."): economic history and geopolitics explained with ANIMATED MAPS, in the style of the channel "Fortune of Nations".

ORIGINAL VIDEO TO COPY (title: "{comp.get('titolo') or ''}"). Keep ~80% of it: the SAME topic, the same story structure, the same facts, numbers and examples, the same hook.
Rewrite EVERYTHING in your own words (never copy sentences: YouTube penalizes reused content). Add ~20% of our own: one extra striking comparison or number, and clearer explanations.
ORIGINAL TRANSCRIPT:
\"\"\"{orig[:45000]}\"\"\"

WRITE: an English (US) narration of about {parole} words, split into about {n_scene} scenes of 15-25 words each (1-2 short sentences).
Tone: curious, punchy, simple words, short sentences, questions that create suspense. The first scene is a strong hook (a paradox or a shocking number). No greeting, no "in this video". End with a one-sentence takeaway.
Narration must be easy to read aloud: write numbers as people say them ("eight times", "300 years", "1700"), never use symbols like × or %.
Use only facts you are confident are true; round numbers are fine ("about", "almost").

For EVERY scene you also direct the MAP (equirectangular world map with shaded relief):
- "vista": camera {{"lon": center longitude, "lat": center latitude, "larghezza": degrees of longitude visible (8 = one small country, 30 = a region, 120 = a continent, 300 = whole world)}}. Change it often (zoom in / out / pan), like a documentary.
- "epoca": "oggi" (modern colored map) or "antica" (old parchment map: use it for events before ~1900). Do not switch epoch more than 4 times in the whole video.
- "oro": ISO-3 codes of the country/countries that are the "rich / winner / focus" side (painted gold, raised in 3D). "verde": ISO-3 codes of the other side (painted blue-green). Max 25 codes each. Can be empty.
- "eventi": something new must appear on screen every 2-3 seconds: put ONE event every 4-5 words of the scene (usually 3-6 per scene), each tied to a different WORD of the scene, spread from the beginning to the end of the scene ("parola" = one exact word that appears in that scene's text; the event appears when the voice says it). The camera automatically zooms on each event that has a location, so give most events a precise lon/lat.
  Every scene must contain at least ONE moving element (freccia, confine, colonna, barre) or a NEW place (icona/etichetta) — never two scenes in a row with only labels.
  An "anno" card must show exactly the year said in that scene (if the text says "300 years ago", write the year that means). Types:
  {{"tipo":"icona","icona": one of [{icone}] or "flag:XX" (ISO-2 country code),"lon":..,"lat":..,"parola":".."}}
  {{"tipo":"etichetta","testo":"SHORT CAPS LABEL (max 4 words)","lon":..,"lat":..,"parola":".."}}
  {{"tipo":"anno","testo":"1700","parola":".."}}   (year card, top-left)
  {{"tipo":"numero","testo":"x8" or "$3 TRILLION" or "109M" (max 12 chars),"lon":..,"lat":..,"parola":".."}}
  {{"tipo":"colonna","testo":"MEXICO","valore":0.1-1.0,"lon":..,"lat":..,"parola":".."}}   (golden column = wealth; use 2-3 in the same scene to compare)
  {{"tipo":"freccia","da":[lon,lat],"a":[lon,lat],"icona":"ship" (or another icon),"parola":".."}}   (route / migration / trade)
  {{"tipo":"contorno","paese":"ISO-3","parola":".."}}   (glowing outline of one country)
  {{"tipo":"confine","punti":[[lon,lat],[lon,lat],...],"parola":".."}}   (a red border/line drawn on the map)
  {{"tipo":"scritta","testo":"STRANGE?","parola":".."}}   (big word in the middle, max 2 words, use rarely)
  {{"tipo":"barre","titolo":"GDP PER PERSON","voci":[{{"testo":"USA","valore":82,"lato":"oro"}},{{"testo":"MEXICO","valore":14,"lato":"verde"}}],"parola":".."}}   (chart panel, max 4 bars, real numbers only)
  Coordinates must be REAL and well inside the "vista" of that scene (not on its edges).
- "pin": where Pin (our red map-pin mascot) stands: {{"lon":..,"lat":..,"faccia":"normale" or "stupito"}} (inside the vista, not covering the main event; "stupito" on shocking numbers).

ALSO WRITE:
- "titolo": YouTube title, same idea and structure as the original title (max 70 characters), Title Case.
- "numero": THE number of the video, shown big at the start and the end: {{"testo":"x8","sotto":"THE GAP BETWEEN TWO AMERICAS (max 6 words)"}}.
- "copertina": thumbnail like the original's idea: {{"testo":"WHY?" (1-3 words, CAPS),"oro":[ISO-3],"verde":[ISO-3],"vista":{{"lon":..,"lat":..,"larghezza":..}}}}.
- "descrizione": 2 short paragraphs for YouTube (no links, no hashtags).
- "tag": 12 YouTube tags.

Reply ONLY with valid JSON:
{{"titolo":"...","numero":{{...}},"copertina":{{...}},"descrizione":"...","tag":[...],"scene":[{{"testo":"...","vista":{{...}},"epoca":"oggi","oro":[],"verde":[],"eventi":[...],"pin":{{...}}}}]}}"""
    for k in range(3):
        try:
            t = claude(prompt)
            c = json.loads(t[t.find('{'): t.rfind('}') + 1])
            if not c.get('scene'):
                raise ValueError('copione senza scene')
            log('copione:', len(c['scene']), 'scene,', sum(len(str(s.get('testo', '')).split()) for s in c['scene']), 'parole')
            return c
        except Exception as e:
            log('copione non valido, riprovo:', str(e)[:200]); time.sleep(5)
    raise RuntimeError('copione non riuscito')


# ============================================================ 2) VOCE (ElevenLabs con i tempi di ogni lettera)
def voce(i, testo, prima='', dopo=''):
    p = os.path.join(LAV, f'voce_{i:03d}.mp3')
    if os.path.exists(p) and os.path.getsize(p) > 1000 and os.path.exists(p[:-4] + '.json'):
        return p
    chiave = E('ELEVENLABS_API_KEY', '')
    if not chiave:   # prova senza chiave: silenzio della durata giusta
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', max(1.5, len(testo.split()) / 2.5), p])
        json.dump({}, open(p[:-4] + '.json', 'w'))
        return p
    for k in range(4):
        try:
            j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_128',
                     {'text': testo, 'model_id': E('VOCE_MODELLO', 'eleven_multilingual_v2'), 'previous_text': prima[-400:], 'next_text': dopo[:400],
                      'voice_settings': {'stability': .5, 'similarity_boost': .75, 'speed': VOCE_VELOCITA}}, {'xi-api-key': chiave})
            open(p, 'wb').write(base64.b64decode(j['audio_base64']))
            json.dump(j.get('alignment') or {}, open(p[:-4] + '.json', 'w'))
            return p
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(4 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


def tempo_parola(testo, parola, al, dur):
    """Secondo (dentro la scena) in cui la voce dice 'parola'. Senza tempi: proporzionale alla posizione nel testo."""
    low = testo.lower(); w = str(parola or '').strip().lower()
    i = low.find(w) if w else -1
    if i < 0:
        return None
    try:
        st = al.get('character_start_times_seconds') or []
        if st and len(st) >= len(testo):
            return float(st[i])
    except Exception:
        pass
    return dur * i / max(1, len(testo))


# ============================================================ 3) MAPPA (rilievo Natural Earth + paesi + icone + Pin)
def ease(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)


def back(t):
    t = max(0.0, min(1.0, t)); c = 1.7; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


_R = {}   # risorse caricate una volta per processo


NOMI_CORTI = {'USA': 'USA', 'GBR': 'UK', 'RUS': 'RUSSIA', 'COD': 'DR CONGO', 'CAF': 'C. AFRICAN REP.', 'ARE': 'UAE', 'DOM': 'DOMINICAN REP.',
              'BIH': 'BOSNIA', 'KOR': 'SOUTH KOREA', 'PRK': 'NORTH KOREA', 'CZE': 'CZECHIA', 'SAU': 'SAUDI ARABIA'}


def risorse():
    if _R:
        return _R
    base = Image.open(os.path.join(RIS, 'shadedrelief.jpg')).convert('RGB')     # 10800 x 5400, 30 px per grado
    g = ImageOps.grayscale(base)
    sep = ImageEnhance.Contrast(ImageOps.colorize(g, black=(70, 50, 28), white=(242, 226, 192), mid=(190, 158, 108))).enhance(1.45)
    geo = json.load(open(os.path.join(RIS, 'paesi50.geojson')))['features']
    paesi, nomi = {}, {}
    for f in geo:
        p = f['properties']
        codici = {str(p.get(k) or '') for k in ('ADM0_A3', 'ISO_A3', 'SOV_A3', 'GU_A3')} - {'', '-99'}
        gm = f['geometry']; polys = gm['coordinates'] if gm['type'] == 'MultiPolygon' else [gm['coordinates']]
        anelli = [np.array(poly[0]) for poly in polys]
        if str(p.get('ADM0_A3')) == 'USA':   # Alaska e Hawaii restano, ma lontano dalla vista non costano: si tagliano nel disegno
            pass
        for cd in codici:
            paesi.setdefault(cd, []).extend(anelli)
            nm = str(p.get('NAME') or p.get('ADMIN') or '')
            nm = NOMI_CORTI.get(cd) or (nm if len(nm) <= 14 else str(p.get('ABBREV') or nm).replace('.', '') if len(str(p.get('ABBREV') or '')) > 4 else nm)
            nomi.setdefault(cd, nm)
    _R.update(base=base, sepia=sep, paesi=paesi, nomi=nomi, P=base.width / 360.0)
    return _R


def font(nome, s):
    return ImageFont.truetype(os.path.join(RIS, nome), max(2, int(s)))


_IC = {}


def icona(nome, size):
    nome = str(nome or '').strip().lower()
    code = bandiera(nome.split(':', 1)[1]) if nome.startswith('flag:') else ICONE.get(nome, '')
    if not code:
        code = ICONE['question']
    k = (code, size)
    if k in _IC:
        return _IC[k]
    import cairosvg
    path = os.path.join(RIS, 'tw', code + '.svg')
    if not os.path.exists(path):
        try:
            scarica(f'https://raw.githubusercontent.com/jdecked/twemoji/main/assets/svg/{code}.svg', path)
        except Exception:
            path = os.path.join(RIS, 'tw', ICONE['question'] + '.svg')
            if not os.path.exists(path):
                scarica(f"https://raw.githubusercontent.com/jdecked/twemoji/main/assets/svg/{ICONE['question']}.svg", path)
    im = Image.open(io.BytesIO(cairosvg.svg2png(url=path, output_width=size, output_height=size))).convert('RGBA')
    out = Image.new('RGBA', (size + 30, size + 30), (0, 0, 0, 0))
    om = Image.new('RGBA', im.size, (20, 20, 30, 255)); om.putalpha(im.split()[3].point(lambda v: int(v * .45)))
    out.paste(om, (18, 24), om); out = out.filter(ImageFilter.GaussianBlur(5)); out.paste(im, (9, 9), im)
    _IC[k] = out
    return out


def nuvola(w):
    h = int(w * .75); im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for cx, cy, r in ((.30, .58, .17), (.50, .45, .22), (.70, .57, .17), (.42, .62, .16), (.60, .63, .16)):
        d.ellipse([w * (cx - r), h * cy - w * r, w * (cx + r), h * cy + w * r], fill=(255, 255, 255, 255))
    im = im.filter(ImageFilter.GaussianBlur(w / 70))
    om = Image.new('RGBA', im.size, (110, 130, 165, 0))
    grad = Image.linear_gradient('L').resize(im.size).point(lambda v: int(max(0, v - 110) * .55))
    om.putalpha(Image.composite(grad, Image.new('L', im.size, 0), im.split()[3]))
    return Image.alpha_composite(im, om)


def camera(v):
    v = v or {}
    try:
        lon, lat, wd = float(v.get('lon', -40)), float(v.get('lat', 20)), float(v.get('larghezza', 120))
    except Exception:
        lon, lat, wd = -40.0, 20.0, 120.0
    wd = max(6.0, min(340.0, wd))
    hd = wd * H / W
    lat = max(-85 + hd / 2, min(85 - hd / 2, lat)) if hd < 170 else 0
    lon = max(-180 + wd / 2, min(180 - wd / 2, lon))
    return lon, lat, wd


def fondo(vista, sep_k):
    R = risorse(); Pg = R['P']
    cx, cy, wd = vista; cw = wd * Pg; ch = cw * H / W
    x0, y0 = (cx + 180) * Pg - cw / 2, (90 - cy) * Pg - ch / 2
    box = (int(x0), int(y0), int(x0 + cw), int(y0 + ch))
    im = R['base'].crop(box).resize((W, H), Image.BILINEAR, reducing_gap=2.0)
    if sep_k > 0.01:
        im = Image.blend(im, R['sepia'].crop(box).resize((W, H), Image.BILINEAR, reducing_gap=2.0), sep_k)
    pt = lambda lon, lat: (((lon + 180) * Pg - x0) * W / cw, ((90 - lat) * Pg - y0) * H / ch)
    return im, pt


def anelli_visibili(codici, pt):
    R = risorse(); out = []
    for cd in codici or []:
        for r in R['paesi'].get(str(cd).upper(), []):
            xy = [pt(lon, lat) for lon, lat in r]
            xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
            if max(xs) < -50 or min(xs) > W + 50 or max(ys) < -50 or min(ys) > H + 50:
                continue
            out.append(xy)
    return out


def riempi(im, base, polys, col, a, rilievo, cerchio=None):
    """Colora i paesi sul rilievo. cerchio=(x, y, r): il colore si ALLARGA dal punto (x, y) fino al raggio r."""
    if a <= 0.01 or not polys:
        return
    m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m)
    for xy in polys:
        dm.polygon(xy, fill=255)
    if cerchio is not None and cerchio[2] < 2400:
        c = Image.new('L', (W, H), 0); cx, cy, r = cerchio
        ImageDraw.Draw(c).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        m = ImageChops.multiply(m, c.filter(ImageFilter.GaussianBlur(18)))
    if rilievo > 0.5:
        sp = Image.new('L', (W, H), 0); ds = ImageDraw.Draw(sp)
        for xy in polys:
            ds.polygon([(x, y + rilievo) for x, y in xy], fill=int(255 * a))
        if cerchio is not None and cerchio[2] < 2400:
            sp = ImageChops.multiply(sp, c.filter(ImageFilter.GaussianBlur(18)))
        im.paste(Image.new('RGBA', (W, H), mix(col, (40, 20, 10), .5) + (255,)), (0, 0), sp)
    chiaro = ImageEnhance.Brightness(ImageOps.grayscale(base).convert('RGB')).enhance(1.35)
    im.paste(ImageChops.multiply(chiaro, Image.new('RGB', (W, H), col)).convert('RGBA'), (0, 0), m.point(lambda v: int(v * a)))
    d = ImageDraw.Draw(im)
    for xy in polys:
        d.line(xy + [xy[0]], fill=mix(col, (255, 255, 255), .55) + (int(200 * a),), width=2)


def etichetta(im, x, y, testo, k, fs=58, colore=None, blocca=True):
    if k <= 0:
        return
    s = back(k); f = font('Anton-Regular.ttf', fs * s); d = ImageDraw.Draw(im)
    w = d.textlength(testo, font=f) + 60 * s; h = fs * .82 * s
    if blocca:   # gli elementi della mappa invece escono dal quadro con la camera, non si ammucchiano sul bordo
        x = max(w / 2 + 10, min(W - w / 2 - 10, x)); y = max(h + 10, min(H - h - 10, y))
    d.rectangle([x - w / 2 + 5, y - h + 6, x + w / 2 + 5, y + h + 6], fill=(0, 0, 0))
    d.rectangle([x - w / 2, y - h, x + w / 2, y + h], fill=NAVY)
    d.rectangle([x - w / 2, y + h - 10 * s, x + w / 2, y + h], fill=ROSSO)
    d.text((x, y - 3 * s), testo, font=f, fill=colore or CREMA, anchor='mm')


def numero_grande(im, testo, sotto, k):
    if k <= 0:
        return
    d = ImageDraw.Draw(im); s = back(k)
    f = font('Anton-Regular.ttf', 220 * s); w = d.textlength(testo, font=f) + 120 * s
    x, y = W / 2, H / 2 - 40
    d.rectangle([x - w / 2 + 12, y - 140 * s + 14, x + w / 2 + 12, y + 140 * s + 14], fill=(0, 0, 0))
    d.rectangle([x - w / 2, y - 140 * s, x + w / 2, y + 140 * s], fill=NAVY)
    d.rectangle([x - w / 2, y + 140 * s - 20 * s, x + w / 2, y + 140 * s], fill=ROSSO)
    d.text((x, y - 12 * s), testo, font=f, fill=ORO, anchor='mm')
    if sotto:
        d.text((x, y + 190 * s), sotto.upper(), font=font('Anton-Regular.ttf', 52 * s), fill='white', anchor='mm', stroke_width=6, stroke_fill=NAVY)


def titolo_fascia(im, riga1, riga2, k):
    if k <= 0:
        return
    d = ImageDraw.Draw(im)
    for i, r in enumerate((riga1, riga2)):
        kk = back(min(1, k * 1.4 - i * .4))
        if kk <= 0 or not r:
            continue
        f = font('Anton-Regular.ttf', 84 * kk); y = 150 + i * 108; w = d.textlength(r, font=f)
        d.rectangle([W / 2 - w / 2 - 26, y - 52, W / 2 + w / 2 + 26, y + 52], fill=ORO if i == 0 else NAVY)
        d.text((W / 2, y), r, font=f, fill=NAVY if i == 0 else CREMA, anchor='mm')
        if i == 1:
            d.rectangle([W / 2 - w / 2 - 26, y + 43, W / 2 + w / 2 + 26, y + 52], fill=ROSSO)


def pin(im, x, y, sc=1.0, faccia='normale', salto=0.0):
    d = ImageDraw.Draw(im); r = 26 * sc
    d.ellipse([x - 16 * sc, y - 5 * sc, x + 16 * sc, y + 5 * sc], fill=(0, 0, 0, 90))
    y = y - salto; cy = y - 58 * sc
    d.polygon([(x - r * .82, cy + r * .55), (x + r * .82, cy + r * .55), (x, y)], fill=(178, 24, 34))
    d.ellipse([x - r, cy - r, x + r, cy + r], fill=ROSSO, outline=(150, 18, 28), width=max(1, int(2 * sc)))
    d.ellipse([x - r * .7, cy - r * .75, x - r * .2, cy - r * .3], fill=(255, 140, 140))
    oy = cy - r * .05
    for ex in (-.38, .38):
        rr = r * (.36 if faccia == 'stupito' else .3); pr = rr * .5
        d.ellipse([x + ex * r - rr, oy - rr, x + ex * r + rr, oy + rr], fill='white')
        d.ellipse([x + ex * r - pr, oy - pr + rr * .15, x + ex * r + pr, oy + pr + rr * .15], fill=(20, 20, 30))
    if faccia == 'stupito':
        d.ellipse([x - r * .16, cy + r * .4, x + r * .16, cy + r * .72], fill=(90, 10, 20))
    else:
        d.arc([x - r * .32, cy + r * .2, x + r * .32, cy + r * .66], 20, 160, fill=(90, 10, 20), width=max(2, int(3 * sc)))


def metti(im, ic, x, y, k=1.0):
    if k <= 0.02:
        return
    s = back(k); i = ic.resize((max(1, int(ic.width * s)), max(1, int(ic.height * s))))
    im.paste(i, (int(x - i.width / 2), int(y - i.height / 2)), i)


def colonna(im, x, y, h, col):
    d = ImageDraw.Draw(im); w = 64
    d.rectangle([x - w / 2, y - h, x + w / 2, y], fill=col)
    d.rectangle([x - w / 2, y - h, x - w / 2 + 16, y], fill=mix(col, (255, 255, 255), .35))
    d.rectangle([x + w / 2 - 14, y - h, x + w / 2, y], fill=mix(col, (0, 0, 0), .25))
    d.ellipse([x - w / 2, y - 14, x + w / 2, y + 14], fill=mix(col, (0, 0, 0), .25))
    d.ellipse([x - w / 2, y - h - 14, x + w / 2, y - h + 14], fill=mix(col, (255, 255, 255), .45))


def cartellino_anno(im, testo, k):
    if k <= 0:
        return
    d = ImageDraw.Draw(im); s = back(k); x, y = 70, 70
    d.rectangle([x + 8, y + 12, x + 8 + 330 * s, y + 12 + 170 * s], fill=(60, 45, 30))
    d.rectangle([x, y, x + 330 * s, y + 170 * s], fill=(245, 236, 214), outline=(120, 100, 70), width=4)
    d.text((x + 165 * s, y + 88 * s), testo, font=font('Poppins-Bold.ttf', 92 * s), fill=(70, 55, 40), anchor='mm')


def box_barre(n):
    """Riquadro del pannello barre con n voci (grande: deve leggersi bene anche da telefono)."""
    sp = 160 if n <= 3 else 135
    return (1000, 200, 1880, 200 + 175 + sp * n), sp


def pannello_barre(im, ev, k):
    if k <= 0:
        return
    voci = [v for v in (ev.get('voci') or []) if isinstance(v, dict)][:4]
    if not voci:
        return
    (x0, y0, x1, y1), sp = box_barre(len(voci))
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rectangle([x0, y0, x1, y1], fill=NAVY + (int(230 * k),)); od.rectangle([x0, y1 - 12, x1, y1], fill=ROSSO + (int(255 * k),))
    im.alpha_composite(ov); d = ImageDraw.Draw(im)
    d.text(((x0 + x1) / 2, y0 + 72), str(ev.get('titolo') or '').upper()[:26], font=font('Anton-Regular.ttf', 68), fill=CREMA, anchor='mm')
    mx = max(float(v.get('valore') or 0) for v in voci) or 1
    for i, v in enumerate(voci):
        y = y0 + 210 + i * sp; kb = ease(k * 1.6 - i * .2)
        val = float(v.get('valore') or 0); col = ORO if str(v.get('lato')) == 'oro' else VERDE
        d.text((x0 + 44, y - 58), str(v.get('testo') or '').upper()[:22], font=font('Poppins-Bold.ttf', 42), fill=(225, 230, 240), anchor='lm')
        lw = 560 * val / mx * kb
        d.rectangle([x0 + 44, y - 24, x0 + 44 + max(6, lw), y + 34], fill=col)
        nv = ('%g' % round(val * kb, 1)) if val < 100 else '{:,}'.format(int(val * kb))
        d.text((x0 + 68 + lw, y + 5), nv, font=font('Anton-Regular.ttf', 64), fill='white', anchor='lm')


# ---------- una scena = un pezzo di video (senza audio). Gira in parallelo su tutti i core.
def luogo(ev):
    """Punto (lon, lat) di un evento, se ne ha uno."""
    try:
        if ev.get('tipo') == 'freccia':
            return float(ev['a'][0]), float(ev['a'][1])
        if ev.get('tipo') == 'confine' and ev.get('punti'):
            pts = ev['punti']; return float(pts[len(pts) // 2][0]), float(pts[len(pts) // 2][1])
        if ev.get('tipo') == 'contorno':
            r = max(risorse()['paesi'].get(str(ev.get('paese')).upper(), []), key=len, default=None)
            return (float(r[:, 0].mean()), float(r[:, 1].mean())) if r is not None else None
        if ev.get('lon') is not None:
            return float(ev['lon']), float(ev['lat'])
    except Exception:
        return None
    return None


def dentro(lon, lat, v, margine=.12):
    """Riporta il punto dentro l'inquadratura v (se Claude lo mette fuori)."""
    cx, cy, wd = v; hd = wd * H / W
    return (max(cx - wd / 2 * (1 - margine * 2), min(cx + wd / 2 * (1 - margine * 2), lon)),
            max(cy - hd / 2 * (1 - margine * 3), min(cy + hd / 2 * (1 - margine * 2), lat)))


def proietta(v):
    """Come il pt di fondo(), ma senza disegnare: (lon, lat) -> pixel per la vista v."""
    cx, cy, wd = v; s = W / wd
    return lambda lon, lat: ((lon - cx) * s + W / 2, (cy - lat) * s + H / 2)


def _largo(testo, fs):
    return ImageDraw.Draw(Image.new('L', (1, 1))).textlength(testo, font=font('Anton-Regular.ttf', fs))


def ingombro(ev, x, y):
    """Rettangoli (in pixel) occupati da un elemento disegnato nel punto (x, y)."""
    tipo = ev.get('tipo')
    if tipo == 'icona':
        return [(x - 122, y - 130, x + 122, y + 130)]
    if tipo == 'etichetta':
        w = _largo(str(ev.get('testo') or '').upper()[:30], 58) + 60; h = 58 * .82
        return [(x - w / 2, y + 110 - h, x + w / 2 + 6, y + 110 + h + 7)]
    if tipo == 'nome':
        w = _largo(str(ev.get('testo') or '')[:24], 50) + 60; h = 50 * .82
        return [(x - w / 2, y - h, x + w / 2 + 6, y + h + 7)]
    if tipo == 'numero':
        w = _largo(str(ev.get('testo') or '')[:14], 120) + 60; h = 120 * .82
        return [(x - w / 2, y - h, x + w / 2 + 6, y + h + 7)]
    if tipo == 'colonna':
        hc = 380 * max(.1, min(1.0, float(ev.get('valore') or .5)))
        w = _largo(str(ev.get('testo') or '').upper()[:22], 44) + 60; h = 44 * .82
        return [(x - 34, y - hc - 16, x + 34, y + 16), (x - w / 2, y + 72 - h, x + w / 2 + 6, y + 72 + h + 7)]
    return []


def _urto(a, b, pad=18):
    return max(0, min(a[2], b[2]) + pad - max(a[0], b[0])) * max(0, min(a[3], b[3]) + pad - max(a[1], b[1]))


def impagina(eventi, tappe, dur, job):
    """Niente piu' elementi uno sopra l'altro: ogni icona/etichetta/numero/colonna viene spostata (il meno possibile)
    finche' non tocca piu' gli elementi gia' a schermo, ne' il cartellino dell'anno, le scritte grandi o il pannello barre.
    Il controllo si fa nella vista piu' larga che la camera avra' mentre l'elemento e' visibile (li' sono piu' vicini).
    Per ogni elemento sceglie anche un posto libero accanto per il Pin."""
    fissi = []
    for ev in eventi:
        tipo = ev.get('tipo')
        if tipo == 'anno':
            fissi.append((60, 60, 420, 260))
        elif tipo == 'scritta':
            w = _largo(str(ev.get('testo') or '').upper()[:16], 190) + 40
            fissi.append((W / 2 - w / 2, H / 2 - 140 - 105, W / 2 + w / 2, H / 2 - 140 + 105))
        elif tipo == 'barre':
            n = len([v for v in (ev.get('voci') or []) if isinstance(v, dict)][:4])
            bx_ = box_barre(max(1, n))[0]; fissi.append((bx_[0] - 10, bx_[1] - 10, bx_[2] + 10, bx_[3] + 10))
    if job.get('apertura'):
        fissi.append((W / 2 - 760, 90, W / 2 + 760, 320))
    giro = [(math.cos(a), math.sin(a)) for a in np.radians([90, 0, 180, 45, 135, 270, 315, 225, 20, 160, 340, 200])]
    passi = [(0, 0)] + [(r * c, r * s_) for r in range(70, 701, 70) for c, s_ in giro]
    messi = []   # (ev, lon, lat)

    def occupati(pt, escludi=None):
        occ = list(fissi)
        for e2, lo, la in messi:
            if e2 is escludi:
                continue
            if e2.get('tipo') == 'freccia':
                x_, y_ = pt(lo, la); occ.append((x_ - 115, y_ - 115, x_ + 115, y_ + 115))
            else:
                occ += ingombro(e2, *pt(lo, la))
            if e2.get('_pin'):
                x_, y_ = pt(*e2['_pin']); occ.append((x_ - 42, y_ - 128, x_ + 42, y_ + 10))
        return occ

    def posto_pin(ev, bx, occ, larga):
        """Posto del Pin accanto all'elemento, dove non tocca niente (prima vicino, poi piu' lontano)."""
        sc_ = W / larga[2]
        bx0 = min(b[0] for b in bx); bx1 = max(b[2] for b in bx); by0 = min(b[1] for b in bx); by1 = max(b[3] for b in bx)
        cy_ = (by0 + by1) / 2 + 60; cand = []
        for extra in (0, 80, 170, 280):
            cand += [(bx0 - 60 - extra, cy_), (bx1 + 60 + extra, cy_), ((bx0 + bx1) / 2, by1 + 140 + extra),
                     (bx0 - 60 - extra, by1 + 60), (bx1 + 60 + extra, by1 + 60), ((bx0 + bx1) / 2, by0 - 20 - extra)]
        scelta, peggio = None, None
        for px, py in cand:
            if not (90 < px < W - 90 and 160 < py < H - 30):
                continue
            pb = (px - 42, py - 128, px + 42, py + 10)
            u = sum(_urto(pb, o, 8) for o in occ + bx)
            if peggio is None or u < peggio:
                scelta, peggio = (px, py), u
            if u == 0:
                break
        if scelta:
            ev['_pin'] = (larga[0] + (scelta[0] - W / 2) / sc_, larga[1] - (scelta[1] - H / 2) / sc_)

    for ev in sorted(eventi, key=lambda e: e['_t']):
        tipo = ev.get('tipo')
        if tipo == 'freccia':
            try:
                lo, la = float(ev['a'][0]), float(ev['a'][1])
                larga = max((vista_a(tappe, t, dur) for t in np.arange(ev['_t'], max(ev['_t'] + .01, dur), .2)), key=lambda q: q[2])
                pt = proietta(larga); x_, y_ = pt(lo, la)
                posto_pin(ev, [(x_ - 115, y_ - 115, x_ + 115, y_ + 115)], occupati(pt), larga)
                messi.append((ev, lo, la))
            except Exception:
                pass
            continue
        if tipo not in ('icona', 'etichetta', 'numero', 'colonna', 'nome') or ev.get('lon') is None:
            continue
        # le inquadrature che la camera avra' mentre l'elemento e' a schermo (6 campioni + la piu' larga)
        ts = np.arange(ev['_t'] + .3, max(ev['_t'] + .31, dur), .2)
        viste = [vista_a(tappe, t, dur) for t in ts]
        larga = max(viste, key=lambda q: q[2])
        campioni = [larga] + [viste[int(i)] for i in np.linspace(0, len(viste) - 1, min(6, len(viste)))]
        pts = [(proietta(v), W / v[2]) for v in campioni]
        occs = [occupati(pt) for pt, _ in pts]
        lon0, lat0 = float(ev['lon']), float(ev['lat'])
        s0 = pts[0][1]

        def costo(dx, dy, solo_larga=False):
            lo, la = lon0 + dx / s0, lat0 - dy / s0; u = 0
            for j, ((pt, _), occ) in enumerate(zip(pts, occs)):
                bx = ingombro(ev, *pt(lo, la))
                u += sum(_urto(b, o) for b in bx for o in occ)
                if j == 0:   # nella vista piu' larga deve stare tutto dentro lo schermo
                    u += sum(max(0, 30 - b[0]) + max(0, b[2] - W + 30) + max(0, 30 - b[1]) + max(0, b[3] - H + 30) for b in bx) * 400
                if solo_larga:
                    break
            return u
        migliore, punti = (0, 0), None
        for dx, dy in passi:
            u = costo(dx, dy)
            if punti is None or u < punti:
                migliore, punti = (dx, dy), u
            if u == 0:
                break
        dx, dy = migliore
        ev['lon'] = lon0 + dx / s0; ev['lat'] = lat0 - dy / s0
        pt, sc_ = pts[0]
        posto_pin(ev, ingombro(ev, *pt(ev['lon'], ev['lat'])), occs[0], larga)
        messi.append((ev, ev['lon'], ev['lat']))


def piano_camera(v0, v1, eventi, dur):
    """Tappe della camera: arrivo sulla vista della scena, poi a ogni evento con un luogo la camera SI AVVICINA (1,5x),
    tra un evento e l'altro deriva lentamente. Risultato: un'inquadratura nuova ogni 2-3 secondi, come il competitor."""
    tappe = [(0.0, v0), (min(1.0, dur * .25), v1)]
    for ev in eventi:
        p = ev.get('_luogo')
        if ev.get('tipo') in ('anno', 'scritta', 'barre') or not p:
            vista = v1   # eventi senza luogo: la camera torna larga
        else:
            vista = (v1[0] + (p[0] - v1[0]) * .6, v1[1] + (p[1] - v1[1]) * .6, v1[2] / 1.5)
        t0 = max(tappe[-1][0] + .3, ev['_t'] - .5)
        if t0 < dur - .5:
            tappe.append((t0, tappe[-1][1])); tappe.append((min(dur - .2, t0 + .8), camera({'lon': vista[0], 'lat': vista[1], 'larghezza': vista[2]})))
    return tappe


def vista_a(tappe, t, dur):
    for (ta, va), (tb, vb) in zip(tappe, tappe[1:]):
        if ta <= t <= tb:
            k = ease((t - ta) / max(tb - ta, 1e-6)); v = tuple(a + (b - a) * k for a, b in zip(va, vb)); break
    else:
        v = tappe[-1][1]
    drift = 1 - .06 * t / max(dur, 1)   # zoom lento continuo: la mappa non e' mai ferma
    return (v[0], v[1], v[2] * drift)


def nomi_paesi(sc, job, v1, dur, eventi):
    """Quando un paese si colora compare anche il suo NOME (al massimo i 2 piu' grandi, solo se si vedono e se non c'e' gia' un'etichetta uguale)."""
    R = risorse(); fatti = {str(e.get('testo') or '').strip().upper() for e in eventi}
    prima = set(job.get('oro_prima') or []) | set(job.get('verde_prima') or [])
    cand = []
    for cd in list(sc.get('oro') or []) + list(sc.get('verde') or []):
        cd = str(cd).upper(); anelli = R['paesi'].get(cd) or []
        nome = (R['nomi'].get(cd) or '').upper()
        if cd in prima or not anelli or not nome or nome in fatti:
            continue
        r = max(anelli, key=len); lon, lat = float(r[:, 0].mean()), float(r[:, 1].mean())
        cx, cy, wd = v1; hd = wd * H / W
        if abs(lon - cx) > wd * .42 or abs(lat - cy) > hd * .42:
            continue
        cand.append((len(r), nome, lon, lat))
    cand.sort(reverse=True)
    return [{'tipo': 'nome', 'testo': n, 'lon': lo, 'lat': la, '_t': min(max(.5, dur - .8), 1.1 + i * .5), '_luogo': None}
            for i, (_, n, lo, la) in enumerate(cand[:2])]


def disegna_scena(job):
    sc, path = job['scena'], job['path']
    R = risorse(); dur = job['dur']; n = max(1, int(round(dur * FPS)))
    v0, v1 = camera(job.get('vista_prima') or sc.get('vista')), camera(sc.get('vista'))
    sep0 = 1.0 if job.get('epoca_prima') == 'antica' else 0.0
    sep1 = 1.0 if sc.get('epoca') == 'antica' else 0.0
    nuv = nuvola(620) if (sep0 != sep1 and job.get('nuvole', True)) else None
    eventi = job['eventi']
    eventi += nomi_paesi(sc, job, v1, dur, eventi)
    for ev in eventi:   # luoghi sempre dentro la vista della scena (i nomi dei paesi non muovono la camera)
        p = luogo(ev) if ev.get('tipo') != 'nome' else None; ev['_luogo'] = dentro(p[0], p[1], v1) if p else None
        if ev['_luogo'] and ev.get('lon') is not None:
            ev['lon'], ev['lat'] = ev['_luogo']
    if nuv is not None:   # cambio d'epoca: niente elementi sotto le nuvole che passano
        for ev in eventi:
            ev['_t'] = max(ev['_t'], 1.5)
    tappe = piano_camera(v0, v1, eventi, dur)
    impagina(eventi, tappe, dur, job)
    pin_a = sc.get('pin') or {}
    try:
        pin_base = dentro(float(pin_a.get('lon')), float(pin_a.get('lat')), v1, .2)
    except Exception:
        pin_base = (v1[0] - v1[2] * .3, v1[1] - v1[2] * H / W * .2)
    pin_da = job.get('pin_prima_luogo') or pin_base
    # da dove si allarga il colore: primo evento con un luogo, altrimenti il centro
    orig = next((ev['_luogo'] for ev in eventi if ev.get('_luogo')), (v1[0], v1[1]))
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', *ENC, path],
                         stdin=subprocess.PIPE)
    for fi in range(n):
        t = fi / FPS
        vista = vista_a(tappe, t, dur)
        sk = sep0 + (sep1 - sep0) * ease((t - .2) / .9)
        base, pt = fondo(vista, sk)
        im = base.convert('RGBA')
        zoom = (120 / vista[2]) ** .5
        a_in = ease(t / .5)
        if job.get('oro_prima') and t < .6:
            riempi(im, base, anelli_visibili(job['oro_prima'], pt), ORO, 1 - a_in, 0)
        if job.get('verde_prima') and t < .6:
            riempi(im, base, anelli_visibili(job['verde_prima'], pt), VERDE, 1 - a_in, 0)
        ox, oy = pt(*orig); r = ease((t - .15) / 1.3) * 2600
        tinta = 1 - sk * .18
        nuovi_v = set(sc.get('verde') or []) - set(job.get('verde_prima') or [])
        nuovi_o = set(sc.get('oro') or []) - set(job.get('oro_prima') or [])
        vecchi_v = [c for c in sc.get('verde') or [] if c not in nuovi_v]; vecchi_o = [c for c in sc.get('oro') or [] if c not in nuovi_o]
        col_o = (240, 172, 30) if sk > .5 else ORO
        riempi(im, base, anelli_visibili(vecchi_v, pt), VERDE, tinta, min(10, 4 * zoom))
        riempi(im, base, anelli_visibili(list(nuovi_v), pt), VERDE, tinta, min(10, 4 * zoom), (ox, oy, r))
        riempi(im, base, anelli_visibili(vecchi_o, pt), col_o, tinta, min(18, 9 * zoom))
        riempi(im, base, anelli_visibili(list(nuovi_o), pt), col_o, tinta, min(18, 9 * zoom), (ox, oy, r))
        d = ImageDraw.Draw(im)
        fine = 1 - ease((t - dur + .25) / .25)
        ultimo = None
        for ev in eventi:
            k = ease((t - ev['_t']) / .35) * fine
            if k <= 0:
                continue
            if ev.get('_luogo'):
                ultimo = ev.get('_pin') or ('base', ev['_luogo'])
            tipo = ev.get('tipo')
            try:
                if tipo in ('icona', 'etichetta', 'numero', 'colonna', 'nome') and ev.get('lon') is not None:
                    x, y = pt(float(ev['lon']), float(ev['lat']))
                if tipo == 'nome':   # nome del paese appena colorato
                    etichetta(im, x, y, str(ev.get('testo') or '')[:24], k, 50, blocca=False)
                if tipo == 'icona':
                    metti(im, icona(ev.get('icona'), 210), x, y + math.sin(t * 2.2 + ev['_t']) * 7, k)
                elif tipo == 'etichetta':
                    etichetta(im, x, y + 110, str(ev.get('testo') or '').upper()[:30], k, blocca=False)
                elif tipo == 'numero':
                    tx = str(ev.get('testo') or '')[:14]
                    etichetta(im, x, y, tx.replace('x', '×', 1) if re.match(r'^x\d', tx) else tx, k, 120, ORO, blocca=False)
                elif tipo == 'colonna':
                    kh = ease((t - ev['_t']) / 1.0) * fine
                    colonna(im, x, y, 380 * max(.1, min(1.0, float(ev.get('valore') or .5))) * kh, (232, 186, 40))
                    etichetta(im, x, y + 72, str(ev.get('testo') or '').upper()[:22], k, 44, blocca=False)
                elif tipo == 'anno':
                    cartellino_anno(im, str(ev.get('testo') or '')[:6], k)
                elif tipo == 'scritta':
                    f = font('Anton-Regular.ttf', 190 * back(k))
                    d.text((W / 2, H / 2 - 140), str(ev.get('testo') or '').upper()[:16], font=f, fill=CREMA, anchor='mm', stroke_width=12, stroke_fill=NAVY)
                elif tipo == 'contorno':
                    lampo = .5 + .5 * math.sin((t - ev['_t']) * 5)
                    for xy in anelli_visibili([ev.get('paese')], pt):
                        d.line(xy + [xy[0]], fill=mix((255, 200, 40), (255, 250, 200), lampo), width=10)
                elif tipo == 'confine':
                    pts = [pt(float(a), float(b)) for a, b in (ev.get('punti') or [])][:60]
                    if len(pts) >= 2:
                        kl = ease((t - ev['_t']) / 1.4); m = max(2, int(len(pts) * kl) + 1)
                        d.line(pts[:m], fill=(120, 10, 10), width=24, joint='curve'); d.line(pts[:m], fill=(230, 40, 40), width=12, joint='curve')
                elif tipo == 'freccia':
                    (xa, ya), (xb, yb) = pt(*map(float, ev['da'])), pt(*map(float, ev['a']))
                    kk = ease((t - ev['_t']) / 2.0); alto = min(260, math.hypot(xb - xa, yb - ya) * .25)
                    pts = [(xa + (xb - xa) * u, ya + (yb - ya) * u - math.sin(u * math.pi) * alto) for u in np.linspace(0, kk, 50)]
                    for j in range(0, len(pts) - 1, 2):
                        d.line([pts[j], pts[j + 1]], fill=(255, 255, 255), width=8)
                    metti(im, icona(ev.get('icona') or 'ship', 190), pts[-1][0], pts[-1][1], k)
                elif tipo == 'barre':
                    pannello_barre(im, ev, k)
            except Exception:
                continue
        # Pin: segue l'ultimo evento con un luogo (gli sta accanto), altrimenti sta al suo posto della scena
        try:
            if ultimo and ultimo[0] != 'base':
                mx, my = pt(*ultimo)                 # posto libero accanto all'ultimo elemento
            else:
                mx, my = pt(*(ultimo[1] if ultimo else pin_base)); mx -= 170; my += 120
            if not hasattr(disegna_scena, '_p') or fi == 0:
                sx, sy = pt(*pin_da); disegna_scena._p = [sx, sy, sx, sy, -9.0]
            st = disegna_scena._p
            if abs(st[2] - mx) > 4 or abs(st[3] - my) > 4:
                if t - st[4] > .7:
                    st[0], st[1] = st[0] + (st[2] - st[0]), st[1] + (st[3] - st[1])
                    st[2], st[3], st[4] = mx, my, t
            kp = ease((t - st[4]) / .7)
            px, py = st[0] + (st[2] - st[0]) * kp, st[1] + (st[3] - st[1]) * kp
            salto = math.sin(kp * math.pi) * 90 + (abs(math.sin(t * 4.5)) * 6 if kp >= 1 else 0)
            faccia = 'stupito' if (pin_a.get('faccia') == 'stupito' and t > dur * .4) else 'normale'
            px = max(80, min(W - 80, px)); py = max(200, min(H - 30, py))
            # il Pin non passa mai sopra scritte grandi, cartellino dell'anno o pannello barre: si sposta sotto/accanto
            for ev in eventi:
                if t < ev['_t'] or ev.get('tipo') not in ('scritta', 'anno', 'barre'):
                    continue
                if ev['tipo'] == 'scritta':
                    w_ = _largo(str(ev.get('testo') or '').upper()[:16], 190) + 40; r_ = (W / 2 - w_ / 2, H / 2 - 245, W / 2 + w_ / 2, H / 2 - 35)
                elif ev['tipo'] == 'anno':
                    r_ = (60, 60, 420, 260)
                else:
                    r_ = box_barre(max(1, len([v for v in (ev.get('voci') or []) if isinstance(v, dict)][:4])))[0]
                if _urto((px - 42, py - 128, px + 42, py + 10), r_, 10):
                    py = r_[3] + 150 if r_[3] + 150 < H - 30 else py
                    if _urto((px - 42, py - 128, px + 42, py + 10), r_, 10):
                        px = r_[0] - 70 if r_[0] - 70 > 80 else r_[2] + 70
            if not (job.get('apertura') and t < 2.5):
                pin(im, px, py, 1.4, faccia, salto)
        except Exception:
            pass
        if job.get('apertura'):   # numero del video, poi il titolo
            num = job['apertura']; tx = str(num.get('testo') or '')
            numero_grande(im, tx.replace('x', '×', 1) if re.match(r'^x\d', tx) else tx,
                          str(num.get('sotto') or ''), ease((t - .1) / .35) * (1 - ease((t - 2.3) / .35)))
            titolo_fascia(im, job['titolo1'], job['titolo2'], ease((t - 2.5) / .6) * (1 - ease((t - min(dur - .4, 6.5)) / .5)))
        if nuv is not None:   # cambio d'epoca: nuvole che passano
            k = t / 1.6
            if 0 < k < 1:
                for yy, scl, off in ((200, 1.3, 0), (560, 1.6, .15), (880, 1.2, .3), (390, 1.0, .45)):
                    x = -700 + (W + 1400) * min(1, max(0, k * 1.3 - off * .6))
                    c = nuv.resize((int(nuv.width * scl), int(nuv.height * scl))); im.alpha_composite(c, (int(x - c.width / 2), int(yy - c.height / 2)))
        p.stdin.write(im.convert('RGB').tobytes())
    p.stdin.close(); p.wait()
    if p.returncode:
        raise RuntimeError('ffmpeg scena fallito')
    return path


def disegna_finale(job):
    """Chiusura: numero del video + nome canale + slogan + Pin + Iscriviti (4 s, senza voce)."""
    path = job['path']; n = int(job['dur'] * FPS)
    v = camera(job.get('vista')); base, pt = fondo(v, 0.0)
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', *ENC, path],
                         stdin=subprocess.PIPE)
    for fi in range(n):
        t = fi / FPS; im = base.convert('RGBA')
        riempi(im, base, anelli_visibili(job.get('verde'), pt), VERDE, 1, 6)
        riempi(im, base, anelli_visibili(job.get('oro'), pt), ORO, 1, 12)
        titolo_fascia(im, NOME_CANALE, SLOGAN, ease(t / .5))
        d = ImageDraw.Draw(im); kk = back((t - .8) / .4)
        if kk > 0:
            d.rectangle([W / 2 - 190 * kk, 760 - 52 * kk, W / 2 + 190 * kk, 760 + 52 * kk], fill=(230, 40, 40))
            if kk > .9:
                d.text((W / 2, 760), 'SUBSCRIBE', font=font('Poppins-ExtraBold.ttf', 48), fill='white', anchor='mm')
        pin(im, W / 2 - 560, 420, 2.4, 'normale', abs(math.sin(t * 4)) * 12)
        p.stdin.write(im.convert('RGB').tobytes())
    p.stdin.close(); p.wait()
    return path


# ============================================================ 4) SUONI (sintetizzati: nessun diritto d'autore)
SR = 44100


def pista_suoni(totale, pop_t, whoosh_t, out):
    rng = np.random.default_rng(1); a = np.zeros(int((totale + 1) * SR))

    def add(t, sig):
        i = int(t * SR)
        if 0 <= i < len(a):
            a[i:i + len(sig)] += sig[:len(a) - i]

    nW = int(1.1 * SR); x = rng.normal(0, 1, nW); env = np.sin(np.linspace(0, np.pi, nW)) ** 2
    y = np.zeros(nW); acc = 0.0
    for i in range(nW):
        acc += (0.008 + 0.05 * env[i]) * (x[i] - acc); y[i] = acc
    f = np.linspace(45, 95, nW)
    whoosh = (y * 2.2 + np.sin(2 * np.pi * np.cumsum(f) / SR) * .45) * env * .28          # morbido e basso
    tt = np.arange(int(.12 * SR)) / SR
    pop = np.sin(2 * np.pi * np.cumsum(520 * np.exp(-tt * 18) + 180) / SR) * np.exp(-tt * 30) * .22
    for t in whoosh_t:
        add(t, whoosh)
    for t in pop_t:
        add(t, pop)
    for i, fr in enumerate((392.0, 493.9, 587.3)):   # firma Rich Borders: tre note all'inizio
        tn = np.arange(int(.5 * SR)) / SR
        add(.15 + i * .16, (np.sin(2 * np.pi * fr * tn) + .3 * np.sin(4 * np.pi * fr * tn)) * np.exp(-tn * 7) * .3)
    if not MUSICA_URL and not brani():   # nessuna musica: tappeto quasi impercettibile
        ta = np.arange(len(a)) / SR
        a += sum(np.sin(2 * np.pi * fr * ta) for fr in (110, 164.8, 220)) * (0.5 + 0.5 * np.sin(2 * np.pi * ta / 8)) * .01
    a = np.clip(a, -1, 1)
    with wave.open(out, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((a * 32767).astype(np.int16).tobytes())
    return out


def brani():
    cart = os.path.join(ROOT, 'musica_mappe')
    return sorted(f for f in os.listdir(cart) if f.lower().endswith(('.mp3', '.m4a', '.wav'))) if os.path.isdir(cart) else []


# ============================================================ 5) COPERTINA (in codice, stile Rich Borders)
def copertina(c, path):
    cp = c.get('copertina') or {}
    Wc, Hc = 1280, 720
    v = camera(cp.get('vista') or (c['scene'][0].get('vista') if c.get('scene') else None))
    base, pt = fondo(v, 0.0)
    im = base.convert('RGBA')
    riempi(im, base, anelli_visibili(cp.get('verde'), pt), VERDE, 1, 10)
    riempi(im, base, anelli_visibili(cp.get('oro'), pt), ORO, 1, 34)
    testo = str(cp.get('testo') or 'WHY?').upper()[:22]
    d = ImageDraw.Draw(im)
    f = font('Anton-Regular.ttf', 190); w = d.textlength(testo, font=f)
    x, y = W / 2 + 120, 190
    d.rectangle([x - w / 2 - 50 + 14, y - 120 + 16, x + w / 2 + 50 + 14, y + 120 + 16], fill=(0, 0, 0))
    d.rectangle([x - w / 2 - 50, y - 120, x + w / 2 + 50, y + 120], fill=NAVY)
    d.rectangle([x - w / 2 - 50, y + 100, x + w / 2 + 50, y + 120], fill=ROSSO)
    d.text((x, y - 10), testo, font=f, fill=ORO, anchor='mm')
    pin(im, 230, 1000, 4.2, 'stupito', 0)
    im.convert('RGB').resize((Wc, Hc), Image.LANCZOS).save(path, quality=92)
    return path


# ============================================================ YOUTUBE + avviso a n8n
EXTRA, INFO_COMP = {}, {}


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


def dati_youtube(c, titolo):
    descr = '\n\n'.join(x for x in [titolo, str(c.get('descrizione') or '').strip(), str(c.get('capitoli_testo') or '').strip(),
                                     str(P.get('descrizione_base') or '').strip()] if x)
    return descr[:4900], lista_tag(titolo, c.get('tag'))


def carica_youtube(path, c, titolo):
    if not E('YT_REFRESH_TOKEN'):
        raise RuntimeError('manca il secret YT_REFRESH_TOKEN del canale: video creato ma non caricato')
    tok = token(); descr, tags_ = dati_youtube(c, titolo)
    snippet = {'title': titolo[:100], 'description': descr, 'tags': tags_, 'categoryId': str(P.get('categoria') or '27'),
               'defaultLanguage': 'en', 'defaultAudioLanguage': 'en'}
    status = {'privacyStatus': P.get('privacy') or 'public', 'selfDeclaredMadeForKids': False}
    if P.get('pubblica_il') and str(P.get('privacy') or 'public').strip().lower() == 'public':
        status['privacyStatus'] = 'private'; status['publishAt'] = P['pubblica_il']
    size = os.path.getsize(path)
    req = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                                 data=json.dumps({'snippet': snippet, 'status': status}).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8',
                                          'X-Upload-Content-Length': str(size), 'X-Upload-Content-Type': 'video/mp4'})
    with urllib.request.urlopen(req, timeout=120) as r:
        sessione = r.headers['Location']
    for tentativo in range(6):
        try:
            put = urllib.request.Request(sessione, data=open(path, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'video/mp4'})
            with urllib.request.urlopen(put, timeout=1800) as r:
                vid = json.loads(r.read().decode())['id']; log('caricato su YouTube:', vid)
                return vid
        except urllib.error.HTTPError as e:
            if e.code == 401:
                tok = token()
            elif e.code not in (500, 502, 503, 504):
                raise RuntimeError('YouTube ha rifiutato il caricamento: ' + str(e.code) + ' ' + e.read().decode()[:400])
        except Exception as e:
            log('upload, riprovo:', str(e)[:150])
        time.sleep(15 * (tentativo + 1))
    raise RuntimeError('caricamento su YouTube non riuscito')


def carica_copertina(video_id, img):
    try:
        req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}', data=open(img, 'rb').read(),
                                     method='POST', headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'image/jpeg'})
        urllib.request.urlopen(req, timeout=120).read()
        return ''
    except Exception as e:
        return 'copertina non caricata: ' + str(e)[:200]


def avvisa(esito):
    for k, v in INFO_COMP.items():
        esito.setdefault(k, v)
    log('esito:', json.dumps(esito, ensure_ascii=False)[:500])
    if not P.get('callback_url'):
        return
    for k in range(3):
        try:
            http(P['callback_url'], {'id': P.get('id'), 'foglio': P.get('foglio', ''), **esito}); return
        except Exception as e:
            log('avviso a n8n non riuscito:', str(e)[:150]); time.sleep(10)


def capitoli(scene, durs):
    """Capitoli YouTube: un capitolo ogni ~90 s, col primo pezzo della frase."""
    out, t, ult = ['0:00 Intro'], 0.0, 0.0
    for s, d in zip(scene, durs):
        if t - ult >= 90 and len(out) < 12:
            frase = re.split(r'[.?!]', str(s.get('testo') or ''))[0].strip()
            if frase:
                out.append(f'{int(t // 60)}:{int(t % 60):02d} ' + ' '.join(frase.split()[:6])); ult = t
        t += d
    return '\n'.join(out) if len(out) > 2 else ''


# ============================================================ MAIN
def pin_luogo(sc):
    try:
        pn = (sc or {}).get('pin') or {}
        return float(pn['lon']), float(pn['lat'])
    except Exception:
        return None


def main():
    os.makedirs(LAV, exist_ok=True); os.makedirs(os.path.join(RIS, 'tw'), exist_ok=True)
    comp = competitor()
    INFO_COMP['titolo_originale'] = comp.get('titolo') or ''
    log('VIDEO DA COPIARE:', comp['id'], '-', comp.get('titolo') or '')
    salvato = os.path.join(LAV, 'copione.json')
    if os.path.exists(salvato):
        c = json.load(open(salvato)); log('RIPRESA: copione salvato')
    else:
        c = copione(comp); json.dump(c, open(salvato, 'w'), ensure_ascii=False, indent=1)
    shutil.copy(salvato, os.path.join(ROOT, 'copione.json'))
    scene = [s for s in c['scene'] if str(s.get('testo') or '').strip()]
    testi = [str(s['testo']).strip() for s in scene]
    with ThreadPoolExecutor(2) as ex:
        voci = list(ex.map(lambda i: voce(i, testi[i], ' '.join(testi[:i])[-400:], ' '.join(testi[i + 1:])[:400]), range(len(testi))))
    durs = [durata(v) + .15 for v in voci]
    log('voce pronta:', round(sum(durs) / 60, 1), 'minuti')
    # tempi degli eventi sulle parole della voce
    pop_t, whoosh_t, t_acc = [], [], 0.0
    jobs = []
    prima = {}
    gia_antica = False
    for i, (s, v, d) in enumerate(zip(scene, voci, durs)):
        try:
            al = json.load(open(v[:-4] + '.json'))
        except Exception:
            al = {}
        evs = []
        for k_, ev in enumerate([e for e in (s.get('eventi') or []) if isinstance(e, dict)][:7]):
            te = tempo_parola(testi[i], ev.get('parola'), al, d)
            if te is None:
                te = d * (k_ + 1) / (len(s.get('eventi') or []) + 1.5)
            ev = dict(ev); ev['_t'] = max(.4, min(d - .6, te)); evs.append(ev)
            pop_t.append(t_acc + ev['_t'])
        if i > 0 and camera(s.get('vista')) != camera(prima.get('vista')) and s.get('epoca') == prima.get('epoca'):
            whoosh_t.append(max(0, t_acc - .35))
        nuvole = s.get('epoca') == 'antica' and prima.get('epoca', s.get('epoca')) != 'antica' and not gia_antica
        gia_antica = gia_antica or s.get('epoca') == 'antica'
        job = {'scena': s, 'dur': d, 'eventi': evs, 'nuvole': nuvole, 'path': os.path.join(LAV, f'scena_{i:03d}.mp4'),
               'vista_prima': prima.get('vista'), 'epoca_prima': prima.get('epoca', s.get('epoca')), 'pin_prima_luogo': pin_luogo(prima),
               'oro_prima': prima.get('oro'), 'verde_prima': prima.get('verde')}
        if i == 0:
            tit = str(c.get('titolo') or comp.get('titolo') or '').upper()
            parole_t = tit.split(); meta = max(1, len(parole_t) // 2)
            job.update(apertura=c.get('numero') or {}, titolo1=' '.join(parole_t[:meta])[:34], titolo2=' '.join(parole_t[meta:])[:40])
        jobs.append(job); prima = s; t_acc += d
    finale_job = {'path': os.path.join(LAV, 'scena_fine.mp4'), 'dur': 4.0, 'vista': (c.get('copertina') or {}).get('vista') or scene[-1].get('vista'),
                  'oro': (c.get('copertina') or {}).get('oro'), 'verde': (c.get('copertina') or {}).get('verde')}
    # disegno in parallelo (ogni core una scena)
    t0 = time.time(); core = max(1, (os.cpu_count() or 2))
    log(f'disegno {len(jobs)} scene su {core} core')
    with ProcessPoolExecutor(core) as ex:
        paths = list(ex.map(disegna_scena, jobs)) + [disegna_finale(finale_job)]
    log('scene disegnate in', round((time.time() - t0) / 60, 1), 'minuti')
    lista = os.path.join(LAV, 'lista.txt')
    open(lista, 'w').write(''.join(f"file '{p}'\n" for p in paths))
    muto = os.path.join(LAV, 'muto.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto])
    # audio: voce (con le pause tra le scene) + suoni + musica
    voce_tot = os.path.join(LAV, 'voce.wav')
    ins, fl = [], ''
    for i, (v, d) in enumerate(zip(voci, durs)):
        ins += ['-i', v]; fl += f'[{i}:a]aresample=44100,apad=whole_dur={d:.3f},atrim=0:{d:.3f}[v{i}];'
    fl += ''.join(f'[v{i}]' for i in range(len(voci))) + f'concat=n={len(voci)}:v=0:a=1[a]'
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', fl, '-map', '[a]', '-ac', '1', voce_tot])
    totale = sum(durs) + 4.0
    suoni = pista_suoni(totale, pop_t + [sum(durs) + .8], whoosh_t, os.path.join(LAV, 'suoni.wav'))
    mix_in = ['-i', voce_tot, '-i', suoni]; mix_f = '[0:a]apad[v0];[v0][1:a]amix=inputs=2:duration=longest:normalize=0[m]'
    mus = None
    if brani():   # un brano della cartella musica_mappe/, scelto in base al video (sempre lo stesso per lo stesso video)
        lista_b = brani(); mus = os.path.join(ROOT, 'musica_mappe', lista_b[sum(map(ord, comp['id'])) % len(lista_b)])
    elif MUSICA_URL:
        try:
            mus = scarica(MUSICA_URL, os.path.join(LAV, 'musica.mp3'))
        except Exception as e:
            log('musica non disponibile:', str(e)[:100])
    if mus:
        log('musica:', os.path.basename(mus))
        mix_in += ['-stream_loop', '-1', '-i', mus]
        # stesso volume per ogni brano (loudnorm), poi basso sotto la voce e ancora piu' basso mentre la voce parla
        mix_f = (f'[0:a]apad,asplit=2[v0][vk];[2:a]loudnorm=I=-24:TP=-3,volume={MUSICA_VOL / .04 * .45:.3f},afade=t=in:d=2,'
                 f'afade=t=out:st={max(0, totale - 3):.2f}:d=3[mu0];[mu0][vk]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=500[mu];'
                 f'[v0][1:a][mu]amix=inputs=3:duration=first:normalize=0[m]')
    audio = os.path.join(LAV, 'audio.m4a')
    run(['ffmpeg', '-y', '-v', 'error', *mix_in, '-filter_complex', mix_f + f';[m]atrim=0:{totale:.3f}[o]', '-map', '[o]', '-c:a', 'aac', '-b:a', '192k', audio])
    finale = os.path.join(ROOT, 'video_mappe.mp4')
    invito_iscriviti(muto, audio, finale, totale)
    cop = copertina(c, os.path.join(ROOT, 'copertina.jpg'))
    titolo = str(c.get('titolo') or comp.get('titolo') or 'Rich Borders')[:100]
    c['capitoli_testo'] = capitoli(scene, durs)
    open(os.path.join(ROOT, 'titolo.txt'), 'w').write(titolo)
    dur_v = durata(finale); log('FATTO:', finale, round(dur_v / 60, 1), 'minuti')
    if CARICA and dur_v >= MIN_SEC_YT:
        vid = carica_youtube(finale, c, titolo); nota = carica_copertina(vid, cop)
        avvisa({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'titolo': titolo,
                'pubblica_il': P.get('pubblica_il') or '', 'minuti_video': round(dur_v / 60, 1), 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1), 'errore': nota})
    else:
        if CARICA:
            log(f'video di {dur_v:.0f} s (sotto {MIN_SEC_YT} s): e\' una prova, NON lo carico')
        if P.get('id'):
            avvisa({'stato': 'PROVA OK' if (PROVA or dur_v < MIN_SEC_YT) else 'CREATO', 'minuti_video': round(dur_v / 60, 1),
                    'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1), 'titolo': titolo})


# ---------- invito SUBSCRIBE come negli altri canali: immagine al secondo N per 4 s + clic + campanella
# (stesse colonne di Channel Configs: subscribe_overlay_*; vuote = valori della riga Main Street Atlas / Rich Borders)
ISC_IMG = str(P.get('subscribe_overlay_url') or 'https://drive.google.com/uc?export=download&id=10HxGKh0ISy1eGapQwuagJyyVuzUo5qd3').strip()
ISC_CLIC = str(P.get('subscribe_overlay_sound_url') or 'https://drive.google.com/uc?export=download&id=1I-kBzQs0Mz_g3w_FDZsYK6-hdGxbTkjJ').strip()
ISC_CAMPANA = str(P.get('subscribe_overlay_bell_url') or 'https://drive.google.com/uc?export=download&id=1xejqUoCdL7fUih6WGuhug5mfinW-91A2').strip()


def _num(v, d):
    try:
        return float(str(v).replace(',', '.')) if str(v or '').strip() != '' else d
    except Exception:
        return d


def bottone_iscriviti(path):
    """Riserva: se l'immagine del Drive non si scarica, bottone SUBSCRIBE rosso con campanella disegnato qui."""
    im = Image.new('RGBA', (900, 230), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([14, 24, 886, 214], 40, fill=(0, 0, 0, 110))
    d.rounded_rectangle([0, 10, 872, 200], 40, fill=(230, 33, 23))
    d.text((380, 105), 'SUBSCRIBE', font=font('Anton-Regular.ttf', 110), fill='white', anchor='mm')
    try:
        metti(im, icona('bell', 150), 760, 105)
    except Exception:
        pass
    im.save(path); return path


def invito_iscriviti(muto, audio, out, totale):
    sec = _num(P.get('subscribe_overlay_second'), 10.0)
    clic_t = sec + _num(P.get('subscribe_overlay_sound_delay'), 0.6)
    camp_t = clic_t + _num(P.get('subscribe_overlay_bell_delay'), 1.0)
    if totale < sec + 5:
        run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', audio, '-c:v', 'copy', '-c:a', 'copy', '-shortest', out]); return
    png = os.path.join(LAV, 'iscriviti.png')
    try:
        scarica(ISC_IMG, png); Image.open(png).verify()
    except Exception as e:
        log('immagine iscriviti dal Drive non disponibile, uso quella disegnata:', str(e)[:80]); bottone_iscriviti(png)
    ins = ['-i', muto, '-i', audio, '-loop', '1', '-t', f'{totale:.3f}', '-i', png]
    fl = (f"[2:v]scale=900:-1,format=rgba,fade=t=in:st={sec}:d=0.3:alpha=1,fade=t=out:st={sec + 3.6}:d=0.4:alpha=1[isc];"
          f"[0:v][isc]overlay=x=(W-w)/2:y=640:enable='between(t,{sec},{sec + 4})'[v]")
    suoni, k = [], 3
    for url, quando, nome in ((ISC_CLIC, clic_t, 'clic'), (ISC_CAMPANA, camp_t, 'campana')):
        try:
            f = scarica(url, os.path.join(LAV, nome + '.mp3'))
        except Exception as e:
            log(nome + ' non disponibile:', str(e)[:80]); continue
        ms = int(quando * 1000); ins += ['-i', f]
        fl += f";[{k}:a]adelay={ms}|{ms},volume=0.5[s{k}]"; suoni.append(f'[s{k}]'); k += 1
    amap = '1:a'
    if suoni:
        fl += f";[1:a]{''.join(suoni)}amix=inputs={len(suoni) + 1}:duration=first:normalize=0[a]"; amap = '[a]'
    run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', fl, '-map', '[v]', '-map', amap, *ENC,
         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-t', f'{totale:.3f}', out])
    log(f'invito SUBSCRIBE al secondo {sec:g} (clic {clic_t:g} s, campanella {camp_t:g} s)')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        if P.get('id'):
            avvisa({'stato': 'ERRORE', 'errore': str(e)[:400], 'minuti_lavoro': round((time.time() - T_INIZIO) / 60, 1)})
        sys.exit(1)
