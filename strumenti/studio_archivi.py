#!/usr/bin/env python3
"""
STUDIO ARCHIVI (per tutti i canali) — da fare PRIMA di aprire un canale nuovo.
Idea: si prende la STRUTTURA di un canale che funziona (i suoi video piu' visti: titolo e copertina)
e la si porta su un ALTRO argomento, uno per ogni archivio di immagini gratuito (niente cartoni, niente AI).
Costo: 0 (solo API gratuite: YouTube Data, Pexels, NASA, Wikimedia Commons, Library of Congress, Met Museum).

FASE (variabile d'ambiente FASE):
  competitor -> PAYLOAD {"nome": "rome-unscrolled", "canale": "Rome Unscrolled" (nome o ID UC...), "n": 5}
                salva prove_archivi/<nome>/competitor.json e loro_<k>.jpg (i video piu' visti di SEMPRE del canale)
  candidati  -> legge prove_archivi/<nome>/piano.json e per ogni copertina scarica fino a 8 immagini candidate
                dall'archivio del filone: cand/<filone>_<k>_<i>.jpg + foglio numerato cand_<filone>_<k>.jpg
  componi    -> legge le scelte in piano.json ("scelta": numero della candidata) e crea le copertine con la scritta,
                il foglio di confronto (LORO | filoni) e la griglia come da telefono

piano.json = {"filoni": [{"id": "nasa", "nome": "ASTRONAUTI", "archivio": "nasa|pexels|commons|loc|met",
                          "colore": "#FFD400", "righe": [{"k": 1, "titolo": "...", "testo": "SCRITTA", "query": ["..."],
                                                         "scelta": 0, "pos": "top|bottom", "fuoco": "center|left|right|top"}]}]}
"""
import io, json, os, re, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = P.get('nome') or 'studio'
CART = os.path.join('prove_archivi', NOME); os.makedirs(os.path.join(CART, 'cand'), exist_ok=True)
UA = {'User-Agent': 'ambience-studio-archivi/1.0 (gggweb23@gmail.com)'}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False, timeout=60):
    req = urllib.request.Request(u, data=dati, headers=dict(UA, **(h or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def img(u):
    return Image.open(io.BytesIO(get(u, raw=True, timeout=90))).convert('RGB')


# ---------------- FASE competitor ----------------
def yt_token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    return get('https://oauth2.googleapis.com/token', d)['access_token']


def competitor():
    h = {'Authorization': 'Bearer ' + yt_token()}
    api = 'https://www.googleapis.com/youtube/v3/'
    can = str(P['canale']).strip()
    if not re.fullmatch(r'UC[\w-]{22}', can):
        r = get(api + 'search?' + urllib.parse.urlencode({'part': 'snippet', 'type': 'channel', 'maxResults': 5, 'q': can}), h=h)
        log('canali trovati:', [(i['snippet']['channelTitle'], i['snippet']['channelId']) for i in r.get('items', [])])
        can = r['items'][0]['snippet']['channelId']
    r = get(api + 'search?' + urllib.parse.urlencode({'part': 'snippet', 'type': 'video', 'order': 'viewCount', 'maxResults': 15, 'channelId': can}), h=h)
    ids = [i['id']['videoId'] for i in r.get('items', [])]
    v = get(api + 'videos?' + urllib.parse.urlencode({'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids)}), h=h)
    voci = []
    for i in v.get('items', []):
        dur = i['contentDetails']['duration']
        m = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur) or None
        sec = sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 0
        if sec < 480:          # niente Shorts / video sotto gli 8 minuti
            continue
        voci.append({'id': i['id'], 'titolo': i['snippet']['title'], 'views': int(i['statistics'].get('viewCount', 0)),
                     'durata_min': round(sec / 60, 1), 'data': i['snippet']['publishedAt'][:10], 'canale': i['snippet']['channelTitle']})
    voci.sort(key=lambda x: -x['views'])
    voci = voci[:int(P.get('n') or 5)]
    for k, x in enumerate(voci, 1):
        for q in ('maxresdefault', 'hqdefault'):
            try:
                img(f'https://i.ytimg.com/vi/{x["id"]}/{q}.jpg').resize((1280, 720)).save(os.path.join(CART, 'loro_%d.jpg' % k), quality=90); break
            except Exception:
                pass
        x['k'] = k
        log(k, x['views'], x['titolo'])
    json.dump({'canale_id': can, 'video': voci}, open(os.path.join(CART, 'competitor.json'), 'w'), ensure_ascii=False, indent=1)


# ---------------- archivi gratuiti ----------------
def a_pexels(q, n):
    r = get('https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'per_page': n, 'orientation': 'landscape'}),
            h={'Authorization': E('PEXELS_API_KEY', '')})
    return [p['src']['large2x'] for p in r.get('photos', [])]


def a_nasa(q, n):
    r = get('https://images-api.nasa.gov/search?' + urllib.parse.urlencode({'q': q, 'media_type': 'image'}))
    out = []
    for it in r.get('collection', {}).get('items', [])[:n * 2]:
        l = (it.get('links') or [{}])[0].get('href', '')
        if l:
            out.append(l.replace('~thumb.', '~large.'))
    return out[:n]


def a_commons(q, n):
    r = get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrlimit': n * 3,
        'gsrsearch': q + ' filetype:bitmap', 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1600}))
    out = []
    for p in sorted((r.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 0)):
        ii = (p.get('imageinfo') or [{}])[0]; m = ii.get('extmetadata') or {}
        lic = ((m.get('LicenseShortName') or {}).get('value', '') + ' ' + (m.get('License') or {}).get('value', ''))
        if not re.search(r'public domain|^pd|cc0|cc-zero|no restrictions', lic.strip(), re.I):   # solo immagini libere (pubblico dominio / CC0)
            continue
        if ii.get('width', 0) >= 900 and ii.get('width', 0) >= ii.get('height', 1) * 0.9 and ii.get('thumburl'):
            out.append(ii['thumburl'])
    return out[:n]


def a_loc(q, n):
    r = get('https://www.loc.gov/photos/?' + urllib.parse.urlencode({'q': q, 'fo': 'json', 'c': n * 2}))
    out = []
    for it in r.get('results', []):
        u = (it.get('image_url') or [])
        if u:
            u = u[-1].split('#')[0]
            out.append(('https:' + u) if u.startswith('//') else u)
    return out[:n]


def a_met(q, n):
    ids = get('https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&q=' + urllib.parse.quote(q)).get('objectIDs') or []
    out = []
    for i in ids[:n * 4]:
        try:
            o = get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{i}')
        except Exception:
            continue
        if o.get('isPublicDomain') and o.get('primaryImage'):
            out.append(o['primaryImage'])
        if len(out) >= n:
            break
    return out


ARCHIVI = {'pexels': a_pexels, 'nasa': a_nasa, 'commons': a_commons, 'loc': a_loc, 'met': a_met}


def font(s):
    fp = os.path.join(CART, '_font.ttf')
    if not os.path.exists(fp):
        open(fp, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
    return ImageFont.truetype(fp, s)


def piano():
    return json.load(open(os.path.join(CART, 'piano.json')))


def candidati():
    pz = piano()
    for f in pz['filoni']:
        if P.get('solo') and f['id'] not in P['solo']:
            continue
        for r in f['righe']:
            urls = []
            for q in r['query']:
                try:
                    for u in ARCHIVI[f['archivio']](q, 8):
                        if u not in urls:
                            urls.append(u)
                except Exception as e:
                    log(f['id'], r['k'], q, 'errore archivio:', str(e)[:120])
                if len(urls) >= 8:
                    break
            r['candidati'] = urls[:8]
            ims = []
            for i, u in enumerate(urls[:8]):
                try:
                    im = img(u); im.thumbnail((1600, 1600)); im.save(os.path.join(CART, 'cand', '%s_%d_%d.jpg' % (f['id'], r['k'], i)), quality=88)
                    ims.append((i, im))
                except Exception as e:
                    log(f['id'], r['k'], i, 'immagine non scaricata', str(e)[:80])
            # foglio numerato 4x2
            S = Image.new('RGB', (4 * 400, 2 * 250), (20, 20, 20)); d = ImageDraw.Draw(S)
            for j, (i, im) in enumerate(ims):
                t = im.copy(); t.thumbnail((396, 246)); x, y = (j % 4) * 400, (j // 4) * 250
                S.paste(t, (x + 2, y + 2)); d.rectangle((x + 2, y + 2, x + 42, y + 42), fill='black'); d.text((x + 10, y + 2), str(i), font=font(34), fill='yellow')
            S.save(os.path.join(CART, 'cand_%s_%d.jpg' % (f['id'], r['k'])), quality=85)
            log(f['id'], r['k'], len(ims), 'candidate')
    json.dump(pz, open(os.path.join(CART, 'piano.json'), 'w'), ensure_ascii=False, indent=1)


# ---------------- FASE componi ----------------
def ritaglia(im, fuoco='center'):
    W, H = im.size; t = 16 / 9
    if W / H > t:
        nw = int(H * t); x = {'left': 0, 'right': W - nw}.get(fuoco, (W - nw) // 2); im = im.crop((x, 0, x + nw, H))
    else:
        nh = int(W / t); y = {'top': 0, 'bottom': H - nh}.get(fuoco, (H - nh) // 3); im = im.crop((0, y, W, y + nh))
    return im.resize((1280, 720), Image.LANCZOS)


def righe_testo(d, testo, f, maxw):
    parole, out, cur = testo.split(), [], ''
    for w in parole:
        prova = (cur + ' ' + w).strip()
        if d.textlength(prova, font=f) <= maxw or not cur:
            cur = prova
        else:
            out.append(cur); cur = w
    return out + ([cur] if cur else [])


def copertina(im, testo, colore, pos):
    im = im.copy()
    # leggero contrasto in piu' (le foto d'archivio sono spesso piatte)
    from PIL import ImageEnhance
    im = ImageEnhance.Contrast(im).enhance(1.15); im = ImageEnhance.Color(im).enhance(1.1)
    d = ImageDraw.Draw(im)
    s = 150
    while True:
        f = font(s); ls = righe_testo(d, testo, f, 1180)
        if (len(ls) <= 2 and all(d.textlength(l, font=f) <= 1180 for l in ls)) or s <= 70:
            break
        s -= 6
    alt = len(ls) * int(s * 1.05)
    y0 = 20 if pos != 'bottom' else 720 - alt - 50
    # sfumatura scura solo dietro la scritta (il resto dell'immagine resta ben visibile)
    g = Image.new('L', (1, 720), 0)
    for y in range(720):
        if pos != 'bottom':
            a = 190 if y < y0 + alt else max(0, int(190 * (1 - (y - y0 - alt) / 120)))
        else:
            a = 190 if y > y0 else max(0, int(190 * (1 - (y0 - y) / 120)))
        g.putpixel((0, y), a)
    im.paste(Image.new('RGB', (1280, 720), (0, 0, 0)), (0, 0), g.resize((1280, 720)))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(ls):
        d.text((640, y0 + i * int(s * 1.05)), l, font=f, fill=colore if i == 0 else 'white',
               stroke_width=max(6, s // 14), stroke_fill=(0, 0, 0), anchor='ma')
    return im


def componi():
    pz = piano(); comp = json.load(open(os.path.join(CART, 'competitor.json')))['video']
    fil = [f for f in pz['filoni'] if not P.get('solo') or f['id'] in P['solo']]
    for f in fil:
        for r in f['righe']:
            sc = r.get('scelta', 0)
            p = os.path.join(CART, 'cand', '%s_%d_%d.jpg' % (f['id'], r['k'], sc))
            if not os.path.exists(p):
                log('manca', p); continue
            copertina(ritaglia(Image.open(p).convert('RGB'), r.get('fuoco', 'center')), r['testo'].upper(), f.get('colore', '#FFD400'),
                      r.get('pos', 'top')).save(os.path.join(CART, '%s_%d.jpg' % (f['id'], r['k'])), quality=92)
    # confronto: una riga per video del competitor, colonne LORO + filoni
    col = 1 + len(fil); tw, th = 480, 270; LB = font(22)
    S = Image.new('RGB', (tw * col + 10 * (col + 1), (th + 80) * len(comp) + 50), 'white'); d = ImageDraw.Draw(S)
    for j, t in enumerate(['LORO'] + [f['nome'] for f in fil]):
        d.text((10 + j * (tw + 10), 12), t, font=LB, fill='black')
    for k, x in enumerate(comp, 1):
        y = 50 + (k - 1) * (th + 80)
        d.text((10, y), '{:,}'.format(x['views']).replace(',', '.') + ' views', font=LB, fill='grey')
        celle = [(os.path.join(CART, 'loro_%d.jpg' % k), x['titolo'])]
        for f in fil:
            r = next((r for r in f['righe'] if r['k'] == k), {})
            celle.append((os.path.join(CART, '%s_%d.jpg' % (f['id'], k)), r.get('titolo', '')))
        for j, (p, tit) in enumerate(celle):
            if os.path.exists(p):
                S.paste(Image.open(p).resize((tw, th)), (10 + j * (tw + 10), y + 30))
            d.text((10 + j * (tw + 10), y + 34 + th), tit[:48], font=font(17), fill='black')
    S.save(os.path.join(CART, 'confronto.jpg'), quality=85)
    # telefono: un foglio per filone, copertine piccole come nella home di YouTube
    for f in fil:
        T = Image.new('RGB', (2 * 246 + 30, 3 * 150 + 20), (15, 15, 15))
        ps = [os.path.join(CART, 'loro_1.jpg')] + [os.path.join(CART, '%s_%d.jpg' % (f['id'], r['k'])) for r in f['righe']]
        for j, p in enumerate(ps[:6]):
            if os.path.exists(p):
                T.paste(Image.open(p).resize((246, 138), Image.LANCZOS), (10 + (j % 2) * 256, 10 + (j // 2) * 150))
        T.save(os.path.join(CART, 'telefono_%s.jpg' % f['id']), quality=90)
    fp = os.path.join(CART, '_font.ttf')
    if os.path.exists(fp):
        os.remove(fp)
    log('FATTO')


{'competitor': competitor, 'candidati': candidati, 'componi': componi}[E('FASE', 'competitor')]()
fp = os.path.join(CART, '_font.ttf')
if os.path.exists(fp):
    os.remove(fp)
