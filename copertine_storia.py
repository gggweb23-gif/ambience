#!/usr/bin/env python3
"""
STORIA IN MINUTI - le 3 copertine di ogni video, SEMPRE partendo dalla copertina ORIGINALE del competitor:
  1 = 20% diversa dall'originale  (va online subito)
  2 = 30% diversa dall'originale  (pronta per il cambio se il CTR resta basso)
  3 = 40% diversa dall'originale  (ultimo cambio)
Regole: stesso testo dell'originale tradotto al 100% in italiano (date "a.C." / "d.C."), stessa impaginazione e stesso stile;
personaggi con espressioni pulite e serene (niente smorfie), niente incendi, esplosioni, distruzione, guerra o catastrofi;
mai testo nell'angolo in basso a destra (durata del video); bollino del canale in un angolo libero (mai in basso a destra).
Uscita: copertine_storia/<video>_1.jpg, _2.jpg, _3.jpg + confronto.jpg + copertine.txt. APPLICA=SI carica la 1 su YouTube.
Env: VIDEO = "nostroID:competitorID,..." (al posto dell'ID si puo' scrivere una parola del titolo, es. "India:p9IIGdg91fE")
     APPLICA (SI/NO), LIVELLI (default "20,30,40"), YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, FAL_KEY, ANTHROPIC_API_KEY
"""
import base64, io, json, os, re, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageOps

E = os.environ.get
APPLICA = str(E('APPLICA', '') or 'NO').strip().upper() == 'SI'
LIVELLI = [int(x) for x in (E('LIVELLI', '') or '20,30,40').split(',') if x.strip()]
COPPIE = [x.strip().split(':', 1) for x in (E('VIDEO', '') or '').split(',') if ':' in x]
OUT = os.path.join(os.getcwd(), 'copertine_storia'); os.makedirs(OUT, exist_ok=True)
FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
BOLLINO = os.path.join(os.getcwd(), 'bollino_storia_in_minuti.png')


def log(*a):
    print(*a, flush=True)


def http(url, dati=None, headers=None, raw=False, metodo=None, timeout=180):
    h = {'User-Agent': 'Mozilla/5.0'}
    if isinstance(dati, (dict, list)):
        h['Content-Type'] = 'application/json'
    h.update(headers or {})
    body = json.dumps(dati).encode() if isinstance(dati, (dict, list)) else dati
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=metodo), timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60) as r:
        return json.loads(r.read().decode())['access_token']


AUTH = {'Authorization': 'Bearer ' + token()}


def video_canale():
    ch = http('https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true', headers=AUTH)['items'][0]
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    r = http('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode({'part': 'snippet', 'playlistId': up, 'maxResults': 50}), headers=AUTH)
    return [(x['snippet']['resourceId']['videoId'], x['snippet']['title']) for x in r.get('items', [])]


def copertina_yt(v):
    for q in ('maxresdefault', 'hqdefault'):
        try:
            im = Image.open(io.BytesIO(http(f'https://i.ytimg.com/vi/{v}/{q}.jpg', raw=True))).convert('RGB')
            if im.width >= 400:
                return ImageOps.fit(im, (1280, 720), Image.LANCZOS)
        except Exception:
            pass
    return None


def jpg64(im, w=1024):
    x = io.BytesIO(); im.convert('RGB').resize((w, w * 9 // 16)).save(x, 'JPEG', quality=88)
    return base64.b64encode(x.getvalue()).decode()


def fal(modello, dati):
    inv = http('https://queue.fal.run/' + modello, dati, FAL)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], headers=FAL)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], headers=FAL)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')


def claude(cont, max_tokens=3000):
    r = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': max_tokens,
             'messages': [{'role': 'user', 'content': cont}]}, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    return ''.join(b.get('text', '') for b in r.get('content', []))


DOMANDA = """Copertina YouTube di un video di storia di grande successo (competitor). La rifacciamo per il nostro canale italiano "Storia in Minuti".
1) "testo": TUTTO il testo scritto sulla copertina, tradotto in italiano AL 100% (stesse parole, stessi numeri e date, stesse maiuscole).
   Date sempre "a.C." / "d.C." scritte esattamente cosi' (a e d minuscole). Se c'e' un nome di paese lascialo come in italiano (es. INDIA, IRAN).
2) Per ognuno di questi livelli di differenza dall'ORIGINALE: {livelli} — elenca in "cambi" cosa cambiare (in inglese, 1 frase per cambio).
   20% = 2 cambi visibili, 30% = 3 cambi, 40% = 4 cambi. Ogni livello e' indipendente e parte sempre dall'ORIGINALE (non dal livello precedente).
   Cambi ammessi: inquadratura un po' diversa, colori dominanti e luce del cielo/sfondo, monumenti o elementi secondari diversi della stessa epoca e paese,
   posizione dei soggetti, ora del giorno (alba, tramonto, giorno), un simbolo storico in piu'.
   VIETATO: incendi, fumo, esplosioni, distruzione, guerra, sangue, catastrofi, cieli apocalittici; espressioni esagerate o smorfie (i personaggi hanno volti puliti, sereni, dignitosi).
   Il testo, la sua posizione e lo stile del disegno NON cambiano. Non aggiungere loghi, bollini o scritte.
3) "righe": lo stesso testo diviso nelle stesse righe dell'originale (es. originale "HISTORY OF" / "IRAN" -> ["STORIA DELL'", "IRAN"]).
Rispondi SOLO JSON: {{"testo": "...", "righe": ["...", "..."], "livelli": [{{"perc": 20, "cambi": ["...", "..."]}}]}}"""


RIGHE = []


def norm(t):
    return re.sub(r'[^A-Z0-9]', '', str(t).upper().replace('’', "'"))


def testo_giusto(im, testo):
    """Claude legge la scritta della copertina: deve essere ESATTAMENTE il testo voluto (nessuna lettera sbagliata o mancante)."""
    try:
        t = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(im, 1024)}},
                    {'type': 'text', 'text': 'Trascrivi ESATTAMENTE tutto il testo scritto in questa immagine, lettera per lettera, senza correggere errori. '
                                             'Rispondi solo con il testo, su una riga.'}], 300)
        ok = norm(t) == norm(testo)
        if not ok:
            log(f'    scritta sbagliata: letto "{t.strip()[:80]}" invece di "{testo}"')
        return ok
    except Exception as e:
        log('    controllo scritta non riuscito:', str(e)[:100]); return True


def regole(testo):
    return ('Rules: the characters have clean, calm, dignified expressions (no grimaces, no exaggerated emotions); '
            'absolutely NO fire, smoke, explosions, destruction, war scenes, blood or catastrophes; bright, clean, inviting colours. '
            'Keep the BOTTOM-RIGHT corner (last 30% of width and last 28% of height) free of any text: YouTube shows the video duration there; '
            f'Replace ALL the text with exactly this Italian text, same font style, same colours, same size and same position (unless it was in the bottom-right corner): "{testo}". '
            + (('Line by line, spelled letter by letter exactly like this: ' + ' / '.join(f'line {i + 1}: "{r}"' for i, r in enumerate(RIGHE))) + '. ' if RIGHE else '')
            + 'Write ONLY this text: do not add any other word, date or line. '
            + ('Dates exactly as written ("a.C." / "d.C." with lowercase a and d). ' if re.search(r'\d', testo) else '')
            + 'No logos, no badges, no stickers, no watermark.')


def bollino(im):
    if str(E('BOLLINO', '') or 'NO').upper() != 'SI' or not os.path.exists(BOLLINO):   # niente bollino: la copertina e' solo la variante dell'originale
        return im
    b = Image.open(BOLLINO).convert('RGBA'); L = 230
    b = b.resize((L, L), Image.LANCZOS)
    out = im.convert('RGBA'); out.alpha_composite(b, (16, 16))   # sempre in alto a sinistra (lasciato libero nel prompt)
    return out.convert('RGB')


righe, testo_log = [], []
canale = None
for nostro, comp in COPPIE:
    nostro, comp = nostro.strip(), comp.strip()
    if not re.fullmatch(r'[\w-]{11}', nostro):   # parola del titolo -> ID del nostro video
        canale = canale or video_canale()
        trovato = next((v for v, t in canale if nostro.lower() in t.lower()), None)
        if not trovato:
            log('video non trovato sul canale:', nostro); continue
        log(f'"{nostro}" -> {trovato}'); nostro = trovato
    orig = copertina_yt(comp)
    if orig is None:
        log('copertina del competitor non trovata:', comp); continue
    try:
        txt = claude([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpg64(orig, 768)}},
                      {'type': 'text', 'text': DOMANDA.format(livelli=', '.join(f'{p}%' for p in LIVELLI))}])
        an = json.loads(txt[txt.find('{'): txt.rfind('}') + 1])
    except Exception as e:
        log('analisi non riuscita', nostro, str(e)[:200]); continue
    testo = str(an.get('testo') or '').strip()
    RIGHE = [str(x).strip() for x in (an.get('righe') or []) if str(x).strip()]
    livelli = {int(x.get('perc', 0)): x.get('cambi') or [] for x in an.get('livelli') or []}
    log(f'{nostro} <- {comp} | testo: {testo}')
    testo_log.append(f'=== {nostro} (originale {comp})\nTesto: {testo}')

    def fai(k_perc):
        k, perc = k_perc
        cambi = livelli.get(perc) or []
        prompt = (f'Recreate the YouTube thumbnail of the reference image as a high-quality 2D cartoon illustration with clean black outlines and rich detail, '
                  f'keeping the same composition, layout, title position and size, and the same subject and theme, but about {perc}% DIFFERENT from it. '
                  f'Change exactly these things: {"; ".join(cambi)}. Everything else stays like the reference. ' + regole(testo))
        try:
            im = None
            for tentativo in range(3):   # la scritta deve essere perfetta: altrimenti si rifa' (max 3 volte)
                r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt + (' CHECK THE SPELLING OF THE TITLE CAREFULLY.' if tentativo else ''),
                                                      'image_urls': ['data:image/jpeg;base64,' + jpg64(orig)],
                                                      'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
                im = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
                if testo_giusto(im, testo):
                    break
                if tentativo == 2:
                    raise RuntimeError('scritta ancora sbagliata dopo 3 tentativi: copertina NON usata')
            im = bollino(im)
            p = os.path.join(OUT, f'{nostro}_{k}.jpg'); im.save(p, quality=92)
            log(f'  copertina {k} ({perc}% diversa): ' + ' | '.join(cambi))
            return k, perc, im, cambi
        except Exception as e:
            log(f'  copertina {k} non riuscita:', str(e)[:200]); return k, perc, None, cambi
    with ThreadPoolExecutor(3) as ex:
        fatte = list(ex.map(fai, list(enumerate(LIVELLI, start=1))))
    for k, perc, im, cambi in fatte:
        testo_log.append(f'{k} = {perc}% diversa: ' + ' | '.join(cambi))
    stato = 'solo anteprima'
    prima = next((im for k, perc, im, c in fatte if k == 1 and im is not None), None)
    if APPLICA and prima is not None:
        try:
            b = io.BytesIO(); prima.save(b, 'JPEG', quality=90)
            http(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={nostro}', b.getvalue(),
                 dict(AUTH, **{'Content-Type': 'image/jpeg'}), metodo='POST')
            stato = 'copertina 1 CARICATA su YouTube'
        except Exception as e:
            dett = ''
            try:
                dett = e.read().decode()[:200]
            except Exception:
                pass
            stato = 'NON caricata (' + str(e)[:60] + ' ' + dett + ')' + (' -> caricala a mano da YouTube Studio: copertine_storia/' + nostro + '_1.jpg' if getattr(e, 'code', 0) == 403 else '')
    log('  ' + stato)
    testo_log.append(stato + '\n')
    righe.append((nostro, [('ORIGINALE', orig)] + [(f'{k} - {perc}%', im) for k, perc, im, c in fatte]))

open(os.path.join(OUT, 'copertine.txt'), 'a', encoding='utf-8').write(time.strftime('%Y-%m-%d %H:%M') + '\n' + '\n'.join(testo_log) + '\n')
if righe:
    tw, th = 400, 225
    S = Image.new('RGB', (tw * 4 + 40, (th + 40) * len(righe) + 10), 'white'); d = ImageDraw.Draw(S)
    try:
        fe = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    except Exception:
        fe = ImageFont.load_default()
    for i, (vid, celle) in enumerate(righe):
        y = i * (th + 40) + 5
        for j, (nome, im) in enumerate(celle):
            if im is not None:
                S.paste(im.resize((tw, th)), (j * (tw + 10), y + 30))
            d.text((j * (tw + 10) + 4, y + 4), f'{vid}  {nome}' if j == 0 else nome, font=fe, fill='black')
    S.save(os.path.join(OUT, 'confronto.jpg'), quality=88)
log('FATTO | APPLICA =', APPLICA)
