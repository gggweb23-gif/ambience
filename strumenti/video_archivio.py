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
import base64, io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = re.sub(r'[^a-z0-9_]+', '_', (P.get('nome') or P.get('titolo') or 'video').lower())[:60]
CART = os.path.join('prove_video', 'archivio', NOME); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/va'; os.makedirs(LAV, exist_ok=True)
LINGUA = {'en': 'English (US)', 'it': 'italiano'}.get(str(P.get('language') or 'en')[:2], str(P.get('language')))
MIN_M = float(str(P.get('durata_min_minuti') or 8.5).replace(',', '.')); MAX_M = float(str(P.get('durata_max_minuti') or 9).replace(',', '.'))
PAROLE_SEC = 3.1                                     # misurato sulla voce di Orbital a 1.08: 3,09 parole al secondo (con 2,9 il video veniva 7,5 min invece di 8,5)
P_MIN, P_MAX = int(MIN_M * 60 * PAROLE_SEC), int(MAX_M * 60 * PAROLE_SEC)
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
        o.write('\t'.join([time.strftime('%Y-%m-%d %H:%M'), f"{SPESA['usd']:.3f}", '0', 'NO', '', json.dumps(SPESA['voci']), 'BLOCCATO']) + '\n')


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


def claude(prompt, modello='claude-sonnet-5-5', max_tokens=24000):
    corpo = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': prompt}]}
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
Scenes: 25-40 words each."""
if riferimento:
    regole += f"""

REFERENCE VIDEO (copy its STRUCTURE, rhythm, hooks and kind of questions — NOT its topic): a successful video about ancient Rome.
{' '.join(riferimento.split()[:6000])}"""
regole += """

Answer ONLY with valid JSON:
{"scene": [{"testo": "...", "q": "...", "tag": ["..."], "scritta": "", "obbligo": []}],
 "descrizione": "YouTube description, 3 short paragraphs (~120 words) with the words people search, then a line with 4-6 hashtags",
 "tag": ["20-30 YouTube tags"],
 "copertina_prompt": "one sentence: the scene of the thumbnail, a FICTIONAL astronaut in close-up with a strong readable emotion matching the title, setting and light"}"""
c = None
for k in range(2):
    t = claude(regole + ('' if k == 0 else f'\n\nATTENTION: the previous attempt had {n} words: it MUST be between {P_MIN} and {P_MAX}.'))
    try:
        c = json.loads(t[t.find('{'): t.rfind('}') + 1])
        n = sum(len(s['testo'].split()) for s in c['scene'])
        log(f'copione: {len(c["scene"])} scene, {n} parole (limite {P_MIN}-{P_MAX})')
        if P_MIN * .85 <= n <= P_MAX * 1.12:
            break
    except Exception as e:
        n = 0; log('copione non leggibile:', str(e)[:120], '| risposta:', len(t), 'caratteri', repr(t[:200]))
    c = None
if not c:
    raise RuntimeError('VIDEO BLOCCATO: copione fuori lunghezza (nessuna spesa per voce e montaggio)')
json.dump(c, open(os.path.join(CART, 'copione.json'), 'w'), ensure_ascii=False, indent=1)

# ---------------- 3) montaggio (strumenti/prova_archivio.py) ----------------
mont = {'nome': NOME, 'voce': P.get('voice_id'), 'velocita': float(str(P.get('voice_speed') or 1.08).replace(',', '.')),
        'stabilita': float(str(P.get('voce_stabilita') or .4).replace(',', '.')), 'stile_voce': float(str(P.get('voce_stile') or .25).replace(',', '.')),
        'musica': P.get('musica_file') or 'epico_002.mp3', 'volume_musica': 0.07, 'max_secondi': 3.3, 'solo_video_fino_a': 30,
        'libreria': P.get('libreria') or '', 'scene': [{k: s.get(k) for k in ('testo', 'q', 'tag', 'scritta', 'obbligo') if s.get(k)} for s in c['scene']]}
VIDEO = os.path.join(CART, 'prova.mp4')


def controlli():
    costi = open(os.path.join(CART, 'costi.txt')).read()
    quota = float((re.search(r'video in movimento: (\d+)', costi) or [0, 0])[1])
    media = float((re.search(r'inquadratura media ([\d.]+)', costi) or [0, 9])[1])
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=duration', '-of', 'csv=p=0', VIDEO], capture_output=True, text=True).stdout or 0)   # durata delle IMMAGINI, non dell'audio
    err = []
    if not (MIN_M * 60 * .93 <= dur <= MAX_M * 60 * 1.07):
        err.append(f'durata {dur / 60:.1f} min fuori da {MIN_M:g}-{MAX_M:g}')
    if quota < 80:
        err.append(f'solo {quota:.0f}% di video in movimento (minimo 80%)')
    if media > 3.6:
        err.append(f'inquadratura media {media:.1f} s (massimo 3,3)')
    log(f'CONTROLLI: durata {dur / 60:.1f} min, video in movimento {quota:.0f}%, inquadratura media {media:.1f} s' + (' | DA RIPARARE: ' + '; '.join(err) if err else ' | OK'))
    return quota, media, dur, err


# RIPARAZIONE AUTOMATICA (31 ott, Giorgio: "i video non si devono bloccare"): se un controllo non passa, si rifa' il montaggio
# con regole piu' strette (clip ovunque, inquadrature piu' corte, altri momenti delle riprese gia' scaricate) invece di fermarsi.
TENTATIVI = [mont, dict(mont, solo_video_fino_a=99999, max_secondi=3.0)]
quota = media = dur = 0; errori = ['montaggio non riuscito']; MONTATO = False
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
parole = str(P.get('testo_copertina') or 'WHY?').upper().split(); righe = [' '.join(parole[:-1]), parole[-1]] if len(parole) > 1 else parole
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
crediti = len(' '.join(s['testo'] for s in c['scene']))
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
riga_produzione({'status': 'Completato', 'youtube_video_id': vid_id, 'descrizione_youtube': c.get('descrizione', ''),
                 'tag_seo': ', '.join(c.get('tag', [])), 'data_pubblicazione': time.strftime('%Y-%m-%d %H:%M') + (' (non in elenco)' if (P.get('privacy') or 'unlisted') != 'public' else '')})
print('VIDEO_ID=' + vid_id)
log('FATTO', NOME, f"{SPESA['usd']:.3f} $")
