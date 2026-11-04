#!/usr/bin/env python3
"""RADAR (al posto del workflow n8n "MULTICHANNEL - RADAR YouTube Scoperta"), ogni mattina su GitHub.
Legge la scheda Impostazioni del foglio RADAR e aggiorna le schede come faceva n8n:
  ricerche YouTube (parole, parola|durata, trend Pexels, SIMILI, categorie) -> statistiche dei video -> filtri video
  -> canali (iscritti, rapporto views/iscritti, numero video) -> data del PRIMO VIDEO ancora online (eta')
  -> valutazione di Claude sui fotogrammi (solo canali che hanno passato TUTTI i filtri, dentro budget_giorno)
  -> materiale gratis (clip Pexels / Archive.org) -> Video trovati (append) -> Storico (append, una riga al giorno per canale)
  -> Canali (riscritta per channel_id, "⭐ Scelta" e "Note" non si toccano mai) -> TREND.
La sola parte a pagamento e' Claude (valutazione e argomenti/trend): budget_giorno vuoto o 0 = nessuna chiamata.
PROVA=SI: massimo 2 ricerche, stampa cosa scriverebbe e non scrive niente (ne' foglio ne' file).
SENZA_CLAUDE=SI: budget forzato a 0 qualunque sia il valore nel foglio (per le prove)."""
import datetime as dt, json, os, re, statistics, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request, base64
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

E = os.environ.get
FOGLIO = E('RADAR_FOGLIO', '1cOLkymyVmU2SQYZWMNMPb99AHkk4qdH8RKMUPtwhcLI')
PROVA = (E('PROVA') or 'NO').strip().upper() == 'SI'
SENZA_CLAUDE = (E('SENZA_CLAUDE') or 'NO').strip().upper() == 'SI'
MAX_RICERCHE = int(re.sub(r'\D', '', E('MAX_RICERCHE') or '') or 0)
YT_KEY = E('YT_API_KEY_RADAR', '')
CART = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'radar')
F_VAL = os.path.join(CART, 'valutazioni.json')    # valutazioni gia' pagate: un canale si valuta UNA volta sola
F_SPESA = os.path.join(CART, 'spesa_claude.json')   # spesa Claude giorno per giorno (per budget_giorno)
OGGI_D = dt.datetime.now(ZoneInfo('Europe/Rome')).date()
OGGI = OGGI_D.isoformat()
ORA = dt.datetime.now(dt.timezone.utc)
MAX_PEXELS = 100       # richieste Pexels per giro (la chiave e' la stessa dei video: limite 200 all'ora)
QUOTA_YT = 9300        # unita' YouTube massime per giro (limite giornaliero 10000)
LINGUA = {'IT': 'it', 'US': 'en', 'GB': 'en', 'CA': 'en', 'AU': 'en', 'ES': 'es', 'FR': 'fr', 'DE': 'de', 'BR': 'pt', 'PT': 'pt'}
CAT = {1: 'Film e animazione', 2: 'Auto e veicoli', 10: 'Musica', 15: 'Animali', 17: 'Sport', 19: 'Viaggi ed eventi', 20: 'Videogiochi',
       22: 'Persone e blog', 23: 'Comedy', 24: 'Intrattenimento', 25: 'Notizie e politica', 26: 'Guide e stile', 27: 'Istruzione',
       28: 'Scienza e tecnologia', 29: 'Non profit e attivismo'}
RIFARE = {'COPIA': '✅ SÌ', 'POCO MATERIALE': '⚠️ poco materiale', 'SCARTA': '❌ NO', 'DA VERIFICARE': '❓ da valutare'}
CON_COSA = {'PEXELS': 'Pexels', 'ARCHIVIO': 'Archivio storico', 'GRAFICI': 'Grafici e mappe', 'AI': 'Cartoni AI'}
ORDINE_CRESCITA = ['🚀 in esplosione', '📈 in crescita', '➖ stabile', '⏳ dati in raccolta', '📉 in calo']
LUNGHEZZA = {}
STAT = {'ricerche': 0, 'quota': 0, 'pexels': 0, 'archivio': 0, 'claude_chiamate': 0}


def log(*a):
    print(' '.join(str(x) for x in a), flush=True)


def num(v, d=0.0):
    if v is None or str(v).strip() == '':
        return d
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace('$', '').replace('%', '').replace(' ', '')
    if re.fullmatch(r'-?\d{1,3}(\.\d{3})+(,\d+)?', s):   # 1.234.567,5
        s = s.replace('.', '')
    try:
        return float(s.replace(',', '.'))
    except Exception:
        return d


MESI = {m: i + 1 for i, m in enumerate(['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'])}


def data(v):
    """date da: 2026-10-26, 2026-10-26 00:00:00, 26/10/2026, 26 Ottobre 2026, numero seriale di Sheets."""
    if v is None or str(v).strip() == '':
        return None
    if isinstance(v, (int, float)):
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))) if 20000 < v < 80000 else None
    s = str(v).strip()
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        return dt.date(int(m[3]), int(m[2]), int(m[1]))
    m = re.match(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', s)
    if m and m[2].lower() in MESI:
        return dt.date(int(m[3]), MESI[m[2].lower()], int(m[1]))
    return None


def T(s):
    """testo libero scritto con USER_ENTERED: l'apostrofo iniziale impedisce che diventi formula, numero o data (non si vede)."""
    s = '' if s is None else str(s)
    return "'" + s if s else ''


def link(u):
    return '=HYPERLINK("' + u.replace('"', '') + '")' if u else ''


def http(url, corpo=None, headers=None, metodo=None, raw=False, timeout=90, tentativi=3):
    err = None
    for k in range(tentativi):
        try:
            req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                         headers=dict({'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 radar'}, **(headers or {})))
            r = urllib.request.urlopen(req, timeout=timeout).read()
            return r if raw else json.loads(r or b'{}')
        except urllib.error.HTTPError as e:
            corpo_err = e.read()[:600].decode('utf-8', 'replace')
            err = RuntimeError(f'HTTP {e.code}: {corpo_err}')
            err.code = e.code
            if e.code not in (429, 500, 502, 503, 504, 529):
                raise err
        except Exception as e:
            err = RuntimeError(str(e)[:200]); err.code = 0
        time.sleep(3 * (k + 1))
    raise err


def pulito(s):
    """mai una chiave nei log (il repository e' pubblico)."""
    s = str(s)
    for k in ('YT_API_KEY_RADAR', 'PEXELS_API_KEY', 'ANTHROPIC_API_KEY'):
        if E(k):
            s = s.replace(E(k), '***')
    return s


# ---------------------------------------------------------------- Google Sheets
def sh(metodo, percorso, corpo=None):
    for k in range(4):
        try:
            return http('https://sheets.googleapis.com/v4/spreadsheets/' + FOGLIO + percorso, corpo, {'Authorization': 'Bearer ' + A.token()}, metodo, tentativi=1)
        except Exception as e:
            if getattr(e, 'code', 0) not in (429, 500, 502, 503, 0) or k == 3:
                raise
            time.sleep(10 * (k + 1))


def leggi_tutto():
    props = {s['properties']['title']: s['properties'] for s in sh('GET', '?fields=sheets.properties')['sheets']}
    nomi = list(props)
    q = '&'.join('ranges=' + urllib.parse.quote(f"'{n}'!A1:AZ") for n in nomi)
    vr = sh('GET', '/values:batchGet?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=FORMATTED_STRING&' + q)['valueRanges']
    tab = {}
    for n, r in zip(nomi, vr):
        v = r.get('values', [])
        h = [str(x).strip() for x in (v[0] if v else [])]
        tab[n] = (h, [dict(zip(h, list(x) + [''] * (len(h) - len(x)))) for x in v[1:] if any(str(c).strip() for c in x)])
        LUNGHEZZA[n] = max(0, len(v) - 1)   # righe occupate (anche con buchi), per svuotare bene quelle avanzate
    return props, tab


def scheda(props, chiave):
    """nome reale della scheda (es. 'Canali' o '🏆 Canali')."""
    for n in props:
        if re.sub(r'[^\w ]', '', n).strip().lower() == chiave.lower():
            return n
    raise RuntimeError('Scheda non trovata nel foglio RADAR: ' + chiave)


def riga_per(h, d):
    return [d.get(c, '') for c in h]


def assicura_righe(props, nome, n):
    p = props[nome]; righe = p.get('gridProperties', {}).get('rowCount', 1000)
    if n > righe:
        sh('POST', ':batchUpdate', {'requests': [{'appendDimension': {'sheetId': p['sheetId'], 'dimension': 'ROWS', 'length': n - righe + 50}}]})


def riscrivi(props, nome, h, righe, vecchie):
    """scrive prima le righe nuove sopra le vecchie, poi svuota solo quelle avanzate: non c'e' mai un momento con la scheda vuota."""
    assicura_righe(props, nome, len(righe) + 2)
    fine = A.lettera(len(h))
    if righe:
        sh('PUT', '/values/' + urllib.parse.quote(f"'{nome}'!A2:{fine}{len(righe) + 1}") + '?valueInputOption=USER_ENTERED', {'values': righe})
    if vecchie > len(righe):
        sh('POST', '/values/' + urllib.parse.quote(f"'{nome}'!A{len(righe) + 2}:{fine}{vecchie + 1}") + ':clear', {})


def aggiungi(nome, righe):
    for i in range(0, len(righe), 2000):
        sh('POST', '/values/' + urllib.parse.quote(f"'{nome}'!A1") + ':append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS', {'values': righe[i:i + 2000]})


# ---------------------------------------------------------------- YouTube (solo la chiave RADAR)
class QuotaFinita(Exception):
    pass


def yt(path, costo=1, **q):
    if STAT['quota'] + costo > QUOTA_YT:
        raise QuotaFinita('limite di quota del giro raggiunto')
    STAT['quota'] += costo
    try:
        return http('https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(dict(q, key=YT_KEY)), timeout=60)
    except Exception as e:
        msg = pulito(e)
        if 'quotaExceeded' in msg or 'dailyLimitExceeded' in msg:
            raise QuotaFinita('quota YouTube del giorno esaurita (si azzera alle 9:00 italiane)')
        raise RuntimeError(msg[:300])


def secondi(iso):
    m = re.match(r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$', iso or '')
    return (int(m[1] or 0) * 86400 + int(m[2] or 0) * 3600 + int(m[3] or 0) * 60 + int(m[4] or 0)) if m else 0


def lista(v):
    return [s.strip() for s in str(v or '').split(',') if s.strip()]


def altra_scrittura(testo, lingua):
    """True se il titolo e' scritto per lo piu' in un alfabeto non latino (hindi, coreano, greco...) e la lingua cercata e' latina."""
    if lingua not in ('en', 'it', 'es', 'fr', 'de', 'pt'):
        return False
    lettere = [c for c in testo if c.isalpha()]
    if len(lettere) < 4:
        return False
    nonlat = sum(1 for c in lettere if 'LATIN' not in unicodedata.name(c, ''))
    return nonlat / len(lettere) > 0.3


# ---------------------------------------------------------------- Claude (l'unica spesa)
class Cassa:
    def __init__(self, budget):
        self.budget = budget
        try:
            self.storico = json.load(open(F_SPESA))
        except Exception:
            self.storico = {}
        self.gia = float(self.storico.get(OGGI, 0) or 0)
        self.oggi = 0.0

    def prezzi(self, modello):
        m = modello.lower()
        return (1, 5) if 'haiku' in m else ((3, 15) if 'sonnet' in m else (15, 75))

    def puo(self, modello, tok_in, tok_out):
        pi, po = self.prezzi(modello)
        stima = (tok_in * pi + tok_out * po) / 1e6
        return self.budget > 0 and self.gia + self.oggi + stima <= self.budget

    def chiedi(self, modello, content, max_tokens, tok_in_stima):
        if PROVA or not E('ANTHROPIC_API_KEY') or not self.puo(modello, tok_in_stima, max_tokens):
            return None
        r = http('https://api.anthropic.com/v1/messages', {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': content}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'}, timeout=120)
        u = r.get('usage', {}); pi, po = self.prezzi(modello)
        tin = (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0) + (u.get('cache_read_input_tokens') or 0)
        self.oggi += (tin * pi + (u.get('output_tokens') or 0) * po) / 1e6
        STAT['claude_chiamate'] += 1
        return ''.join(c.get('text', '') for c in r.get('content', []))

    def salva(self):
        if PROVA:
            return
        self.storico[OGGI] = round(self.gia + self.oggi, 4)
        os.makedirs(CART, exist_ok=True)
        json.dump(dict(sorted(self.storico.items())[-120:]), open(F_SPESA, 'w'), indent=1)


def json_da(testo, a='{', b='}'):
    t = (testo or '').replace('```json', '').replace('```', '')
    return json.loads(t[t.index(a):t.rindex(b) + 1])


# ---------------------------------------------------------------- materiale gratis
def conta_pexels(q):
    if STAT['pexels'] >= MAX_PEXELS or not E('PEXELS_API_KEY'):
        return None
    STAT['pexels'] += 1
    try:
        r = http('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 1, 'orientation': 'landscape'}),
                 headers={'Authorization': E('PEXELS_API_KEY')}, timeout=30, tentativi=2)
        return int(r.get('total_results') or 0)
    except Exception as e:
        log('   Pexels non risponde per', repr(q), pulito(e)[:80]); return None


def conta_archivio(q):
    if STAT.get('archivio_ko', 0) >= 3:   # Archive.org non risponde: si riprova al prossimo giro
        return None
    STAT['archivio'] += 1
    try:
        parole = ' AND '.join('(' + w + ')' for w in re.findall(r"[\w']+", q)[:6])
        r = http('https://archive.org/advancedsearch.php?' + urllib.parse.urlencode({'q': f'({parole}) AND mediatype:(movies OR image)', 'rows': 0, 'output': 'json'}),
                 timeout=25, tentativi=2)
        STAT['archivio_ko'] = 0
        return int(r.get('response', {}).get('numFound') or 0)
    except Exception as e:
        STAT['archivio_ko'] = STAT.get('archivio_ko', 0) + 1
        log('   Archive.org non risponde per', repr(q), pulito(e)[:80]); return None


def controlla_materiale(v, S):
    """v = valutazione con formato e ricerche: conta il materiale e mette POCO MATERIALE se sotto soglia. Gratis."""
    fmt = v.get('formato_replica')
    if v.get('esito_replica') not in ('COPIA', 'POCO MATERIALE') or fmt not in ('PEXELS', 'ARCHIVIO'):
        v['da_contare'] = False; return v
    qs = [q for q in v.get('ricerche') or [] if q][:3]
    if not qs:
        v['da_contare'] = False; return v
    pex = fmt == 'PEXELS'
    cont = [(q, conta_pexels(q) if pex else conta_archivio(q)) for q in qs]
    ok = [n for _, n in cont if n is not None]
    if not ok:
        v['da_contare'] = True; return v   # Pexels/Archive non rispondono: si riconta al prossimo giro (gratis)
    med = sorted(ok)[(len(ok) - 1) // 2]
    soglia = num(S.get('min_clip_pexels'), 200) if pex else num(S.get('min_risultati_archivio'), 100)
    v.update({'materiale_trovato': med, 'fonte_materiale': 'pexels' if pex else 'archivio', 'da_contare': len(ok) < len(qs),
              'materiale_dettaglio': ' | '.join(f'{q}: {n if n is not None else "?"}' for q, n in cont),
              'esito_replica': 'COPIA' if med >= soglia else 'POCO MATERIALE'})
    return v


PROMPT = (
    "Sei un analista di canali YouTube. Le immagini sono FOTOGRAMMI presi da DENTRO i video del canale (non le copertine).\n"
    "Noi rifacciamo i video SOLO con materiale gratuito e voce narrante AI, in uno di questi FORMATI:\n"
    "PEXELS = clip stock generiche (luoghi, natura, citta', animali, oggetti, cibo, persone generiche, drone, timelapse, atmosfera).\n"
    "ARCHIVIO = foto e filmati storici d'archivio, materiale NASA, dipinti, sculture e incisioni di museo, mappe antiche (pubblico dominio).\n"
    "GRAFICI = mappe animate, grafici, infografiche, timeline, testi e numeri animati.\n"
    "AI = illustrazioni, disegni, cartoni, stickman, animazioni o immagini generate.\n"
    "COPIA = almeno il 70% dei fotogrammi si rifa' con UNO di questi formati (scegli quello prevalente).\n"
    "SCARTA = storie con animali specifici protagonisti di azioni precise (lotte \"vs\", cacce, inseguimenti, nascite, \"secret life of\"), "
    "riprese reali di eventi o persone precise (polizia, bodycam, cronaca, incidenti, liti, interviste), videogiochi, film o serie, "
    "celebrita' o influencer, volto del creatore che parla, contenuti per bambini, video musicali.\n"
    "Scrivi anche 3 ricerche in inglese (2-4 parole) per trovare materiale simile: su Pexels se il formato e' PEXELS, su Archive.org se e' ARCHIVIO.\n"
    "{RPM}"
    "Rispondi SOLO con JSON: {\"esito\":\"COPIA|SCARTA\",\"formato\":\"PEXELS|ARCHIVIO|GRAFICI|AI\",\"percentuale_materiale\":0-100,"
    "\"nicchia\":\"massimo 5 parole in italiano\",\"motivo\":\"massimo 15 parole in italiano\",{RPMJ}\"ricerche\":[\"...\",\"...\",\"...\"]}\n\n")


def valuta(cassa, S, c, vids):
    """c = dati del canale, vids = suoi video trovati (i migliori prima). None = non valutato (budget o immagini mancanti)."""
    modello = str(S.get('modello_valutazione') or '').strip() or 'claude-haiku-4-5-20251001'
    fmt = str(S.get('fotogramma_formato') or 'hq').strip().lower()
    pref = '' if fmt == 'base' else (fmt if fmt in ('hq', 'mq', 'sd') else 'hq')
    n_vid = int(min(3, max(1, num(S.get('video_per_canale'), 1))))
    rpm_ai = str(S.get('rpm_da_ai') or '').strip().upper() == 'SI'
    stima_in = 750 + n_vid * 3 * 260
    if not cassa.puo(modello, stima_in, 400) or PROVA:
        return None
    content, imm = [], 0
    for v in vids[:n_vid]:
        content.append({'type': 'text', 'text': 'Video: ' + str(v['titolo'])[:150]})
        for f in (1, 2, 3):
            try:
                b = http(f"https://i.ytimg.com/vi/{v['video_id']}/{pref}{f}.jpg", raw=True, timeout=30, tentativi=2)
                content.append({'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b).decode()}}); imm += 1
            except Exception:
                pass
    if not imm:
        return None
    p = PROMPT.replace('{RPM}', "Stima anche l'RPM in dollari (guadagno ogni 1000 views) tipico per questa nicchia e questo pubblico.\n" if rpm_ai else '') \
              .replace('{RPMJ}', '"rpm":numero,' if rpm_ai else '')
    content.append({'type': 'text', 'text': p + f"Canale: {c['canale']} ({c['iscritti']} iscritti)"})
    try:
        t = cassa.chiedi(modello, content, 400, stima_in)
    except Exception as e:
        log('   Claude errore per', c['canale'], pulito(e)[:150]); return None
    if t is None:
        return None
    try:
        j = json_da(t)
    except Exception:
        log('   risposta di Claude non leggibile per', c['canale'], t[:120]); return None
    esito = str(j.get('esito') or '').strip().upper()
    formato = str(j.get('formato') or '').strip().upper()
    rpm = num(j.get('rpm'), 0) if rpm_ai else 0
    return {'esito_replica': esito if esito in ('COPIA', 'SCARTA') else 'DA VERIFICARE', 'formato_replica': formato if formato in CON_COSA else '',
            'nicchia': str(j.get('nicchia') or '')[:80], 'motivo_replica': str(j.get('motivo') or '')[:200],
            'rpm_stimato': rpm if rpm > 0 else num(S.get('rpm_stimato'), 4), 'percentuale_materiale': num(j.get('percentuale_materiale'), ''),
            'materiale_trovato': '', 'fonte_materiale': '', 'materiale_dettaglio': '',
            'ricerche': [str(q).strip() for q in (j.get('ricerche') or j.get('pexels_query') or []) if str(q).strip()][:3], 'valutato_il': OGGI}


# ---------------------------------------------------------------- ricerche
def prepara_ricerche(S, cassa, canali_scelta):
    dopo = (ORA - dt.timedelta(days=num(S.get('finestra_scoperta_giorni'), 7))).strftime('%Y-%m-%dT%H:%M:%SZ')
    DUR = ('any', 'short', 'medium', 'long')
    dur = lambda v, d: (str(v or '').strip().lower() if str(v or '').strip().lower() in DUR else d)
    durate_semi = [dur(x, 'long') for x in str(S.get('durata_semi') or 'long').split('+')]
    paesi_semi = [p.upper() for p in lista(S.get('paesi_semi') or 'US')]
    out, gia = [], set()

    def add(seme, p, extra):
        k = (str(extra.get('q', '')).lower(), extra.get('videoCategoryId', ''), extra['videoDuration'], p)
        if k in gia:
            return
        gia.add(k)
        q = dict({'part': 'snippet', 'type': 'video', 'order': 'viewCount', 'publishedAfter': dopo, 'regionCode': p,
                  'relevanceLanguage': LINGUA.get(p, 'en'), 'maxResults': 50}, **extra)
        out.append({'seme': seme, 'paese': p, 'lingua': LINGUA.get(p, 'en'), 'parola': 'q' in extra, 'query': q})

    for p in paesi_semi:
        for k in lista(S.get('semi_parole')):
            kw, _, d = (x.strip() for x in k.partition('|'))
            if kw:
                for dd in ([dur(x, 'long') for x in d.split('+')] if d else durate_semi):
                    add('parola: ' + kw, p, {'q': kw, 'videoDuration': dd})
    # SIMILI: canali con "SIMILI" nella colonna ⭐ Scelta -> si cercano i titoli dei loro video migliori
    n_sim = int(num(S.get('ricerche_per_simili'), 3))
    for cid, nome in canali_scelta:
        if n_sim <= 0 or PROVA:
            break
        try:
            ch = yt('channels', part='contentDetails', id=cid)['items'][0]
            ids = [x['contentDetails']['videoId'] for x in yt('playlistItems', part='contentDetails', maxResults=50,
                   playlistId=ch['contentDetails']['relatedPlaylists']['uploads']).get('items', [])]
            vv = yt('videos', part='snippet,statistics,contentDetails', id=','.join(ids[:50])).get('items', []) if ids else []
            vv = [v for v in vv if secondi(v['contentDetails'].get('duration')) >= num(S.get('min_durata_video_secondi'), 0)] or vv
            vv.sort(key=lambda v: -int(v['statistics'].get('viewCount') or 0))
            for v in vv[:n_sim]:
                t = re.sub(r'[^\w\s\'?!,.:-]', ' ', v['snippet']['title'].split('|')[0])
                q = ' '.join(t.split()[:7])
                for p in paesi_semi:
                    for dd in durate_semi:
                        add(f'parola: {q} (simili a {nome})', p, {'q': q, 'videoDuration': dd})
        except QuotaFinita as e:
            log('SIMILI: stop,', e); break
        except Exception as e:
            log('SIMILI: canale', cid, 'non letto', str(e)[:100])
    # TREND PEXELS: dai video piu' popolari di Pexels in questo periodo
    if str(S.get('trend_pexels') or '').strip().upper() == 'SI':
        for x in trend_pexels(S, cassa):
            for p in paesi_semi:
                add('parola: ' + x['q'] + ' (trend Pexels)', p, {'q': x['q'], 'videoDuration': dur(x.get('durata'), durate_semi[0])})
    # CATEGORIE (solo_parole = NO): costano tanta quota
    if str(S.get('solo_parole') or '').strip().upper() != 'SI':
        escl = set(lista(S.get('categorie_escluse')))
        for p in [x.upper() for x in lista(S.get('paesi_mercato') or 'IT,US')]:
            for cid, nome in CAT.items():
                if str(cid) not in escl:
                    add('categoria: ' + nome, p, {'videoCategoryId': str(cid), 'videoDuration': dur(S.get('durata_categorie'), 'medium')})
    return out


STOP = set('a an the of in on at to and or for with by from is are be this that it its into over under near up down out off new old video videos footage stock '
           'close shot view man woman person people young two one three background slow motion each other while looking using holding sitting standing '
           'walking wearing working talking playing apple iphone phone laptop computer screen digital projection hand hands face top side'.split())
CALMI = set('rain ocean waves sea beach forest fire fireplace snow waterfall night sky clouds sunset sunrise lake river nature relaxing ambience'.split())


def trend_pexels(S, cassa):
    mx = int(num(S.get('max_trend'), 20))
    desc = []
    for pg in (1, 2):
        if STAT['pexels'] >= MAX_PEXELS or not E('PEXELS_API_KEY'):
            break
        STAT['pexels'] += 1
        try:
            r = http(f'https://api.pexels.com/videos/popular?per_page=80&min_duration=5&page={pg}', headers={'Authorization': E('PEXELS_API_KEY')}, timeout=30, tentativi=2)
        except Exception as e:
            log('Pexels popolari non letti:', pulito(e)[:100]); break
        for v in r.get('videos', []):
            m = re.search(r'/video/([^/]+?)-\d+/?$', str(v.get('url') or ''))
            if m:
                desc.append(re.sub(r'\s+', ' ', m[1].replace('-', ' ')).strip().lower())
    desc = list(dict.fromkeys(desc))[:400]
    log('Video popolari letti da Pexels:', len(desc))
    if not desc:
        return []
    prompt = ("Queste sono le descrizioni dei VIDEO piu' popolari su Pexels in questo periodo (quindi materiale abbondante e di tendenza):\n" + '; '.join(desc) + "\n\n"
              f"Raggruppale per tema e ricava al massimo {mx} ricerche da fare su YouTube (in inglese, 2-5 parole) per trovare canali faceless che pubblicano video "
              "costruiti con questo tipo di clip (atmosfera, relax, natura, citta', animali, viaggi, documentari, spiegazioni). Metti prima i temi con piu' video. "
              "Escludi: religione e feste religiose, persone o celebrita' precise, marchi, eventi di cronaca, politica, bambini, contenuti romantici o sessuali. "
              "Per ogni ricerca indica la durata: \"long\" per atmosfera/relax/ambience/suoni per dormire, \"medium\" per documentari, compilation e spiegazioni.\n"
              "Rispondi SOLO con un array JSON: [{\"q\":\"city at night 4k\",\"durata\":\"long\"}]")
    modello = str(S.get('modello_argomenti') or '').strip() or 'claude-haiku-4-5-20251001'
    try:
        t = cassa.chiedi(modello, prompt, 1500, len(prompt) // 3 + 50)
        if t:
            out = [x for x in json_da(t, '[', ']') if isinstance(x, dict) and str(x.get('q') or '').strip()][:mx]
            log('Ricerche dai trend Pexels (Claude):', len(out)); return out
    except Exception as e:
        log('Claude trend non riuscito, uso il calcolo gratuito:', pulito(e)[:100])
    # gratis: le coppie di parole piu' frequenti nelle descrizioni
    cont = {}
    for d in desc:
        w = [x for x in re.findall(r'[a-z]+', d)]
        for i in range(len(w) - 1):
            if w[i] in STOP or w[i + 1] in STOP or len(w[i]) < 3 or len(w[i + 1]) < 3:
                continue
            cont[w[i] + ' ' + w[i + 1]] = cont.get(w[i] + ' ' + w[i + 1], 0) + 1
    top = [k for k, n in sorted(cont.items(), key=lambda x: -x[1]) if n >= 2][:mx]
    out = [{'q': k, 'durata': 'long' if set(k.split()) & CALMI else 'medium'} for k in top]
    log('Ricerche dai trend Pexels (calcolo gratuito, senza Claude):', len(out), '|', ', '.join(x['q'] for x in out))
    return out


# ---------------------------------------------------------------- argomenti (TREND)
def argomenti(cassa, S, canali, cache):
    """argomento per canale: quello gia' dato da Claude (cache), altrimenti Claude (se c'e' budget), altrimenti la ricerca che l'ha trovato."""
    nuovi = [c for c in canali if not cache.get(c['channel_id'], {}).get('argomento')]
    modello = str(S.get('modello_argomenti') or '').strip() or 'claude-haiku-4-5-20251001'
    esistenti = sorted({v.get('argomento') for v in cache.values() if v.get('argomento')})
    for i in range(0, len(nuovi), 120):
        blocco = nuovi[i:i + 120]
        prompt = ("Raggruppa questi canali YouTube per ARGOMENTO di contenuto (cosa raccontano, non lo stile). Un argomento deve essere abbastanza preciso "
                  "da diventare un canale (es. \"Stoicismo e sviluppo personale\", \"Mitologia e divinita' antiche\"), in italiano, massimo 5 parole.\n"
                  + ("Argomenti gia' esistenti: se un canale rientra in uno di questi usa ESATTAMENTE lo stesso nome: " + ' ; '.join(esistenti) + "\n" if esistenti else '')
                  + "Rispondi SOLO con JSON {\"numero\":\"argomento\"} per ogni canale.\n\n"
                  + '\n'.join(f"{k} | {c['nicchia']} | {c['canale']} | {str(c['video_migliore'])[:90]}" for k, c in enumerate(blocco)))
        try:
            t = cassa.chiedi(modello, prompt, 12 * len(blocco) + 200, len(prompt) // 3 + 50)
        except Exception as e:
            log('Claude argomenti errore:', pulito(e)[:120]); t = None
        if not t:
            break
        try:
            j = json_da(t)
        except Exception:
            log('Risposta argomenti non leggibile'); break
        for k, c in enumerate(blocco):
            a = str(j.get(str(k)) or '').strip()
            if a:
                cache.setdefault(c['channel_id'], {})['argomento'] = a[:60]
                esistenti = sorted(set(esistenti) | {a[:60]})
    out = {}
    for c in canali:
        a = cache.get(c['channel_id'], {}).get('argomento')
        if not a:
            s = re.sub(r'^(parola|categoria):\s*', '', str(c['trovato_con']))
            a = '~ ' + re.sub(r'\s*\((trend Pexels|tema emerso|simili a .*)\)\s*$', '', s).strip()   # ~ = senza Claude
        out[c['channel_id']] = a
    return out


def salva_cache(cache):
    if PROVA:
        return
    os.makedirs(CART, exist_ok=True)
    json.dump(dict(sorted(cache.items())), open(F_VAL, 'w'), ensure_ascii=False, indent=0)


# ---------------------------------------------------------------- main
def main():
    props, tab = leggi_tutto()
    n_imp, n_can, n_vt, n_sto, n_tr = (scheda(props, k) for k in ('Impostazioni', 'Canali', 'Video trovati', 'Storico', 'TREND'))
    hi, imp = tab[n_imp]
    S = {str(r.get('parametro')).strip(): r.get('valore') for r in imp if str(r.get('parametro') or '').strip()}
    nuova_impostazione = None
    if 'budget_giorno' not in S:
        nuova_impostazione = riga_per(hi, {'parametro': 'budget_giorno', 'valore': '', 'gruppo': 'VALUTAZIONE',
                                           'spiegazione': "Spesa massima al giorno in $ per Claude (valutazione e trend). Vuoto o 0 = nessuna chiamata a Claude: "
                                                          "i canali nuovi restano 'da valutare'. Lo decide Giorgio."})
    budget = 0.0 if SENZA_CLAUDE else num(S.get('budget_giorno'), 0)
    cassa = Cassa(budget)
    log(f"RADAR {OGGI} | prova={'SI' if PROVA else 'NO'} | budget Claude oggi ${budget:.2f} (gia' speso oggi ${cassa.gia:.3f})"
        + (' | SENZA_CLAUDE: budget forzato a 0' if SENZA_CLAUDE else ''))

    h_vt, vt = tab[n_vt]; h_sto, sto = tab[n_sto]; h_can, can_old = tab[n_can]; h_tr, tr_old = tab[n_tr]
    # cache delle valutazioni: dal foglio (ultima riga valutata per canale) + file del repository (piu' recente)
    cache = {}
    primo_cache = {}
    for r in vt:
        cid = str(r.get('channel_id') or '').strip()
        if not cid:
            continue
        d = data(r.get('data_primo_video'))
        if d:
            primo_cache[cid] = d
        es = str(r.get('esito_replica') or '').strip().upper()
        if es in ('COPIA', 'SCARTA', 'POCO MATERIALE'):
            det = str(r.get('materiale_dettaglio') or '')
            cache[cid] = {k: r.get(k, '') for k in ('esito_replica', 'formato_replica', 'nicchia', 'motivo_replica', 'rpm_stimato', 'percentuale_materiale',
                                                    'materiale_trovato', 'fonte_materiale', 'materiale_dettaglio')}
            cache[cid]['ricerche'] = [x.rsplit(':', 1)[0].strip() for x in det.split(' | ') if ':' in x]
            # n8n contava 0 clip quando Pexels rispondeva "troppe richieste": quei conteggi tutti a 0 si rifanno (gratis)
            cache[cid]['da_contare'] = es == 'POCO MATERIALE' and bool(cache[cid]['ricerche']) and all(x.rsplit(':', 1)[1].strip() in ('0', '?') for x in det.split(' | ') if ':' in x)
    try:
        for cid, v in json.load(open(F_VAL)).items():
            cache[cid] = dict(cache.get(cid, {}), **v)
    except Exception:
        pass

    for r in tr_old:   # argomenti gia' dati da Claude nella scheda TREND
        cid, a = str(r.get('channel_id') or '').strip(), str(r.get('Argomento') or '').strip()
        if cid and a and not a.startswith('~') and not cache.get(cid, {}).get('argomento'):
            cache.setdefault(cid, {})['argomento'] = a
    scelte = {str(r.get('channel_id')).strip(): r for r in can_old if str(r.get('channel_id') or '').strip()}
    simili = [(cid, r.get('Canale')) for cid, r in scelte.items() if str(r.get('⭐ Scelta') or '').strip().upper() == 'SIMILI']

    # 1) RICERCHE
    ricerche = prepara_ricerche(S, cassa, simili)
    tot = len(ricerche)
    limite = 2 if PROVA else (MAX_RICERCHE or 10 ** 6)
    ricerche = ricerche[:limite]
    log(f'Ricerche preparate: {tot}, fatte oggi: {len(ricerche)} (circa {len(ricerche) * 100} unita\' di quota)')
    trovati = {}   # video_id -> (ricerca, item)
    for r in ricerche:
        try:
            res = yt('search', costo=100, **r['query'])
        except QuotaFinita as e:
            log('STOP ricerche:', e); break
        except Exception as e:
            log(r['seme'], ': errore ricerca', str(e)[:150]); continue
        STAT['ricerche'] += 1
        for x in res.get('items', []):
            vid = (x.get('id') or {}).get('videoId')
            if vid and vid not in trovati:
                trovati[vid] = (r, None)
    log('Video trovati dalle ricerche (diversi):', len(trovati))

    # 2) STATISTICHE VIDEO e FILTRI VIDEO
    ids = list(trovati)
    for i in range(0, len(ids), 50):
        try:
            for v in yt('videos', part='snippet,statistics,contentDetails,status,topicDetails', id=','.join(ids[i:i + 50]), maxResults=50).get('items', []):
                trovati[v['id']] = (trovati[v['id']][0], v)
        except QuotaFinita as e:
            log('STOP statistiche:', e); break
    min_views = num(S.get('min_views_video'), 10000)
    min_dur, max_dur = num(S.get('min_durata_video_secondi'), 0), num(S.get('max_durata_video_secondi'), 0)
    f_lingua = str(S.get('filtro_lingua') or '').strip().upper() == 'SI'
    escludi = str(S.get('escludi_non_producibili') or '').strip().upper() == 'SI'
    parole_escl = [p.lower() for p in lista(S.get('parole_escluse'))]
    scarti = {'views': 0, 'durata': 0, 'non producibili': 0, 'lingua': 0}
    cand = []
    for vid, (r, v) in trovati.items():
        if not v:
            continue
        views = int(v.get('statistics', {}).get('viewCount') or 0)
        if views < min_views:
            scarti['views'] += 1; continue
        d = secondi(v.get('contentDetails', {}).get('duration'))
        if (min_dur > 0 and d < min_dur) or (max_dur > 0 and d > max_dur):
            scarti['durata'] += 1; continue
        sn = v.get('snippet', {})
        if escludi:
            testo = (sn.get('title', '') + ' ' + ' '.join(sn.get('tags') or []) + ' ' + str(sn.get('description', ''))[:300]).lower()
            temi = ' '.join((v.get('topicDetails') or {}).get('topicCategories') or []).lower()
            if sn.get('categoryId') == '20' or 'game' in temi or (v.get('status') or {}).get('madeForKids') is True or any(p in testo for p in parole_escl):
                scarti['non producibili'] += 1; continue
        if f_lingua:
            lv = str(sn.get('defaultAudioLanguage') or sn.get('defaultLanguage') or '').lower()
            if (lv and r['lingua'] and not lv.startswith(r['lingua'])) or altra_scrittura(sn.get('title', ''), r['lingua']):
                scarti['lingua'] += 1; continue
        pub = sn.get('publishedAt') or ORA.isoformat()
        giorni = max(1.0, (ORA - dt.datetime.fromisoformat(pub.replace('Z', '+00:00'))).total_seconds() / 86400)
        cand.append({'video_id': vid, 'titolo': sn.get('title', ''), 'canale': sn.get('channelTitle', ''), 'channel_id': sn.get('channelId', ''),
                     'pubblicato_il': pub[:10], 'views': views, 'views_al_giorno': round(views / giorni), 'durata_min': round(d / 6) / 10,
                     'seme': r['seme'], 'paese': r['paese'], 'parola': r['parola']})
    log('Video oltre le soglie:', len(cand), '| scartati:', ', '.join(f'{k} {n}' for k, n in scarti.items()))

    # 3) CANALI: iscritti, numero video, rapporto views/iscritti
    chs = {}
    cids = list(dict.fromkeys(c['channel_id'] for c in cand))
    for i in range(0, len(cids), 50):
        try:
            for c in yt('channels', part='snippet,statistics,contentDetails', id=','.join(cids[i:i + 50]), maxResults=50).get('items', []):
                chs[c['id']] = c
        except QuotaFinita as e:
            log('STOP canali:', e); break
    paesi_m = [p.upper() for p in lista(S.get('paesi_mercato'))]
    max_isc, min_rap, max_vid = num(S.get('max_iscritti_canale'), 50000), num(S.get('min_rapporto_views_iscritti'), 5), num(S.get('max_video_canale'), 500)
    per_canale = {}
    for v in cand:
        c = chs.get(v['channel_id'])
        if not c:
            continue
        st = c.get('statistics', {})
        isc = int(st.get('subscriberCount') or 0)
        if st.get('hiddenSubscriberCount') or isc < 1:
            continue
        paese = str(c.get('snippet', {}).get('country') or '').upper()
        if paesi_m and paese and paese not in paesi_m and not v['parola']:
            continue
        if isc > max_isc or int(st.get('videoCount') or 0) > max_vid:
            continue
        rap = v['views'] / isc
        if rap < min_rap:
            continue
        v.update({'iscritti': isc, 'views_canale': int(st.get('viewCount') or 0), 'n_video_canale': int(st.get('videoCount') or 0), 'rapporto_views_iscritti': round(rap, 1)})
        per_canale.setdefault(v['channel_id'], {'c': c, 'video': []})['video'].append(v)
    log('Canali dopo i filtri iscritti/rapporto/numero video:', len(per_canale))

    # 4) ETA': data del PRIMO VIDEO ancora online
    max_eta = num(S.get('max_eta_primo_video_giorni'), 180)
    righe_vt, passati = [], {}
    for cid, x in per_canale.items():
        d0 = primo_cache.get(cid)
        if not d0:
            try:
                up = x['c']['contentDetails']['relatedPlaylists']['uploads']; pg = ''; minimo = None
                for _ in range(10):
                    r = yt('playlistItems', part='contentDetails', playlistId=up, maxResults=50, **({'pageToken': pg} if pg else {}))
                    for it in r.get('items', []):
                        p = (it.get('contentDetails') or {}).get('videoPublishedAt')
                        if p and (not minimo or p < minimo):
                            minimo = p
                    pg = r.get('nextPageToken')
                    if not pg:
                        break
                d0 = data(minimo) if minimo else None
            except QuotaFinita as e:
                log('STOP eta\' canali:', e); break
            except Exception as e:
                log('primo video non letto per', cid, str(e)[:80]); continue
        if not d0:
            continue
        eta = (OGGI_D - d0).days
        if eta > max_eta:
            continue
        primo_cache[cid] = d0
        passati[cid] = x
        for v in x['video']:
            v.update({'data_primo_video': d0.isoformat(), 'giorni_dal_primo_video': eta,
                      'giorni_dalla_pubblicazione': (OGGI_D - data(v['pubblicato_il'])).days})
    log('Canali che passano TUTTI i filtri (eta\' compresa):', len(passati))

    # 5) VALUTAZIONE (Claude, solo canali che hanno passato i filtri) e materiale gratis
    paroleScarta = [p.lower() for p in lista(S.get('parole_scarta_titolo'))]
    storia_vt = {}
    for r in vt:
        storia_vt.setdefault(str(r.get('channel_id') or '').strip(), []).append(r)
    lim_can = OGGI_D - dt.timedelta(days=num(S.get('canali_giorni'), 60))

    def da_titoli(titoli):
        for t in titoli:
            t = ' ' + str(t).lower() + ' '
            hit = next((p for p in paroleScarta if re.search(r'(^|[^a-z0-9])' + re.escape(p), t)), None)
            if hit:
                return hit
        return None

    # canali da valutare: quelli di oggi + quelli gia' trovati (filtri passati) negli ultimi canali_giorni ancora "da valutare"
    attesa = {}
    for cid, x in passati.items():
        attesa[cid] = {'canale': x['c']['snippet']['title'], 'iscritti': x['video'][0]['iscritti'],
                       'video': sorted(x['video'], key=lambda v: -v['views']), 'potenziale': max(v['views_al_giorno'] for v in x['video'])}
    for cid, rr in storia_vt.items():
        if cid in attesa or not cid or cid in cache:
            continue
        rr2 = [r for r in rr if (data(r.get('data_rilevazione')) or dt.date(2000, 1, 1)) >= lim_can]
        if not rr2:
            continue
        d0 = primo_cache.get(cid)
        if not d0 or (OGGI_D - d0).days > max_eta:
            continue
        vv = sorted(({'video_id': str(r.get('video_id')), 'titolo': r.get('titolo'), 'views': num(r.get('views')), 'views_al_giorno': num(r.get('views_al_giorno'))} for r in rr2),
                    key=lambda v: -v['views'])
        vv = list({v['video_id']: v for v in reversed(vv)}.values()); vv.sort(key=lambda v: -v['views'])
        attesa[cid] = {'canale': rr2[-1].get('canale'), 'iscritti': rr2[-1].get('iscritti'), 'video': vv, 'potenziale': max(v['views_al_giorno'] for v in vv)}
    nuovi = valutati = gratis_scarta = 0
    ordine = sorted((cid for cid in attesa if cid not in cache), key=lambda c: -attesa[c]['potenziale'])
    for cid in ordine:
        a = attesa[cid]
        hit = da_titoli([v['titolo'] for v in a['video']] + [r.get('titolo') for r in storia_vt.get(cid, [])])
        if hit:   # gratis, senza Claude (come n8n: nate per le lotte tra animali)
            cache[cid] = {'esito_replica': 'SCARTA', 'formato_replica': '', 'nicchia': '', 'motivo_replica': f'storia con animali specifici (titolo: {hit})',
                          'rpm_stimato': num(S.get('rpm_stimato'), 4), 'valutato_il': OGGI}
            gratis_scarta += 1; continue
        nuovi += 1
        v = valuta(cassa, S, a, a['video'])
        if v is None:
            continue
        valutati += 1
        cache[cid] = controlla_materiale(v, S)
        if valutati % 10 == 0:
            salva_cache(cache); cassa.salva()   # se il giro si interrompe, quello che e' stato pagato non si ripaga
        log(f"   valutato {a['canale']} ({a['potenziale']:.0f} views/g): {cache[cid]['esito_replica']} {cache[cid].get('formato_replica', '')} | {cache[cid].get('nicchia', '')}")
    log(f'Valutazione Claude: da valutare {nuovi}, valutati oggi {valutati}, rimasti "da valutare" {nuovi - valutati} '
        f'(scartati gratis per parole nel titolo: {gratis_scarta}) | spesa oggi ${cassa.oggi:.4f}')
    # riconteggio gratuito del materiale (conteggi rimasti a zero o non riusciti), i canali migliori prima
    def potenziale(cid):
        if cid in attesa:
            return attesa[cid]['potenziale']
        rr2 = [r for r in storia_vt.get(cid, []) if (data(r.get('data_rilevazione')) or dt.date(2000, 1, 1)) >= lim_can]
        return max([num(r.get('views_al_giorno')) for r in rr2] or [-1])
    riconta = sorted((cid for cid, v in cache.items() if v.get('da_contare') and v.get('esito_replica') and potenziale(cid) >= 0), key=lambda c: -potenziale(c))
    rifatti = cambiati = 0
    t_fine = time.time() + 600   # al massimo 10 minuti di riconteggi per giro
    for cid in riconta[:10] if PROVA else riconta:
        if time.time() > t_fine:
            break
        if STAT['pexels'] >= MAX_PEXELS - 3 and cache[cid].get('formato_replica') == 'PEXELS':
            continue
        prima = cache[cid].get('esito_replica')
        controlla_materiale(cache[cid], S); rifatti += 1
        cambiati += cache[cid].get('esito_replica') != prima
    if rifatti:
        log(f'Materiale ricontato (gratis) per {rifatti} canali, esito cambiato per {cambiati}')

    # 6) righe di Video trovati (append)
    rpm_def = num(S.get('rpm_stimato'), 4)
    for cid, x in passati.items():
        ev = cache.get(cid) or {'esito_replica': 'DA VERIFICARE', 'motivo_replica': 'da valutare: budget Claude di oggi esaurito o a 0'}
        rpm = num(ev.get('rpm_stimato'), 0) or rpm_def
        v0 = x['video'][0]
        mesi = max(1.0, v0['giorni_dal_primo_video'] / 30)
        ricavi = 0 if v0['iscritti'] < 1000 else round(v0['views_canale'] / mesi / 1000 * rpm)
        for v in x['video']:
            d = dict(v, data_rilevazione=OGGI, link='https://www.youtube.com/watch?v=' + v['video_id'], rpm_stimato=rpm, ricavi_stimati_mese=ricavi,
                     **{k: ev.get(k, '') for k in ('esito_replica', 'formato_replica', 'nicchia', 'motivo_replica', 'percentuale_materiale',
                                                   'materiale_trovato', 'fonte_materiale', 'materiale_dettaglio')})
            for k in ('seme', 'video_id', 'titolo', 'canale', 'channel_id', 'nicchia', 'motivo_replica', 'materiale_dettaglio'):
                d[k] = T(d.get(k))
            righe_vt.append(riga_per(h_vt, d))
    log('Righe nuove per Video trovati:', len(righe_vt))

    # 7) STORICO: una fotografia al giorno dei canali della scheda Canali
    vt_tutti = list(vt) + [dict(zip(h_vt, [str(c)[1:] if isinstance(c, str) and c.startswith("'") else c for c in r])) for r in righe_vt]
    per_vt = {}
    for r in vt_tutti:
        cid = str(r.get('channel_id') or '').strip()
        if cid:
            per_vt.setdefault(cid, []).append(r)
    ultima = {cid: max((data(r.get('data_rilevazione')) or dt.date(2000, 1, 1)) for r in rr) for cid, rr in per_vt.items()}
    scelta_cid = {cid for cid, r in scelte.items() if str(r.get('⭐ Scelta') or '').strip() or str(r.get('Note') or '').strip()}
    foto_cid = [cid for cid in per_vt if ultima[cid] >= lim_can and primo_cache.get(cid) and (OGGI_D - primo_cache[cid]).days <= max_eta]
    foto_cid = list(dict.fromkeys(foto_cid + [c for c in scelta_cid if c in per_vt]))
    oggi_sto = {str(r.get('channel_id')).strip() for r in sto if data(r.get('data')) == OGGI_D}
    snap = {}
    for i in range(0, len(foto_cid), 50):
        try:
            for c in yt('channels', part='snippet,statistics', id=','.join(foto_cid[i:i + 50]), maxResults=50).get('items', []):
                st = c.get('statistics', {})
                snap[c['id']] = {'canale': c['snippet']['title'], 'iscritti': int(st.get('subscriberCount') or 0), 'views': int(st.get('viewCount') or 0),
                                 'n_video': int(st.get('videoCount') or 0)}
        except QuotaFinita as e:
            log('STOP storico:', e); break
    righe_sto = [riga_per(h_sto, {'data': OGGI, 'channel_id': T(cid), 'canale': T(s['canale']), 'iscritti': s['iscritti'], 'views': s['views'], 'n_video': s['n_video']})
                 for cid, s in snap.items() if cid not in oggi_sto]
    log('Righe nuove per Storico:', len(righe_sto), f'(canali fotografati {len(snap)}, gia\' presenti oggi {len(oggi_sto & set(snap))})')
    serie = {}
    for r in vt:   # anche Video trovati ha i numeri del canale giorno per giorno (views_canale, iscritti): allunga lo storico
        d, cid = data(r.get('data_rilevazione')), str(r.get('channel_id') or '').strip()
        if d and cid and num(r.get('views_canale')) > 0:
            serie.setdefault(cid, {})[d] = (num(r.get('views_canale')), num(r.get('iscritti')))
    for r in sto:
        d = data(r.get('data'))
        if d:
            serie.setdefault(str(r.get('channel_id')).strip(), {})[d] = (num(r.get('views')), num(r.get('iscritti')))
    for cid, s in snap.items():
        serie.setdefault(cid, {})[OGGI_D] = (s['views'], s['iscritti'])

    # 8) CANALI
    s_espl, s_cresc, s_calo = num(S.get('soglia_esplosione'), 1.5), num(S.get('soglia_crescita'), 1.1), num(S.get('soglia_calo'), 0.9)
    mostra_scartati = str(S.get('mostra_scartati') or '').strip().upper() == 'SI'
    canali = []
    for cid in foto_cid:
        rr = per_vt[cid]
        ev = cache.get(cid) or {'esito_replica': 'DA VERIFICARE', 'motivo_replica': 'da valutare: budget Claude esaurito o a 0'}
        es = str(ev.get('esito_replica') or 'DA VERIFICARE').upper()
        if es == 'SCARTA' and not mostra_scartati and cid not in scelta_cid:
            continue
        vids = {}
        for r in sorted(rr, key=lambda r: data(r.get('data_rilevazione')) or dt.date(2000, 1, 1)):
            vids[str(r.get('video_id'))] = r
        best = max(vids.values(), key=lambda r: num(r.get('views')))
        altri = [r.get('titolo') for r in sorted(vids.values(), key=lambda r: -num(r.get('views'))) if r is not best][:3]
        ult = max(rr, key=lambda r: data(r.get('data_rilevazione')) or dt.date(2000, 1, 1))
        s = snap.get(cid, {'canale': ult.get('canale'), 'iscritti': int(num(ult.get('iscritti'))), 'views': int(num(ult.get('views_canale')))})
        ser = serie.get(cid, {})
        def a(gg):
            ds = [d for d in ser if d <= OGGI_D - dt.timedelta(days=gg)]
            return (max(ds), ser[max(ds)]) if ds else None
        oggi_v = ser.get(OGGI_D) or (max(ser.values()) if ser else None)
        p7, p14 = a(7), a(14)
        vu = vp = cx = isg = ''
        if oggi_v and p7:
            gg = max(1, (OGGI_D - p7[0]).days)
            vu = round((oggi_v[0] - p7[1][0]) / gg); isg = round((oggi_v[1] - p7[1][1]) / gg)
            if p14:
                vp = round((p7[1][0] - p14[1][0]) / max(1, (p7[0] - p14[0]).days))
        if vu != '' and vp != '':
            rap = (vu / vp) if vp > 0 else (99.0 if vu > 0 else 1.0)
            cx = round(rap, 2) if vp > 0 else ''
            cresc = ORDINE_CRESCITA[0] if rap >= s_espl else ORDINE_CRESCITA[1] if rap >= s_cresc else ORDINE_CRESCITA[4] if rap <= s_calo else ORDINE_CRESCITA[2]
        else:
            cresc = ORDINE_CRESCITA[3]
        d0 = primo_cache[cid]; eta = (OGGI_D - d0).days
        rpm = num(ev.get('rpm_stimato'), 0) or rpm_def
        guad = 0 if s['iscritti'] < 1000 else round(s['views'] / max(1.0, eta / 30) / 1000 * rpm)
        prima = min(data(r.get('data_rilevazione')) or OGGI_D for r in rr)
        canali.append({'channel_id': cid, 'cresc': cresc, 'guad': guad, 'canale': s['canale'], 'nicchia': ev.get('nicchia', ''), 'trovato_con': ult.get('seme'),
                       'video_migliore': best.get('titolo'), 'rifare': RIFARE.get(es, '❓ da valutare'), 'con_cosa': CON_COSA.get(str(ev.get('formato_replica') or '').upper(), ''),
                       'iscritti': s['iscritti'], 'eta': eta, 'vu': vu, 'link_best': 'https://www.youtube.com/watch?v=' + str(best.get('video_id')),
                       'riga': {'Aggiornato il': OGGI, 'Crescita': cresc, 'Canale': T(s['canale']), 'Nicchia': T(ev.get('nicchia', '')), 'Si può rifare?': RIFARE.get(es, '❓ da valutare'),
                                'Con cosa': CON_COSA.get(str(ev.get('formato_replica') or '').upper(), ''), 'RPM stimato $': rpm, 'Iscritti': s['iscritti'],
                                'Primo video': d0.isoformat(), 'Giorni dal primo video': eta, 'Views al giorno (ultima settimana)': vu,
                                'Views al giorno (settimana prima)': vp, 'Crescita x': cx, 'Iscritti al giorno': isg, 'Video migliore': T(best.get('titolo')),
                                'Guadagno stimato $/mese': guad, 'Views video migliore': num(best.get('views')),
                                'Link video migliore': link('https://www.youtube.com/watch?v=' + str(best.get('video_id'))), 'Video esplosi trovati': len(vids),
                                'Altri video': T(' | '.join(str(t) for t in altri)), 'Link canale': link('https://www.youtube.com/channel/' + cid),
                                'Motivo': T(ev.get('motivo_replica', '')), 'Materiale gratis trovato': ev.get('materiale_trovato', ''), 'Trovato con': T(ult.get('seme')),
                                'Prima volta trovato': prima.isoformat(), 'Ultima volta trovato': ultima[cid].isoformat(), 'channel_id': T(cid)}})
    canali.sort(key=lambda c: (ORDINE_CRESCITA.index(c['cresc']), -c['guad']))

    def vecchio(k, v):   # un valore letto dalla scheda, da riscrivere tale e quale
        if isinstance(v, str) and v.startswith('http') and k.startswith('Link'):
            return link(v)
        if isinstance(v, str) and v and not data(v):
            return T(v)
        return v
    fatti = {c['channel_id'] for c in canali}
    righe_can = []
    for c in canali:
        vecchia = scelte.get(c['channel_id'], {})
        d = {k: vecchio(k, vecchia.get(k, '')) for k in h_can if k not in c['riga']}   # ⭐ Scelta, Note e ogni colonna aggiunta da Giorgio restano com'erano
        d.update(c['riga'])
        righe_can.append(riga_per(h_can, d))
    tenuti = 0
    for cid, r in scelte.items():   # canali con una Scelta o una Nota che oggi non rientrano: restano com'erano
        if cid in scelta_cid and cid not in fatti:
            righe_can.append([vecchio(k, r.get(k, '')) for k in h_can]); tenuti += 1
    log(f'Scheda Canali: {len(righe_can)} righe (di cui {tenuti} tenute solo per la tua Scelta/Note) | '
        + ', '.join(f"{k} {sum(1 for c in canali if c['cresc'] == k)}" for k in ORDINE_CRESCITA)
        + ' | ' + ', '.join(f"{v} {sum(1 for c in canali if c['rifare'] == v)}" for v in RIFARE.values()))

    # 9) TREND
    da_raggruppare = [c for c in canali if c['rifare'] != '❌ NO']
    arg = argomenti(cassa, S, da_raggruppare, cache)
    gruppi = {}
    for c in da_raggruppare:
        gruppi.setdefault(arg[c['channel_id']], []).append(c)
    min_tr = num(S.get('trend_min_canali'), 3)
    righe_tr = []
    for g, cc in sorted(gruppi.items(), key=lambda x: -sum(c['cresc'] in ORDINE_CRESCITA[:2] for c in x[1])):
        n = sum(c['cresc'] in ORDINE_CRESCITA[:2] for c in cc)
        if n < min_tr:
            continue
        for c in sorted(cc, key=lambda c: (ORDINE_CRESCITA.index(c['cresc']), -c['guad'])):
            righe_tr.append(riga_per(h_tr, {'Trend': '🔥 TREND', 'Argomento': T(g), 'Canali in crescita': f'{n} su {len(cc)}', 'Canale': T(c['canale']), 'Crescita': c['cresc'],
                                            'Si può rifare?': c['rifare'], 'Con cosa': c['con_cosa'], 'Guadagno stimato $/mese': c['guad'], 'Iscritti': c['iscritti'],
                                            'Giorni dal primo video': c['eta'], 'Views al giorno (ultima settimana)': c['vu'], 'Video migliore': T(c['video_migliore']),
                                            'Link video migliore': link(c['link_best']), 'Link canale': link('https://www.youtube.com/channel/' + c['channel_id']),
                                            'channel_id': T(c['channel_id']), 'Aggiornato il': OGGI}))
    if not righe_tr:
        righe_tr = [riga_per(h_tr, {'Trend': '—', 'Argomento': T(f'Oggi nessun argomento con almeno {int(min_tr)} canali in crescita'), 'Aggiornato il': OGGI})]
    senza = sum(1 for a in arg.values() if a.startswith('~ '))
    log(f"TREND: {sum(1 for r in righe_tr if r and r[0] == '🔥 TREND')} righe, argomenti {len(gruppi)}"
        + (f' ({senza} canali raggruppati senza Claude per ricerca, segnati con ~)' if senza else ''))

    # 10) SCRITTURA
    log(f"Quota YouTube usata ~{STAT['quota']} unita' | ricerche {STAT['ricerche']} | richieste Pexels {STAT['pexels']} | Archive.org {STAT['archivio']} | "
        f"chiamate Claude {STAT['claude_chiamate']} | spesa Claude oggi ${cassa.oggi:.4f} (totale del giorno ${cassa.gia + cassa.oggi:.4f} su ${budget:.2f})")
    if PROVA:
        log('\nPROVA: non scrivo niente. Ecco cosa scriverei:')
        if nuova_impostazione:
            log('Impostazioni + riga:', nuova_impostazione)
        for nome, h, rr in ((n_vt, h_vt, righe_vt), (n_sto, h_sto, righe_sto), (n_can, h_can, righe_can), (n_tr, h_tr, righe_tr)):
            log(f'--- {nome}: {len(rr)} righe ---')
            for r in rr[:4]:
                log('   ', json.dumps(dict(zip(h, r)), ensure_ascii=False)[:600])
        return
    salva_cache(cache); cassa.salva()   # prima del foglio: quello che e' stato pagato resta anche se la scrittura fallisce
    if nuova_impostazione:
        aggiungi(n_imp, [nuova_impostazione]); log('Impostazioni: aggiunta la riga budget_giorno (vuota)')
    if righe_vt:
        aggiungi(n_vt, righe_vt)
    if righe_sto:
        aggiungi(n_sto, righe_sto)
    riscrivi(props, n_can, h_can, righe_can, LUNGHEZZA[n_can])
    riscrivi(props, n_tr, h_tr, righe_tr, LUNGHEZZA[n_tr])
    log('Foglio RADAR aggiornato.')


if __name__ == '__main__':
    main()
