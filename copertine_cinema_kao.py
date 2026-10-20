#!/usr/bin/env python3
"""
KAO PSICOLOGIA - copertine in stile CINEMATOGRAFICO (M2), automatiche.
1) prende da YouTube tutti i video pubblicati o programmati dal DAL in poi (Short esclusi);
2) salta quelli gia' rifatti (file in kao_copertine/cinema): gira ogni 3 ore e sistema da solo ogni video nuovo;
   COACH (1 volta al giorno, al posto di coach_auto_applica): video con CTR < CTR_MIN dopo ATTESA giorni dall'ultima copertina -> copertina nuova, stesso stile, testo diverso;
3) Claude scrive per ognuno testo (2 righe) + emozione + oggetto + scena; Nano Banana fa l'immagine col KAO originale; le scritte le mette lo script;
4) salva la copertina vecchia (kao_copertine/originali, per tornare indietro) e la nuova (kao_copertine/cinema);
5) APPLICA=SI (standard) -> carica le nuove copertine su YouTube. APPLICA=NO -> solo anteprima.
Chiavi: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (di KAO), FAL_KEY, ANTHROPIC_API_KEY.
"""
import base64, csv, io, json, os, re, shutil, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

E = os.environ.get
APPLICA = str(E('APPLICA', '') or 'SI').strip().upper() == 'SI'
DAL = str(E('DAL', '') or '2026-09-21').strip()   # tutti i video pubblicati (o programmati) da questa data in poi
MAX_VIDEO = int(E('MAX_VIDEO', '') or 60)
RIFAI = str(E('RIFAI', '') or 'NO').strip().upper() == 'SI'   # SI = rifa' anche quelli gia' fatti
STILE = str(E('STILE', '') or 'cinema').strip().lower()   # cinema = stile attuale; piatto = copia 100% del competitor con il KAO originale piatto, senza effetti luce
COACH = str(E('COACH', '') or 'NO').strip().upper() == 'SI'   # NO: i cambi li decide il Rotatore CTR (24 ore, spinta finita, CTR < 4%)
_COACH_VECCHIO = ''  #   # una volta al giorno: rifa' la copertina dei video con CTR basso (come coach_auto_applica)
CTR_MIN = float(E('CTR_MIN', '') or 4); IMP_MIN = int(E('IMP_MIN', '') or 500)
ATTESA = int(E('ATTESA_GIORNI', '') or 7); MAX_CAMBI = int(E('MAX_CAMBI', '') or 2); MAX_AL_GIORNO = int(E('MAX_AL_GIORNO', '') or 3)
BASE = os.path.join(os.getcwd(), 'kao_copertine'); NUOVE = os.path.join(BASE, ('cinema' if STILE == 'cinema' else 'piatto') + ('' if APPLICA else '_prova')); VECCHIE = os.path.join(BASE, 'originali')
A_MANO = os.path.join(BASE, 'a_mano')   # copertine che YouTube rifiuta via API: si caricano da YouTube Studio
BASI = os.path.join(BASE, 'cinema_base')   # immagine senza scritte: per cambiare il testo senza rifare il disegno
os.makedirs(NUOVE, exist_ok=True); os.makedirs(VECCHIE, exist_ok=True); os.makedirs(BASI, exist_ok=True)
MAG, BIANCO, NERO = (255, 26, 156), (255, 255, 255), (0, 0, 0)
FAL = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}


def log(*a):
    print(*a, flush=True)


def http(url, dati=None, headers=None, raw=False, metodo=None, timeout=120):
    h = {'Content-Type': 'application/json'} if isinstance(dati, (dict, list)) else {}
    h.update(headers or {})
    body = json.dumps(dati).encode() if isinstance(dati, (dict, list)) else dati
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=metodo), timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def token():
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''),
                                'refresh_token': E('YT_REFRESH_TOKEN', ''), 'grant_type': 'refresh_token'}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=60) as r:
            return json.loads(r.read().decode())['access_token']
    except urllib.error.HTTPError as e:
        raise SystemExit('Token YouTube non valido (' + e.read().decode()[:200] + '): controlla i secrets YT_REFRESH_TOKEN_KAO, YT_CLIENT_ID e YT_CLIENT_SECRET')


TK = token(); AUTH = {'Authorization': 'Bearer ' + TK}

# ---------- 1) video del canale dal DAL in poi (compresi quelli programmati, es. quello delle 17:00)
ch = http('https://www.googleapis.com/youtube/v3/channels?part=contentDetails,snippet&mine=true', headers=AUTH)['items'][0]
log('Canale:', ch['snippet']['title'])
uploads, ids, pg = ch['contentDetails']['relatedPlaylists']['uploads'], [], ''
for _ in range(6):
    r = http('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode(
        {'part': 'contentDetails', 'playlistId': uploads, 'maxResults': 50, 'pageToken': pg}), headers=AUTH)
    ids += [it['contentDetails']['videoId'] for it in r.get('items', [])]
    pg = r.get('nextPageToken')
    if not pg:
        break
cand = []
for k in range(0, len(ids), 50):
    r = http('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode(
        {'part': 'snippet,status,contentDetails', 'id': ','.join(ids[k:k + 50])}), headers=AUTH)
    for v in r.get('items', []):
        quando = str(v['status'].get('publishAt') or v['snippet'].get('publishedAt') or '')[:10]
        durata = v['contentDetails'].get('duration', '')
        corto = not re.search(r'\d+M', durata) and not re.search(r'\d+H', durata)   # Short (meno di 1 minuto): si salta
        if quando >= DAL and not corto:
            cand.append({'id': v['id'], 'titolo': v['snippet']['title'], 'quando': quando, 'stato': v['status'].get('privacyStatus')})
fatti = {f[:-4] for f in os.listdir(BASI if APPLICA else NUOVE) if f.endswith('.jpg')}   # v2: testo grande e lontano dall'orario
if not RIFAI:
    cand = [c for c in cand if c['id'] not in fatti]
cand.sort(key=lambda x: x['quando'], reverse=True); cand = cand[:MAX_VIDEO]
SOLO = [x.strip() for x in (E('SOLO', '') or '').split(',') if x.strip()]   # prova: solo questi video (anche se gia' fatti)
ULTIMI = int(E('ULTIMI', '') or 0)   # prova: gli ultimi N video del canale (anche se gia' fatti), una copertina ciascuno
if ULTIMI and not SOLO:
    SOLO = [c['id'] for c in sorted(cand, key=lambda x: x['quando'], reverse=True)[:ULTIMI]] if RIFAI else SOLO
    os.environ['TRE'] = 'NO'
if SOLO:
    cand = [{'id': v, 'titolo': '', 'quando': '', 'stato': 'prova'} for v in SOLO]
    info = http('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode({'part': 'snippet', 'id': ','.join(SOLO)}), headers=AUTH)
    tit = {x['id']: x['snippet']['title'] for x in info.get('items', [])}
    for c in cand:
        c['titolo'] = tit.get(c['id'], '')
    if not APPLICA and str(E('TRE', '') or 'SI').upper() == 'SI':   # prova: le 3 copertine insieme (100% copia, 20% diversa, 30% diversa)
        cand = [dict(c, gia=['1a'] * n, suff=('' if not n else f'_{n + 1}')) for c in cand for n in range(3)]
for c in cand:
    c['motivo'] = 'nuovo stile'
VARIANTI = os.path.join(BASE, 'varianti'); os.makedirs(VARIANTI, exist_ok=True)
VARIANTE = str(E('VARIANTE', '') or '').strip()   # "2" o "3": crea SOLO quella copertina (la chiede il Rotatore CTR quando serve: niente spesa prima)
if VARIANTE in ('2', '3') and SOLO:
    n_ = int(VARIANTE)
    cand = [dict(c, gia=['1a'] * (n_ - 1), suff=f'_{n_}', variante=True, motivo=f'variante {n_}') for c in cand]
elif APPLICA and str(E('VARIANTI', '') or 'NO').upper() == 'SI':   # (facoltativo) preparare subito 2 e 3
    cand += [dict(c, gia=['1a'] * n, suff=f'_{n + 1}', variante=True) for c in list(cand) if not c.get('gia') for n in (1, 2)]

# ---------- 1b) competitor di ogni video (scheda "Copertine" del file di produzione, pubblicata come CSV): copertina e copy da copiare al 100%
COMP = {}
if E('COPERTINE_CSV', ''):
    try:
        righe_c = list(csv.DictReader(io.StringIO(http(E('COPERTINE_CSV'), raw=True).decode('utf-8-sig'))))
        for rr in righe_c:
            vid = str(rr.get('youtube_video_id') or '').strip()
            m = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', str(rr.get('Link video') or ''))
            if vid and m:
                COMP[vid] = {'comp': m.group(1), 'copy': str(rr.get('copy_competitor_it') or '').strip()}
        log(f'Competitor letti dal foglio: {len(COMP)} video')
    except Exception as e:
        log('foglio competitor non letto:', str(e)[:150])
log(f'Video dal {DAL} senza copertina nuova: {len(cand)}')

# ---------- 2) COACH (una volta al giorno): video con CTR basso DOPO l'ultimo cambio -> nuova copertina, stesso stile, testo diverso
storico = {}   # video -> [(data, testo)] delle copertine caricate
esito_csv = os.path.join(BASE, 'cinema_esito.csv')
if os.path.exists(esito_csv):
    for row in csv.DictReader(open(esito_csv, encoding='utf-8')):
        if row.get('stato') == 'CARICATA':
            storico.setdefault(row['youtube_video_id'], []).append((row['data'], row.get('testo_copertina', '')))
oggi = time.strftime('%Y-%m-%d'); segno = os.path.join(BASE, 'coach_ultimo.txt')
fatto_oggi = os.path.exists(segno) and open(segno).read().strip() == oggi
if COACH and APPLICA and not fatto_oggi:
    try:
        jobs = http('https://youtubereporting.googleapis.com/v1/jobs', headers=AUTH).get('jobs', [])
        job = next((j for j in jobs if 'reach' in str(j.get('reportTypeId', ''))), None)
        if not job:   # primo giro: crea il report delle impressioni (i dati arrivano dopo ~2 giorni)
            tipi = http('https://youtubereporting.googleapis.com/v1/reportTypes', headers=AUTH).get('reportTypes', [])
            tipo = next((t['id'] for t in tipi if 'reach' in t['id']), None)
            if tipo:
                http('https://youtubereporting.googleapis.com/v1/jobs', {'reportTypeId': tipo, 'name': 'kao_reach'}, AUTH, metodo='POST')
                log('Coach: creato il report impressioni/CTR, dati tra ~2 giorni')
        reports, pg = [], ''
        for _ in range(10 if job else 0):
            r = http(f'https://youtubereporting.googleapis.com/v1/jobs/{job["id"]}/reports?' + urllib.parse.urlencode({'pageSize': 100, 'pageToken': pg}), headers=AUTH)
            reports += r.get('reports', []); pg = r.get('nextPageToken')
            if not pg:
                break
        giorno = {}
        for rp in reports:
            g = str(rp.get('startTime', ''))[:10]
            if g and rp.get('downloadUrl') and (g not in giorno or str(rp.get('createTime')) > str(giorno[g].get('createTime'))):
                giorno[g] = rp
        per = {}   # video -> {giorno: [impressioni, clic]}
        for g, rp in sorted(giorno.items())[-35:]:
            try:
                righe = list(csv.reader(io.StringIO(http(rp['downloadUrl'], headers=AUTH, raw=True).decode('utf-8', 'ignore'))))
            except Exception:
                continue
            if not righe or 'video_thumbnail_impressions' not in righe[0]:
                continue
            h = righe[0]; iV, iI, iC = h.index('video_id'), h.index('video_thumbnail_impressions'), h.index('video_thumbnail_impressions_ctr')
            dati = [(c[iV], float(c[iI] or 0), float(c[iC] or 0)) for c in righe[1:] if len(c) > iC and c[iV]]
            scala = 100 if any(x[2] > 1 for x in dati) else 1
            for v, imp, ctr in dati:
                x = per.setdefault(v, {}).setdefault(g, [0.0, 0.0]); x[0] += imp; x[1] += imp * ctr / scala
        ids_nuovi = {c['id'] for c in cand}
        coach = []
        for v, giorni in per.items():
            st = storico.get(v, [])
            if v in ids_nuovi or not st:   # solo video gia' nel nuovo stile (gli altri li sistema la parte "nuovi")
                continue
            ultimo = max(d for d, _ in st)
            if (time.mktime(time.strptime(oggi, '%Y-%m-%d')) - time.mktime(time.strptime(ultimo, '%Y-%m-%d'))) / 86400 < ATTESA or len(st) > MAX_CAMBI:
                continue
            imp = sum(x[0] for g, x in giorni.items() if g > ultimo); clic = sum(x[1] for g, x in giorni.items() if g > ultimo)
            if imp >= IMP_MIN and clic / imp * 100 < CTR_MIN:
                coach.append({'id': v, 'imp': int(imp), 'ctr': round(clic / imp * 100, 2), 'persi': imp * (CTR_MIN / 100) - clic,
                              'gia': [t for _, t in st]})
        coach.sort(key=lambda x: -x['persi']); coach = coach[:MAX_AL_GIORNO]
        if coach:
            info = http('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode({'part': 'snippet', 'id': ','.join(c['id'] for c in coach)}), headers=AUTH)
            titoli = {x['id']: x['snippet']['title'] for x in info.get('items', [])}
            for c in coach:
                cand.append({'id': c['id'], 'titolo': titoli.get(c['id'], ''), 'quando': '', 'stato': 'coach',
                             'motivo': f'coach: CTR {c["ctr"]}% su {c["imp"]} impressioni dopo il cambio', 'gia': c['gia']})
        log(f'Coach: {len(coach)} video con CTR sotto {CTR_MIN}% dopo l\'ultima copertina')
        open(segno, 'w').write(oggi)
    except Exception as e:
        log('coach saltato:', str(e)[:200])
for c in cand:
    log(f'  {c.get("quando", ""):10}  {c["id"]}  {c["titolo"][:55]}  [{c["motivo"]}]')
if not cand:
    raise SystemExit(0)

# ---------- 3) testi e scene con Claude
elenco = '\n'.join(f'{i}. {c["titolo"]}' + (f'   (copertine gia\' provate e NON funzionate: {"; ".join(c["gia"])} -> scrivi un testo e un\'emozione DIVERSI)' if c.get('gia') else '') for i, c in enumerate(cand))
domanda = f"""Sei un esperto di copertine YouTube per un canale italiano di psicologia (personaggio KAO). Per ogni titolo scrivi la copertina.
Regole del testo: italiano, MAIUSCOLO, deve leggersi in un attimo da TELEFONO: "riga1" = 1-2 parole, MASSIMO 10 lettere in tutto; "riga2" = la parola chiave, 1 parola (2 solo se cortissime), MASSIMO 9 caratteri compreso il "?" finale se c'e'. Preferisci parole CORTE e forti (es. "SOLO / TU?", "CASA / MIA?", "TI FIDI / MAI?"): niente parole lunghe come INDIFFERENTE o CONSAPEVOLE. Deve COMPLETARE il titolo creando curiosita', non ripeterlo; niente clickbait vuoto (vietato: incredibile, scioccante).
Per l'immagine (in inglese): "emo" = emozione esagerata e leggibile del personaggio legata al tema; "oggetto" = cosa tiene in mano o ha accanto (un oggetto concreto che racconta il tema); "scena" = l'ambiente sfocato dietro di lui, concreto e a tema, con luci calde (es. a dim living room with fairy lights).
TITOLI:
{elenco}
Rispondi SOLO con un array JSON nello stesso ordine: [{{"n": 0, "riga1": "...", "riga2": "...", "emo": "...", "oggetto": "...", "scena": "..."}}]"""
r = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 8000,
         'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'medium'},
         'messages': [{'role': 'user', 'content': domanda}]}, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
txt = ''.join(b.get('text', '') for b in r.get('content', []))
testi = {int(x['n']): x for x in json.loads(txt[txt.find('['): txt.rfind(']') + 1])}


def copertina_yt(v):
    for q in ('maxresdefault', 'hqdefault'):
        try:
            b = http(f'https://i.ytimg.com/vi/{v}/{q}.jpg', raw=True)
            im = Image.open(io.BytesIO(b)).convert('RGB')
            if im.width >= 400:
                return ImageOps.fit(im, (1280, 720), Image.LANCZOS)
        except Exception:
            pass
    return None


def copia_competitor(i):
    """Copertina del competitor: testo tradotto al 100% (stesse parole, solo diviso in 2 righe) + scena, emozione, oggetto e composizione identici."""
    c = cand[i]
    k = COMP.get(c['id'])
    if not k:
        return
    # 1a copertina = copia al 100%; se il CTR resta basso: 2a = 20% diversa dall'originale, 3a = 30% diversa
    perc = 0 if not c.get('gia') else (20 if len(c['gia']) == 1 else 30)
    im = copertina_yt(k['comp'])
    if im is None:
        log('copertina competitor non trovata per', c['id']); return
    buf = io.BytesIO(); im.resize((768, 432)).save(buf, 'JPEG', quality=85)
    dom = f"""Questa e' la copertina YouTube di un video di psicologia di successo (competitor). Va copiata al 100% per il nostro canale italiano.
TESTO: {('il testo della copertina gia\' tradotto in italiano e\' "' + k['copy'] + '": usa ESATTAMENTE queste parole, stesso ordine') if k['copy'] else 'traduci in italiano ESATTAMENTE il testo scritto nella copertina, parola per parola'}.
Dividilo in due righe SENZA cambiare, togliere o aggiungere parole: "riga1" = la prima parte, "riga2" = SOLO l'ultima parola (la parola chiave, andra' su un'etichetta colorata; 2 parole solo se l'ultima ha meno di 3 lettere). MAIUSCOLO.
{('VARIANTE: questa e\' la copertina numero ' + str(len(c.get('gia') or []) + 1) + ' (le precedenti hanno avuto CTR basso). Il TESTO resta identico. '
   'L\'IMMAGINE deve essere diversa per circa il ' + str(perc) + '% dall\'originale: cambia ' + ('UN solo elemento visivo forte' if perc <= 20 else 'DUE elementi visivi forti') +
   ' (es. l\'oggetto in mano, l\'espressione, il gesto, l\'ambiente sfocato dietro), tutto il resto identico. '
   'Scrivi in "cambi" (in inglese) esattamente cosa cambia.') if perc else ''}
PERSONAGGIO (in inglese, SENZA MAI citare scritte, lettere o riquadri di testo): copia ESATTAMENTE cosa fa il personaggio principale, che diventera' il nostro KAO:
"emo" = emozione ed espressione esatte; "azione" = cosa fa, posa, gesti, mani, caratteristiche speciali (es. tante braccia che tengono oggetti) descritte come se fosse KAO.
VIETATO descrivere l'ASPETTO del personaggio del competitor: niente colore della pelle o del corpo, forma, specie (fagiolo, mostro, animale, creatura), vestiti, capelli. Scrivi sempre "KAO" come soggetto;
"oggetto" = gli oggetti e simboli che tiene o ha accanto (gli stessi della copertina).
"scena" = uno sfondo per il NOSTRO stile cinematografico, coerente con il tema: un ambiente reale sfocato con luci calde e bokeh (es. a cozy study at night with warm lamps). NON copiare lo sfondo o i colori del competitor.
"lato_testo" = "sinistra" o "destra": il lato dove il competitor ha messo la scritta.
"luogo" (in inglese) = il LUOGO REALE e concreto dove si svolge la situazione della copertina, descritto con 4-6 dettagli visibili (es. "a small Italian living room at night: old sofa, TV light, family photos on the wall, a door half open").
"persone" (in inglese) = le ALTRE persone della situazione (quelle della copertina competitor o quelle che servono a far capire il contesto: genitori che litigano, partner, amici, folla...), cosa fanno e dove stanno; "" se la situazione e' di una persona sola.
Rispondi SOLO JSON: {{"riga1": "...", "riga2": "...", "emo": "...", "oggetto": "...", "scena": "...", "azione": "...", "luogo": "...", "persone": "...", "lato_testo": "destra", "cambi": ""}}"""
    try:
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 2000,
                  'messages': [{'role': 'user', 'content': [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                                                            {'type': 'text', 'text': dom}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
        tt = ''.join(b.get('text', '') for b in rr.get('content', []))
        x = json.loads(tt[tt.find('{'): tt.rfind('}') + 1])
        x['comp_img'] = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
        x['comp_id'] = k['comp']; x['perc'] = perc; x['lato_testo_comp'] = str(x.pop('lato_testo', '') or 'destra').lower()
        testi[i] = dict(testi.get(i) or {}, **x)
        log(f"copia competitor {k['comp']} -> {c['id']} ({100 - perc}% uguale): {x.get('riga1')} / {x.get('riga2')}" + (f" | cambia: {x.get('cambi')}" if perc else ''))
    except Exception as e:
        log('copia competitor non riuscita', c['id'], str(e)[:150])


with ThreadPoolExecutor(3) as ex:
    list(ex.map(copia_competitor, range(len(cand))))

# ---------- 4) immagini + scritte
ID = 'data:image/png;base64,' + base64.b64encode(http('https://drive.usercontent.google.com/download?id=1W0qfeLwJ6NweRJwyC9GuezRh2L2GisGu&export=download&confirm=t', raw=True)).decode()
FONT = os.path.join(BASE, 'Anton.ttf'); open(FONT, 'wb').write(http('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
KAO = ('The main character is the character of the reference image: completely bald round head, same simple friendly face, magenta '
       'long-sleeve shirt. Keep his identity. ')


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


def e_kao(im):
    """Claude confronta il personaggio con KAO originale: True se e' lui al 100%."""
    buf = io.BytesIO(); im.resize((640, 360)).save(buf, 'JPEG', quality=85)
    try:
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 800,
                  'messages': [{'role': 'user', 'content': [
                      {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': ID.split(',', 1)[1]}},
                      {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                      {'type': 'text', 'text': 'Image 1 is our character KAO. In image 2, is the main character EXACTLY KAO (same bald round head, same light skin colour, '
                                               'same face style, magenta shirt), with nothing of another character (no green or coloured skin, no bean/monster/creature body)? '
                                               'Extra arms are fine only if they have KAO skin and magenta sleeves. Answer only SI or NO.'}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=200)
        return 'NO' not in ''.join(b.get('text', '') for b in rr.get('content', [])).upper()
    except Exception as e:
        log('controllo KAO non riuscito:', str(e)[:100]); return True


def zona_libera(im, lato):
    """Claude guarda l'immagine finita e indica il rettangolo LIBERO piu' grande (niente volto, corpo, braccia od oggetti) per il testo."""
    buf = io.BytesIO(); im.resize((768, 432)).save(buf, 'JPEG', quality=85)
    dom = (f'This is a YouTube thumbnail without text. We must add a 2-line title on the {"LEFT" if lato == "sinistra" else "RIGHT"} side. '
           'Find the LARGEST rectangle on that side that is EMPTY background: it must NOT cover the face, body, arms, hands or any object, not even partially. '
           'Keep a small margin from them, but make the rectangle as BIG as possible (the title must be huge, readable on a phone). Avoid the bottom-right corner (last 25% of height on the right 30% of width: video timestamp). '
           'Answer ONLY JSON with percentages of width/height: {"x0": 0, "y0": 0, "x1": 0, "y1": 0}')
    try:
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 1500,
                  'messages': [{'role': 'user', 'content': [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                                                            {'type': 'text', 'text': dom}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=200)
        tt = ''.join(b.get('text', '') for b in rr.get('content', []))
        z = json.loads(tt[tt.find('{'): tt.rfind('}') + 1])
        z = [max(0.0, min(100.0, float(z[k]))) / 100 for k in ('x0', 'y0', 'x1', 'y1')]
        if z[2] - z[0] >= .22 and z[3] - z[1] >= .30:
            return z
        log('zona libera troppo piccola:', z)
    except Exception as e:
        log('zona libera non trovata:', str(e)[:120])
    return None


def scritta(im, righe, lato='destra', zona=None):
    """Testo GRANDE a destra, mai sotto l'orario di YouTube (angolo in basso a destra): riga bianca (anche su 2 righe se lunga) + etichetta magenta."""
    W, Hh = im.size
    x0, x1, y0, y1 = int(W * .50), int(W * .965), int(Hh * .06), int(Hh * .72)   # sotto il 75% c'e' l'orario del video
    if lato == 'sinistra':   # stesso lato del testo del competitor
        x0, x1, y0, y1 = int(W * .035), int(W * .50), int(Hh * .06), int(Hh * .92)
    if zona:   # rettangolo libero indicato da Claude: la scritta si adatta allo spazio, senza coprire niente
        x0, y0, x1, y1 = int(W * zona[0]) + 10, int(Hh * zona[1]) + 10, int(W * zona[2]) - 10, int(Hh * zona[3]) - 10
        if lato == 'destra':   # centrata nello spazio vuoto a destra: dal bordo del personaggio al bordo dell'immagine, e in altezza
            x0, x1 = max(x0, int(W * .46)), int(W * .965)
            y0, y1 = int(Hh * .06), int(Hh * .72)   # mai nell'angolo in basso a destra: li' YouTube mette la durata del video
    larg, alt = x1 - x0, y1 - y0
    F = lambda k: ImageFont.truetype(FONT, k)
    r1, r2 = righe[0].strip(), righe[1].strip()
    parole = r1.split()
    disposizioni = [[r1]] + ([[' '.join(parole[:i]), ' '.join(parole[i:])] for i in range(1, len(parole))] if len(parole) > 1 else [])
    best = None
    for d1 in disposizioni:
        for k in range(330, 60, -4):   # k = grandezza riga bianca; etichetta = 0.8 k
            k2 = int(k * .8); pad = k2 * .22
            w_et = (F(k2).getlength(r2) + pad * 2) * 1.0   # larghezza etichetta
            h_tot = len(d1) * k * 1.04 + k2 * 1.32 + k2 * .12
            if max(F(k).getlength(x) for x in d1) <= larg and w_et <= larg * .98 and h_tot <= alt:
                if not best or k > best[0]:
                    best = (k, d1)
                break
    k, d1 = best or (70, [r1]); k2 = int(k * .8); pad = k2 * .22
    h_tot = len(d1) * k * 1.04 + k2 * 1.32
    y = y0 + (alt - h_tot) / 2
    base = im.convert('RGBA'); cx = (x0 + x1) / 2; f1 = F(k)
    ombra = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ombra)
    for j, riga in enumerate(d1):
        do.text((cx + 6, y + j * k * 1.04 + 8), riga, font=f1, fill=(0, 0, 0, 170), anchor='mt')
    base.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(9)))
    dr = ImageDraw.Draw(base)
    for j, riga in enumerate(d1):
        dr.text((cx, y + j * k * 1.04), riga, font=f1, fill=BIANCO, anchor='mt', stroke_width=max(4, k // 16), stroke_fill=NERO)
    y += len(d1) * k * 1.04 + k2 * .06
    f2 = F(k2)
    et = Image.new('RGBA', (int(f2.getlength(r2) + pad * 2), int(k2 * 1.25)), (0, 0, 0, 0)); de = ImageDraw.Draw(et)
    de.rounded_rectangle((0, 0, et.width - 1, et.height - 1), radius=int(k2 * .2), fill=MAG + (255,))
    de.text((et.width / 2, et.height / 2), r2, font=f2, fill=BIANCO, anchor='mm')
    et = et.rotate(3, expand=True, resample=Image.BICUBIC)
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0)); sh.alpha_composite(et, (int(cx - et.width / 2 + 8), int(y + 10)))
    sh = Image.merge('RGBA', (*[Image.new('L', base.size, 0)] * 3, sh.split()[3].point(lambda a: a * .45))).filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(sh); base.alpha_composite(et, (int(cx - et.width / 2), int(y)))
    return base.convert('RGB')


def fai(i):
    c, t = cand[i], testi.get(i) or {}
    if c.get('variante') and not t.get('comp_id'):   # varianti 20%/30% solo per i video con il competitor nel foglio
        return None
    if not t.get('riga1') or not t.get('riga2'):
        log('testo mancante per', c['id']); return None
    p = os.path.join(NUOVE, c['id'] + c.get('suff', '') + '.jpg')
    for q in ('maxresdefault', 'hqdefault'):   # copertina attuale: si salva per poter tornare indietro
        if os.path.exists(os.path.join(VECCHIE, c['id'] + '.jpg')):
            break
        try:
            b = http(f'https://i.ytimg.com/vi/{c["id"]}/{q}.jpg', raw=True)
            Image.open(io.BytesIO(b)).verify()   # solo se e' davvero un'immagine
            open(os.path.join(VECCHIE, c['id'] + '.jpg'), 'wb').write(b); break
        except Exception:
            pass
    prompt = (f'{KAO}Keep him a flat 2D cartoon with thick black outlines, but place him in a modern CINEMATIC thumbnail: behind him a softly blurred, '
              f'colourful, semi-realistic background ({t.get("scena", "")}) with bokeh lights and shallow depth of field, and a strong warm rim light outlining him. '
              f'Head and shoulders BIG on the LEFT 55%, exaggerated emotion: {t.get("emo", "")}. {t.get("oggetto", "")}. '
              'The RIGHT 45% is darker, blurred and calm for text. YouTube thumbnail 16:9, modern, premium, very high contrast, readable on a phone. '
              'Absolutely NO text, letters or numbers in the image.')
    refs = [ID]
    if t.get('comp_id'):   # dal competitor: testo, emozione, azione e oggetti; stile, colori e impaginazione restano i nostri
        diverso = (f'(Variant: change ONLY this compared to the reference idea: {t.get("cambi", "")}.) ' if t.get('perc') else '')
        prompt = (f'{KAO}Every part of the character is KAO: KAO\'s bald round head, face, skin colour and magenta long-sleeve shirt; '
                  'if he has extra arms they have KAO\'s skin and magenta sleeves. '
                  f'{diverso}Keep him a flat 2D cartoon with thick black outlines, but place him in a modern CINEMATIC thumbnail: behind him a softly blurred, '
                  f'colourful, semi-realistic background ({t.get("scena", "")}) with bokeh lights and shallow depth of field, and a strong warm rim light outlining him. '
                  f'Head and shoulders BIG on the LEFT HALF. What he does: {t.get("azione", "")}. Emotion: {t.get("emo", "")}. Objects: {t.get("oggetto", "")} '
                  '(drawn in the same flat cartoon style). KAO, his arms and ALL objects stay inside the LEFT 50% of the image. '
                  'The RIGHT 50% is completely EMPTY: only darker blurred background, no arms, no objects, nothing (it is reserved for a very big title). '
                  'YouTube thumbnail 16:9, modern, premium, very high contrast, readable on a phone. Absolutely NO text, letters or numbers in the image.')
        t['lato_testo'] = 'destra'
        if STILE == 'piatto':   # stile delle vecchie copertine di successo: scena completa (ambiente + persone) con il KAO originale piatto, idea copiata dal competitor
            refs = [ID, t['comp_img']]
            prompt = ('Image 1 is our character KAO. Image 2 is a successful YouTube thumbnail: copy its IDEA 100% (situation, what the character does, emotion, objects, other people). '
                      'Draw it as a COMPLETE SCENE in a real place that explains the context at first glance: '
                      f'PLACE: {t.get("luogo") or t.get("scena", "")}. The environment is fully drawn with all its details (walls, furniture, windows, lights, nature...), not a plain or blurred background. '
                      f'MAIN CHARACTER = KAO exactly as image 1: bald round head, same simple face, light skin, magenta long-sleeve shirt, black trousers. {diverso}'
                      f'What KAO does: {t.get("azione", "")}. Emotion, very clear on his face: {t.get("emo", "")}. Objects: {t.get("oggetto", "")}. '
                      + (f'OTHER PEOPLE in the scene: {t.get("persone")}. They are drawn in the same style as KAO (bald round heads, simple faces) but wear NEUTRAL colours (grey, blue, brown, white): only KAO wears magenta. '
                         if t.get('persone') else '') +
                      'The scene fills the LEFT 58% of the image completely, edge to edge, top to bottom; KAO is big and clearly visible in it. '
                      'The RIGHT 42% is a plain solid very dark (almost black) area, completely empty: reserved for a big title. '
                      'Style: the SAME flat 2D cartoon style as image 1 for everything: thick black outlines, flat colours, simple shapes, NO shading gradients, '
                      'NO glow, NO rim light, NO bokeh, NO blur, NO cinematic light effects. Do NOT copy the drawing style or the characters of image 2. '
                      'YouTube thumbnail 16:9. Absolutely NO text, letters or numbers in the image.')
            t['lato_testo'] = 'destra'
    try:
        r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1})
        im = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB')
        im = ImageOps.fit(im, (1280, 720), Image.LANCZOS)
        if t.get('comp_id') and not e_kao(im):   # personaggio non originale: si rifa' una volta, con KAO ancora piu' vincolato
            log('personaggio non e\' KAO, rifaccio:', c['id'])
            r = fal('fal-ai/nano-banana-2/edit', {'prompt': 'IMPORTANT: the ONLY character is EXACTLY the character of the reference image (KAO): bald round head, '
                                                 'light skin, simple face, magenta long-sleeve shirt. No other creature, no green or coloured body. ' + prompt,
                                                 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1})
            im = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
        if APPLICA and not c.get('suff'):
            im.save(os.path.join(BASI, c['id'] + '.jpg'), quality=92)
        lato = 'sinistra' if t.get('lato_testo') == 'sinistra' else 'destra'
        scritta(im, [str(t['riga1']).upper(), str(t['riga2']).upper()], lato, zona_libera(im, lato)).save(p, quality=90)
        log('copertina pronta:', c['id'], t['riga1'], '/', t['riga2'])
        return p
    except Exception as e:
        log('copertina non riuscita', c['id'], str(e)[:150]); return None


with ThreadPoolExecutor(3) as ex:
    fatte = list(ex.map(fai, range(len(cand))))

# ---------- 5) caricamento su YouTube
esiti = []
for c, p in zip(cand, fatte):
    stato = 'non creata' if not p else 'solo anteprima'
    if c.get('variante'):   # non si carica: resta pronta per il Rotatore CTR
        if p:
            shutil.copy(p, os.path.join(VARIANTI, c['id'] + c['suff'] + '.jpg')); log('variante pronta:', c['id'] + c['suff'])
        continue
    if p and APPLICA:
        shutil.copy(p, os.path.join(VARIANTI, c['id'] + '_1.jpg'))
        try:
            http(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={c["id"]}', open(p, 'rb').read(),
                 dict(AUTH, **{'Content-Type': 'image/jpeg'}), metodo='POST')
            stato = 'CARICATA'
        except Exception as e:
            dett = ''
            try:
                dett = e.read().decode()[:300]   # motivo preciso dato da YouTube
            except Exception:
                pass
            stato = 'errore: ' + str(e)[:80] + ' ' + dett.replace('\n', ' ')
            if getattr(e, 'code', 0) == 403:   # YouTube non la accetta via API (es. video passato da un test A/B): pronta da caricare a mano
                os.makedirs(A_MANO, exist_ok=True)
                os.replace(p, os.path.join(A_MANO, c['id'] + '.jpg'))
                stato = 'DA CARICARE A MANO (kao_copertine/a_mano): ' + stato
            else:
                for x in (p, os.path.join(BASI, c['id'] + '.jpg')):   # non caricata: al prossimo giro si riprova
                    if os.path.exists(x):
                        os.remove(x)
    t = testi.get(cand.index(c)) or {}
    esiti.append([time.strftime('%Y-%m-%d'), c['id'], c['titolo'], c['quando'] or c['motivo'], f'{t.get("riga1", "")} {t.get("riga2", "")}', stato])
    log(stato, c['id'], c['titolo'][:50])
with open(os.path.join(BASE, 'cinema_esito.csv'), 'a', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    if f.tell() == 0:
        w.writerow(['data', 'youtube_video_id', 'titolo', 'pubblicazione', 'testo_copertina', 'stato'])
    w.writerows(esiti)

# anteprima: vecchia | nuova
ok = [(c, p) for c, p in zip(cand, fatte) if p and os.path.exists(p)]
if ok:
    tw, th = 480, 270
    S = Image.new('RGB', (tw * 3 + 40, (th + 36) * len(ok) + 10), 'white'); d = ImageDraw.Draw(S); fe = ImageFont.truetype(FONT, 22)
    for i, (c, p) in enumerate(ok):
        y = i * (th + 36) + 5
        tc = testi.get(cand.index(c)) or {}
        if tc.get('comp_id'):
            ci = copertina_yt(tc['comp_id'])
            if ci is not None:
                S.paste(ci.resize((tw, th)), (tw * 2 + 40, y))
        v = os.path.join(VECCHIE, c['id'] + '.jpg')
        try:
            S.paste(ImageOps.fit(Image.open(v).convert('RGB'), (tw, th)), (0, y))
        except Exception:   # copertina vecchia mancante o rovinata: si salta
            pass
        S.paste(Image.open(p).resize((tw, th)), (tw + 20, y))
        d.text((5, y + th + 4), f'{c["quando"]}  {c["titolo"][:60]}', font=fe, fill='black')
    S.save(os.path.join(BASE, 'cinema_anteprima.jpg'), quality=85)
os.remove(FONT)
log('FATTO:', sum(1 for e in esiti if e[-1] == 'CARICATA'), 'caricate su', len(esiti), '| APPLICA =', APPLICA)
