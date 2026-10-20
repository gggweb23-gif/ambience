#!/usr/bin/env python3
"""
ROTATORE CTR - metodo semi, fase CTR, per tutti i canali con test_varianti = SI (foglio Channel Configs).
Gira ogni 2 ore su GitHub. Per ogni canale:
 1) video nuovi in test (primi `test_primi_video` del canale, oppure canale in fase SEME): prepara 2 copertine in piu' (B e C)
    partendo dalla copertina A: stesso SENSO del testo, stile del canale, 2 ipotesi diverse. Salva anche A per tornare indietro.
 2) MAI cambiare mentre YouTube spinge. Ogni 2 ore si misurano le views delle ULTIME 6 ORE (le impressioni in tempo reale non sono
    leggibili da programma: le views ne sono la conseguenza diretta). Spinta "finita" = ultime 6 ore <= 20% (spinta_finita_perc)
    delle 6 ore migliori del video, con la copertina online da almeno 12 ore. Quando ci sono i report ufficiali, si usano le impressioni.
 3) CTR della copertina attuale dai report YouTube (giorni interi con quella copertina, minimo ctr_impressioni_min impressioni).
 4) si cambia SOLO se spinta finita E CTR sotto ctr_obiettivo (o non ancora nei report) -> copertina successiva (B, poi C); CTR sopra obiettivo confermato dopo 72 ore online -> resta e chiude.
    Provate tutte -> resta la migliore. Poche impressioni = la leva non e' la copertina (avviso nel log, nessun cambio).
 5) fase del canale: CRESCITA se almeno 4 degli ultimi 5 video hanno CTR >= ctr_obiettivo, altrimenti SEME (si continua a testare).
Config: input CONFIG dal workflow n8n "Config Rotatore CTR" (salvata in ctr_test/config.json per i giri automatici).
Chiavi: YT_CLIENT_ID, YT_CLIENT_SECRET, FAL_KEY, ANTHROPIC_API_KEY + un refresh token per canale (secret YT_REFRESH_TOKEN_<CANALE>).
"""
import base64, csv, glob, io, json, os, re, shutil, statistics, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

E = os.environ.get
BASE = os.path.join(os.getcwd(), 'ctr_test'); os.makedirs(BASE, exist_ok=True)
PT = ZoneInfo('America/Los_Angeles')
ORA = datetime.now(timezone.utc)
SEGRETI = json.loads(E('SEGRETI', '') or '{}')
FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
ALIAS = {'STORIA_IN_MINUTI': 'YT_REFRESH_TOKEN_STORIA', 'KAO_PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}
NERO, BIANCO = (0, 0, 0), (255, 255, 255)


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


def num(x, base):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return base


# ---------------------------------------------------------------- config
cfg_path = os.path.join(BASE, 'config.json')
if (E('CONFIG', '') or '').strip():
    CANALI = json.loads(E('CONFIG'))
    json.dump(CANALI, open(cfg_path, 'w'), ensure_ascii=False, indent=1)
    log('config aggiornata dal foglio:', len(CANALI), 'canali')
elif os.path.exists(cfg_path):
    CANALI = json.load(open(cfg_path))
else:
    raise SystemExit('nessuna config: lancia una volta il workflow n8n "Config Rotatore CTR"')
FONT = os.path.join(BASE, 'Anton.ttf')


def font_file(url):
    p = os.path.join(BASE, 'font_' + re.sub(r'\W', '', url)[-40:] + '.ttf')
    if not os.path.exists(p):
        try:
            open(p, 'wb').write(http(url, raw=True))
        except Exception:
            return FONT
    return p


if not os.path.exists(FONT):
    open(FONT, 'wb').write(http('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))


def token(rt):
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60) as r:
        return json.loads(r.read().decode())['access_token']


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


def colore(x, base):
    try:
        x = str(x).strip().lstrip('#')
        return tuple(int(x[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return base


def scritta(im, v, ffile):
    """Testo grande nel lato libero, mai nel quarto in basso (orario di YouTube)."""
    W, H = im.size
    destra = str(v.get('lato_soggetto', 'right')).lower().startswith('l')
    x0, x1 = (int(W * .50), int(W * .965)) if destra else (int(W * .035), int(W * .52))
    y0, y1 = int(H * .08), int(H * .76)
    righe = [r for r in (str(v.get('riga1', '')).upper().strip(), str(v.get('riga2', '')).upper().strip()) if r]
    cols = [colore(v.get('colore_riga1'), BIANCO), colore(v.get('colore_riga2'), (255, 210, 31))]
    F = lambda k: ImageFont.truetype(ffile, k)
    k = next((k for k in range(320, 50, -4) if len(righe) * k <= (y1 - y0) and all(F(k).getlength(r) <= (x1 - x0) for r in righe)), 60)
    y = y0 + ((y1 - y0) - len(righe) * k) / 2
    base = im.convert('RGBA'); ombra = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ombra); cx = (x0 + x1) / 2
    for j, r in enumerate(righe):
        do.text((cx + 6, y + j * k + 8), r, font=F(k), fill=(0, 0, 0, 180), anchor='mt')
    base.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(base)
    for j, r in enumerate(righe):
        d.text((cx, y + j * k), r, font=F(k), fill=cols[min(j, 1)], anchor='mt', stroke_width=max(4, k // 18), stroke_fill=NERO)
    return base.convert('RGB')


def b64(im):
    x = io.BytesIO(); im.convert('RGB').resize((640, 360)).save(x, 'JPEG', quality=85)
    return base64.b64encode(x.getvalue()).decode()


def leggibile(im):
    """Test gratuito: copertina ridotta alla grandezza del telefono (170x95): contrasto e nitidezza (0-100)."""
    p = im.convert('L').resize((170, 95))
    px = list(p.getdata()); m = sum(px) / len(px)
    contrasto = (sum((x - m) ** 2 for x in px) / len(px)) ** .5
    bordi = p.filter(ImageFilter.FIND_EDGES); nit = sum(bordi.getdata()) / len(px)
    return round(min(100, contrasto * 1.1 + nit * 0.9), 1)


DOMANDA = """Sei il miglior esperto al mondo di copertine YouTube (CTR). Canale "{canale}" (lingua dei testi: {lingua}).
Stile del canale (da rispettare): {stile}
L'immagine e' la copertina ATTUALE (A) del video "{titolo}". Crea 2 copertine nuove (B e C) per un test di CTR.
- STESSO SENSO del testo della A (puoi riformulare meglio, max 4 parole su 2 righe, nella lingua dei testi), MAI cambiare argomento.
- B: stessa idea della A ma piu' forte (soggetto piu' grande, emozione piu' intensa, contrasto piu' alto).
- C: ipotesi diversa (altra inquadratura, altra emozione o oggetto simbolico) per capire cosa clicca di piu'.
Per ognuna: "prompt_en" (immagine dettagliata SENZA alcun testo, lato del testo libero e scuro), "lato_soggetto" ("left"/"right"),
"riga1", "riga2", "colore_riga1", "colore_riga2" (esadecimali), "ipotesi" (cosa testa, 1 frase in italiano).
Rispondi SOLO JSON: {{"testo_A": "...", "varianti": [{{"nome": "B", ...}}, {{"nome": "C", ...}}]}}"""


def crea_varianti(c, vid, titolo, im_a, cartella):
    stile = ' '.join(str(c.get(k) or '') for k in ('thumbnail_art_direction', 'thumbnail_background_style')).strip()[:1200] or 'come la copertina attuale'
    r = http('https://api.anthropic.com/v1/messages', {
        'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 4000, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64(im_a)}},
                                                  {'type': 'text', 'text': DOMANDA.format(canale=c.get('channel_name') or c['channel_id'], lingua=c.get('language') or 'it', stile=stile, titolo=titolo)}]}]},
        {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    t = ''.join(b.get('text', '') for b in r.get('content', []))
    a = json.loads(t[t.find('{'): t.rfind('}') + 1])
    ref = str(c.get('character_ref_url') or '').strip()
    ffile = font_file(c['thumbnail_font_url']) if str(c.get('thumbnail_font_url') or '').startswith('http') else FONT
    fatte = {}
    for v in a.get('varianti', [])[:2]:
        nome = v.get('nome', 'X')
        try:
            corpo = {'prompt': v['prompt_en'] + '. YouTube thumbnail 16:9, very high contrast, readable on a phone. Absolutely NO text, letters or numbers.',
                     'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1}
            if ref:
                corpo['image_urls'] = [ref]
            rr = fal('fal-ai/nano-banana-2/edit' if ref else 'fal-ai/nano-banana-2', corpo)
            im = ImageOps.fit(Image.open(io.BytesIO(http(rr['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
            im = scritta(im, v, ffile)
            im.save(os.path.join(cartella, f'{vid}_{nome}.jpg'), quality=90)
            fatte[nome] = {'ipotesi': v.get('ipotesi', ''), 'testo': f"{v.get('riga1', '')} / {v.get('riga2', '')}", 'leggibilita': leggibile(im)}
            log('   variante', nome, fatte[nome])
        except Exception as e:
            log('   variante', nome, 'non riuscita:', str(e)[:150])
    return a.get('testo_A', ''), fatte


def applica(auth, vid, path):
    try:
        http(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}', open(path, 'rb').read(),
             dict(auth, **{'Content-Type': 'image/jpeg'}), metodo='POST')
        return 'ok'
    except urllib.error.HTTPError as e:
        return f'errore {e.code}: ' + e.read().decode()[:150].replace('\n', ' ')
    except Exception as e:
        return 'errore: ' + str(e)[:150]


def ctr_giornaliero(auth, c):
    """{video: {giorno_PT: [impressioni, clic]}} dai report reach di YouTube (ultimi 20 giorni)."""
    jobs = http('https://youtubereporting.googleapis.com/v1/jobs', headers=auth).get('jobs', [])
    job = next((j for j in jobs if j.get('id') == str(c.get('reach_job_id') or '').strip()), None) or next((j for j in jobs if 'reach' in str(j.get('reportTypeId', ''))), None)
    if not job:
        tipi = http('https://youtubereporting.googleapis.com/v1/reportTypes', headers=auth).get('reportTypes', [])
        tipo = next((t['id'] for t in tipi if 'reach' in t['id']), None)
        if tipo:
            http('https://youtubereporting.googleapis.com/v1/jobs', {'reportTypeId': tipo, 'name': 'reach_ctr'}, auth, metodo='POST')
            log('  creato il report CTR: dati tra circa 2 giorni')
        return {}
    reps, pg = [], ''
    for _ in range(5):
        r = http(f'https://youtubereporting.googleapis.com/v1/jobs/{job["id"]}/reports?' + urllib.parse.urlencode({'pageSize': 100, 'pageToken': pg}), headers=auth)
        reps += r.get('reports', []); pg = r.get('nextPageToken')
        if not pg:
            break
    giorno = {}
    for rp in reps:
        g = str(rp.get('startTime', ''))[:10]
        if g and rp.get('downloadUrl') and (g not in giorno or str(rp.get('createTime')) > str(giorno[g].get('createTime'))):
            giorno[g] = rp
    per = {}
    for g, rp in sorted(giorno.items())[-20:]:
        try:
            righe = list(csv.reader(io.StringIO(http(rp['downloadUrl'], headers=auth, raw=True).decode('utf-8', 'ignore'))))
        except Exception:
            continue
        if not righe or 'video_thumbnail_impressions' not in righe[0]:
            continue
        h = righe[0]; iV, iI, iC = h.index('video_id'), h.index('video_thumbnail_impressions'), h.index('video_thumbnail_impressions_ctr')
        dati = [(x[iV], num(x[iI], 0), num(x[iC], 0)) for x in righe[1:] if len(x) > iC and x[iV]]
        scala = 100 if any(d[2] > 1 for d in dati) else 1
        for v, imp, ctr in dati:
            z = per.setdefault(v, {}).setdefault(g, [0.0, 0.0]); z[0] += imp; z[1] += imp * ctr / scala
    return per


def views_a(st, ore):
    """views di un video a una certa eta' (interpolazione delle foto delle views)."""
    pts = sorted((x[0], x[1]) for x in st.get('views', []))
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if a <= ore <= b:
            return va + (vb - va) * (ore - a) / max(.01, b - a)
    return None


# copertine alternative create SOLO quando servono (risparmio): il rotatore chiede al workflow del canale di crearla, poi lo rilancia
GENERATORI = {
    'STORIA_IN_MINUTI': ('copertine_storia.yml', lambda vid, n: {'video': vid + ':', 'applica': 'SI', 'variante': str(n)}, 2),
    'KAO_PSICOLOGIA': ('copertine_cinema_kao.yml', lambda vid, n: {'applica': 'SI', 'solo': vid, 'variante': str(n)}, 3),
}


def chiedi_copertina(slug, vid, n):
    file_, inputs, _ = GENERATORI[slug]
    repo, tk = E('GITHUB_REPOSITORY', ''), E('GH_TOKEN', '')
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}/actions/workflows/{file_}/dispatches',
                                 data=json.dumps({'ref': 'main', 'inputs': inputs(vid, n)}).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + tk, 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=60).read()


# ---------------------------------------------------------------- giro sui canali
for c in CANALI:
    nome = c.get('channel_name') or c['channel_id']
    slug = re.sub(r'[^A-Z0-9]+', '_', str(c['channel_id']).upper()).strip('_')
    rt = SEGRETI.get(str(c.get('ctr_secret') or '').strip()) or SEGRETI.get('YT_REFRESH_TOKEN_' + slug) or SEGRETI.get(ALIAS.get(slug, ''))
    log(f'=== {nome}')
    if not rt:
        log(f'  manca il secret YT_REFRESH_TOKEN_{slug} su GitHub: salto'); continue
    try:
        auth = {'Authorization': 'Bearer ' + token(rt)}
    except Exception as e:
        log('  token non valido:', str(e)[:150]); continue
    cart = os.path.join(BASE, slug); os.makedirs(cart, exist_ok=True)
    sp = os.path.join(cart, 'stato.json')
    S = json.load(open(sp)) if os.path.exists(sp) else {'inizio': ORA.strftime('%Y-%m-%d'), 'video': {}}
    obiettivo = num(c.get('ctr_obiettivo'), 4)
    ore_ctrl = [num(x, 0) for x in str(c.get('controllo_ore') or '6,12').replace(';', ',').split(',') if str(x).strip()]
    primi = int(num(c.get('test_primi_video'), 5))
    dal = str(c.get('test_dal') or S['inizio'])[:10]
    IMP_MIN = int(num(c.get('ctr_impressioni_min'), 500))   # impressioni minime per giudicare una copertina (sotto, il CTR e' quasi tutto caso)
    SCARTO = num(c.get('ctr_scarto_minimo'), 1.5)            # si torna a una copertina gia' provata solo se migliore di almeno 1,5 punti
    STALLO = num(c.get('spinta_finita_perc'), 20) / 100        # spinta finita = views ultime 6 ore <= 20% delle 6 ore migliori
    GIORNI_MAX = int(num(c.get('test_giorni_max'), 14))
    ORE_CONFERMA = num(c.get('ore_conferma_ctr'), 72)
    MIN_ORE_ONLINE = num(c.get('ore_minime_copertina'), 24)   # prima di giudicare una copertina: almeno 24 ore online

    ch = http('https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true', headers=auth)['items'][0]
    r = http('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode({'part': 'contentDetails', 'playlistId': ch['contentDetails']['relatedPlaylists']['uploads'], 'maxResults': 50}), headers=auth)
    ids = [it['contentDetails']['videoId'] for it in r.get('items', [])]
    vv = http('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode({'part': 'snippet,status,statistics,contentDetails', 'id': ','.join(ids)}), headers=auth).get('items', []) if ids else []
    lunghi = [v for v in vv if (re.search(r'\d+M', v['contentDetails'].get('duration', '')) or re.search(r'\d+H', v['contentDetails'].get('duration', '')))
              and v['status'].get('privacyStatus') == 'public']
    lunghi.sort(key=lambda v: v['snippet']['publishedAt'])
    ordine = {v['id']: i for i, v in enumerate(lunghi)}

    # fase del canale (dai risultati dei test chiusi)
    chiusi = [x for x in S['video'].values() if x.get('ctr_finale') is not None]
    chiusi.sort(key=lambda x: x['pubblicato'])
    ultimi = [x['ctr_finale'] for x in chiusi[-5:]]
    fase = 'CRESCITA' if len(ultimi) >= 5 and sum(1 for x in ultimi if x >= obiettivo) >= 4 else 'SEME'
    S['fase'] = fase
    log(f'  fase: {fase} (ultimi CTR: {ultimi}) | obiettivo {obiettivo}%')

    per = None
    for v in lunghi:
        vid = v['id']; pub = datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z', '+00:00'))
        eta = (ORA - pub).total_seconds() / 3600
        st = S['video'].get(vid)
        if st is None:
            if pub.strftime('%Y-%m-%d') < dal or eta > 24 * GIORNI_MAX or not (ordine[vid] < primi or fase == 'SEME'):
                continue
            inizio_a = pub if eta <= 24 else ORA   # video gia' online da tempo: la copertina 1 si considera messa adesso
            st = S['video'][vid] = {'titolo': v['snippet']['title'], 'pubblicato': pub.isoformat(), 'attiva': 'A', 'cambi': [[inizio_a.isoformat(), 'A']],
                                    'views': [], 'freno': [], 'varianti': {}}
        if st.get('chiuso'):
            continue
        st['views'].append([round(eta, 2), int(v['statistics'].get('viewCount', 0))])
        log(f'  {vid} {eta:5.1f}h views {st["views"][-1][1]} attiva {st["attiva"]}  {st["titolo"][:50]}')

        # 1) copertina 2 GIA' PRONTA nel repository (es. copertine_storia/<video>_2.jpg): nessuna copertina inventata dal rotatore
        pa = os.path.join(cart, f'{vid}_A.jpg')
        uno = [p for p in glob.glob(f'**/{vid}_1.jpg', recursive=True) if not p.startswith('ctr_test')]
        if not os.path.exists(pa) and uno:
            shutil.copy(uno[0], pa)
        if not os.path.exists(pa):   # copertina 1 attuale: serve per tornare indietro se la 2 va peggio
            for q in ('maxresdefault', 'hqdefault'):
                try:
                    b = http(f'https://i.ytimg.com/vi/{vid}/{q}.jpg', raw=True); Image.open(io.BytesIO(b)).verify(); open(pa, 'wb').write(b); break
                except Exception:
                    pass
        for n_, k_ in ((2, 'B'), (3, 'C')):   # copertine 2 e 3 gia' pronte nel repository (Storia: _2 = l'altra figura; KAO: _2 = 20%, _3 = 30%)
            if k_ in st['varianti']:
                continue
            pronte = [p for p in glob.glob(f'**/{vid}_{n_}.jpg', recursive=True) if not p.startswith('ctr_test')]
            if pronte:
                shutil.copy(pronte[0], os.path.join(cart, f'{vid}_{k_}.jpg'))
                st['varianti'].setdefault('A', {'ipotesi': 'copertina 1', 'testo': ''})
                st['varianti'][k_] = {'ipotesi': f'copertina {n_} ({pronte[0]})', 'testo': ''}
                st['sequenza'] = ['A'] + [x for x in ('B', 'C') if x in st['varianti']]
                log(f'   copertina {n_} pronta: {pronte[0]}')
        if slug in GENERATORI:   # sequenza prevista anche se le alternative non esistono ancora: si creano quando servono
            st['sequenza'] = ['A', 'B', 'C'][:GENERATORI[slug][2]]
            for k_ in st['sequenza']:
                st['varianti'].setdefault(k_, {'ipotesi': 'copertina ' + str('ABC'.index(k_) + 1) + (' (da creare quando serve)' if k_ != 'A' else ''), 'testo': ''})
        if len(st['varianti']) < 2 and not st.get('avviso_b'):
            st['avviso_b'] = True; log('   nessuna copertina 2 pronta: il video si controlla ma non si cambia')
        seq = st.get('sequenza') or ['A']

        def cambia(nuova, motivo):
            p = os.path.join(cart, f'{vid}_{nuova}.jpg')
            if nuova == st['attiva']:
                return
            if not os.path.exists(p):
                if slug in GENERATORI and not st.get('chiesta_' + nuova):
                    try:
                        chiedi_copertina(slug, vid, 'ABC'.index(nuova) + 1)
                        st['chiesta_' + nuova] = ORA.isoformat()
                        log(f'   copertina {nuova} serve ({motivo}): chiesta adesso al workflow del canale, la mette online il prossimo giro')
                    except Exception as e:
                        log('   richiesta copertina non riuscita:', str(e)[:150])
                return
            esito = applica(auth, vid, p)
            log(f'   -> copertina {nuova} ({motivo}): {esito}')
            if esito == 'ok':
                st['attiva'] = nuova; st['cambi'].append([ORA.isoformat(), nuova])
            else:
                st.setdefault('errori', []).append(esito)
                if esito.startswith('errore 403'):
                    st['chiuso'] = True   # YouTube non accetta copertine via API su questo video

        # 2) YouTube sta ancora spingendo? (views delle ultime 6 ore rispetto alle 6 ore migliori)
        pts = sorted(st['views'])
        def guadagno(t0, t1):
            a_ = views_a(st, t0); b_ = views_a(st, t1)
            return (b_ - a_) if a_ is not None and b_ is not None else None
        finestre = [guadagno(t - 6, t) for t, _ in pts if t >= 6]
        finestre = [x for x in finestre if x is not None]
        picco = max(finestre) if finestre else 0
        ultime = finestre[-1] if finestre else None
        ore_on = (ORA - datetime.fromisoformat(st['cambi'][-1][0])).total_seconds() / 3600
        if ultime is None or ore_on < MIN_ORE_ONLINE:   # ogni copertina ha almeno 12 ore per farsi spingere
            spinta = 'in corso'
        elif picco < 3:
            spinta = 'mai partita' if eta >= 24 else 'in corso'
        else:
            spinta = 'finita' if ultime <= picco * STALLO else 'in corso'
        st['spinta'] = spinta
        # 3) CTR della copertina attuale, solo sui giorni interi passati con quella copertina (report YouTube, 1-2 giorni di ritardo)
        if per is None:
            try:
                per = ctr_giornaliero(auth, c)
            except Exception as e:
                log('  report CTR non letti:', str(e)[:150]); per = {}
        gg = per.get(vid, {})
        misure = {}
        tratti = []   # (inizio, fine, copertina): quando e' stata online ogni copertina
        for i, (t_, var) in enumerate(st['cambi']):
            fine_ = datetime.fromisoformat(st['cambi'][i + 1][0]) if i + 1 < len(st['cambi']) else ORA
            tratti.append((datetime.fromisoformat(t_), fine_, var))
        for giorno_, (imp, clic) in gg.items():   # impressioni e clic del giorno divisi tra le copertine in base alle ore online
            g0 = datetime.fromisoformat(giorno_).replace(tzinfo=PT); g1 = g0 + timedelta(days=1)
            ore = {}
            for t0, t1, var in tratti:
                o = (min(t1, g1) - max(t0, g0)).total_seconds() / 3600
                if o > 0:
                    ore[var] = ore.get(var, 0) + o
            tot = sum(ore.values())
            for var, o in ore.items():
                z = misure.setdefault(var, [0.0, 0.0]); z[0] += imp * o / tot; z[1] += clic * o / tot
        st['misure'] = {k: [int(v_[0]), round(v_[1] / v_[0] * 100, 2) if v_[0] else 0] for k, v_ in misure.items()}
        att = st['misure'].get(st['attiva'])
        # la spinta si legge sulle IMPRESSIONI giornaliere ufficiali (se ci sono almeno 2 giorni di report); prima, sulle views
        imp_g = [gg[k][0] for k in sorted(gg)]
        segnale = 'views'
        if ultime is None and len(imp_g) >= 2:   # le views (fresche) hanno la precedenza; le impressioni solo se mancano
            segnale = 'impressioni'
            ultime, picco = int(imp_g[-1]), int(max(imp_g))
            if picco < IMP_MIN:
                spinta = 'mai partita' if eta >= 72 else 'in corso'
            else:
                spinta = 'finita' if imp_g[-1] <= max(imp_g) * STALLO else 'in corso'
            st['spinta'] = spinta
        ultimo_cambio = datetime.fromisoformat(st['cambi'][-1][0])
        ore_online = (ORA - ultimo_cambio).total_seconds() / 3600   # da quante ore e' online la copertina attuale
        log(f'   spinta {spinta} ({segnale}: ultimo {ultime}, picco {picco}) | copertina {st["attiva"]} online da {ore_online:.0f}h, CTR {att}')
        # 4) si cambia SOLO se la spinta e' finita E il CTR della copertina attuale e' sotto obiettivo (con abbastanza impressioni)
        provate = [x for x in seq if x in st['misure'] and st['misure'][x][0] >= IMP_MIN]
        if att and att[0] >= IMP_MIN and att[1] >= obiettivo:
            if ore_online >= ORE_CONFERMA:   # sopra obiettivo e confermato dopo 72 ore online: ha vinto
                st['vincente'] = st['attiva']; st['ctr_finale'] = att[1]; st['chiuso'] = True
                log(f'   OK: {st["attiva"]} sopra obiettivo ({att[1]}%) confermato dopo {ore_online:.0f}h, resta questa')
            else:
                log(f'   {st["attiva"]} sopra obiettivo ({att[1]}%), attendo conferma a {ORE_CONFERMA}h')
        elif (spinta == 'finita' and (((not att or att[0] < IMP_MIN) and str(c.get('cambio_senza_ctr') or 'SI').upper() == 'SI') or (att and att[0] >= IMP_MIN and att[1] < obiettivo))) or \
             (spinta == 'mai partita' and att and att[0] >= IMP_MIN and att[1] < obiettivo):
            prossima = next((x for x in seq if x not in st['misure'] and x != st['attiva'] and x not in [k for _, k in st['cambi']]), None)
            if prossima:
                cambia(prossima, f'spinta {spinta} e CTR ' + (f'{att[1]}% < {obiettivo}%' if att and att[0] >= IMP_MIN else 'non ancora nei report'))
            elif len(provate) == len(seq):   # provate tutte e misurate: si torna indietro SOLO se un'altra e' nettamente migliore
                vinc = max(provate, key=lambda k: st['misure'][k][1])
                if att and vinc != st['attiva'] and st['misure'][vinc][1] - att[1] < SCARTO:
                    vinc = st['attiva']
                cambia(vinc, 'nettamente migliore delle provate')
                st['vincente'] = vinc; st['ctr_finale'] = st['misure'][vinc][1]; st['chiuso'] = True
            else:
                log('   provate tutte: aspetto i report CTR per scegliere la migliore')
        elif eta > 24 * GIORNI_MAX:
            vinc = max(provate, key=lambda k: st['misure'][k][1]) if provate else st['attiva']
            cambia(vinc, f'fine test dopo {GIORNI_MAX} giorni')
            st['vincente'] = vinc; st['ctr_finale'] = st['misure'].get(vinc, [0, 0])[1] if provate else None; st['chiuso'] = True
        elif spinta == 'mai partita' and eta >= 72 and not (att and att[0] >= IMP_MIN):
            if not st.get('avviso_impressioni'):
                st['avviso_impressioni'] = True
                log('   ATTENZIONE: YouTube quasi non lo mostra (poche impressioni): la leva non e\' la copertina ma argomento/titolo/SEO')
        if st.get('chiuso') and st.get('vincente'):
            nuovo_f = not os.path.exists(os.path.join(cart, 'risultati.csv'))
            with open(os.path.join(cart, 'risultati.csv'), 'a', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                if nuovo_f:
                    w.writerow(['data', 'video', 'titolo', 'variante', 'testo', 'ipotesi', 'impressioni', 'ctr', 'vincente'])
                for k, (imp, ctr) in st['misure'].items():
                    info = st['varianti'].get(k, {})
                    w.writerow([ORA.strftime('%Y-%m-%d'), vid, st['titolo'], k, info.get('testo', ''), info.get('ipotesi', ''), imp, ctr, 'SI' if k == st['vincente'] else ''])
            log(f'   CHIUSO: vince {st["vincente"]} {st["misure"]}')
    json.dump(S, open(sp, 'w'), ensure_ascii=False, indent=1)
    # riepilogo: quale TIPO di copertina di partenza rende di piu' nel lancio (stessa fase per tutti: prima copertina, prime 72 ore)
    tipi = {}
    for reg in glob.glob('**/registro_copertine.csv', recursive=True):
        for row in csv.DictReader(open(reg, encoding='utf-8')):
            tipi[row.get('video', '')] = row.get('tipo_1', '')
    gruppi = {}
    for vid_, st_ in S['video'].items():
        m_ = (st_.get('misure') or {}).get('A')
        if tipi.get(vid_) and m_ and m_[0] >= IMP_MIN:
            gruppi.setdefault(tipi[vid_], []).append(m_)
    if gruppi:
        with open(os.path.join(cart, 'riepilogo.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f); w.writerow(['tipo copertina di partenza', 'video', 'impressioni', 'CTR medio di lancio'])
            for t_, ms in sorted(gruppi.items()):
                imp_ = sum(x[0] for x in ms); ctr_ = round(sum(x[0] * x[1] for x in ms) / imp_, 2) if imp_ else 0
                w.writerow([t_, len(ms), imp_, ctr_]); log(f'  riepilogo: partenza "{t_}" su {len(ms)} video -> CTR medio di lancio {ctr_}%')
log('FATTO')
