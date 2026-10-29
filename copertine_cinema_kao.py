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
import base64, csv, io, json, os, re, shutil, time, unicodedata, urllib.error, urllib.parse, urllib.request
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
# ---------- modo n8n: copertina del NUOVO video prima del caricamento (n8n la carica insieme al video, come sempre)
N8N = json.loads(E('PAYLOAD', '') or '{}') if E('PAYLOAD', '') else {}
if N8N:
    m_ = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', str(N8N.get('link_competitor') or ''))
    cand = [{'id': 'n8n_' + re.sub(r'[^\w-]', '', str(N8N.get('id') or 'nuovo')), 'titolo': str(N8N.get('titolo') or ''), 'quando': '', 'stato': 'n8n', 'motivo': 'n8n'}]
    COMP = {cand[0]['id']: {'comp': m_.group(1), 'copy': str(N8N.get('copy') or '').strip()}} if m_ else {}
    APPLICA = False   # n8n carica la copertina insieme al video: qui non si carica niente su YouTube
    log('modo n8n: copertina per', cand[0]['titolo'], '| competitor:', m_.group(1) if m_ else 'MANCANTE')
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
TRADUZIONE NATURALE: stesso significato al 100% e stessa forza, ma in italiano CORRETTO e NATURALE, come lo direbbe un italiano. Mai parola per parola: le espressioni idiomatiche si traducono con l'equivalente italiano (es. "POR SI ACASO" = "NON SI SA MAI" / "PER OGNI EVENIENZA", mai "PER SICUREZZA SE MAI"; "GUARDAN TODO POR SI ACASO" = "TENGONO TUTTO, NON SI SA MAI"). Rileggi: la frase deve suonare giusta a un italiano. MAI togliere articoli, preposizioni o parole che servono all'italiano corretto, anche se l'originale e' piu' corto (es. "NO VEN EL MUNDIAL" = "NON GUARDANO IL MONDIALE", MAI "NON GUARDANO MONDIALE").
CONTROLLO: confronta con il testo SCRITTO nell'immagine. Se la traduzione data e' incompleta (mancano parole, es. "HAZLO AUNQUE NO QUIERAS" tradotto solo "FALLO ANCHE SE", oppure manca una data tra parentesi), usa la traduzione COMPLETA di tutte le parole dell'immagine (es. "FALLO ANCHE SE NON VUOI"). Date e numeri tra parentesi vanno in riga2 insieme all'ultima parola.
Dividilo in due righe SENZA cambiare, togliere o aggiungere parole: "riga1" = la prima parte, "riga2" = SOLO l'ultima parola (la parola chiave, andra' su un'etichetta colorata; 2 parole solo se l'ultima ha meno di 3 lettere; se la frase finisce con un'espressione fissa, es. NON SI SA MAI, riga2 e' l'intera espressione). MAIUSCOLO.
{('VARIANTE: questa e\' la copertina numero ' + str(len(c.get('gia') or []) + 1) + ' (le precedenti hanno avuto CTR basso). Il TESTO resta identico. '
   'L\'IMMAGINE deve essere diversa per circa il ' + str(perc) + '% dall\'originale: cambia ' + ('UN solo elemento visivo forte' if perc <= 20 else 'DUE elementi visivi forti') +
   ' (es. l\'oggetto in mano, l\'espressione, il gesto, l\'ambiente sfocato dietro), tutto il resto identico. '
   'Scrivi in "cambi" (in inglese) esattamente cosa cambia.') if perc else ''}
PERSONAGGIO (in inglese, SENZA MAI citare scritte, lettere o riquadri di testo): copia ESATTAMENTE cosa fa il personaggio principale, che diventera' il nostro KAO:
"emo" = emozione ed espressione esatte; "azione" = cosa fa, posa, gesti, mani, caratteristiche speciali (es. tante braccia che tengono oggetti) descritte come se fosse KAO.
VIETATO descrivere l'ASPETTO del personaggio del competitor: niente colore della pelle o del corpo, forma, specie (fagiolo, mostro, animale, creatura), vestiti, capelli. Scrivi sempre "KAO" come soggetto;
"oggetto" = gli oggetti e simboli che tiene o ha accanto (gli stessi della copertina).
"scena" = uno sfondo per il NOSTRO stile cinematografico, coerente con il tema: un ambiente reale sfocato con luci calde e bokeh (es. a cozy study at night with warm lamps). NON copiare lo sfondo o i colori del competitor.
"lato_testo" = dove il competitor ha messo la scritta: "alto" (fascia in alto su tutta o quasi tutta la larghezza, anche sopra un'immagine divisa), "basso" (fascia in basso), "sinistra", "destra" o "centro" (al centro, sopra la linea divisoria).
"luogo" (in inglese) = lo STESSO luogo della copertina competitor (stesso ambiente, stessa ora del giorno, stessa luce, stesso tempo atmosferico), descritto con 4-6 dettagli visibili (es. "mountains at sunset, orange sky, a dirt path"). Mai cambiare luogo, TRANNE un caso: il nostro stile e' SEMPRE un luogo REALE e quotidiano (casa, camera, ufficio, strada, parco, bar...). SE il luogo del competitor e' surreale, onirico, fantastico o astratto (nuvole, cielo, spazio, scale verso il cielo, sogni, mondi immaginari): NON copiarlo, usa il luogo reale e quotidiano dove quella azione succede davvero (es. chi abbraccia il cuscino per dormire: "a cozy bedroom at night, bed with pillows and blanket, bedside lamp, window with the moon"), con 4-6 dettagli visibili. SE lo sfondo del competitor e' vuoto, a tinta unita o quasi senza ambiente: inventa TU un luogo reale e completo, coerente con il tema e con l'azione (es. per chi dimentica i nomi: "a lively party in a living room, guests chatting, string lights, a buffet table"), sempre con 4-6 dettagli visibili. MAI uno sfondo vuoto.
"posa" (in inglese) = il MOVIMENTO e la posa ESATTI del personaggio (corre, salta, e' sdraiato, seduto, di spalle, di profilo; dove guarda; posizione di braccia e gambe) e l'inquadratura (figura intera, mezzo busto, primo piano).
"accessori" (in inglese) = cio' che il personaggio ha addosso OLTRE ai vestiti (cuffie, occhiali, coperta sulle spalle, cappello, zaino...); "" se niente. MAI maglioni, maglie, giacche o altri vestiti: KAO ha SEMPRE la sua maglia magenta.
"grafica" (in inglese) = gli elementi grafici disegnati sopra la scena (frecce rosse e dove puntano, cerchi, punti di domanda, punti esclamativi, nuvolette di pensiero, X, linee di movimento); "" se nessuno.
"composizione" (in inglese) = SOLO se la copertina NON e' una scena unica: com'e' divisa e cosa c'e' in ogni parte (es. "split screen in two halves: LEFT a very messy living room with clothes and dishes everywhere and KAO overwhelmed; RIGHT the same living room perfectly clean and KAO relaxed in an armchair with a cup; the title is in the middle over the dividing line"). Il personaggio compare in OGNI parte dove compare nel competitor. "" se e' una scena unica.
"persone" (in inglese) = le ALTRE persone della situazione (quelle della copertina competitor o quelle che servono a far capire il contesto: genitori che litigano, partner, amici, folla...), cosa fanno e dove stanno; "" se la situazione e' di una persona sola.
Rispondi SOLO JSON: {{"riga1": "...", "riga2": "...", "emo": "...", "oggetto": "...", "scena": "...", "azione": "...", "luogo": "...", "persone": "...", "posa": "...", "accessori": "...", "grafica": "", "composizione": "", "lato_testo": "destra", "cambi": ""}}"""
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
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 3000,
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


SFONDI_TESTO = {   # sfondo dietro la scritta MAGENTA (la scritta resta sempre magenta)
    'fumetto': 'a big white rounded card / comic speech-bubble with a thick black outline, the magenta letters inside it, a small soft shadow under the card.',
    'nero': 'each line sits on its own solid BLACK strip (like a highlighter), tight around the words, slightly tilted; the magenta letters have a thin white outline.',
    'bianco': 'each line sits on its own solid WHITE strip (like a highlighter), tight around the words; the magenta letters have a thick black outline.',
    'ombra': 'NO box: thick black outline around every magenta letter and a soft dark glow/shadow only right behind the words, the rest of the scene stays bright.',
}
SFONDI_NOMI = {'fumetto': 'Cartoncino bianco (fumetto)', 'nero': 'Strisce nere', 'bianco': 'Strisce bianche', 'ombra': 'Solo contorno + ombra'}
SFONDO_TESTO = str(E('SFONDO_TESTO', '') or 'fumetto').strip().lower()
if SFONDO_TESTO not in SFONDI_TESTO:
    SFONDO_TESTO = 'fumetto'
PROVA_SFONDI = str(E('PROVA_SFONDI', '') or ('SI' if 0 < int(E('ULTIMI', '') or 0) <= 2 else 'NO')).upper() == 'SI'   # prova: lo stesso video con i 4 sfondi della scritta


def testo_esatto(im, frase, divisa_ok=False, braccia_extra=False):   # divisa_ok: il competitor e' diviso in parti (composizione), quindi la linea divisoria va bene
    """Claude trascrive la scritta della copertina: deve essere identica alla frase (lettere e numeri), senza altre scritte."""
    buf = io.BytesIO(); im.resize((960, 540)).save(buf, 'JPEG', quality=88)
    try:
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 4000, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': 'Transcribe EXACTLY all the text written in this image, letter by letter, as it is written (do not correct mistakes). '
                                     'Then on the LAST line write CHECK: GRANDE=SI/NO (SI if the title letters are big: each letter at least about 12% of the image height, readable on a phone), '
                                     'BASSO=SI/NO (SI if any part of the title is in the bottom 25% of the image near the left or right corner), '
                                     'CARTONCINO=SI/NO (SI if the title is inside a WHITE rounded card/box with a black outline), '
                                     'SCURO=SI/NO (SI if a large part of the image is darkened by a dark gradient or dark panel), '
                                     'DIVISA=SI/NO (SI if the picture is cut into separate panels by a vertical or horizontal dividing line), '
                                     'COPRE=SI/NO (SI if the title or its card covers the character, his face or an important object of the scene), '
                                     'ANATOMIA=SI/NO (SI if the main character has a correct body: exactly two arms attached to the shoulders and both visible or naturally hidden behind the body, '
                                     'two hands, two legs; NO if an arm is missing, cut off, merged into the body, or there are extra limbs).'}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=120)
        tutto = ''.join(b.get('text', '') for b in rr.get('content', []))
        letto = tutto.split('CHECK:')[0]
        chk = tutto.split('CHECK:')[1].upper() if 'CHECK:' in tutto else ''
        c_ = chk.replace(' ', '')
        if 'GRANDE=NO' in c_ or 'BASSO=SI' in c_ or (not divisa_ok and 'DIVISA=SI' in c_) or 'COPRE=SI' in c_ or (not braccia_extra and 'ANATOMIA=NO' in c_) or (SFONDO_TESTO == 'fumetto' and ('CARTONCINO=NO' in c_ or 'SCURO=SI' in c_)):
            log('    scritta piccola, troppo in basso o fuori stile (cartoncino bianco, niente lato scuro):', chk.strip()[:90]); return False
        norm = lambda x: re.sub(r'[^A-Z0-9]', '', x.upper().replace('À', 'A').replace('È', 'E').replace('É', 'E').replace('Ì', 'I').replace('Ò', 'O').replace('Ù', 'U'))
        ok = norm(letto) == norm(frase)
        if not ok:
            log('    scritta letta:', letto.strip()[:80], '| voluta:', frase)
        return ok
    except Exception as e:
        log('controllo scritta non riuscito:', str(e)[:100]); return False


def zona_libera(im, lato):
    """Claude guarda l'immagine finita e indica il rettangolo LIBERO piu' grande (niente volto, corpo, braccia od oggetti) per il testo."""
    buf = io.BytesIO(); im.resize((768, 432)).save(buf, 'JPEG', quality=85)
    dom = (f'This is a YouTube thumbnail without text. We must add a 2-line title on the {"LEFT" if lato == "sinistra" else "RIGHT"} side. '
           'Find the LARGEST rectangle on that side that is EMPTY background: it must NOT cover the face, body, arms, hands or any object, not even partially. '
           'Keep a small margin from them, but make the rectangle as BIG as possible (the title must be huge, readable on a phone). Avoid the bottom-right corner (last 25% of height on the right 30% of width: video timestamp). '
           'Answer ONLY JSON with percentages of width/height: {"x0": 0, "y0": 0, "x1": 0, "y1": 0}')
    try:
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 3000,
                  'messages': [{'role': 'user', 'content': [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
                                                            {'type': 'text', 'text': dom}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=200)
        tt = ''.join(b.get('text', '') for b in rr.get('content', []))
        z = json.loads(tt[tt.find('{'): tt.rfind('}') + 1])
        z = [float(z[k]) for k in ('x0', 'y0', 'x1', 'y1')]
        z = [max(0.0, min(100.0, v * (100 if max(z) <= 1.0 else 1))) / 100 for v in z]   # a volte risponde 0-1 invece che 0-100
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


def scurisci_destra(im):
    """Sfumatura scura da meta' immagine verso destra (come le vecchie copertine): la scena resta visibile, la scritta si legge."""
    W, Hh = im.size
    m = Image.new('L', (W, 1))
    for x in range(W):
        f = min(1.0, max(0.0, (x / W - .40) / .22))
        m.putpixel((x, 0), int(205 * f))
    m = m.resize((W, Hh))
    return Image.composite(Image.new('RGB', im.size, (8, 8, 12)), im.convert('RGB'), m)


EVID = tuple(int(x) for x in (E('EVID_COLORE', '') or '255,214,10').split(','))   # evidenziatore sotto la scritta (come il competitor: giallo)
EVID_TESTO = tuple(int(x) for x in (E('EVID_TESTO', '') or '0,0,0').split(','))    # colore delle lettere (nero)


def scritta_evidenziata(im, frase, lato='destra', zona=None):
    """Come il competitor: lettere nere su strisce gialle (una per riga), il resto della copertina resta ben visibile. Mai sotto l'orario di YouTube."""
    W, Hh = im.size
    if lato == 'sinistra':
        x0, x1, y0, y1 = int(W * .03), int(W * .52), int(Hh * .06), int(Hh * .92)
    else:
        x0, x1, y0, y1 = int(W * .50), int(W * .97), int(Hh * .06), int(Hh * .74)
    if zona:   # spazio libero indicato da Claude, dentro il lato giusto
        zx0, zy0, zx1, zy1 = int(W * zona[0]), int(Hh * zona[1]), int(W * zona[2]), int(Hh * zona[3])
        if zx1 - zx0 > W * .25 and zy1 - zy0 > Hh * .30:
            x0, x1 = max(x0, zx0), min(x1, zx1)
            y0, y1 = max(y0, zy0), min(y1, zy1)
    larg, alt = x1 - x0, y1 - y0
    F = lambda k: ImageFont.truetype(FONT, k)
    parole = frase.upper().split(); n = len(parole)
    best = None
    for maschera in range(1 << max(0, n - 1)):
        righe, cur = [], [parole[0]]
        for i in range(1, n):
            if maschera >> (i - 1) & 1:
                righe.append(' '.join(cur)); cur = [parole[i]]
            else:
                cur.append(parole[i])
        righe.append(' '.join(cur))
        if len(righe) > 5:
            continue
        lo, hi = 20, 300
        while lo < hi:
            k = (lo + hi + 1) // 2
            if max(F(k).getlength(r) for r in righe) + k * .36 <= larg and len(righe) * k * 1.22 <= alt:
                lo = k
            else:
                hi = k - 1
        if not best or lo > best[0]:
            best = (lo, righe)
    k, righe = best
    f = F(k); padx, pady, passo = k * .18, k * .08, k * 1.22
    y = y0 + (alt - len(righe) * passo) / 2
    cx = (x0 + x1) / 2
    base = im.convert('RGBA')
    ombra = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ombra)
    for j, r in enumerate(righe):
        w = f.getlength(r); yy = y + j * passo
        do.rectangle((cx - w / 2 - padx + 6, yy - pady + 7, cx + w / 2 + padx + 6, yy + k * 1.08 + pady + 7), fill=(0, 0, 0, 120))
    base.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(7)))
    dr = ImageDraw.Draw(base)
    for j, r in enumerate(righe):
        w = f.getlength(r); yy = y + j * passo
        dr.rectangle((cx - w / 2 - padx, yy - pady, cx + w / 2 + padx, yy + k * 1.08 + pady), fill=EVID)
        dr.text((cx, yy + k * .02), r, font=f, fill=EVID_TESTO, anchor='mt')
    return base.convert('RGB')


MAG_TESTO = (236, 0, 214)


def ingrandisci_kao(im, lato_testo='destra'):
    """KAO deve occupare quasi tutta l'altezza (si vede bene da telefono). Claude trova il riquadro di KAO; se e' piu' basso dell'85%
    dell'altezza si fa uno zoom (max 1,6x) centrato su di lui, lasciando spazio per la scritta dal lato giusto. Esce sempre a 1280x720."""
    W0, H0 = im.size
    if lato_testo in ('alto', 'basso'):   # scritta su una fascia: l'immagine resta intera, come il competitor
        return im.resize((1280, 720), Image.LANCZOS)
    try:
        buf = io.BytesIO(); im.resize((768, 432)).save(buf, 'JPEG', quality=85)
        rr = http('https://api.anthropic.com/v1/messages', {'model': E('MODELLO_AI', 'claude-sonnet-5-5'), 'max_tokens': 1500, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': 'Find the main bald cartoon character in the magenta shirt (KAO). Give the tight bounding box of his WHOLE visible body '
                                     '(head included, plus anything he holds). Answer ONLY JSON with percentages of width/height: {"x0":0,"y0":0,"x1":0,"y1":0}'}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=120)
        tt = ''.join(b.get('text', '') for b in rr.get('content', []))
        z = json.loads(tt[tt.find('{'): tt.rfind('}') + 1]); z = [float(z[k]) for k in ('x0', 'y0', 'x1', 'y1')]
        z = [v / 100 if max(z) > 1.0 else v for v in z]
        alt = max(0.05, z[3] - z[1])
        s_ = max(1.0, min(1.6, 0.88 / alt))
        if s_ > 1.03:
            cw, ch = W0 / s_, H0 / s_
            cy = (z[1] + z[3]) / 2 * H0
            y0 = max(0, min(H0 - ch, z[1] * H0 - ch * .05 if alt * s_ < .95 else cy - ch / 2))   # la testa resta in alto, con un filo d'aria
            cx = (z[0] + z[2]) / 2 * W0
            # KAO resta nella sua meta': la scritta va dall'altro lato
            x0 = cx - cw * (0.30 if lato_testo == 'destra' else 0.70)
            x0 = max(0, min(W0 - cw, x0))
            im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch)))
            log(f'  KAO era alto il {alt:.0%}: zoom {s_:.2f}x')
    except Exception as e:
        log('  zoom su KAO non riuscito:', str(e)[:100])
    return im.resize((1280, 720), Image.LANCZOS)


def scritta_cartoncino(im, frase, lato='destra', zona=None):
    """Riserva nello stile approvato: frase magenta su cartoncino bianco arrotondato con bordo nero e ombra, grande, mai negli angoli bassi."""
    W, Hh = im.size
    x0, x1 = (int(W * .025), int(W * .53)) if lato == 'sinistra' else (int(W * .47), int(W * .975))
    y0, y1 = int(Hh * .04), (int(Hh * .90) if lato == 'sinistra' else int(Hh * .76))   # in basso a destra c'e' la durata del video
    if lato in ('alto', 'basso'):   # fascia come il competitor: larga e bassa, la scena sotto resta visibile
        x0, x1 = int(W * .05), int(W * .95)
        y0, y1 = (int(Hh * .03), int(Hh * .30)) if lato == 'alto' else (int(Hh * .66), int(Hh * .90))
        if lato == 'basso':
            x1 = int(W * .78)   # mai sotto la durata del video
        zona = None
    if zona:
        zx0, zx1 = int(W * zona[0]), int(W * zona[2])
        if zx1 - zx0 > W * .38:   # la zona libera restringe la scritta solo se resta comunque grande
            x0, x1 = max(x0, zx0), min(x1, zx1)
    pad = int(W * .016)
    larg, alt = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
    F = lambda k: ImageFont.truetype(FONT, k)
    parole = frase.upper().split(); n = len(parole); best = None
    for maschera in range(1 << max(0, n - 1)):
        righe, cur = [], [parole[0]]
        for i in range(1, n):
            if maschera >> (i - 1) & 1:
                righe.append(' '.join(cur)); cur = [parole[i]]
            else:
                cur.append(parole[i])
        righe.append(' '.join(cur))
        if len(righe) > 4 or (len(righe) > 1 and any(len(r) <= 2 for r in righe)):   # niente righe con una parolina sola (IL, DI, A...)
            continue
        lo, hi = 20, 300
        while lo < hi:
            k = (lo + hi + 1) // 2
            if max(F(k).getlength(r) for r in righe) <= larg and altezza_righe(F(k), righe)[2] <= alt:
                lo = k
            else:
                hi = k - 1
        if not best or lo > best[0]:
            best = (lo, righe)
    k, righe = best
    senza = lambda r: ''.join(ch for ch in unicodedata.normalize('NFD', r) if unicodedata.category(ch) != 'Mn')

    def misure(k):   # centratura in altezza sul CORPO delle lettere: l'accento di É/À sta nel margine sopra, che resta uguale a quello sotto
        f = F(k); bb, gap, _ = altezza_righe(f, righe)
        bn = [f.getbbox(senza(r), anchor='ls') for r in righe]
        ext = [max(0, n[1] - a[1]) for n, a in zip(bn, bb)]
        hn = sum(n[3] - n[1] for n in bn) + sum(gap + e for e in ext[1:])
        vpad = pad + (ext[0] + pad * .35 if ext[0] else 0)
        return f, gap, bn, ext, hn, vpad
    f, gap, bn, ext, hn, vpad = misure(k)
    while hn + 2 * vpad > (y1 - y0) and k > 24:   # con il margine per l'accento deve stare comunque nello spazio
        k -= 2; f, gap, bn, ext, hn, vpad = misure(k)
    wt = max(f.getlength(r) for r in righe)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = (cx - wt / 2 - pad, cy - hn / 2 - vpad, cx + wt / 2 + pad, cy + hn / 2 + vpad)
    base = im.convert('RGBA')
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((box[0] + 8, box[1] + 10, box[2] + 8, box[3] + 10), radius=int(pad * 1.4), fill=(0, 0, 0, 110))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    dr = ImageDraw.Draw(base)
    dr.rounded_rectangle(box, radius=int(pad * 1.4), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=max(4, k // 18))
    y = cy - hn / 2
    for i, (r, n) in enumerate(zip(righe, bn)):   # ogni riga sotto la precedente, con lo spazio per i suoi accenti: le lettere non si toccano mai
        if i:
            y += gap + ext[i]
        dr.text((cx, y - n[1]), r, font=f, fill=MAG_TESTO, anchor='ms')
        y += n[3] - n[1]
    return base.convert('RGB')   # magenta delle vecchie copertine di successo (come la maglia di KAO)


def altezza_righe(f, righe):
    """Ingombro reale di ogni riga (dalla cima degli accenti al fondo delle lettere) + spazio tra le righe = altezza totale della scritta."""
    bb = [f.getbbox(r, anchor='ls') for r in righe]
    gap = f.size * .16
    return bb, gap, sum(b[3] - b[1] for b in bb) + gap * (len(righe) - 1)


def scritta_magenta(im, frase, zona=None):
    """Stile delle vecchie copertine di successo: la frase INTERA in magenta, Anton maiuscolo, su piu' righe, piu' grande possibile, centrata nel fondo scuro a destra.
    Mai sotto l'orario di YouTube (angolo in basso a destra)."""
    W, Hh = im.size
    x0, x1, y0, y1 = int(W * .48), int(W * .97), int(Hh * .05), int(Hh * .74)
    if zona:   # mai sopra KAO o gli oggetti: la scritta parte dopo di loro (al massimo dal 62%)
        x0 = min(int(W * .62), max(x0, int(W * zona[0]) + 12))
    larg, alt = x1 - x0, y1 - y0
    F = lambda k: ImageFont.truetype(FONT, k)
    parole = frase.upper().split()
    n = len(parole)
    best = None
    for maschera in range(1 << max(0, n - 1)):   # tutti i modi di andare a capo
        righe, cur = [], [parole[0]]
        for i in range(1, n):
            if maschera >> (i - 1) & 1:
                righe.append(' '.join(cur)); cur = [parole[i]]
            else:
                cur.append(parole[i])
        righe.append(' '.join(cur))
        if len(righe) > 6:
            continue
        lo, hi = 20, 400
        while lo < hi:   # grandezza massima che entra
            k = (lo + hi + 1) // 2
            if max(F(k).getlength(r) for r in righe) <= larg and len(righe) * k * .98 <= alt:
                lo = k
            else:
                hi = k - 1
        if not best or lo > best[0]:
            best = (lo, righe)
    k, righe = best
    f = F(k); passo = k * .98
    y = y0 + (alt - len(righe) * passo) / 2
    cx = (x0 + x1) / 2
    base = im.convert('RGBA')
    ombra = Image.new('RGBA', base.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ombra)
    for j, r in enumerate(righe):
        do.text((cx + 5, y + j * passo + 6), r, font=f, fill=(0, 0, 0, 200), anchor='mt')
    base.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(6)))
    dr = ImageDraw.Draw(base)
    for j, r in enumerate(righe):
        dr.text((cx, y + j * passo), r, font=f, fill=MAG_TESTO, anchor='mt', stroke_width=max(3, k // 18), stroke_fill=NERO)
    return base.convert('RGB')


VECCHIE_INIZIO = sorted(f for f in os.listdir(VECCHIE) if f.endswith('.jpg'))   # copertine vecchie gia' salvate nel repo
_stile_ok = {}


def stile_vecchio(path):
    """True se la copertina e' nello stile vecchio che funzionava (KAO piatto in una scena disegnata + frase magenta), non quella cinematografica sfocata."""
    if path in _stile_ok:
        return _stile_ok[path]
    ok = False
    try:
        buf = io.BytesIO(); Image.open(path).convert('RGB').resize((640, 360)).save(buf, 'JPEG', quality=80)
        rr = http('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 20, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': 'Is this thumbnail a flat 2D cartoon scene with a fully drawn, sharp environment (NOT a blurred/bokeh cinematic background) '
                                     'and a big title written ALL in magenta letters (not white letters with a magenta label)? Answer only SI or NO.'}]}]},
                  {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=120)
        ok = 'SI' in ''.join(b.get('text', '') for b in rr.get('content', [])).upper()
    except Exception as e:
        log('controllo stile vecchio non riuscito:', str(e)[:100])
    _stile_ok[path] = ok
    return ok


def rif_data(pth):
    buf = io.BytesIO(); Image.open(pth).convert('RGB').resize((1024, 576)).save(buf, 'JPEG', quality=88)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def riferimento_stile(vid):
    """La vecchia copertina del video (se e' nello stile vecchio), altrimenti un'altra vecchia copertina del canale nello stile vecchio."""
    for f in [vid + '.jpg'] + [x for x in VECCHIE_INIZIO if x != vid + '.jpg'][:12]:
        pth = os.path.join(VECCHIE, f)
        if f in VECCHIE_INIZIO and os.path.exists(pth) and stile_vecchio(pth):
            return pth, f == vid + '.jpg'
    return None, False


def fai(i):
    c, t = cand[i], testi.get(i) or {}
    if c.get('variante') and not t.get('comp_id'):   # varianti 20%/30% solo per i video con il competitor nel foglio
        return None
    r1, r2 = str(t.get('riga1') or '').strip(), str(t.get('riga2') or '').strip()
    if not r2 and len(r1.split()) >= 2:   # tutto su una riga: l'ultima parola va sull'etichetta
        r1, r2 = ' '.join(r1.split()[:-1]), r1.split()[-1]
    if not r1 and len(r2.split()) >= 2:
        r1, r2 = ' '.join(r2.split()[:-1]), r2.split()[-1]
    t['riga1'], t['riga2'] = r1, r2
    testi[i] = t
    if not t.get('riga1') or not t.get('riga2'):
        log('testo mancante per', c['id']); return None
    p = os.path.join(NUOVE, c['id'] + c.get('suff', '') + '.jpg')
    approvata = os.path.join(BASE, 'piatto_prova', c['id'] + '.jpg')
    if APPLICA and STILE == 'piatto' and not c.get('suff') and os.path.exists(approvata):   # si carica ESATTAMENTE la copertina vista e approvata in prova
        shutil.copy(approvata, p); shutil.copy(approvata, os.path.join(BASI, c['id'] + '.jpg')); log('copertina approvata in prova:', c['id']); return p
    rifai_id = [x.strip() for x in (E('RIFAI_ID', '') or '').split(',') if x.strip()]
    if APPLICA and c['id'] in rifai_id:
        rifai_id = []
    if not APPLICA and STILE == 'piatto' and not c.get('suff') and os.path.exists(approvata) and str(E('RIFAI_PROVE', '') or 'NO').upper() != 'SI' and c['id'] not in rifai_id:
        log('prova gia\' fatta, la tengo:', c['id']); return approvata   # niente spesa: le copertine gia' viste non si rifanno
    if STILE == 'piatto' and not t.get('comp_id'):   # senza il video competitor nella scheda "Copertine" non c'e' niente da copiare: la copertina resta com'e'
        log('nessun competitor nella scheda Copertine, copertina NON cambiata:', c['id'], c['titolo'][:50]); return None
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
        if STILE == 'piatto':   # la VECCHIA copertina (stile che funzionava) aggiornata: stessa grafica, ma scena/posa/oggetti come il competitor
            rif, sua = riferimento_stile(c['id'])
            refs = ([rif_data(rif)] if rif else []) + [ID]   # NIENTE immagine del competitor: solo la descrizione
            t['rif_stile'] = rif or ''
            lc_ = str(t.get('lato_testo_comp') or '')
            lato_c = lc_ if lc_ in ('alto', 'basso') else ('sinistra' if lc_ == 'sinistra' else ('centro' if lc_ == 'centro' and t.get('composizione') else 'destra'))
            fascia = {'alto': 'TOP', 'basso': 'BOTTOM'}.get(lato_c)   # scritta su una fascia, come il competitor: la scena resta tutta visibile
            prompt = (('Image 1 is our OLD thumbnail' + (' of this video' if sua else '') + ': keep EXACTLY its graphic style: same flat 2D cartoon drawing, same rich colours and warm lighting, '
                       'same size and look of KAO, same detailed environment drawing. IGNORE its old title and its dark shaded side: no dark gradient, everything bright and visible. Image 2 is our character KAO. '
                       if rif else 'Image 1 is our character KAO. Flat 2D cartoon, thick black outlines, rich warm colours, fully drawn detailed environment. ') +
                      'Draw a NEW scene in that style with this content (it must match exactly): '
                      f'PLACE: {t.get("luogo") or t.get("scena", "")} (same time of day and light). '
                      f'KAO POSE AND MOVEMENT: {t.get("posa", "")}. ' + (f'KAO WEARS: {t.get("accessori")}. ' if t.get('accessori') else '') +
                      f'WHAT KAO DOES: {t.get("azione", "")}. EMOTION, very clear on his face: {t.get("emo", "")}. OBJECTS: {t.get("oggetto", "")}. {diverso}'
                      + (f'OTHER PEOPLE: {t.get("persone")} (same style as KAO, neutral clothes, only KAO wears magenta). ' if t.get('persone') else '') +
                      (f'GRAPHIC ELEMENTS drawn over the scene, copy them exactly (same position and direction): {t.get("grafica")}. ' if t.get('grafica') else '') +
                      'KAO has a correct body: TWO arms attached to the shoulders (both visible, never missing or cut), two hands, two legs. KAO is exactly as in the KAO reference: bald round head, simple face, light skin, ALWAYS his magenta long-sleeve shirt (never a sweater, jacket or other top), black trousers. '
                      + (f'In the {fascia} 35% of the image there are NO heads, faces or important objects (a title band will be placed there): the SAME scene simply continues there, seamlessly '
                         '(the same sky, wall, ceiling or street of each part, drawn continuously up to the edge of the image): NO separate band, NO stripe, NO horizontal cut line, NO frame, NO empty margin. '
                         'All characters and objects stay in the rest of the image, fully visible. ' if fascia else '')
                      + (f'COMPOSITION (copy it exactly, KAO appears in every part where the character appears): {t.get("composizione")}. The title goes where described, never covering KAO or faces. Everything bright and fully visible. '
                         'When the parts show DIFFERENT people or DIFFERENT situations, make it obvious at a glance: each different person has clearly different clothes (different colour and type of top), hair and look, '
                         'and each part has a clearly DIFFERENT TYPE of place and light, never the same kind of place twice (e.g. a warm home living room vs a city street at night, an office vs a park). ' if t.get('composizione') else
                         'The scene fills the WHOLE image, bright and fully visible everywhere. KAO is big and close to the camera, his face clearly readable on a phone. ' if fascia else f'The scene fills the WHOLE image, bright and fully visible everywhere (NO dark side, NO dark gradient). KAO, people and important objects stay in the {"RIGHT" if lato_c == "sinistra" else "LEFT"} 50%. KAO is VERY BIG and close to the camera: '
                      'he fills 85-95% of the image HEIGHT (from the top of his head down to his knees or waist), his face large and clearly readable on a phone. '                      f'The {"LEFT" if lato_c == "sinistra" else "RIGHT"} 50% simply continues the same environment (wall, sky, room, landscape), bright, with nothing important: a title will go there. ') +
                      ('' if t.get('composizione') else 'ONE single continuous scene filling the whole image: NO split screen, NO vertical dividing line, NO panels, NO frames, NO borders. ') +
                      'The background is ALWAYS a complete, fully drawn, detailed real place (room, street, garage, park...) filling the whole image: NEVER a plain, empty, cream or single-colour background. '
                      'NO blur, NO bokeh, NO glow, NO rim light. Remove ALL text: absolutely NO text, letters or numbers in the image. YouTube thumbnail 16:9.')
            t['lato_testo'] = lato_c
    if STILE == 'piatto' and str(E('TESTO_STILE', '') or 'cartoncino').lower() == 'disegnata':   # (spento di default dal 27/10: Nano Banana faceva le lettere troppo piccole) la scritta la disegna Nano Banana
        frase = f"{t['riga1']} {t['riga2']}".upper().strip()
        lato_t = {'sinistra': 'LEFT', 'centro': 'CENTRE'}.get(t.get('lato_testo'), 'RIGHT')
        stili = list(SFONDI_TESTO) if PROVA_SFONDI else [SFONDO_TESTO]
        fatte_s = {}
        for st_ in stili:
            pt = prompt.replace('Remove ALL text: absolutely NO text, letters or numbers in the image.',
                                f'TITLE: write EXACTLY this Italian text, nothing else: "{frase}". Put it ' + ('in the CENTRE, over the dividing line between the parts,' if lato_t == 'CENTRE' else f'on the {lato_t} side, in the empty part of the scene,') + f' VERY BIG (letters at least 15% of the image height, '
                                'the title block about 40-45% of the image width), on 2-4 lines, centred, inside the UPPER 72% of the image (never in the bottom corners), '
                                'readable on a phone: bold condensed uppercase letters (like the Anton font) in bright MAGENTA (the same magenta as KAO\'s shirt). '
                                f'Behind the title: {SFONDI_TESTO[st_]} High impact, clean, professional, like a viral YouTube thumbnail. '
                                'Break the lines only between word groups that belong together (e.g. "TENGONO TUTTO / NON SI SA MAI"), never split an expression and never leave a short word alone on a line. '
                                'The title card sits on an EMPTY area of the scene (wall, sky, floor): it never covers KAO, faces, the objects of the scene or the graphic elements, '
                                'and stays out of the bottom-left and bottom-right corners (video timer). '
                                'No other text anywhere. Spell every word exactly.')
            for tent in range(2 if PROVA_SFONDI else 3):
                try:
                    r = fal('fal-ai/nano-banana-2/edit', {'prompt': pt, 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1})
                    im = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (1280, 720), Image.LANCZOS)
                    extra = bool(re.search(r'(extra|multiple|many|six|four|several)\s+arms', str(t.get('azione', '')) + ' ' + str(t.get('posa', '')), re.I))
                    if testo_esatto(im, frase, bool(t.get('composizione')), extra) and e_kao(im):
                        fatte_s[st_] = im
                        log('copertina pronta (scritta disegnata):', c['id'], st_, frase, f'tentativo {tent + 1}')
                        break
                    log(f'  {c["id"]} {st_}: scritta o personaggio non perfetti, rifaccio ({tent + 1})')
                except Exception as e:
                    log('  tentativo non riuscito:', str(e)[:120])
        if fatte_s and APPLICA and not c.get('suff'):   # segno "fatta": il giro automatico non la rifa'
            next(iter(fatte_s.values())).save(os.path.join(BASI, c['id'] + '.jpg'), quality=90)
        if PROVA_SFONDI and fatte_s:   # confronto degli sfondi della scritta: una griglia per video
            tw, th = 640, 360
            G = Image.new('RGB', (tw * 2 + 10, (th + 40) * 2), 'white'); dg = ImageDraw.Draw(G); fg = ImageFont.truetype(FONT, 26)
            for n_, st_ in enumerate(stili):
                x_, y_ = (n_ % 2) * (tw + 10), (n_ // 2) * (th + 40)
                dg.text((x_ + 6, y_ + 4), f'{n_ + 1}) {SFONDI_NOMI[st_]}', font=fg, fill='black')
                if st_ in fatte_s:
                    G.paste(fatte_s[st_].resize((tw, th)), (x_, y_ + 38))
                    fatte_s[st_].save(os.path.join(NUOVE, f'{c["id"]}_{st_}.jpg'), quality=90)
            G.save(os.path.join(NUOVE, f'sfondi_{c["id"]}.jpg'), quality=88)
            first = next(iter(fatte_s.values())); first.save(p, quality=90)
            return p
        if fatte_s:
            fatte_s[SFONDO_TESTO].save(p, quality=90)
            return p
        log(f'  {c["id"]}: tentativi non perfetti, scrivo io la scritta')
    try:
        try:
            r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
        except Exception as e_:   # es. HTTP 422: si riprova solo con il KAO di riferimento
            log('  immagine senza scritta non riuscita (' + str(e_)[:60] + '), riprovo solo con KAO')
            r = fal('fal-ai/nano-banana-2/edit', {'prompt': prompt, 'image_urls': [ID], 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
        im = Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB')
        im = ImageOps.fit(im, (2560, 1440), Image.LANCZOS)
        if t.get('comp_id') and not e_kao(im):   # personaggio non originale: si rifa' una volta, con KAO ancora piu' vincolato
            log('personaggio non e\' KAO, rifaccio:', c['id'])
            r = fal('fal-ai/nano-banana-2/edit', {'prompt': 'IMPORTANT: the ONLY character is EXACTLY the character of the reference image (KAO): bald round head, '
                                                 'light skin, simple face, magenta long-sleeve shirt. No other creature, no green or coloured body. ' + prompt,
                                                 'image_urls': refs, 'aspect_ratio': '16:9', 'resolution': '2K', 'output_format': 'jpeg', 'num_images': 1})
            im = ImageOps.fit(Image.open(io.BytesIO(http(r['images'][0]['url'], raw=True))).convert('RGB'), (2560, 1440), Image.LANCZOS)
        im = ingrandisci_kao(im, t.get('lato_testo') if t.get('lato_testo') in ('sinistra', 'alto', 'basso') else 'destra')   # KAO quasi a tutta altezza (zoom), poi 1280x720
        if APPLICA and not c.get('suff'):
            im.save(os.path.join(BASI, c['id'] + '.jpg'), quality=92)
        lato = t.get('lato_testo') if t.get('lato_testo') in ('sinistra', 'alto', 'basso') else 'destra'
        if STILE == 'piatto' and str(E('TESTO_STILE', '') or 'cartoncino').lower() == 'evidenziata':   # come il competitor: lettere nere su strisce gialle, copertina tutta visibile
            scritta_evidenziata(im, f"{t['riga1']} {t['riga2']}", lato, zona_libera(im, lato)).save(p, quality=90)
        elif STILE == 'piatto':   # DEFAULT dal 27/10: scritta magenta su cartoncino bianco scritta dal codice, sempre la piu' grande possibile (leggibile da telefono)
            scritta_cartoncino(im, f"{t['riga1']} {t['riga2']}", lato, None if lato in ('alto', 'basso') else zona_libera(im, lato)).save(p, quality=90)
        else:
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
    S = Image.new('RGB', ((tw * 2 + 20) if STILE == 'piatto' else (tw * 3 + 40), (th + 36) * len(ok) + 10), 'white'); d = ImageDraw.Draw(S); fe = ImageFont.truetype(FONT, 22)
    for i, (c, p) in enumerate(ok):
        y = i * (th + 36) + 5
        tc = testi.get(cand.index(c)) or {}
        if tc.get('comp_id'):
            ci = copertina_yt(tc['comp_id'])
            if ci is not None:
                S.paste(ci.resize((tw, th)), ((tw + 20) if STILE == 'piatto' else (tw * 2 + 40), y))
        if STILE == 'piatto':   # 2 colonne: nuova | competitor
            S.paste(Image.open(p).resize((tw, th)), (0, y))
        else:
            v = os.path.join(VECCHIE, c['id'] + '.jpg')
            try:
                S.paste(ImageOps.fit(Image.open(v).convert('RGB'), (tw, th)), (0, y))
            except Exception:   # copertina vecchia mancante o rovinata: si salta
                pass
            S.paste(Image.open(p).resize((tw, th)), (tw + 20, y))
        d.text((5, y + th + 4), f'{c["quando"]}  {c["titolo"][:60]}', font=fe, fill='black')
    S.save(os.path.join(BASE, 'cinema_anteprima.jpg'), quality=85)
if N8N and N8N.get('resume_url'):   # risposta a n8n: link pubblico della copertina (oppure errore -> n8n usa la copertina di sempre)
    risposta = {'status': 'failed', 'message': 'copertina non creata'}
    try:
        pp = next((p for c, p in zip(cand, fatte) if p and os.path.exists(p)), None)
        if pp:
            h_ = {'Authorization': 'Key ' + E('FAL_KEY', '')}
            ini = http('https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3', {'content_type': 'image/jpeg', 'file_name': 'copertina_kao.jpg'}, h_)
            urllib.request.urlopen(urllib.request.Request(ini['upload_url'], data=open(pp, 'rb').read(), method='PUT', headers={'Content-Type': 'image/jpeg'}), timeout=300).read()
            risposta = {'status': 'done', 'url': ini['file_url']}
    except Exception as e:
        risposta = {'status': 'failed', 'message': str(e)[:300]}
    try:
        http(N8N['resume_url'], {'copertina': risposta}, raw=True)
        log('risposta a n8n:', risposta)
    except Exception as e:
        log('risposta a n8n non riuscita:', str(e)[:200])
os.remove(FONT)
log('FATTO:', sum(1 for e in esiti if e[-1] == 'CARICATA'), 'caricate su', len(esiti), '| APPLICA =', APPLICA)
