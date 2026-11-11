#!/usr/bin/env python3
"""SCOUT SU GITHUB (6 nov 2026: lo scout n8n e' sparito con Agntable). Per ogni canale di Channel Configs con scout_filone compilato:
1. legge i canali da copiare (colonna canali_da_copiare: link separati da ; o ,) e i loro video lunghi (durata e views dalle colonne scout_*);
2. Claude legge i TITOLI e tiene solo quelli del filone del canale (scout_filone), scartando gli altri filoni dello stesso competitor;
3. con scout_un_video_per = paese: riconosce il soggetto (paese/impero/civilta') e lo salta se e' gia' fatto o gia' in coda nel file di
   produzione (anche se il competitor ha piu' views); tra piu' video sullo stesso soggetto tiene il piu' visto;
4. aggiunge righe "Pronto" dal piu' visto, solo quante servono per avere scout_coda righe Pronto.
Spesa: solo la lettura dei titoli (modello economico), mai oltre scout_budget_giorno (vuota = lo scout non gira)."""
import datetime as dt, json, os, re, sys, unicodedata, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

E = os.environ.get
SOLO = E('SOLO_CANALE', '').strip()
PROVA = E('PROVA', 'NO').strip().upper() == 'SI'
MODELLO = 'claude-haiku-4-5-20251001'
ESPLOSI, GIORNI, MOLT = False, 30, 3


def log(*a):
    print(*a, flush=True)


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.').replace('$', '').strip())
    except Exception:
        return d


def norm(t):
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'\b(the|of|empire|kingdom|republic|civilization|civilisation|ancient|history)\b', ' ', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def get(u, dati=None, h=None):
    with urllib.request.urlopen(urllib.request.Request(u, data=dati, headers=h or {}), timeout=120) as r:
        return json.loads(r.read().decode() or '{}')


T = get('https://oauth2.googleapis.com/token', urllib.parse.urlencode({
    'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': E('YT_REFRESH_TOKEN', ''),
    'grant_type': 'refresh_token'}).encode())['access_token']
yt = lambda path, **q: get('https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(q), h={'Authorization': 'Bearer ' + T})


def id_canale(link):
    link = link.strip()
    m = re.search(r'(UC[\w-]{22})', link)
    if m:
        return m.group(1)
    m = re.search(r'(?:v=|youtu\.be/|shorts/)([\w-]{11})', link)   # 11 nov: va bene anche il link di un loro video
    if m:
        it = yt('videos', part='snippet', id=m.group(1)).get('items', [])
        return it[0]['snippet']['channelId'] if it else None
    m = re.search(r'@([\w.\-]+)', link)
    if m:
        it = yt('channels', part='id', forHandle='@' + m.group(1)).get('items', [])
        return it[0]['id'] if it else None
    return None


def secondi(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return sum(int(x or 0) * k for x, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def video_canale(cid, pagine):
    ch = yt('channels', part='snippet,contentDetails', id=cid).get('items', [])
    if not ch:
        return '', []
    nome = ch[0]['snippet']['title']; up = ch[0]['contentDetails']['relatedPlaylists']['uploads']
    ids, tok = [], None
    for _ in range(pagine):
        q = dict(part='contentDetails', playlistId=up, maxResults=50)
        if tok:
            q['pageToken'] = tok
        r = yt('playlistItems', **q)
        ids += [x['contentDetails']['videoId'] for x in r.get('items', [])]
        tok = r.get('nextPageToken')
        if not tok:
            break
    out = []
    for i in range(0, len(ids), 50):
        for v in yt('videos', part='snippet,statistics,contentDetails', id=','.join(ids[i:i + 50])).get('items', []):
            out.append({'id': v['id'], 'titolo': v['snippet']['title'], 'views': int(v.get('statistics', {}).get('viewCount', 0)),
                        'sec': secondi(v.get('contentDetails', {}).get('duration')), 'cat': v['snippet'].get('categoryId', ''),
                        'canale': nome, 'lingua': v['snippet'].get('defaultAudioLanguage') or v['snippet'].get('defaultLanguage') or '',
                        'pub': v['snippet'].get('publishedAt', '')})
    return nome, out


def classifica(cand, filone, per, budget, fatti=()):
    elenco = '\n'.join(f"{i}. {c['titolo']}" for i, c in enumerate(cand))
    domanda = (f'Our YouTube channel only publishes this format: "{filone}".\n'
               f'Below are video titles from competitor channels (any language). For EACH title say if it fits our format exactly '
               f'(other topics or other formats of the same channel = false)' +
               (f', and give its subject as ONE {per} name in English (e.g. "Iran", "Ottoman Empire", "Maya civilization", "Japan"); '
                f'a city, a war, an organisation, a person, a company or a period that is not a whole {per} = false' if per else '') +
               (f'.\nOur channel ALREADY made (or has queued) these {per}s: {"; ".join(sorted(fatti))}. '
                f'Set "gia": true when the title is about the SAME {per} as one of them, even with a different name '
                f'(e.g. Persia = Iran, Russian Empire = Russia, Ottoman Empire = Turkey, Roman Empire = Ancient Rome)' if per and fatti else '') +
               '.\nAnswer ONLY with JSON: [{"i": number, "ok": true/false, "soggetto": "...", "gia": true/false}]\n\n' + elenco)
    r = get('https://api.anthropic.com/v1/messages', json.dumps({'model': MODELLO, 'max_tokens': 8000, 'messages': [{'role': 'user', 'content': domanda}]}).encode(),
            {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    u = r.get('usage', {}); costo = (u.get('input_tokens', 0) * 1.0 + u.get('output_tokens', 0) * 5.0) / 1e6
    log(f'  lettura dei titoli: {len(cand)} titoli, {costo:.4f} $ (budget {budget} $)')
    if costo > budget:
        raise RuntimeError(f'spesa {costo:.4f} $ oltre scout_budget_giorno: nessuna riga aggiunta')
    t = ''.join(b.get('text', '') for b in r.get('content', []))
    m = re.search(r'\[.*\]', t, re.S)
    return (json.loads(m.group(0)) if m else []), costo


def colonna(h, *nomi):
    return next((n for n in nomi if n in h), None)


def canale(cfg):
    cid = str(cfg.get('channel_id') or '').strip(); filone = str(cfg.get('scout_filone') or '').strip()
    links = [x for x in re.split(r'[;,\s]+', str(cfg.get('canali_da_copiare') or '')) if x.strip()]
    if not filone or not links or (SOLO and cid != SOLO):
        return
    log('===', cid)
    budget = num(cfg.get('scout_budget_giorno'))
    if budget <= 0:
        log('  scout_budget_giorno vuota: lo scout non gira (nessuna spesa senza il tuo ok)'); return
    fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    sch, h, prod = A.righe(fid)
    c_link, c_stato = colonna(h, 'Link video', 'video_originale'), colonna(h, 'status', 'stato')
    coda = sum(1 for r in prod if str(r.get(c_stato)).strip() == 'Pronto')
    obiettivo = int(num(cfg.get('scout_coda'), 7))
    manca = obiettivo - coda
    log(f'  righe Pronto: {coda} (obiettivo {obiettivo})')
    if manca <= 0 and not PROVA:
        return
    global ESPLOSI, GIORNI, MOLT
    ESPLOSI = str(cfg.get('scout_modo') or '').strip().lower() == 'esplosi'   # vuota = i piu' visti di sempre (come prima)
    GIORNI = int(num(cfg.get('scout_giorni'), 30) or 30); MOLT = num(cfg.get('scout_moltiplicatore'), 3) or 3
    per = str(cfg.get('scout_un_video_per') or '').strip()
    gia_link = {m.group(1) for r in prod for m in [re.search(r'(?:v=|youtu\.be/)([\w-]{11})', str(r.get(c_link) or ''))] if m}
    gia_sogg = {norm(r.get('paese')) for r in prod if str(r.get('paese') or '').strip()}
    log('  soggetti gia\' fatti o in coda:', len(gia_sogg))
    mn, mx = num(cfg.get('scout_min_duration_seconds'), 300), num(cfg.get('scout_max_duration_seconds'), 5400)
    min_views = num(cfg.get('scout_min_views'), 10000); pagine = int(num(cfg.get('scout_max_pages'), 10)) or 10
    cand = []
    for l in links:
        try:
            ch = id_canale(l)
            nome, vids = video_canale(ch, pagine) if ch else ('', [])
        except Exception as e:
            log('  canale non letto', l, str(e)[:100]); continue
        lunghi = [v for v in vids if mn <= v['sec'] <= mx]
        if ESPLOSI:   # 11 nov (Giorgio OK, metodo Reed): solo i video ESPLOSI di recente = molte piu' views della mediana del loro canale
            vv = sorted(v['views'] for v in lunghi) or [0]; med = max(1, vv[len(vv) // 2])
            limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=GIORNI)).isoformat()
            for v in lunghi:
                v['volte'] = round(v['views'] / med, 1)
            buoni = [v for v in lunghi if v['pub'] >= limite and v['volte'] >= MOLT and v['views'] >= min_views and v['id'] not in gia_link]
            log(f'  {nome or l}: {len(vids)} video, mediana {med:,} views, {len(buoni)} esplosi negli ultimi {GIORNI} giorni (>= {MOLT}x la mediana)')
        else:
            buoni = [v for v in lunghi if v['views'] >= min_views and v['id'] not in gia_link]
            log(f'  {nome or l}: {len(vids)} video, {len(buoni)} candidati')
        cand += buoni
    cand.sort(key=lambda v: (v.get('volte', 0), v['views']) if ESPLOSI else v['views'], reverse=True)
    cand = cand[:200]
    if not cand:
        log('  nessun video nuovo'); return
    fatti_nomi = [str(r.get('paese')).strip() for r in prod if str(r.get('paese') or '').strip()]
    log('  gia\' fatti:', ', '.join(fatti_nomi))
    giudizi, costo = classifica(cand, filone, per, budget, set(fatti_nomi))
    scelti, presi = [], set()
    for g in sorted(giudizi, key=lambda g: (cand[int(g.get('i', 0))].get('volte', 0), cand[int(g.get('i', 0))]['views']) if str(g.get('i', '')).isdigit() and int(g['i']) < len(cand) else (0, 0), reverse=True):
        try:
            v = cand[int(g['i'])]
        except Exception:
            continue
        if not g.get('ok'):
            continue
        s = norm(g.get('soggetto')) if per else ''
        if per and (not s or s in gia_sogg or s in presi or g.get('gia')):
            continue
        presi.add(s); v['soggetto'] = str(g.get('soggetto') or '').strip(); scelti.append(v)
    scartati = sum(1 for g in giudizi if not g.get('ok'))
    log(f'  del filone: {sum(1 for g in giudizi if g.get("ok"))}, altri filoni scartati: {scartati}, nuovi soggetti: {len(scelti)}')
    for v in scelti[:max(manca, 0) or 10]:
        log(f"    {v['views']:>10,} ({v.get('volte', '-')}x) | {v['soggetto']} | {v['titolo'][:80]} | {v['canale']}")
    if PROVA or manca <= 0:
        return
    righe = []
    for v in scelti[:manca]:
        val = {c_link: f"https://www.youtube.com/watch?v={v['id']}", c_stato: 'Pronto', 'titolo_originale': v['titolo'],
               'views_at_discovery': v['views'], 'views_originale': v['views'], 'nome_canale': v['canale'], 'canale_originale': v['canale'],
               'competitor_category_id': v['cat'], 'categoria_originale': v['cat'], 'paese': v.get('soggetto', ''),
               'data_scoperta': dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')}
        righe.append([val.get(x, '') if x in val else '' for x in h])
    if righe:
        A.api(fid, 'POST', f"/values/{urllib.parse.quote(chr(39) + sch + chr(39) + '!A1')}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS", {'values': righe})
        log(f'  aggiunte {len(righe)} righe Pronto')
    os.makedirs('coach/costi', exist_ok=True)
    f = 'coach/costi/scout.tsv'; nuovo = not os.path.exists(f)
    with open(f, 'a') as o:
        if nuovo:
            o.write('data\tcanale\tcosto_dollari\tnota\n')
        o.write(f"{dt.datetime.now():%Y-%m-%d %H:%M}\t{cid}\t{costo:.4f}\t{len(righe)} righe aggiunte\n")


def main():
    _, _, canali = A.righe(A.CONFIGS)
    err = []
    for cfg in canali:
        try:
            canale(cfg)
        except Exception as e:
            log('  ERRORE', cfg.get('channel_id'), str(e)[:300]); err.append(str(cfg.get('channel_id')))
    if err:
        sys.exit('scout non riuscito per: ' + ', '.join(err))


if __name__ == '__main__':
    main()
